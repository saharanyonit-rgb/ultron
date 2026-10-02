/**
 * JARVIS — Notification stack.
 *
 * Compact toasts for connection changes, command/tool outcomes, permission
 * requests and errors. Rate-limited and deduplicated so the UI never becomes
 * an annoyance.
 */

import { $, el } from '../lib/dom.js';

const stack = () => $('#toast-stack');

const LIMITS = {
  maxVisible: 4,
  ttl: { info: 4200, system: 4200, tool: 3600, success: 3600, warning: 6000, error: 9000 },
  minGap: 900, // ms — same message within this window is refreshed, not stacked
};

const recent = new Map();
const live = [];

export function notify(level, title, message = '', { ttl } = {}) {
  const key = `${level}:${title}:${message}`;
  const now = Date.now();
  const previous = recent.get(key);
  if (previous && now - previous < LIMITS.minGap) return null;
  recent.set(key, now);
  if (recent.size > 60) {
    for (const [k, at] of recent) {
      if (now - at > 60000) recent.delete(k);
    }
  }

  const host = stack();
  if (!host) return null;

  const node = el('div', { class: `toast t-${level}`, role: 'status' }, [
    el('span', {}, [el('span', { class: 'ttl', text: title }), message ? el('span', { text: message }) : null]),
  ]);
  host.append(node);
  live.push(node);

  while (live.length > LIMITS.maxVisible) dismiss(live[0]);

  const duration = ttl ?? LIMITS.ttl[level] ?? 4200;
  const timer = setTimeout(() => dismiss(node), duration);
  node.addEventListener('click', () => {
    clearTimeout(timer);
    dismiss(node);
  });
  return node;
}

function dismiss(node) {
  const index = live.indexOf(node);
  if (index === -1) return;
  live.splice(index, 1);
  node.classList.add('is-leaving');
  setTimeout(() => node.remove(), 220);
}

export function dismissAll() {
  for (const node of live.slice()) dismiss(node);
}

export const info = (title, message, opts) => notify('info', title, message, opts);
export const success = (title, message, opts) => notify('success', title, message, opts);
export const warning = (title, message, opts) => notify('warning', title, message, opts);
export const error = (title, message, opts) => notify('error', title, message, opts);

