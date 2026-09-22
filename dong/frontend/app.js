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
  };

  // DOM Elements
  const el = {
    sidebar: document.getElementById('sidebar'),
    btnToggleSidebar: document.getElementById('btn-toggle-sidebar'),
    btnNewChat: document.getElementById('btn-new-chat'),
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
  };

  // Initialize
  function init() {
    setupEventListeners();
    applyStateToUI();
    checkSystemHealth();
    adjustTextareaHeight();
  }

  function setupEventListeners() {
    // Sidebar toggle
    el.btnToggleSidebar.addEventListener('click', () => {
      el.sidebar.classList.toggle('collapsed');
      el.sidebar.classList.toggle('active');
    });

    // New Chat
    el.btnNewChat.addEventListener('click', resetChat);

    // Quick Domain Tags & Suggestion Cards
    document.querySelectorAll('[data-query]').forEach(item => {
      item.addEventListener('click', () => {
        const query = item.getAttribute('data-query');
        if (query) {
          el.questionInput.value = query;
          adjustTextareaHeight();
          handleSendMessage();
        }
      });
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

  function resetChat() {
    state.messages = [];
    el.messagesList.innerHTML = '';
    el.welcomeScreen.style.display = 'block';
    el.questionInput.value = '';
    adjustTextareaHeight();
    resetGraph();
    el.questionInput.focus();
  }

  // ==========================================================================
  // Graph Logic (Phase 5+)
  // ==========================================================================
  const IO_MAX_CHARS = 2000;
  let graphRunId = 0;

  function truncateIoText(text) {
    if (text.length <= IO_MAX_CHARS) return text;
    return text.slice(0, IO_MAX_CHARS) + '\n… (đã cắt ~2KB)';
  }

  function resetGraph() {
    graphRunId += 1;
    if (state.streamAbortController) {
      state.streamAbortController.abort();
    }
    state.streamAbortController = new AbortController();
    state.streamEventsCount = 0;
    state.lastChart = null;
    state.graphNodes = {};
    if (el.graphNodes) el.graphNodes.innerHTML = '';
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
    const raw =
      'input:\n' + JSON.stringify(n.input ?? null, null, 2) +
      '\n\noutput:\n' + JSON.stringify(n.output ?? null, null, 2);
    el.graphIoBody.textContent = truncateIoText(raw);
  }

  function upsertGraphNode(nodeId, status, input, output) {
    if (el.graphPlaceholder) el.graphPlaceholder.classList.add('hidden');
    state.graphNodes[nodeId] = { status, input, output };
    let card = el.graphNodes.querySelector(`[data-node-id="${nodeId}"]`);
    if (!card) {
      card = document.createElement('button');
      card.type = 'button';
      card.className = 'graph-node';
      card.dataset.nodeId = nodeId;
      card.innerHTML =
        '<div class="graph-node-id"></div><div class="graph-node-status"></div>';
      card.addEventListener('click', () => showNodeIo(nodeId));
      card.addEventListener('mouseenter', () => showNodeIo(nodeId));
      el.graphNodes.appendChild(card);
    }
    card.classList.remove('running', 'done');
    card.classList.add(status);
    card.querySelector('.graph-node-id').textContent = nodeId;
    card.querySelector('.graph-node-status').textContent =
      status === 'running' ? 'đang chạy…' : 'xong — trỏ hoặc bấm để xem I/O';
      
    if (status === 'done' && card.classList.contains('selected')) {
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

  function appendMessage(role, content, detail) {
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
    if (!question) return;

    state.isGenerating = true;
    el.btnSend.disabled = true;
    el.questionInput.value = '';
    adjustTextareaHeight();

    appendMessage('user', question);
    showThinkingIndicator();
    
    // Subscribe to SSE
    resetGraph();
    const currentRunId = graphRunId;

    fetch(getApiEndpoint('/api/agent/stream'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: question, model_provider: state.activeModel }),
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
              
              if (event.node_id === '__answer__') {
                if (currentRunId !== graphRunId) return;
                hasAnswer = true;
                removeThinkingIndicator();
                
                let answerHtml = event.output || 'Không có câu trả lời.';
                if (state.lastChart) {
                  answerHtml += `\n\n<img src="data:image/png;base64,${state.lastChart}" alt="Biểu đồ" style="max-width:100%; border-radius:8px; margin-top:10px;">`;
                  state.lastChart = null;
                }
                
                appendMessage('assistant', answerHtml, event.detail);
                continue;
              }

              upsertGraphNode(event.node_id, event.status, event.input, event.output);
              state.streamEventsCount++;
            } catch (e) {
              console.error("Parse SSE data error", e);
            }
          }
        }
      }
      if (!hasAnswer && currentRunId === graphRunId) {
        removeThinkingIndicator();
        appendMessage('assistant', 'Xin lỗi, đã xảy ra lỗi trong quá trình xử lý (stream ended early).');
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
