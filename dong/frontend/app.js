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
    el.questionInput.focus();
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

    // Tool Execution Accordion if detail is present
    if (detail && (detail.tool || detail.tools_used || detail.rows_count !== undefined)) {
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
    if (!question || state.isGenerating) return;

    state.isGenerating = true;
    el.btnSend.disabled = true;
    el.questionInput.value = '';
    adjustTextareaHeight();

    appendMessage('user', question);
    showThinkingIndicator();

    try {
      // Try /api/chat or fallback to /ask
      const url = getApiEndpoint('/api/chat');
      const payload = {
        question: question,
        model_provider: state.activeModel,
      };

      let response;
      try {
        response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } catch (err) {
        // Fallback to /ask endpoint for backward compatibility
        const fallbackUrl = getApiEndpoint('/ask');
        response = await fetch(fallbackUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: question }),
        });
      }

      removeThinkingIndicator();

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Lỗi máy chủ' }));
        appendMessage('assistant', `⚠️ **Lỗi**: ${errorData.detail || 'Không thể lấy dữ liệu từ máy chủ.'}`);
      } else {
        const data = await response.json();
        const answer = data.answer || 'Không có câu trả lời.';
        const detail = data.detail || (data.tool ? { tool: data.tool } : null);
        appendMessage('assistant', answer, detail);
      }
    } catch (error) {
      removeThinkingIndicator();
      appendMessage('assistant', `⚠️ **Lỗi kết nối**: Không thể kết nối tới Backend tại \`${getApiEndpoint('/')}\`. Vui lòng kiểm tra lại cấu hình API.`);
    } finally {
      state.isGenerating = false;
      el.btnSend.disabled = false;
      el.questionInput.focus();
    }
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
    el.healthResult.textContent = 'Đang kiểm tra kết nối...';
    el.healthResult.style.color = 'var(--text-secondary)';

    try {
      const url = getApiEndpoint('/api/health');
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        el.healthResult.innerHTML = `✅ <strong>Kết nối thành công!</strong> Model active: <code>${data.active_model || 'N/A'}</code>`;
        el.healthResult.style.color = '#10b981';
      } else {
        throw new Error();
      }
    } catch {
      el.healthResult.innerHTML = `❌ <strong>Không thể kết nối</strong> tới Backend. Hãy chắc chắn Uvicorn/Docker đang chạy trên cổng 8000.`;
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
