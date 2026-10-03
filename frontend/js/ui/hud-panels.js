/**
 * JARVIS — Side telemetry panels (left: link/threat/node) plus the dock's
 * summary metrics. All values come from the store, which only holds real
 * backend readings.
 */

import { $, setText, setClass } from '../lib/dom.js';
import { on } from '../lib/bus.js';
import { get } from '../core/store.js';

/* ── Left: link panel ─────────────────────────────────────────────── */
function renderLinkRow() {
  const { link, latencyMs, network, backend } = get();

  setText($('#t-latency'), typeof latencyMs === 'number' ? `${latencyMs}ms` : '--');
  setClass($('#t-latency'), 'is-unknown', typeof latencyMs !== 'number');

  const uplink = network?.connected;
  const uplinkNode = $('#t-uplink');
  if (uplink === true) {
    setText(uplinkNode, 'CONNECTED');
    setClass(uplinkNode, 'is-unknown', false);
    setClass(uplinkNode, 'ok', true);
  } else if (uplink === false) {
    setText(uplinkNode, 'OFFLINE');
    setClass(uplinkNode, 'is-unknown', false);
    setClass(uplinkNode, 'crit', true);
  } else {
    setText(uplinkNode, 'UNKNOWN');
    setClass(uplinkNode, 'is-unknown', true);
  }

  const backendNode = $('#t-backend');
  if (backend) {
    const parts = [];
    parts.push(backend.status ? String(backend.status).toUpperCase() : 'RUNNING');
    if (backend.provider) parts.push(String(backend.provider).toUpperCase());
    if (backend.orchestrator) parts.push('ORCH');
    setText(backendNode, parts.join(' · '));
    setClass(backendNode, 'is-unknown', false);
    setClass(backendNode, 'ok', backend.status === 'running');
  } else {
    setText(backendNode, link === 'online' ? 'RUNNING' : 'UNREACHABLE');
    setClass(backendNode, 'is-unknown', link !== 'online');
    setClass(backendNode, 'crit', link === 'offline');
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
    renderDockMetrics();
  };

  on('telemetry', renderAll);
  on('link', renderAll);
  renderAll();
}
