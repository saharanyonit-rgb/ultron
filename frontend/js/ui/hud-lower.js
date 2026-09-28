/**
 * JARVIS — Lower deck: acoustic radar (real microphone spectrum), satellite
 * uplink globe (real network telemetry, decorative orbit), and the CPU
 * history sparkline.
 */

import { $, setText, setClass } from '../lib/dom.js';
import { on } from '../lib/bus.js';
import { get } from '../core/store.js';
import { setAudioIntensity } from './hud-core.js';

/* ═══════════════════════════════════════════════════════════════════
   ACOUSTIC SCAN — real microphone spectrum via Web Audio
   ═══════════════════════════════════════════════════════════════════ */
const Radar = {
  canvas: null,
  ctx: null,
  stream: null,
  audioCtx: null,
  analyser: null,
  raf: null,
  data: null,
  smooth: 0,
  running: false,
  available: null, // null = untested, false = denied/unavailable, true = live
  bound: false,

  /** Size the backing store. Safe to call repeatedly (e.g. on resize). */
  resize() {
    this.canvas = $('#radar-canvas');
    if (!this.canvas) return false;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const size = this.canvas.clientWidth || 84;
    this.canvas.width = size * dpr;
    this.canvas.height = size * dpr;
    this.ctx = this.canvas.getContext('2d');
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.size = size;
    return true;
  },

  init() {
    if (!this.resize()) return;

    // Clicking the radar is an explicit opt-in to microphone access.
    // Listeners are bound exactly once, no matter how often init() runs.
    if (!this.bound) {
      this.bound = true;
      const host = $('#radar');
      if (host) {
        host.style.cursor = 'pointer';
        host.setAttribute('role', 'button');
        host.setAttribute('tabindex', '0');
        host.setAttribute('aria-label', 'Acoustic scan — activate to enable microphone spectrum');
        const toggle = () => (this.running ? this.stop('MIC RELEASED') : this.start());
        host.addEventListener('click', toggle);
        host.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggle();
          }
        });
      }
    }
    this.renderIdle();
  },

  async start() {
    if (this.running) return true;
    if (!navigator.mediaDevices?.getUserMedia || typeof AudioContext === 'undefined') {
      this.fail('MIC UNAVAILABLE', 'This browser exposes no microphone API');
      return false;
    }
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
    } catch (err) {
      const denied = err && (err.name === 'NotAllowedError' || err.name === 'SecurityError');
      this.fail(
        denied ? 'MIC DENIED' : 'MIC UNAVAILABLE',
        denied ? 'Microphone permission was refused' : 'No capture device could be opened',
      );
      return false;
    }

    const Ctx = window.AudioContext || window.webkitAudioContext;
    this.audioCtx = new Ctx();
    const source = this.audioCtx.createMediaStreamSource(this.stream);
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 1024;
    this.analyser.smoothingTimeConstant = 0.72;
    source.connect(this.analyser);
    this.data = new Uint8Array(this.analyser.frequencyBinCount);

    this.running = true;
    this.available = true;
    setClass($('#radar'), 'is-offline', false);
    setText($('#scan-state-text'), 'SCANNING');
    setText($('#scan-note'), 'Live microphone spectrum');
    this.loop();
    return true;
  },

  stop(reason = 'STANDBY') {
    this.running = false;
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = null;
    if (this.stream) {
      for (const track of this.stream.getTracks()) track.stop();
      this.stream = null;
    }
    if (this.audioCtx) {
      this.audioCtx.close().catch(() => {});
      this.audioCtx = null;
    }
    this.analyser = null;
    setClass($('#radar'), 'is-offline', true);
    setText($('#scan-state-text'), reason);
    setText($('#scan-note'), 'Microphone released');
    setText($('#scan-contacts'), '--');
    setText($('#scan-peak'), '--');
    setAudioIntensity(0);
    this.renderIdle();
  },

  fail(stateLabel, note) {
    this.available = false;
    setClass($('#radar'), 'is-offline', true);
    setText($('#scan-state-text'), stateLabel);
    setText($('#scan-note'), note);
    setText($('#scan-contacts'), '--');
    setText($('#scan-peak'), '--');
    this.renderIdle();
  },

  loop() {
    if (!this.running || !this.analyser) return;
    this.analyser.getByteFrequencyData(this.data);

    const bins = this.data.length;
    // Human-audible band only (roughly 40 Hz – 8 kHz of the 48 kHz FFT).
    const nyquist = (this.audioCtx?.sampleRate || 48000) / 2;
    const binHz = nyquist / bins;
    const startBin = Math.max(1, Math.floor(40 / binHz));
    const endBin = Math.min(bins - 1, Math.floor(8000 / binHz));

    let peakValue = 0;
    let peakBin = startBin;
    let contacts = 0;
    const threshold = 96; // out of 255 — a genuine spectral peak, not noise
    for (let i = startBin; i <= endBin; i += 1) {
      const v = this.data[i];
      if (v > threshold) contacts += 1;
      if (v > peakValue) {
        peakValue = v;
        peakBin = i;
      }
    }

    const peakHz = Math.round(peakBin * binHz);
    setText($('#scan-peak'), peakValue > 40 ? `${peakHz} Hz` : '--');
    setText($('#scan-contacts'), peakValue > 40 ? String(contacts) : '0');

    // RMS-ish intensity for the core waveform — real, not simulated.
    let sum = 0;
    const step = Math.max(1, Math.floor((endBin - startBin) / 48));
    for (let i = startBin; i <= endBin; i += step) sum += this.data[i];
    const avg = sum / ((endBin - startBin) / step) / 255;
    this.smooth = this.smooth * 0.7 + avg * 0.3;
    setAudioIntensity(Math.min(1, this.smooth * 2.2));

    this.draw(peakValue);
    this.raf = requestAnimationFrame(() => this.loop());
  },

  draw(peak) {
    const ctx = this.ctx;
    if (!ctx) return;
    const size = this.size;
    const c = size / 2;
    const r = size * 0.44;

    ctx.clearRect(0, 0, size, size);

    // grid rings
    ctx.strokeStyle = 'rgba(0,212,255,0.10)';
    ctx.lineWidth = 1;
    for (let i = 1; i <= 3; i += 1) {
      ctx.beginPath();
      ctx.arc(c, c, (r * i) / 3, 0, Math.PI * 2);
      ctx.stroke();
    }
    // crosshair
    ctx.beginPath();
    ctx.moveTo(c - r, c); ctx.lineTo(c + r, c);
    ctx.moveTo(c, c - r); ctx.lineTo(c, c + r);
    ctx.stroke();

    // sweep wedge
    const angle = (Date.now() / 2400) * Math.PI * 2;
    const grad = ctx.createConicGradient
      ? ctx.createConicGradient(angle - Math.PI / 2, c, c)
      : null;
    if (grad) {
      grad.addColorStop(0, 'rgba(0,212,255,0.32)');
      grad.addColorStop(0.14, 'rgba(0,212,255,0)');
      grad.addColorStop(1, 'rgba(0,212,255,0)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(c, c);
      ctx.arc(c, c, r, angle - Math.PI / 2, angle - Math.PI / 2 + Math.PI * 2);
      ctx.fill();
    }

    // live spectrum
    if (this.data) {
      const bins = this.data.length;
      const nyquist = (this.audioCtx?.sampleRate || 48000) / 2;
      const binHz = nyquist / bins;
      const endBin = Math.min(bins - 1, Math.floor(8000 / binHz));
      const startBin = Math.max(1, Math.floor(40 / binHz));
      const span = endBin - startBin;
      const bars = 40;
      ctx.fillStyle = peak > 96 ? 'rgba(0,212,255,0.85)' : 'rgba(0,160,200,0.55)';
      for (let i = 0; i < bars; i += 1) {
        const idx = startBin + Math.floor((i / bars) * span);
        const v = (this.data[idx] || 0) / 255;
        const h = Math.max(1, v * r * 0.92);
        const x = c - r + (i / bars) * r * 2;
        ctx.fillRect(x, c + r - h, Math.max(1, (r * 2) / bars - 1), h);
      }
    }

    // contact blips from genuine peaks
    if (this.data && peak > 96) {
      ctx.fillStyle = 'rgba(0,255,200,0.9)';
      const bins = this.data.length;
      const binHz = ((this.audioCtx?.sampleRate || 48000) / 2) / bins;
      for (let i = 1; i < bins; i += 1) {
        if (this.data[i] > 150) {
          const hz = i * binHz;
          if (hz < 40 || hz > 8000) continue;
          const t = hz / 8000;
          const x = c - r + t * r * 2;
          const y = c - Math.min(r * 0.85, (this.data[i] / 255) * r);
          ctx.beginPath();
          ctx.arc(x, y, 1.2, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }
  },

  renderIdle() {
    const ctx = this.ctx;
    if (!ctx) return;
    const size = this.size;
    const c = size / 2;
    const r = size * 0.44;
    ctx.clearRect(0, 0, size, size);
    ctx.strokeStyle = 'rgba(0,212,255,0.08)';
    ctx.lineWidth = 1;
    for (let i = 1; i <= 3; i += 1) {
      ctx.beginPath();
      ctx.arc(c, c, (r * i) / 3, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.moveTo(c - r, c); ctx.lineTo(c + r, c);
    ctx.moveTo(c, c - r); ctx.lineTo(c, c + r);
    ctx.stroke();
    ctx.fillStyle = 'rgba(0,212,255,0.28)';
    ctx.beginPath();
    ctx.arc(c, c, 2, 0, Math.PI * 2);
    ctx.fill();
  },
};

/* ═══════════════════════════════════════════════════════════════════
   SATELLITE UPLINK — real network telemetry, decorative orbit
   ═══════════════════════════════════════════════════════════════════ */
function renderUplink() {
  const { link, network, latencyMs } = get();
  const stateNode = $('#uplink-state');

  if (link === 'offline') setText(stateNode, 'OFFLINE');
  else if (link === 'connecting') setText(stateNode, 'CONNECTING');
  else if (network?.connected === true) setText(stateNode, 'LOCKED');
  else if (network?.connected === false) setText(stateNode, 'NO ROUTE');
  else setText(stateNode, 'SYNCING');

  setText($('#uplink-host'), network?.hostname ? network.hostname.toUpperCase() : 'UNKNOWN');
  setText($('#uplink-ip'), network?.local_ip || 'UNKNOWN');
  setText(
    $('#uplink-ping'),
    typeof latencyMs === 'number' ? `${latencyMs}ms` : network?.latency_ms != null ? `${network.latency_ms}ms` : '--',
  );
}

/* ═══════════════════════════════════════════════════════════════════
   CPU HISTORY SPARKLINE
   ═══════════════════════════════════════════════════════════════════ */
const Spark = {
  canvas: null,
  ctx: null,
  w: 0,
  h: 0,

  init() {
    this.canvas = $('#spark-canvas');
    if (!this.canvas) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const rect = this.canvas.getBoundingClientRect();
    this.w = Math.max(80, Math.round(rect.width || 168));
    this.h = Math.max(20, Math.round(rect.height || 26));
    this.canvas.width = this.w * dpr;
    this.canvas.height = this.h * dpr;
    this.ctx = this.canvas.getContext('2d');
    this.ctx.scale(dpr, dpr);
    this.draw();
  },

  draw() {
    const ctx = this.ctx;
    if (!ctx) return;
    const { w, h } = this;
    const history = get().cpuHistory;

    ctx.clearRect(0, 0, w, h);

    // baseline grid
    ctx.strokeStyle = 'rgba(0,212,255,0.07)';
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i += 1) {
      const y = (h / 4) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    const points = history.map((v, i) => ({
      x: (i / (history.length - 1)) * w,
      y: v === null ? null : h - (Math.min(100, v) / 100) * (h - 2) - 1,
    }));

    // line
    ctx.beginPath();
    let started = false;
    let lastY = h;
    for (const p of points) {
      if (p.y === null) continue;
      if (!started) {
        ctx.moveTo(p.x, p.y);
        started = true;
      } else ctx.lineTo(p.x, p.y);
      lastY = p.y;
    }
    if (started) {
      const current = points[points.length - 1].y;
      ctx.strokeStyle = current !== null && current < h * 0.3 ? 'rgba(255,170,0,0.9)' : 'rgba(0,212,255,0.75)';
      ctx.lineWidth = 1;
      ctx.stroke();

      // fill under the curve
      const firstX = points.find((p) => p.y !== null)?.x ?? 0;
      ctx.lineTo(w, h);
      ctx.lineTo(firstX, h);
      ctx.closePath();
      ctx.fillStyle = 'rgba(0,212,255,0.06)';
      ctx.fill();

      // leading dot
      ctx.beginPath();
      ctx.arc(w - 1, lastY, 1.6, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0,212,255,0.95)';
      ctx.fill();
    } else {
      ctx.fillStyle = 'rgba(90,122,130,0.7)';
      ctx.font = '8px ui-monospace, monospace';
      ctx.fillText('AWAITING TELEMETRY', 6, h / 2 + 3);
    }
  },
};

/* ── Boot ─────────────────────────────────────────────────────────── */
export function initLowerDeck() {
  Radar.init();
  Spark.init();
  renderUplink();

  on('telemetry', ({ key }) => {
    if (key === 'network') renderUplink();
    if (key === 'metrics') Spark.draw();
  });
  on('link', renderUplink);
  on('cpu:sample', () => Spark.draw());

  // Resize only re-scales the backing store; it must never re-bind
  // listeners or restart the microphone stream.
  let resizeTimer = null;
  window.addEventListener('resize', () => {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      Spark.init();
      Radar.resize();
      if (!Radar.running) Radar.renderIdle();
    }, 150);
  });

  on('teardown', () => Radar.stop('MIC RELEASED'));
}

export { Radar, Spark };
