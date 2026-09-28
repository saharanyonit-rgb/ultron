/**
 * JARVIS — Module drawer.
 * A single reusable panel that hosts every module, with focus management,
 * ESC-to-close and a scrim. Modules render into `#drawer-body`.
 */

import { $, setText, setClass } from '../lib/dom.js';
import { setActiveModule } from '../core/store.js';

let current = null;
let currentModule = null;
let lastFocused = null;
const cleanups = new Set();

const scrim = () => $('#drawer-scrim');
const drawer = () => $('#drawer');

export function onClose(handler) {
  drawerCleanups.add(handler);
}

const drawerCleanups = new Set();

export function open(id, module) {
  const node = drawer();
  if (!node) return;

  if (current && current !== id) runCleanup();
  if (current === id && node.classList.contains('is-open')) return;

  current = id;
  currentModule = module;
  lastFocused = document.activeElement;

  setText($('#drawer-title'), (module?.title || id).toUpperCase());
  setText($('#drawer-subtitle'), module?.subtitle || '—');
  const body = $('#drawer-body');
  const foot = $('#drawer-foot');
  body.replaceChildren();
  foot.replaceChildren();
  foot.hidden = true;

  setClass(scrim(), 'is-open', true);
  node.classList.add('is-open');
  node.setAttribute('aria-hidden', 'false');
  setActiveModule(id);

  try {
    const result = module?.render?.(body, { setFooter, setSubtitle });
    if (typeof result === 'function') cleanups.add(result);
  } catch (err) {
    console.error(`[drawer] module "${id}" failed to render`, err);
    body.replaceChildren(errorBlock('MODULE FAULT', err.message || 'Unknown render failure'));
  }

  requestAnimationFrame(() => $('#drawer-close')?.focus());
}

export function close() {
  const node = drawer();
  if (!node || !current) return;
  runCleanup();
  setClass(scrim(), 'is-open', false);
  node.classList.remove('is-open');
  node.setAttribute('aria-hidden', 'true');
  setActiveModule(null);
  current = null;
  currentModule = null;
  if (lastFocused && document.contains(lastFocused)) lastFocused.focus();
  lastFocused = null;
}

function runCleanup() {
  for (const fn of cleanups) {
    try {
      fn();
    } catch (err) {
      console.error('[drawer] cleanup failed', err);
    }
  }
  cleanups.clear();
  for (const fn of drawerCleanups) {
    try {
      fn(current);
    } catch {
      /* module teardown must never break the shell */
    }
  }
}

export function setFooter(nodes) {
  const foot = $('#drawer-foot');
  if (!foot) return;
  foot.replaceChildren();
  if (!nodes || (Array.isArray(nodes) && !nodes.length)) {
    foot.hidden = true;
    return;
  }
  foot.hidden = false;
  foot.append(...[].concat(nodes));
}

export function setSubtitle(text) {
  setText($('#drawer-subtitle'), text || '—');
}

export function body() {
  return $('#drawer-body');
}

export function activeModule() {
  return currentModule;
}

/* ── Shared building blocks for modules ───────────────────────────── */
export function errorBlock(heading, detail = '') {
  const wrap = document.createElement('div');
  wrap.className = 'state-block';
  wrap.innerHTML = `
    <svg aria-hidden="true"><use href="#i-alert"></use></svg>
    <span class="h"></span>
    <span class="d"></span>
  `;
  wrap.querySelector('.h').textContent = heading;
  wrap.querySelector('.d').textContent = detail;
  return wrap;
}

export function emptyBlock(heading, detail = '') {
  const wrap = document.createElement('div');
  wrap.className = 'state-block';
  wrap.innerHTML = `
    <svg aria-hidden="true"><use href="#i-unavail"></use></svg>
    <span class="h"></span>
    <span class="d"></span>
  `;
  wrap.querySelector('.h').textContent = heading;
  wrap.querySelector('.d').textContent = detail;
  return wrap;
}

export function loadingBlock(label = 'SYNCING') {
  const wrap = document.createElement('div');
  wrap.className = 'loading-line';
  wrap.textContent = label;
  return wrap;
}

export function initDrawer() {
  scrim()?.addEventListener('click', close);
  $('#drawer-close')?.addEventListener('click', close);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && current) {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === 'Tab' && current) trapFocus(e);
  });

  // Any element with data-module opens that module.
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest?.('[data-module]');
    if (!trigger || trigger.classList.contains('dock-item')) return;
    const id = trigger.dataset.module;
    if (id) window.dispatchEvent(new CustomEvent('jarvis:open-module', { detail: id }));
  });
}

function trapFocus(e) {
  const node = drawer();
  const focusables = node.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
  );
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
}

export { current };
