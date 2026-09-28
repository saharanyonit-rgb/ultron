/**
 * JARVIS — Minimal event bus.
 * Used to decouple UI modules from data sources (SSE / polling).
 */
const listeners = new Map();

export function on(event, handler) {
  if (!listeners.has(event)) listeners.set(event, new Set());
  listeners.get(event).add(handler);
  return () => off(event, handler);
}

export function once(event, handler) {
  const dispose = on(event, (payload) => {
    dispose();
    handler(payload);
  });
  return dispose;
}

export function off(event, handler) {
  const set = listeners.get(event);
  if (set) set.delete(handler);
}

export function emit(event, payload) {
  const set = listeners.get(event);
  if (!set) return;
  for (const handler of Array.from(set)) {
    try {
      handler(payload);
    } catch (err) {
      console.error(`[bus] handler failed for "${event}"`, err);
    }
  }
}

export function clear() {
  listeners.clear();
}
