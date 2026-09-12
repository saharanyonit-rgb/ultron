/* ═══════════════════════════════════════════════════════════════
   JARVIS API Layer — High-Performance Backend Connection
   ═══════════════════════════════════════════════════════════════ */

const API = {
  _base: '',
  _sseSource: null,
  _sseListeners: {},
  _pollTimers: {},
  _connected: false,
  _lastMetrics: null,
  _lastNetwork: null,
  _lastOrchestrator: null,

  // ── Public HTTP Helpers ─────────────────────────────────────────
  async get(path) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      const r = await fetch(this._base + path, {
        signal: controller.signal,
        headers: { 'Cache-Control': 'no-cache' }
      });
      clearTimeout(timeout);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      if (e.name !== 'AbortError') {
        console.warn(`API GET ${path} failed:`, e.message);
      }
      return null;
    }
  },

  async post(path, body, timeoutMs) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), timeoutMs || 10000);
      const r = await fetch(this._base + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const text = await r.text();
      return text ? JSON.parse(text) : null;
    } catch (e) {
      if (e.name !== 'AbortError') {
        console.warn(`API POST ${path} failed:`, e.message);
      }
      return null;
    }
  },

  async put(path, body) {
    try {
      const r = await fetch(this._base + path, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const text = await r.text();
      return text ? JSON.parse(text) : null;
    } catch (e) {
      console.warn(`API PUT ${path} failed:`, e);
      return null;
    }
  },

  // ── SSE Connection ──────────────────────────────────────────
  connectSSE() {
    if (this._sseSource) {
      this._sseSource.close();
    }

    this._sseSource = new EventSource(this._base + '/api/events');

    this._sseSource.onopen = () => {
      this._connected = true;
      this._emit('connection', { status: 'connected' });
    };

    this._sseSource.onerror = () => {
      this._connected = false;
      this._emit('connection', { status: 'disconnected' });
    };

    this._sseSource.onmessage = (e) => {
      this._emit('message', { data: e.data });
    };

    const eventTypes = [
      'goal_created', 'execution_paused', 'execution_resumed',
      'execution_stopped', 'task_started', 'planning', 'plan_created',
      'agent_selected', 'step_started', 'step_completed', 'step_failed',
      'verifying', 'verified', 'completed', 'failed', 'error',
      'permission_required', 'permission_decided',
      'voice_state',
    ];

    eventTypes.forEach(type => {
      this._sseSource.addEventListener(type, (e) => {
        try {
          const data = JSON.parse(e.data);
          this._emit(type, data);
        } catch {
          this._emit(type, { raw: e.data });
        }
      });
    });
  },

  disconnectSSE() {
    if (this._sseSource) {
      this._sseSource.close();
      this._sseSource = null;
    }
    this._connected = false;
  },

  // ── Event Emitter ───────────────────────────────────────────
  on(event, callback) {
    if (!this._sseListeners[event]) {
      this._sseListeners[event] = [];
    }
    this._sseListeners[event].push(callback);
  },

  off(event, callback) {
    if (this._sseListeners[event]) {
      this._sseListeners[event] = this._sseListeners[event].filter(cb => cb !== callback);
    }
  },

  _emit(event, data) {
    const listeners = this._sseListeners[event] || [];
    for (let i = 0; i < listeners.length; i++) {
      try { listeners[i](data); } catch (e) { console.error('Event listener error:', e); }
    }
  },

  // ── Smart Polling with Change Detection ─────────────────────
  startPolling() {
    // Fast: orchestrator state (core UI updates)
    this._startPoll('orchestrator', () => this._pollOrchestrator(), 2000);
    // Medium: system metrics, computer state
    this._startPoll('metrics', () => this._pollSystemMetrics(), 3000);
    this._startPoll('computer', () => this._pollComputerState(), 4000);
    // Slow: agents, network, security, memory, system info, tools
    this._startPoll('agents', () => this._pollAgentStatus(), 5000);
    this._startPoll('network', () => this._pollNetworkStatus(), 8000);
    this._startPoll('security', () => this._pollSecurityStatus(), 10000);
    this._startPoll('memory', () => this._pollMemoryStatus(), 10000);
    this._startPoll('sysinfo', () => this._pollSystemInfo(), 30000);
    this._startPoll('tools', () => this._pollTools(), 15000);
  },

  _startPoll(name, fn, interval) {
    fn(); // Initial call
    this._pollTimers[name] = setInterval(fn, interval);
  },

  stopPolling() {
    Object.values(this._pollTimers).forEach(t => clearInterval(t));
    this._pollTimers = {};
  },

  async _pollSystemMetrics() {
    const data = await this.get('/api/system/metrics');
    if (data && JSON.stringify(data) !== JSON.stringify(this._lastMetrics)) {
      this._lastMetrics = data;
      this._emit('system_metrics', data);
    }
  },

  async _pollNetworkStatus() {
    const data = await this.get('/api/system/network');
    if (data && JSON.stringify(data) !== JSON.stringify(this._lastNetwork)) {
      this._lastNetwork = data;
      this._emit('network_status', data);
    }
  },

  async _pollOrchestrator() {
    const data = await this.get('/api/orchestrator');
    if (data && JSON.stringify(data) !== JSON.stringify(this._lastOrchestrator)) {
      this._lastOrchestrator = data;
      this._emit('orchestrator_state', data);
    }
  },

  async _pollAgentStatus() {
    const data = await this.get('/api/agents');
    if (data) this._emit('agent_status', data);
  },

  async _pollMemoryStatus() {
    const data = await this.get('/api/memory');
    if (data) this._emit('memory_status', data);
  },

  async _pollSecurityStatus() {
    const data = await this.get('/api/security');
    if (data) this._emit('security_status', data);
  },

  async _pollComputerState() {
    const data = await this.get('/api/computer');
    if (data) this._emit('computer_state', data);
  },

  async _pollSystemInfo() {
    const data = await this.get('/api/system/info');
    if (data) this._emit('system_info', data);
  },

  async _pollTools() {
    const data = await this.get('/api/tools');
    if (data) this._emit('tools_list', data);
  },

  // ── Actions ─────────────────────────────────────────────────
  async submitGoal(description) {
    return await this.post('/api/goals', { description, mode: 'chat' });
  },

  async pauseExecution() {
    return await this.post('/api/control/pause', {});
  },

  async resumeExecution() {
    return await this.post('/api/control/resume', {});
  },

  async stopExecution() {
    return await this.post('/api/control/stop', {});
  },

  async executeCommand(command, timeout) {
    return await this.post('/api/execute', { command, timeout });
  },

  // ── Permissions ───────────────────────────────────────────────
  async listPermissions() {
    return await this.get('/api/permissions');
  },

  async getPermission(permissionId) {
    return await this.get('/api/permissions/' + permissionId);
  },

  async allowPermission(permissionId) {
    return await this.post('/api/permissions/' + permissionId + '/allow', {});
  },

  async denyPermission(permissionId) {
    return await this.post('/api/permissions/' + permissionId + '/deny', {});
  },

  async speak(text) {
    return await this.post('/api/voice/speak', { text });
  },

  async listen(timeout) {
    return await this.post('/api/voice/listen', { timeout }, 30000);
  },

  async getVoiceState() {
    return await this.get('/api/voice');
  },

  // ── Calendar ───────────────────────────────────────────────
  async listCalendarEvents(fromTime, toTime) {
    const params = new URLSearchParams();
    if (fromTime) params.set('from_time', fromTime);
    if (toTime) params.set('to_time', toTime);
    const q = params.toString();
    return await this.get('/api/calendar/events' + (q ? '?' + q : ''));
  },

  async createCalendarEvent(data) {
    return await this.post('/api/calendar/events', data);
  },

  async deleteCalendarEvent(eventId) {
    try {
      const r = await fetch(this._base + '/api/calendar/events/' + eventId, { method: 'DELETE' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const text = await r.text();
      return text ? JSON.parse(text) : null;
    } catch (e) {
      console.warn('Delete calendar event failed:', e);
      return null;
    }
  },

  async updateCalendarEvent(eventId, data) {
    return await this.put('/api/calendar/events/' + eventId, data);
  },

  // ── Notes ──────────────────────────────────────────────────
  async listNotes(tag) {
    const q = tag ? '?tag=' + encodeURIComponent(tag) : '';
    return await this.get('/api/notes' + q);
  },

  async createNote(data) {
    return await this.post('/api/notes', data);
  },

  async updateNote(noteId, data) {
    return await this.put('/api/notes/' + noteId, data);
  },

  async deleteNote(noteId) {
    try {
      const r = await fetch(this._base + '/api/notes/' + noteId, { method: 'DELETE' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const text = await r.text();
      return text ? JSON.parse(text) : null;
    } catch (e) {
      console.warn('Delete note failed:', e);
      return null;
    }
  },

  // ── Reminders ───────────────────────────────────────────────
  async listReminders(status) {
    const q = status ? '?status=' + encodeURIComponent(status) : '';
    return await this.get('/api/reminders' + q);
  },

  async createReminder(data) {
    return await this.post('/api/reminders', data);
  },

  async cancelReminder(reminderId) {
    try {
      const r = await fetch(this._base + '/api/reminders/' + reminderId, { method: 'DELETE' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const text = await r.text();
      return text ? JSON.parse(text) : null;
    } catch (e) {
      console.warn('Cancel reminder failed:', e);
      return null;
    }
  },

  // ── Vision ────────────────────────────────────────────────
  async analyzeVision(prompt, path) {
    return await this.post('/api/vision/analyze', { prompt, path });
  },
};

window.JarvisAPI = API;
