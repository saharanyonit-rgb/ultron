/**
 * JARVIS — Optional hand-gesture tracking.
 *
 * Adapted from the Ultron Orb UI by Sagar Tamang (MIT, see
 * THIRD_PARTY_NOTICES.md).
 *
 * This is strictly an optional enhancement. A machine with no camera is a
 * normal, fully supported configuration:
 *
 *  - The camera is probed *before* any permission prompt or network request, so
 *    a camera-less PC never triggers a browser prompt and never waits on a CDN.
 *  - MediaPipe is imported dynamically and only when tracking is requested, so
 *    it costs nothing at startup and is not a JARVIS dependency.
 *  - `start()` never rejects and never throws. Every failure is reported through
 *    `onStatus` with a human-readable reason.
 *  - A camera plugged in later is picked up automatically via the `devicechange`
 *    event, with no UI redesign required.
 */

// @ts-nocheck

const MEDIAPIPE_MODULE_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/vision_bundle.mjs';
const MEDIAPIPE_WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm';
const MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';

// MediaPipe landmark indices.
const WRIST = 0;
const THUMB_TIP = 4;
const INDEX_TIP = 8;
const MIDDLE_MCP = 9;

// Pinch hysteresis on thumb–index distance relative to hand size.
const PINCH_ON = 0.32;
const PINCH_OFF = 0.45;
const ROTATE_SPEED = 5.0;
const SMOOTHING = 0.4;

/** Lifecycle states. `unavailable` is an expected outcome, not a fault. */
export const TRACK = {
  idle: 'idle',
  starting: 'starting',
  active: 'active',
  unavailable: 'unavailable',
  denied: 'denied',
  error: 'error',
};

export const MODE_LABEL = {
  idle: 'STANDBY',
  spin: 'SPIN',
  zoom: 'ZOOM',
};

let cachedModule = null;

function dist2d(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/**
 * Detect whether this machine has a usable camera.
 * Never prompts for permission and never throws.
 *
 * @returns {Promise<{available: boolean, count: number, reason: string|null}>}
 */
export async function probeCamera() {
  const media = typeof navigator !== 'undefined' ? navigator.mediaDevices : null;
  if (!media || typeof media.enumerateDevices !== 'function') {
    return { available: false, count: 0, reason: 'MEDIA DEVICES UNSUPPORTED' };
  }
  try {
    const devices = await media.enumerateDevices();
    // Device *kind* is reported without permission, so this works on a PC that
    // has never been granted camera access. Only labels stay hidden.
    const cameras = devices.filter((d) => d.kind === 'videoinput');
    if (!cameras.length) {
      return { available: false, count: 0, reason: 'CAMERA NOT FOUND' };
    }
    return { available: true, count: cameras.length, reason: null };
  } catch (err) {
    // If enumeration is blocked we cannot prove absence; let the caller try.
    return { available: true, count: 0, reason: null, uncertain: true };
  }
}

/** Subscribe to camera hot-plug events. Returns an unsubscribe function. */
export function onCameraChange(handler) {
  const media = typeof navigator !== 'undefined' ? navigator.mediaDevices : null;
  if (!media || typeof media.addEventListener !== 'function') return () => {};
  media.addEventListener('devicechange', handler);
  return () => media.removeEventListener('devicechange', handler);
}

export class HandTracker {
  constructor(video, overlay, callbacks = {}) {
    this.video = video;
    this.overlay = overlay;
    this.callbacks = callbacks;
    this.landmarker = null;
    this.stream = null;
    this.rafId = 0;
    this.running = false;
    this.lastVideoTime = -1;
    this.handStates = new Map();
    this.prevMode = 'idle';
    this.prevSpinGrab = null;
    this.prevZoomDist = null;
    this.lastStatus = { state: TRACK.idle, hands: 0, mode: 'idle', reason: null };
  }

  get active() {
    return this.running;
  }

  emit(state, extra = {}) {
    this.lastStatus = { ...this.lastStatus, ...extra, state };
    if (typeof this.callbacks.onStatus === 'function') {
      try {
        this.callbacks.onStatus(this.lastStatus);
      } catch (err) {
        console.warn('[orb] tracker status handler failed', err);
      }
    }
  }

  /**
   * Attempt to start tracking.
   * Always resolves; never rejects, never throws.
   * @returns {Promise<boolean>} true when tracking is running.
   */
  async start() {
    if (this.running) return true;
    this.emit(TRACK.starting, { reason: null });

    // 1. Refuse early when there is provably no camera. No prompt, no download.
    const probe = await probeCamera();
    if (!probe.available) {
      this.emit(TRACK.unavailable, { reason: probe.reason || 'CAMERA NOT FOUND', hands: 0, mode: 'idle' });
      return false;
    }

    // 2. Acquire the camera, translating every failure into a readable status.
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
        audio: false,
      });
    } catch (err) {
      this.stream = null;
      this.emit(TRACK.unavailable, { reason: describeCameraError(err), hands: 0, mode: 'idle' });
      return false;
    }

    try {
      this.video.srcObject = this.stream;
      await this.video.play();
    } catch (err) {
      this.releaseStream();
      this.emit(TRACK.error, { reason: 'CAMERA FEED BLOCKED', hands: 0, mode: 'idle' });
      return false;
    }

    // 3. Load the gesture engine on demand. A network failure must not be fatal.
    let vision;
    try {
      vision = cachedModule || await import(/* @vite-ignore */ MEDIAPIPE_MODULE_URL);
      cachedModule = vision;
    } catch (err) {
      this.releaseStream();
      this.emit(TRACK.unavailable, { reason: 'GESTURE ENGINE OFFLINE', hands: 0, mode: 'idle' });
      return false;
    }

    try {
      const fileset = await vision.FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_URL);
      const options = {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: 'GPU' },
        runningMode: 'VIDEO',
        numHands: 2,
        minHandDetectionConfidence: 0.6,
        minHandPresenceConfidence: 0.6,
        minTrackingConfidence: 0.6,
      };
      try {
        this.landmarker = await vision.HandLandmarker.createFromOptions(fileset, options);
      } catch {
        // Some GPUs reject the GPU delegate; CPU always works but is slower.
        this.landmarker = await vision.HandLandmarker.createFromOptions(fileset, {
          ...options,
          baseOptions: { ...options.baseOptions, delegate: 'CPU' },
        });
      }
    } catch (err) {
      this.releaseStream();
      this.emit(TRACK.unavailable, { reason: 'HAND MODEL UNAVAILABLE', hands: 0, mode: 'idle' });
      return false;
    }

    this.running = true;
    this.lastVideoTime = -1;
    this.emit(TRACK.active, { reason: null, hands: 0, mode: 'idle' });
    this.loop();
    return true;
  }

  releaseStream() {
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    if (this.video) this.video.srcObject = null;
  }

  stop() {
    this.running = false;
    cancelAnimationFrame(this.rafId);
    if (this.landmarker) {
      try {
        this.landmarker.close();
      } catch {
        /* already closed */
      }
      this.landmarker = null;
    }
    this.releaseStream();
    this.handStates.clear();
    this.prevMode = 'idle';
    this.prevSpinGrab = null;
    this.prevZoomDist = null;
    if (this.overlay) {
      const ctx = this.overlay.getContext('2d');
      if (ctx) ctx.clearRect(0, 0, this.overlay.width, this.overlay.height);
    }
    this.emit(TRACK.idle, { hands: 0, mode: 'idle', reason: null });
  }

  loop = () => {
    if (!this.running) return;
    this.rafId = requestAnimationFrame(this.loop);

    if (!this.landmarker || !this.video || this.video.readyState < 2) return;
    if (this.video.currentTime === this.lastVideoTime) return;
    this.lastVideoTime = this.video.currentTime;

    let result;
    try {
      result = this.landmarker.detectForVideo(this.video, performance.now());
    } catch {
      return; // a dropped frame is not worth tearing the session down
    }
    if (!result) return;

    const labels = (result.handedness || []).map((h) => (h[0] && h[0].categoryName) || '?');
    this.processHands(result.landmarks || [], labels);
    this.drawOverlay(result.landmarks || []);
  };

  processHands(landmarks, labels) {
    const pinchedGrabs = [];
    const seen = new Set();

    landmarks.forEach((lm, i) => {
      const label = labels[i] || `hand-${i}`;
      seen.add(label);

      const handScale = dist2d(lm[WRIST], lm[MIDDLE_MCP]);
      if (handScale < 1e-6) return;
      const pinchRatio = dist2d(lm[THUMB_TIP], lm[INDEX_TIP]) / handScale;

      // Mirrored so hand-right appears on screen-right.
      const raw = {
        x: 1 - (lm[THUMB_TIP].x + lm[INDEX_TIP].x) / 2,
        y: (lm[THUMB_TIP].y + lm[INDEX_TIP].y) / 2,
      };

      let state = this.handStates.get(label);
      if (!state) {
        state = { pinching: false, grab: raw };
        this.handStates.set(label, state);
      }

      if (state.pinching && pinchRatio > PINCH_OFF) state.pinching = false;
      else if (!state.pinching && pinchRatio < PINCH_ON) state.pinching = true;

      state.grab = {
        x: state.grab.x + (raw.x - state.grab.x) * SMOOTHING,
        y: state.grab.y + (raw.y - state.grab.y) * SMOOTHING,
      };

      if (state.pinching) pinchedGrabs.push(state.grab);
    });

    for (const key of Array.from(this.handStates.keys())) {
      if (!seen.has(key)) this.handStates.delete(key);
    }

    const mode = pinchedGrabs.length >= 2 ? 'zoom' : pinchedGrabs.length === 1 ? 'spin' : 'idle';

    if (mode !== this.prevMode) {
      this.prevSpinGrab = null;
      this.prevZoomDist = null;
      this.prevMode = mode;
    }

    if (mode === 'spin') {
      const grab = pinchedGrabs[0];
      if (this.prevSpinGrab) {
        const dx = grab.x - this.prevSpinGrab.x;
        const dy = grab.y - this.prevSpinGrab.y;
        if (Math.abs(dx) > 1e-4 || Math.abs(dy) > 1e-4) {
          this.callbacks.onRotate?.(dx * ROTATE_SPEED, dy * ROTATE_SPEED);
        }
      }
      this.prevSpinGrab = grab;
    } else if (mode === 'zoom') {
      const d = Math.hypot(
        pinchedGrabs[0].x - pinchedGrabs[1].x,
        pinchedGrabs[0].y - pinchedGrabs[1].y,
      );
      if (this.prevZoomDist && d > 1e-4) {
        // Spreading hands apart gives a factor < 1, moving the camera closer.
        const factor = Math.min(1.18, Math.max(0.85, this.prevZoomDist / d));
        this.callbacks.onZoom?.(factor);
      }
      this.prevZoomDist = d;
    }

    this.pushStatus(landmarks.length, mode);
  }

  pushStatus(hands, mode) {
    if (hands === this.lastStatus.hands && mode === this.lastStatus.mode) return;
    this.lastStatus = { ...this.lastStatus, hands, mode, state: TRACK.active, reason: null };
    try {
      this.callbacks.onStatus?.(this.lastStatus);
    } catch (err) {
      console.warn('[orb] tracker status handler failed', err);
    }
  }

  drawOverlay(landmarks) {
    if (!this.overlay) return;
    const ctx = this.overlay.getContext('2d');
    if (!ctx) return;
    const { width, height } = this.overlay;
    ctx.clearRect(0, 0, width, height);

    for (const lm of landmarks) {
      const thumb = lm[THUMB_TIP];
      const index = lm[INDEX_TIP];
      // The overlay sits on the mirrored preview, so mirror x here too.
      const tx = (1 - thumb.x) * width;
      const ty = thumb.y * height;
      const ix = (1 - index.x) * width;
      const iy = index.y * height;

      const handScale = dist2d(lm[WRIST], lm[MIDDLE_MCP]);
      const pinched = handScale > 1e-6 && dist2d(thumb, index) / handScale < PINCH_ON;

      ctx.strokeStyle = pinched ? '#ffcc66' : 'rgba(255,170,48,0.5)';
      ctx.lineWidth = pinched ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      ctx.lineTo(ix, iy);
      ctx.stroke();

      ctx.fillStyle = pinched ? '#ffcc66' : 'rgba(255,170,48,0.7)';
      for (const [x, y] of [[tx, ty], [ix, iy]]) {
        ctx.beginPath();
        ctx.arc(x, y, pinched ? 5 : 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
}

/** Turn a getUserMedia rejection into an operator-readable phrase. */
function describeCameraError(err) {
  const name = err && err.name ? err.name : '';
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'CAMERA ACCESS DENIED';
  if (name === 'NotFoundError' || name === 'OverconstrainedError' || name === 'DevicesNotFoundError') return 'CAMERA NOT FOUND';
  if (name === 'NotReadableError' || name === 'TrackStartError') return 'CAMERA IN USE BY ANOTHER APP';
  return 'CAMERA UNAVAILABLE';
}
