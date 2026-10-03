/**
 * JARVIS — DOM helpers.
 * Small, allocation-conscious utilities used across the HUD.
 */

/**
 * Look up a single element by id.
 * Accepts either `'status-strip'` or `'#status-strip'` because every call site
 * in the HUD uses the selector form.
 */
export const $ = (id) => document.getElementById(String(id).replace(/^#/, ''));
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/** Create an element with attributes and children. */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key === 'html') node.innerHTML = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

/** SVG element factory (namespace-aware). */
export function svgEl(tag, attrs = {}) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined) continue;
    node.setAttribute(key, value);
  }
  return node;
}

/**
 * Reference an icon from the sprite. `id` is the full symbol id as defined in
 * the sprite, e.g. `i-system` — the same string the modules carry in
 * `icon:` — because the static markup writes `<use href="#i-system">`.
 */
export function icon(id, className = '') {
  const svg = svgEl('svg', className ? { class: className, 'aria-hidden': 'true' } : { 'aria-hidden': 'true' });
  const use = svgEl('use');
  use.setAttribute('href', `#${id}`);
  svg.append(use);
  return svg;
}

/** Set text only when it actually changed (avoids needless layout work). */
export function setText(node, value) {
  if (!node) return;
  const next = value === null || value === undefined ? '' : String(value);
  if (node.textContent !== next) node.textContent = next;
}

export function setHTML(node, value) {
  if (!node) return;
  const next = value === null || value === undefined ? '' : String(value);
  if (node.innerHTML !== next) node.innerHTML = next;
}

/** Toggle a class only when changed. */
export function setClass(node, name, on) {
  if (!node) return;
  if (node.classList.contains(name) !== !!on) node.classList.toggle(name, !!on);
}

/** Replace a node's class attribute, tolerating a missing node. */
export function setClassName(node, value) {
  if (!node) return;
  if (node.className !== value) node.className = value;
}

export function clear(node) {
  if (node) node.replaceChildren();
}

/** Human-readable duration: HH:MM:SS */
export function formatDuration(totalSeconds) {
  if (totalSeconds === null || totalSeconds === undefined || !isFinite(totalSeconds)) return '--:--:--';
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = String(Math.floor(s / 3600)).padStart(2, '0');
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const sec = String(s % 60).padStart(2, '0');
  return `${h}:${m}:${sec}`;
}

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined || !isFinite(bytes)) return '--';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = Number(bytes);
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatClock(date) {
  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
}

export function formatDate(date) {
  return date
    .toLocaleDateString(undefined, { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })
    .toUpperCase();
}

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

export const prefersReducedMotion = () =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Short aliases used by the module layer. */
export const fmtDuration = formatDuration;
export const fmtBytes = formatBytes;

export function fmtNumber(value) {
  if (value === null || value === undefined || !isFinite(value)) return 'UNKNOWN';
  return Number(value).toLocaleString();
}

/** Accepts ISO strings, epoch seconds, epoch millis, or null. */
export function relativeTime(value) {
  if (value === null || value === undefined || value === '') return 'UNKNOWN';
  const then = typeof value === 'number'
    ? (value < 1e11 ? value * 1000 : value)
    : Date.parse(value);
  if (!Number.isFinite(then)) return 'UNKNOWN';
  const diff = Math.round((Date.now() - then) / 1000);
  if (diff < 0) return 'in the future';
  if (diff < 45) return 'just now';
  if (diff < 90) return 'a minute ago';
  if (diff < 3600) return `${Math.round(diff / 60)} minutes ago`;
  if (diff < 7200) return 'an hour ago';
  if (diff < 86400) return `${Math.round(diff / 3600)} hours ago`;
  if (diff < 172800) return 'yesterday';
  if (diff < 2592000) return `${Math.round(diff / 86400)} days ago`;
  return new Date(then).toLocaleDateString().toUpperCase();
}

/** Debounce with trailing invocation. */
export function debounce(fn, wait = 200) {
  let timer = null;
  return (...args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn(...args);
    }, wait);
  };
}
