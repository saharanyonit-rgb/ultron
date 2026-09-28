/**
 * JARVIS — Activity log.
 *
 * A bounded ring buffer fed by real backend events (SSE) and real client
 * lifecycle events (connect / disconnect / command outcome / tool execution).
 * Duplicate consecutive messages are collapsed so the log never floods.
 */

import { emit } from '../lib/bus.js';

const MAX_ENTRIES = 500;

export const LEVELS = ['info', 'success', 'warning', 'error', 'system', 'tool'];

let entries = [];
let seq = 0;
let lastMessage = null;
let lastLevel = null;
let lastAt = 0;

function normaliseLevel(level) {
  const value = String(level || 'info').toLowerCase();
  return LEVELS.includes(value) ? value : 'info';
}

export function push(level, message, detail = null) {
  const now = Date.now();
  const text = String(message ?? '').trim();
  if (!text) return null;

  // Collapse identical consecutive events inside a short window.
  if (text === lastMessage && normaliseLevel(level) === lastLevel && now - lastAt < 1500) {
    return null;
  }
  lastMessage = text;
  lastLevel = normaliseLevel(level);
  lastAt = now;

  const entry = {
    id: ++seq,
    at: now,
    level: normaliseLevel(level),
    message: text,
    detail: detail === null ? null : typeof detail === 'string' ? detail : safeJson(detail),
  };

  entries.push(entry);
  if (entries.length > MAX_ENTRIES) entries = entries.slice(-MAX_ENTRIES);
  emit('log:entry', entry);
  return entry;
}

function safeJson(value) {
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function list(filter = null) {
  if (!filter || filter === 'all') return entries.slice();
  return entries.filter((e) => e.level === filter);
}

export function all() {
  return entries.slice();
}

export function count() {
  return entries.length;
}

export function clear() {
  entries = [];
  seq = 0;
  lastMessage = null;
  lastLevel = null;
  emit('log:cleared', null);
}

export function latest() {
  return entries.length ? entries[entries.length - 1] : null;
}
