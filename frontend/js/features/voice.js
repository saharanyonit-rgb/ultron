/**
 * JARVIS — Voice interface.
 *
 * Uses the real backend voice pipeline (`/api/voice/listen`, `/api/voice/speak`,
 * `/api/voice/interrupt`). The browser SpeechRecognition API is used only as a
 * documented fallback when the backend engine has no usable microphone.
 *
 * State flow: IDLE → LISTENING → PROCESSING → SPEAKING → IDLE
 */

import { on } from '../lib/bus.js';
import { get } from '../core/store.js';
import { setCoreState, setTranscript, getCoreState } from '../ui/hud-core.js';
import { Radar } from '../ui/hud-lower.js';
import * as api from '../lib/api.js';
import * as log from '../core/activity-log.js';
import * as toast from '../core/toast.js';

let sessionActive = false;
let speakAfter = false;
let browserRecognition = null;
let voiceReply = null; // set by chat.js: (text) => Promise<void>

const ERRORS = {
  'not-allowed': 'Microphone permission denied — allow it in the browser to use voice.',
  'service-not-allowed': 'Speech service blocked by browser site permissions.',
  'audio-capture': 'No microphone detected on this system.',
  network: 'Speech recognition service unreachable — check connectivity.',
  aborted: 'Listening interrupted.',
};

export function setVoiceReplyHandler(fn) {
  voiceReply = fn;
}

export function isSessionActive() {
  return sessionActive;
}

/* ── Backend voice state (authoritative) ──────────────────────────── */
on('sse:voice_state', (data) => {
  if (!data || !data.state) return;
  const mapped = data.state === 'processing' ? 'processing' : data.state;
  if (mapped === 'idle' && (sessionActive || getCoreState() === 'processing')) return;
  if (['idle', 'listening', 'processing', 'speaking', 'error'].includes(mapped)) {
    if (mapped === 'speaking') setCoreState('speaking');
    else if (mapped === 'error') setCoreState('error');
  }
});

/* ── Public entry point (mic button) ──────────────────────────────── */
export async function toggleVoice() {
  const state = getCoreState();

  if (state === 'speaking') {
    await interrupt();
    return;
  }
  if (state === 'listening' || state === 'processing' || state === 'executing') {
    // Cancel the current capture.
    sessionActive = false;
    browserRecognition?.abort?.();
    try {
      await api.interruptVoice();
    } catch {
      /* backend may not have a voice engine — local cancel is enough */
    }
    setCoreState(get().link === 'offline' ? 'offline' : 'idle');
    setTranscript('');
    log.push('system', 'Voice capture cancelled');
    return;
  }

  await startListening();
}

/* ── Listening ────────────────────────────────────────────────────── */
async function startListening() {
  if (getCoreState() === 'offline') {
    toast.error('VOICE UNAVAILABLE', 'Backend is offline — voice requires the JARVIS core');
    setCoreState('error');
    setTimeout(() => setCoreState('idle'), 2200);
    return;
  }

  sessionActive = true;
  setCoreState('listening');
  setTranscript('');
  log.push('system', 'Voice capture started');

  // Light up the acoustic radar. This is also the only thing in the app that
  // makes the browser ask for microphone permission, so its outcome is awaited
  // and reported rather than swallowed — the radar panel is not always mounted
  // to show the reason, and voice itself runs server-side.
  await startWaveform();

  let result = null;
  try {
    result = await api.listen(10);
  } catch (err) {
    log.push('error', `Backend voice endpoint failed: ${err.message}`);
  }

  if (!sessionActive) return;

  const transcribed = result && result.success && result.text ? result.text.trim() : null;

  if (!transcribed) {
    const reason = (result && result.error) || 'Backend voice engine returned no audio';
    const fellBack = startBrowserFallback();
    if (fellBack) return;
    sessionActive = false;
    setCoreState('error');
    setTranscript(reason);
    log.push('error', reason);
    toast.error('VOICE UNAVAILABLE', reason);
    setTimeout(() => {
      setCoreState('idle');
      setTranscript('');
    }, 2600);
    return;
  }

  setCoreState('processing');
  setTranscript(transcribed);
  log.push('info', `Heard: "${transcribed}"`);
  await deliver(transcribed);
}

/* ── Microphone permission ─────────────────────────────────────────── */
/**
 * The radar owns the browser's microphone stream, so it owns the permission
 * prompt. Voice transcription runs on the JARVIS core instead, which means a
 * refused prompt must not look like a dead mic button — say what happened and
 * what still works.
 */
async function startWaveform() {
  if (Radar.running) return;

  let granted = false;
  try {
    granted = await Radar.start();
  } catch {
    granted = false;
  }
  if (granted) return;

  const blocked = await isMicBlockedByBrowser();
  const reason = Radar.lastFailure || 'No capture device could be opened';
  toast.warning(
    blocked ? 'MICROPHONE BLOCKED' : 'NO MICROPHONE',
    blocked
      ? 'This site is not allowed to use the microphone. Enable it from the address bar, then press the mic again.'
      : `${reason}. Voice input still runs on the JARVIS core.`,
  );
  log.push('warning', `Microphone unavailable: ${reason}`);
}

/** True when the browser has this origin blocked, rather than merely failing. */
async function isMicBlockedByBrowser() {
  try {
    const status = await navigator.permissions?.query({ name: 'microphone' });
    return status?.state === 'denied';
  } catch {
    // The Permissions API is not available for every origin; treat that as
    // "not blocked" and let the generic message stand.
    return false;
  }
}

/* ── Browser SpeechRecognition fallback ────────────────────────────── */
function startBrowserFallback() {
  const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Ctor) return false;

  try {
    browserRecognition = new Ctor();
  } catch {
    return false;
  }
  browserRecognition.continuous = false;
  browserRecognition.interimResults = true;
  browserRecognition.lang = navigator.language || 'en-US';

  let finalText = '';
  let retries = 0;
  const MAX_RETRIES = 2;

  const start = () => {
    try {
      browserRecognition.start();
    } catch {
      /* already started */
    }
  };

  browserRecognition.onresult = (event) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const chunk = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += chunk;
      else interim += chunk;
    }
    setTranscript(finalText || interim);
  };

  browserRecognition.onerror = (event) => {
    if (event.error === 'no-speech' && retries < MAX_RETRIES) {
      retries += 1;
      start();
      return;
    }
    sessionActive = false;
    const message = ERRORS[event.error] || `Speech recognition failed: ${event.error}`;
    setCoreState('error');
    setTranscript(message);
    log.push('error', message);
    toast.error('VOICE FAULT', message);
    setTimeout(() => {
      setCoreState('idle');
      setTranscript('');
    }, 2800);
  };

  browserRecognition.onend = async () => {
    if (!sessionActive) return;
    if (finalText.trim()) {
      setCoreState('processing');
      await deliver(finalText.trim());
      return;
    }
    if (retries < MAX_RETRIES) {
      retries += 1;
      start();
      return;
    }
    sessionActive = false;
    setCoreState('error');
    setTranscript('No speech detected');
    log.push('warning', 'No speech detected after retries');
    setTimeout(() => {
      setCoreState('idle');
      setTranscript('');
    }, 2200);
  };

  log.push('info', 'Backend voice unavailable — using browser speech recognition');
  start();
  return true;
}

/* ── Delivery + reply ─────────────────────────────────────────────── */
async function deliver(text) {
  if (!voiceReply) {
    sessionActive = false;
    setCoreState('idle');
    return;
  }
  speakAfter = true;
  try {
    await voiceReply(text, { fromVoice: true });
  } catch (err) {
    log.push('error', `Voice command failed: ${err.message}`);
  }
}

export async function speak(text) {
  if (!text) return;
  // During a voice turn the core is already owned by the conversation
  // (`deliver` set speakAfter), so only ad-hoc speech drives the core itself
  // — and it hands the state back when it finishes.
  const previous = getCoreState();
  if (!speakAfter) setCoreState('speaking');
  try {
    await api.speak(text);
    log.push('info', 'Spoken response delivered');
  } catch (err) {
    log.push('warning', `TTS unavailable: ${err.message}`);
    toast.warning('TTS UNAVAILABLE', 'Backend speech engine did not respond');
  } finally {
    if (speakAfter) {
      speakAfter = false;
      sessionActive = false;
      setCoreState('idle');
    } else if (previous !== 'speaking') {
      setCoreState(previous);
    }
  }
}

export async function interrupt() {
  sessionActive = false;
  speakAfter = false;
  browserRecognition?.abort?.();
  try {
    await api.interruptVoice();
    log.push('system', 'Speech interrupted by user');
  } catch {
    log.push('system', 'Speech interrupted locally (backend voice unavailable)');
  }
  setCoreState('idle');
  setTranscript('');
}

export function initVoice(button) {
  button?.addEventListener('click', () => {
    toggleVoice().catch((err) => {
      console.error('[voice]', err);
      setCoreState('error');
    });
  });

  on('sse:shutting_down', () => {
    sessionActive = false;
    browserRecognition?.abort?.();
    setCoreState('offline');
  });

  on('teardown', () => {
    browserRecognition?.abort?.();
    browserRecognition = null;
  });
}
