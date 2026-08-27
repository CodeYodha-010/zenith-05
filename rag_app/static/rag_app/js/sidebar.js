/* ============================================================
   Zenith Export AI — Sidebar JavaScript
   ============================================================ */

(function () {
    'use strict';

    // ---- State ----
    let currentRegion = 'india';
    let selectedDocId = null;

    // ---- DOM refs ----
    const docSearch    = document.getElementById('sidebar-doc-search');
    const docList      = document.getElementById('sidebar-doc-list');
    const recentList   = document.getElementById('sidebar-recent-list');
    const sidebarUploadBtn = document.getElementById('sidebar-upload-btn');
    const sidebarUploadAction = document.getElementById('sidebar-upload-action');
    const sidebarStatsAction = document.getElementById('sidebar-stats-action');

    // ---- Mock document data (replace with real API call) ----
    const documents = [
        { id: 1, title: 'DGFT Export Policy 2024-25', region: 'india', pages: 124, status: 'ok', date: '2025-01-15' },
        { id: 2, title: 'CBIC Customs Manual', region: 'india', pages: 89, status: 'ok', date: '2025-02-20' },
        { id: 3, title: 'CBP HTSUS 2025', region: 'us', pages: 340, status: 'ok', date: '2025-01-01' },
        { id: 4, title: 'EU REACH Regulation', region: 'eu', pages: 256, status: 'warn', date: '2024-11-10' },
        { id: 5, title: 'RSTEP Rate Notification 2024', region: 'india', pages: 45, status: 'ok', date: '2025-03-01' },
        { id: 6, title: 'USITC Trade Data Portal', region: 'us', pages: 120, status: 'ok', date: '2025-02-15' },
        { id: 7, title: 'EU TARIC Database', region: 'eu', pages: 180, status: 'ok', date: '2025-01-20' },
    ];

    const recentQuestions = [
        { text: 'HS code for apple export to USA', region: 'us', time: '2 min ago', webFallback: false },
        { text: 'Duty rate for mango export to UAE', region: 'india', time: '15 min ago', webFallback: true },
        { text: 'Export procedure for grapes to EU', region: 'eu', time: '1 hour ago', webFallback: false },
        { text: 'Phytosanitary certificate requirements', region: 'india', time: '3 hours ago', webFallback: false },
        { text: 'Compare duty rates for wheat India vs USA', region: '', time: 'Yesterday', webFallback: true },
    ];

    // ---- Helpers ----
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function getRegionFlag(region) {
        const flags = { india: '🇮🇳', us: '🇺🇸', eu: '🇪🇺', '': '🌐' };
        return flags[region] || '📄';
    }

    function getStatusClass(status) {
        if (status === 'ok') return 'z-doc-status--ok';
        if (status === 'warn') return 'z-doc-status--warn';
        return 'z-doc-status--err';
    }

    // ---- Render Documents ----
    function renderDocuments(filterRegion, searchQuery) {
        if (!docList) return;

        let filtered = documents;
        if (filterRegion) {
            filtered = filtered.filter((doc) => doc.region === filterRegion);
        }
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            filtered = filtered.filter((doc) => doc.title.toLowerCase().includes(q));
        }

        docList.innerHTML = filtered.map((doc) => `
            <div class="z-doc-item"
                 role="listitem"
                 data-doc-id="${doc.id}"
                 data-doc-region="${doc.region}"
                 tabindex="0"
                 aria-selected="${selectedDocId === doc.id ? 'true' : 'false'}">
                <div class="z-doc-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                </div>
                <div class="z-doc-info">
                    <div class="z-doc-title">${escapeHtml(doc.title)}</div>
                    <div class="z-doc-meta">
                        <span>${doc.pages} pages</span>
                        <span class="z-doc-region-badge">${doc.region.toUpperCase()}</span>
                    </div>
                </div>
                <div class="z-doc-status ${getStatusClass(doc.status)}" title="${doc.status === 'ok' ? 'Indexed' : doc.status === 'warn' ? 'Partial' : 'Error'}"></div>
            </div>
        `).join('');

        // Wire click handlers
        docList.querySelectorAll('.z-doc-item').forEach((item) => {
            item.addEventListener('click', () => {
                const docId = parseInt(item.dataset.docId, 10);
                const docRegion = item.dataset.docRegion;
                const doc = documents.find((d) => d.id === docId);
                selectDocument(docId, doc);
            });

            item.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    item.click();
                }
            });
        });
    }

    function selectDocument(docId, doc) {
        selectedDocId = docId;
        document.querySelectorAll('.z-doc-item').forEach((item) => {
            item.setAttribute('aria-selected', item.dataset.docId == docId ? 'true' : 'false');
        });

        if (doc && window._openContextPanel) {
            window._openContextPanel('document', {
                id: doc.id,
                title: doc.title,
                region: doc.region,
                pages: doc.pages,
                status: doc.status,
                date: doc.date,
            });
        }
    }

    // ---- Render Recent Questions ----
    function renderRecentQuestions() {
        if (!recentList) return;
        recentList.innerHTML = recentQuestions.map((q, i) => `
            <button class="z-recent-item"
                    role="listitem"
                    data-query="${escapeHtml(q.text)}"
                    data-region="${q.region}"
                    tabindex="0">
                <span class="z-recent-text">${escapeHtml(q.text)}</span>
                <span class="z-recent-meta">${q.time} ${q.webFallback ? '• web' : ''}</span>
            </button>
        `).join('');

        recentList.querySelectorAll('.z-recent-item').forEach((btn) => {
            btn.addEventListener('click', () => {
                const query = btn.dataset.query;
                const region = btn.dataset.region;
                if (window._setQuery) window._setQuery(query, region);
            });
        });
    }

    // ---- Region Tab Selection ----
    function initRegionTabs() {
        document.querySelectorAll('.z-region-tab').forEach((tab) => {
            tab.addEventListener('click', function () {
                const region = this.dataset.region;
                currentRegion = region;

                document.querySelectorAll('.z-region-tab').forEach((t) => {
                    t.setAttribute('aria-selected', t.dataset.region === region ? 'true' : 'false');
                });

                renderDocuments(region, docSearch ? docSearch.value : '');
            });
        });
    }

    // ---- Document Search ----
    function initDocSearch() {
        if (!docSearch) return;
        docSearch.addEventListener('input', () => {
            renderDocuments(currentRegion, docSearch.value);
        });
    }

    // ---- Quick Actions ----
    function initQuickActions() {
        if (sidebarUploadBtn) {
            sidebarUploadBtn.addEventListener('click', () => {
                const fileInput = document.getElementById('file-input');
                if (fileInput) fileInput.click();
            });
        }

        if (sidebarUploadAction) {
            sidebarUploadAction.addEventListener('click', () => {
                const fileInput = document.getElementById('file-input');
                if (fileInput) fileInput.click();
            });
        }

        if (sidebarStatsAction) {
            sidebarStatsAction.addEventListener('click', () => {
                window._showStats();
            });
        }
    }

    // ---- Init ----
    function init() {
        renderDocuments('india', '');
        renderRecentQuestions();
        initRegionTabs();
        initDocSearch();
        initQuickActions();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
