// ═══════════════════════════════════════════════════════════════════════════
// MULTILINGUAL TEXT RETRIEVER — DSA ENGINEERING CONSOLE (app.js)
// Classical Data Structures & Algorithms Client Engine
// ═══════════════════════════════════════════════════════════════════════════

const LANG_CONFIG = {
    hi: { code: 'HI', name: 'Hindi', script: 'Devanagari', color: '#f59e0b' },
    bn: { code: 'BN', name: 'Bengali', script: 'Bengali', color: '#a855f7' },
    te: { code: 'TE', name: 'Telugu', script: 'Telugu', color: '#10b981' },
    mr: { code: 'MR', name: 'Marathi', script: 'Devanagari', color: '#ea580c' },
    ta: { code: 'TA', name: 'Tamil', script: 'Tamil', color: '#14b8a6' },
    ur: { code: 'UR', name: 'Urdu', script: 'Arabic-Persian', color: '#9333ea' },
    gu: { code: 'GU', name: 'Gujarati', script: 'Gujarati', color: '#16a34a' },
    kn: { code: 'KN', name: 'Kannada', script: 'Kannada', color: '#2563eb' },
    ml: { code: 'ML', name: 'Malayalam', script: 'Malayalam', color: '#dc2626' },
    or: { code: 'OR', name: 'Odia', script: 'Odia', color: '#d97706' },
    pa: { code: 'PA', name: 'Punjabi', script: 'Gurmukhi', color: '#1d4ed8' },
    as: { code: 'AS', name: 'Assamese', script: 'Bengali-Assamese', color: '#6366f1' },
    sa: { code: 'SA', name: 'Sanskrit', script: 'Devanagari', color: '#db2777' },
    en: { code: 'EN', name: 'English', script: 'Latin', color: '#0ea5e9' },
    es: { code: 'ES', name: 'Spanish', script: 'Latin', color: '#f43f5e' },
    fr: { code: 'FR', name: 'French', script: 'Latin', color: '#3b82f6' },
    de: { code: 'DE', name: 'German', script: 'Latin', color: '#8b5cf6' },
    pt: { code: 'PT', name: 'Portuguese', script: 'Latin', color: '#22c55e' },
    ar: { code: 'AR', name: 'Arabic', script: 'Arabic', color: '#06b6d4' },
    zh: { code: 'ZH', name: 'Chinese', script: 'Hanzi (CJK)', color: '#ef4444' }
};

let currentSearchResults = [];
let allCorpusDocs = [];
let clusterHeadsList = [];

// ── DOM Init ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    fetchGlobalStats();
    loadGraphClusterHeads();
    loadCorpusData();

    // Hotkey for main tabs
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        if (e.key === '1') switchMainTab('searchTab');
        if (e.key === '2') switchMainTab('labTab');
        if (e.key === '3') switchMainTab('benchmarkTab');
        if (e.key === '4') switchMainTab('corpusTab');
    });

    // Enter key on search
    document.getElementById('searchInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    // Initialize lab default values
    runTrieExplorer();
    runDPExplorer();
});

// ── Global Stats Telemetry ────────────────────────────────────────────────
async function fetchGlobalStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        if (data.status === 'online') {
            document.getElementById('metricDocs').textContent = data.index.total_docs;
            document.getElementById('metricVocab').textContent = data.index.vocab_size.toLocaleString();
            document.getElementById('metricPostings').textContent = data.index.total_postings.toLocaleString();
            document.getElementById('metricTrie').textContent = data.index.trie_stats.total_nodes.toLocaleString();
            document.getElementById('metricEdges').textContent = data.graph.total_edges.toLocaleString();
            
            const hitRate = data.cache.hit_rate_pct || 0;
            document.getElementById('metricCache').textContent = `${data.cache.size}/${data.cache.capacity} (${hitRate}%)`;
        }
    } catch (err) {
        console.warn('Telemetry polling error:', err);
    }
}

// ── Main Tab Switching ────────────────────────────────────────────────────
function switchMainTab(tabId) {
    document.querySelectorAll('.nav-tab').forEach((b, i) => {
        b.classList.remove('active');
        const ids = ['searchTab', 'labTab', 'benchmarkTab', 'corpusTab'];
        if (ids[i] === tabId) b.classList.add('active');
    });
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    const target = document.getElementById(tabId);
    if (target) target.classList.add('active');

    // Auto-actions when switching tabs
    if (tabId === 'corpusTab') loadCorpusData();
    if (tabId === 'labTab') {
        const activeSub = document.querySelector('.lab-pill.active');
        if (!activeSub) switchLabSubtab('labTrie');
    }
}

// ── Search & Pipeline Trace ───────────────────────────────────────────────
function clearSearch() {
    document.getElementById('searchInput').value = '';
    document.getElementById('searchInput').focus();
    document.getElementById('pipelineInspector').style.display = 'none';
    document.getElementById('resultsHeader').style.display = 'none';
    document.getElementById('resultsContainer').innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">⚡</div>
            <h3>Search Cleared</h3>
            <p>Enter a query above or click any query preset to trace execution.</p>
        </div>
    `;
}

function applyPreset(query, lang) {
    document.getElementById('searchInput').value = query;
    document.getElementById('langFilter').value = lang;
    switchMainTab('searchTab');
    performSearch();
}

async function performSearch(isBrowse = false) {
    let query = document.getElementById('searchInput').value.trim();
    if (isBrowse) {
        query = '';
        document.getElementById('searchInput').value = '';
    } else if (!query) {
        showToast('Please enter a query term or select Browse All.', 'warning');
        return;
    }

    const lang = document.getElementById('langFilter').value;
    const limit = document.getElementById('limitFilter').value;
    const useFuzzy = document.getElementById('toggleFuzzy').checked;
    const useSynonyms = document.getElementById('toggleSynonyms').checked;

    const resultsContainer = document.getElementById('resultsContainer');
    const pipelineInspector = document.getElementById('pipelineInspector');
    const resultsHeader = document.getElementById('resultsHeader');
    const resultsCount = document.getElementById('resultsCount');
    const traceLatency = document.getElementById('traceLatency');
    const spellBanner = document.getElementById('spellCorrectionBanner');

    resultsContainer.innerHTML = '<div class="loading-state"><span class="spinner"></span> Executing search across classical DSA pipeline...</div>';

    try {
        const url = `/search?q=${encodeURIComponent(query)}&lang=${encodeURIComponent(lang)}&limit=${limit}&fuzzy=${useFuzzy}&synonyms=${useSynonyms}`;
        const res = await fetch(url);
        const data = await res.json();

        currentSearchResults = data.results || [];
        traceLatency.textContent = `⏱ ${data.latency} ms total`;

        // Render Pipeline Stages
        if (data.execution_trace && data.execution_trace.stages && data.execution_trace.stages.length > 0) {
            pipelineInspector.style.display = 'block';
            renderPipelineTrace(data.execution_trace);
        } else {
            pipelineInspector.style.display = 'none';
        }

        // Spell Correction Banner
        if (data.corrected_query) {
            spellBanner.style.display = 'flex';
            spellBanner.innerHTML = `
                <div class="spell-text">
                    <span class="spell-icon">💡</span>
                    <span>Did you mean: <strong>${escapeHtml(data.corrected_query)}</strong>? (Resolved via 2D Levenshtein Dynamic Programming)</span>
                </div>
                <div class="spell-actions">
                    <button class="btn-micro" onclick="applyPreset('${escapeJs(data.corrected_query)}', '${lang}')">Search Corrected</button>
                    <button class="btn-micro" onclick="openDPInspectorWithTypo('${escapeJs(query)}', '${escapeJs(data.corrected_query)}')">Inspect DP Matrix</button>
                </div>
            `;
        } else {
            spellBanner.style.display = 'none';
        }

        // Render Results List
        resultsHeader.style.display = 'flex';
        resultsCount.textContent = data.results.length;

        if (data.results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <h3>No Documents Found</h3>
                    <p>No documents matched the criteria. Try selecting "All Languages" or enabling DP Levenshtein fuzzy matching.</p>
                </div>
            `;
            return;
        }

        resultsContainer.innerHTML = data.results.map(r => renderResultCard(r)).join('');

    } catch (err) {
        console.error('Search error:', err);
        resultsContainer.innerHTML = `<div class="error-state">Failed to execute search. Check console logs.</div>`;
    }
}

function renderPipelineTrace(trace) {
    const grid = document.getElementById('pipelineStagesGrid');
    grid.innerHTML = trace.stages.map(st => `
        <div class="stage-card">
            <div class="stage-header">
                <div class="stage-number">${st.id}</div>
                <div class="stage-meta">
                    <div class="stage-name">${st.name}</div>
                    <div class="stage-dsa">${st.dsa}</div>
                </div>
                <div class="stage-time">${st.latency_ms} ms</div>
            </div>
            <div class="stage-body">
                <div class="stage-complexity">COMPLEXITY: <code>${st.complexity}</code></div>
                <div class="stage-details">${escapeHtml(st.details)}</div>
            </div>
        </div>
    `).join('');
}

function togglePipelineDetails() {
    const grid = document.getElementById('pipelineStagesGrid');
    const label = document.getElementById('pipelineToggleLabel');
    if (grid.style.display === 'none') {
        grid.style.display = 'grid';
        label.textContent = 'Collapse Stages ▲';
    } else {
        grid.style.display = 'none';
        label.textContent = 'Expand Stages ▼';
    }
}

function renderResultCard(r) {
    const langInfo = LANG_CONFIG[r.lang.toLowerCase()] || { code: r.lang.toUpperCase(), name: r.lang, script: 'Script', color: '#64748b' };
    const scoreVal = (r.score !== 'N/A' && r.score !== undefined) ? r.score : null;
    const relPercent = r.relative_score_pct || (scoreVal ? 100 : 0);

    const breakdownJson = JSON.stringify(r.breakdown || []).replace(/"/g, '&quot;');

    return `
        <article class="result-card" id="doc-${r.id}">
            <div class="card-sidebar">
                <span class="lang-badge" style="background-color: ${langInfo.color}">${langInfo.code}</span>
                <span class="script-badge">${langInfo.script}</span>
                <span class="doc-id-pill">#${r.id}</span>
            </div>

            <div class="card-main">
                <div class="card-top-row">
                    <h3 class="card-title">${r.title}</h3>
                    <div class="score-display">
                        <div class="score-meter-wrap" title="Relevance: ${relPercent}%">
                            <div class="score-meter-bar" style="width: ${relPercent}%"></div>
                        </div>
                        <span class="score-text">${scoreVal ? `Score: <strong>${scoreVal}</strong>` : 'Unranked'}</span>
                    </div>
                </div>

                <p class="card-snippet">${r.snippet}</p>

                <div class="card-footer-toolbar">
                    <div class="doc-meta-info">
                        <span>Tokens: <strong>${r.doc_length || '—'}</strong></span>
                        <span>•</span>
                        <span>Language: <strong>${langInfo.name}</strong></span>
                    </div>

                    <div class="card-actions">
                        ${scoreVal ? `
                            <button class="btn-card-action" onclick="openExplainScoreModal('${r.id}', '${escapeJs(r.title)}', ${breakdownJson})">
                                🔬 Explain Score
                            </button>
                        ` : ''}
                        <button class="btn-card-action" onclick="openDefineModalForTitle('${escapeJs(r.title)}', '${r.lang}')">
                            📖 Define
                        </button>
                        <button class="btn-card-action" onclick="inspectDocPostings('${r.id}')">
                            📑 Postings
                        </button>
                        <button class="btn-card-delete" onclick="deleteDoc('${r.id}')" title="Delete document from index">
                            ✕
                        </button>
                    </div>
                </div>
            </div>
        </article>
    `;
}

// ── Tab 2: Interactive DSA Laboratory ─────────────────────────────────────
function switchLabSubtab(subId) {
    document.querySelectorAll('.lab-pill').forEach((p, idx) => {
        p.classList.remove('active');
        const ids = ['labTrie', 'labDP', 'labGraph', 'labIndex'];
        if (ids[idx] === subId) p.classList.add('active');
    });
    document.querySelectorAll('.lab-panel').forEach(pan => pan.classList.remove('active'));
    const target = document.getElementById(subId);
    if (target) target.classList.add('active');

    if (subId === 'labTrie') runTrieExplorer();
    if (subId === 'labDP') runDPExplorer();
    if (subId === 'labGraph') runGraphExplorer();
    if (subId === 'labIndex') runIndexInspector();
}

// 1. TRIE EXPLORER
function setTriePrefix(pref) {
    document.getElementById('triePrefixInput').value = pref;
    runTrieExplorer();
}

async function runTrieExplorer() {
    const prefix = document.getElementById('triePrefixInput').value.trim();
    const countEl = document.getElementById('trieMatchCount');
    const nodesEl = document.getElementById('trieNodesVisited');
    const latencyEl = document.getElementById('trieLatency');
    const wordsContainer = document.getElementById('trieWordsContainer');
    const treeRenderer = document.getElementById('trieTreeRenderer');
    const countLabel = document.getElementById('trieTermsCountLabel');

    if (!prefix) {
        countEl.textContent = '0';
        nodesEl.textContent = '0';
        latencyEl.textContent = '0.00 ms';
        countLabel.textContent = '0';
        wordsContainer.innerHTML = '<div class="empty-note">Enter a prefix above to explore Trie vocabulary.</div>';
        treeRenderer.innerHTML = '<div class="empty-note">No active subtree.</div>';
        return;
    }

    try {
        const res = await fetch(`/api/trie/prefix?prefix=${encodeURIComponent(prefix)}`);
        const data = await res.json();

        countEl.textContent = data.count;
        nodesEl.textContent = data.nodes_visited;
        latencyEl.textContent = `${data.latency_ms} ms`;
        countLabel.textContent = data.count;

        if (data.matches.length === 0) {
            wordsContainer.innerHTML = '<div class="empty-note">No vocabulary terms starting with this prefix.</div>';
        } else {
            wordsContainer.innerHTML = data.matches.map(w => `
                <div class="trie-word-chip" onclick="searchWordFromTrie('${escapeJs(w)}')">
                    <span class="chip-match-prefix">${escapeHtml(prefix)}</span><span>${escapeHtml(w.slice(prefix.length))}</span>
                    <span class="chip-word-len">${w.length}</span>
                </div>
            `).join('');
        }

        // Render Visual Subtree
        if (data.tree) {
            treeRenderer.innerHTML = renderTrieTreeVisual(data.tree);
        } else {
            treeRenderer.innerHTML = '<div class="empty-note">No subtree nodes found.</div>';
        }

    } catch (err) {
        console.error('Trie explore error:', err);
    }
}

function renderTrieTreeVisual(node, level = 0) {
    if (!node) return '';
    let childrenHtml = '';
    if (node.children && node.children.length > 0) {
        childrenHtml = `<div class="trie-children-row">${node.children.map(ch => renderTrieTreeVisual(ch, level + 1)).join('')}</div>`;
    }
    const endBadge = node.is_end ? `<span class="trie-end-marker" title="End of valid word">●</span>` : '';
    const moreBadge = node.truncated ? `<div class="trie-more-pill">+${node.truncated} more</div>` : '';

    return `
        <div class="trie-node-wrapper">
            <div class="trie-node ${node.is_end ? 'is-terminal' : ''}">
                <span class="trie-char">${escapeHtml(node.char)}</span>
                ${endBadge}
            </div>
            ${childrenHtml}
            ${moreBadge}
        </div>
    `;
}

function searchWordFromTrie(word) {
    document.getElementById('searchInput').value = word;
    switchMainTab('searchTab');
    performSearch();
}

// 2. LEVENSHTEIN DP MATRIX
function setDPWords(w1, w2) {
    document.getElementById('dpWord1').value = w1;
    document.getElementById('dpWord2').value = w2;
    runDPExplorer();
}

function openDPInspectorWithTypo(w1, w2) {
    switchMainTab('labTab');
    switchLabSubtab('labDP');
    setDPWords(w1, w2);
}

async function runDPExplorer() {
    const w1 = document.getElementById('dpWord1').value.trim();
    const w2 = document.getElementById('dpWord2').value.trim();
    const distEl = document.getElementById('dpDistance');
    const sizeEl = document.getElementById('dpMatrixSize');
    const stepEl = document.getElementById('dpStepCount');
    const badgeEl = document.getElementById('dpStatusBadge');
    const tableContainer = document.getElementById('dpTableContainer');
    const opsContainer = document.getElementById('dpOperationsContainer');

    if (!w1 || !w2) return;

    try {
        const res = await fetch(`/api/dp/matrix?w1=${encodeURIComponent(w1)}&w2=${encodeURIComponent(w2)}`);
        const data = await res.json();

        distEl.textContent = data.distance;
        sizeEl.textContent = `${w1.length + 1} × ${w2.length + 1}`;
        stepEl.textContent = data.operations.length;

        if (data.distance <= 2) {
            badgeEl.innerHTML = `<span class="badge-success">Within Max Feasible Dist (≤ 2)</span>`;
        } else {
            badgeEl.innerHTML = `<span class="badge-danger">Exceeds Max Dist (> 2)</span>`;
        }

        // Render Table
        tableContainer.innerHTML = renderDPMatrixTable(data);

        // Render Operations Sequence
        opsContainer.innerHTML = data.operations.map((op, i) => {
            let opBadgeClass = 'op-match';
            let opSymbol = '✓';
            if (op.op === 'insert') { opBadgeClass = 'op-insert'; opSymbol = '+'; }
            else if (op.op === 'delete') { opBadgeClass = 'op-delete'; opSymbol = '−'; }
            else if (op.op === 'substitute') { opBadgeClass = 'op-sub'; opSymbol = '⟳'; }

            return `
                <div class="dp-op-item ${opBadgeClass}">
                    <span class="op-step-num">#${i + 1}</span>
                    <span class="op-symbol">${opSymbol}</span>
                    <div class="op-desc">
                        <strong>${op.op.toUpperCase()}</strong>:
                        ${op.char1 ? `<code>'${op.char1}'</code>` : 'ε'} ➔ ${op.char2 ? `<code>'${op.char2}'</code>` : 'ε'}
                        <span class="op-cost-tag">cost: ${op.cost}</span>
                    </div>
                </div>
            `;
        }).join('');

    } catch (err) {
        console.error('DP matrix error:', err);
    }
}

function renderDPMatrixTable(data) {
    const { word1_chars, word2_chars, matrix, path } = data;
    const pathSet = new Set(path.map(p => `${p[0]},${p[1]}`));

    let html = '<table class="dp-matrix-table"><thead><tr><th></th><th>ε</th>';
    word2_chars.forEach(c => { html += `<th>${escapeHtml(c)}</th>`; });
    html += '</tr></thead><tbody>';

    for (let i = 0; i < matrix.length; i++) {
        const rowHeader = (i === 0) ? 'ε' : escapeHtml(word1_chars[i - 1]);
        html += `<tr><th class="row-header">${rowHeader}</th>`;
        for (let j = 0; j < matrix[i].length; j++) {
            const isPath = pathSet.has(`${i},${j}`);
            const cellClass = isPath ? 'dp-cell is-path' : 'dp-cell';
            html += `<td class="${cellClass}" title="DP[${i}][${j}] = ${matrix[i][j]}">${matrix[i][j]}</td>`;
        }
        html += '</tr>';
    }
    html += '</tbody></table>';
    return html;
}

// 3. SYNONYM GRAPH BFS EXPLORER
async function loadGraphClusterHeads() {
    try {
        const res = await fetch('/api/graph/clusters');
        const data = await res.json();
        clusterHeadsList = data.clusters || [];
        const select = document.getElementById('graphClusterSelect');
        select.innerHTML = clusterHeadsList.map(c => `
            <option value="${c}">${c.toUpperCase()} Cluster</option>
        `).join('');
    } catch (err) {
        console.warn('Could not load clusters:', err);
    }
}

function runGraphExplorer() {
    const select = document.getElementById('graphClusterSelect');
    const word = select.value || 'chocolate';
    executeGraphClusterQuery(word);
}

function runGraphExplorerCustom() {
    const custom = document.getElementById('graphCustomInput').value.trim();
    if (!custom) return;
    executeGraphClusterQuery(custom);
}

async function executeGraphClusterQuery(word) {
    try {
        const res = await fetch(`/api/graph/cluster?word=${encodeURIComponent(word)}`);
        const data = await res.json();

        document.getElementById('graphSeedNode').textContent = word;
        document.getElementById('graphClusterSize').textContent = data.found ? (data.synonyms.length + 1) : 0;

        const nodesContainer = document.getElementById('graphNodesContainer');
        const stepsContainer = document.getElementById('graphBFSStepsContainer');

        if (!data.found || data.synonyms.length === 0) {
            nodesContainer.innerHTML = '<div class="empty-note">No synonym cluster registered for this term.</div>';
            stepsContainer.innerHTML = '<div class="empty-note">BFS exploration queue empty.</div>';
            return;
        }

        // Render Multilingual cluster terms
        const allClusterWords = [data.seed, ...data.synonyms];
        nodesContainer.innerHTML = allClusterWords.map(w => `
            <div class="graph-node-chip ${w === data.seed ? 'is-seed' : ''}">
                <div class="node-word">${escapeHtml(w)}</div>
                ${w === data.seed ? '<span class="seed-indicator">SEED NODE</span>' : ''}
            </div>
        `).join('');

        // Render BFS Step Logs
        stepsContainer.innerHTML = data.steps.map(st => `
            <div class="bfs-step-card">
                <div class="bfs-step-top">
                    <span class="bfs-step-badge">Step #${st.step}</span>
                    <span class="bfs-dequeued">Dequeued: <code>${escapeHtml(st.popped)}</code></span>
                    <span class="bfs-visited-count">Visited Total: ${st.visited_total}</span>
                </div>
                <div class="bfs-step-details">
                    <div>Discovered Neighbors (${st.discovered.length}): ${st.discovered.length ? st.discovered.map(d => `<span class="bfs-neighbor-pill">${escapeHtml(d)}</span>`).join('') : '<em style="color:#64748b;">none new</em>'}</div>
                </div>
            </div>
        `).join('');

    } catch (err) {
        console.error('Graph cluster error:', err);
    }
}

// 4. INVERTED INDEX POSTINGS INSPECTOR
function setIndexTerm(term) {
    document.getElementById('indexTermInput').value = term;
    runIndexInspector();
}

function inspectDocPostings(docId) {
    const card = document.getElementById(`doc-${docId}`);
    if (!card) return;
    const title = card.querySelector('.card-title').textContent;
    const firstWord = title.trim().split(/\s+/)[0].replace(/[^a-zA-Z\u0900-\u0D7F]/g, '').toLowerCase();
    switchMainTab('labTab');
    switchLabSubtab('labIndex');
    setIndexTerm(firstWord || 'chocolate');
}

async function runIndexInspector() {
    const term = document.getElementById('indexTermInput').value.trim();
    if (!term) return;

    try {
        const res = await fetch(`/api/index/term/${encodeURIComponent(term)}`);
        const data = await res.json();

        document.getElementById('idxTermName').textContent = data.term;
        document.getElementById('idxDocFreq').textContent = data.found ? data.doc_freq : 0;
        
        // Calculate IDF dynamically: ln(109 / (1 + df)) + 1
        const totalDocs = parseInt(document.getElementById('metricDocs').textContent) || 109;
        const idfVal = data.found ? (Math.log(totalDocs / (1 + data.doc_freq)) + 1).toFixed(4) : '0.0000';
        document.getElementById('idxIDFVal').textContent = idfVal;
        document.getElementById('idxPostingsCount').textContent = data.found ? data.postings.length : 0;

        const tableContainer = document.getElementById('postingsTableContainer');
        if (!data.found || data.postings.length === 0) {
            tableContainer.innerHTML = '<div class="empty-note">Term does not exist in Inverted Index dictionary.</div>';
            return;
        }

        tableContainer.innerHTML = `
            <table class="postings-table">
                <thead>
                    <tr>
                        <th style="width:70px;">Doc ID</th>
                        <th style="width:70px;">Lang</th>
                        <th style="width:90px;">Term Freq (tf)</th>
                        <th>Document Title</th>
                        <th>Content Snippet</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.postings.map(p => `
                        <tr>
                            <td><strong style="color:var(--accent);">#${p.doc_id}</strong></td>
                            <td><span class="lang-pill-mini">${p.lang.toUpperCase()}</span></td>
                            <td><span class="tf-badge">${p.tf}</span></td>
                            <td><strong>${escapeHtml(p.title)}</strong></td>
                            <td class="snippet-cell">${escapeHtml(p.snippet)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

    } catch (err) {
        console.error('Inverted index inspect error:', err);
    }
}

// ── Tab 3: Performance Benchmarks ─────────────────────────────────────────
async function runBenchmarkSuite() {
    const btnText = document.getElementById('benchRunBtnText');
    const container = document.getElementById('benchContainer');

    btnText.textContent = '⏳ Executing Benchmarks across Corpus...';
    container.innerHTML = '<div class="loading-state"><span class="spinner"></span> Benchmarking Index Build scaling (20, 200, 2,000 docs) & Query Scans...</div>';

    try {
        const res = await fetch('/api/run_benchmark');
        const data = await res.json();

        btnText.textContent = '▶ Re-Run Benchmark Suite';

        const speedup = (data.naive_latency_ms / (data.indexed_latency_ms || 0.001)).toFixed(1);

        container.innerHTML = `
            <!-- 1. Index Scaling -->
            <div class="bench-card">
                <div class="bench-card-header">
                    <h3>1. Index Build Time Scaling \(O(N)\)</h3>
                    <span class="bench-badge">Corpus Size Scaling</span>
                </div>
                <p class="bench-desc">Time required to construct the Inverted Index and populate Trie prefix vocabulary as document count scales 100-fold.</p>
                <div class="bench-chart-box">
                    ${data.build_times.map(b => {
                        const width = Math.min(100, Math.max(10, (b.time_ms / (data.build_times[data.build_times.length - 1].time_ms || 1)) * 100));
                        return `
                            <div class="bench-bar-row">
                                <div class="bar-label">${b.size} Docs</div>
                                <div class="bar-track">
                                    <div class="bar-fill" style="width: ${width}%"></div>
                                </div>
                                <div class="bar-val">${b.time_ms} ms</div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>

            <!-- 2. Query Latency Comparison -->
            <div class="bench-card">
                <div class="bench-card-header">
                    <h3>2. Inverted Index vs Naive Scan Latency</h3>
                    <span class="bench-badge speedup">${speedup}x FASTER</span>
                </div>
                <p class="bench-desc">Average per-query execution time comparing \(O(1)\) Hash Map postings retrieval against \(O(D \cdot N)\) linear string scan.</p>
                <div class="bench-chart-box">
                    <div class="bench-bar-row">
                        <div class="bar-label">Inverted Index</div>
                        <div class="bar-track">
                            <div class="bar-fill green" style="width: ${Math.max(6, (data.indexed_latency_ms / data.naive_latency_ms) * 100)}%"></div>
                        </div>
                        <div class="bar-val">${data.indexed_latency_ms} ms</div>
                    </div>
                    <div class="bench-bar-row">
                        <div class="bar-label">Naive Linear Scan</div>
                        <div class="bar-track">
                            <div class="bar-fill red" style="width: 100%"></div>
                        </div>
                        <div class="bar-val">${data.naive_latency_ms} ms</div>
                    </div>
                </div>
                <div class="bench-summary-note">
                    The classical Inverted Index executes in <strong>${data.indexed_latency_ms} ms</strong> vs <strong>${data.naive_latency_ms} ms</strong> for the naive scan, delivering a <strong>${speedup}× performance advantage</strong>.
                </div>
            </div>

            <!-- 3. Dynamic Programming Typo Accuracy -->
            <div class="bench-card">
                <div class="bench-card-header">
                    <h3>3. DP Levenshtein Typo Recovery Accuracy</h3>
                    <span class="bench-badge accuracy">${data.fuzzy_accuracy_pct}% ACCURACY</span>
                </div>
                <p class="bench-desc">Accuracy of minimum edit distance 2D dynamic programming in correcting deliberate multilingual typos against vocabulary keys.</p>
                <div class="accuracy-gauge-box">
                    <div class="accuracy-number">${data.fuzzy_accuracy_pct}%</div>
                    <div class="accuracy-sub">Correct Vocabulary Resolution</div>
                    <div class="accuracy-meter">
                        <div class="accuracy-fill" style="width: ${data.fuzzy_accuracy_pct}%"></div>
                    </div>
                </div>
            </div>
        `;

    } catch (err) {
        console.error('Benchmark error:', err);
        container.innerHTML = '<div class="error-state">Benchmark execution failed.</div>';
    }
}

// ── Tab 4: Corpus Document Manager ────────────────────────────────────────
async function loadCorpusData() {
    try {
        const res = await fetch('/api/corpus');
        const data = await res.json();
        allCorpusDocs = data.documents || [];
        filterCorpusTable();
    } catch (err) {
        console.error('Corpus load error:', err);
    }
}

function filterCorpusTable() {
    const searchVal = document.getElementById('corpusSearchInput').value.trim().toLowerCase();
    const langVal = document.getElementById('corpusLangFilter').value;
    const tbody = document.getElementById('corpusTableBody');
    const countEl = document.getElementById('corpusTableCount');

    let filtered = allCorpusDocs.filter(d => {
        const matchLang = (langVal === 'all') || (d.lang === langVal);
        const matchText = (!searchVal) || (d.title.toLowerCase().includes(searchVal)) || (d.text.toLowerCase().includes(searchVal));
        return matchLang && matchText;
    });

    countEl.textContent = filtered.length;

    tbody.innerHTML = filtered.map(d => {
        const langInfo = LANG_CONFIG[d.lang] || { code: d.lang.toUpperCase(), color: '#64748b' };
        return `
            <tr id="corpus-row-${d.id}">
                <td><code>#${d.id}</code></td>
                <td><span class="lang-pill-mini" style="background:${langInfo.color}">${langInfo.code}</span></td>
                <td><strong>${escapeHtml(d.title)}</strong></td>
                <td><code>${d.word_count} w</code></td>
                <td class="snippet-cell">${escapeHtml(d.snippet)}</td>
                <td>
                    <button class="btn-table-delete" onclick="deleteDocFromCorpus('${d.id}')" title="Delete document">Delete</button>
                </td>
            </tr>
        `;
    }).join('');
}

function exportCorpusJson() {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(allCorpusDocs, null, 2));
    const dl = document.createElement('a');
    dl.setAttribute("href", dataStr);
    dl.setAttribute("download", `corpus_export_${Date.now()}.json`);
    dl.click();
    showToast('Corpus JSON exported successfully.', 'success');
}

// ── CRUD Document Operations ──────────────────────────────────────────────
function openAddDocModal() {
    document.getElementById('addModal').style.display = 'flex';
    document.getElementById('newTitle').focus();
}

async function submitDoc() {
    const title = document.getElementById('newTitle').value.trim();
    const lang = document.getElementById('newLang').value;
    const text = document.getElementById('newText').value.trim();

    if (!title || !text) {
        showToast('Title and content are required.', 'error');
        return;
    }

    try {
        const res = await fetch('/add_document', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, lang, text })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Document #${data.id} indexed successfully!`, 'success');
            closeModal('addModal');
            document.getElementById('newTitle').value = '';
            document.getElementById('newText').value = '';
            fetchGlobalStats();
            loadCorpusData();
        } else {
            showToast(data.error || 'Failed to add document.', 'error');
        }
    } catch (err) {
        showToast('Network error while adding document.', 'error');
    }
}

async function deleteDoc(docId) {
    if (!confirm(`Delete Document #${docId} from Inverted Index and Corpus?`)) return;
    try {
        const res = await fetch(`/delete_document/${docId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            const card = document.getElementById(`doc-${docId}`);
            if (card) card.remove();
            showToast(`Document #${docId} deleted.`, 'success');
            fetchGlobalStats();
            loadCorpusData();
        } else {
            showToast(data.error || 'Could not delete document.', 'error');
        }
    } catch {
        showToast('Network error while deleting.', 'error');
    }
}

async function deleteDocFromCorpus(docId) {
    await deleteDoc(docId);
}

// ── Explain Score Modal ───────────────────────────────────────────────────
function openExplainScoreModal(docId, title, breakdown) {
    const modal = document.getElementById('explainScoreModal');
    const titleEl = document.getElementById('explainScoreDocTitle');
    const contentEl = document.getElementById('explainScoreContent');

    titleEl.textContent = `Document #${docId} — "${title}"`;

    if (!breakdown || breakdown.length === 0) {
        contentEl.innerHTML = '<div class="empty-note">No active query terms contributed to this document.</div>';
    } else {
        const total = breakdown.reduce((acc, b) => acc + (b.contribution || 0), 0);
        contentEl.innerHTML = `
            <table class="explain-table">
                <thead>
                    <tr>
                        <th>Query Term</th>
                        <th>TF (in Doc)</th>
                        <th>DF (Corpus)</th>
                        <th>IDF Weight</th>
                        <th>TF × IDF Contribution</th>
                    </tr>
                </thead>
                <tbody>
                    ${breakdown.map(b => `
                        <tr>
                            <td><code>${escapeHtml(b.term)}</code></td>
                            <td><strong>${b.tf}</strong></td>
                            <td>${b.df}</td>
                            <td><code>${b.idf}</code></td>
                            <td><strong style="color:var(--accent);">${b.contribution}</strong></td>
                        </tr>
                    `).join('')}
                </tbody>
                <tfoot>
                    <tr>
                        <th colspan="4" style="text-align:right;">Accumulated Total Relevance:</th>
                        <th style="color:var(--emerald);">${total.toFixed(4)}</th>
                    </tr>
                </tfoot>
            </table>
        `;
    }

    modal.style.display = 'flex';
}

// ── Wiktionary Define Modal ───────────────────────────────────────────────
function openDefineModal(initialWord = '', lang = 'all') {
    const modal = document.getElementById('defineModal');
    const input = document.getElementById('defineWordInput');
    const select = document.getElementById('defineLangSelect');
    const resultArea = document.getElementById('modalDefinitionResult');

    modal.style.display = 'flex';
    input.value = initialWord;
    select.value = lang;
    resultArea.innerHTML = '';
    input.focus();

    if (initialWord) lookupDefinitionModal();
}

function openDefineModalForTitle(rawTitle, lang) {
    const cleanText = rawTitle.replace(/<[^>]+>/g, '').trim();
    const firstWord = cleanText.split(/\s+/)[0];
    openDefineModal(firstWord, lang);
}

async function lookupDefinitionModal() {
    const word = document.getElementById('defineWordInput').value.trim();
    const lang = document.getElementById('defineLangSelect').value;
    const resultArea = document.getElementById('modalDefinitionResult');

    if (!word) {
        showToast('Please enter a term to look up.', 'warning');
        return;
    }

    resultArea.innerHTML = '<div class="loading-state"><span class="spinner"></span> Querying Wiktionary REST API & checking LRU cache...</div>';

    try {
        const langParam = (lang && lang !== 'all') ? `?lang=${encodeURIComponent(lang)}` : '';
        const res = await fetch(`/api/define/${encodeURIComponent(word)}${langParam}`);
        const data = await res.json();

        if (data.found && data.entries && data.entries.length > 0) {
            const cacheBadge = data.cached
                ? `<span class="lru-badge hit">⚡ LRU Cache Hit (O(1))</span>`
                : `<span class="lru-badge miss">🌐 Wiktionary REST API</span>`;

            resultArea.innerHTML = `
                <div class="def-card">
                    <div class="def-header">
                        <div class="def-word-title">
                            <h3>${escapeHtml(data.word)}</h3>
                            ${cacheBadge}
                        </div>
                        <a href="${data.wiktionary_url}" target="_blank" rel="noopener" class="wiktionary-ext-link">Wikimedia Page ↗</a>
                    </div>
                    <div class="def-entries">
                        ${data.entries.map(e => `
                            <div class="def-entry">
                                <div class="def-entry-meta">
                                    <span class="def-pos">${escapeHtml(e.part_of_speech || 'General')}</span>
                                    <span class="def-lang">${escapeHtml(e.language)}</span>
                                </div>
                                <ol class="def-list">
                                    ${e.definitions.map(d => `<li>${escapeHtml(d)}</li>`).join('')}
                                </ol>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
            fetchGlobalStats(); // Refresh LRU cache metrics
        } else {
            resultArea.innerHTML = `
                <div class="empty-note">
                    <p>No Wiktionary definition found for "<strong>${escapeHtml(word)}</strong>".</p>
                </div>
            `;
        }
    } catch {
        resultArea.innerHTML = '<div class="error-state">Failed to fetch definition.</div>';
    }
}

// ── Modal & Toast Helpers ─────────────────────────────────────────────────
function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

function closeModalOnBackdrop(e, modalId) {
    if (e.target.id === modalId) closeModal(modalId);
}

function showToast(msg, type = 'info') {
    const t = document.createElement('div');
    t.className = `toast-pill ${type}`;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => {
        t.style.opacity = '0';
        t.style.transform = 'translateY(15px)';
        setTimeout(() => t.remove(), 300);
    }, 2800);
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeJs(str) {
    if (!str) return '';
    return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}
