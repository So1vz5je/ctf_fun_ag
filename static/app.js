/* ── CTF Agent Frontend ────────────────────────────────────────────── */

// ── Theme ────────────────────────────────────────────────────────────

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('ctf-agent-theme', theme);
  document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.themeBtn === theme);
  });
}

(function initTheme() {
  const saved = localStorage.getItem('ctf-agent-theme') || 'dark';
  setTheme(saved);
})();

// ── Navigation ───────────────────────────────────────────────────────

let currentPage = 'dashboard';

function navigateTo(page) {
  currentPage = page;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const pageEl = document.getElementById('page-' + page);
  const navEl = document.querySelector(`.nav-item[data-page="${page}"]`);
  if (pageEl) pageEl.classList.add('active');
  if (navEl) navEl.classList.add('active');

  if (page === 'dashboard') refreshDashboard();
  if (page === 'settings') loadSettings();
  if (page === 'games') loadGames();
  if (page === 'agent') { refreshSelects(); loadTasksList(); }
  if (page === 'challenges') refreshChallengeGameSelect();
}

// ── API helpers ──────────────────────────────────────────────────────

async function api(url, opts = {}) {
  try {
    const resp = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`${resp.status}: ${text.slice(0, 200)}`);
    }
    return await resp.json();
  } catch (e) {
    showToast(e.message, 'error');
    throw e;
  }
}

function escHtml(s) {
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Toast ────────────────────────────────────────────────────────────

function showToast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  const colors = { info: 'var(--info)', success: 'var(--success)', error: 'var(--danger)', warning: 'var(--warning)' };
  el.style.background = colors[type] || colors.info;
  document.body.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3000);
}

// ── Dashboard ────────────────────────────────────────────────────────

async function refreshDashboard() {
  try {
    const tasks = await api('/api/tasks');
    const taskCount = Object.keys(tasks).length;
    const running = Object.values(tasks).filter(t => t.status === 'running').length;
    document.getElementById('stat-tasks').textContent = taskCount;
    document.getElementById('stat-running').textContent = running;

    const games = await api('/api/games').catch(() => []);
    document.getElementById('stat-games').textContent = Array.isArray(games) ? games.length : '-';
    document.getElementById('stat-status').textContent = 'Online';
  } catch {
    document.getElementById('stat-status').textContent = 'Offline';
  }
}

// ── Settings ─────────────────────────────────────────────────────────

async function loadSettings() {
  try {
    const s = await api('/api/settings');
    document.getElementById('set-gzctf-url').value = s.gzctf_url || '';
    document.getElementById('set-gzctf-username').value = s.gzctf_username || '';
    document.getElementById('set-gzctf-password').value = s.gzctf_password || '';
    document.getElementById('set-gzctf-token').value = s.gzctf_token || '';
    document.getElementById('set-gzctf-team-id').value = s.gzctf_team_id || '';
    document.getElementById('set-llm-provider').value = s.llm_provider || 'openai';
    document.getElementById('set-llm-api-key').value = s.llm_api_key || '';
    document.getElementById('set-llm-base-url').value = s.llm_base_url || '';
    document.getElementById('set-llm-model').value = s.llm_model || 'gpt-4o';
    document.getElementById('set-llm-temperature').value = s.llm_temperature ?? 0.1;
    document.getElementById('set-llm-max-tokens').value = s.llm_max_tokens || 4096;
    document.getElementById('set-agent-max-retries').value = s.agent_max_retries || 3;
    document.getElementById('set-agent-auto-submit').checked = s.agent_auto_submit !== false;
    document.getElementById('set-agent-auto-container').checked = s.agent_auto_start_container !== false;
    document.getElementById('set-agent-skip-solved').checked = s.agent_skip_solved !== false;
  } catch { /* toast already shown */ }
}

async function saveSettings() {
  const data = {
    gzctf_url: document.getElementById('set-gzctf-url').value.trim(),
    gzctf_username: document.getElementById('set-gzctf-username').value.trim(),
    gzctf_password: document.getElementById('set-gzctf-password').value,
    gzctf_token: document.getElementById('set-gzctf-token').value.trim(),
    gzctf_team_id: parseInt(document.getElementById('set-gzctf-team-id').value) || null,
    llm_provider: document.getElementById('set-llm-provider').value,
    llm_api_key: document.getElementById('set-llm-api-key').value,
    llm_base_url: document.getElementById('set-llm-base-url').value.trim() || null,
    llm_model: document.getElementById('set-llm-model').value || 'gpt-4o',
    llm_temperature: parseFloat(document.getElementById('set-llm-temperature').value) || 0.1,
    llm_max_tokens: parseInt(document.getElementById('set-llm-max-tokens').value) || 4096,
    agent_max_retries: parseInt(document.getElementById('set-agent-max-retries').value) || 3,
    agent_auto_submit: document.getElementById('set-agent-auto-submit').checked,
    agent_auto_start_container: document.getElementById('set-agent-auto-container').checked,
    agent_skip_solved: document.getElementById('set-agent-skip-solved').checked,
  };
  await api('/api/settings', { method: 'POST', body: JSON.stringify(data) });
  showToast('Settings saved', 'success');
}

async function testConnection() {
  showToast('Testing connection...', 'info');
  try {
    const profile = await api('/api/login', { method: 'POST' });
    const name = profile.userName || profile.bio || 'OK';
    showToast('Connected: ' + name, 'success');
  } catch { /* toast already shown */ }
}

// ── Games ────────────────────────────────────────────────────────────

let gamesCache = [];

async function loadGames() {
  const container = document.getElementById('games-list');
  container.innerHTML = '<div class="placeholder">Loading...</div>';
  try {
    const games = await api('/api/games');
    gamesCache = games;
    if (!games.length) {
      container.innerHTML = '<div class="placeholder">No games found. Check your settings and connection.</div>';
      return;
    }
    container.innerHTML = games.map(g => `
      <div class="game-card" onclick="navigateTo('challenges'); selectGameForChallenges(${g.id})">
        <h3>${escHtml(g.title)}</h3>
        <div class="game-summary">${escHtml((g.summary || g.content || '').slice(0, 120))}</div>
        <div class="game-meta">
          <span>#${g.id}</span>
          <span>${g.teamCount || '-'} teams</span>
        </div>
      </div>
    `).join('');
  } catch {
    container.innerHTML = '<div class="placeholder">Failed to load games</div>';
  }
}

function selectGameForChallenges(gameId) {
  const sel = document.getElementById('challenge-game-select');
  sel.value = gameId;
  loadChallenges(gameId);
}

// ── Challenges ───────────────────────────────────────────────────────

async function refreshChallengeGameSelect() {
  const sel = document.getElementById('challenge-game-select');
  if (sel.options.length <= 1 && gamesCache.length) {
    populateGameSelect(sel, gamesCache);
  }
  if (sel.options.length <= 1) {
    try {
      const games = await api('/api/games');
      gamesCache = games;
      populateGameSelect(sel, games);
    } catch { /* skip */ }
  }
}

function populateGameSelect(sel, games) {
  const current = sel.value;
  sel.innerHTML = '<option value="">Select a game...</option>';
  games.forEach(g => {
    const opt = document.createElement('option');
    opt.value = g.id;
    opt.textContent = `#${g.id} - ${g.title}`;
    sel.appendChild(opt);
  });
  if (current) sel.value = current;
}

async function loadChallenges(gameId) {
  const container = document.getElementById('challenges-container');
  if (!gameId) {
    container.innerHTML = '<div class="placeholder">Select a game to view challenges</div>';
    return;
  }
  container.innerHTML = '<div class="placeholder">Loading...</div>';
  try {
    const categories = await api(`/api/games/${gameId}/challenges`);
    let html = '';
    for (const [cat, challenges] of Object.entries(categories)) {
      html += `
        <div class="card" style="margin-bottom:16px;">
          <h3><span class="badge badge-category">${escHtml(cat)}</span> ${challenges.length} challenges</h3>
          <div class="table-container"><table>
            <thead><tr><th>ID</th><th>Title</th><th>Score</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              ${challenges.map(c => `
                <tr>
                  <td>${c.id}</td>
                  <td>${escHtml(c.title)}</td>
                  <td>${c.score || c.originalScore || '-'}</td>
                  <td>${c.isSolved
                    ? '<span class="badge badge-solved">Solved</span>'
                    : '<span class="badge badge-unsolved">Unsolved</span>'
                  }</td>
                  <td><button class="btn btn-small btn-solve" onclick="quickSolve(${gameId},${c.id})">Solve</button></td>
                </tr>
              `).join('')}
            </tbody>
          </table></div>
        </div>
      `;
    }
    container.innerHTML = html || '<div class="placeholder">No challenges found</div>';
  } catch {
    container.innerHTML = '<div class="placeholder">Failed to load challenges</div>';
  }
}

function quickSolve(gameId, challengeId) {
  navigateTo('agent');
  const gs = document.getElementById('agent-game-select');
  gs.value = gameId;
  onAgentGameChange(gameId).then(() => {
    document.getElementById('agent-challenge-select').value = challengeId;
  });
}

// ── Agent ────────────────────────────────────────────────────────────

async function refreshSelects() {
  const sel = document.getElementById('agent-game-select');
  if (sel.options.length <= 1) {
    try {
      const games = gamesCache.length ? gamesCache : await api('/api/games');
      gamesCache = games;
      populateGameSelect(sel, games);
    } catch { /* skip */ }
  }
}

async function onAgentGameChange(gameId) {
  const sel = document.getElementById('agent-challenge-select');
  sel.innerHTML = '<option value="">All Challenges (Per-Category)</option>';
  if (!gameId) return;
  try {
    const categories = await api(`/api/games/${gameId}/challenges`);
    for (const [cat, challenges] of Object.entries(categories)) {
      challenges.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = `[${cat}] ${c.title} (${c.score || '-'} pts)`;
        sel.appendChild(opt);
      });
    }
  } catch { /* skip */ }
}

let currentWs = null;
let currentTaskId = null;

async function startSolve() {
  const gameId = parseInt(document.getElementById('agent-game-select').value);
  if (!gameId) { showToast('Please select a game', 'warning'); return; }
  const challengeId = parseInt(document.getElementById('agent-challenge-select').value) || null;
  const concurrent = document.getElementById('agent-concurrent').checked;

  try {
    const result = await api('/api/solve', {
      method: 'POST',
      body: JSON.stringify({ game_id: gameId, challenge_id: challengeId, concurrent }),
    });
    currentTaskId = result.task_id;
    showToast(`Task ${result.task_id} started`, 'success');
    showLogViewer(result.task_id);
    connectLogStream(result.task_id);
    loadTasksList();
  } catch { /* toast already shown */ }
}

function showLogViewer(taskId) {
  document.getElementById('log-card').style.display = 'block';
  document.getElementById('log-output').innerHTML = '';
  document.getElementById('log-task-id').textContent = taskId;
  document.getElementById('log-task-id').className = 'badge badge-running';
  document.getElementById('log-status').textContent = 'Connecting...';
}

async function loadTasksList() {
  const card = document.getElementById('tasks-card');
  const container = document.getElementById('tasks-list');
  try {
    const tasks = await api('/api/tasks');
    const ids = Object.keys(tasks);
    if (!ids.length) { card.style.display = 'none'; return; }
    card.style.display = 'block';
    container.innerHTML = ids.reverse().map(tid => {
      const t = tasks[tid];
      const statusClass = t.status === 'running' ? 'badge-running'
        : t.status === 'completed' ? 'badge-completed' : 'badge-error';
      return `
        <div class="task-item" onclick="viewTaskLogs('${tid}')">
          <div class="task-info">
            <span class="badge ${statusClass}">${t.status}</span>
            <span>Task ${tid} &mdash; Game #${t.game_id}${t.challenge_id ? ' Ch#' + t.challenge_id : ' (All)'}</span>
          </div>
          <span style="color:var(--text-muted);font-size:12px;">${t.log_count} logs</span>
        </div>
      `;
    }).join('');
  } catch { /* skip */ }
}

async function viewTaskLogs(taskId) {
  showLogViewer(taskId);
  if (currentWs) { currentWs.close(); currentWs = null; }

  try {
    const data = await api(`/api/tasks/${taskId}/logs`);
    const logOutput = document.getElementById('log-output');
    logOutput.innerHTML = '';
    (data.logs || []).forEach(log => appendLog(logOutput, log));

    if (data.status === 'running') {
      connectLogStream(taskId);
    } else {
      document.getElementById('log-task-id').className =
        `badge ${data.status === 'completed' ? 'badge-completed' : 'badge-error'}`;
      document.getElementById('log-status').textContent = data.status;
    }
  } catch { /* toast */ }
}

// ── WebSocket Log Streaming ──────────────────────────────────────────

function connectLogStream(taskId) {
  if (currentWs) { currentWs.close(); }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}/ws/logs/${taskId}`);
  currentWs = ws;

  ws.onopen = () => {
    document.getElementById('log-status').textContent = 'Live';
    document.getElementById('log-status').style.color = 'var(--success)';
  };

  ws.onmessage = (event) => {
    const log = JSON.parse(event.data);
    const logOutput = document.getElementById('log-output');
    appendLog(logOutput, log);
    if (log.type === 'done') {
      document.getElementById('log-task-id').className =
        `badge ${log.status === 'completed' ? 'badge-completed' : 'badge-error'}`;
      document.getElementById('log-status').textContent = log.status || 'Done';
      loadTasksList();
    }
  };

  ws.onerror = () => {
    document.getElementById('log-status').textContent = 'Disconnected';
    document.getElementById('log-status').style.color = 'var(--danger)';
    // Fallback to polling
    pollLogs(taskId);
  };

  ws.onclose = () => {
    if (currentWs === ws) currentWs = null;
  };
}

function pollLogs(taskId) {
  let seen = 0;
  const interval = setInterval(async () => {
    try {
      const data = await api(`/api/tasks/${taskId}/logs`);
      const logOutput = document.getElementById('log-output');
      const logs = data.logs || [];
      for (let i = seen; i < logs.length; i++) {
        appendLog(logOutput, logs[i]);
      }
      seen = logs.length;
      if (data.status !== 'running') {
        clearInterval(interval);
        document.getElementById('log-task-id').className =
          `badge ${data.status === 'completed' ? 'badge-completed' : 'badge-error'}`;
        document.getElementById('log-status').textContent = data.status;
        loadTasksList();
      }
    } catch { clearInterval(interval); }
  }, 1500);
}

// ── Log rendering ────────────────────────────────────────────────────

function appendLog(container, log) {
  const el = document.createElement('div');
  el.className = `log-entry log-${log.type || 'info'}`;

  const time = new Date().toLocaleTimeString();
  let content = `<span class="log-time">${time}</span>`;

  if (log.category) {
    content += `<span class="log-cat-tag">${escHtml(log.category)}</span>`;
  }

  switch (log.type) {
    case 'challenge':
      content += `<strong>${escHtml(log.message)}</strong>`;
      if (log.score) content += ` <span class="badge badge-info">${log.score} pts</span>`;
      break;
    case 'llm_response':
      content += escHtml(log.message);
      if (log.action) content += ` <span class="log-action-badge">${escHtml(log.action)}</span>`;
      if (log.confidence) content += ` <span style="color:var(--text-muted)">confidence: ${log.confidence}</span>`;
      break;
    case 'code':
      content += `<pre class="code-block">${escHtml(log.message)}</pre>`;
      break;
    case 'code_output':
      content += `<pre class="code-block" style="border-color:var(--success);">${escHtml(log.message)}</pre>`;
      break;
    case 'flag_submit':
    case 'flag_result':
      content += `<strong>${escHtml(log.message)}</strong>`;
      break;
    case 'result':
      content += `<strong>${escHtml(log.message)}</strong>`;
      break;
    default:
      content += escHtml(log.message);
  }

  el.innerHTML = content;
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
}

// ── Init ─────────────────────────────────────────────────────────────

refreshDashboard();
