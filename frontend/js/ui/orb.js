/**
 * JARVIS — Orb backdrop controller.
 *
 * The holographic orb is the main screen. It renders as a fixed
 * backdrop and the command console floats above it as glass, so the
 * orb is always present rather than a separate view the operator has
 * to open. `body[data-ui]` selects the layout:
 *
 *   "orb"      — orb backdrop + glass console. The default.
 *   "console"  — the original flat dashboard. The automatic fallback
 *                when WebGL is unavailable or motion is reduced, and
 *                one keypress or one toolbar button away.
 *
 * The scene and the hand tracker are still imported dynamically, so a
 * machine without a GPU never downloads ~800 KB of Three.js: the import
 * simply never happens, because the layout starts in "console".
 *
 * The orb is driven by state JARVIS already produces:
 *   body[data-core-state]  -> idle | listening | processing | executing |
 *                             speaking | error | offline   (ui/hud-core.js)
 *   store metrics          -> real CPU / RAM load drives motion intensity
 *
 * Nothing here fabricates backend data and nothing here is required for the
 * rest of the interface to work.
 */

import { $, setText, setClass } from '../lib/dom.js';
import { on } from '../lib/bus.js';
import { get } from '../core/store.js';
import * as log from '../core/activity-log.js';
import * as toast from '../core/toast.js';

/** Mirrors CORE_STATES in ui/hud-core.js, plus the operator-facing phrasing. */
const STATE_LABEL = {
  idle: 'STANDBY',
  listening: 'LISTENING',
  processing: 'PROCESSING',
  executing: 'EXECUTING',
  speaking: 'RESPONDING',
  error: 'FAULT',
  offline: 'BACKEND OFFLINE',
};

const GESTURE_LABEL = {
  starting: 'INITIALISING GESTURES…',
  active: 'GESTURES ACTIVE',
  idle: 'GESTURES OFF',
};

/** Layout modes. Kept as a set so a corrupt preference cannot invent one. */
const MODE_ORB = 'orb';
const MODE_CONSOLE = 'console';
const MODES = new Set([MODE_ORB, MODE_CONSOLE]);
const PREF_KEY = 'jarvis.ui.mode';

let scene = null;
let tracker = null;
let trackerApi = null;
let booting = false;
let gesturesWanted = false;
let cameraProbe = null;
let stateObserver = null;
let releaseCameraWatch = null;
let mode = MODE_ORB;

/* ── Public API ──────────────────────────────────────────────────── */

/** Choose the starting layout, wire the toggle and mount if appropriate. */
export function initOrb() {
  mode = readPreferredMode();

  const toggle = $('#btn-orb');
  if (toggle) toggle.addEventListener('click', () => setMode(mode === MODE_ORB ? MODE_CONSOLE : MODE_ORB));

  applyMode(mode);

  window.addEventListener('keydown', onKeyDown);
  on('teardown', disposeOrb);
}

/** The layout JARVIS is currently in. */
export function getOrbMode() {
  return mode;
}

/** True once the scene is actually rendering. */
export function isOrbMounted() {
  return scene !== null;
}

/* ── Layout mode ─────────────────────────────────────────────────── */

function readPreferredMode() {
  const stored = localStorage.getItem(PREF_KEY);
  if (MODES.has(stored)) return stored;
  // Motion-sensitive operators get the static dashboard by default: the orb
  // animates continuously and offers no reduced-motion variant.
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return MODE_CONSOLE;
  return MODE_ORB;
}

function applyMode(next) {
  document.body.dataset.ui = next;
  syncToggle(next);

  if (next === MODE_ORB) {
    const view = $('#orb-view');
    if (view) view.hidden = false;
    void mountOrb();
  } else {
    stopGestures();
    disposeOrb();
    const view = $('#orb-view');
    if (view) view.hidden = true;
  }
}

function setMode(next) {
  if (!MODES.has(next) || next === mode) return;
  mode = next;
  try {
    localStorage.setItem(PREF_KEY, next);
  } catch {
    // A blocked storage quota only costs us the remembered preference.
  }
  applyMode(next);
  log.push('system', next === MODE_ORB ? 'Orb backdrop layout active' : 'Classic console layout active');
}

function syncToggle(next) {
  const toggle = $('#btn-orb');
  if (!toggle) return;
  const orb = next === MODE_ORB;
  toggle.setAttribute('aria-pressed', orb ? 'true' : 'false');
  const label = orb ? 'Switch to the classic console layout' : 'Switch to the orb backdrop layout';
  toggle.setAttribute('aria-label', label);
  toggle.setAttribute('data-tooltip', label.toUpperCase());
  setClass(toggle, 'is-active', orb);
}

/* ── Scene lifecycle ─────────────────────────────────────────────── */

/** Create the WebGL scene. Safe to call repeatedly; only the first wins. */
async function mountOrb() {
  if (scene || booting) return;
  const view = $('#orb-view');
  const root = $('#orb-root');
  if (!view || !root) return;

  booting = true;
  view.dataset.render = 'pending';
  view.setAttribute('aria-hidden', 'false');

  try {
    // Deferred so the ~800 KB of Three.js is fetched only when it is
    // actually going to be shown.
    const [{ createOrbScene }, trackerModule] = await Promise.all([
      import('./orb-scene.js'),
      import('./hand-tracker.js'),
    ]);
    trackerApi = trackerModule;

    const result = createOrbScene(root);
    if (!result.ok) {
      onOrbUnavailable(result.reason || 'WEBGL UNAVAILABLE');
      return;
    }

    scene = result;
    view.dataset.render = 'ok';
    scene.setState(document.body.dataset.coreState || 'idle');
    scene.setLoad(readLoad());

    bindControls();
    bindCoreState();
    bindLoad();
    startCameraWatch();
    void refreshGestureStatus();

    log.push('system', 'Orb backdrop online');
  } catch (err) {
    // A failure here must never break the HUD that is already running.
    onOrbUnavailable(err?.message || 'ORB FAILED TO LOAD');
  } finally {
    booting = false;
  }
}

/**
 * The orb could not render. Fall back to the classic console rather than
 * leaving the operator staring at an empty backdrop, and say why once.
 */
function onOrbUnavailable(reason) {
  log.push('warning', `Orb backdrop unavailable: ${reason}`);
  toast.warning('ORB BACKDROP OFFLINE', `${reason} — using the classic console layout.`);

  // A machine with no GPU will never succeed, so stop retrying on every
  // reload. This only clears when the operator picks the orb explicitly.
  try {
    localStorage.setItem(PREF_KEY, MODE_CONSOLE);
  } catch {
    // Non-fatal; the layout is still switched for this session.
  }
  mode = MODE_CONSOLE;
  applyMode(MODE_CONSOLE);
}

export function disposeOrb() {
  if (stateObserver) {
    stateObserver.disconnect();
    stateObserver = null;
  }
  if (releaseCameraWatch) {
    releaseCameraWatch();
    releaseCameraWatch = null;
  }
  if (scene) {
    scene.dispose();
    scene = null;
  }
  const view = $('#orb-view');
  if (view) view.dataset.render = '';
}

/* ── Keyboard ────────────────────────────────────────────────────── */

function onKeyDown(event) {
  if (mode !== MODE_ORB || !scene) return;
  const tag = document.activeElement?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable) return;
  if (event.metaKey || event.ctrlKey || event.altKey) return;

  switch (event.key) {
    case '+':
    case '=':
      scene.zoomIn();
      break;
    case '-':
    case '_':
      scene.zoomOut();
      break;
    case 'r':
    case 'R':
      scene.resetView();
      break;
    case 'g':
    case 'G':
      toggleGestures();
      break;
    case 'Escape':
      setMode(MODE_CONSOLE);
      break;
    default:
      return;
  }
  event.preventDefault();
}

/* ── JARVIS state -> orb ─────────────────────────────────────────── */

function bindCoreState() {
  if (stateObserver) return;
  // hud-core.js publishes state on body[data-core-state]; observe it so the orb
  // stays in step with the rest of the HUD without duplicating that logic.
  stateObserver = new MutationObserver(() => {
    const next = document.body.dataset.coreState || 'idle';
    scene?.setState(next);
    syncStateLabel(next);
  });
  stateObserver.observe(document.body, { attributes: true, attributeFilter: ['data-core-state'] });
}

function syncStateLabel(state) {
  const resolved = state || document.body.dataset.coreState || 'idle';
  setText($('#orb-state'), STATE_LABEL[resolved] || STATE_LABEL.idle);
}

/** Real machine load, averaged across CPU and RAM. Null when unknown. */
function readLoad() {
  const m = get().metrics;
  const cpu = typeof m?.cpu_percent === 'number' ? m.cpu_percent : null;
  const ram = typeof m?.ram_percent === 'number' ? m.ram_percent : null;
  if (cpu === null && ram === null) return 0;
  const values = [cpu, ram].filter((v) => v !== null);
  return values.reduce((a, b) => a + b, 0) / values.length / 100;
}

function bindLoad() {
  on('telemetry:metrics', () => scene?.setLoad(readLoad()));
}

/* ── Optional gestures ───────────────────────────────────────────── */

function bindControls() {
  const once = (id, fn) => {
    const node = $(id);
    if (node) node.addEventListener('click', fn);
  };
  once('orb-zoom-in', () => scene?.zoomIn());
  once('orb-zoom-out', () => scene?.zoomOut());
  once('orb-reset', () => scene?.resetView());
  once('orb-gestures', () => toggleGestures());
}

function startCameraWatch() {
  if (!trackerApi || releaseCameraWatch) return;
  // A webcam connected later is picked up without any UI change.
  releaseCameraWatch = trackerApi.onCameraChange(() => {
    if (gesturesWanted) void startGestures();
    else void refreshGestureStatus();
  });
}

async function refreshGestureStatus() {
  if (!trackerApi) return;
  cameraProbe = await trackerApi.probeCamera();
  renderGestureStatus({
    state: cameraProbe.available ? 'idle' : 'unavailable',
    reason: cameraProbe.reason,
    hands: 0,
    mode: 'idle',
  });
}

async function toggleGestures() {
  if (gesturesWanted) {
    stopGestures();
    return;
  }
  gesturesWanted = true;
  await startGestures();
}

async function startGestures() {
  if (!trackerApi || !scene) return;
  const video = $('#orb-camera-video');
  const overlay = $('#orb-camera-overlay');
  if (!video || !overlay) return;

  if (!tracker) {
    tracker = new trackerApi.HandTracker(video, overlay, {
      onRotate: (dTheta, dPhi) => scene?.rotateBy(dTheta, dPhi),
      onZoom: (factor) => scene?.zoomBy(factor),
      onStatus: renderGestureStatus,
    });
  }

  const button = $('#orb-gestures');
  setText(button, GESTURE_LABEL.starting);
  if (button) button.disabled = true;

  const started = await tracker.start();

  if (button) button.disabled = false;
  if (!started) {
    // Keep the operator's intent only when a camera is genuinely present, so a
    // later hot-plug starts tracking by itself but a denied prompt is not
    // retried behind their back.
    gesturesWanted = cameraProbe?.available === true;
  }
}

function stopGestures() {
  gesturesWanted = false;
  if (tracker) {
    tracker.stop();
    tracker = null;
  }
  setClass($('#orb-camera'), 'visible', false);
  renderGestureStatus({ state: 'idle', reason: null, hands: 0, mode: 'idle' });
}

/**
 * Render gesture state as a small, non-blocking line of text.
 * A missing camera is a normal status, never an error dialog.
 */
function renderGestureStatus(status) {
  const node = $('#orb-gesture-status');
  const button = $('#orb-gestures');
  const panel = $('#orb-camera');
  const camState = $('#orb-camera-state');

  if (node) node.dataset.state = status.state;

  switch (status.state) {
    case 'active':
      setText(
        node,
        status.hands > 0
          ? `${status.hands} HAND${status.hands > 1 ? 'S' : ''} · ${trackerApi.MODE_LABEL[status.mode] || 'STANDBY'}`
          : 'GESTURES ACTIVE · SHOW YOUR HANDS',
      );
      setText(camState, status.hands > 0 ? `${status.hands} HAND${status.hands > 1 ? 'S' : ''}` : 'SHOW HANDS');
      setClass(panel, 'visible', true);
      setText(button, 'GESTURES ON');
      if (button) button.setAttribute('aria-pressed', 'true');
      break;

    case 'starting':
      setText(node, GESTURE_LABEL.starting);
      setText(button, GESTURE_LABEL.starting);
      break;

    case 'unavailable':
    case 'denied':
    case 'error':
      setText(node, `GESTURES UNAVAILABLE — ${status.reason || 'CAMERA NOT FOUND'}`);
      setText(button, 'GESTURES UNAVAILABLE');
      setClass(panel, 'visible', false);
      if (button) {
        button.setAttribute('aria-pressed', 'false');
        button.title = status.reason
          ? `Hand gestures need a camera. ${status.reason}. Plug one in and this becomes available.`
          : 'Hand gestures need a camera.';
      }
      log.push('info', `Hand gestures unavailable: ${status.reason || 'camera not found'}`);
      break;

    default:
      setText(node, gesturesWanted
        ? 'GESTURES OFF · NO CAMERA DETECTED'
        : 'GESTURES OFF · PRESS G IF A CAMERA IS CONNECTED');
      setText(button, 'GESTURES OFF');
      if (button) {
        button.setAttribute('aria-pressed', 'false');
        button.title = 'Hand gestures are optional and need a camera.';
      }
      break;
  }
}
