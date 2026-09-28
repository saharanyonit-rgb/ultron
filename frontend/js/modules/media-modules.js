/**
 * JARVIS — Camera, Focus and Telegram modules.
 *
 * Camera: real `getUserMedia` preview in the browser plus the existing
 *         `POST /api/vision/analyze` route for real vision analysis.
 * Focus: a real local focus timer (no backend dependency, no fake state).
 * Telegram: no integration exists in this backend — shown honestly as such.
 */

import { el } from '../lib/dom.js';
import * as api from '../lib/api.js';
import * as log from '../core/activity-log.js';
import * as toast from '../core/toast.js';
import { setSubtitle, emptyBlock } from '../ui/drawer.js';
import { section, field, button, reportError } from './kit.js';

/* ── CAMERA ───────────────────────────────────────────────────────── */
function cameraView(body) {
  const stage = el('div', { class: 'cam-stage' });
  const video = el('video', { class: 'cam-video', autoplay: true, muted: true, playsinline: true });
  video.setAttribute('aria-label', 'Live camera preview');
  const placeholder = el('div', { class: 'cam-placeholder' }, [
    el('span', { class: 'h', text: 'CAMERA OFFLINE' }),
    el('span', { class: 'd', text: 'Grant camera access to see a live preview.' }),
  ]);
  stage.append(video, placeholder);

  const promptField = field('What should JARVIS look for?');
  const result = el('div', { class: 'vision-result' });
  let stream = null;

  const stop = button('Stop preview', () => teardown());
  const start = button('Start preview', async () => {
    await open();
  }, 'primary');

  async function open() {
    if (stream) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      placeholder.querySelector('.d').textContent = 'This browser exposes no camera API.';
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280 }, audio: false });
      video.srcObject = stream;
      await video.play().catch(() => {});
      stage.classList.add('is-live');
      start.disabled = true;
      stop.disabled = false;
      log.push('success', 'Camera stream opened');
      toast.success('CAMERA ONLINE', 'Local preview active');
    } catch (err) {
      const reason =
        err.name === 'NotAllowedError' ? 'Camera permission denied'
        : err.name === 'NotFoundError' ? 'No camera device found'
        : err.name === 'NotReadableError' ? 'Camera is in use by another application'
        : err.message;
      placeholder.querySelector('.d').textContent = reason;
      log.push('warning', `Camera unavailable: ${reason}`);
      toast.warning('CAMERA UNAVAILABLE', reason);
    }
  }

  function teardown() {
    if (stream) {
      for (const track of stream.getTracks()) track.stop();
      stream = null;
    }
    video.srcObject = null;
    stage.classList.remove('is-live');
    start.disabled = false;
    stop.disabled = true;
  }

  const analyse = button('Analyse frame', async () => {
    if (!stream) {
      toast.warning('CAMERA OFFLINE', 'Start the preview before analysing');
      return;
    }
    const prompt = promptField.value.trim() || 'Describe what you see in this image.';
    result.replaceChildren(el('div', { class: 'loading-line', text: 'ANALYSING FRAME' }));
    try {
      const response = await api.analyzeVision(prompt);
      const text = response?.result || response?.response || response?.analysis || response?.text;
      if (!text) throw new Error(response?.error || 'Vision route returned no analysis');
      result.replaceChildren(el('p', { class: 'vision-text', text }));
      log.push('success', 'Vision analysis completed');
    } catch (err) {
      result.replaceChildren(
        el('div', { class: 'state-block is-error' }, [
          el('span', { class: 'h', text: 'VISION UNAVAILABLE' }),
          el('span', { class: 'd', text: err.message }),
        ]),
      );
      reportError('Vision analysis', err);
    }
  });

  body.append(
    section('LOCAL PREVIEW'),
    stage,
    el('div', { class: 'button-row' }, [start, stop]),
    section('VISION ANALYSIS'),
    promptField,
    el('div', { class: 'button-row' }, [analyse]),
    result,
  );
  start.disabled = false;
  stop.disabled = true;

  return teardown;
}

export const camera = {
  id: 'camera',
  title: 'Camera',
  label: 'CAMERA',
  icon: 'i-camera',
  subtitle: 'Local preview and vision',
  available: true,
  render: cameraView,
};

/* ── FOCUS ────────────────────────────────────────────────────────── */
const PRESETS = [15, 25, 50, 90];

function focusView(body) {
  let remaining = 25 * 60;
  let target = 25 * 60;
  let timer = null;

  const display = el('div', { class: 'focus-display', text: '25:00' });
  const goal = field('What are you focusing on?');
  goal.setAttribute('aria-label', 'Focus intention');

  const presets = el('div', { class: 'button-row' },
    PRESETS.map((m) => button(`${m}m`, () => setLength(m * 60), 'soft')));

  function setLength(seconds) {
    if (timer) return;
    target = seconds;
    remaining = seconds;
    paint();
  }

  function paint() {
    const m = String(Math.floor(remaining / 60)).padStart(2, '0');
    const s = String(remaining % 60).padStart(2, '0');
    display.textContent = `${m}:${s}`;
    document.title = timer ? `${m}:${s} · JARVIS` : 'JARVIS';
  }

  function tick() {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(timer);
      timer = null;
      display.textContent = '00:00';
      document.title = 'JARVIS';
      body.classList.add('is-focus-done');
      log.push('success', 'Focus session complete');
      toast.success('FOCUS COMPLETE', 'Session finished — take a break');
      if (goal.value.trim()) api.speak(`Focus session complete. Well done on ${goal.value.trim()}.`).catch(() => {});
      return;
    }
    paint();
  }

  function start() {
    if (timer) return;
    remaining = target;
    timer = setInterval(tick, 1000);
    startBtn.disabled = true;
    pauseBtn.disabled = false;
    log.push('info', `Focus session started (${Math.round(target / 60)} min)`);
  }

  function pause() {
    if (!timer) return;
    clearInterval(timer);
    timer = null;
    startBtn.disabled = false;
    pauseBtn.disabled = true;
    document.title = 'JARVIS';
    log.push('system', 'Focus session paused');
  }

  const startBtn = button('Start', start, 'primary');
  const pauseBtn = button('Pause', pause);
  pauseBtn.disabled = true;

  body.append(
    section('TIMER'),
    display,
    presets,
    el('div', { class: 'button-row' }, [startBtn, pauseBtn]),
    section('INTENTION'),
    goal,
  );
  paint();

  return () => {
    if (timer) clearInterval(timer);
    document.title = 'JARVIS';
  };
}

export const focus = {
  id: 'focus',
  title: 'Focus',
  label: 'FOCUS',
  icon: 'i-focus',
  subtitle: 'Local focus timer',
  available: true,
  render: focusView,
};

/* ── TELEGRAM ─────────────────────────────────────────────────────── */
function telegramView(body) {
  body.append(
    section('INTEGRATION STATUS'),
    emptyBlock(
      'NOT CONFIGURED',
      'This JARVIS build has no Telegram bridge. No bot token or chat ID is present in the backend, so nothing can be sent or received.',
    ),
    section('WHAT WOULD BE NEEDED'),
    el('ul', { class: 'bullets' }, [
      el('li', { text: 'A Telegram bot token from @BotFather' }),
      el('li', { text: 'A chat or channel ID to deliver messages to' }),
      el('li', { text: 'A backend bridge that polls the Telegram Bot API' }),
      el('li', { text: 'An outbound webhook or long-poll worker' }),
    ]),
  );
  setSubtitle('unavailable — no backend integration');
  return () => {};
}

export const telegram = {
  id: 'telegram',
  title: 'Telegram',
  label: 'TELEGRAM',
  icon: 'i-telegram',
  subtitle: 'Not configured',
  available: false,
  unavailableReason: 'No Telegram integration exists in this backend',
  render: telegramView,
};
