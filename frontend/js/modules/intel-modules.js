/**
 * JARVIS — Chat and activity log modules.
 */

import { el, relativeTime } from '../lib/dom.js';
import { on } from '../lib/bus.js';
import * as log from '../core/activity-log.js';
import { renderChatModule, renderer as chatRenderer } from '../ui/chat-view.js';
import { setRenderer } from '../features/chat.js';
import { section, button } from './kit.js';

/* ── CHAT ─────────────────────────────────────────────────────────── */
export const chat = {
  id: 'chat',
  title: 'Chat',
  label: 'CHAT',
  icon: 'i-chat',
  subtitle: 'Command the core',
  available: true,
  render: (body) => {
    setRenderer(chatRenderer);
    return renderChatModule(body);
  },
};

/* ── LOG ──────────────────────────────────────────────────────────── */
const FILTERS = [
  { id: 'all', label: 'ALL' },
  { id: 'system', label: 'SYSTEM' },
  { id: 'info', label: 'INFO' },
  { id: 'tool', label: 'TOOLS' },
  { id: 'success', label: 'OK' },
  { id: 'warning', label: 'WARN' },
  { id: 'error', label: 'FAULTS' },
];

let activeFilter = 'all';
let listNode = null;
let countNode = null;

function paint() {
  if (!listNode) return;
  const entries = log.list(activeFilter);
  if (countNode) countNode.textContent = `${entries.length} of ${log.count()}`;
  listNode.replaceChildren();
  if (!entries.length) {
    listNode.append(
      el('div', { class: 'state-block' }, [
        el('span', { class: 'h', text: 'NO ENTRIES' }),
        el('span', { class: 'd', text: activeFilter === 'all' ? 'No events recorded yet.' : 'No entries for this filter.' }),
      ]),
    );
    return;
  }
  for (const entry of entries) {
    listNode.append(
      el('div', { class: `log-row lv-${entry.level}` }, [
        el('span', { class: 'log-time', text: new Date(entry.at).toLocaleTimeString(undefined, { hour12: false }) }),
        el('span', { class: 'log-level', text: entry.level.toUpperCase() }),
        el('span', { class: 'log-msg', text: entry.message }),
        entry.detail ? el('span', { class: 'log-detail', text: entry.detail }) : null,
      ]),
    );
  }
  listNode.scrollTop = listNode.scrollHeight;
}

function logView(body) {
  const filterRow = el('div', { class: 'button-row' });
  for (const f of FILTERS) {
    const chip = button(f.label, () => {
      activeFilter = f.id;
      for (const chipNode of filterRow.children) {
        chipNode.classList.toggle('is-active', chipNode.dataset.filter === f.id);
      }
      paint();
    }, 'soft');
    chip.dataset.filter = f.id;
    if (f.id === activeFilter) chip.classList.add('is-active');
    filterRow.append(chip);
  }

  listNode = el('div', { class: 'log-list scrollable' });
  countNode = el('span', { class: 'mod-section-meta' });

  const unsubscribe = on('log:entry', paint);
  const onCleared = () => paint();

  body.append(
    section('ACTIVITY LOG'),
    el('div', { class: 'mod-section-head' }, [countNode]),
    filterRow,
    el('div', { class: 'button-row' }, [
      button('Copy', () => copyLog(), 'soft'),
      button('Clear', () => log.clear(), 'soft danger'),
    ]),
    listNode,
  );
  paint();

  return () => {
    unsubscribe();
    onCleared?.();
    listNode = null;
    countNode = null;
  };
}

async function copyLog() {
  const text = log.all().map((e) => {
    const stamp = new Date(e.at).toISOString();
    return `${stamp} [${e.level.toUpperCase()}] ${e.message}${e.detail ? ` — ${e.detail}` : ''}`;
  }).join('\n');
  try {
    await navigator.clipboard.writeText(text);
    log.push('info', 'Activity log copied to clipboard');
  } catch (err) {
    log.push('error', `Clipboard unavailable: ${err.message}`);
  }
}

export const logModule = {
  id: 'log',
  title: 'Log',
  label: 'LOG',
  icon: 'i-log',
  subtitle: 'Real event history',
  available: true,
  render: logView,
};
