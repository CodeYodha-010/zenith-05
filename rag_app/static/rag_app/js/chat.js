/* ============================================================
   Zenith Export AI — Chat JavaScript
   Regulatory Workspace Layout
   ============================================================ */

(function () {
    'use strict';

    // ---- DOM refs ----
    const textarea           = document.getElementById('question-input');
    const suggestionBox      = document.getElementById('suggestion-box');
    const questionForm       = document.getElementById('question-form');
    const sendButton         = document.getElementById('send-button');
    const fileInput          = document.getElementById('file-input');
    const chatContainer      = document.getElementById('chat-container');
    const chatMessages       = document.getElementById('chat-messages');
    const welcomeMessage     = document.getElementById('welcome-message');
    const attachedFileDisplay= document.getElementById('attached-file-display');
    const attachedFileName   = document.getElementById('attached-file-name');
    const commandRegionSelect= document.getElementById('command-region-select');
    const toolbarRegion      = document.getElementById('toolbar-region');
    const toolbarKb          = document.getElementById('toolbar-kb');
    const toolbarDoc         = document.getElementById('toolbar-doc');
    const commandStatus      = document.getElementById('command-status');

    // ---- State ----
    let selectedRegion       = 'india';
    let isLoading            = false;
    let activeSuggestionIndex = -1;
    let debounceTimer        = null;
    let attachedDocId        = null;
    let messageCounter       = 0;

    const STREAM_URL = questionForm ? questionForm.dataset.streamUrl : '/ask/stream/';

    // ============================================================
    //  UTILITIES
    // ============================================================

    function getCookie(name) {
        if (!document.cookie || !document.cookie.trim()) return null;
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                return decodeURIComponent(cookie.substring(name.length + 1));
            }
        }
        return null;
    }

    function getCsrfToken() { return getCookie('csrftoken'); }

    function extractDomain(url) {
        try { return new URL(url).hostname.replace(/^www\./, ''); }
        catch { return url; }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function scrollToBottom() {
        if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function updateToolbar() {
        const regionLabels = { india: 'India', us: 'USA', eu: 'EU', '': 'All Regions' };
        if (toolbarRegion) toolbarRegion.textContent = 'Region: ' + (regionLabels[selectedRegion] || selectedRegion);
    }

    function setCommandStatus(text) {
        if (commandStatus) commandStatus.textContent = text;
    }

    function clearCommandStatus() {
        if (commandStatus) commandStatus.textContent = '';
    }

    // ============================================================
    //  AUTO-RESIZE TEXTAREA
    // ============================================================

    if (textarea) {
        textarea.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 150) + 'px';
        });
    }

    // ============================================================
    //  SUGGESTIONS
    // ============================================================

    if (textarea && suggestionBox) {
        textarea.addEventListener('input', function () {
            const query = this.value.trim();
            if (query.length < 2) { suggestionBox.style.display = 'none'; return; }

            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(async () => {
                try {
                    const response = await fetch(`/suggestions/?q=${encodeURIComponent(query)}&limit=6`);
                    const data = await response.json();
                    if (data.success && data.suggestions.length > 0) {
                        renderSuggestions(data.suggestions, query);
                        suggestionBox.style.display = 'block';
                    } else {
                        suggestionBox.style.display = 'none';
                    }
                } catch (err) { console.error('Failed to fetch suggestions', err); }
            }, 300);
        });

        textarea.addEventListener('keydown', function (e) {
            const items = suggestionBox.querySelectorAll('.z-suggestion-item');
            if (suggestionBox.style.display === 'block') {
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    activeSuggestionIndex = (activeSuggestionIndex + 1) % items.length;
                    updateActiveSuggestion(items);
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    activeSuggestionIndex = (activeSuggestionIndex - 1 + items.length) % items.length;
                    updateActiveSuggestion(items);
                } else if (e.key === 'Enter' && activeSuggestionIndex > -1) {
                    e.preventDefault();
                    selectSuggestion(items[activeSuggestionIndex].textContent);
                } else if (e.key === 'Escape') {
                    suggestionBox.style.display = 'none';
                }
            } else if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (questionForm) questionForm.dispatchEvent(new Event('submit'));
            }
        });
    }

    function renderSuggestions(matches, query) {
        if (!suggestionBox) return;
        suggestionBox.innerHTML = '';
        activeSuggestionIndex = -1;
        const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${escapedQuery})`, 'gi');

        matches.forEach((match) => {
            const div = document.createElement('div');
            div.className = 'z-suggestion-item';
            div.innerHTML = escapeHtml(match).replace(regex, '<strong>$1</strong>');
            div.addEventListener('click', () => selectSuggestion(match));
            suggestionBox.appendChild(div);
        });
    }

    function selectSuggestion(text) {
        if (!textarea || !suggestionBox || !questionForm) return;
        textarea.value = text;
        suggestionBox.style.display = 'none';
        clearTimeout(debounceTimer);
        textarea.focus();
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
        questionForm.dispatchEvent(new Event('submit'));
    }

    function updateActiveSuggestion(items) {
        items.forEach((item, index) => {
            if (index === activeSuggestionIndex) {
                item.classList.add('z-active');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('z-active');
            }
        });
    }

    document.addEventListener('click', function (e) {
        if (suggestionBox && textarea && !textarea.contains(e.target) && !suggestionBox.contains(e.target)) {
            suggestionBox.style.display = 'none';
        }
    });

    // ============================================================
    //  REGION SELECTION
    // ============================================================

    function selectRegion(region) {
        selectedRegion = region;
        updateToolbar();
        const regionBtns = document.querySelectorAll('.z-region-tab, .z-region-pill');
        regionBtns.forEach((btn) => {
            const isTarget = btn.dataset.region === (region || 'all');
            btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
            btn.setAttribute('aria-pressed', isTarget ? 'true' : 'false');
        });
        if (commandRegionSelect) commandRegionSelect.value = region;
    }

    document.querySelectorAll('.z-region-tab, .z-region-pill').forEach((btn) => {
        btn.addEventListener('click', function () {
            const region = this.dataset.region || this.id.replace('region-', '');
            selectRegion(region);
        });
    });

    if (commandRegionSelect) {
        commandRegionSelect.addEventListener('change', function () {
            selectRegion(this.value);
        });
    }

    // ============================================================
    //  FILE UPLOAD
    // ============================================================

    if (fileInput) {
        fileInput.addEventListener('change', async function (e) {
            const file = e.target.files[0];
            if (!file) return;

            const allowedTypes = ['.pdf', '.png', '.jpg', '.jpeg'];
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (!allowedTypes.includes(ext)) {
                alert('Please upload PDF, PNG, JPG or JPEG files only.');
                this.value = '';
                return;
            }

            if (file.size > 20 * 1024 * 1024) {
                alert('File too large. Maximum size is 20MB.');
                this.value = '';
                return;
            }

            const loadingId = addLoadingMessage();
            const statusEl = document.getElementById(loadingId + '-status');
            if (statusEl) statusEl.textContent = 'Processing document...';

            try {
                const formData = new FormData();
                formData.append('file', file);
                const response = await fetch('/upload-document/', {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-CSRFToken': getCsrfToken() },
                });
                const data = await response.json();

                if (data.success) {
                    attachedDocId = data.doc_id;
                    if (attachedFileName) attachedFileName.textContent = data.filename;
                    if (attachedFileDisplay) attachedFileDisplay.style.display = 'flex';
                    if (toolbarDoc) toolbarDoc.textContent = data.filename;
                    removeLoadingMessage(loadingId);
                } else {
                    alert('Upload failed: ' + data.error);
                    removeLoadingMessage(loadingId);
                }
            } catch (err) {
                alert('Upload error: ' + err);
                removeLoadingMessage(loadingId);
            }

            this.value = '';
        });
    }

    function clearAttachedFile() {
        attachedDocId = null;
        if (attachedFileDisplay) attachedFileDisplay.style.display = 'none';
        if (toolbarDoc) toolbarDoc.textContent = 'No document attached';
    }

    window._clearAttachedFile = clearAttachedFile;

    // ============================================================
    //  FORM SUBMISSION — STREAMING
    // ============================================================

    if (questionForm) {
        questionForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            if (suggestionBox) suggestionBox.style.display = 'none';
            clearTimeout(debounceTimer);

            const question = textarea ? textarea.value.trim() : '';
            if (!question || isLoading) return;

            if (textarea) {
                textarea.value = '';
                textarea.style.height = 'auto';
            }

            isLoading = true;
            if (sendButton) sendButton.disabled = true;
            if (welcomeMessage) welcomeMessage.style.display = 'none';

            addMessage('user', question);
            const messageId = addStreamingMessage();

            try {
                const response = await fetch(STREAM_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify({ question, region: selectedRegion || null }),
                });

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';

                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            const data = JSON.parse(line);
                            handleStreamEvent(messageId, data);
                        } catch (parseErr) { console.error('Parse error:', parseErr); }
                    }
                }

                finalizeStreamingMessage(messageId);
            } catch (error) {
                updateStreamingMessage(messageId, 'error', 'Sorry, a network error occurred. Please try again.');
            }

            isLoading = false;
            if (sendButton) sendButton.disabled = false;
            clearCommandStatus();
            scrollToBottom();
        });
    }

    // ============================================================
    //  STREAMING EVENT HANDLER
    // ============================================================

    function handleStreamEvent(messageId, data) {
        const messageDiv = document.getElementById(messageId);
        if (!messageDiv) return;

        switch (data.type) {
            case 'status': {
                const statusEl = messageDiv.querySelector('.z-stream-status');
                if (statusEl) statusEl.textContent = data.text;
                setCommandStatus(data.text);
                break;
            }

            case 'sources': {
                renderKBSources(messageId, data.data);
                break;
            }

            case 'web_sources': {
                renderWebSources(messageId, data.data);
                break;
            }

            case 'answer_start': {
                const loadingEl = messageDiv.querySelector('.z-loading-animation');
                if (loadingEl) loadingEl.style.display = 'none';
                const statusEl = messageDiv.querySelector('.z-stream-status');
                if (statusEl) statusEl.style.display = 'none';
                const answerEl = messageDiv.querySelector('.z-answer-content');
                if (answerEl) answerEl.innerHTML = '';
                break;
            }

            case 'answer_chunk': {
                const contentEl = messageDiv.querySelector('.z-answer-content');
                if (contentEl) {
                    contentEl.innerHTML += escapeHtml(data.text);
                    const rawEl = messageDiv.querySelector('.z-raw-content');
                    if (rawEl) rawEl.textContent += data.text;
                    scrollToBottom();
                }
                break;
            }

            case 'thinking': {
                addThinkingContent(messageId, data.text);
                break;
            }

            case 'done': {
                const finalEl = messageDiv.querySelector('.z-answer-content');
                if (finalEl && finalEl.innerHTML) {
                    // Soft crossfade: dip opacity one frame, swap to parsed markdown, fade back in
                    finalEl.classList.add('z-content-swap');
                    finalEl.innerHTML = DOMPurify.sanitize(marked.parse(finalEl.textContent));
                    requestAnimationFrame(() => finalEl.classList.remove('z-content-swap'));
                }
                clearCommandStatus();
                break;
            }

            case 'error': {
                updateStreamingMessage(messageId, 'error', data.text);
                clearCommandStatus();
                break;
            }
        }
    }

    // ============================================================
    //  MESSAGE RENDERING — COMPLIANCE CARDS
    // ============================================================

    function addMessage(type, content, sources, usedWebFallback) {
        if (!chatMessages) return null;
        messageCounter++;
        const messageDiv = document.createElement('div');
        messageDiv.className = 'z-message';
        messageDiv.classList.add(type === 'user' ? 'z-message-user' : 'z-message-ai');
        messageDiv.setAttribute('data-message-id', messageCounter);

        if (type === 'user') {
            messageDiv.innerHTML = `
                <div class="z-message-bubble">
                    <p style="margin:0;font-size:0.9375rem;line-height:1.5;">${escapeHtml(content)}</p>
                </div>
            `;
        } else {
            const parsedContent = DOMPurify.sanitize(marked.parse(content));
            let sourcesHtml = '';
            if (sources && sources.length > 0) {
                sourcesHtml = `
                    <div class="z-sources-panel">
                        <p class="z-sources-label">Sources</p>
                        <div class="z-source-pills">
                            ${sources.map((s) => {
                                if (s.type === 'web') {
                                    const domain = extractDomain(s.url);
                                    return `
                                        <a href="${escapeHtml(s.url)}"
                                           target="_blank"
                                           rel="noopener noreferrer"
                                           class="z-source-pill z-source-pill-web"
                                           aria-label="Open web source: ${escapeHtml(domain)}"
                                           data-source-type="web"
                                           data-source-url="${escapeHtml(s.url)}"
                                           data-source-domain="${escapeHtml(domain)}">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                                                <polyline points="15 3 21 3 21 9"/>
                                                <line x1="10" y1="14" x2="21" y2="3"/>
                                            </svg>
                                            ${escapeHtml(domain)}
                                        </a>`;
                                }
                                return `
                                    <button class="z-source-pill z-source-pill-kb"
                                            aria-label="Knowledge base source: ${escapeHtml(s.document)} page ${s.page}"
                                            data-source-type="kb"
                                            data-source-document="${escapeHtml(s.document)}"
                                            data-source-page="${s.page}">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                                            <polyline points="14 2 14 8 20 8"/>
                                        </svg>
                                        ${escapeHtml(s.document)} (Page ${s.page})
                                    </button>`;
                            }).join('')}
                        </div>
                    </div>
                `;
            }

            let fallbackHtml = '';
            if (usedWebFallback) {
                fallbackHtml = `
                    <div class="z-fallback-banner" role="note" aria-label="Knowledge base expanded with live web search">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="12" y1="16" x2="12" y2="12"/>
                            <line x1="12" y1="8" x2="12.01" y2="8"/>
                        </svg>
                        Knowledge base expanded with live official web search.
                    </div>
                `;
            }

            messageDiv.innerHTML = `
                <div class="z-message-bubble">
                    <div class="z-compliance-card">
                        <div class="z-compliance-answer">
                            <div class="z-markdown-content">${parsedContent}</div>
                        </div>
                        <div class="z-compliance-actions">
                            <button type="button" class="z-compliance-action" data-action="copy" aria-label="Copy answer">Copy</button>
                            <button type="button" class="z-compliance-action" data-action="regenerate" aria-label="Regenerate answer">Regenerate</button>
                            <button type="button" class="z-compliance-action" data-action="thinking" aria-label="Toggle thinking">Thinking</button>
                        </div>
                        ${fallbackHtml}
                        ${sourcesHtml}
                    </div>
                </div>
            `;

            // Wire up action buttons
            messageDiv.querySelectorAll('[data-action="copy"]').forEach((btn) => {
                btn.addEventListener('click', () => {
                    const text = messageDiv.querySelector('.z-markdown-content')?.textContent || '';
                    navigator.clipboard.writeText(text).then(() => {
                        const original = btn.textContent;
                        btn.textContent = 'Copied!';
                        setTimeout(() => btn.textContent = original, 1500);
                    });
                });
            });

            messageDiv.querySelectorAll('[data-action="thinking"]').forEach((btn) => {
                btn.addEventListener('click', function () {
                    const container = messageDiv.querySelector('.z-thinking-container');
                    const content = messageDiv.querySelector('.z-thinking-content');
                    const chevron = this.querySelector('.z-thinking-chevron');
                    if (!container || !content) return;
                    const isExpanded = content.classList.contains('z-visible');
                    if (isExpanded) {
                        content.classList.remove('z-visible');
                        if (chevron) chevron.style.transform = 'rotate(0deg)';
                    } else {
                        content.classList.add('z-visible');
                        if (chevron) chevron.style.transform = 'rotate(90deg)';
                    }
                });
            });

            // Wire source pills
            messageDiv.querySelectorAll('[data-source-type="kb"]').forEach((btn) => {
                btn.addEventListener('click', () => {
                    const doc = btn.dataset.sourceDocument;
                    const page = btn.dataset.sourcePage;
                    if (window._openContextPanel) window._openContextPanel('source', { document: doc, page: page });
                });
            });

            messageDiv.querySelectorAll('[data-source-type="web"]').forEach((btn) => {
                btn.addEventListener('click', () => {
                    const url = btn.dataset.sourceUrl;
                    const domain = btn.dataset.sourceDomain;
                    if (window._openContextPanel) window._openContextPanel('web', { url, domain });
                });
            });
        }

        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        return messageDiv;
    }

    // ============================================================
    //  STREAMING MESSAGE
    // ============================================================

    function addStreamingMessage() {
        if (!chatMessages) return 'stream-' + Date.now();

        const messageId = 'stream-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.id = messageId;
        messageDiv.className = 'z-message z-message-ai';
        messageDiv.innerHTML = `
            <div class="z-message-bubble">
                <div class="z-loading-animation z-loading-container">
                    <div class="z-pulse-bars">
                        <div class="z-pulse-bar"></div>
                        <div class="z-pulse-bar"></div>
                        <div class="z-pulse-bar"></div>
                        <div class="z-pulse-bar"></div>
                        <div class="z-pulse-bar"></div>
                    </div>
                    <span class="z-loading-status z-stream-status">Searching Knowledge Base...</span>
                </div>
                <div class="z-sources-panel z-kb-sources-container"></div>
                <div class="z-sources-panel z-web-sources-container"></div>
                <div class="z-fallback-banner-container"></div>
                <div class="z-thinking-container" style="display:none;">
                    <button type="button" class="z-thinking-toggle" aria-expanded="false">
                        <svg class="z-thinking-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="9 18 15 12 9 6"/>
                        </svg>
                        <span>AI Thinking</span>
                    </button>
                    <div class="z-thinking-content"><div class="z-raw-content"></div></div>
                </div>
                <div class="z-markdown-content z-answer-content"></div>
            </div>
        `;

        // Wire thinking toggle
        const thinkingToggle = messageDiv.querySelector('.z-thinking-toggle');
        const thinkingContent = messageDiv.querySelector('.z-thinking-content');
        const thinkingChevron = messageDiv.querySelector('.z-thinking-chevron');
        if (thinkingToggle && thinkingContent) {
            thinkingToggle.addEventListener('click', () => {
                const isExpanded = thinkingContent.classList.contains('z-visible');
                if (isExpanded) {
                    thinkingContent.classList.remove('z-visible');
                    if (thinkingChevron) thinkingChevron.style.transform = 'rotate(0deg)';
                    thinkingToggle.setAttribute('aria-expanded', 'false');
                } else {
                    thinkingContent.classList.add('z-visible');
                    if (thinkingChevron) thinkingChevron.style.transform = 'rotate(90deg)';
                    thinkingToggle.setAttribute('aria-expanded', 'true');
                }
            });
        }

        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        return messageId;
    }

    function updateStreamingStatus(messageId, status) {
        const statusEl = document.querySelector(`#${messageId} .z-stream-status`);
        if (statusEl) statusEl.textContent = status;
    }

    function updateStreamingMessage(messageId, type, text) {
        const messageDiv = document.getElementById(messageId);
        if (!messageDiv) return;
        if (type === 'error') {
            const bubble = messageDiv.querySelector('.z-message-bubble');
            if (bubble) bubble.classList.add('z-error-bubble');
            const answerEl = messageDiv.querySelector('.z-answer-content');
            if (answerEl) answerEl.innerHTML = `<p style="margin:0;color:#fca5a5;">${escapeHtml(text)}</p>`;
            const loadingEl = messageDiv.querySelector('.z-loading-animation');
            if (loadingEl) loadingEl.style.display = 'none';
        }
    }

    function finalizeStreamingMessage(messageId) {
        const statusEl = document.querySelector(`#${messageId} .z-stream-status`);
        if (statusEl) statusEl.style.display = 'none';
    }

    // ============================================================
    //  SOURCE RENDERING
    // ============================================================

    function renderKBSources(messageId, sources) {
        const container = document.querySelector(`#${messageId} .z-kb-sources-container`);
        if (!container || !sources || sources.length === 0) return;

        let html = `<p class="z-sources-label">Knowledge Base</p><div class="z-source-pills">`;
        sources.forEach((s) => {
            html += `
                <button class="z-source-pill z-source-pill-kb"
                        aria-label="Knowledge base source: ${escapeHtml(s.document)} page ${s.page}"
                        data-source-type="kb"
                        data-source-document="${escapeHtml(s.document)}"
                        data-source-page="${s.page}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    ${escapeHtml(s.document)} (Page ${s.page})
                </button>`;
        });
        html += '</div>';
        container.innerHTML = html;

        // Wire click handlers
        container.querySelectorAll('[data-source-type="kb"]').forEach((btn) => {
            btn.addEventListener('click', () => {
                if (window._openContextPanel) window._openContextPanel('source', {
                    document: btn.dataset.sourceDocument,
                    page: btn.dataset.sourcePage,
                });
            });
        });
    }

    function renderWebSources(messageId, sources) {
        const container = document.querySelector(`#${messageId} .z-web-sources-container`);
        if (!container || !sources || sources.length === 0) return;

        let html = `<p class="z-sources-label">Official Web Sources</p><div class="z-source-pills">`;
        sources.forEach((s) => {
            const domain = extractDomain(s.url);
            html += `
                <a href="${escapeHtml(s.url)}"
                   target="_blank"
                   rel="noopener noreferrer"
                   class="z-source-pill z-source-pill-web"
                   aria-label="Open web source: ${escapeHtml(domain)}"
                   data-source-type="web"
                   data-source-url="${escapeHtml(s.url)}"
                   data-source-domain="${escapeHtml(domain)}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                        <polyline points="15 3 21 3 21 9"/>
                        <line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                    ${escapeHtml(domain)}
                </a>`;
        });
        html += '</div>';
        container.innerHTML = html;

        // Wire click handlers
        container.querySelectorAll('[data-source-type="web"]').forEach((btn) => {
            btn.addEventListener('click', () => {
                if (window._openContextPanel) window._openContextPanel('web', {
                    url: btn.dataset.sourceUrl,
                    domain: btn.dataset.sourceDomain,
                });
            });
        });
    }

    function showFallbackBanner(messageId) {
        const container = document.querySelector(`#${messageId} .z-fallback-banner-container`);
        if (!container) return;
        container.innerHTML = `
            <div class="z-fallback-banner" role="note" aria-label="Knowledge base expanded with live web search">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="16" x2="12" y2="12"/>
                    <line x1="12" y1="8" x2="12.01" y2="8"/>
                </svg>
                Knowledge base expanded with live official web search.
            </div>
        `;
    }

    // ============================================================
    //  LOADING MESSAGE
    // ============================================================

    function addLoadingMessage() {
        if (!chatMessages) return 'loading-' + Date.now();

        const loadingDiv = document.createElement('div');
        const loadingId = 'loading-' + Date.now();
        loadingDiv.id = loadingId;
        loadingDiv.className = 'z-message z-message-ai';
        loadingDiv.innerHTML = `
            <div class="z-message-bubble">
                <div class="z-loading-container">
                    <div class="z-pulse-bars">
                        <div class="z-pulse-bar"></div>
                        <div class="z-pulse-bar"></div>
                        <div class="z-pulse-bar"></div>
                        <div class="z-pulse-bar"></div>
                        <div class="z-pulse-bar"></div>
                    </div>
                    <span id="${loadingId}-status" class="z-loading-status">Searching Knowledge Base...</span>
                </div>
            </div>
        `;
        chatMessages.appendChild(loadingDiv);
        scrollToBottom();

        setTimeout(() => {
            const el = document.getElementById(loadingId + '-status');
            if (el) el.textContent = 'Analyzing trade documents...';
        }, 3000);

        setTimeout(() => {
            const el = document.getElementById(loadingId + '-status');
            if (el) el.textContent = 'Searching official web portals...';
        }, 6000);

        setTimeout(() => {
            const el = document.getElementById(loadingId + '-status');
            if (el) el.textContent = 'Generating compliance report...';
        }, 10000);

        return loadingId;
    }

    function removeLoadingMessage(loadingId) {
        const loadingDiv = document.getElementById(loadingId);
        if (loadingDiv) loadingDiv.remove();
    }

    // ============================================================
    //  THINKING CONTENT
    // ============================================================

    function addThinkingContent(messageId, thinkingText) {
        const container = document.querySelector(`#${messageId} .z-thinking-container`);
        if (!container) return;
        container.style.display = 'block';
        const rawContent = container.querySelector('.z-raw-content');
        if (rawContent) rawContent.textContent += thinkingText;
    }

    // ============================================================
    //  INITIALIZATION
    // ============================================================

    selectRegion(selectedRegion);
    if (textarea) setTimeout(() => textarea.focus(), 100);

    // Quick start buttons
    document.querySelectorAll('.z-quick-start-item').forEach((btn) => {
        btn.addEventListener('click', () => {
            const query = btn.dataset.query;
            if (query && textarea && questionForm) {
                textarea.value = query;
                textarea.style.height = 'auto';
                textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
                questionForm.dispatchEvent(new Event('submit'));
            }
        });
    });

    // Expose for sidebar.js
    window._setQuery = function (query, region) {
        if (!textarea || !questionForm) return;
        if (region) selectRegion(region);
        textarea.value = query;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
        textarea.focus();
    };

    window._showStats = function () {
        alert('Statistics feature would open a modal with KB stats.\n\nDocuments: {{ stats.total_documents }}\nPages: {{ stats.total_pages }}\nFacts: {{ stats.total_facts }}');
    };

    // ============================================================
    //  KB STAT COUNT-UP (Spec §5.5E) — welcome screen only
    //  Animates numeric [data-count] stat values in once on load.
    // ============================================================
    function runStatCountUp() {
        const els = document.querySelectorAll('.z-kb-stat-value[data-count]');
        if (!els.length) return;
        // Respect reduced motion: jump straight to the final value.
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            els.forEach((el) => { el.textContent = el.dataset.count; });
            return;
        }
        const duration = 800; // matches spec §5.5E (800ms, ease-out-expo)
        const easeOutExpo = function (t) {
            return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
        };
        els.forEach((el) => {
            const target = parseInt(el.dataset.count, 10);
            if (isNaN(target)) return;
            const start = performance.now();
            function tick(now) {
                const p = Math.min(1, (now - start) / duration);
                el.textContent = Math.round(easeOutExpo(p) * target).toLocaleString();
                if (p < 1) requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
        });
    }

    // Fonts may load after; welcome stats are in initial DOM, so run directly.
    runStatCountUp();

})();
