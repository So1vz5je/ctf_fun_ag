/* ── CTF Agent Frontend ─────────────────────────────────────────── */

const API = '';  // same origin

// ── Navigation ───────────────────────────────────────────────────

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    const page = item.dataset.page;
    navigateTo(page);
  });
});

function navigateTo(page) {
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const navItem = document.querySelector(`.nav-item[data-page="${page}"]`);
  const pageEl = document.getElementById(`page-${page}`);
  if (navItem) navItem.classList.add('active');
  if (pageEl) pageEl.classList.add('active');

  // Auto-load on navigation
  if (page === 'games') loadGames();
  if (page === 'settings') loadSettings();
  if (page === 'agent') { loadTasksList(); populateGameSelects(); }
  if (page === 'challenges') populateGameSelects();
  if (page === 'dashboard') loadDashboard();
}

// ── Settings ─────────────────────────────────────────────────────

async function loadSettings() {
  try {
    const resp = await fetch(`${API}/api/settings`);
    const data = await resp.json();
    document.getElementById('set-gzctf-url').value = data.gzctf_url || '';
    document.getElementById('set-gzctf-username').value = data.gzctf_username || '';
    document.getElementById('set-gzctf-password').value = data.gzctf_password || '';
    document.getElementById('set-gzctf-team-id').value = data.gzctf_team_id || '';
    document.getElementById('set-llm-provider').value = data.llm_provider || 'openai';
    document.getElementById('set-llm-api-key').value = data.llm_api_key || '';
    document.getElementById('set-llm-base-url').value = data.llm_base_url || '';
    document.getElementById('set-llm-model').value = data.llm_model || 'gpt-4o';
    document.getElementById('set-llm-temperature').value = data.llm_temperature || 0.1;
    document.getElementById('set-llm-max-tokens').value = data.llm_max_tokens || 4096;
    document.getElementById('set-agent-retries').value = data.agent_max_retries || 3;
    document.getElementById('set-agent-auto-submit').checked = data.agent_auto_submit !== false;
    document.getElementById('set-agent-auto-container').checked = data.agent_auto_start_container !== false;
    document.getElementById('set-agent-skip-solved').checked = data.agent_skip_solved !== false;
    document.getElementById('set-agent-categories').value = (data.agent_categories || []).join(',');
  } catch (e) {
    console.error('Failed to load settings:', e);
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const body = {
    gzctf_url: document.getElementById('set-gzctf-url').value,
    gzctf_username: document.getElementById('set-gzctf-username').value,
    gzctf_password: document.getElementById('set-gzctf-password').value,
    gzctf_team_id: parseInt(document.getElementById('set-gzctf-team-id').value) || null,
    llm_provider: document.getElementById('set-llm-provider').value,
    llm_api_key: document.getElementById('set-llm-api-key').value,
    llm_base_url: document.getElementById('set-llm-base-url').value || null,
    llm_model: document.getElementById('set-llm-model').value,
    llm_temperature: parseFloat(document.getElementById('set-llm-temperature').value),
    llm_max_tokens: parseInt(document.getElementById('set-llm-max-tokens').value),
    agent_max_retries: parseInt(document.getElementById('set-agent-retries').value),
    agent_auto_submit: document.getElementById('set-agent-auto-submit').checked,
    agent_auto_start_container: document.getElementById('set-agent-auto-container').checked,
    agent_skip_solved: document.getElementById('set-agent-skip-solved').checked,
    agent_categories: document.getElementById('set-agent-categories').value.split(',').map(s => s.trim()).filter(Boolean),
  };

  try {
    const resp = await fetch(`${API}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (resp.ok) {
      showToast('设置已保存');
    } else {
      showToast('保存失败', 'error');
    }
  } catch (e) {
    showToast('保存失败: ' + e.message, 'error');
  }
}

async function testConnection() {
  const status = document.getElementById('connection-status');
  status.textContent = '连接中...';
  status.style.color = 'var(--info)';
  try {
    // Save settings first
    await saveSettings(new Event('submit'));
    const resp = await fetch(`${API}/api/login`, { method: 'POST' });
    if (resp.ok) {
      const data = await resp.json();
      status.textContent = `连接成功! 用户: ${data.userName}`;
      status.style.color = 'var(--success)';
    } else {
      status.textContent = '连接失败';
      status.style.color = 'var(--danger)';
    }
  } catch (e) {
    status.textContent = '连接失败: ' + e.message;
    status.style.color = 'var(--danger)';
  }
}

// ── Games ────────────────────────────────────────────────────────

let gamesCache = [];

async function loadGames() {
  const container = document.getElementById('games-list');
  container.innerHTML = '<div class="placeholder">加载中...</div>';
  try {
    const resp = await fetch(`${API}/api/games`);
    const games = await resp.json();
    gamesCache = games;
    populateGameSelects();

    if (!games.length) {
      container.innerHTML = '<div class="placeholder">暂无比赛</div>';
      return;
    }
    container.innerHTML = games.map(g => `
      <div class="game-card" onclick="selectGame(${g.id})">
        <h3>${escHtml(g.title)}</h3>
        <p style="color:var(--text-dim);font-size:13px">${escHtml(g.summary || '')}</p>
        <div class="game-meta">
          <span>状态: <strong>${escHtml(g.status || '未知')}</strong></span>
          <span>队伍: ${g.teamCount || 0}</span>
          <span>ID: #${g.id}</span>
        </div>
      </div>
    `).join('');

    document.getElementById('stat-games').textContent = games.length;
  } catch (e) {
    container.innerHTML = `<div class="placeholder">加载失败: ${escHtml(e.message)}<br>请先在设置中配置平台地址并测试连接</div>`;
  }
}

function selectGame(gameId) {
  document.getElementById('game-select').value = gameId;
  document.getElementById('solve-game-select').value = gameId;
  navigateTo('challenges');
  loadChallenges();
}

function populateGameSelects() {
  ['game-select', 'solve-game-select'].forEach(id => {
    const sel = document.getElementById(id);
    const current = sel.value;
    sel.innerHTML = '<option value="">选择比赛...</option>';
    gamesCache.forEach(g => {
      sel.innerHTML += `<option value="${g.id}">${escHtml(g.title)} (#${g.id})</option>`;
    });
    if (current) sel.value = current;
  });
}

// ── Challenges ───────────────────────────────────────────────────

async function loadChallenges() {
  const gameId = document.getElementById('game-select').value;
  const container = document.getElementById('challenges-list');
  if (!gameId) {
    container.innerHTML = '<div class="placeholder">请先选择一场比赛</div>';
    return;
  }
  container.innerHTML = '<div class="placeholder">加载中...</div>';
  try {
    const resp = await fetch(`${API}/api/games/${gameId}/challenges`);
    const categories = await resp.json();

    let rows = '';
    for (const [cat, challenges] of Object.entries(categories)) {
      for (const ch of challenges) {
        const statusBadge = ch.isSolved
          ? '<span class="badge badge-solved">已解决</span>'
          : '<span class="badge badge-unsolved">未解决</span>';
        rows += `<tr>
          <td>${ch.id}</td>
          <td><span class="badge badge-info">${escHtml(cat)}</span></td>
          <td><strong>${escHtml(ch.title)}</strong></td>
          <td>${ch.score}</td>
          <td>${statusBadge}</td>
          <td>
            <button class="btn btn-small btn-solve" onclick="solveOne(${gameId}, ${ch.id})">
              解题
            </button>
          </td>
        </tr>`;
      }
    }

    if (!rows) {
      container.innerHTML = '<div class="placeholder">暂无题目</div>';
      return;
    }

    container.innerHTML = `
      <table>
        <thead><tr><th>ID</th><th>分类</th><th>标题</th><th>分值</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  } catch (e) {
    container.innerHTML = `<div class="placeholder">加载失败: ${escHtml(e.message)}</div>`;
  }
}

// ── Agent / Solve ────────────────────────────────────────────────

function solveOne(gameId, challengeId) {
  document.getElementById('solve-game-select').value = gameId;
  document.getElementById('solve-challenge-id').value = challengeId;
  navigateTo('agent');
  startSolve();
}

async function startSolve() {
  const gameId = document.getElementById('solve-game-select').value;
  if (!gameId) {
    showToast('请先选择比赛', 'error');
    return;
  }
  const challengeId = document.getElementById('solve-challenge-id').value || null;

  try {
    const resp = await fetch(`${API}/api/solve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        game_id: parseInt(gameId),
        challenge_id: challengeId ? parseInt(challengeId) : null,
      }),
    });
    const data = await resp.json();
    if (data.task_id) {
      showToast('解题任务已启动: ' + data.task_id);
      connectLogStream(data.task_id);
      loadTasksList();
    } else {
      showToast('启动失败', 'error');
    }
  } catch (e) {
    showToast('启动失败: ' + e.message, 'error');
  }
}

async function loadTasksList() {
  try {
    const resp = await fetch(`${API}/api/tasks`);
    const tasks = await resp.json();
    const container = document.getElementById('tasks-list');

    const entries = Object.entries(tasks);
    if (!entries.length) {
      container.innerHTML = '<div style="color:var(--text-dim);padding:8px">暂无任务</div>';
      document.getElementById('stat-tasks').textContent = '0';
      return;
    }

    document.getElementById('stat-tasks').textContent = entries.length;

    container.innerHTML = entries.map(([tid, t]) => {
      const statusClass = t.status === 'running' ? 'badge-running'
        : t.status === 'completed' ? 'badge-completed' : 'badge-error';
      const chLabel = t.challenge_id ? `题目#${t.challenge_id}` : '全部题目';
      return `
        <div class="task-item" onclick="connectLogStream('${tid}')">
          <div class="task-info">
            <span class="badge ${statusClass}">${t.status}</span>
            <span>比赛#${t.game_id} ${chLabel}</span>
          </div>
          <span style="color:var(--text-dim);font-size:12px">${tid} (${t.log_count} 条日志)</span>
        </div>
      `;
    }).join('');
  } catch (e) {
    console.error('Failed to load tasks:', e);
  }
}

// ── WebSocket log streaming ──────────────────────────────────────

let currentWs = null;

function connectLogStream(taskId) {
  // Close existing connection
  if (currentWs) {
    currentWs.close();
    currentWs = null;
  }

  const logOutput = document.getElementById('log-output');
  const logTaskId = document.getElementById('log-task-id');
  logOutput.innerHTML = '';
  logTaskId.textContent = taskId;
  logTaskId.className = 'badge badge-running';

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${proto}//${location.host}/ws/logs/${taskId}`;

  const ws = new WebSocket(wsUrl);
  currentWs = ws;

  ws.onmessage = (event) => {
    const log = JSON.parse(event.data);
    appendLog(logOutput, log);
    logOutput.scrollTop = logOutput.scrollHeight;

    if (log.type === 'done') {
      logTaskId.className = `badge ${log.status === 'completed' ? 'badge-completed' : 'badge-error'}`;
      logTaskId.textContent = `${taskId} (${log.status})`;
      loadTasksList();
    }
  };

  ws.onerror = () => {
    // Fallback to polling
    pollLogs(taskId, logOutput, logTaskId);
  };

  ws.onclose = () => {
    currentWs = null;
  };
}

async function pollLogs(taskId, logOutput, logTaskId) {
  let seen = 0;
  const poll = async () => {
    try {
      const resp = await fetch(`${API}/api/tasks/${taskId}/logs`);
      const data = await resp.json();

      if (data.logs && data.logs.length > seen) {
        for (let i = seen; i < data.logs.length; i++) {
          appendLog(logOutput, data.logs[i]);
        }
        seen = data.logs.length;
        logOutput.scrollTop = logOutput.scrollHeight;
      }

      if (data.status !== 'running') {
        logTaskId.className = `badge ${data.status === 'completed' ? 'badge-completed' : 'badge-error'}`;
        logTaskId.textContent = `${taskId} (${data.status})`;
        loadTasksList();
        return;
      }
      setTimeout(poll, 1000);
    } catch (e) {
      setTimeout(poll, 2000);
    }
  };
  poll();
}

function appendLog(container, log) {
  const div = document.createElement('div');
  div.className = `log-entry log-${log.type}`;

  const time = new Date().toLocaleTimeString();
  let content = `<span class="log-time">[${time}]</span> `;

  switch (log.type) {
    case 'challenge':
      content += `<strong>📋 ${escHtml(log.message)}</strong>`;
      break;
    case 'thinking':
      content += `<em>🤔 ${escHtml(log.message)}</em>`;
      break;
    case 'llm_response':
      const actionBadge = log.action
        ? `<span class="log-action-badge" style="background:var(--accent);color:#fff">${escHtml(log.action)}</span>`
        : '';
      content += `${actionBadge}${escHtml(log.message)}`;
      if (log.confidence) content += ` <span style="color:var(--text-dim)">(置信度: ${log.confidence})</span>`;
      break;
    case 'code':
      content += `<pre style="margin:4px 0;padding:8px;background:rgba(0,0,0,0.3);border-radius:4px;overflow-x:auto">${escHtml(log.message)}</pre>`;
      break;
    case 'code_output':
      content += `<pre style="margin:4px 0;padding:8px;background:rgba(0,0,0,0.2);border-radius:4px;overflow-x:auto">📤 ${escHtml(log.message)}</pre>`;
      break;
    case 'flag_submit':
      content += `🚩 ${escHtml(log.message)}`;
      break;
    case 'flag_result':
      content += `✅ ${escHtml(log.message)}`;
      break;
    case 'error':
      content += `❌ ${escHtml(log.message)}`;
      break;
    case 'result':
      content += `🏁 <strong>${escHtml(log.message)}</strong>`;
      break;
    case 'done':
      content += `⏹ 任务结束 (${escHtml(log.status)})`;
      break;
    default:
      content += escHtml(log.message);
  }

  div.innerHTML = content;
  container.appendChild(div);
}

// ── Dashboard ────────────────────────────────────────────────────

async function loadDashboard() {
  try {
    const resp = await fetch(`${API}/api/settings`);
    const data = await resp.json();
    const statusEl = document.getElementById('stat-status');
    if (data.gzctf_url) {
      statusEl.textContent = '已配置';
      statusEl.style.color = 'var(--success)';
    } else {
      statusEl.textContent = '未配置';
      statusEl.style.color = 'var(--danger)';
    }
  } catch (e) {
    console.error(e);
  }
  loadTasksList();
}

// ── Helpers ──────────────────────────────────────────────────────

function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.style.cssText = `
    position: fixed; top: 20px; right: 20px; z-index: 9999;
    padding: 12px 20px; border-radius: 8px;
    background: ${type === 'error' ? 'var(--danger)' : 'var(--success)'};
    color: #fff; font-size: 14px; font-weight: 500;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    animation: fadeIn 0.3s ease;
  `;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// ── Init ─────────────────────────────────────────────────────────
loadDashboard();
