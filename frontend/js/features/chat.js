/**
 * JARVIS — Intelligence / chat.
 *
 * Sends user input to the real goal pipeline (`POST /api/goals`) and renders
 * the events the orchestrator streams back over SSE: plans, tool executions,
 * verification, completion and failure. No synthetic assistant replies.
 */

import { on } from '../lib/bus.js';
import { get } from '../core/store.js';
import { setCoreState, setTranscript } from '../ui/hud-core.js';
import * as api from '../lib/api.js';
import * as log from '../core/activity-log.js';
import * as toast from '../core/toast.js';
import { setVoiceReplyHandler, speak, isSessionActive } from './voice.js';

/* Rendering is delegated to the chat module view. */
let render = () => {};
let composer = null;

let planSteps = [];
let planNode = null;
let currentStep = -1;
let awaitingFinal = false;
let goalId = null;
let activeProvider = null;
/*
 * The backend broadcasts `goal_created` from inside `POST /api/goals`, so the
 * SSE frame can land *before* the fetch resolves and `goalId` is still null.
 * This records the description we already rendered optimistically so the echo
 * is not painted a second time.
 */
let localEcho = null;

const STATE_TO_CORE = {
  planning: 'processing',
  executing: 'executing',
  verifying: 'processing',
  waiting: 'executing',
  recovering: 'processing',
  replanning: 'processing',
  completed: 'idle',
  error: 'error',
  offline: 'offline',
  shutting_down: 'offline',
};

/* ── Public API ───────────────────────────────────────────────────── */
export function setRenderer(fn) {
  render = fn;
}

export async function submit(text) {
  const message = String(text || '').trim();
  if (!message) return;
  if (!await ensureConnected()) return;

  render.user(message);
  setTranscript(message);
  setCoreState('processing');
  awaitingFinal = true;
  localEcho = message;
  resetPlan();

  try {
    const result = await api.submitGoal(message, 'chat');
    goalId = result?.id || null;
    activeProvider = null;
    localEcho = null;
    if (!goalId) throw new Error('Backend accepted no goal identifier');
    log.push('system', `Goal submitted · ${goalId}`);
  } catch (err) {
    awaitingFinal = false;
    localEcho = null;
    setCoreState(get().link === 'offline' ? 'offline' : 'error');
    render.system('COMMAND REJECTED — backend unreachable or errored');
    log.push('error', `Goal submission failed: ${err.message}`);
    toast.error('COMMAND FAILED', err.message);
    setTimeout(() => setCoreState('idle'), 2400);
  }
}

async function ensureConnected() {
  if (get().link === 'offline') {
    render.system('BACKEND OFFLINE — start the JARVIS core to continue');
    log.push('error', 'Command blocked: backend offline');
    toast.error('BACKEND OFFLINE', 'Start JARVIS, then retry');
    return false;
  }
  return true;
}

function resetPlan() {
  planSteps = [];
  currentStep = -1;
  if (planNode) {
    planNode.remove();
    planNode = null;
  }
}

/* ── SSE wiring: real execution events ────────────────────────────── */
function wireEvents() {
  on('sse:goal_created', (d) => {
    if (!d) return;
    if (goalId && d.id === goalId) return; // already rendered optimistically
    if (localEcho !== null && (d.description || '') === localEcho) {
      // Our own submission echoing back before the fetch resolved.
      localEcho = null;
      return;
    }
    render.user(d.description || '');
    setCoreState('processing');
    awaitingFinal = true;
    resetPlan();
  });

  on('sse:planning', () => {
    setCoreState('processing');
    log.push('system', 'Planning request');
  });

  on('sse:plan_created', (d) => {
    const count = d?.metadata?.step_count;
    const steps = d?.metadata?.steps;
    log.push('info', count ? `Plan created · ${count} steps` : 'Plan created');
    if (steps?.length) {
      planSteps = steps.map((text) => ({ text: String(text), status: 'pending' }));
      planNode = render.plan('EXECUTION PLAN', planSteps);
    }
    setCoreState('executing');
  });

  on('sse:agent_selected', (d) => {
    const name = d?.metadata?.agent_name;
    if (name) log.push('tool', `Agent selected · ${name}`);
  });

  on('sse:task_started', () => setCoreState('executing'));

  on('sse:step_started', (d) => {
    setCoreState('executing');
    const message = d?.message || 'Step started';
    log.push('tool', message);
    if (d?.metadata?.objective) {
      const idx = planSteps.findIndex((s) => s.text === d.metadata.objective && s.status === 'pending');
      if (idx >= 0) {
        currentStep = idx;
        setStep(idx, 'running');
      }
    } else {
      currentStep += 1;
      if (currentStep < planSteps.length) setStep(currentStep, 'running');
    }
  });

  on('sse:step_completed', (d) => {
    const message = d?.message || d?.description || 'Step completed';
    log.push('success', message);
    if (currentStep >= 0 && currentStep < planSteps.length) setStep(currentStep, 'completed');
  });

  on('sse:step_failed', (d) => {
    const message = d?.message || d?.description || 'Step failed';
    const err = d?.metadata?.error || '';
    log.push('error', err ? `${message} — ${err}` : message);
    if (currentStep >= 0 && currentStep < planSteps.length) setStep(currentStep, 'failed');
  });

  on('sse:verifying', () => setCoreState('processing'));
  on('sse:verified', (d) => {
    if (d?.metadata && d.metadata.passed === false) log.push('warning', 'Verification reported a failure');
  });

  on('sse:retrying', (d) => {
    setCoreState('processing');
    const retry = d?.metadata?.retry;
    const max = d?.metadata?.max_retries;
    log.push('warning', retry ? `Retrying step (attempt ${retry}/${max})` : 'Retrying step');
  });

  on('sse:recovering', (d) => {
    setCoreState('processing');
    if (d?.message) log.push('warning', d.message);
  });

  on('sse:replaning', (d) => {
    setCoreState('processing');
    if (d?.message) log.push('warning', d.message);
  });

  on('sse:execution_paused', () => {
    log.push('system', 'Execution paused');
    render.system('EXECUTION PAUSED');
  });
  on('sse:execution_resumed', () => {
    log.push('system', 'Execution resumed');
    setCoreState('executing');
  });
  on('sse:execution_stopped', () => {
    log.push('system', 'Execution stopped by operator');
    render.system('EXECUTION STOPPED');
    awaitingFinal = false;
    resetPlan();
    setCoreState('idle');
  });

  on('sse:completed', (d) => {
    const text = d?.response || 'Task completed.';
    render.assistant(text);
    log.push('success', 'Goal completed');
    awaitingFinal = false;
    setCoreState('idle');
    resetPlan();
    toast.success('TASK COMPLETE', text.slice(0, 90));
    if (isSessionActive()) speak(text);
  });

  on('sse:failed', (d) => {
    const text = d?.message || d?.error || 'Task failed.';
    render.error(text);
    log.push('error', `Goal failed — ${text}`);
    awaitingFinal = false;
    setCoreState('error');
    resetPlan();
    toast.error('TASK FAILED', text.slice(0, 90));
    setTimeout(() => setCoreState('idle'), 2600);
  });

  on('sse:error', (d) => {
    const text = d?.error || d?.message || d?.raw || 'Unhandled backend error';
    render.error(text);
    log.push('error', text);
    if (awaitingFinal) {
      awaitingFinal = false;
      setCoreState('error');
      setTimeout(() => setCoreState('idle'), 2400);
    }
  });

  on('sse:shutting_down', () => {
    render.system('Backend is shutting down');
    awaitingFinal = false;
    resetPlan();
  });
}

function setStep(index, status) {
  if (!planSteps[index]) return;
  planSteps[index].status = status;
  render.updatePlan(planNode, planSteps);
}

/* ── Boot ─────────────────────────────────────────────────────────── */
export function initChat() {
  wireEvents();
  // Voice replies route through the same goal pipeline.
  setVoiceReplyHandler(async (text) => {
    await submit(text);
  });
  on('teardown', () => {
    localEcho = null;
    resetPlan();
  });
}

