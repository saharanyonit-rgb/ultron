/**
 * JARVIS — API client / backend adapter.
 *
 * Thin layer over the existing JARVIS HTTP + SSE API. No backend endpoint is
 * renamed or re-invented here: every path below already exists in
 * `ultron/web.py`. This module only adds timeouts, cancellation, change
 * detection and a single place for the UI to talk to the core.
 */

const BASE = '';
const DEFAULT_TIMEOUT = 8000;

class ApiError extends Error {
  constructor(message, { status = 0, path = '' } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.path = path;
  }
}

async function request(path, { method = 'GET', body, timeout = DEFAULT_TIMEOUT, signal } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  if (signal) signal.addEventListener('abort', () => controller.abort(), { once: true });

  try {
    const res = await fetch(BASE + path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      cache: 'no-cache',
      signal: controller.signal,
    });
    if (!res.ok) throw new ApiError(`HTTP ${res.status}`, { status: res.status, path });
    if (res.status === 204) return null;
    const text = await res.text();
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch {
      throw new ApiError('Malformed JSON response', { status: res.status, path });
    }
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err.name === 'AbortError') {
      throw new ApiError(signal?.aborted ? 'Cancelled' : 'Request timed out', { path });
    }
    throw new ApiError(err.message || 'Network unreachable', { path });
  } finally {
    clearTimeout(timer);
  }
}

const get = (path, opts) => request(path, opts);
const post = (path, body, opts = {}) => request(path, { method: 'POST', body: body ?? {}, ...opts });
const put = (path, body, opts = {}) => request(path, { method: 'PUT', body: body ?? {}, ...opts });
const del = (path, opts = {}) => request(path, { method: 'DELETE', ...opts });

/* ── Telemetry & status (existing endpoints) ─────────────────────── */
export const status = () => get('/api/status');
export const systemMetrics = () => get('/api/system/metrics', { timeout: 12000 });
export const networkStatus = () => get('/api/system/network', { timeout: 12000 });
export const systemInfo = () => get('/api/system/info');
export const securityStatus = () => get('/api/security');
export const computerState = () => get('/api/computer', { timeout: 12000 });
export const orchestrator = () => get('/api/orchestrator');
export const voiceState = () => get('/api/voice');
export const agents = () => get('/api/agents');
export const memory = () => get('/api/memory');
export const tools = () => get('/api/tools');
export const goals = () => get('/api/goals');
export const control = () => get('/api/control');

/* ── Intelligence ────────────────────────────────────────────────── */
export const submitGoal = (description, mode = 'chat') =>
  post('/api/goals', { description, mode });
export const getGoal = (id) => get(`/api/goals/${encodeURIComponent(id)}`);

/* ── Execution control ───────────────────────────────────────────── */
export const pauseExecution = () => post('/api/control/pause', {});
export const resumeExecution = () => post('/api/control/resume', {});
export const stopExecution = () => post('/api/control/stop', {});
export const executeCommand = (command, timeout = 60) =>
  post('/api/execute', { command, timeout }, { timeout: (timeout + 10) * 1000 });

/* ── Voice pipeline ──────────────────────────────────────────────── */
export const speak = (text) => post('/api/voice/speak', { text }, { timeout: 60000 });
export const listen = (timeout = 10) =>
  post('/api/voice/listen', { timeout }, { timeout: (timeout + 25) * 1000 });
export const interruptVoice = () => post('/api/voice/interrupt', {});

/* ── Vision ──────────────────────────────────────────────────────── */
export const analyzeVision = (prompt, path) =>
  post('/api/vision/analyze', { prompt, path }, { timeout: 90000 });

/* ── Notes ───────────────────────────────────────────────────────── */
export const listNotes = (tag) => get(`/api/notes${tag ? `?tag=${encodeURIComponent(tag)}` : ''}`);
export const createNote = (data) => post('/api/notes', data);
export const updateNote = (id, data) => put(`/api/notes/${encodeURIComponent(id)}`, data);
export const deleteNote = (id) => del(`/api/notes/${encodeURIComponent(id)}`);

/* ── Calendar ────────────────────────────────────────────────────── */
export const listEvents = (fromTime, toTime) => {
  const params = new URLSearchParams();
  if (fromTime) params.set('from_time', fromTime);
  if (toTime) params.set('to_time', toTime);
  const q = params.toString();
  return get(`/api/calendar/events${q ? `?${q}` : ''}`);
};
export const createEvent = (data) => post('/api/calendar/events', data);
export const updateEvent = (id, data) => put(`/api/calendar/events/${encodeURIComponent(id)}`, data);
export const deleteEvent = (id) => del(`/api/calendar/events/${encodeURIComponent(id)}`);

/* ── Reminders ───────────────────────────────────────────────────── */
export const listReminders = () => get('/api/reminders');
export const createReminder = (data) => post('/api/reminders', data);
export const deleteReminder = (id) => del(`/api/reminders/${encodeURIComponent(id)}`);

/* ── Permissions ─────────────────────────────────────────────────── */
export const listPermissions = () => get('/api/permissions');
export const allowPermission = (id) => post(`/api/permissions/${encodeURIComponent(id)}/allow`, {});
export const denyPermission = (id) => post(`/api/permissions/${encodeURIComponent(id)}/deny`, {});

/* ── Android device bridge ───────────────────────────────────────── */
export const androidStatus = () => get('/api/android');

/* ── Additive read-only endpoints (see ultron/web_modules.py) ────── */
/**
 * Fetch current conditions.
 * `place` is a free-text city name; `lat`/`lon` are raw browser coordinates and
 * take precedence when present, since geocoding a coordinate string fails.
 */
export const weather = (place, { signal, lat, lon } = {}) => {
  let q = '';
  if (typeof lat === 'number' && typeof lon === 'number') {
    q = `?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`;
  } else if (place) {
    q = `?q=${encodeURIComponent(place)}`;
  }
  return get(`/api/weather${q}`, { timeout: 12000, signal });
};
export const news = (signal) => get('/api/news', { timeout: 15000, signal });

/* ── Health probe used for link + latency ────────────────────────── */
export async function probe() {
  const started = performance.now();
  await status();
  return Math.round(performance.now() - started);
}

