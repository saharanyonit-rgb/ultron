/**
 * JARVIS — Bottom navigation dock.
 * Modules are registered by the module layer; the dock only renders and routes.
 */

import { $, el, icon, setClass } from '../lib/dom.js';
import { on } from '../lib/bus.js';

let registry = [];
let onOpen = () => {};
const buttons = new Map();

export function setOpenHandler(handler) {
  onOpen = handler;
}

export function initDock(modules) {
  registry = modules;
  const host = $('#dock-items');
  if (!host) return;

  const frag = document.createDocumentFragment();
  for (const mod of registry) {
    const button = el(
      'button',
      {
        type: 'button',
        class: 'dock-item',
        role: 'tab',
        id: `dock-tab-${mod.id}`,
        'data-module': mod.id,
        'aria-controls': 'drawer',
        'aria-selected': 'false',
        title: mod.title || mod.label,
      },
      [icon(mod.icon), el('span', { text: mod.label })],
    );
    if (!mod.available) {
      button.classList.add('is-unavailable');
      const badge = el('span', { class: 'dock-badge', text: 'N/A' });
      badge.title = mod.unavailableReason || 'No backend support';
      button.append(badge);
      button.setAttribute('aria-description', mod.unavailableReason || 'No backend support');
    }
    button.addEventListener('click', () => {
      if (!mod.available) {
        onOpen(mod.id, { blocked: true });
        return;
      }
      onOpen(mod.id);
    });
    buttons.set(mod.id, button);
    frag.append(button);
  }
  host.replaceChildren(frag);

  on('module:active', (id) => {
    for (const [modId, button] of buttons) {
      const active = modId === id;
      setClass(button, 'is-active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    }
  });
}

/** Surface an alert dot on a module (e.g. pending permission, critical disk). */
export function flagModule(id, level = 'alert') {
  const button = buttons.get(id);
  if (!button) return;
  button.classList.add('has-alert');
  if (level === 'critical') {
    button.classList.add('is-unavailable');
    button.classList.remove('has-alert');
  }
}

export function clearModuleFlag(id) {
  const button = buttons.get(id);
  if (button) button.classList.remove('has-alert');
}

export function focusDockItem(id) {
  buttons.get(id)?.focus();
}

export function dockItemIds() {
  return registry.map((m) => m.id);
}

export function isModuleAvailable(id) {
  const mod = registry.find((m) => m.id === id);
  return mod ? mod.available !== false : false;
}

