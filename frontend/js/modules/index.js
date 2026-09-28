/**
 * JARVIS — Module registry.
 * Single source of truth for what the dock renders and what the drawer opens.
 */

import { system, uptime, armor, tools, initExecutionControls } from './system-modules.js';
import { notes, weather, news } from './data-modules.js';
import { camera, focus, telegram } from './media-modules.js';
import { chat, logModule } from './intel-modules.js';
import { open as openDrawer } from '../ui/drawer.js';
import * as log from '../core/activity-log.js';
import * as toast from '../core/toast.js';

export const MODULES = [
  system,
  weather,
  camera,
  uptime,
  news,
  notes,
  focus,
  telegram,
  armor,
  tools,
  logModule,
  chat,
];

const byId = new Map(MODULES.map((m) => [m.id, m]));

export function getModule(id) {
  return byId.get(id) || null;
}

export function openModule(id, options = {}) {
  const mod = byId.get(id);
  if (!mod) return;

  if (mod.available === false) {
    const reason = mod.unavailableReason || 'No backend support for this module';
    log.push('warning', `Module unavailable: ${mod.title} — ${reason}`);
    toast.warning('MODULE UNAVAILABLE', reason);
    return;
  }
  if (options.blocked) return;

  openDrawer(mod.id, mod);
}

export function initModuleRouter() {
  window.addEventListener('jarvis:open-module', (event) => {
    openModule(event.detail);
  });
  // Global shortcuts.
  window.addEventListener('keydown', (event) => {
    const tag = document.activeElement?.tagName;
    const typing = tag === 'INPUT' || tag === 'TEXTAREA';
    if (typing || event.metaKey || event.ctrlKey || event.altKey) return;

    const map = {
      c: 'chat',
      s: 'system',
      n: 'notes',
      l: 'log',
      a: 'armor',
      f: 'focus',
      k: 'camera',
      w: 'weather',
      u: 'uptime',
      m: 'news',
      t: 'tools',
    };
    const id = map[event.key.toLowerCase()];
    if (!id) return;
    event.preventDefault();
    openModule(id);
  });
}

export { initExecutionControls };
