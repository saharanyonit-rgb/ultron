/* ═══════════════════════════════════════════════════════════════
   ULTRON UI — JavaScript
   ═══════════════════════════════════════════════════════════════ */

(function() {
  'use strict';

  // ═══ State ═══════════════════════════════════════════════════
  let appState = 'idle';
  let connected = false;
  let lastGoalId = null;  // Track last submitted goal to avoid double-adding

  const $ = id => document.getElementById(id);

  // ═══ DOM Refs ════════════════════════════════════════════════
  const dom = {
    netLabel: $('net-label'),
    vLatency: $('v-latency'),
    vUptime: $('v-uptime'),
    vTx: $('v-tx'),
    vRx: $('v-rx'),
    barTx: $('bar-tx'),
    barRx: $('bar-rx'),
    vCpu: $('v-cpu'),
    vRam: $('v-ram'),
    vTemp: $('v-temp'),
    vOs: $('v-os'),
    miniCpu: $('mini-cpu'),
    miniRam: $('mini-ram'),
    miniTemp: $('mini-temp'),
    sysBadge: $('sys-badge'),
    convScroll: $('convScroll'),
    msgTyping: $('msg-typing'),
    cmdInput: $('cmd-input'),
    btnSend: $('btn-send'),
    btnMic: $('btn-mic'),
    dockStatus: $('dock-status'),
    dockTitle: $('dock-title'),
    dockSub: $('dock-sub'),
    netPill: $('net-pill'),
    visionPill: $('vision-pill'),
    visionLabel: $('vision-label'),
    providerSelect: $('provider-select'),
  };

  // ═══ 3D Particle Sphere (Fibonacci) ═══════════════════════════
  const canvas = document.getElementById('orb');
  const ctx = canvas.getContext('2d');
  let DPR;
  const N = 420;
  const points = [];
  const golden = Math.PI * (3 - Math.sqrt(5));

  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2;
    const radius = Math.sqrt(1 - y * y);
    const theta = golden * i;
    points.push({
      x: Math.cos(theta) * radius,
      y: y,
      z: Math.sin(theta) * radius
    });
  }

  function resizeOrb() {
    const rect = canvas.parentElement.getBoundingClientRect();
    const size = Math.min(rect.width, rect.height) * 0.86;
    DPR = window.devicePixelRatio || 1;
    canvas.style.width = size + 'px';
    canvas.style.height = size + 'px';
    canvas.width = size * DPR;
    canvas.height = size * DPR;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }
  window.addEventListener('resize', resizeOrb);
  resizeOrb();

  let rot = 0;

  function drawOrb() {
    const size = canvas.width / DPR;
    ctx.clearRect(0, 0, size, size);
    const cx = size / 2, cy = size / 2;
    const R = size * 0.42;

    rot += 0.0022;

    ctx.save();
    ctx.strokeStyle = 'rgba(61,255,176,0.35)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(cx, cy, R * 0.62, R * 1.02, Math.PI * 0.18, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.ellipse(cx, cy, R * 0.62, R * 1.02, -Math.PI * 0.18, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    const proj = points.map(p => {
      const cosr = Math.cos(rot), sinr = Math.sin(rot);
      const x1 = p.x * cosr - p.z * sinr;
      const z1 = p.x * sinr + p.z * cosr;
      const scale = (z1 + 2) / 3;
      return { x: cx + x1 * R, y: cy + p.y * R, z: z1, scale };
    });

    proj.sort((a, b) => a.z - b.z);

    proj.forEach(p => {
      const alpha = 0.25 + p.scale * 0.55;
      const r = 0.9 + p.scale * 1.1;
      ctx.beginPath();
      ctx.fillStyle = `rgba(220,255,240,${alpha.toFixed(2)})`;
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fill();
    });

    requestAnimationFrame(drawOrb);
  }
  drawOrb();

  // ═══ State Machine ═══════════════════════════════════════════
  const STATE_LABELS = {
    idle: 'ULTRON ONLINE', planning: 'ANALYZING',
    executing: 'PROCESSING', verifying: 'VERIFYING',
    completed: 'COMPLETE', error: 'ERROR',
    offline: 'OFFLINE', waiting: 'PAUSED', listening: 'LISTENING',
    recovering: 'RECOVERING', replaning: 'REPLANNING'
  };

  const STATE_SUB = {
    idle: 'NEURAL NETWORK', planning: 'GOAL ANALYSIS',
    executing: 'NEURAL EXECUTION', verifying: 'VALIDATION',
    completed: 'ALL SYSTEMS GO', error: 'SYSTEM FAULT',
    offline: 'NO CONNECTION', waiting: 'ON STANDBY', listening: 'AWAITING INPUT',
    recovering: 'ANALYZING FAILURE', replaning: 'GENERATING ALTERNATIVE'
  };

  function setState(s) {
    appState = s;
    document.body.className = 'state-' + s;
    dom.dockTitle.textContent = STATE_LABELS[s] || s.toUpperCase();
    dom.dockSub.textContent = STATE_SUB[s] || '';
  }

  function setConnected(c) {
    connected = c;
    dom.netLabel.textContent = c ? 'CONNECTED' : 'OFFLINE';
    dom.netPill.textContent = c ? 'CONNECTED' : 'DISCONNECTED';
    dom.netPill.className = c ? 'pill green' : 'pill';
    if (!c) setState('offline');
  }

  // ═══ Execution Panel (Plan/Tool Visibility) ════════════════════
  let currentPlan = null;
  let planSteps = [];
  let planDisplayElement = null;

  function showPlanStep(stepNum, totalSteps, description, status) {
    hideTyping();
    const symbols = { pending: '○', running: '→', completed: '✓', failed: '✗', skipped: '⊘' };
    const sym = symbols[status] || '○';
    const div = document.createElement('div');
    div.className = 'msg plan-step msg-' + status;
    div.innerHTML = '<span class="plan-symbol">' + sym + '</span> Step ' + stepNum + '/' + totalSteps + ': ' + description;
    dom.convScroll.appendChild(div);
    dom.convScroll.scrollTop = dom.convScroll.scrollTop + 100;
  }

  function updatePlanDisplay() {
    if (!currentPlan || !planDisplayElement) return;

    const container = planDisplayElement.querySelector('.plan-steps');
    if (!container) return;

    container.innerHTML = '';

    planSteps.forEach((step, index) => {
      const item = document.createElement('div');
      item.className = 'plan-step-item ' + step.status;

      const symbols = { pending: '○', running: '→', completed: '✓', failed: '✗', skipped: '⊘' };
      const sym = symbols[step.status] || '○';

      item.innerHTML = '<span class="plan-step-symbol">' + sym + '</span><span class="plan-step-text">' + step.description + '</span>';
      container.appendChild(item);
    });
  }

  function createPlanDisplay(title) {
    if (planDisplayElement) {
      planDisplayElement.remove();
    }

    const div = document.createElement('div');
    div.className = 'plan-display';
    div.innerHTML = '<div class="plan-title">' + title + '</div><div class="plan-steps"></div>';
    dom.convScroll.appendChild(div);
    dom.convScroll.scrollTop = dom.convScroll.scrollTop + 100;
    planDisplayElement = div;
    return div;
  }

  function setStepStatus(stepIndex, status) {
    if (stepIndex >= 0 && stepIndex < planSteps.length) {
      planSteps[stepIndex].status = status;
      updatePlanDisplay();
    }
  }

  function showToolExecution(toolName, status, details) {
    hideTyping();
    const symbols = { started: '⚡', completed: '✓', failed: '✗' };
    const sym = symbols[status] || '⚡';
    const div = document.createElement('div');
    div.className = 'msg tool-exec msg-' + status;
    let html = '<span class="tool-symbol">' + sym + '</span><span class="tool-name">' + toolName + '</span>';
    if (details) {
      html += '<span class="tool-details">' + details + '</span>';
    }
    div.innerHTML = html;
    dom.convScroll.appendChild(div);
    dom.convScroll.scrollTop = dom.convScroll.scrollHeight;
  }

  // ═══ Conversation ═══════════════════════════════════════════
  function hideTyping() {
    dom.msgTyping.style.display = 'none';
  }

  function addMsg(type, text) {
    hideTyping();
    const div = document.createElement('div');
    div.className = 'msg ' + type;
    div.textContent = text;
    dom.convScroll.appendChild(div);
    dom.convScroll.scrollTop = dom.convScroll.scrollHeight;
  }

  function showTyping() {
    hideTyping();
    dom.msgTyping.style.display = 'flex';
    dom.convScroll.scrollTop = dom.convScroll.scrollHeight;
  }

  // ═══ SSE Events ══════════════════════════════════════════════
  JarvisAPI.on('connection', d => setConnected(d.status === 'connected'));

  JarvisAPI.on('orchestrator_state', d => {
    if (!d) return;
    setState(d.online ? (d.state || 'idle') : 'offline');
  });

  // The HTTP response and SSE event can arrive in either order.  Track the
  // exact submitted text so a local message is rendered only once.
  JarvisAPI.on('goal_created', d => {
    if (!d) return;
    const description = (d.description || '').trim();
    if (pendingGoalDescriptions.has(description)) {
      pendingGoalDescriptions.delete(description);
    } else {
      addMsg('user', description);
    }
    setState('planning');
    showTyping();
  });

  JarvisAPI.on('planning', () => setState('planning'));

  JarvisAPI.on('plan_created', d => {
    addMsg('assistant', 'Plan ready. Beginning execution...');
    if (d && d.metadata) {
      if (d.metadata.step_count) {
        addMsg('assistant', 'Total steps: ' + d.metadata.step_count);
      }
      // Create structured plan display
      planSteps = [];
      if (d.metadata.steps) {
        // Use provided step list
        d.metadata.steps.forEach(step => {
          planSteps.push({ description: step, status: 'pending' });
        });
      } else if (d.metadata.step_count) {
        // Create placeholder steps
        for (let i = 0; i < d.metadata.step_count; i++) {
          planSteps.push({ description: 'Step ' + (i + 1), status: 'pending' });
        }
      }
      createPlanDisplay('EXECUTION PLAN');
      updatePlanDisplay();
    }
  });

  let currentStepIndex = -1;

  JarvisAPI.on('task_started', d => {
    setState('executing');
    showTyping();
    // Mark next step as running
    currentStepIndex++;
    if (currentStepIndex >= 0 && currentStepIndex < planSteps.length) {
      planSteps[currentStepIndex].status = 'running';
      updatePlanDisplay();
    }
  });

  JarvisAPI.on('step_started', d => {
    setState('executing');
    showTyping();
    if (d) {
      showToolExecution(d.message || 'Executing step', 'started');
      // Try to match step to plan
      if (d.metadata && d.metadata.objective) {
        const desc = d.metadata.objective;
        const idx = planSteps.findIndex(s => s.description === desc && s.status === 'pending');
        if (idx >= 0) {
          currentStepIndex = idx;
          planSteps[idx].status = 'running';
        } else {
          // Add as current running step
          const runIdx = planSteps.findIndex(s => s.status === 'running');
          if (runIdx >= 0 && !planSteps[runIdx].description) {
            planSteps[runIdx].description = desc;
          }
        }
        updatePlanDisplay();
      }
    }
  });

  JarvisAPI.on('step_completed', d => {
    if (d) {
      const msg = d.message || (d.description ? 'Executed ' + d.description : 'Step completed');
      showToolExecution(msg, 'completed');
      // Mark current step as completed
      if (currentStepIndex >= 0 && currentStepIndex < planSteps.length) {
        planSteps[currentStepIndex].status = 'completed';
        updatePlanDisplay();
      }
    }
  });

  JarvisAPI.on('agent_selected', d => {
    if (d && d.metadata && d.metadata.agent_name) {
      addMsg('assistant', 'Agent selected: ' + d.metadata.agent_name);
    }
  });

  JarvisAPI.on('step_failed', d => {
    hideTyping();
    if (d) {
      showToolExecution(d.message || d.description || 'Step failed', 'failed', d.metadata && d.metadata.error ? d.metadata.error : '');
      addMsg('assistant', 'Step failed: ' + (d.description || d.error || ''));
      // Mark current step as failed
      if (currentStepIndex >= 0 && currentStepIndex < planSteps.length) {
        planSteps[currentStepIndex].status = 'failed';
        updatePlanDisplay();
      }
    }
  });

  JarvisAPI.on('verifying', () => setState('verifying'));

  JarvisAPI.on('verified', d => {
    if (d && d.metadata) {
      if (d.metadata.passed) {
        // Silent for passed verification
      } else {
        addMsg('assistant', 'Verification failed for step');
      }
    }
  });

  JarvisAPI.on('retrying', d => {
    setState('recovering');
    if (d && d.metadata) {
      addMsg('assistant', 'Retrying task (attempt ' + d.metadata.retry + ' of ' + d.metadata.max_retries + ')');
    }
  });

  JarvisAPI.on('recovering', d => {
    setState('recovering');
    if (d && d.message) {
      addMsg('assistant', d.message);
    }
  });

  JarvisAPI.on('replaning', d => {
    setState('replaning');
    if (d && d.message) {
      addMsg('assistant', d.message);
    }
  });

  // ═══ Permission Modal ══════════════════════════════════════════════
  let currentPermission = null;
  let permissionModalShown = false;

  function showPermissionModal(data) {
    if (permissionModalShown) return;  // Prevent duplicate modals
    permissionModalShown = true;

    currentPermission = data;
    hideTyping();

    const modal = document.createElement('div');
    modal.id = 'permission-modal';
    modal.className = 'permission-modal';

    const riskColor = data.risk === 'HIGH' ? 'var(--pink)' : data.risk === 'CRITICAL' ? 'var(--orange)' : 'var(--yellow)';

    let argsDisplay = '';
    if (data.arguments && Object.keys(data.arguments).length > 0) {
      argsDisplay = '<div class="perm-args">Arguments: ' + JSON.stringify(data.arguments, null, 0) + '</div>';
    }

    modal.innerHTML = `
      <div class="perm-content">
        <div class="perm-header">⚠️ PERMISSION REQUIRED</div>
        <div class="perm-body">
          <div class="perm-tool">Tool: <strong>${escapeHtml(data.tool)}</strong></div>
          <div class="perm-risk" style="color: ${riskColor}">Risk: ${data.risk}</div>
          <div class="perm-reason">${escapeHtml(data.reason)}</div>
          ${argsDisplay}
        </div>
        <div class="perm-actions">
          <button id="perm-deny" class="perm-btn perm-deny">DENY</button>
          <button id="perm-allow" class="perm-btn perm-allow">ALLOW</button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    // Disable buttons while processing
    const denyBtn = document.getElementById('perm-deny');
    const allowBtn = document.getElementById('perm-allow');

    let decided = false;
    function handleDecision(allowed) {
      if (decided) return;
      decided = true;
      denyBtn.disabled = allowBtn.disabled = true;
      denyBtn.classList.add('processing');
      allowBtn.classList.add('processing');

      JarvisAPI[allowed ? 'allowPermission' : 'denyPermission'](data.permission_id)
        .then(result => {
          if (!result || !result.accepted) {
            addMsg('assistant', 'Permission decision could not be submitted. Please try again.');
          }
        })
        .catch(err => {
          addMsg('assistant', 'Error submitting permission decision: ' + err.message);
        })
        .finally(() => {
          closePermissionModal();
        });
    }

    denyBtn.addEventListener('click', () => handleDecision(false));
    allowBtn.addEventListener('click', () => handleDecision(true));

    // Close on escape key
    const escHandler = (e) => {
      if (e.key === 'Escape') {
        handleDecision(false);
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);
  }

  function closePermissionModal() {
    const modal = document.getElementById('permission-modal');
    if (modal) {
      modal.remove();
    }
    permissionModalShown = false;
    currentPermission = null;
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  JarvisAPI.on('permission_required', d => {
    if (!d) return;
    showPermissionModal(d);
  });

  JarvisAPI.on('permission_decided', d => {
    if (!d) return;
    if (currentPermission && currentPermission.permission_id === d.permission_id) {
      closePermissionModal();
    }
  });

  JarvisAPI.on('connection', d => {
    if (d && d.status === 'disconnected') {
      // Connection lost - close any open permission modal
      if (permissionModalShown) {
        const modal = document.getElementById('permission-modal');
        if (modal) {
          const content = modal.querySelector('.perm-content');
          if (content) {
            content.innerHTML = `
              <div class="perm-header">⚠️ CONNECTION LOST</div>
              <div class="perm-body">
                <div class="perm-reason">Permission state uncertain. Connection to server was lost.</div>
                <div class="perm-reason" style="color: var(--pink);">Do not retry until connection is restored.</div>
              </div>
              <div class="perm-actions">
                <button id="perm-close" class="perm-btn perm-deny" disabled>CLOSED</button>
              </div>
            `;
            const closeBtn = document.getElementById('perm-close');
            closeBtn.addEventListener('click', () => closePermissionModal());
          }
        }
      }
    }
    setConnected(d.status === 'connected');
  });

  JarvisAPI.on('completed', d => {
    setState('completed');
    hideTyping();
    const text = d && d.response ? d.response : 'Task completed successfully.';
    addMsg('assistant', text);
    // Mark any remaining running step as completed
    if (currentStepIndex >= 0 && currentStepIndex < planSteps.length) {
      planSteps[currentStepIndex].status = 'completed';
      updatePlanDisplay();
    }
    // Clean up plan state after a delay
    setTimeout(() => {
      planSteps = [];
      currentStepIndex = -1;
      if (planDisplayElement) {
        planDisplayElement.remove();
        planDisplayElement = null;
      }
    }, 3000);
  });

  JarvisAPI.on('failed', d => {
    setState('error');
    hideTyping();
    const text = d && (d.message || d.error) ? (d.message || d.error) : 'Task failed.';
    addMsg('assistant', text);
    // Mark any remaining running step as failed
    if (currentStepIndex >= 0 && currentStepIndex < planSteps.length) {
      planSteps[currentStepIndex].status = 'failed';
      updatePlanDisplay();
    }
    // Clean up plan state after a delay
    setTimeout(() => {
      planSteps = [];
      currentStepIndex = -1;
      if (planDisplayElement) {
        planDisplayElement.remove();
        planDisplayElement = null;
      }
    }, 3000);
  });

  JarvisAPI.on('error', d => {
    setState('error');
    hideTyping();
    addMsg('assistant', 'Error: ' + (d.error || d.message || 'Unknown error'));
  });

  JarvisAPI.on('execution_paused', () => {
    setState('waiting');
    showTyping();
  });

  JarvisAPI.on('execution_resumed', () => {
    setState('executing');
    showTyping();
  });

  JarvisAPI.on('execution_stopped', () => {
    setState('idle');
    hideTyping();
    addMsg('assistant', 'Execution stopped.');
  });

  // ═══ Polling ═════════════════════════════════════════════════
  JarvisAPI.on('system_metrics', d => {
    if (!d) return;
    if (d.cpu_percent != null) {
      const v = Math.round(d.cpu_percent);
      dom.vCpu.innerHTML = v + '<small>%</small>';
      dom.miniCpu.style.width = v + '%';
    }
    if (d.ram_percent != null) {
      const v = Math.round(d.ram_percent);
      dom.vRam.innerHTML = v + '<small>%</small>';
      dom.miniRam.style.width = v + '%';
    }
    if (d.temperature != null) {
      const v = Math.round(d.temperature);
      dom.vTemp.innerHTML = v + '<small>°C</small>';
      dom.miniTemp.style.width = Math.min(v, 100) + '%';
    }
    if (d.uptime_seconds != null) {
      const s = Math.floor(d.uptime_seconds);
      const h = (s / 3600).toFixed(1);
      dom.vUptime.innerHTML = h + '<small>h</small>';
    }
    if (d.os) dom.vOs.textContent = d.os;
  });

  JarvisAPI.on('network_status', d => {
    if (!d) return;
    if (d.latency_ms != null) {
      dom.vLatency.innerHTML = d.latency_ms + '<small>ms</small>';
    }
    if (d.tx_percent != null) {
      dom.vTx.textContent = Math.round(d.tx_percent);
      dom.barTx.style.width = d.tx_percent + '%';
    }
    if (d.rx_percent != null) {
      dom.vRx.textContent = Math.round(d.rx_percent);
      dom.barRx.style.width = d.rx_percent + '%';
    }
  });

  JarvisAPI.on('tools_list', d => {
    if (d && d.tools) {
      // Could render tools list here if needed
    }
  });

  JarvisAPI.on('agent_status', d => {
    if (Array.isArray(d)) {
      // Could render agent list here
    }
  });

  // ═══ Latency ═════════════════════════════════════════════════
  setInterval(async () => {
    const t0 = Date.now();
    await JarvisAPI.get('/api/status');
    const ms = Date.now() - t0;
    dom.vLatency.innerHTML = ms + '<small>ms</small>';
  }, 5000);

  // ═══ Command Submit ══════════════════════════════════════════
  const pendingGoalDescriptions = new Set();

  async function submitCommand(text) {
    if (!text || !text.trim()) return;
    const message = text.trim();
    pendingGoalDescriptions.add(message);
    addMsg('user', message);
    showTyping();
    const result = await JarvisAPI.submitGoal(message);
    if (result && result.id) {
      lastGoalId = result.id;  // Track so we don't double-add on SSE echo
    } else {
      hideTyping();
      setState('error');
      pendingGoalDescriptions.delete(message);
      addMsg('assistant', 'I could not reach the JARVIS backend. Make sure it is running, then refresh this page.');
    }
    dom.cmdInput.value = '';
  }

  dom.btnSend.addEventListener('click', () => submitCommand(dom.cmdInput.value));

  dom.cmdInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitCommand(dom.cmdInput.value);
    }
  });

  // ═══ Voice — Browser Web Speech API ══════════════════════════
  function initVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return null;
    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = 'en-US';
    return rec;
  }

  dom.btnMic.addEventListener('click', async () => {
    const recognition = initVoice();
    if (!recognition) {
      addMsg('assistant', 'Voice recognition not supported in this browser.');
      return;
    }

    document.body.classList.add('listening');
    dom.dockTitle.textContent = 'LISTENING';
    dom.dockSub.textContent = 'AWAITING INPUT';
    dom.btnMic.style.boxShadow = '0 0 0 0 rgba(61,255,176,0.4)';

    let finalTranscript = '';

    recognition.onresult = event => {
      let interimTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }
      dom.cmdInput.value = finalTranscript || interimTranscript;
    };

    recognition.onerror = event => {
      console.warn('Speech recognition error:', event.error);
      if (event.error === 'no-speech') {
        addMsg('assistant', 'No speech detected. Please try again.');
      } else if (event.error === 'not-allowed') {
        addMsg('assistant', 'Microphone access denied. Please allow microphone permissions.');
      } else {
        addMsg('assistant', 'Voice error: ' + event.error);
      }
    };

    recognition.onend = () => {
      document.body.classList.remove('listening');
      dom.btnMic.style.boxShadow = '';
      if (finalTranscript) {
        submitCommand(finalTranscript);
      } else {
        setState('idle');
      }
    };

    try {
      recognition.start();
    } catch (e) {
      document.body.classList.remove('listening');
      addMsg('assistant', 'Failed to start voice recognition.');
      setState('idle');
    }
  });

  // ═══ Connected workspace: local database and installed tools ═══
  const workspace = $('workspace');
  const workspaceTitle = $('workspace-title');
  const workspaceSubtitle = $('workspace-subtitle');
  const workspaceForm = $('workspace-form');
  const workspaceList = $('workspace-list');
  let activeView = 'command';

  const viewInfo = {
    notes: ['NOTES', 'Persistent notes from the JARVIS local database'],
    calendar: ['CALENDAR', 'Persistent calendar events from the JARVIS local database'],
    reminders: ['REMINDERS', 'Persistent reminders and their schedule'],
    tools: ['TOOLS', 'Capabilities registered with the running JARVIS backend'],
  };

  const item = (title, body, meta, id, removeLabel) => `
    <article class="workspace-item"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(body || '')}</p>
    <small>${escapeHtml(meta || '')}</small>${id ? `<button data-remove="${escapeHtml(id)}">${removeLabel}</button>` : ''}</article>`;

  function showWorkspaceEmpty(message) {
    workspaceList.innerHTML = `<div class="workspace-empty">${escapeHtml(message)}</div>`;
  }

  async function renderWorkspace(view) {
    activeView = view;
    const info = viewInfo[view];
    if (!info) return;
    workspace.hidden = false;
    workspaceTitle.textContent = info[0];
    workspaceSubtitle.textContent = info[1];
    workspaceForm.innerHTML = '';
    showWorkspaceEmpty('Loading…');

    if (view === 'notes') {
      workspaceForm.innerHTML = '<input class="wide" id="note-title" placeholder="Note title" required><textarea id="note-content" placeholder="Write a note…"></textarea><input class="wide" id="note-tags" placeholder="Tags, separated by commas"><button id="save-note">SAVE NOTE</button>';
      $('save-note').onclick = async () => {
        const title = $('note-title').value.trim();
        if (!title) return;
        await JarvisAPI.createNote({ title, content: $('note-content').value, tags: $('note-tags').value.split(',').map(x => x.trim()).filter(Boolean) });
        renderWorkspace('notes');
      };
      const data = await JarvisAPI.listNotes();
      const notes = data && data.notes || [];
      workspaceList.innerHTML = notes.length ? notes.map(n => item(n.title, n.content, (n.tags || []).join(' · ') || n.updated_at, n.id, 'DELETE')).join('') : '';
      if (!notes.length) showWorkspaceEmpty('No notes yet. Create one above.');
      workspaceList.querySelectorAll('[data-remove]').forEach(button => button.onclick = async () => { await JarvisAPI.deleteNote(button.dataset.remove); renderWorkspace('notes'); });
    }

    if (view === 'calendar') {
      workspaceForm.innerHTML = '<input class="half" id="event-title" placeholder="Event title" required><input class="half" id="event-start" type="datetime-local" required><input class="half" id="event-end" type="datetime-local"><button id="save-event">ADD EVENT</button>';
      $('save-event').onclick = async () => {
        const title = $('event-title').value.trim(), start = $('event-start').value;
        if (!title || !start) return;
        await JarvisAPI.createCalendarEvent({ title, start_time: new Date(start).toISOString(), end_time: $('event-end').value ? new Date($('event-end').value).toISOString() : null, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
        renderWorkspace('calendar');
      };
      const data = await JarvisAPI.listCalendarEvents();
      const events = data && data.events || [];
      workspaceList.innerHTML = events.length ? events.map(e => item(e.title, e.description, new Date(e.start_time).toLocaleString(), e.id, 'DELETE')).join('') : '';
      if (!events.length) showWorkspaceEmpty('No calendar events yet. Add one above.');
      workspaceList.querySelectorAll('[data-remove]').forEach(button => button.onclick = async () => { await JarvisAPI.deleteCalendarEvent(button.dataset.remove); renderWorkspace('calendar'); });
    }

    if (view === 'reminders') {
      workspaceForm.innerHTML = '<input class="wide" id="reminder-message" placeholder="What should JARVIS remind you about?" required><input class="half" id="reminder-at" type="datetime-local" required><button id="save-reminder">SET REMINDER</button>';
      $('save-reminder').onclick = async () => {
        const message = $('reminder-message').value.trim(), when = $('reminder-at').value;
        if (!message || !when) return;
        await JarvisAPI.createReminder({ message, trigger_time: new Date(when).toISOString() });
        renderWorkspace('reminders');
      };
      const data = await JarvisAPI.listReminders();
      const reminders = data && data.reminders || [];
      workspaceList.innerHTML = reminders.length ? reminders.map(r => item(r.message, r.status.toUpperCase(), new Date(r.trigger_time).toLocaleString(), r.id, 'DELETE')).join('') : '';
      if (!reminders.length) showWorkspaceEmpty('No reminders are scheduled.');
      workspaceList.querySelectorAll('[data-remove]').forEach(button => button.onclick = async () => { await JarvisAPI.cancelReminder(button.dataset.remove); renderWorkspace('reminders'); });
    }

    if (view === 'tools') {
      const data = await JarvisAPI.get('/api/tools');
      const tools = data && data.tools || [];
      workspaceList.innerHTML = tools.length ? tools.map(t => item(t.name, t.description, 'Available to JARVIS', '', '')).join('') : '';
      if (!tools.length) showWorkspaceEmpty('The backend has not registered any tools. Start JARVIS with its web interface enabled.');
    }
  }

  $('workspace-close').onclick = () => {
    workspace.hidden = true;
    activeView = 'command';
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.view === 'command'));
  };

  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      if (tab.dataset.view === 'command') {
        workspace.hidden = true;
        activeView = 'command';
      } else {
        renderWorkspace(tab.dataset.view);
      }
    });
  });

  // ═══ Boot ════════════════════════════════════════════════════
  JarvisAPI.connectSSE();
  JarvisAPI.startPolling();
  setConnected(false);
  setState('idle');
  addMsg('assistant', 'JARVIS online. Systems operational. What would you like me to do, Boss?');

  // Load current provider from server
  async function loadProvider() {
    try {
      const status = await JarvisAPI.get('/api/status');
      if (status && status.provider && dom.providerSelect) {
        dom.providerSelect.value = status.provider;
      }
    } catch (e) {
      console.warn('Could not load provider:', e);
    }
  }
  loadProvider();

  // Provider change handler
  if (dom.providerSelect) {
    dom.providerSelect.addEventListener('change', async (e) => {
      const newProvider = e.target.value;
      addMsg('assistant', `Provider switched to ${newProvider}. Restart JARVIS to apply: ultron --provider ${newProvider}`);
    });
  }

})();
