/**
 * JARVIS — Central core.
 *
 * A live SVG instrument: rotating rings, arcs, tick band, an audio-reactive
 * halo and a real waveform driven by microphone input. Core state is bound to
 * `body[data-core-state]` so CSS handles most of the visual response and we
 * only touch the DOM when a value actually changes.
 */

import { $, setText, setClass, prefersReducedMotion } from '../lib/dom.js';
import { on } from '../lib/bus.js';
import { get } from '../core/store.js';

export const CORE_STATES = ['idle', 'listening', 'processing', 'executing', 'speaking', 'error', 'offline'];

const SUB_LABEL = {
  idle: 'Standing by',
  listening: 'Listening to command...',
  processing: 'Processing request',
  executing: 'Executing task',
  speaking: 'Vocalising response',
  error: 'Fault detected',
  offline: 'Backend unreachable',
};

const MIC_LABEL = {
  idle: 'ENGAGE MIC',
  listening: 'LISTENING',
  processing: 'PROCESSING',
  executing: 'EXECUTING',
  speaking: 'SPEAKING',
  error: 'RETRY VOICE',
  offline: 'VOICE OFFLINE',
};

const WAVE_BARS = 34;

let coreState = 'idle';
let waveform = [];
let rafId = null;

/* ── Static geometry ──────────────────────────────────────────────── */
function buildTicks() {
  const group = $('#core-ticks');
  if (!group) return;
  const NS = 'http://www.w3.org/2000/svg';
  const count = 72;
  for (let i = 0; i < count; i += 1) {
    const angle = (i / count) * Math.PI * 2;
    const major = i % 6 === 0;
    const r1 = major ? 128 : 132;
    const r2 = 140;
    const line = document.createElementNS(NS, 'line');
    line.setAttribute('x1', (160 + Math.cos(angle) * r1).toFixed(2));
    line.setAttribute('y1', (160 + Math.sin(angle) * r1).toFixed(2));
    line.setAttribute('x2', (160 + Math.cos(angle) * r2).toFixed(2));
    line.setAttribute('y2', (160 + Math.sin(angle) * r2).toFixed(2));
    line.setAttribute('stroke', major ? '#1a353d' : '#0e1a1e');
    line.setAttribute('stroke-width', major ? '1.2' : '0.7');
    group.append(line);
  }
}

function buildWaveform() {
  const host = $('#waveform');
  if (!host) return;
  const frag = document.createDocumentFragment();
  for (let i = 0; i < WAVE_BARS; i += 1) {
    const bar = document.createElement('span');
    bar.className = 'waveform-bar';
    bar.style.height = '2px';
    frag.append(bar);
  }
  host.replaceChildren(frag);
  waveform = Array.from(host.children);
}

/* ── State ────────────────────────────────────────────────────────── */
export function setCoreState(next, sublabel = null) {
  const state = CORE_STATES.includes(next) ? next : 'idle';
  const link = get().link;
  const resolved = link === 'offline' && state !== 'error' ? 'offline' : state;
  if (resolved === coreState && sublabel === null) return;
  coreState = resolved;

  document.body.dataset.coreState = resolved;
  setText($('#core-svg-state'), resolved);
  setText($('#core-sub'), sublabel || SUB_LABEL[resolved]);
  setText($('#mic-label'), MIC_LABEL[resolved] || MIC_LABEL.idle);

  const mic = $('#btn-mic');
  if (mic) {
    mic.disabled = resolved === 'processing' || resolved === 'executing';
    mic.setAttribute(
      'aria-label',
      resolved === 'listening' ? 'Stop listening' : 'Start voice command',
    );
  }
}

export function setTranscript(text) {
  setText($('#core-transcript'), text || '');
}

export function getCoreState() {
  return coreState;
}

/* ── Waveform / reactive audio ────────────────────────────────────── */
/**
 * Feed a 0..1 intensity (from a real AnalyserNode RMS, or a synthetic idle
 * value). `level` is honest: without a microphone the bars stay flat.
 */
export function setAudioIntensity(level) {
  const clamped = Math.max(0, Math.min(1, Number(level) || 0));
  document.documentElement.style.setProperty('--reactive-scale', (1 + clamped * 0.035).toFixed(4));
  paintWave(clamped);
}

function paintWave(intensity) {
  const reduced = prefersReducedMotion();
  for (let i = 0; i < waveform.length; i += 1) {
    const bar = waveform[i];
    if (!bar) continue;
    // Deterministic pseudo-variation seeded by index — stable, no allocation.
    const wobble = 0.55 + 0.45 * Math.sin(i * 1.7 + Date.now() / 130);
    const h = reduced ? 2 + intensity * 2 : 2 + intensity * 20 * wobble;
    const next = `${h.toFixed(1)}px`;
    if (bar.style.height !== next) bar.style.height = next;
  }
}

/* ── Idle animation (cheap, pauses when hidden) ───────────────────── */
let idleRaf = null;
function idleLoop() {
  const active = coreState === 'idle' || coreState === 'offline';
  if (active) {
    // Very low amplitude breathing so the instrument feels alive when idle.
    const t = Date.now() / 1400;
    setAudioIntensity(0.06 + 0.04 * Math.sin(t));
  }
  idleRaf = requestAnimationFrame(idleLoop);
}

function handleVisibility() {
  if (document.hidden) {
    if (idleRaf) cancelAnimationFrame(idleRaf);
    idleRaf = null;
  } else if (!idleRaf) {
    idleRaf = requestAnimationFrame(idleLoop);
  }
}

export function initCore() {
  buildTicks();
  buildWaveform();
  setCoreState('idle');
  setAudioIntensity(0);
  if (!prefersReducedMotion()) {
    idleRaf = requestAnimationFrame(idleLoop);
  }
  document.addEventListener('visibilitychange', handleVisibility);

  on('link', (link) => {
    if (link === 'offline') {
      setCoreState('offline');
      setTranscript('');
    } else if (coreState === 'offline') {
      setCoreState('idle');
    }
  });
}

export function disposeCore() {
  if (idleRaf) cancelAnimationFrame(idleRaf);
  if (rafId) cancelAnimationFrame(rafId);
  idleRaf = null;
  rafId = null;
  document.removeEventListener('visibilitychange', handleVisibility);
}

export { rafId };
