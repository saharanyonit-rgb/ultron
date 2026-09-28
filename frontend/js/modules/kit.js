/**
 * JARVIS — Module kit.
 * Small shared building blocks so every module renders with the same visual
 * language and the same refresh/teardown discipline.
 */

import { el, setText } from '../lib/dom.js';
import * as toast from '../core/toast.js';
import * as log from '../core/activity-log.js';

export function section(title, meta = '') {
  return el('div', { class: 'mod-section' }, [
    el('div', { class: 'mod-section-head' }, [
      el('span', { class: 'mod-section-title', text: title }),
      meta ? el('span', { class: 'mod-section-meta', text: meta }) : null,
    ]),
  ]);
}

export function row(label, value, extra) {
  const node = el('div', { class: 'kv' }, [
    el('span', { class: 'k', text: label }),
    el('span', { class: 'v', text: value === null || value === undefined || value === '' ? 'UNKNOWN' : String(value) }),
  ]);
  if (extra) node.append(el('span', { class: 'kv-extra' }, extra));
  return node;
}

export function meter(label, percent, detail) {
  const wrap = el('div', { class: 'meter' });
  const bar = el('div', { class: 'meter-fill' });
  bar.style.width = `${Math.max(0, Math.min(100, percent || 0))}%`;
  const value = typeof percent === 'number' ? `${Math.round(percent)}%` : 'UNKNOWN';
  wrap.append(
    el('div', { class: 'meter-head' }, [
      el('span', { class: 'k', text: label }),
      el('span', { class: 'v', text: value }),
    ]),
    el('div', { class: 'meter-track' }, [bar]),
  );
  if (detail) wrap.append(el('div', { class: 'meter-note', text: detail }));
  return wrap;
}

export function button(label, onClick, variant = '') {
  return el('button', { type: 'button', class: `btn-mini${variant ? ` ${variant}` : ''}`, text: label, onclick: onClick });
}

export function field(placeholder, value = '') {
  return el('input', { class: 'input-field', type: 'text', placeholder, value, 'aria-label': placeholder });
}

export function textarea(placeholder, value = '') {
  const node = el('textarea', { class: 'input-area', placeholder, rows: '4', 'aria-label': placeholder });
  if (value) node.value = value;
  return node;
}

/**
 * Wraps an async loader with loading / error / empty handling so a module can
 * never render a blank panel or a silent failure.
 */
export function asyncBlock(body, label, loader, transform) {
  const host = el('div', { class: 'mod-async' });
  const status = el('div', { class: 'loading-line', text: label });
  host.append(status);

  loader()
    .then((data) => {
      status.remove();
      const view = transform(data);
      if (view === null || view === undefined) {
        host.append(el('div', { class: 'state-block', text: 'NO DATA' }));
        return;
      }
      host.append(view);
    })
    .catch((err) => {
      status.remove();
      log.push('warning', `Module load failed: ${err.message}`);
      host.append(
        el('div', { class: 'state-block is-error' }, [
          el('span', { class: 'h', text: 'UNAVAILABLE' }),
          el('span', { class: 'd', text: err.message || 'No response from backend' }),
        ]),
      );
    });

  body.append(host);
  return host;
}

/**
 * Repeats a loader on an interval with proper teardown. Pauses while the tab
 * is hidden so background tabs do not hammer the backend.
 */
export function poll(loader, interval, onData) {
  let stopped = false;
  let inFlight = false;

  const run = async () => {
    if (stopped || document.hidden || inFlight) return;
    inFlight = true;
    try {
      const data = await loader();
      if (!stopped) onData(data);
    } catch {
      /* the view keeps its last good value */
    } finally {
      inFlight = false;
    }
  };

  run();
  const timer = setInterval(run, interval);
  return () => {
    stopped = true;
    clearInterval(timer);
  };
}

export function reportError(action, err) {
  log.push('error', `${action} failed: ${err.message}`);
  toast.error(`${action} FAILED`, err.message);
}

export { setText };
