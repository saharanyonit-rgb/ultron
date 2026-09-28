/**
 * JARVIS — System, Uptime, Armor and Tools modules.
 * Every value below is read from an existing backend endpoint.
 */

import { el, fmtBytes, fmtDuration, fmtNumber } from '../lib/dom.js';
import { on } from '../lib/bus.js';
import { get } from '../core/store.js';
import * as api from '../lib/api.js';
import * as log from '../core/activity-log.js';
import * as toast from '../core/toast.js';
import { setFooter, errorBlock } from '../ui/drawer.js';
import { section, row, meter, button, poll, reportError } from './kit.js';

/* ── SYSTEM ───────────────────────────────────────────────────────── */
function systemView(body) {
  body.append(section('CORE TELEMETRY', 'live'));
  const host = el('div', { class: 'mod-body' });
  body.append(host);

  const stop = poll(
    () => Promise.all([api.systemMetrics(), api.systemInfo()]),
    3000,
    ([metrics, info]) => {
      const m = metrics || {};
      host.replaceChildren(
        meter('CPU LOAD', m.cpu_percent, `${m.cpu_cores ?? '?'} cores · ${m.cpu_name || 'UNKNOWN'}`),
        meter('MEMORY', m.ram_percent, `${fmtBytes(m.ram_used)} / ${fmtBytes(m.ram_total)}`),
        m.temperature != null ? meter('THERMAL', m.temperature, 'sensor reported') : null,
        section('PLATFORM'),
        row('Operating system', info?.os),
        row('Release', info?.os_version),
        row('Machine', info?.machine),
        row('Processor', info?.processor),
        row('Python', info?.python_version),
        row('Hostname', info?.hostname),
        section('MEMORY SUBSYSTEM'),
        ...memoryRows(),
        section('AGENT ROSTER'),
        ...agentRows(),
      );
      const m2 = m.temperature;
      if (m2 != null) {
        const thermal = host.querySelectorAll('.meter')[2];
        // Temperature is degrees Celsius, not a percentage.
        if (thermal) {
          thermal.querySelector('.v').textContent = `${m2}°C`;
          thermal.querySelector('.meter-fill').style.width = `${Math.min(100, (m2 / 100) * 100)}%`;
        }
      }
    },
  );
  return stop;
}

function memoryRows() {
  const mem = get().memory;
  if (!mem) return [row('Memory', 'UNKNOWN')];
  return Object.entries(mem).map(([key, value]) =>
    row(key.replace(/_/g, ' ').toUpperCase(), `${value.status} · ${value.entries} entries`),
  );
}

function agentRows() {
  const agents = get().agents || [];
  if (!agents.length) return [row('Agents', 'UNKNOWN')];
  return agents.map((a) => row(a.name || a.type, `${a.status}${a.current_task ? ` · ${a.current_task}` : ''}`));
}

export const system = {
  id: 'system',
  title: 'System',
  label: 'SYSTEM',
  icon: 'i-system',
  subtitle: 'Live machine telemetry',
  available: true,
  render: systemView,
};

/* ── UPTIME ───────────────────────────────────────────────────────── */
function uptimeView(body) {
  body.append(section('SESSION', 'live'));
  const host = el('div', { class: 'mod-body' });
  body.append(host);

  const stop = poll(api.systemMetrics, 5000, (m) => {
    const s = get();
    host.replaceChildren(
      el('div', { class: 'stat-hero' }, [
        el('span', { class: 'stat-hero-value', text: fmtDuration(m?.uptime_seconds) }),
        el('span', { class: 'stat-hero-label', text: 'HOST UPTIME' }),
      ]),
      row('Session uptime', fmtDuration(s.backend?.uptime_seconds)),
      row('Link latency', s.latencyMs != null ? `${s.latencyMs} ms` : 'UNKNOWN'),
      row('Link state', s.link.toUpperCase()),
      row('Streaming', s.streaming ? 'ACTIVE' : 'IDLE'),
      section('STORAGE'),
      ...(m?.drives?.length
        ? m.drives.map((d) =>
            meter(`DRIVE ${String(d.letter || '').toUpperCase() || '?'}`,
              d.percent,
              `${fmtBytes(d.used)} / ${fmtBytes(d.total)}`),
          )
        : [row('Drives', 'UNKNOWN')]),
    );
  });
  return stop;
}

export const uptime = {
  id: 'uptime',
  title: 'Uptime',
  label: 'UPTIME',
  icon: 'i-uptime',
  subtitle: 'Session and storage health',
  available: true,
  render: uptimeView,
};

/* ── ARMOR (security + permissions) ───────────────────────────────── */
function armorView(body) {
  body.append(section('SECURITY POSTURE', 'live'));
  const host = el('div', { class: 'mod-body' });
  const pendingHost = el('div', { class: 'mod-body' });
  body.append(host, section('PENDING PERMISSIONS'), pendingHost);

  const stop = poll(
    () => Promise.all([api.securityStatus(), api.listPermissions()]),
    8000,
    ([sec, perms]) => {
      const s = sec || {};
      const risk = String(s.risk_level || 'unknown').toUpperCase();
      host.replaceChildren(
        row('Risk level', risk),
        row('Policy', s.policy),
        row('Pending approvals', s.pending_approvals),
        section('POLICY MATRIX'),
        ...Object.entries(s.permissions || {}).map(([k, v]) => row(k.replace(/_/g, ' ').toUpperCase(), v)),
      );

      const pending = perms?.pending || [];
      pendingHost.replaceChildren();
      if (!pending.length) {
        pendingHost.append(el('div', { class: 'state-block', text: 'NO PENDING REQUESTS' }));
        return;
      }
      for (const p of pending) {
        const card = el('div', { class: 'perm-card inline' }, [
          el('div', { class: 'perm-tool', text: `Tool: ${p.tool}` }),
          el('div', { class: 'perm-risk', text: `Risk: ${String(p.risk || '').toUpperCase()}` }),
          el('div', { class: 'perm-reason', text: p.reason || 'No reason supplied.' }),
          el('div', { class: 'perm-actions' }, [
            button('Deny', () => decide(p.permission_id, false)),
            button('Allow', () => decide(p.permission_id, true), 'primary'),
          ]),
        ]);
        pendingHost.append(card);
      }
    },
  );
  return stop;
}

async function decide(id, allow) {
  try {
    const result = allow ? await api.allowPermission(id) : await api.denyPermission(id);
    if (!result?.accepted) throw new Error(result?.error || 'Request expired');
    log.push(allow ? 'success' : 'info', `Permission ${allow ? 'allowed' : 'denied'}`);
    toast[allow ? 'success' : 'info'](allow ? 'PERMISSION GRANTED' : 'PERMISSION DENIED', id);
  } catch (err) {
    reportError('Permission decision', err);
  }
}

export const armor = {
  id: 'armor',
  title: 'Armor',
  label: 'ARMOR',
  icon: 'i-armor',
  subtitle: 'Security posture and approvals',
  available: true,
  render: armorView,
};

/* ── TOOLS (registry + execution control) ─────────────────────────── */
function toolsView(body) {
  body.append(section('REGISTERED TOOLS', 'live'));
  const host = el('div', { class: 'mod-body' });
  body.append(host);

  const stop = poll(api.tools, 20000, (data) => {
    const tools = data?.tools || [];
    host.replaceChildren();
    if (!tools.length) {
      host.append(el('div', { class: 'state-block', text: 'NO TOOLS REGISTERED' }));
      return;
    }
    for (const tool of tools) {
      const name = tool.name || tool.tool || 'UNKNOWN';
      const desc = tool.description || '';
      host.append(
        el('div', { class: 'tool-card' }, [
          el('div', { class: 'tool-head' }, [
            el('span', { class: 'tool-name', text: name }),
            el('span', { class: 'pill', text: tool.risk_level || tool.risk || 'standard' }),
          ]),
          desc ? el('div', { class: 'tool-desc', text: desc }) : null,
          el('div', { class: 'tool-meta', text: `${tool.category || 'general'} · ${fmtNumber(tool.call_count ?? 0)} calls` }),
        ]),
      );
    }
  });
  return stop;
}

export const tools = {
  id: 'tools',
  title: 'Tools',
  label: 'TOOLS',
  icon: 'i-settings',
  subtitle: 'Agent tool registry',
  available: true,
  render: toolsView,
};

/* ── EXECUTION CONTROL ────────────────────────────────────────────── */
export function initExecutionControls(root) {
  const bind = (id, fn, label) => {
    const button = root.querySelector(id);
    if (!button) return;
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const result = await fn();
        if (result?.status === 'no_controller') {
          toast.warning('NO CONTROLLER', 'The orchestrator is not attached to this server');
          log.push('warning', `${label}: backend reported no execution controller`);
        } else {
          toast.success(`${label.toUpperCase()}`, 'Backend acknowledged the request');
          log.push('system', `${label} sent to orchestrator`);
        }
      } catch (err) {
        reportError(label, err);
      } finally {
        button.disabled = false;
      }
    });
  };

  bind('#btn-pause', api.pauseExecution, 'Pause');
  bind('#btn-resume', api.resumeExecution, 'Resume');
  bind('#btn-stop', api.stopExecution, 'Stop');

  on('sse:execution_paused', () => setControlState('paused'));
  on('sse:execution_resumed', () => setControlState('executing'));
  on('sse:execution_stopped', () => setControlState('idle'));
  on('sse:completed', () => setControlState('idle'));
  on('sse:failed', () => setControlState('idle'));
}

function setControlState(state) {
  const map = {
    idle: ['IDLE', 'ok'],
    executing: ['RUNNING', 'ok'],
    paused: ['PAUSED', 'warn'],
    error: ['FAULT', 'crit'],
  };
  const [text, tone] = map[state] || ['UNKNOWN', 'is-unknown'];
  const node = document.getElementById('t-state');
  if (!node) return;
  node.textContent = text;
  node.classList.remove('is-unknown', 'ok', 'warn', 'crit');
  node.classList.add(tone);
}
