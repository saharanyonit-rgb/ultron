/**
 * JARVIS — Latest-event strip above the core.
 * Mirrors the most recent real log entry; clicking opens the LOG module.
 */

import { $, setText, setClass } from '../lib/dom.js';
import { on } from '../lib/bus.js';
import * as log from '../core/activity-log.js';
import { setLastEvent } from '../core/store.js';

const SEVERITY = {
  info: 'info',
  success: 'success',
  warning: 'warning',
  error: 'error',
  system: 'info',
  tool: 'tool',
};

function timeOf(ts) {
  return new Date(ts).toLocaleTimeString(undefined, { hour12: false });
}

export function renderLatest(entry) {
  if (!entry) return;
  setLastEvent(entry);
  setText($('#event-time'), `LOG ${timeOf(entry.at)}`);
  setText($('#event-sev'), entry.level.toUpperCase());
  setText($('#event-text'), entry.detail ? `${entry.message} — ${entry.detail}` : entry.message);
  const sev = $('#event-sev');
  setClass(sev, `sev-${SEVERITY[entry.level] || 'info'}`, true);
  for (const key of Object.values(SEVERITY)) setClass(sev, `sev-${key}`, false);
  setClass(sev, `sev-${SEVERITY[entry.level] || 'info'}`, true);
}

export function initEventStrip() {
  const strip = $('#event-strip');
  strip?.setAttribute('aria-label', 'Latest system event — open activity log');

  on('log:entry', renderLatest);

  const existing = log.latest();
  if (existing) renderLatest(existing);
  else {
    setText($('#event-text'), 'AWAITING FIRST EVENT');
  }
}
