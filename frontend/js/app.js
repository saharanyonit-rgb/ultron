/**
 * JARVIS — Application bootstrap.
 *
 * Wires the HUD, the data layer, the module system and the global shortcuts.
 * Every visible value originates from the backend; nothing is simulated.
 */

import { $, $$ } from './lib/dom.js';
import { on, emit } from './lib/bus.js';
import { get } from './core/store.js';
import * as log from './core/activity-log.js';
import * as toast from './core/toast.js';

import { initTopHud, renderStatusStrip, refreshWeather } from './ui/hud-top.js';
import { initCore, setCoreState, getCoreState } from './ui/hud-core.js';
import { initPanels } from './ui/hud-panels.js';
import { initLowerDeck, Radar } from './ui/hud-lower.js';
import { initEventStrip } from './ui/event-strip.js';
import { initDock, setOpenHandler } from './ui/dock.js';
import { initDrawer } from './ui/drawer.js';
import { initOrb } from './ui/orb.js';
import { renderer as chatRenderer } from './ui/chat-view.js';

import { initTelemetry, disposeTelemetry } from './features/telemetry.js';
import { initSSE, closeSSE } from './features/sse.js';
import { initVoice, speak } from './features/voice.js';
import { initChat, setRenderer as setChatRenderer } from './features/chat.js';
import { initPermissions } from './features/permissions.js';

import { MODULES, openModule, initModuleRouter } from './modules/index.js';

const BOOT_START = performance.now();

/* ── Boot ─────────────────────────────────────────────────────────── */
function boot() {
  log.push('system', 'JARVIS interface initialising');

  initTopHud();
  initCore();
  initPanels();
  initLowerDeck();
  initEventStrip();

  initDrawer();
  setOpenHandler((id, options) => openModule(id, options));
  initDock(MODULES);
  initModuleRouter();
  initOrb();

  initChat();
  setChatRenderer(chatRenderer);
  initVoice($('#btn-mic'));
  initPermissions();

  initSSE();
  initTelemetry();

  wireGlobalChrome();
  wireLinkState();
  refreshWeather();

  log.push('success', `Interface ready in ${Math.round(performance.now() - BOOT_START)} ms`);
}

/* ── Global chrome ────────────────────────────────────────────────── */
function wireGlobalChrome() {
  // The core: short press opens chat, long press speaks a status report.
  const core = $('#core-stage');
  if (core) {
    let holdTimer = null;
    let longPressed = false;

    // The mic is a control nested inside the core, so its press bubbles up
    // here. Without this guard, starting a voice command would also count as
    // a core press and pop the chat drawer open over the transcript.
    const fromMic = (event) => Boolean(event.target?.closest?.('.core-mic'));

    const release = (openChat) => {
      if (holdTimer) clearTimeout(holdTimer);
      holdTimer = null;
      if (openChat && !longPressed) openModule('chat');
      longPressed = false;
    };

    core.addEventListener('pointerdown', (event) => {
      if (fromMic(event)) return;
      longPressed = false;
      holdTimer = setTimeout(() => {
        longPressed = true;
        speakStatus();
      }, 700);
    });
    // On a mic release the hold timer still has to be cleared, but the chat
    // drawer must stay closed.
    core.addEventListener('pointerup', (event) => release(!fromMic(event)));
    core.addEventListener('pointerleave', () => release(false));
    core.addEventListener('pointercancel', () => release(false));

    core.addEventListener('keydown', (e) => {
      // Same for keyboard: Enter/Space on the focused mic belongs to the mic.
      if (fromMic(e)) return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openModule('chat');
      } else if (e.key.toLowerCase() === 'v' && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        $('#btn-mic')?.click();
      }
    });
  }

  // Dock roving focus so arrow keys behave like a tablist.
  $('#dock-items')?.addEventListener('keydown', (e) => {
    const items = $$('.dock-item', e.currentTarget);
    const index = items.indexOf(document.activeElement);
    if (index < 0) return;
    let next = null;
    if (e.key === 'ArrowRight') next = items[(index + 1) % items.length];
    else if (e.key === 'ArrowLeft') next = items[(index - 1 + items.length) % items.length];
    else if (e.key === 'Home') next = items[0];
    else if (e.key === 'End') next = items[items.length - 1];
    if (next) {
      e.preventDefault();
      next.focus();
    }
  });

  // Global shortcut: focus the composer.
  window.addEventListener('keydown', (e) => {
    if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
      e.preventDefault();
      openModule('chat');
      setTimeout(() => $('#chat-input')?.focus(), 120);
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) renderStatusStrip();
  });

  window.addEventListener('beforeunload', () => {
    emit('teardown');
    closeSSE();
    disposeTelemetry();
    Radar.stop('MIC RELEASED');
  });
}

/* ── Voice status report built from real telemetry ────────────────── */
async function speakStatus() {
  const s = get();
  const parts = [];
  parts.push(s.link === 'online' ? 'All systems nominal' : 'Backend link is down');
  if (s.metrics?.cpu_percent != null) parts.push(`CPU at ${Math.round(s.metrics.cpu_percent)} percent`);
  if (s.metrics?.ram_percent != null) parts.push(`memory at ${Math.round(s.metrics.ram_percent)} percent`);
  if (s.backend?.uptime_seconds != null) {
    const h = Math.floor(s.backend.uptime_seconds / 3600);
    const m = Math.floor((s.backend.uptime_seconds % 3600) / 60);
    parts.push(`session uptime ${h} hours and ${m} minutes`);
  }
  const text = `${parts.join(', ')}.`;
  log.push('system', 'Status report requested');
  await speak(text);
}

/* ── Link state drives the whole shell ────────────────────────────── */
function wireLinkState() {
  on('link', (link) => {
    renderStatusStrip();
    if (link === 'offline') {
      setCoreState('offline');
      log.push('error', 'Backend link lost — showing last known telemetry');
      toast.error('BACKEND OFFLINE', 'Cached telemetry only. Start JARVIS to reconnect.');
    } else {
      if (getCoreState() === 'offline') setCoreState('idle');
      if (link === 'online') refreshWeather();
    }
  });
}

/* ── Failure surface ──────────────────────────────────────────────── */
window.addEventListener('error', (event) => {
  log.push('error', `Uncaught: ${event.message}`);
  toast.error('INTERFACE FAULT', event.message);
});

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason?.message || String(event.reason);
  log.push('error', `Unhandled rejection: ${reason}`);
});

/* ── Go ───────────────────────────────────────────────────────────── */
// Module scripts are deferred, so the document is normally already parsed here.
// Wait for DOMContentLoaded when it is not, and always give the parser a frame
// to finish so the first paint measures a settled layout.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => requestAnimationFrame(boot), { once: true });
} else {
  requestAnimationFrame(boot);
}
