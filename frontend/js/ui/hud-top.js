/**
 * JARVIS — Top HUD: identity, link state, clock, weather, system status strip.
 * Every value is read from the store (which only contains real backend data).
 */

import { $, setText, setClass, setClassName, formatClock, formatDate } from '../lib/dom.js';
import { on } from '../lib/bus.js';
import { get, patch, severityFor, getWeatherQuery } from '../core/store.js';
import * as api from '../lib/api.js';
import * as log from '../core/activity-log.js';

let clockTimer = null;
let weatherController = null;
let weatherTimer = null;

/* ── Clock ────────────────────────────────────────────────────────── */
function startClock() {
  const timeNode = $('#clock-time');
  const dateNode = $('#clock-date');
  const tick = () => {
    const now = new Date();
    setText(timeNode, formatClock(now));
    setText(dateNode, formatDate(now));
  };
  tick();
  // Align to the next second boundary so the display never skips.
  const delay = 1000 - (Date.now() % 1000);
  clockTimer = setTimeout(function run() {
    tick();
    clockTimer = setTimeout(run, 1000);
  }, delay);
}

/* ── Link / identity ──────────────────────────────────────────────── */
function renderLink(link) {
  document.body.dataset.link = link;

  const label = link === 'online' ? 'ONLINE' : link === 'offline' ? 'OFFLINE' : 'CONNECTING';
  setText($('#link-label'), label);
  setText($('#t-link'), label);
  setClass($('#t-link'), 'is-unknown', link !== 'online');
  setClass($('#t-link'), 'ok', link === 'online');
  setClass($('#t-link'), 'crit', link === 'offline');

  const pill = $('#link-pill');
  setClassName(pill, `status-pill ${link === 'online' ? 'online' : link === 'offline' ? 'offline' : 'connecting'}`);
  setText(pill, label);
}

/* ── Weather ──────────────────────────────────────────────────────── */
function renderWeather(data) {
  const widget = $('#weather-widget');
  const temp = $('#weather-temp');
  const loc = $('#weather-location');
  if (!widget) return;
  const current = data?.current;
  if (data?.available && current && typeof current.temperature_c === 'number') {
    widget.classList.remove('is-unavailable');
    widget.setAttribute('aria-label', `Weather: ${current.temperature_c.toFixed(1)} degrees in ${data.location}`);
    setText(temp, `${current.temperature_c.toFixed(1)}°C`);
    setText(loc, (data.location || 'UNKNOWN').toUpperCase());
  } else {
    widget.classList.add('is-unavailable');
    widget.setAttribute('aria-label', 'Weather unavailable. Open weather module for details.');
    setText(temp, data && data.available === false ? 'UNAVAILABLE' : '--');
    setText(loc, data && data.reason ? String(data.reason).toUpperCase().slice(0, 22) : 'UNAVAILABLE');
  }
}

export async function refreshWeather() {
  if (weatherController) weatherController.abort();
  weatherController = new AbortController();

  const { place, lat, lon } = getWeatherQuery();
  if (!place && lat === undefined) {
    // No location chosen yet: say so rather than pretending the feed failed.
    const state = { available: false, reason: 'set location' };
    patch('weather', state);
    renderWeather(state);
    return;
  }

  try {
    const data = await api.weather(place, { signal: weatherController.signal, lat, lon });
    patch('weather', { available: true, ...data });
    renderWeather({ available: true, ...data });
  } catch (err) {
    if (err.message === 'Cancelled') return;
    const reason = err.status === 404 ? 'not found' : 'unreachable';
    patch('weather', { available: false, reason });
    renderWeather({ available: false, reason });
  }
}

function startWeather() {
  refreshWeather();
  // Weather changes slowly; 10 minutes is plenty and keeps the UI calm.
  weatherTimer = setInterval(refreshWeather, 10 * 60 * 1000);
  // A new location chosen in the module refreshes the widget immediately.
  on('prefs:weatherLocation', () => refreshWeather());
}

/* ── System status strip ──────────────────────────────────────────── */
const stripText = () => $('#status-strip-text');
const stripMeta = () => $('#status-strip-meta');
const strip = () => $('#status-strip');

export function renderStatusStrip() {
  const { metrics, link, orchestrator } = get();
  const stripNode = strip();

  if (link === 'offline') {
    stripNode.className = 'status-strip sev-critical';
    setText(stripText(), 'BACKEND OFFLINE');
    setText(stripMeta(), 'RECONNECT ATTEMPT ACTIVE');
    return;
  }
  if (link === 'connecting') {
    stripNode.className = 'status-strip';
    setText(stripText(), 'CONNECTING');
    setText(stripMeta(), 'HANDSHAKE IN PROGRESS');
    return;
  }

  const execState = orchestrator?.state;
  if (execState && execState !== 'idle') {
    stripNode.className = 'status-strip';
    setText(stripText(), `EXECUTION ${String(execState).toUpperCase()}`);
    setText(stripMeta(), orchestrator?.current_goal?.description?.slice(0, 48) || '');
    return;
  }

  const severities = [
    { label: 'CPU', value: metrics?.cpu_percent },
    { label: 'RAM', value: metrics?.ram_percent },
  ];

  const critical = severities.find((s) => severityFor(s.value) === 'critical');
  if (critical) {
    stripNode.className = 'status-strip sev-critical';
    setText(stripText(), `${critical.label} CRITICAL`);
    setText(stripMeta(), `${Math.round(critical.value)}% · THRESHOLD 90%`);
    return;
  }

  const warning = severities.find((s) => severityFor(s.value) === 'warning');
  if (warning) {
    stripNode.className = 'status-strip sev-warning';
    setText(stripText(), `${warning.label} LOAD HIGH`);
    setText(stripMeta(), `${Math.round(warning.value)}% · THRESHOLD 70%`);
    return;
  }

  stripNode.className = 'status-strip';
  setText(stripText(), 'SYSTEMS NOMINAL');
  const parts = [];
  if (typeof metrics?.cpu_percent === 'number') parts.push(`CPU ${Math.round(metrics.cpu_percent)}%`);
  if (typeof metrics?.ram_percent === 'number') parts.push(`RAM ${Math.round(metrics.ram_percent)}%`);
  setText(stripMeta(), parts.join(' · ') || 'AWAITING TELEMETRY');
}

/* ── Boot ─────────────────────────────────────────────────────────── */
export function initTopHud() {
  startClock();
  startWeather();

  on('link', (link) => {
    renderLink(link);
    renderStatusStrip();
  });
  on('telemetry', ({ key }) => {
    if (key === 'metrics' || key === 'orchestrator') renderStatusStrip();
  });

  renderLink(get().link);
  renderStatusStrip();
}

export function disposeTopHud() {
  if (clockTimer) clearTimeout(clockTimer);
  if (weatherTimer) clearInterval(weatherTimer);
  if (weatherController) weatherController.abort();
  log.clear();
}
