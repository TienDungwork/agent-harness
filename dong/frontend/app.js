/**
 * agent_ATIN v3 — Frontend Client Logic
 * Claude-inspired UI, Tool Execution Accordion, Markdown Rendering, Model Config
 */

(function () {
  'use strict';

  // State
  const state = {
    activeModel: localStorage.getItem('agent_model_provider') || 'openai',
    apiBaseUrl: localStorage.getItem('agent_api_base_url') || '',
    isGenerating: false,
    messages: [],
    graphNodes: {},
    streamAbortController: null,
    streamEventsCount: 0,
    userId: null,
    activeSessionId: null,
    sessions: [],
    lastChart: null,
    lastChartSpec: null,
    lastChartType: null,
    lastChartRows: null,
    lastStreamError: null,
  };

  // DOM Elements
  const el = {
    sidebar: document.getElementById('sidebar'),
    btnToggleSidebar: document.getElementById('btn-toggle-sidebar'),
    btnNewChat: document.getElementById('btn-new-chat'),
    sessionList: document.getElementById('session-list'),
    domainChips: document.getElementById('domain-chips'),
    btnOpenSettings: document.getElementById('btn-open-settings'),
    sidebarModelLabel: document.getElementById('sidebar-model-label'),
    systemStatusText: document.getElementById('system-status-text'),
    systemStatusBadge: document.getElementById('system-status-badge'),
    chatViewport: document.getElementById('chat-viewport'),
    welcomeScreen: document.getElementById('welcome-screen'),
    messagesList: document.getElementById('messages-list'),
    questionInput: document.getElementById('question-input'),
    btnSend: document.getElementById('btn-send'),
    settingsModal: document.getElementById('settings-modal'),
    btnCloseSettings: document.getElementById('btn-close-settings'),
    btnSaveSettings: document.getElementById('btn-save-settings'),
    radioOpenAI: document.getElementById('radio-openai'),
    radioSelfHosted: document.getElementById('radio-self-hosted'),
    inputApiUrl: document.getElementById('input-api-url'),
    btnCheckHealth: document.getElementById('btn-check-health'),
    healthResult: document.getElementById('health-result'),
    graphPlaceholder: document.getElementById('graph-placeholder'),
    graphNodes: document.getElementById('graph-nodes'),
    graphIoEmpty: document.getElementById('graph-io-empty'),
    graphIoBody: document.getElementById('graph-io-body'),
    graphPanelHint: document.getElementById('graph-panel-hint'),
  };


  // ==========================================================================
  // Session & LocalStorage Helpers (Phase 2)
  // ==========================================================================
  function generateUUID() {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  async function initUserAndSessions() {
    // agent_user_id: UUID once
    let uid = localStorage.getItem('agent_user_id');
    if (!uid) {
      uid = generateUUID();
      localStorage.setItem('agent_user_id', uid);
    }
    state.userId = uid;

    // Clean up mock agent_sessions if leftover from Phase 2
    localStorage.removeItem('agent_sessions');

    let loaded = [];
    try {
      const res = await fetch(getApiEndpoint(`/api/sessions?user_id=${encodeURIComponent(state.userId)}`));
      if (res.ok) {
        const data = await res.json();
        loaded = Array.isArray(data.sessions) ? data.sessions : [];
      }
    } catch (err) {
      console.error('Lỗi khi tải danh sách sessions:', err);
      loaded = [];
    }

    if (loaded.length === 0) {
      try {
        const res = await fetch(getApiEndpoint('/api/sessions'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: state.userId }),
        });
        if (res.ok) {
          const firstSession = await res.json();
          loaded = [firstSession];
        }
      } catch (err) {
        console.error('Lỗi khi tạo session mặc định:', err);
      }
    }

    loaded.forEach(s => {
      if (!Array.isArray(s.messages)) s.messages = [];
    });
    state.sessions = loaded;

    // agent_session_id
    let sid = localStorage.getItem('agent_session_id');
    if (!sid || !state.sessions.some(s => s.id === sid)) {
      sid = state.sessions.length > 0 ? state.sessions[0].id : null;
      if (sid) {
        localStorage.setItem('agent_session_id', sid);
      } else {
        localStorage.removeItem('agent_session_id');
      }
    }
    state.activeSessionId = sid;
  }

  function formatSessionTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return '';
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    if (isToday) {
      return `${hours}:${minutes}`;
    }
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    return `${day}/${month} ${hours}:${minutes}`;
  }

  function renderSessionList() {
    if (!el.sessionList) return;
    el.sessionList.innerHTML = '';

    state.sessions.forEach(sess => {
      const item = document.createElement('div');
      item.className = 'session-item' + (sess.id === state.activeSessionId ? ' active' : '');
      item.dataset.sessionId = sess.id;

      const header = document.createElement('div');
      header.className = 'session-item-header';

      const title = document.createElement('span');
      title.className = 'session-item-title';
      title.textContent = sess.title || 'Phiên chat';

      const meta = document.createElement('div');
      meta.className = 'session-item-meta';

      const time = document.createElement('span');
      time.className = 'session-item-time';
      time.textContent = formatSessionTime(sess.updated_at || sess.updatedAt);

      const deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'session-delete-btn';
      deleteBtn.title = 'Xóa phiên chat';
      deleteBtn.setAttribute('aria-label', 'Xóa phiên chat');
      deleteBtn.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      `;
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteSession(sess.id);
      });

      meta.appendChild(time);
      meta.appendChild(deleteBtn);
      header.appendChild(title);
      header.appendChild(meta);

      const preview = document.createElement('div');
      preview.className = 'session-item-preview';
      preview.textContent = sess.preview || 'Chưa có tin nhắn';

      item.appendChild(header);
      item.appendChild(preview);

      item.addEventListener('click', () => {
        switchSession(sess.id);
      });

      el.sessionList.appendChild(item);
    });
  }

  async function switchSession(sessionId) {
    if (state.activeSessionId === sessionId) return;
    state.activeSessionId = sessionId;
    localStorage.setItem('agent_session_id', sessionId);
    renderSessionList();
    await loadCurrentSessionMessages();
  }

  async function loadCurrentSessionMessages() {
    el.messagesList.innerHTML = '';
    resetGraph();

    if (!state.activeSessionId) {
      el.welcomeScreen.style.display = 'block';
      state.messages = [];
      return;
    }

    let messages = [];
    try {
      const res = await fetch(
        getApiEndpoint(
          `/api/sessions/${encodeURIComponent(state.activeSessionId)}/messages?user_id=${encodeURIComponent(state.userId)}`
        )
      );
      if (res.ok) {
        const data = await res.json();
        messages = Array.isArray(data.messages) ? data.messages : [];
      }
    } catch (err) {
      console.error('Lỗi khi tải lịch sử phiên:', err);
    }

    const sess = state.sessions.find(s => s.id === state.activeSessionId);
    if (sess) {
      sess.messages = messages;
    }

    if (messages.length === 0) {
      el.welcomeScreen.style.display = 'block';
      state.messages = [];
      return;
    }

    el.welcomeScreen.style.display = 'none';
    state.messages = messages;
    messages.forEach(msg => {
      appendMessage(msg.role, msg.content, msg.detail, msg.chart);
    });
    scrollToBottom();
  }

  async function createNewSession() {
    if (state.isGenerating) return;
    try {
      const res = await fetch(getApiEndpoint('/api/sessions'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: state.userId }),
      });
      if (!res.ok) throw new Error('Không thể tạo phiên chat mới');
      const newSession = await res.json();
      newSession.messages = [];
      state.sessions.unshift(newSession);
      state.activeSessionId = newSession.id;
      localStorage.setItem('agent_session_id', newSession.id);
      renderSessionList();
      await loadCurrentSessionMessages();
      el.questionInput.value = '';
      adjustTextareaHeight();
      el.questionInput.focus();
    } catch (e) {
      console.error('Lỗi createNewSession:', e);
    }
  }

  async function deleteSession(sessionId) {
    if (!sessionId) return;
    try {
      const res = await fetch(
        getApiEndpoint(`/api/sessions/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(state.userId)}`),
        { method: 'DELETE' }
      );
      if (!res.ok && res.status !== 404) {
        console.error('Lỗi khi xóa session:', res.statusText);
        return;
      }

      state.sessions = state.sessions.filter(s => s.id !== sessionId);

      if (state.activeSessionId === sessionId) {
        if (state.sessions.length > 0) {
          state.activeSessionId = state.sessions[0].id;
          localStorage.setItem('agent_session_id', state.activeSessionId);
          renderSessionList();
          await loadCurrentSessionMessages();
        } else {
          await createNewSession();
          return;
        }
      } else {
        renderSessionList();
      }
    } catch (err) {
      console.error('Lỗi deleteSession:', err);
    }
  }

  // Initialize
  async function init() {
    setupEventListeners();
    applyStateToUI();
    adjustTextareaHeight();
    checkSystemHealth();
    await initUserAndSessions();
    renderSessionList();
    await loadCurrentSessionMessages();
  }

  function setupEventListeners() {
    // Sidebar toggle
    el.btnToggleSidebar.addEventListener('click', () => {
      el.sidebar.classList.toggle('collapsed');
      el.sidebar.classList.toggle('active');
    });

    // New Chat (#btn-new-chat)
    el.btnNewChat.addEventListener('click', createNewSession);

    // Domain Chips & Suggestion Cards (data-query click -> send)
    document.addEventListener('click', (e) => {
      const item = e.target.closest('[data-query]');
      if (!item) return;
      const query = item.getAttribute('data-query');
      if (query) {
        el.questionInput.value = query;
        adjustTextareaHeight();
        handleSendMessage();
      }
    });

    // Input Handling
    el.questionInput.addEventListener('input', adjustTextareaHeight);
    el.questionInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    });

    el.btnSend.addEventListener('click', handleSendMessage);

    // Settings Modal
    el.btnOpenSettings.addEventListener('click', openSettings);
    el.btnCloseSettings.addEventListener('click', closeSettings);
    el.settingsModal.addEventListener('click', e => {
      if (e.target === el.settingsModal) closeSettings();
    });

    el.btnSaveSettings.addEventListener('click', saveSettings);
    el.btnCheckHealth.addEventListener('click', checkSystemHealthInModal);
  }

  function applyStateToUI() {
    if (state.activeModel === 'self_hosted') {
      el.sidebarModelLabel.textContent = 'Qwen3-4B (Self-hosted)';
      if (el.radioSelfHosted) el.radioSelfHosted.checked = true;
    } else {
      el.sidebarModelLabel.textContent = 'OpenAI (gpt-4o-mini)';
      if (el.radioOpenAI) el.radioOpenAI.checked = true;
    }
    el.inputApiUrl.value = state.apiBaseUrl;
  }

  function adjustTextareaHeight() {
    el.questionInput.style.height = 'auto';
    el.questionInput.style.height = Math.min(el.questionInput.scrollHeight, 160) + 'px';
  }

  // ==========================================================================
  // Graph Logic (Phase 5+)
  // ==========================================================================
  const IO_MAX_CHARS = 80000;
  let graphRunId = 0;
  let hoveredGraphNodeId = null;

  function formatIoValue(val) {
    if (val === null || val === undefined) return '(empty)';
    if (typeof val === 'string') {
      const trimmed = val.trim();
      if (
        (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
        (trimmed.startsWith('[') && trimmed.endsWith(']'))
      ) {
        try {
          return JSON.stringify(JSON.parse(trimmed), null, 2);
        } catch (e) {
          return val;
        }
      }
      return val;
    }
    if (typeof val === 'object') {
      try {
        return JSON.stringify(val, null, 2);
      } catch (e) {
        return String(val);
      }
    }
    return String(val);
  }

  function truncateIoText(text) {
    if (text.length <= IO_MAX_CHARS) return text;
    return text.slice(0, IO_MAX_CHARS) + '\n… (đã cắt — xem Langfuse để full)';
  }

  function resetGraph() {
    graphRunId += 1;
    if (state.streamAbortController) {
      state.streamAbortController.abort();
    }
    state.streamAbortController = new AbortController();
    state.streamEventsCount = 0;
    state.streamStartTime = performance.now();
    state.nodeStartTimes = {};
    state.nodeDurations = {};
    state.lastChart = null;
    state.lastChartSpec = null;
    state.lastChartType = null;
    state.lastChartRows = null;
    state.lastStreamError = null;
    state.graphNodes = {};
    if (el.graphNodes) el.graphNodes.innerHTML = '';
    if (el.graphPanelHint) {
      el.graphPanelHint.innerHTML = '<span class="graph-panel-total">⏱️ Đang chạy…</span>';
    }
    if (el.graphPlaceholder) {
      el.graphPlaceholder.classList.remove('hidden');
      el.graphPlaceholder.textContent = 'Chờ sự kiện node...';
    }
    if (el.graphIoEmpty) el.graphIoEmpty.hidden = false;
    if (el.graphIoBody) {
      el.graphIoBody.hidden = true;
      el.graphIoBody.textContent = '';
    }
  }

  function showNodeIo(nodeId) {
    const n = state.graphNodes[nodeId];
    if (!n || n.status !== 'done') return;
    document.querySelectorAll('.graph-node').forEach(node => {
      node.classList.toggle('selected', node.dataset.nodeId === nodeId);
    });
    el.graphIoEmpty.hidden = true;
    el.graphIoBody.hidden = false;
    let raw =
      'input:\n' + formatIoValue(n.input) +
      '\n\noutput:\n' + formatIoValue(n.output);
    if (n.durationMs !== undefined && n.durationMs !== null) {
      const durFormatted = n.durationMs >= 1000 ? (n.durationMs / 1000).toFixed(2) + 's' : n.durationMs + 'ms';
      raw += `\n\nthời gian thực thi (latency): ${durFormatted} (${n.durationMs}ms)`;
    }
    if (n.meta && typeof n.meta === 'object' && Object.keys(n.meta).length > 0) {
      raw += '\n\nmeta:\n' + formatIoValue(n.meta);
    }
    el.graphIoBody.textContent = truncateIoText(raw);
  }

  function upsertGraphNode(nodeId, status, input, output, meta, durationMs) {
    if (el.graphPlaceholder) el.graphPlaceholder.classList.add('hidden');
    const prev = state.graphNodes[nodeId] || {};
    
    let dur = durationMs !== undefined && durationMs !== null ? durationMs : (meta && meta.duration_ms);
    if (!state.nodeStartTimes) state.nodeStartTimes = {};
    if (!state.nodeDurations) state.nodeDurations = {};

    if (status === 'running') {
      state.nodeStartTimes[nodeId] = performance.now();
    } else if (status === 'done') {
      if ((dur === undefined || dur === null) && state.nodeStartTimes[nodeId]) {
        dur = Math.round(performance.now() - state.nodeStartTimes[nodeId]);
      }
      if (dur !== undefined && dur !== null) {
        state.nodeDurations[nodeId] = dur;
      }
    }

    const next = {
      status,
      durationMs: dur !== undefined && dur !== null ? dur : prev.durationMs,
      input: status === 'done'
        ? input
        : (input !== undefined && input !== null ? input : prev.input),
      output: status === 'done'
        ? output
        : (output !== undefined && output !== null ? output : prev.output),
      meta: status === 'done'
        ? (meta !== undefined ? meta : prev.meta)
        : (meta !== undefined && meta !== null ? meta : prev.meta),
    };
    state.graphNodes[nodeId] = next;
    let card = el.graphNodes.querySelector(`[data-node-id="${nodeId}"]`);
    if (!card) {
      card = document.createElement('button');
      card.type = 'button';
      card.className = 'graph-node';
      card.dataset.nodeId = nodeId;
      card.innerHTML =
        '<div class="graph-node-header"><span class="graph-node-id"></span><span class="graph-node-time"></span></div><div class="graph-node-status"></div>';
      card.addEventListener('click', () => showNodeIo(nodeId));
      card.addEventListener('mouseenter', () => {
        hoveredGraphNodeId = nodeId;
        showNodeIo(nodeId);
      });
      card.addEventListener('mouseleave', () => {
        if (hoveredGraphNodeId === nodeId) hoveredGraphNodeId = null;
      });
      el.graphNodes.appendChild(card);
    }
    let headerEl = card.querySelector('.graph-node-header');
    let idEl = card.querySelector('.graph-node-id');
    let timeEl = card.querySelector('.graph-node-time');
    let statusEl = card.querySelector('.graph-node-status');

    if (!headerEl) {
      headerEl = document.createElement('div');
      headerEl.className = 'graph-node-header';
      idEl = document.createElement('span');
      idEl.className = 'graph-node-id';
      timeEl = document.createElement('span');
      timeEl.className = 'graph-node-time';
      headerEl.appendChild(idEl);
      headerEl.appendChild(timeEl);
      card.insertBefore(headerEl, card.firstChild);
    } else {
      if (!idEl) {
        idEl = document.createElement('span');
        idEl.className = 'graph-node-id';
        headerEl.insertBefore(idEl, headerEl.firstChild);
      }
      if (!timeEl) {
        timeEl = document.createElement('span');
        timeEl.className = 'graph-node-time';
        headerEl.appendChild(timeEl);
      }
    }
    if (!statusEl) {
      statusEl = document.createElement('div');
      statusEl.className = 'graph-node-status';
      card.appendChild(statusEl);
    }

    idEl.textContent = nodeId;

    const curDur = next.durationMs;
    let durLabel = '';
    if (typeof curDur === 'number' && !isNaN(curDur)) {
      durLabel = curDur >= 1000 ? (curDur / 1000).toFixed(2) + 's' : (curDur >= 10 ? Math.round(curDur) : curDur.toFixed(1)) + 'ms';
    }

    if (timeEl) {
      if (status === 'running') {
        timeEl.className = 'graph-node-time running';
        timeEl.textContent = '…';
        timeEl.style.display = 'inline-block';
      } else if (durLabel) {
        timeEl.className = 'graph-node-time';
        timeEl.textContent = durLabel;
        timeEl.style.display = 'inline-block';
      } else {
        timeEl.textContent = '';
        timeEl.style.display = 'none';
      }
    }

    statusEl.textContent =
      status === 'running'
        ? 'đang chạy…'
        : (durLabel ? `xong (${durLabel}) — trỏ hoặc bấm để xem I/O` : 'xong — trỏ hoặc bấm để xem I/O');

    if (status === 'done' && (card.classList.contains('selected') || hoveredGraphNodeId === nodeId)) {
      showNodeIo(nodeId);
    }
  }


  // ==========================================================================
  // Markdown & Message Rendering
  // ==========================================================================
  function parseMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);

    // Code Blocks: ```code```
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');

    // Inline code: `code`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold: **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Tables: | col1 | col2 |
    const lines = html.split('\n');
    let inTable = false;
    let tableHtml = '';
    const processedLines = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line.startsWith('|') && line.endsWith('|')) {
        if (!inTable) {
          inTable = true;
          tableHtml = '<table>';
        }
        // Header separator line check: |---|---|
        if (/^\|(\s*[-:]+\s*\|)+$/.test(line)) {
          continue;
        }
        const cells = line.slice(1, -1).split('|');
        const tag = tableHtml === '<table>' ? 'th' : 'td';
        tableHtml += '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
      } else {
        if (inTable) {
          tableHtml += '</table>';
          processedLines.push(tableHtml);
          inTable = false;
        }
        processedLines.push(line);
      }
    }
    if (inTable) {
      tableHtml += '</table>';
      processedLines.push(tableHtml);
    }

    html = processedLines.join('\n');

    // Bullet lists: - item
    html = html.replace(/^\s*-\s+(.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // Line breaks
    html = html.replace(/\n\n+/g, '<br><br>').replace(/\n/g, '<br>');

    return html;
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // ==========================================================================
  // Chart.js rendering helper & Vietnamese localization
  // ==========================================================================

  /** Vietnamese translation map for categorical chart values */
  const CHART_VI_LABELS = {
    'CAR': 'Ô tô',
    'MOTORCYCLE': 'Xe máy',
    'MOTORBIKE': 'Xe máy',
    'TRUCK': 'Xe tải',
    'BUS': 'Xe buýt',
    'IN': 'Vào',
    'OUT': 'Ra',
    'FIRE': 'Cháy',
    'SMOKE': 'Khói',
    'HIGH': 'Cao',
    'MEDIUM': 'Trung bình',
    'LOW': 'Thấp',
    'FIGHT_DETECTION': 'Ẩu đả',
    'CROWD_DETECTION': 'Đám đông',
    'INTRUSION_DETECTION': 'Xâm nhập',
    'WATER_LEVEL_DETECTION': 'Mực nước',
    'SIDEWALK_ENCROACHMENT': 'Lấn chiếm vỉa hè',
    'TRAFFIC_JAM': 'Ùn tắc giao thông',
    'UNKNOWN': 'Không xác định',
    'OTHER': 'Khác',
  };

  /** Vietnamese translation map for common numeric columns and group-by dimensions */
  const CHART_VI_COLUMNS = {
    'count': 'Số lượng',
    'total': 'Tổng số',
    'so_luot': 'Số lượt',
    'so_luong': 'Số lượng',
    'event_count': 'Số sự kiện',
    'plate_count': 'Số lượt xe',
    'sum': 'Tổng cộng',
    'value': 'Giá trị',
    'n': 'Số lượng',
    'vehicle_type': 'Loại xe',
    'direction': 'Hướng di chuyển',
    'manufacturer': 'Hãng xe',
    'event_type': 'Loại sự kiện',
    'severity': 'Mức độ',
    'alert_level': 'Mức cảnh báo',
    'zone_name': 'Khu vực',
    'camera_name': 'Camera',
    'department_name': 'Phòng ban',
  };

  /**
   * Format categorical label to human-friendly Vietnamese.
   * @param {*} val
   * @returns {string}
   */
  function formatChartLabel(val) {
    if (val === null || val === undefined || val === '') return '(trống)';
    const str = String(val).trim();
    const upper = str.toUpperCase();
    if (CHART_VI_LABELS[upper]) {
      return CHART_VI_LABELS[upper];
    }
    if (str.length > 24) {
      return str.slice(0, 21) + '…';
    }
    return str;
  }

  /**
   * Format column header to friendly Vietnamese label.
   * @param {string} col
   * @returns {string}
   */
  function formatChartColumn(col) {
    if (!col) return 'Số lượng';
    const lower = String(col).toLowerCase().trim();
    if (CHART_VI_COLUMNS[lower]) return CHART_VI_COLUMNS[lower];
    if (lower.includes('count') || lower.includes('so_luong') || lower.includes('so_luot')) return 'Số lượng';
    return col;
  }

  /** WeakMap to track Chart.js instances keyed by canvas element */
  const _chartInstances = new WeakMap();

  /**
   * Render an interactive Chart.js bar or pie chart inside containerEl.
   * Polish bar chart: title rõ, nhãn tiếng Việt, màu sắc tương phản cao, chống méo / blank.
   * @param {HTMLElement} containerEl  - the .chart-slot element
   * @param {{ chartType: string, chartSpec: Object, rows: Array }} opts
   */
  function renderChartJs(containerEl, { chartType, chartSpec, rows }) {
    if (typeof Chart === 'undefined') return;
    if (!Array.isArray(rows) || rows.length === 0) return;
    if (!chartSpec || !chartSpec.x_column || !chartSpec.y_column) return;

    const xCol = chartSpec.x_column;
    const yCol = chartSpec.y_column;
    const rawTitle = chartSpec.title_vi || '';
    const title = rawTitle.trim() || `Biểu đồ thống kê theo ${formatChartColumn(xCol)}`;

    const labels = rows.map(r => formatChartLabel(r[xCol]));
    const values = rows.map(r => {
      const v = r[yCol];
      return (v !== undefined && v !== null && !isNaN(Number(v))) ? Number(v) : 0;
    });

    const type = (chartType === 'pie') ? 'pie' : 'bar';

    // Curated high-contrast palette: duy pine-teal (#1f5c4f) leading, with warm theme accents
    const palette = [
      '#1f5c4f', // Deep pine teal (duy pattern)
      '#c2410c', // Terracotta orange (theme warm)
      '#2563eb', // Vivid royal blue
      '#d97706', // Warm amber
      '#7c3aed', // Rich violet
      '#059669', // Emerald green
      '#dc2626', // Crimson red
      '#0891b2', // Ocean cyan
      '#4f46e5', // Deep indigo
      '#ea580c', // Bright orange
    ];
    const colors = values.map((_, i) => palette[i % palette.length]);

    // Clear previous content and wrap canvas in responsive container to prevent distortion
    containerEl.innerHTML = '';
    const wrapper = document.createElement('div');
    wrapper.className = 'chart-canvas-wrapper';

    const canvas = document.createElement('canvas');
    canvas.setAttribute('aria-label', title || 'Biểu đồ');
    canvas.setAttribute('role', 'img');
    wrapper.appendChild(canvas);
    containerEl.appendChild(wrapper);

    // Destroy existing Chart instance on this canvas if any
    if (_chartInstances.has(canvas)) {
      _chartInstances.get(canvas).destroy();
    }

    const colLabel = formatChartColumn(yCol);
    const dataset = {
      label: colLabel,
      data: values,
      backgroundColor: colors.map(c => c + 'd9'), // ~85% opacity
    };

    if (type === 'bar') {
      dataset.borderColor = colors;
      dataset.borderWidth = 1.5;
      dataset.borderRadius = 6;
      dataset.borderSkipped = false;
      dataset.maxBarThickness = 48;
    } else if (type === 'pie') {
      dataset.borderColor = '#ffffff';
      dataset.borderWidth = 2;
    }

    const totalValue = values.reduce((sum, v) => sum + (Number(v) || 0), 0);

    const config = {
      type,
      data: { labels, datasets: [dataset] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: type === 'pie',
            position: 'bottom',
            labels: {
              color: '#2a2824',
              padding: 12,
              boxWidth: 14,
              boxHeight: 14,
              font: {
                family: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
                size: 12,
              },
              generateLabels: (chart) => {
                const datasets = chart.data.datasets;
                if (!datasets.length) return [];
                const ds = datasets[0];
                const data = ds.data || [];
                const total = data.reduce((acc, v) => acc + (Number(v) || 0), 0);
                return (chart.data.labels || []).map((label, i) => {
                  const val = Number(data[i]) || 0;
                  const pct = total > 0 ? ((val / total) * 100).toFixed(1).replace(/\.0$/, '') : '0';
                  const text = `${label}: ${pct}%`;
                  const fill = Array.isArray(ds.backgroundColor) ? ds.backgroundColor[i] : ds.backgroundColor;
                  const stroke = Array.isArray(ds.borderColor) ? ds.borderColor[i] : ds.borderColor;
                  return {
                    text,
                    fillStyle: fill,
                    strokeStyle: stroke || fill,
                    lineWidth: 1,
                    hidden: !chart.getDataVisibility(i),
                    index: i,
                  };
                });
              },
            },
          },
          title: {
            display: Boolean(title),
            text: title,
            color: '#1c1b18',
            font: {
              family: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
              size: 13,
              weight: '600',
            },
            padding: { top: 4, bottom: 12 },
          },
          tooltip: {
            backgroundColor: 'rgba(28, 27, 24, 0.92)',
            titleColor: '#ffffff',
            bodyColor: '#ffffff',
            titleFont: { size: 12, weight: '600' },
            bodyFont: { size: 12 },
            padding: { top: 6, bottom: 6, left: 10, right: 10 },
            cornerRadius: 6,
            displayColors: true,
            callbacks: {
              label: (context) => {
                const val = context.parsed.y !== undefined ? context.parsed.y : context.parsed;
                const num = Number(val) || 0;
                if (type === 'pie') {
                  const pct = totalValue > 0 ? ((num / totalValue) * 100).toFixed(1).replace(/\.0$/, '') : '0';
                  return ` ${colLabel}: ${num.toLocaleString('vi-VN')} (${pct}%)`;
                }
                return ` ${colLabel}: ${num.toLocaleString('vi-VN')}`;
              },
            },
          },
        },
      },
    };

    // Specific scale configuration for bar chart: clean ticks, integer precision, beginAtZero
    if (type === 'bar') {
      const maxVal = values.length ? Math.max(...values) : 0;
      config.options.scales = {
        x: {
          grid: { display: false },
          ticks: {
            color: '#636159',
            font: { family: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", size: 11 },
            maxRotation: 35,
            minRotation: 0,
            autoSkip: true,
          },
        },
        y: {
          beginAtZero: true,
          suggestedMax: maxVal > 0 ? Math.ceil(maxVal * 1.15) : 5,
          grid: {
            color: 'rgba(229, 228, 220, 0.6)',
          },
          ticks: {
            color: '#636159',
            font: { family: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", size: 11 },
            precision: 0,
            callback: (val) => Number(val).toLocaleString('vi-VN'),
          },
        },
      };
    }

    const instance = new Chart(canvas, config);
    _chartInstances.set(canvas, instance);
  }

  function appendMessage(role, content, detail, chartPayload) {
    el.welcomeScreen.style.display = 'none';

    const item = document.createElement('div');
    item.className = `message-item ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? 'U' : 'AI';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    let hasRealMetadata = false;
    if (detail) {
      const hasToolStr = typeof detail.tool === 'string' && detail.tool.trim() !== '';
      const hasToolsArr = Array.isArray(detail.tools_used) && detail.tools_used.length > 0;
      const hasRowCount = (typeof detail.row_count === 'number' && detail.row_count > 0) || (typeof detail.rows_count === 'number' && detail.rows_count > 0);
      const hasCols = Array.isArray(detail.columns) && detail.columns.length > 0;
      hasRealMetadata = hasToolStr || hasToolsArr || hasRowCount || hasCols;
    }

    // Tool Execution Accordion if detail has real metadata
    if (hasRealMetadata) {
      const accordion = document.createElement('details');
      accordion.className = 'tool-accordion';
      
      const summary = document.createElement('summary');
      summary.className = 'tool-accordion-summary';
      
      const toolName = detail.tool || (detail.tools_used ? detail.tools_used.join(', ') : 'Database Query');
      summary.innerHTML = `
        <div class="tool-summary-left">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          <span>Công cụ đã gọi:</span>
          <span class="tool-badge">${escapeHtml(toolName)}</span>
        </div>
        <span style="font-size: 0.75rem;">Chi tiết ▼</span>
      `;

      const detailContent = document.createElement('div');
      detailContent.className = 'tool-accordion-content';
      detailContent.textContent = JSON.stringify(detail, null, 2);

      accordion.appendChild(summary);
      accordion.appendChild(detailContent);
      contentDiv.appendChild(accordion);
    }

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = parseMarkdown(content);
    contentDiv.appendChild(bubble);

    // Chart rendering in assistant messages: only render when chartPayload is present
    if (role === 'assistant' && chartPayload) {
      // Normalize chartPayload: can be string (legacy PNG base64) or object {png, spec, type, rows, empty}
      let chartObj = null;
      if (typeof chartPayload === 'object') {
        chartObj = chartPayload; // {png, spec, type, rows, empty}
      } else if (typeof chartPayload === 'string' && chartPayload.trim().length > 0) {
        chartObj = { png: chartPayload.trim() };
      }

      if (chartObj) {
        const chartSpec = chartObj.spec || null;
        const chartRows = chartObj.rows || null;
        const chartType = chartObj.type || 'bar';
        const chartPng = chartObj.png || null;

        const hasChartJsData = Boolean(
          chartSpec &&
          Array.isArray(chartRows) &&
          chartRows.length > 0 &&
          typeof Chart !== 'undefined'
        );

        const chartSlot = document.createElement('div');
        chartSlot.className = 'chart-slot';

        if (hasChartJsData) {
          // Prefer Chart.js interactive render
          renderChartJs(chartSlot, { chartType, chartSpec, rows: chartRows });
          contentDiv.appendChild(chartSlot);
        } else if (chartPng) {
          // PNG fallback
          chartSlot.innerHTML = `<img src="data:image/png;base64,${chartPng}" alt="Biểu đồ" style="max-width:100%; border-radius:8px; display:block; margin:0 auto;">`;
          contentDiv.appendChild(chartSlot);
        } else if (chartSpec || chartObj.type || (Array.isArray(chartRows) && chartRows.length === 0) || chartObj.empty) {
          // Explicit empty chart state: payload present but no renderable data (empty/missing rows, etc.)
          chartSlot.classList.add('chart-slot-empty');
          chartSlot.innerHTML = `
            <div class="chart-placeholder chart-empty-state">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              <span>Chưa có dữ liệu để hiển thị biểu đồ</span>
            </div>
          `;
          contentDiv.appendChild(chartSlot);
        }
      }
    }

    item.appendChild(avatar);
    item.appendChild(contentDiv);

    el.messagesList.appendChild(item);
    scrollToBottom();
  }

  function showThinkingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'message-item assistant';
    indicator.id = 'thinking-indicator';

    indicator.innerHTML = `
      <div class="message-avatar">AI</div>
      <div class="message-content">
        <div class="thinking-indicator">
          <span>Đang truy vấn dữ liệu camera AI...</span>
          <div class="thinking-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    `;

    el.messagesList.appendChild(indicator);
    scrollToBottom();
  }

  function removeThinkingIndicator() {
    const indicator = document.getElementById('thinking-indicator');
    if (indicator) indicator.remove();
  }

  function scrollToBottom() {
    el.chatViewport.scrollTop = el.chatViewport.scrollHeight;
  }

  // ==========================================================================
  // API Communication
  // ==========================================================================
  function getApiEndpoint(path) {
    const base = state.apiBaseUrl.replace(/\/+$/, '');
    return base ? `${base}${path}` : path;
  }

  async function handleSendMessage() {
    const question = el.questionInput.value.trim();
    if (!question || state.isGenerating) return;

    let sess = state.sessions.find(s => s.id === state.activeSessionId);
    if (!sess) {
      await createNewSession();
      sess = state.sessions[0];
    }
    if (!sess) return;

    state.isGenerating = true;
    el.btnSend.disabled = true;
    el.questionInput.value = '';
    adjustTextareaHeight();

    const now = new Date().toISOString();
    const userMsg = {
      role: 'user',
      content: question,
      timestamp: now,
    };
    if (!Array.isArray(sess.messages)) sess.messages = [];
    sess.messages.push(userMsg);
    sess.updated_at = now;
    sess.updatedAt = now;
    sess.preview = question;

    if (sess.title === 'Phiên chat mới' || sess.messages.filter(m => m.role === 'user').length === 1) {
      sess.title = question.length > 32 ? question.slice(0, 32) + '…' : question;
    }

    const sessIdx = state.sessions.findIndex(s => s.id === sess.id);
    if (sessIdx > 0) {
      state.sessions.splice(sessIdx, 1);
      state.sessions.unshift(sess);
    }
    renderSessionList();

    appendMessage('user', question);
    showThinkingIndicator();
    
    // Subscribe to SSE
    resetGraph();
    const currentRunId = graphRunId;
    const currentSessionId = sess.id;

    fetch(getApiEndpoint('/api/agent/stream'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: question,
        model_provider: state.activeModel,
        session_id: state.activeSessionId,
        user_id: state.userId,
      }),
      signal: state.streamAbortController.signal
    }).then(async (res) => {
      if (currentRunId !== graphRunId) return;

      if (!res.ok) {
        let errText = '⚠️ **Lỗi kết nối**: Không thể kết nối tới backend/API. Vui lòng kiểm tra lại hệ thống.';
        try {
          const errData = await res.json();
          if (res.status === 400 && (errData.detail || errData.reason)) {
            errText = errData.detail || errData.reason;
          } else if (errData.detail) {
            errText = errData.detail;
          }
        } catch (e) {}
        const errObj = new Error(errText);
        errObj.isCustomMsg = true;
        throw errObj;
      }
      if (!res.body) return;
      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let hasAnswer = false;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep the incomplete line in buffer
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim();
            if (!dataStr || dataStr === '[DONE]') continue;
            try {
              const event = JSON.parse(dataStr);
              if (!event.node_id || !event.status) continue;
              
              if (event.chart_png_base64) {
                state.lastChart = event.chart_png_base64;
              }

              // Dedicated __chart__ event — update chart state
              if (event.node_id === '__chart__') {
                state.lastChart = event.chart_png_base64 || state.lastChart || null;
                state.lastChartSpec = event.chart_spec || null;
                state.lastChartType = event.chart_type || null;
                state.lastChartRows = Array.isArray(event.chart_rows) ? event.chart_rows : null;
                continue;
              }

              if (event.node_id === 'error') {
                state.lastStreamError = event.output || 'Đã xảy ra lỗi.';
              }

              if (event.node_id === '__answer__') {
                if (currentRunId !== graphRunId) return;
                hasAnswer = true;
                removeThinkingIndicator();

                const isError = event.status === 'error' ||
                  (event.detail && event.detail.status === 'error');
                let answerText = event.output || 'Không có câu trả lời.';
                if (isError) {
                  state.lastStreamError = answerText;
                  if (!answerText.startsWith('⚠️')) {
                    answerText = '⚠️ ' + answerText;
                  }
                }
                // Build full chart payload object (prefer rows from detail if available)
                const detailRows = event.detail && Array.isArray(event.detail.chart_rows) ? event.detail.chart_rows : null;
                const chartPayload = (state.lastChart || state.lastChartSpec) ? {
                  png: state.lastChart || null,
                  spec: state.lastChartSpec || (event.detail && event.detail.chart_spec) || null,
                  type: state.lastChartType || (event.detail && event.detail.chart_type) || 'bar',
                  rows: detailRows || state.lastChartRows || null,
                } : null;
                state.lastChart = null;
                state.lastChartSpec = null;
                state.lastChartType = null;
                state.lastChartRows = null;

                const targetSession = state.sessions.find(item => item.id === currentSessionId);
                if (targetSession) {
                  if (!Array.isArray(targetSession.messages)) targetSession.messages = [];
                  targetSession.messages.push({
                    role: 'assistant',
                    content: answerText,
                    detail: event.detail,
                    chart: chartPayload,
                    timestamp: new Date().toISOString()
                  });
                  const now = new Date().toISOString();
                  targetSession.updated_at = now;
                  targetSession.updatedAt = now;
                  const cleanPreview = answerText.replace(/[\n\r#*`]/g, ' ').replace(/\s+/g, ' ').trim();
                  targetSession.preview = cleanPreview.length > 45 ? cleanPreview.slice(0, 45) + '…' : cleanPreview;
                  renderSessionList();
                }
                
                if (state.streamStartTime && el.graphPanelHint) {
                  const totalMs = Math.round(performance.now() - state.streamStartTime);
                  const totalStr = totalMs >= 1000 ? (totalMs / 1000).toFixed(2) + 's' : totalMs + 'ms';
                  el.graphPanelHint.innerHTML = '<span class="graph-panel-total">⏱️ Tổng: ' + totalStr + '</span>';
                }
                appendMessage('assistant', answerText, event.detail, chartPayload);
                continue;
              }

              upsertGraphNode(
                event.node_id,
                event.status,
                event.input,
                event.output,
                event.meta,
                event.duration_ms
              );
              state.streamEventsCount++;
            } catch (e) {
              console.error("Parse SSE data error", e);
            }
          }
        }

      }
      if (!hasAnswer && currentRunId === graphRunId) {
        removeThinkingIndicator();
        const fallbackText = state.lastStreamError
          ? ('⚠️ ' + state.lastStreamError)
          : '⚠️ Xin lỗi, đã xảy ra lỗi trong quá trình xử lý. Vui lòng thử lại.';
        state.lastStreamError = null;
        const targetSession = state.sessions.find(item => item.id === currentSessionId);
        if (targetSession) {
          if (!Array.isArray(targetSession.messages)) targetSession.messages = [];
          targetSession.messages.push({
            role: 'assistant',
            content: fallbackText,
            timestamp: new Date().toISOString()
          });
          const now = new Date().toISOString();
          targetSession.updated_at = now;
          targetSession.updatedAt = now;
          targetSession.preview = fallbackText;
          renderSessionList();
        }
        appendMessage('assistant', fallbackText);
      }
    }).catch(err => {
      if (currentRunId !== graphRunId || err.name === 'AbortError') return;
      
      removeThinkingIndicator();
      const placeholder = document.getElementById('graph-placeholder');
      if (placeholder) {
        placeholder.classList.remove('hidden');
        placeholder.textContent = 'Lỗi Stream SSE';
      }
      const msg = err.isCustomMsg ? err.message : '⚠️ **Lỗi kết nối**: Không thể kết nối tới backend/API. Vui lòng kiểm tra lại hệ thống.';
      const targetSession = state.sessions.find(item => item.id === currentSessionId);
      if (targetSession) {
        if (!Array.isArray(targetSession.messages)) targetSession.messages = [];
        targetSession.messages.push({
          role: 'assistant',
          content: msg,
          timestamp: new Date().toISOString()
        });
        const now = new Date().toISOString();
        targetSession.updated_at = now;
        targetSession.updatedAt = now;
        targetSession.preview = '⚠️ Lỗi kết nối';
        renderSessionList();
      }
      appendMessage(
        'assistant',
        msg
      );
    }).finally(() => {
      if (currentRunId === graphRunId) {
        state.isGenerating = false;
        el.btnSend.disabled = false;
        el.questionInput.focus();
      }
    });
  }

  async function checkSystemHealth() {
    try {
      const url = getApiEndpoint('/api/health');
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        el.systemStatusText.textContent = 'Hệ thống sẵn sàng';
        el.systemStatusBadge.querySelector('.status-dot').style.background = '#10b981';
      } else {
        throw new Error();
      }
    } catch {
      // Try /health
      try {
        const fallback = getApiEndpoint('/health');
        const res = await fetch(fallback);
        if (res.ok) {
          el.systemStatusText.textContent = 'Hệ thống sẵn sàng';
          el.systemStatusBadge.querySelector('.status-dot').style.background = '#10b981';
          return;
        }
      } catch {}
      el.systemStatusText.textContent = 'Backend Offline';
      el.systemStatusBadge.querySelector('.status-dot').style.background = '#ef4444';
    }
  }

  async function checkSystemHealthInModal() {
    const apiUrlInput = el.inputApiUrl.value.trim();
    if (apiUrlInput && !apiUrlInput.startsWith('http://') && !apiUrlInput.startsWith('https://')) {
      el.healthResult.innerHTML = `❌ <strong>Lỗi:</strong> URL phải bắt đầu bằng http:// hoặc https://`;
      el.healthResult.style.color = '#ef4444';
      return;
    }

    el.healthResult.textContent = 'Đang kiểm tra kết nối...';
    el.healthResult.style.color = 'var(--text-secondary)';

    try {
      const base = apiUrlInput.replace(/\/+$/, '');
      const path = '/api/health';
      const url = base ? `${base}${path}` : path;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        el.healthResult.innerHTML = `✅ <strong>Kết nối thành công!</strong> Model active: <code>${data.active_model || 'N/A'}</code>`;
        el.healthResult.style.color = '#10b981';
      } else {
        throw new Error();
      }
    } catch {
      el.healthResult.innerHTML = `❌ <strong>Không thể kết nối</strong> tới Backend. Hãy chắc chắn Uvicorn/FastAPI đang chạy.`;
      el.healthResult.style.color = '#ef4444';
    }
  }

  // ==========================================================================
  // Settings Management
  // ==========================================================================
  function openSettings() {
    applyStateToUI();
    el.healthResult.textContent = '';
    el.settingsModal.classList.add('active');
  }

  function closeSettings() {
    el.settingsModal.classList.remove('active');
  }

  function saveSettings() {
    const selectedProvider = el.radioSelfHosted.checked ? 'self_hosted' : 'openai';
    const apiUrl = el.inputApiUrl.value.trim();

    if (apiUrl && !apiUrl.startsWith('http://') && !apiUrl.startsWith('https://')) {
      el.healthResult.innerHTML = `❌ <strong>Lỗi:</strong> URL phải bắt đầu bằng http:// hoặc https://`;
      el.healthResult.style.color = '#ef4444';
      return;
    }

    state.activeModel = selectedProvider;
    state.apiBaseUrl = apiUrl;

    localStorage.setItem('agent_model_provider', selectedProvider);
    localStorage.setItem('agent_api_base_url', apiUrl);

    applyStateToUI();
    closeSettings();
    checkSystemHealth();
  }

  // Start app
  document.addEventListener('DOMContentLoaded', init);
})();
