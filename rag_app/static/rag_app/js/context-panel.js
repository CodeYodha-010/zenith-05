/* ============================================================
   Zenith Export AI — Context Panel JavaScript
   ============================================================ */

(function () {
    'use strict';

    // ---- DOM refs ----
    const contextPanel       = document.getElementById('right-context-panel');
    const contextCloseBtn    = document.getElementById('context-panel-close');
    const contextEmptyState  = document.getElementById('context-empty-state');
    const contextSourceView  = document.getElementById('context-source-view');
    const contextDocView     = document.getElementById('context-document-view');
    const contextDataView    = document.getElementById('context-data-view');
    const contextRelatedView = document.getElementById('context-related-view');
    const contextSourceDetails = document.getElementById('context-source-details');
    const contextDocDetails  = document.getElementById('context-document-details');
    const contextDataDetails = document.getElementById('context-data-details');
    const contextRelatedList = document.getElementById('context-related-list');

    let isPanelOpen = false;

    // ---- Helpers ----
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function showView(viewId) {
        [contextEmptyState, contextSourceView, contextDocView, contextDataView, contextRelatedView].forEach((view) => {
            if (view) view.style.display = 'none';
        });
        const target = document.getElementById(viewId);
        if (target) target.style.display = 'block';
    }

    function openPanel() {
        if (!contextPanel) return;
        contextPanel.setAttribute('aria-hidden', 'false');
        contextPanel.classList.add('z-context-panel--open');
        isPanelOpen = true;
    }

    function closePanel() {
        if (!contextPanel) return;
        contextPanel.setAttribute('aria-hidden', 'true');
        contextPanel.classList.remove('z-context-panel--open');
        isPanelOpen = false;
        setTimeout(() => showView('context-empty-state'), 300);
    }

    // ---- Context Panel Actions ----
    window._openContextPanel = function (type, data) {
        if (!contextPanel) return;

        switch (type) {
            case 'source':
                renderSourceDetails(data);
                showView('context-source-view');
                break;

            case 'document':
                renderDocumentDetails(data);
                showView('context-document-view');
                break;

            case 'web':
                renderWebDetails(data);
                showView('context-source-view');
                break;

            case 'structured':
                renderStructuredDetails(data);
                showView('context-data-view');
                break;

            case 'related':
                renderRelatedQueries(data);
                showView('context-related-view');
                break;

            default:
                showView('context-empty-state');
        }

        openPanel();
    };

    // ---- Render Source Details ----
    function renderSourceDetails(data) {
        if (!contextSourceDetails) return;
        if (data.type === 'web') {
            contextSourceDetails.innerHTML = `
                <div class="z-context-detail-row">
                    <span class="z-context-detail-key">Type</span>
                    <span class="z-context-detail-value">Web Source</span>
                </div>
                <div class="z-context-detail-row">
                    <span class="z-context-detail-key">Domain</span>
                    <span class="z-context-detail-value">${escapeHtml(data.domain || '')}</span>
                </div>
                <div class="z-context-detail-row">
                    <span class="z-context-detail-key">URL</span>
                    <span class="z-context-detail-value"><a href="${escapeHtml(data.url || '#')}" target="_blank" rel="noopener noreferrer" style="color:var(--z-accent);word-break:break-all;">${escapeHtml(data.url || '')}</a></span>
                </div>
            `;
        } else {
            contextSourceDetails.innerHTML = `
                <div class="z-context-detail-row">
                    <span class="z-context-detail-key">Type</span>
                    <span class="z-context-detail-value">Knowledge Base</span>
                </div>
                <div class="z-context-detail-row">
                    <span class="z-context-detail-key">Document</span>
                    <span class="z-context-detail-value">${escapeHtml(data.document || '')}</span>
                </div>
                <div class="z-context-detail-row">
                    <span class="z-context-detail-key">Page</span>
                    <span class="z-context-detail-value">${escapeHtml(data.page || '')}</span>
                </div>
                <div class="z-context-detail-row">
                    <span class="z-context-detail-key">Relevance</span>
                    <span class="z-context-detail-value">High</span>
                </div>
            `;
        }
    }

    // ---- Render Document Details ----
    function renderDocumentDetails(data) {
        if (!contextDocDetails) return;
        const regionLabels = { india: '🇮🇳 India', us: '🇺🇸 USA', eu: '🇪🇺 EU' };
        contextDocDetails.innerHTML = `
            <div class="z-context-detail-row">
                <span class="z-context-detail-key">Title</span>
                <span class="z-context-detail-value">${escapeHtml(data.title || '')}</span>
            </div>
            <div class="z-context-detail-row">
                <span class="z-context-detail-key">Region</span>
                <span class="z-context-detail-value">${regionLabels[data.region] || data.region || ''}</span>
            </div>
            <div class="z-context-detail-row">
                <span class="z-context-detail-key">Pages</span>
                <span class="z-context-detail-value">${data.pages || ''}</span>
            </div>
            <div class="z-context-detail-row">
                <span class="z-context-detail-key">Status</span>
                <span class="z-context-detail-value" style="color:${data.status === 'ok' ? 'var(--z-teal)' : data.status === 'warn' ? 'var(--z-amber)' : 'var(--z-error)'}">${data.status || ''}</span>
            </div>
            <div class="z-context-detail-row">
                <span class="z-context-detail-key">Indexed</span>
                <span class="z-context-detail-value">${escapeHtml(data.date || '')}</span>
            </div>
            <p style="font-size:0.75rem;color:var(--z-text-muted);margin-top:0.75rem;line-height:1.5;">
                Document preview would appear here with the first 500 characters of content, highlighting matching terms from the current query.
            </p>
        `;
    }

    // ---- Render Web Details ----
    function renderWebDetails(data) {
        renderSourceDetails(data);
    }

    // ---- Render Structured Details ----
    function renderStructuredDetails(data) {
        if (!contextDataDetails) return;
        contextDataDetails.innerHTML = `
            <div class="z-context-detail-row">
                <span class="z-context-detail-key">Type</span>
                <span class="z-context-detail-value">${escapeHtml(data.dataType || 'Structured Data')}</span>
            </div>
            <div class="z-context-detail-row">
                <span class="z-context-detail-key">Value</span>
                <span class="z-context-detail-value" style="font-family:'JetBrains Mono',monospace;color:var(--z-accent);">${escapeHtml(data.value || '')}</span>
            </div>
            ${data.condition ? `
            <div class="z-context-detail-row">
                <span class="z-context-detail-key">Condition</span>
                <span class="z-context-detail-value">${escapeHtml(data.condition)}</span>
            </div>
            ` : ''}
            <p style="font-size:0.75rem;color:var(--z-text-muted);margin-top:0.75rem;line-height:1.5;">
                Additional context, related HS codes, and applicable regulations would appear here.
            </p>
        `;
    }

    // ---- Render Related Queries ----
    function renderRelatedQueries(queries) {
        if (!contextRelatedList || !queries) return;
        contextRelatedList.innerHTML = queries.map((q) => `
            <button class="z-related-item" data-query="${escapeHtml(q)}">
                ${escapeHtml(q)}
            </button>
        `).join('');

        contextRelatedList.querySelectorAll('.z-related-item').forEach((btn) => {
            btn.addEventListener('click', () => {
                const query = btn.dataset.query;
                if (window._setQuery) window._setQuery(query);
                closePanel();
            });
        });
    }

    // ---- Close Button ----
    if (contextCloseBtn) {
        contextCloseBtn.addEventListener('click', closePanel);
    }

    // ---- Keyboard: Escape to close ----
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && isPanelOpen) {
            closePanel();
        }
    });

    // ---- Init ----
    showView('context-empty-state');

})();
