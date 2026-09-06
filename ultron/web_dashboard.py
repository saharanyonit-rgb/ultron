"""Minimal HTML Dashboard for JARVIS.

Single-page dashboard with SSE status streaming.
"""

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JARVIS Control Panel</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; background: #0d1117; color: #c9d1d9; padding: 20px; }
  h1 { color: #58a6ff; margin-bottom: 20px; font-size: 1.5em; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; margin-bottom: 20px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .card h2 { color: #58a6ff; font-size: 0.9em; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }
  .status { font-size: 1.4em; font-weight: bold; }
  .status.running { color: #3fb950; }
  .status.stopped { color: #f85149; }
  .status.paused { color: #d29922; }
  .metric { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #21262d; }
  .metric:last-child { border-bottom: none; }
  .metric-label { color: #8b949e; }
  .metric-value { color: #c9d1d9; }
  .goal-form { display: flex; gap: 8px; margin-top: 12px; }
  .goal-form input { flex: 1; padding: 8px 12px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-family: inherit; }
  .goal-form button { padding: 8px 16px; background: #238636; border: none; border-radius: 6px; color: #fff; cursor: pointer; font-family: inherit; }
  .goal-form button:hover { background: #2ea043; }
  .btn-pause { background: #d29922; }
  .btn-pause:hover { background: #e3b341; }
  .btn-resume { background: #238636; }
  .btn-resume:hover { background: #2ea043; }
  .btn-stop { background: #da3633; }
  .btn-stop:hover { background: #f85149; }
  .controls { display: flex; gap: 8px; margin-top: 12px; }
  .controls button { padding: 6px 14px; border: none; border-radius: 6px; color: #fff; cursor: pointer; font-family: inherit; font-size: 0.85em; }
  .list { max-height: 200px; overflow-y: auto; }
  .list-item { padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 0.9em; }
  .list-item:last-child { border-bottom: none; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; font-weight: bold; }
  .badge-created { background: #1f6feb33; color: #58a6ff; }
  .badge-executing { background: #d2992233; color: #d29922; }
  .badge-completed { background: #23863633; color: #3fb950; }
  .badge-failed { background: #da363333; color: #f85149; }
  #events { max-height: 200px; overflow-y: auto; font-size: 0.85em; }
  .event { padding: 4px 0; border-bottom: 1px solid #21262d; color: #8b949e; }
  .event-type { color: #58a6ff; font-weight: bold; }
</style>
</head>
<body>
<h1>JARVIS Control Panel</h1>
<div class="grid">
  <div class="card">
    <h2>System Status</h2>
    <div id="status" class="status running">loading...</div>
    <div style="margin-top:12px">
      <div class="metric"><span class="metric-label">Goals</span><span class="metric-value" id="goals-count">0</span></div>
      <div class="metric"><span class="metric-label">Tasks</span><span class="metric-value" id="tasks-count">0</span></div>
      <div class="metric"><span class="metric-label">Uptime</span><span class="metric-value" id="uptime">0s</span></div>
    </div>
  </div>
  <div class="card">
    <h2>Submit Goal</h2>
    <div class="goal-form">
      <input type="text" id="goal-input" placeholder="Describe your goal...">
      <button onclick="submitGoal()">Submit</button>
    </div>
    <div class="controls" style="margin-top:12px">
      <button class="btn-pause" onclick="controlAction('pause')">Pause</button>
      <button class="btn-resume" onclick="controlAction('resume')">Resume</button>
      <button class="btn-stop" onclick="controlAction('stop')">Emergency Stop</button>
    </div>
  </div>
  <div class="card">
    <h2>Goals</h2>
    <div id="goals-list" class="list"><div class="list-item" style="color:#8b949e">No goals yet</div></div>
  </div>
  <div class="card">
    <h2>Tools</h2>
    <div id="tools-list" class="list"><div class="list-item" style="color:#8b949e">Loading...</div></div>
  </div>
  <div class="card" style="grid-column: 1 / -1">
    <h2>Live Events</h2>
    <div id="events"></div>
  </div>
</div>
<script>
const API = '';
function $(id) { return document.getElementById(id); }

async function fetchStatus() {
  try {
    const r = await fetch(API + '/api/status');
    const d = await r.json();
    $('status').textContent = d.status;
    $('status').className = 'status ' + d.status;
    $('goals-count').textContent = d.goals_count;
    $('tasks-count').textContent = d.tasks_count;
    $('uptime').textContent = Math.floor(d.uptime_seconds) + 's';
  } catch(e) {}
}

async function fetchGoals() {
  try {
    const r = await fetch(API + '/api/goals');
    const d = await r.json();
    const el = $('goals-list');
    if (!d.goals.length) { el.innerHTML = '<div class="list-item" style="color:#8b949e">No goals yet</div>'; return; }
    el.innerHTML = d.goals.map(g =>
      '<div class="list-item">' + g.id + ' <span class="badge badge-' + g.status + '">' + g.status + '</span> ' + g.description + '</div>'
    ).join('');
  } catch(e) {}
}

async function fetchTools() {
  try {
    const r = await fetch(API + '/api/tools');
    const d = await r.json();
    const el = $('tools-list');
    if (!d.tools.length) { el.innerHTML = '<div class="list-item" style="color:#8b949e">No tools registered</div>'; return; }
    el.innerHTML = d.tools.map(t =>
      '<div class="list-item"><strong>' + t.name + '</strong> ' + (t.description || '') + '</div>'
    ).join('');
  } catch(e) {}
}

async function submitGoal() {
  const input = $('goal-input');
  const desc = input.value.trim();
  if (!desc) return;
  try {
    await fetch(API + '/api/goals', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({description: desc})
    });
    input.value = '';
    fetchGoals();
  } catch(e) {}
}

async function controlAction(action) {
  try {
    await fetch(API + '/api/control/' + action, {method: 'POST'});
    fetchStatus();
  } catch(e) {}
}

function addEvent(type, data) {
  const el = $('events');
  const div = document.createElement('div');
  div.className = 'event';
  div.innerHTML = '<span class="event-type">' + type + '</span> ' + JSON.stringify(data).slice(0, 120);
  el.prepend(div);
  if (el.children.length > 50) el.lastChild.remove();
}

function startSSE() {
  const source = new EventSource(API + '/api/events');
  source.onmessage = function(e) { addEvent('message', e.data); };
  source.onerror = function() { addEvent('error', 'SSE connection lost, reconnecting...'); };
  ['goal_created', 'execution_paused', 'execution_resumed', 'execution_stopped'].forEach(type => {
    source.addEventListener(type, function(e) { addEvent(type, e.data); });
  });
}

fetchStatus(); fetchGoals(); fetchTools();
setInterval(fetchStatus, 5000);
setInterval(fetchGoals, 10000);
startSSE();

$('goal-input').addEventListener('keydown', function(e) { if (e.key === 'Enter') submitGoal(); });
</script>
</body>
</html>
"""


__all__ = ["DASHBOARD_HTML"]
