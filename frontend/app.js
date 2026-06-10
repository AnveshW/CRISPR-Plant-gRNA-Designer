/* ============================================================
   CLIENT CONTROLLER - CRISPR Plant gRNA Designer Vanilla JS
   ============================================================ */

// ── Helper to resolve API subpaths (e.g. /sharp) ──
function getApiUrl(endpoint) {
    const pathname = window.location.pathname;
    let basePath = "";
    if (pathname !== "/") {
        const segments = pathname.split("/").filter(s => s);
        const cleanSegments = segments.filter(s => !s.endsWith(".html") && s !== "index.php" && s !== "index.html");
        if (cleanSegments.length > 0) {
            basePath = "/" + cleanSegments.join("/");
        }
    }
    return `${basePath}/api/${endpoint}`;
}

// ── Application State ──
let state = {
    genomes: [],
    selectedGenome: '',
    inputType: 'Locus Tag', // "Locus Tag", "Sequence", "Genomic Position"
    gRNAData: [],          // Parsed guide RNAs
    activeFilters: {
        strand: 'all',
        gc: 'all',
        efficiency: '0.0',
        risk: 'all',
        region: 'all'
    },
    chatHistory: [],
    shortlist: [] // Starred candidates sequence list for comparison
};

// ── Progress Tracker Variables ──
let progressTimerId = null;
let elapsedSeconds = 0;

// ── DOM References ──
const elements = {
    serverStatusText: document.getElementById('server-status-text'),
    tabButtons: document.querySelectorAll('.tab-btn'),
    locusTab: document.getElementById('locus-tab'),
    seqTab: document.getElementById('seq-tab'),
    posTab: document.getElementById('pos-tab'),
    designForm: document.getElementById('design-form'),
    inputLocus: document.getElementById('input-locus'),
    inputSeq: document.getElementById('input-seq'),
    inputPos: document.getElementById('input-pos'),
    inputPam: document.getElementById('input-pam'),
    inputGuideLength: document.getElementById('input-guide-length'),
    promoters: document.getElementsByName('promoter'),
    fetchGenomesBtn: document.getElementById('fetch-genomes-btn'),
    genomeSelectGroup: document.getElementById('genome-select-group'),
    inputGenome: document.getElementById('input-genome'),
    runBtn: document.getElementById('run-btn'),
    
    welcomeView: document.getElementById('welcome-view'),
    loadingView: document.getElementById('loading-view'),
    resultsView: document.getElementById('results-view'),
    progressStatusText: document.getElementById('progress-status-text'),
    progressElapsedCounter: document.getElementById('progress-elapsed-counter'),
    
    resultsCount: document.getElementById('results-count'),
    grnaTableBody: document.getElementById('grna-table-body'),
    dnaTrackSvg: document.getElementById('dna-track-svg'), // kept for safety, no longer drawn physically
    downloadCsvBtn: document.getElementById('download-csv-btn'),
    downloadFastaBtn: document.getElementById('download-fasta-btn'),
    
    filterStrand: document.getElementById('filter-strand'),
    filterGc: document.getElementById('filter-gc'),
    filterEfficiency: document.getElementById('filter-efficiency'),
    filterRisk: document.getElementById('filter-risk'),
    filterRegion: document.getElementById('filter-region'),
    
    chatBoxMessages: document.getElementById('chat-box-messages'),
    chatUserInput: document.getElementById('chat-user-input'),
    chatSendBtn: document.getElementById('chat-send-btn'),
    quickQBtns: document.querySelectorAll('.quick-q-btn'),
    floatingChatTrigger: document.getElementById('floating-chat-trigger'),
    floatingChatPanel: document.getElementById('floating-chat-panel'),
    closeChatBtn: document.getElementById('close-chat-btn'),
    
    litSearchInput: document.getElementById('lit-search-input'),
    litSearchBtn: document.getElementById('lit-search-btn'),
    presetOfftarget: document.getElementById('preset-offtarget'),
    presetDesign: document.getElementById('preset-design'),
    presetGene: document.getElementById('preset-gene'),
    papersListContainer: document.getElementById('papers-list-container'),
    
    criticalGenesAccordion: document.getElementById('critical-genes-accordion'),

    // Summary Metrics Strip references
    statTotal: document.getElementById('stat-total'),
    statLowRisk: document.getElementById('stat-low-risk'),
    statAvgEfficiency: document.getElementById('stat-avg-efficiency'),
    statAvgGc: document.getElementById('stat-avg-gc'),
    statUniquePam: document.getElementById('stat-unique-pam'),
    statStrandBalance: document.getElementById('stat-strand-balance'),
    
    // Shortlist references
    shortlistTableBody: document.getElementById('shortlist-table-body'),
    shortlistBox: document.getElementById('shortlist-box'),
    clearShortlistBtn: document.getElementById('clear-shortlist-btn'),
    
    // Detail Drawer references
    candidateDetailDrawer: document.getElementById('candidate-detail-drawer'),
    drawerCloseBtn: document.getElementById('drawer-close-btn'),
    drawerBodyContent: document.getElementById('drawer-body-content')
};

// ── Initialization ──
document.addEventListener('DOMContentLoaded', () => {
    initApp();
    checkServerConnection();
});

function initApp() {
    // Input Type Tabs
    elements.tabButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            elements.tabButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const activeTab = btn.getAttribute('data-tab');
            elements.locusTab.style.display = 'none';
            elements.seqTab.style.display = 'none';
            elements.posTab.style.display = 'none';
            
            document.getElementById(activeTab).style.display = 'block';
            state.inputType = btn.textContent.trim();
            validateForm();
        });
    });

    // Inputs listener
    elements.inputLocus.addEventListener('input', validateForm);
    elements.inputSeq.addEventListener('input', validateForm);
    elements.inputPos.addEventListener('input', validateForm);

    // Fetch Genomes Button
    elements.fetchGenomesBtn.addEventListener('click', fetchGenomes);

    // Form submission
    elements.designForm.addEventListener('submit', runAnalysis);

    // Grid Filters
    elements.filterStrand.addEventListener('change', handleFilters);
    elements.filterGc.addEventListener('change', handleFilters);
    elements.filterEfficiency.addEventListener('change', handleFilters);
    elements.filterRisk.addEventListener('change', handleFilters);
    elements.filterRegion.addEventListener('change', handleFilters);

    // Downloads
    if (elements.downloadCsvBtn) elements.downloadCsvBtn.addEventListener('click', downloadCSV);
    if (elements.downloadFastaBtn) elements.downloadFastaBtn.addEventListener('click', downloadFASTA);

    // Chatbot actions
    elements.chatSendBtn.addEventListener('click', sendChatMessage);
    elements.chatUserInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChatMessage();
    });

    elements.quickQBtns.forEach(btn => {
        if (btn.classList.contains('quick-q-btn') && btn.parentElement.classList.contains('quick-q-bar')) {
            btn.addEventListener('click', () => {
                const question = btn.getAttribute('data-q');
                elements.chatUserInput.value = question;
                sendChatMessage();
            });
        }
    });

    // Floating assistant triggers
    if (elements.floatingChatTrigger && elements.floatingChatPanel) {
        elements.floatingChatTrigger.addEventListener('click', () => {
            const isHidden = elements.floatingChatPanel.classList.toggle('hidden');
            if (!isHidden) {
                elements.chatUserInput.focus();
            }
        });
    }

    if (elements.closeChatBtn && elements.floatingChatPanel) {
        elements.closeChatBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            elements.floatingChatPanel.classList.add('hidden');
        });
    }

    // OpenAlex custom searches
    elements.litSearchBtn.addEventListener('click', handleCustomPaperSearch);
    elements.presetOfftarget.addEventListener('click', () => searchLiterature("CRISPR off-target effects"));
    elements.presetDesign.addEventListener('click', () => searchLiterature("guide RNA design optimization"));
    elements.presetGene.addEventListener('click', () => {
        if (state.inputType === 'Locus Tag' && elements.inputLocus.value.trim()) {
            searchLiterature(elements.inputLocus.value.trim());
        }
    });

    // Star Shortlist & Drawer Bindings
    elements.clearShortlistBtn.addEventListener('click', clearAllShortlist);
    elements.drawerCloseBtn.addEventListener('click', closeDetailDrawer);

    // Close drawer on ESC key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDetailDrawer();
    });
}

// ── Check Server Connectivity ──
async function checkServerConnection() {
    try {
        const res = await fetch(getApiUrl('genomes'));
        if (res.ok) {
            elements.serverStatusText.textContent = 'Server Connected';
            // Auto fetch genomes on load if server is active to make UI look complete
            fetchGenomes();
        } else {
            elements.serverStatusText.textContent = 'Server Offline';
        }
    } catch {
        elements.serverStatusText.textContent = 'Disconnected';
    }
}

// ── Validate Control Form ──
function validateForm() {
    let hasInput = false;
    if (state.inputType === 'Locus Tag' && elements.inputLocus.value.trim()) {
        hasInput = true;
    } else if (state.inputType === 'DNA Sequence' && elements.inputSeq.value.trim()) {
        hasInput = true;
    } else if (state.inputType === 'Genomic Position' && elements.inputPos.value.trim()) {
        hasInput = true;
    }
    
    const hasGenomes = elements.inputGenome.options.length > 0;
    elements.runBtn.disabled = !(hasInput && hasGenomes);
}

// ── Fetch Genomes dropdown list ──
async function fetchGenomes() {
    elements.fetchGenomesBtn.disabled = true;
    elements.fetchGenomesBtn.textContent = 'Connecting to HZAU...';
    
    try {
        const res = await fetch(getApiUrl('genomes'));
        if (!res.ok) throw new Error('API genomes endpoint failure');
        const data = await res.json();
        
        state.genomes = data.genomes || [];
        
        // Populating dropdown selector
        elements.inputGenome.innerHTML = '';
        state.genomes.forEach(g => {
            const opt = document.createElement('option');
            opt.value = g;
            opt.textContent = g;
            if (g.includes("Glycine max")) opt.selected = true; // default soybean match
            elements.inputGenome.appendChild(opt);
        });
        
        elements.genomeSelectGroup.style.display = 'block';
        elements.fetchGenomesBtn.style.display = 'none';
        elements.runBtn.removeAttribute('disabled');
        validateForm();
    } catch (e) {
        console.error(e);
        elements.fetchGenomesBtn.disabled = false;
        elements.fetchGenomesBtn.textContent = 'Fetch Database List (Failed)';
    }
}

// ── Resolve concise, clean error messages mapping ──
function getCleanErrorMessage(rawMessage) {
    const msg = String(rawMessage).toLowerCase();
    if (msg.includes('connection_refused') || msg.includes('connection refused') || msg.includes('net::err_connection')) {
        return "Connection refused: The CRISPR-PLANT portal is currently unreachable or offline.";
    }
    if (msg.includes('timeout') || msg.includes('timed out') || msg.includes('time out')) {
        return "Request timed out: The CRISPR-PLANT server is slow or did not respond in time.";
    }
    if (msg.includes('no such element') || msg.includes('not found') || msg.includes('locus') || msg.includes('invalid')) {
        return "Target not found: Locus tag was not recognized by the selected genome database.";
    }
    return "Design failed: Please check your input parameters and try again.";
}

// ── Append log message inside Stepper Panel ──
function logProgress(msg, type = 'log') {
    if (!elements.progressStatusText) return;
    
    if (type === 'error') {
        const cleanMsg = getCleanErrorMessage(msg);
        elements.progressStatusText.textContent = cleanMsg;
        elements.progressStatusText.style.color = 'var(--risk-high)';
        return;
    }
    
    const text = String(msg).toLowerCase();
    if (text.includes('connecting') || text.includes('initializing') || text.includes('launching') || text.includes('spawning') || text.includes('chrome')) {
        elements.progressStatusText.textContent = "Connecting to CRISPR-PLANT Design Portal...";
    } else if (text.includes('selecting') || text.includes('setting') || text.includes('injecting') || text.includes('genome') || text.includes('promoter')) {
        elements.progressStatusText.textContent = "Configuring design parameters...";
    } else if (text.includes('submitting') || text.includes('running') || text.includes('request') || text.includes('portal')) {
        elements.progressStatusText.textContent = "Submitting request and running parsing algorithm...";
    } else if (text.includes('auditing') || text.includes('off-target') || text.includes('candidates')) {
        elements.progressStatusText.textContent = "Auditing candidate off-target profiles...";
    } else if (text.includes('complete') || text.includes('rendering')) {
        elements.progressStatusText.textContent = "Design complete! Rendering interactive dashboard...";
    }
}

// ── Run gRNA Design Scraper ──
async function runAnalysis(e) {
    e.preventDefault();
    
    const selected_genome = elements.inputGenome.value;
    const pam = elements.inputPam.value;
    const guide_length = elements.inputGuideLength.value;
    
    let promoter = 'U3 (default)';
    elements.promoters.forEach(r => {
        if (r.checked) promoter = r.value;
    });

    const payload = {
        selected_genome,
        input_type: state.inputType,
        locus_tag: elements.inputLocus.value.trim(),
        sequence: elements.inputSeq.value.trim(),
        position: elements.inputPos.value.trim(),
        pam,
        guide_length,
        promoter
    };

    // Transition View State: loading
    elements.welcomeView.classList.remove('active');
    elements.resultsView.classList.remove('active');
    elements.loadingView.classList.add('active');
    
    // Hide assistant during transition and loading
    if (elements.floatingChatTrigger) elements.floatingChatTrigger.style.display = 'none';
    if (elements.floatingChatPanel) elements.floatingChatPanel.classList.add('hidden');
    
    // Setup and clear progress UI
    if (progressTimerId) clearInterval(progressTimerId);
    elapsedSeconds = 0;
    if (elements.progressElapsedCounter) {
        elements.progressElapsedCounter.textContent = '0s';
    }
    if (elements.progressStatusText) {
        elements.progressStatusText.textContent = 'Connecting to CRISPR-PLANT Design Portal...';
        elements.progressStatusText.style.color = 'var(--primary)';
    }

    progressTimerId = setInterval(() => {
        elapsedSeconds++;
        if (elements.progressElapsedCounter) {
            elements.progressElapsedCounter.textContent = `${elapsedSeconds}s`;
        }
    }, 1000);

    try {
        const response = await fetch(getApiUrl('analyze'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("Scraper endpoint connection error");

        // Parse SSE Stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // Hold onto incomplete lines

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));
                    
                    if (data.type === 'log') {
                        logProgress(data.message);
                    } else if (data.type === 'complete') {
                        clearInterval(progressTimerId);
                        logProgress("Guide RNA synthesis complete! Rendering interactive dashboard...", 'complete');
                        state.gRNAData = data.results || [];
                        setTimeout(() => {
                            renderResults();
                        }, 1000);
                    } else if (data.type === 'error') {
                        clearInterval(progressTimerId);
                        logProgress(data.message, 'error');
                        throw new Error(data.message);
                    }
                }
            }
        }

    } catch (e) {
        clearInterval(progressTimerId);
        const cleanMsg = getCleanErrorMessage(e.message);
        logProgress(cleanMsg, 'error');
        alert(`Design Failed: ${cleanMsg}`);
        // Revert to welcome card on fatal error
        setTimeout(() => {
            elements.loadingView.classList.remove('active');
            elements.welcomeView.classList.add('active');
        }, 3000);
    }
}

// ── Render Results View ──
function renderResults() {
    elements.loadingView.classList.remove('active');
    elements.resultsView.classList.add('active');
    
    // Show the floating chat trigger once results are ready
    if (elements.floatingChatTrigger) elements.floatingChatTrigger.style.display = 'block';
    
    elements.resultsCount.textContent = state.gRNAData.length;
    
    // Configure research explorer buttons
    if (state.inputType === 'Locus Tag' && elements.inputLocus.value.trim()) {
        const gene = elements.inputLocus.value.trim();
        elements.presetGene.textContent = `Papers: ${gene}`;
        elements.presetGene.style.display = 'block';
    } else {
        elements.presetGene.style.display = 'none';
    }

    // Load OpenAlex preset papers automatically to look populated
    searchLiterature("CRISPR off-target effects");
    
    // Hydrate guide RNA dataset with genomic coordinates and spacer/PAM variables
    computeCoordinates(state.gRNAData);
    
    // Clear and build tables/visualizations
    clearFilters();
    buildCriticalGenesExplorer();
}

// ── Hydrate Genomic Coordinates ──
function computeCoordinates(data) {
    const fullSequence = elements.inputSeq.value ? elements.inputSeq.value.trim().toUpperCase() : '';
    const seqLen = fullSequence ? fullSequence.length : 500;
    
    data.forEach((grna, i) => {
        const sequence = grna.sequence.toUpperCase();
        const spacer = sequence.slice(0, -3);
        const pam = sequence.slice(-3);
        
        let start = null;
        let end = null;
        let strand = grna.strand || '+';
        
        if (fullSequence) {
            // Search Sense strand
            let idx = fullSequence.indexOf(spacer);
            if (idx >= 0) {
                start = idx + 1; // 1-based coordinate for scientists
                end = idx + sequence.length;
                strand = '+';
            } else {
                // Search Antisense strand
                const revSpacer = getReverseComplement(spacer);
                idx = fullSequence.indexOf(revSpacer);
                if (idx >= 0) {
                    start = idx + 1;
                    end = idx + sequence.length;
                    strand = '-';
                }
            }
        } else if (grna.position) {
            // Use the real parsed coordinates and strand from the CRISPR-PLANT database!
            const parts = grna.position.split(':');
            if (parts.length >= 2) {
                const coordStr = parts[1].replace('+', '').replace('-', '');
                const coord = parseInt(coordStr);
                if (!isNaN(coord)) {
                    start = coord;
                    end = coord + 22; // 23 bp total length (spacer+PAM)
                }
            }
            strand = grna.strand || '+';
        }
        
        // Attach calculated variables directly to the gRNA candidate state object
        grna.computedStart = start;
        grna.computedEnd = end;
        grna.computedStrand = strand;
        grna.spacerSeq = spacer;
        grna.pamSeq = pam;
        
        // Compute rule-based sequence warning liabilities
        grna.warnings = [];
        if (spacer.includes("TTTT")) {
            grna.warnings.push({ type: "polyT", message: "Premature Poly-T Transcription Term Tract (TTTT) detected for U3/U6" });
        }
        if (grna.gc_content < 40) {
            grna.warnings.push({ type: "lowGC", message: "Low GC content (<40%): potentially unstable target binding" });
        }
        if (grna.gc_content > 65) {
            grna.warnings.push({ type: "highGC", message: "High GC content (>65%): rigid sequence, high off-target potential" });
        }
        if (grna.critical_count > 3) {
            grna.warnings.push({ type: "offtarget", message: "High off-target risk: affects 4 or more critical exon/CDS regions" });
        }
    });
}

// ── Clipboard Copy Helper ──
window.copyToClipboard = function(text, btnId) {
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById(btnId);
        if (btn) {
            const oldText = btn.innerHTML;
            btn.innerHTML = 'COPIED';
            btn.title = 'Copied!';
            setTimeout(() => {
                btn.innerHTML = oldText;
                btn.title = 'Copy spacer sequence';
            }, 1500);
        }
    }).catch(err => {
        console.error('Failed to copy spacer sequence:', err);
    });
};

// ── GC% 12px Circular Filled-Arc Widget ──
function getGcCircleSvg(gcPercent) {
    const radius = 5;
    const circumference = 2 * Math.PI * radius; // ~31.42
    const strokeDashOffset = circumference - (Math.min(Math.max(gcPercent, 0), 100) / 100) * circumference;
    
    // Olive is #707a43, Sage is #4a7c59
    let color = '#707a43'; // Default olive
    if (gcPercent >= 55) {
        color = '#4a7c59'; // Sage green for high/optimal
    } else if (gcPercent > 40) {
        // Interpolate between olive and sage
        const factor = (gcPercent - 40) / 15;
        const r = Math.round(112 + (74 - 112) * factor);
        const g = Math.round(122 + (124 - 122) * factor);
        const b = Math.round(67 + (89 - 67) * factor);
        color = `rgb(${r}, ${g}, ${b})`;
    } else {
        color = '#8a8570'; // Muted dark olive-gray for low GC
    }
    
    return `<svg class="gc-circle-svg" width="12" height="12" viewBox="0 0 12 12" style="display:inline-block; vertical-align:middle; margin-right:6px; transform: rotate(-90deg);">
        <circle cx="6" cy="6" r="5" fill="none" stroke="var(--border-neutral)" stroke-width="1.5" />
        <circle cx="6" cy="6" r="5" fill="none" stroke="${color}" stroke-width="1.5" 
                stroke-dasharray="${circumference}" stroke-dashoffset="${strokeDashOffset}" />
    </svg>`;
}

// ── Render Guide Grid Table ──
function renderTable(data) {
    elements.grnaTableBody.innerHTML = '';
    
    if (data.length === 0) {
        elements.grnaTableBody.innerHTML = `
            <tr>
                <td colspan="10" style="text-align:left; padding: 40px; color: var(--text-muted);">
                    <div style="font-size:15px; margin-bottom:8px; font-weight:600;">No Designed Candidates Match Filters</div>
                    <div style="font-size:13px; color:var(--text-inactive);">Try relaxing your selection filters (e.g. min efficiency or risk limits).</div>
                </td>
            </tr>
        `;
        return;
    }

    data.forEach((grna, idx) => {
        const tr = document.createElement('tr');
        tr.id = `table-row-${grna.sequence}`;
        tr.className = state.shortlist.includes(grna.sequence) ? 'selected-row' : '';
        
        // Row selection links straight to candidate drawer deep-dive
        tr.addEventListener('click', () => {
            openDetailDrawer(grna.sequence);
        });

        // Region coloring classes
        const regionLower = grna.region.toLowerCase();
        
        // Risk assessment variables
        let riskClass = 'low';
        const criticalGenes = grna.off_targets ? [...new Set(grna.off_targets.filter(o => o.gene && o.gene !== 'N/A' && o.region && ['exon', 'cds', 'utr', '5\'utr', '3\'utr'].includes(o.region.toLowerCase())).map(o => o.gene))] : [];
        
        if (grna.critical_count > 3) {
            riskClass = 'high';
        } else if (grna.critical_count > 0) {
            riskClass = 'medium';
        }

        const offTargetContent = `
            <div class="offtarget-two-col">
                <span class="severity-dot ${riskClass}">●</span>
                <span class="critical-genes-text">${criticalGenes.length > 0 ? criticalGenes.join(', ') : 'None'}</span>
            </div>
        `;

        // Divide target and PAM sequence
        const seqBody = grna.spacerSeq;
        const seqPam = grna.pamSeq;
        
        // Check if starred favorite
        const isStarred = state.shortlist.includes(grna.sequence);
        const starHTML = `<span class="star-toggle" onclick="event.stopPropagation(); window.toggleShortlist('${grna.sequence}')" style="cursor:pointer; font-size:15px; margin-right:8px; color:${isStarred ? '#4a7c59' : 'var(--text-inactive)'};">${isStarred ? '★' : '☆'}</span>`;

        // Warnings layout
        let warningIcons = '';
        if (grna.warnings.length > 0) {
            const warningTitle = grna.warnings.map(w => w.message).join(' | ');
            warningIcons = `<span class="warning-label" title="${warningTitle}">!</span>`;
        }

        tr.innerHTML = `
            <td class="rank-cell">${starHTML}${idx + 1}</td>
            <td>
                <div class="seq-align-box">
                    <span class="seq-spacer">${seqBody}</span>
                </div>
            </td>
            <td>
                <span class="mono seq-pam-mark">${seqPam}</span>
            </td>
            <td class="tabular mono">
                ${getGcCircleSvg(grna.gc_content)}<span>${grna.gc_content.toFixed(1)}%</span>
            </td>
            <td class="col-offtarget">
                ${offTargetContent}
            </td>
            <td>
                <span class="region-pill ${regionLower}">${grna.region.toUpperCase()}</span>
                ${warningIcons}
            </td>
            <td>
                <button class="copy-btn" id="copy-btn-${idx}" onclick="event.stopPropagation(); window.copyToClipboard('${grna.sequence}', 'copy-btn-${idx}')" title="Copy spacer+PAM sequence">
                    COPY
                </button>
            </td>
        `;
        elements.grnaTableBody.appendChild(tr);
    });
}

// ── Star Shortlist Triage Controller ──
window.toggleShortlist = function(seq) {
    const idx = state.shortlist.indexOf(seq);
    if (idx >= 0) {
        state.shortlist.splice(idx, 1);
    } else {
        state.shortlist.push(seq);
    }
    
    // Save to shortlist panel
    renderShortlist();
    
    // Re-render core grids to keep star status synced
    handleFilters();
};

function renderShortlist() {
    elements.shortlistTableBody.innerHTML = '';
    
    if (state.shortlist.length === 0) {
        elements.shortlistBox.style.display = 'none';
        return;
    }
    
    elements.shortlistBox.style.display = 'block';
    
    state.shortlist.forEach((seq, idx) => {
        const grna = state.gRNAData.find(g => g.sequence === seq);
        if (!grna) return;
        
        const tr = document.createElement('tr');
        tr.style.background = 'rgba(74, 124, 89, 0.02)';
        
        // Weighted recommendation statuses
        let recStatus = 'Borderline';
        let recColor = 'var(--risk-med)';
        
        if (grna.critical_count === 0 && grna.gc_content >= 40 && grna.gc_content <= 60 && grna.score >= 0.5) {
            recStatus = 'Highly Recommended';
            recColor = 'var(--risk-low)';
        } else if (grna.critical_count <= 2 && grna.gc_content >= 35 && grna.gc_content <= 68 && grna.score >= 0.35) {
            recStatus = 'Recommended';
            recColor = 'var(--risk-low)';
        } else if (grna.critical_count > 3 || grna.sequence.includes("TTTT")) {
            recStatus = 'Not Recommended';
            recColor = 'var(--risk-high)';
        }

        const regionLower = grna.region.toLowerCase();
        const criticalGenes = grna.off_targets ? [...new Set(grna.off_targets.filter(o => o.gene && o.gene !== 'N/A' && o.region && ['exon', 'cds', 'utr', '5\'utr', '3\'utr'].includes(o.region.toLowerCase())).map(o => o.gene))] : [];
        
        let riskClass = 'low';
        if (grna.critical_count > 3) {
            riskClass = 'high';
        } else if (grna.critical_count > 0) {
            riskClass = 'medium';
        }
        
        const offTargetShortlist = `
            <div class="offtarget-two-col">
                <span class="severity-dot ${riskClass}">●</span>
                <span class="critical-genes-text">${criticalGenes.length > 0 ? criticalGenes.join(', ') : 'None'}</span>
            </div>
        `;

        tr.innerHTML = `
            <td class="rank-cell">${idx + 1}</td>
            <td><span class="mono seq-align-box" style="padding:2px 4px; font-size:12px;">${grna.spacerSeq}</span></td>
            <td><span class="mono seq-pam-mark">${grna.pamSeq}</span></td>
            <td class="tabular mono">
                ${getGcCircleSvg(grna.gc_content)}<span>${grna.gc_content.toFixed(1)}%</span>
            </td>
            <td class="col-offtarget">${offTargetShortlist}</td>
            <td><span class="region-pill ${regionLower}">${grna.region.toUpperCase()}</span></td>
            <td style="color:${recColor}; font-weight:600;">${recStatus}</td>
            <td>
                <button class="quick-q-btn" onclick="window.toggleShortlist('${grna.sequence}')" style="padding:2px 8px; font-size:11px; background:none; border-color:var(--border-neutral); color:var(--text-muted);">
                    Remove
                </button>
            </td>
        `;
        elements.shortlistTableBody.appendChild(tr);
    });
}

function clearAllShortlist() {
    state.shortlist = [];
    renderShortlist();
    handleFilters();
}

// ── Open Candidate Detail Drawer Overlay ──
function openDetailDrawer(seq) {
    const grna = state.gRNAData.find(g => g.sequence === seq);
    if (!grna) return;
    
    // Find index for rank
    const rank = state.gRNAData.findIndex(g => g.sequence === seq) + 1;
    
    // Evaluate transparent decision-support recommendation
    let recStatus = 'Borderline Liability';
    let recClass = 'medium';
    let recExplanation = 'GC content falls in extreme boundaries or spacer shows sub-optimal on-target binding parameters.';
    
    if (grna.critical_count === 0 && grna.gc_content >= 40 && grna.gc_content <= 60 && grna.score >= 0.5) {
        recStatus = 'Highly Recommended';
        recClass = 'low';
        recExplanation = 'High specificity profile with 0 predicted critical exon/CDS off-target strikes, balanced GC content (40-60%), and robust on-target nuclease binding affinity.';
    } else if (grna.critical_count <= 2 && grna.gc_content >= 35 && grna.gc_content <= 68 && grna.score >= 0.35) {
        recStatus = 'Recommended';
        recClass = 'low';
        recExplanation = 'Satisfactory nuclease affinity with minor off-target risk. Specificity auditing is recommended prior to vector assembly.';
    } else if (grna.critical_count > 3) {
        recStatus = 'Not Recommended';
        recClass = 'high';
        recExplanation = 'Severe specificity risk: audits indicate 4 or more predicted critical exon off-target knockouts, increasing probability of severe phenotypic noise.';
    }
    
    if (grna.sequence.includes("TTTT")) {
        recStatus = 'Severe Transcription Termination Hazard';
        recClass = 'high';
        recExplanation = 'Premature Poly-T sequence tract (TTTT) detected inside the spacer. This tract acts as a transcription termination signal for U3/U6 U6-snoRNA RNA Polymerase III promoters, aborting active gRNA synthesis.';
    }

    const strandLabel = grna.computedStrand === '+' ? 'Sense (+)' : 'Antisense (-)';
    const positionText = grna.computedStart !== null ? `${grna.computedStart}-${grna.computedEnd} bp` : 'N/A (pos map not loaded)';

    // Build specific off-target genes list
    let offTargetsHTML = `<div style="font-size:13px; color:var(--text-muted); padding: 4px 0;">No critical off-targets parsed. Perfect specificity profile.</div>`;
    if (grna.off_targets && grna.off_targets.length > 0) {
        offTargetsHTML = `
            <table class="drawer-data-table" style="font-size:13px; margin-top:6px;">
                <thead>
                    <tr style="color:var(--text-muted); text-align:left; border-bottom:1px solid var(--border-neutral);">
                        <th style="padding:6px 0;">Off-Target Sequence</th>
                        <th style="padding:6px 0;">Region</th>
                        <th style="padding:6px 0; text-align:right;">Locus Tag</th>
                    </tr>
                </thead>
                <tbody>
                    ${grna.off_targets.map(ot => `
                        <tr style="border-bottom: 1px solid var(--border-neutral);">
                            <td class="mono" style="padding:6px 0;">${ot.sequence}</td>
                            <td style="padding:6px 0; text-transform:uppercase; font-size:11px;">${ot.region}</td>
                            <td style="padding:6px 0; text-align:right; font-weight:bold;">${ot.gene || 'N/A'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    let recColor = 'var(--risk-med)';
    if (recClass === 'high') recColor = 'var(--risk-high)';
    else if (recClass === 'low') recColor = 'var(--risk-low)';

    elements.drawerBodyContent.innerHTML = `
        <!-- Candidate Identity -->
        <div>
            <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px;">Candidate Record Profile</div>
            <h2 style="font-family:'Instrument Serif', Georgia, serif; font-style: italic; color:var(--text-main); font-size:26px; margin-top:2px;">Guide # ${rank}</h2>
        </div>
 
        <!-- Spacer Display -->
        <div style="background:var(--bg-control); border:1px solid var(--border-neutral); padding:12px; border-radius:2px;">
            <div class="mono" style="font-size:15px; font-weight:700; letter-spacing:0.5px; color: var(--text-main);">
                ${grna.spacerSeq}<span style="color:var(--pam-color); text-decoration:underline;">${grna.pamSeq}</span>
            </div>
        </div>
 
        <!-- Decision Support Box -->
        <div style="background:var(--primary-bg); border:1px solid ${recColor}; border-radius:2px; padding:12px;">
            <div style="font-size:14px; font-weight:700; color:${recColor}; text-transform: uppercase; letter-spacing: 0.3px;">${recStatus}</div>
            <div style="font-size:14px; line-height:1.45; color:var(--text-main); margin-top:6px;">
                ${recExplanation}
            </div>
        </div>
 
        <!-- Core Profile Variables -->
        <div>
            <div class="drawer-section-title">Design Parameters</div>
            <table class="drawer-data-table">
                <tr><td class="lbl">Predicted Efficiency</td><td class="val" style="color:var(--primary); font-size:14px;">${grna.score.toFixed(4)}</td></tr>
                <tr><td class="lbl">GC Content Ratio</td><td class="val" style="color:var(--text-main);">${grna.gc_content.toFixed(1)}%</td></tr>
                <tr><td class="lbl">Targeted Strand</td><td class="val" style="color:var(--text-main);">${strandLabel}</td></tr>
                <tr><td class="lbl">Genomic Annotation</td><td class="val" style="color:var(--text-main); text-transform:uppercase;">${grna.region}</td></tr>
                <tr><td class="lbl">Absolute Position</td><td class="val" style="color:var(--text-main);">${positionText}</td></tr>
                <tr><td class="lbl">Total Off-Targets</td><td class="val" style="color:var(--text-main);">${grna.off_target_count} sites</td></tr>
                <tr><td class="lbl">Critical Exon Off-Targets</td><td class="val" style="color:${grna.critical_count > 0 ? 'var(--risk-med)' : 'var(--risk-low)'};">${grna.critical_count} hits</td></tr>
            </table>
        </div>
 
        <!-- Specific Off-target list -->
        <div>
            <div class="drawer-section-title">Critical Off-Target Targets</div>
            ${offTargetsHTML}
        </div>
 
        <!-- Action Drawer Options -->
        <div style="margin-top:20px; display:flex; gap:10px;">
            <button class="btn" style="flex:1; padding:8px 12px; font-size:13px; border-radius: 2px;" onclick="window.toggleShortlist('${grna.sequence}')">
                ${state.shortlist.includes(grna.sequence) ? 'Unstar Candidate' : 'Star Candidate'}
            </button>
            <button class="btn btn-secondary" style="width:60px; padding:0; border-radius: 2px; font-size: 12px;" onclick="window.copyToClipboard('${grna.sequence}', 'drawer-copy')" id="drawer-copy" title="Copy spacer+PAM">
                COPY
            </button>
        </div>
    `;
    
    // Slide Drawer In
    elements.candidateDetailDrawer.classList.add('open');
}

function closeDetailDrawer() {
    elements.candidateDetailDrawer.classList.remove('open');
}

// ── Helper: compute reverse complement of nucleotide sequence ──
function getReverseComplement(seq) {
    const map = { 'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C', 'N': 'N', 'a': 't', 't': 'a', 'c': 'g', 'g': 'c', 'n': 'n' };
    return seq.split('').reverse().map(c => map[c] || c).join('');
}

// ── No-Op DNA Browser Track (kept for functional call safety) ──
function drawDNATrack(data) {
    // Keep dynamic update of subtitle for coordinate honesty mode
    const fullSequence = elements.inputSeq.value ? elements.inputSeq.value.trim().toUpperCase() : '';
    const seqLen = fullSequence ? fullSequence.length : 500;
}

// ── Overview Statistics Strips Calculator ──
function updateSummaryMetrics(data) {
    const count = data.length;
    if (elements.statTotal) elements.statTotal.textContent = count;
    
    const avgScore = count > 0 ? data.reduce((sum, g) => sum + g.score, 0) / count : 0.0;
    if (elements.statAvgEfficiency) elements.statAvgEfficiency.textContent = avgScore.toFixed(4);
    
    const avgGc = count > 0 ? data.reduce((sum, g) => sum + g.gc_content, 0) / count : 0.0;
    if (elements.statAvgGc) elements.statAvgGc.textContent = avgGc.toFixed(1) + '%';
}

// ── Scientific Multivariable Filter Auditing ──
function handleFilters() {
    state.activeFilters.region = elements.filterRegion.value;
    state.activeFilters.risk = elements.filterRisk.value;
    state.activeFilters.gc = elements.filterGc.value;
    state.activeFilters.strand = elements.filterStrand.value;
    state.activeFilters.efficiency = elements.filterEfficiency.value;
    
    const filtered = state.gRNAData.filter(grna => {
        // 1. Target Strand Filtering
        if (state.activeFilters.strand !== 'all') {
            if (state.activeFilters.strand === 'plus' && grna.computedStrand !== '+') return false;
            if (state.activeFilters.strand === 'minus' && grna.computedStrand !== '-') return false;
        }
        
        // 2. Genomic Annotation Region Filtering
        if (state.activeFilters.region !== 'all') {
            const lowerReg = grna.region.toLowerCase();
            if (state.activeFilters.region === 'exon' && (lowerReg !== 'exon' && lowerReg !== 'cds')) return false;
            if (state.activeFilters.region === 'utr' && !lowerReg.includes('utr')) return false;
            if (state.activeFilters.region === 'intron' && lowerReg !== 'intron') return false;
        }
        
        // 3. Off-Target Risk Tier Filtering
        if (state.activeFilters.risk !== 'all') {
            const crit = grna.critical_count;
            if (state.activeFilters.risk === 'low' && crit !== 0) return false;
            if (state.activeFilters.risk === 'med' && crit > 3) return false;
        }
        
        // 4. GC Content Range Filtering
        if (state.activeFilters.gc !== 'all') {
            const gc = grna.gc_content;
            if (state.activeFilters.gc === 'optimal' && (gc < 40 || gc > 65)) return false;
            if (state.activeFilters.gc === 'high' && gc <= 65) return false;
            if (state.activeFilters.gc === 'low' && gc >= 40) return false;
        }
        
        // 5. Predicted Efficiency Threshold Filtering
        const minEff = parseFloat(state.activeFilters.efficiency);
        if (grna.score < minEff) return false;
        
        return true;
    });

    renderTable(filtered);
    drawDNATrack(filtered);
    updateSummaryMetrics(filtered);
}

function clearFilters() {
    elements.filterRegion.value = 'all';
    elements.filterRisk.value = 'all';
    elements.filterGc.value = 'all';
    elements.filterStrand.value = 'all';
    elements.filterEfficiency.value = '0.0';
    
    state.activeFilters = { region: 'all', risk: 'all', gc: 'all', strand: 'all', efficiency: '0.0' };
    
    renderTable(state.gRNAData);
    drawDNATrack(state.gRNAData);
    updateSummaryMetrics(state.gRNAData);
}

// ── Export Downloads ──
function downloadCSV() {
    if (state.gRNAData.length === 0) return;
    
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "Rank,Sequence,GC Content,On-Target Score,Region,Critical Off-Targets,Total Off-Targets\n";
    
    state.gRNAData.forEach((grna, idx) => {
        csvContent += `${idx+1},${grna.sequence},${grna.gc_content.toFixed(1)}%,${grna.score.toFixed(4)},${grna.region},${grna.critical_count},${grna.off_target_count}\n`;
    });
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    const inputLabel = elements.inputLocus.value.trim() || "grna_results";
    link.setAttribute("download", `grna_top30_${inputLabel}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function downloadFASTA() {
    if (state.gRNAData.length === 0) return;
    
    let fastaContent = "";
    state.gRNAData.forEach((grna, idx) => {
        fastaContent += `>gRNA_Rank_${idx+1}_Score_${grna.score.toFixed(4)}_GC_${grna.gc_content.toFixed(1)}%_Region_${grna.region}\n${grna.sequence}\n`;
    });
    
    const blob = new Blob([fastaContent], { type: 'text/plain;charset=utf-8' });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    const inputLabel = elements.inputLocus.value.trim() || "grna_results";
    link.setAttribute("download", `grna_top30_${inputLabel}.fasta`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// ── Accordion builder for Critical Off-Targets ──
function buildCriticalGenesExplorer() {
    const container = elements.criticalGenesAccordion;
    container.innerHTML = '';
    
    const allCriticalGenes = [];
    const seen = new Set();
    
    state.gRNAData.forEach(grna => {
        if (grna.off_targets) {
            grna.off_targets.forEach(ot => {
                if (ot.gene && !seen.has(ot.gene) && ot.region && ['exon', 'cds', 'utr', "5'utr", "3'utr"].includes(ot.region)) {
                    allCriticalGenes.push(ot.gene);
                    seen.add(ot.gene);
                }
            });
        }
    });

    if (allCriticalGenes.length === 0) {
        container.innerHTML = `
            <div style="text-align:left; padding: 24px; color: var(--text-muted); font-size: 14px;">
                No critical off-target genes identified across candidate guides. This sequence offers excellent specificity.
            </div>
        `;
        return;
    }

    allCriticalGenes.forEach(gene => {
        const row = document.createElement('div');
        row.className = 'gene-explorer-row';
        row.id = `gene-row-${gene}`;
        
        row.innerHTML = `
            <div class="gene-explorer-trigger">
                <span class="gene-name">Gene target: <strong>${gene}</strong></span>
                <span class="arrow" style="font-size:13px; color:var(--text-muted);">Expand deep-dive papers</span>
            </div>
            <div class="gene-papers-content">
                <div class="papers-loader" style="text-align:left; padding: 20px; color: var(--text-muted); font-size: 13px;">
                    Fetching OpenAlex papers for ${gene}...
                </div>
                <div class="gene-papers-results-grid" style="display:flex; flex-direction:column; gap:10px;"></div>
            </div>
        `;
        
        // Click trigger accordion expand
        row.querySelector('.gene-explorer-trigger').addEventListener('click', () => {
            const isActive = row.classList.contains('active');
            
            // Close all
            container.querySelectorAll('.gene-explorer-row').forEach(r => r.classList.remove('active'));
            
            if (!isActive) {
                row.classList.add('active');
                fetchGeneLiterature(gene, row.querySelector('.gene-papers-results-grid'), row.querySelector('.papers-loader'));
            }
        });

        container.appendChild(row);
    });
}

// ── OpenAlex Gene Specific Literature ──
async function fetchGeneLiterature(gene, gridEl, loaderEl) {
    gridEl.innerHTML = '';
    loaderEl.style.display = 'block';
    
    try {
        const res = await fetch(getApiUrl(`papers?query=${encodeURIComponent(gene)}&per_page=4`));
        if (!res.ok) throw new Error('Papers API error');
        const data = await res.json();
        
        loaderEl.style.display = 'none';
        const papers = data.papers || [];
        
        if (papers.length === 0) {
            gridEl.innerHTML = `<div style="font-size:13px; color:var(--text-muted); text-align:left;">No direct papers resolved for '${gene}' in OpenAlex DB. Try broader search.</div>`;
            return;
        }

        papers.forEach(paper => {
            const card = document.createElement('div');
            card.className = 'paper-card';
            card.style.padding = '12px';
            card.style.background = 'rgba(255, 255, 255, 0.45)';
            
            const oa = paper.open_access ? '<span class="paper-badge">Open Access</span>' : '';
            
            card.innerHTML = `
                <div style="font-weight:600; font-size:15px; margin-bottom:4px; color:var(--text-main);">${paper.title}</div>
                <div style="font-size:12px; color:var(--text-muted); margin-bottom:6px;">
                    By ${paper.authors} (${paper.year}) | Citations: ${paper.citations} ${oa}
                </div>
                <div style="font-size:14px; line-height:1.4; color:var(--text-muted); margin-bottom:8px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">
                    ${paper.abstract || 'No abstract preview available. View DOI link.'}
                </div>
                <a href="${paper.url}" target="_blank" class="paper-doi-link">View DOI Portal</a>
            `;
            gridEl.appendChild(card);
        });

    } catch (e) {
        loaderEl.style.display = 'none';
        gridEl.innerHTML = `<div style="font-size:13px; color:var(--error); text-align:left;">Failed to load OpenAlex papers: ${e.message}</div>`;
    }
}

// ── OpenAlex Literature Explorer Searches ──
async function handleCustomPaperSearch() {
    const q = elements.litSearchInput.value.trim();
    if (q) searchLiterature(q);
}

async function searchLiterature(query) {
    elements.papersListContainer.innerHTML = `
        <div style="text-align:left; padding: 40px; color: var(--text-muted); font-size: 14px;">
            Querying OpenAlex databases for "${query}"...
        </div>
    `;
    
    try {
        const res = await fetch(getApiUrl(`papers?query=${encodeURIComponent(query)}`));
        if (!res.ok) throw new Error('API failure');
        const data = await res.json();
        const papers = data.papers || [];
        
        elements.papersListContainer.innerHTML = '';
        
        if (papers.length === 0) {
            elements.papersListContainer.innerHTML = `
                <div style="text-align:left; padding: 40px; color: var(--text-muted); font-size: 14px;">
                    No results found in OpenAlex catalog. Try different keywords.
                </div>
            `;
            return;
        }

        papers.forEach(paper => {
            const card = document.createElement('div');
            card.className = 'paper-card';
            
            const oa = paper.open_access ? '<span class="paper-badge">Open Access</span>' : '';
            
            card.innerHTML = `
                <div class="paper-title">${paper.title}</div>
                <div class="paper-meta">
                    <span>By: ${paper.authors}</span>
                    <span>Year: ${paper.year}</span>
                    <span>Citations: ${paper.citations}</span>
                    ${oa}
                </div>
                <div class="paper-abstract">${paper.abstract || 'No abstract preview text resolved in OpenAlex index. Access publication portal directly via DOI link.'}</div>
                <a href="${paper.url}" target="_blank" class="paper-doi-link">View DOI Portal</a>
            `;
            elements.papersListContainer.appendChild(card);
        });

    } catch (e) {
        elements.papersListContainer.innerHTML = `
            <div style="text-align:left; padding: 40px; color: var(--error); font-size: 14px;">
                Failed to search OpenAlex publications: ${e.message}
            </div>
        `;
    }
}

// ── AI Chatbot Assistant ──
async function sendChatMessage() {
    const input = elements.chatUserInput.value.trim();
    if (!input) return;
    
    // Clear input
    elements.chatUserInput.value = '';
    
    // Append User Bubble
    appendChatBubble('user', input);
    
    // Prepare conversation payload
    state.chatHistory.push({ role: 'user', content: input });
    
    // Build context summary of gRNA results
    const genome = elements.inputGenome.value;
    // Extract all unique genes mentioned in off-targets
    const allGenes = new Set();
    state.gRNAData.forEach(g => {
        if (g.off_targets) {
            g.off_targets.forEach(o => {
                if (o.gene) allGenes.add(o.gene);
            });
        }
    });
    
    // Check if user input mentions any of these genes
    const mentionedGenes = [...allGenes].filter(gene => input.includes(gene));
    
    let dynamicContext = "";
    if (mentionedGenes.length > 0) {
        dynamicContext = "\n[Detailed Off-targets Context for user's mentioned genes]:\n";
        mentionedGenes.forEach(gene => {
            dynamicContext += `Gene ${gene}:\n`;
            state.gRNAData.forEach(g => {
                if (g.off_targets) {
                    const ots = g.off_targets.filter(o => o.gene === gene);
                    if (ots.length > 0) {
                        dynamicContext += `  Candidate Seq ${g.sequence}: ${ots.length} off-target(s) (Regions: ${ots.map(o=>o.region).join(', ')})\n`;
                    }
                }
            });
        });
    }

    // Include all candidates in the base details, but keep it concise (one line per candidate)
    const details = state.gRNAData.map(g => {
        const genes = g.off_targets ? [...new Set(g.off_targets.filter(o => o.gene && o.region && ['exon', 'cds', 'utr'].includes(o.region)).map(o => o.gene))] : [];
        return `Seq: ${g.sequence} | Score: ${g.score.toFixed(4)} | GC: ${g.gc_content.toFixed(1)}% | Region: ${g.region} | Crit-Offtargets: ${g.critical_count} | Affected-Genes: ${genes.join(',') || 'None'}`;
    }).join('\n');
    
    const summary = `
Analysis Target: ${elements.inputLocus.value.trim() || state.inputType}
Organism Genome: ${genome}
Total candidate gRNAs analyzed: ${state.gRNAData.length}

All gRNA Candidate Overviews:
${details}
${dynamicContext}
    `;

    // Typing bubble loader
    const typingBubble = appendChatBubble('assistant', 'Thinking...', true);

    try {
        const payload = {
            messages: state.chatHistory,
            summary,
            user_key: state.geminiKey || null
        };
        
        const res = await fetch(getApiUrl('chat'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        typingBubble.remove();
        
        if (!res.ok) {
            const data = await res.json();
            throw new Error(data.detail || 'Gemini API Error');
        }
        
        const data = await res.json();
        const responseText = data.response;
        
        // Append response
        appendChatBubble('assistant', responseText);
        state.chatHistory.push({ role: 'assistant', content: responseText });
        
    } catch (e) {
        typingBubble.remove();
        appendChatBubble('assistant', `Error: ${e.message}. Please verify the server API key configuration.`);
    }
}

function appendChatBubble(role, content, isLoader = false) {
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;
    bubble.textContent = content;
    if (isLoader) bubble.id = 'chat-bubble-loader';
    
    elements.chatBoxMessages.appendChild(bubble);
    elements.chatBoxMessages.scrollTop = elements.chatBoxMessages.scrollHeight;
    
    return bubble;
}
