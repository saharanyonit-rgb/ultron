/**
 * JARVIS — Central state store.
 *
 * Holds the latest real telemetry snapshot and notifies subscribers on change.
 * Nothing here fabricates data: a field stays `null` until the backend
 * actually reports it, and the UI renders `UNKNOWN` / `UNAVAILABLE`.
 */

import { emit } from '../lib/bus.js';

const state = {
  link: 'connecting',          // connecting | online | offline
  backend: null,               // GET /api/status
  metrics: null,               // GET /api/system/metrics
  network: null,               // GET /api/system/network
  systemInfo: null,            // GET /api/system/info
  security: null,              // GET /api/security
  computer: null,              // GET /api/computer
  orchestrator: null,          // GET /api/orchestrator
  voice: { state: 'idle', available: null },
  tools: [],
  agents: [],
  memory: null,                 // GET /api/memory
  weather: null,                // GET /api/weather (additive)
  news: null,                   // GET /api/news (additive)
  latencyMs: null,
  cpuHistory: new Array(56).fill(null),
  activeModule: null,
  lastEvent: null,
  streaming: false,             // true while the SSE stream is open
  weatherLocation: readPrefs().weatherLocation || '',
  weatherCoords: readPrefs().weatherCoords || null,
  strip: null,                  // precomputed status-strip text
};

export function get() {
  return state;
}

export function setLink(link) {
  if (state.link === link) return;
  state.link = link;
  emit('link', link);
}

export function patch(key, value) {
  const prev = state[key];
  if (prev === value) return;
  state[key] = value;
  emit(`telemetry:${key}`, value);
  emit('telemetry', { key, value, prev });
}

export function pushCpuSample(value) {
  if (typeof value !== 'number' || !isFinite(value)) return;
  const history = state.cpuHistory;
  history.push(value);
  if (history.length > 56) history.shift();
  emit('cpu:sample', value);
}

/* ── Persisted user preferences ─────────────────────────────────── */
const PREFS_KEY = 'jarvis.prefs';

function readPrefs() {
  try {
    const parsed = JSON.parse(localStorage.getItem(PREFS_KEY) || '{}');
    const out = {};
    if (parsed && typeof parsed.weatherLocation === 'string') out.weatherLocation = parsed.weatherLocation;
    if (parsed && parsed.weatherCoords && typeof parsed.weatherCoords.lat === 'number' && typeof parsed.weatherCoords.lon === 'number') {
      out.weatherCoords = { lat: parsed.weatherCoords.lat, lon: parsed.weatherCoords.lon };
    }
    return out;
  } catch {
    return {};
  }
}

function writePrefs(patch) {
  try {
    const next = { ...readPrefs(), ...patch };
    localStorage.setItem(PREFS_KEY, JSON.stringify(next));
  } catch {
    /* storage may be unavailable (private mode) - preferences are optional */
  }
}

/** The city used by the weather module. Empty until the operator sets one. */
export function getWeatherLocation() {
  return state.weatherLocation;
}

/**
 * Remember the weather location.
 * A city is stored as text; browser coordinates are stored separately because
 * the backend must not try to geocode them.
 */
export function setWeatherLocation(place, coords = null) {
  const value = String(place || '').trim();
  state.weatherLocation = value;
  state.weatherCoords = coords && Number.isFinite(coords.lat) && Number.isFinite(coords.lon)
    ? { lat: coords.lat, lon: coords.lon }
    : null;
  writePrefs({ weatherLocation: value, weatherCoords: state.weatherCoords });
  emit('prefs:weatherLocation', value);
}

/** Resolve the location to send with a weather request. */
export function getWeatherQuery() {
  if (state.weatherCoords) return { lat: state.weatherCoords.lat, lon: state.weatherCoords.lon };
  return { place: state.weatherLocation || null };
}

export function setStreaming(value) {
  const next = Boolean(value);
  if (state.streaming === next) return;
  state.streaming = next;
  emit('telemetry:streaming', next);
}

export function setActiveModule(id) {
  if (state.activeModule === id) return;
  state.activeModule = id;
  emit('module:active', id);
}

export function setLastEvent(event) {
  state.lastEvent = event;
  emit('event:latest', event);
}

/* Convenience selectors ------------------------------------------------ */
export const cpuPercent = () => (typeof state.metrics?.cpu_percent === 'number' ? state.metrics.cpu_percent : null);
export const ramPercent = () => (typeof state.metrics?.ram_percent === 'number' ? state.metrics.ram_percent : null);

export function severityFor(percent, { warn = 70, crit = 90 } = {}) {
  if (typeof percent !== 'number' || !isFinite(percent)) return 'unknown';
  if (percent >= crit) return 'critical';
  if (percent >= warn) return 'warning';
  return 'normal';
}

