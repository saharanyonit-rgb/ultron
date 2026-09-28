/**
 * JARVIS — SSE connection.
 *
 * Consumes `/api/events` (unchanged backend endpoint), fans events into the
 * bus, and drives the real link state. EventSource already reconnects on its
 * own; we only translate its lifecycle into application state.
 */

import { on, emit } from '../lib/bus.js';
import { setLink, setStreaming } from '../core/store.js';
import * as log from '../core/activity-log.js';
import * as toast from '../core/toast.js';

const STREAM_EVENTS = [
  'goal_created', 'planning', 'plan_created', 'task_started', 'agent_selected',
  'step_started', 'step_completed', 'step_failed', 'verifying', 'verified',
  'retrying', 'recovering', 'replaning', 'completed', 'failed', 'error',
  'execution_paused', 'execution_resumed', 'execution_stopped',
  'permission_required', 'permission_decided', 'voice_state', 'shutting_down',
  'brain_routing', 'agent.selected', 'agent.started', 'agent.progress',
  'agent.completed', 'agent.failed', 'verification.started',
  'verification.completed', 'replan.started', 'replan.completed', 'brain_error',
];

let source = null;
let wasOnline = false;
let closedByUs = false;

export function initSSE() {
  if (source) return;
  closedByUs = false;
  setLink('connecting');
  log.push('system', 'Opening event stream to backend');

  try {
    source = new EventSource('/api/events');
  } catch (err) {
    setLink('offline');
    log.push('error', `Event stream unavailable: ${err.message}`);
    return;
  }

  source.onopen = () => {
    setLink('online');
    setStreaming(true);
    if (!wasOnline) {
      wasOnline = true;
      log.push('success', 'Event stream established — backend online');
      toast.success('LINK ESTABLISHED', 'JARVIS backend connected');
    }
  };

  source.onerror = () => {
    // EventSource retries by default; reflect the gap honestly meanwhile.
    setStreaming(false);
    if (source && source.readyState === EventSource.CLOSED && !closedByUs) {
      setLink('offline');
      log.push('error', 'Event stream closed — link lost');
      toast.error('LINK LOST', 'Backend connection dropped, retrying');
    } else {
      setLink('connecting');
    }
  };

  for (const type of STREAM_EVENTS) {
    source.addEventListener(type, (event) => {
      let data = {};
      try {
        data = JSON.parse(event.data);
      } catch {
        data = { raw: event.data };
      }
      emit(`sse:${type}`, data);
    });
  }
}

export function closeSSE() {
  closedByUs = true;
  if (source) {
    source.close();
    source = null;
  }
  setStreaming(false);
  setLink('offline');
}

export function isStreaming() {
  return Boolean(source && source.readyState === EventSource.OPEN);
}

export { on };
