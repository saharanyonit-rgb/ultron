/**
 * JARVIS — Permission prompts.
 * Real pending-permission requests streamed from the backend require an
 * explicit operator decision; nothing is auto-approved.
 */

import { el, escapeHtml } from '../lib/dom.js';
import { on } from '../lib/bus.js';
import * as api from '../lib/api.js';
import * as log from '../core/activity-log.js';
import * as toast from '../core/toast.js';
import { flagModule, clearModuleFlag } from '../ui/dock.js';

let activeRequest = null;
let node = null;

function build(request) {
  const scrim = el('div', { class: 'perm-scrim', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'perm-head' });
  const risk = String(request.risk || 'UNKNOWN').toUpperCase();
  const riskColour = risk === 'CRITICAL' || risk === 'HIGH' ? 'var(--danger)' : 'var(--warning)';

  const card = el('div', { class: 'perm-card' }, [
    el('div', { class: 'perm-head', id: 'perm-head', text: 'Permission required' }),
    el('div', { class: 'perm-tool', html: `Tool: <strong>${escapeHtml(request.tool)}</strong>` }),
    el('div', { class: 'perm-risk', style: `color:${riskColour}`, text: `Risk: ${risk}` }),
    el('div', { class: 'perm-reason', text: request.reason || 'No reason supplied by the backend.' }),
  ]);

  if (request.arguments && Object.keys(request.arguments).length) {
    card.append(
      el('div', { class: 'perm-args', text: `Arguments: ${JSON.stringify(request.arguments)}` }),
    );
  }

  const allow = el('button', { type: 'button', class: 'btn-mini primary', text: 'Allow' });
  const deny = el('button', { type: 'button', class: 'btn-mini', text: 'Deny' });
  const actions = el('div', { class: 'perm-actions' }, [deny, allow]);
  card.append(actions);
  scrim.append(card);

  let decided = false;
  const decide = async (approved) => {
    if (decided) return;
    decided = true;
    allow.disabled = true;
    deny.disabled = true;
    try {
      const result = approved
        ? await api.allowPermission(request.permission_id)
        : await api.denyPermission(request.permission_id);
      if (!result?.accepted) throw new Error(result?.error || 'Request expired or unknown');
      log.push(approved ? 'success' : 'info',
        `Permission ${approved ? 'granted' : 'denied'} · ${request.tool}`);
      toast[approved ? 'success' : 'info'](
        approved ? 'PERMISSION GRANTED' : 'PERMISSION DENIED',
        String(request.tool),
      );
    } catch (err) {
      log.push('error', `Permission decision failed: ${err.message}`);
      toast.error('PERMISSION FAULT', err.message);
    } finally {
      close();
    }
  };

  allow.addEventListener('click', () => decide(true));
  deny.addEventListener('click', () => decide(false));
  document.addEventListener('keydown', function onKey(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      document.removeEventListener('keydown', onKey);
      decide(false);
    }
  });

  return scrim;
}

function close() {
  if (node) node.remove();
  node = null;
  activeRequest = null;
  clearModuleFlag('armor');
}

export function showPermissionPrompt(request) {
  if (!request || !request.permission_id) return;
  if (activeRequest) return; // never stack prompts
  activeRequest = request;
  node = build(request);
  document.body.append(node);
  node.querySelector('.btn-mini.primary')?.focus();
  log.push('warning', `Permission requested · ${request.tool} (${request.risk})`);
  toast.warning('PERMISSION REQUEST', String(request.tool));
  flagModule('armor', 'alert');
}

export function initPermissions() {
  on('sse:permission_required', showPermissionPrompt);
  on('sse:permission_decided', (d) => {
    if (activeRequest && d && d.permission_id === activeRequest.permission_id) close();
  });
  on('link', (link) => {
    if (link === 'offline' && node) close();
  });
  on('teardown', close);
}
