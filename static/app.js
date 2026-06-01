/* ══════════════════════════════════════════════════════════════════════
   GZ_CTF Agent — Frontend Application
   ══════════════════════════════════════════════════════════════════════ */

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
  if (page === 'challenges') refreshChallengeGameSelect();
  if (page === 'logs') refreshFullLogs();
}

// ── API helpers ──────────────────────────────────────────────────────

async function api(url, opts = {}) {
  try {
    const resp = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    });
    if (!resp.ok) {
      let errMsg = `${resp.status}`;
      try {
        const data = await resp.json();
        errMsg = data.error || data.detail || data.message || JSON.stringify(data).slice(0, 200);
      } catch {
        const text = await resp.text();
        errMsg = text.slice(0, 200) || errMsg;
      }
      throw new Error(errMsg);
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

let dashboardData = {
  games: [],
  challengesByGame: {},
  tasks: {},
  startTime: Date.now(),
};

let uptimeInterval = null;

function startUptimeTimer() {
  if (uptimeInterval) clearInterval(uptimeInterval);
  uptimeInterval = setInterval(() => {
    const elapsed = Date.now() - dashboardData.startTime;
    const h = String(Math.floor(elapsed / 3600000)).padStart(2, '0');
    const m = String(Math.floor((elapsed % 3600000) / 60000)).padStart(2, '0');
    const s = String(Math.floor((elapsed % 60000) / 1000)).padStart(2, '0');
    const el = document.getElementById('stat-uptime');
    if (el) el.textContent = `${h}:${m}:${s}`;
  }, 1000);
}

async function refreshDashboard() {
  try {
    const tasks = await api('/api/tasks');
    dashboardData.tasks = tasks;
    const taskIds = Object.keys(tasks);
    const running = Object.values(tasks).filter(t => t.status === 'running').length;

    // Update connection status
    const indicator = document.getElementById('connection-indicator');
    const statusText = document.getElementById('header-status');
    indicator.classList.add('online');
    statusText.textContent = running > 0 ? '运行中' : '在线';

    // Update recent tasks table
    updateRecentTasks(tasks);

    // Try to load games
    const games = await api('/api/games').catch(() => []);
    dashboardData.games = Array.isArray(games) ? games : [];
    document.getElementById('stat-games').textContent = dashboardData.games.length;

    // If we have games, try to load challenges for the first active one
    if (dashboardData.games.length > 0) {
      updateCurrentGame(dashboardData.games[0]);
      try {
        const challenges = await api(`/api/games/${dashboardData.games[0].id}/challenges`);
        dashboardData.challengesByGame[dashboardData.games[0].id] = challenges;
        updateChallengeStats(challenges);
        drawCategoryChart(challenges);
      } catch {
        // games loaded but challenges failed
      }
    }
  } catch {
    const indicator = document.getElementById('connection-indicator');
    indicator.classList.remove('online');
    document.getElementById('header-status').textContent = '离线';
  }
}

async function refreshDashboardData() {
  showToast('正在刷新...', 'info');
  await refreshDashboard();
  showToast('刷新完成', 'success');
}

function updateCurrentGame(game) {
  const container = document.getElementById('current-game-info');
  if (!game) return;
  const url = game.inviteCode ? `https://gz.imxbt.cn/games/${game.id}` : '';
  container.innerHTML = `
    <div class="current-game-row">
      <div class="current-game-icon">CTF</div>
      <div class="current-game-details">
        <h4>${escHtml(game.title)}</h4>
        <div class="current-game-meta">
          ${url ? `<div>${escHtml(url)}</div>` : ''}
          <div>队伍数: ${game.teamCount || '-'}</div>
        </div>
      </div>
      <div class="current-game-progress">
        <div class="progress-ring-label" id="progress-pct">0%</div>
        <div class="progress-ring-sub">解题进度</div>
      </div>
    </div>
  `;
}

function updateChallengeStats(challenges) {
  let total = 0;
  let solved = 0;
  for (const [, items] of Object.entries(challenges)) {
    total += items.length;
    solved += items.filter(c => c.isSolved).length;
  }
  document.getElementById('stat-challenges').textContent = total;
  document.getElementById('stat-solved').textContent = solved;
  const pct = total > 0 ? ((solved / total) * 100).toFixed(1) : '0';
  document.getElementById('stat-accuracy').textContent = pct + '%';
  const pctEl = document.getElementById('progress-pct');
  if (pctEl) pctEl.textContent = pct + '%';
}

function updateRecentTasks(tasks) {
  const tbody = document.getElementById('recent-tasks-body');
  const ids = Object.keys(tasks);
  if (!ids.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="table-empty">暂无任务</td></tr>';
    return;
  }
  tbody.innerHTML = ids.slice(-5).reverse().map(tid => {
    const t = tasks[tid];
    const statusClass = t.status === 'running' ? 'badge-running'
      : t.status === 'completed' ? 'badge-completed' : 'badge-error';
    const type = t.challenge_id ? '解题任务' : '比赛任务';
    const name = t.challenge_id ? `Ch#${t.challenge_id}` : `Game#${t.game_id}`;
    return `<tr>
      <td>${type}</td>
      <td>${name}</td>
      <td><span class="badge ${statusClass}">${t.status}</span></td>
      <td style="font-size:11px;color:var(--text-muted);">${new Date().toLocaleTimeString()}</td>
    </tr>`;
  }).join('');
}

// ── Category Chart (Canvas donut) ────────────────────────────────────

const CATEGORY_COLORS = {
  'Web': '#3b82f6',
  'Pwn': '#ef4444',
  'Misc': '#8b5cf6',
  'Reverse': '#f59e0b',
  'Crypto': '#10b981',
  'Forensics': '#06b6d4',
  'OSINT': '#ec4899',
  'Blockchain': '#6366f1',
};

function getCategoryColor(cat, idx) {
  if (CATEGORY_COLORS[cat]) return CATEGORY_COLORS[cat];
  const fallback = ['#6366f1', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4'];
  return fallback[idx % fallback.length];
}

function drawCategoryChart(challenges) {
  const canvas = document.getElementById('category-chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  canvas.width = 128 * dpr;
  canvas.height = 128 * dpr;
  canvas.style.width = '128px';
  canvas.style.height = '128px';
  ctx.scale(dpr, dpr);

  const entries = Object.entries(challenges);
  let total = 0;
  const segments = [];
  entries.forEach(([cat, items], idx) => {
    const count = items.length;
    total += count;
    segments.push({ cat, count, color: getCategoryColor(cat, idx) });
  });

  document.getElementById('chart-total-num').textContent = total;

  const cx = 64, cy = 64, outerR = 58, innerR = 38;
  let startAngle = -Math.PI / 2;

  if (total === 0) {
    ctx.beginPath();
    ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
    ctx.arc(cx, cy, innerR, 0, Math.PI * 2, true);
    ctx.fillStyle = 'rgba(128,128,128,0.1)';
    ctx.fill();
  } else {
    segments.forEach(seg => {
      const sweep = (seg.count / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(cx, cy, outerR, startAngle, startAngle + sweep);
      ctx.arc(cx, cy, innerR, startAngle + sweep, startAngle, true);
      ctx.closePath();
      ctx.fillStyle = seg.color;
      ctx.fill();
      startAngle += sweep;
    });
  }

  // Legend
  const legend = document.getElementById('chart-legend');
  legend.innerHTML = segments.map(s => `
    <div class="legend-item">
      <span class="legend-dot" style="background:${s.color}"></span>
      ${escHtml(s.cat)} (${s.count})
    </div>
  `).join('');
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
  showToast('配置已保存', 'success');
}

async function testConnection() {
  showToast('保存配置并测试连接...', 'info');
  try {
    await saveSettings();
  } catch {
    showToast('保存配置失败，无法测试连接', 'error');
    return;
  }
  try {
    const profile = await api('/api/login', { method: 'POST' });
    const name = profile.userName || profile.bio || 'OK';
    showToast('连接成功: ' + name, 'success');
  } catch { /* toast already shown by api() */ }
}

// ── Games ────────────────────────────────────────────────────────────

let gamesCache = [];

async function loadGames() {
  const container = document.getElementById('games-list');
  container.innerHTML = '<div class="empty-state small"><p>加载中...</p></div>';
  try {
    const games = await api('/api/games');
    gamesCache = games;
    if (!games.length) {
      container.innerHTML = '<div class="empty-state"><p>未找到比赛，请检查配置和连接</p></div>';
      return;
    }
    container.innerHTML = games.map(g => `
      <div class="game-card" onclick="navigateTo('challenges'); selectGameForChallenges(${g.id})">
        <h3>${escHtml(g.title)}</h3>
        <div class="game-summary">${escHtml((g.summary || g.content || '').slice(0, 120))}</div>
        <div class="game-meta">
          <span>#${g.id}</span>
          <span>${g.teamCount || '-'} 支队伍</span>
        </div>
      </div>
    `).join('');
  } catch {
    container.innerHTML = '<div class="empty-state"><p>加载失败</p></div>';
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
  sel.innerHTML = '<option value="">选择比赛...</option>';
  games.forEach(g => {
    const opt = document.createElement('option');
    opt.value = g.id;
    opt.textContent = `#${g.id} - ${g.title}`;
    sel.appendChild(opt);
  });
  if (current) sel.value = current;
}

let currentChallengeGameId = null;

async function loadChallenges(gameId) {
  const container = document.getElementById('challenges-container');
  if (!gameId) {
    container.innerHTML = '<div class="empty-state"><p>选择比赛查看题目</p></div>';
    document.getElementById('btn-solve-all').style.display = 'none';
    document.getElementById('btn-stop-all').style.display = 'none';
    return;
  }
  currentChallengeGameId = parseInt(gameId);
  container.innerHTML = '<div class="empty-state small"><p>加载中...</p></div>';
  try {
    const categories = await api(`/api/games/${gameId}/challenges`);
    let html = '';
    for (const [cat, challenges] of Object.entries(categories)) {
      const solved = challenges.filter(c => c.isSolved).length;
      html += `
        <div class="challenge-category-card" id="cat-${escHtml(cat)}">
          <div class="challenge-category-header" onclick="toggleCategory(this)">
            <h3>
              <svg class="category-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
              <span class="badge badge-category">${escHtml(cat)}</span>
              ${challenges.length} 题 (${solved} 已解)
            </h3>
            <div class="category-header-actions">
              <button class="btn btn-small btn-solve" onclick="event.stopPropagation();solveCategory(${gameId},'${escHtml(cat)}')">解题该方向</button>
            </div>
          </div>
          <div class="challenge-category-body">
            <div style="overflow-x:auto;">
              <table class="dash-table">
                <thead><tr><th>ID</th><th>标题</th><th>分值</th><th>状态</th><th>操作</th></tr></thead>
                <tbody>
                  ${challenges.map(c => `
                    <tr>
                      <td>${c.id}</td>
                      <td style="font-weight:500;">${escHtml(c.title)}</td>
                      <td>${c.score || c.originalScore || '-'}</td>
                      <td>${c.isSolved
                        ? '<span class="badge badge-solved">已解</span>'
                        : '<span class="badge badge-unsolved">未解</span>'
                      }</td>
                      <td><button class="btn btn-small btn-solve" onclick="solveSingle(${gameId},${c.id})">Solve</button></td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      `;
    }
    container.innerHTML = html || '<div class="empty-state"><p>暂无题目</p></div>';
    document.getElementById('btn-solve-all').style.display = '';
    document.getElementById('btn-stop-all').style.display = '';
  } catch {
    container.innerHTML = '<div class="empty-state"><p>加载失败</p></div>';
  }
}

function toggleCategory(headerEl) {
  headerEl.closest('.challenge-category-card').classList.toggle('collapsed');
}

function solveSingle(gameId, challengeId) {
  startSolveTask(gameId, challengeId, false);
}

function solveCategory(gameId, category) {
  // category solve = all challenges, concurrent, but we pass game_id only
  // Backend handles per-category agent when challenge_id is null
  startSolveTask(gameId, null, true);
}

function solveAllCategories() {
  if (!currentChallengeGameId) { showToast('请先选择比赛', 'warning'); return; }
  startSolveTask(currentChallengeGameId, null, true);
}



function stopAllTasks() {
  showToast('停止功能开发中...', 'warning');
}

function setFlowStep(step) {
  const steps = ['read', 'download', 'container', 'solve', 'submit'];
  const idx = steps.indexOf(step);
  steps.forEach((s, i) => {
    const el = document.getElementById('flow-' + s);
    if (!el) return;
    el.classList.remove('active', 'done');
    if (i < idx) el.classList.add('done');
    if (i === idx) el.classList.add('active');
  });
  const info = document.getElementById('agent-current-info');
  const labels = { read: '正在读取题目...', download: '正在下载附件...', container: '正在启动靶机...', solve: '正在解题分析...', submit: '正在提交Flag...' };
  if (info) info.innerHTML = `<span class="agent-current-label">${labels[step] || '等待任务'}</span>`;
  // Progress
  const pct = ((idx + 1) / steps.length) * 100;
  const bar = document.getElementById('agent-progress');
  if (bar) bar.style.width = pct + '%';
}

function showChallengeLogViewer(taskId) {
  const card = document.getElementById('challenge-log-card');
  if (!card) return;
  card.style.display = 'block';
  document.getElementById('challenge-log-output').innerHTML = '';
  document.getElementById('challenge-log-task-id').textContent = taskId;
  document.getElementById('challenge-log-task-id').className = 'badge badge-running';
  document.getElementById('challenge-log-status').textContent = '连接中...';
  card.scrollIntoView({ behavior: 'smooth' });
}

// ── WebSocket Log Streaming ──────────────────────────────────────────

function connectLogStream(taskId) {
  if (currentWs) { currentWs.close(); }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}/ws/logs/${taskId}`);
  currentWs = ws;

  ws.onopen = () => {
    const s = document.getElementById('challenge-log-status');
    if (s) { s.textContent = '实时'; s.style.color = 'var(--success)'; }
  };

  ws.onmessage = (event) => {
    const log = JSON.parse(event.data);

    // Write to challenge page log viewer
    const challengeLog = document.getElementById('challenge-log-output');
    if (challengeLog) appendLog(challengeLog, log);

    // Also push to dashboard log
    const dashLog = document.getElementById('dash-log-output');
    if (dashLog) {
      const emptyState = dashLog.querySelector('.empty-state');
      if (emptyState) emptyState.remove();
      appendLog(dashLog, log, true);
    }

    // Also push to full logs page
    const fullLog = document.getElementById('full-log-output');
    if (fullLog) {
      const emptyState = fullLog.querySelector('.empty-state');
      if (emptyState) emptyState.remove();
      appendLog(fullLog, log);
    }

    // Update flow steps based on log type
    if (log.type === 'challenge' || log.type === 'category_start') setFlowStep('read');
    if (log.message && log.message.includes('下载')) setFlowStep('download');
    if (log.message && log.message.includes('靶机')) setFlowStep('container');
    if (log.type === 'thinking' || log.type === 'llm_response') setFlowStep('solve');
    if (log.type === 'flag_submit') setFlowStep('submit');

    if (log.type === 'done') {
      const tid = document.getElementById('challenge-log-task-id');
      if (tid) tid.className = `badge ${log.status === 'completed' ? 'badge-completed' : 'badge-error'}`;
      const ls = document.getElementById('challenge-log-status');
      if (ls) ls.textContent = log.status || '完成';
    }
  };

  ws.onerror = () => {
    const s = document.getElementById('challenge-log-status');
    if (s) { s.textContent = '已断开'; s.style.color = 'var(--danger)'; }
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
      const logOutput = document.getElementById('challenge-log-output');
      const logs = data.logs || [];
      if (logOutput) {
        for (let i = seen; i < logs.length; i++) {
          appendLog(logOutput, logs[i]);
        }
      }
      seen = logs.length;
      if (data.status !== 'running') {
        clearInterval(interval);
        const tid = document.getElementById('challenge-log-task-id');
        if (tid) tid.className = `badge ${data.status === 'completed' ? 'badge-completed' : 'badge-error'}`;
        const ls = document.getElementById('challenge-log-status');
        if (ls) ls.textContent = data.status;
      }
    } catch { clearInterval(interval); }
  }, 1500);
}

// ── Full Logs page ───────────────────────────────────────────────────

async function refreshFullLogs() {
  const container = document.getElementById('full-log-output');
  try {
    const tasks = await api('/api/tasks');
    const ids = Object.keys(tasks);
    if (!ids.length) return;
    container.innerHTML = '';
    // Show logs from all tasks
    for (const tid of ids.reverse()) {
      try {
        const data = await api(`/api/tasks/${tid}/logs`);
        const header = document.createElement('div');
        header.className = 'log-entry log-category_start';
        header.innerHTML = `<strong>═══ 任务 ${tid} (Game#${tasks[tid].game_id}) ═══</strong>`;
        container.appendChild(header);
        (data.logs || []).forEach(log => appendLog(container, log));
      } catch { /* skip */ }
    }
  } catch { /* skip */ }
}

function clearDashLogs() {
  const el = document.getElementById('full-log-output');
  if (el) el.innerHTML = '<div class="empty-state small"><p>日志已清空</p></div>';
}

// ── Log rendering ────────────────────────────────────────────────────

function appendLog(container, log, compact = false) {
  const el = document.createElement('div');
  el.className = `log-entry log-${log.type || 'info'}`;

  const time = new Date().toLocaleTimeString();
  let content = `<span class="log-time">${time}</span>`;

  if (log.category) {
    content += `<span class="log-cat-tag">${escHtml(log.category)}</span>`;
  }

  const typeLabels = {
    info: 'INFO',
    error: 'ERROR',
    challenge: 'TASK',
    flag_submit: 'FLAG',
    flag_result: 'FLAG',
    result: 'DONE',
  };
  const typeLabel = typeLabels[log.type];
  if (typeLabel) {
    content += `<span style="font-weight:700;margin-right:6px;">[${typeLabel}]</span>`;
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
      if (compact) {
        content += `<span style="color:var(--warning)">代码执行...</span>`;
      } else {
        content += `<pre class="code-block">${escHtml(log.message)}</pre>`;
      }
      break;
    case 'code_output':
      if (compact) {
        content += `<span style="color:var(--text-dim)">代码输出: ${escHtml((log.message || '').slice(0, 80))}</span>`;
      } else {
        content += `<pre class="code-block" style="border-color:var(--success);">${escHtml(log.message)}</pre>`;
      }
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

startUptimeTimer();
refreshDashboard();
