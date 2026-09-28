/**
 * JARVIS — Side telemetry panels (left: link/threat/node, right: storage,
 * execution control, active window) plus the CPU/RAM flanks around the core.
 * All values come from the store, which only holds real backend readings.
 */

import { $, setText, setClass, setWidth, formatBytes } from '../lib/dom.js';
import { on } from '../lib/bus.js';
import { get, severityFor } from '../core/store.js';
import { setClass as toggle } from '../lib/dom.js';

/* ── Left: link panel ─────────────────────────────────────────────── */
function renderLinkRow() {
  const { link, latencyMs, network, backend } = get();

  setText($('#t-latency'), typeof latencyMs === 'number' ? `${latencyMs}ms` : '--');
  toggle($('#t-latency'), 'is-unknown', typeof latencyMs !== 'number');

  const uplink = network?.connected;
  const uplinkNode = $('#t-uplink');
  if (uplink === true) {
    setText(uplinkNode, 'CONNECTED');
    toggle(uplinkNode, 'is-unknown', false);
    toggle(uplinkNode, 'ok', true);
  } else if (uplink === false) {
    setText(uplinkNode, 'OFFLINE');
    toggle(uplinkNode, 'is-unknown', false);
    toggle(uplinkNode, 'crit', true);
  } else {
    setText(uplinkNode, 'UNKNOWN');
    toggle(uplinkNode, 'is-unknown', true);
  }

  const backendNode = $('#t-backend');
  if (backend) {
    const parts = [];
    parts.push(backend.status ? String(backend.status).toUpperCase() : 'RUNNING');
    if (backend.provider) parts.push(String(backend.provider).toUpperCase());
    if (backend.orchestrator) parts.push('ORCH');
    setText(backendNode, parts.join(' · '));
    toggle(backendNode, 'is-unknown', false);
    toggle(backendNode, 'ok', backend.status === 'running');
  } else {
    setText(backendNode, link === 'online' ? 'RUNNING' : 'UNREACHABLE');
    toggle(backendNode, 'is-unknown', link !== 'online');
    toggle(backendNode, 'crit', link === 'offline');
  }
}

/* ── Left: threat panel ───────────────────────────────────────────── */
function renderThreat() {
  const { security, link } = get();
  const pill = $('#threat-pill');
  const riskNode = $('#t-risk');
  const approvalsNode = $('#t-approvals');
  const policyNode = $('#t-policy');

  if (!security) {
    // No security system reporting → say so honestly, never fake a threat.
    setText(pill, link === 'online' ? 'MONITORING' : 'UNAVAILABLE');
    pill.className = 'status-pill';
    setText(riskNode, 'MONITORING');
    riskNode.className = 'telemetry-val is-unknown';
    setText(approvalsNode, '--');
    approvalsNode.className = 'telemetry-val is-unknown';
    setText(policyNode, 'UNKNOWN');
    policyNode.className = 'telemetry-val is-unknown';
    return;
  }

  const risk = String(security.risk_level || 'unknown').toLowerCase();
  const pending = Number(security.pending_approvals || 0);
  const severity = risk === 'high' || risk === 'critical' ? 'crit' : risk === 'medium' ? 'warn' : 'ok';
  const label = risk.toUpperCase();

  setText(pill, label);
  pill.className = `status-pill ${severity === 'crit' ? 'critical' : severity === 'warn' ? 'warning' : 'online'}`;

  setText(riskNode, label);
  riskNode.className = `telemetry-val ${severity}`;

  setText(approvalsNode, String(pending));
  approvalsNode.className = `telemetry-val ${pending > 0 ? 'warn' : 'is-unknown'}`;

  setText(policyNode, String(security.policy || 'unknown').toUpperCase());
  policyNode.className = 'telemetry-val is-unknown';
}

/* ── Left: node panel ─────────────────────────────────────────────── */
function renderNode() {
  const { systemInfo, metrics, network } = get();

  const os = systemInfo?.os;
  setText($('#t-os'), os ? os.toUpperCase() : 'UNKNOWN');
  $('#t-os').className = `telemetry-val ${os ? '' : 'is-unknown'}`;

  const cpu = metrics?.cpu_name && metrics.cpu_name !== 'unknown' ? metrics.cpu_name : systemInfo?.processor;
  setText($('#t-cpu-name'), cpu && cpu !== 'unknown' ? String(cpu).toUpperCase().slice(0, 26) : 'UNKNOWN');
  $('#t-cpu-name').className = `telemetry-val ${cpu && cpu !== 'unknown' ? '' : 'is-unknown'}`;

  const host = network?.hostname || systemInfo?.hostname;
  setText($('#t-host'), host ? host.toUpperCase() : 'UNKNOWN');
  $('#t-host').className = `telemetry-val ${host ? '' : 'is-unknown'}`;

  const tempNode = $('#t-temp');
  const temp = metrics?.temperature;
  if (typeof temp === 'number' && isFinite(temp)) {
    setText(tempNode, `${temp.toFixed(1)}°C`);
    const sev = temp >= 85 ? 'crit' : temp >= 70 ? 'warn' : 'ok';
    tempNode.className = `telemetry-val ${sev}`;
  } else {
    setText(tempNode, 'NO SENSOR');
    tempNode.className = 'telemetry-val is-unknown';
  }
}

/* ── Core flanks: CPU / RAM ───────────────────────────────────────── */
function renderFlanks() {
  const { metrics, link } = get();

  const cpu = metrics?.cpu_percent;
  const ram = metrics?.ram_percent;

  const apply = (prefix, value, subText) => {
    const flank = $(`#flank-${prefix}`);
    const valNode = $(`#flank-${prefix}-val`);
    const fill = $(`#flank-${prefix}-fill`);
    const sub = $(`#flank-${prefix}-sub`);
    const sev = severityFor(value);

    if (typeof value === 'number' && isFinite(value)) {
      valNode.innerHTML = `${Math.round(value)}<small>%</small>`;
      setWidth(fill, value);
      flank.className = `flank${sev === 'warning' ? ' sev-warn' : sev === 'critical' ? ' sev-crit' : ''}`;
      setText(sub, subText);
    } else {
      valNode.innerHTML = `--<small>%</small>`;
      setWidth(fill, 0);
      flank.className = 'flank';
      setText(sub, link === 'offline' ? 'BACKEND OFFLINE' : 'AWAITING TELEMETRY');
    }
  };

  apply(
    'cpu',
    cpu,
    typeof metrics?.cpu_cores === 'number' ? `${metrics.cpu_cores} CORES` : 'AWAITING TELEMETRY',
  );

  const ramSub =
    typeof metrics?.ram_used === 'number' && typeof metrics?.ram_total === 'number'
      ? `${formatBytes(metrics.ram_used)} / ${formatBytes(metrics.ram_total)}`
      : 'AWAITING TELEMETRY';
  apply('ram', ram, ramSub);
}

/* ── Right: storage ───────────────────────────────────────────────── */
function renderStorage() {
  const { metrics } = get();
  const list = $('#disk-list');
  const pill = $('#disk-pill');
  if (!list) return;

  const drives = Array.isArray(metrics?.drives) ? metrics.drives : [];
  if (!drives.length) {
    list.replaceChildren();
    const row = document.createElement('div');
    row.className = 'telemetry-row';
    row.innerHTML = '<span class="telemetry-key">No drive data</span><span class="telemetry-val is-unknown">UNAVAILABLE</span>';
    list.append(row);
    setText(pill, 'UNAVAILABLE');
    pill.className = 'status-pill';
    return;
  }

  list.replaceChildren();
  let worst = 0;
  for (const drive of drives) {
    const pct = Number(drive.percent) || 0;
    worst = Math.max(worst, pct);
    const sev = pct >= 90 ? 'crit' : pct >= 75 ? 'warn' : 'ok';
    const row = document.createElement('div');
    row.className = 'telemetry-row';
    row.innerHTML = `
      <span class="telemetry-key">${drive.drive} · ${drive.used_gb} / ${drive.total_gb} GB</span>
      <span class="telemetry-val ${sev}">${pct.toFixed(0)}%</span>
      <div class="mini-meter"><div class="mini-meter-fill ${sev === 'crit' ? 'sev-crit' : sev === 'warn' ? 'sev-warn' : ''}" style="width:${Math.min(100, pct)}%"></div></div>
    `;
    list.append(row);
  }

  const sev = worst >= 90 ? 'critical' : worst >= 75 ? 'warning' : 'online';
  setText(pill, worst >= 90 ? 'CRITICAL' : worst >= 75 ? 'HIGH' : 'NOMINAL');
  pill.className = `status-pill ${sev}`;
}

/* ── Right: execution ─────────────────────────────────────────────── */
function renderExecution() {
  const { orchestrator } = get();
  const stateNode = $('#t-state');
  const goalNode = $('#t-goal');
  const progressNode = $('#t-progress');
  const fill = $('#progress-fill');

  const state = orchestrator?.state || 'idle';
  setText(stateNode, String(state).toUpperCase());
  const sev = state === 'error' || state === 'failed' ? 'crit' : state === 'idle' ? 'is-unknown' : 'ok';
  stateNode.className = `telemetry-val ${sev}`;

  const goal = orchestrator?.current_goal?.description;
  setText(goalNode, goal ? goal.toUpperCase().slice(0, 28) : 'NONE');
  goalNode.className = `telemetry-val ${goal ? '' : 'is-unknown'}`;

  const progress = typeof orchestrator?.progress === 'number' ? orchestrator.progress : null;
  const pct = progress === null ? null : Math.round(progress <= 1 ? progress * 100 : progress);
  setText(progressNode, pct === null ? '--' : `${pct}%`);
  progressNode.className = `telemetry-val ${pct === null ? 'is-unknown' : ''}`;
  setWidth(fill, pct ?? 0);
}

/* ── Right: active window ─────────────────────────────────────────── */
function renderDesktop() {
  const { computer } = get();
  const pill = $('#desktop-pill');
  const win = $('#t-window');
  const procs = $('#t-procs');

  const windowTitle = computer?.active_window;
  setText(win, windowTitle ? windowTitle.toUpperCase().slice(0, 30) : 'NONE DETECTED');
  win.className = `telemetry-val ${windowTitle ? '' : 'is-unknown'}`;

  const list = Array.isArray(computer?.running_applications) ? computer.running_applications : [];
  setText(procs, list.length ? String(list.length) : '--');
  procs.className = `telemetry-val ${list.length ? '' : 'is-unknown'}`;

  const ready = computer?.automation_ready;
  setText(pill, ready ? 'READY' : 'UNKNOWN');
  pill.className = `status-pill ${ready ? 'online' : ''}`;
}

/* ── Dock bottom-left metrics ─────────────────────────────────────── */
function renderDockMetrics() {
  const { metrics, backend } = get();

  const drives = Array.isArray(metrics?.drives) ? metrics.drives : [];
  if (drives.length) {
    const primary = drives[0];
    setText($('#dock-disk'), `${primary.used_gb} / ${primary.total_gb} GB`);
  } else {
    setText($('#dock-disk'), 'UNAVAILABLE');
  }

  const uptime = backend?.uptime_seconds;
  if (typeof uptime === 'number' && isFinite(uptime)) {
    const s = Math.floor(uptime);
    setText($('#dock-uptime'), `${String(Math.floor(s / 3600)).padStart(2, '0')}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`);
  } else {
    setText($('#dock-uptime'), '--:--:--');
  }
}

/* ── Wire up ──────────────────────────────────────────────────────── */
export function initPanels() {
  const renderAll = () => {
    renderLinkRow();
    renderThreat();
    renderNode();
    renderFlanks();
    renderStorage();
    renderExecution();
    renderDesktop();
    renderDockMetrics();
  };

  on('telemetry', renderAll);
  on('link', renderAll);
  renderAll();
}
