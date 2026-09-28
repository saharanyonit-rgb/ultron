/**
 * JARVIS — Telemetry poller.
 *
 * Polls the existing read-only endpoints at sensible intervals, skips work
 * while the tab is hidden, detects link loss, and only emits when a value
 * actually changed (so the HUD never re-renders for nothing).
 */

import { on } from '../lib/bus.js';
import { get, patch, setLink, pushCpuSample } from '../core/store.js';
import * as api from '../lib/api.js';
import * as log from '../core/activity-log.js';

const TASKS = [
  { name: 'orchestrator', fn: api.orchestrator, key: 'orchestrator', interval: 2000, critical: true },
  { name: 'metrics', fn: api.systemMetrics, key: 'metrics', interval: 3000, critical: true },
  { name: 'computer', fn: api.computerState, key: 'computer', interval: 6000 },
  { name: 'network', fn: api.networkStatus, key: 'network', interval: 10000 },
  { name: 'security', fn: api.securityStatus, key: 'security', interval: 12000 },
  { name: 'sysinfo', fn: api.systemInfo, key: 'systemInfo', interval: 120000 },
  { name: 'tools', fn: api.tools, key: 'tools', interval: 30000 },
  { name: 'agents', fn: api.agents, key: 'agents', interval: 30000 },
  { name: 'memory', fn: api.memory, key: 'memory', interval: 30000 },
  { name: 'status', fn: api.status, key: 'backend', interval: 5000, critical: true },
];

const timers = new Map();
const snapshots = new Map();
let consecutiveFailures = 0;
let latencyTimer = null;
let disposed = false;

function changed(name, data) {
  const key = JSON.stringify(data);
  if (snapshots.get(name) === key) return false;
  snapshots.set(name, key);
  return true;
}

async function tick(task) {
  if (disposed || document.hidden) return;
  try {
    const data = await task.fn();
    if (data === null || data === undefined) throw new Error('No response');

    if (consecutiveFailures >= 3 && get().link !== 'online') setLink('online');

    if (task.key === 'tools') {
      const tools = Array.isArray(data?.tools) ? data.tools : [];
      if (changed('tools', tools)) patch('tools', tools);
    } else if (task.key === 'agents') {
      const agents = Array.isArray(data) ? data : [];
      if (changed('agents', agents)) patch('agents', agents);
    } else if (changed(task.name, data)) {
      patch(task.key, data);
    }

    if (task.key === 'metrics' && typeof data?.cpu_percent === 'number') {
      pushCpuSample(data.cpu_percent);
    }
    if (task.key === 'backend' && typeof data?.uptime_seconds === 'number') {
      log.push('system', `Backend heartbeat · uptime ${Math.round(data.uptime_seconds)}s`);
    }
  } catch (err) {
    if (!task.critical) return;
    consecutiveFailures += 1;
    if (consecutiveFailures === 3) {
      setLink('offline');
      log.push('error', 'Backend unreachable — telemetry link lost');
    }
  }
}

async function measureLatency() {
  if (disposed || document.hidden) return;
  try {
    const ms = await api.probe();
    if (ms !== get().latencyMs) {
      patch('latencyMs', ms);
      on('telemetry', () => {});
    }
  } catch {
    consecutiveFailures += 1;
  }
}

function start() {
  for (const task of TASKS) {
    tick(task);
    timers.set(task.name, setInterval(() => tick(task), task.interval));
  }
  measureLatency();
  latencyTimer = setInterval(measureLatency, 5000);
}

function handleVisibility() {
  if (document.hidden) return;
  // Refresh immediately on return so the HUD is never stale.
  for (const task of TASKS) tick(task);
  measureLatency();
}

export function initTelemetry() {
  setLink('connecting');
  document.addEventListener('visibilitychange', handleVisibility);
  start();
}

export function disposeTelemetry() {
  disposed = true;
  for (const timer of timers.values()) clearInterval(timer);
  if (latencyTimer) clearInterval(latencyTimer);
  timers.clear();
  document.removeEventListener('visibilitychange', handleVisibility);
}
