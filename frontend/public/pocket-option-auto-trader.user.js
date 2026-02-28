// ==UserScript==
// @name         GPT Signal Bot - Pocket Option Auto Trader v3.0
// @namespace    https://signal-generator-pro.preview.emergentagent.com
// @version      3.0.0
// @description  Advanced auto-trader with comprehensive data display, auto on/off, fetch, and reset controls
// @author       GPT Signal Bot
// @match        *://*.pocketoption.com/*
// @match        *://pocketoption.com/*
// @match        *://*.po.trade/*
// @match        *://po.trade/*
// @match        *://*.pocket-option.com/*
// @match        *://pocket-option.com/*
// @match        *://*.po.market/*
// @match        *://po.market/*
// @grant        GM_notification
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_log
// @connect      signal-generator-pro.preview.emergentagent.com
// @connect      *
// @run-at       document-idle
// @noframes
// ==/UserScript==

(function() {
    'use strict';

    // ===========================================
    // CONFIGURATION
    // ===========================================
    const CONFIG = {
        API_URL: 'https://signal-generator-pro.preview.emergentagent.com/api',
        POLL_INTERVAL: 5000,  // Poll every 5 seconds
        AUTO_TRADE_ENABLED: GM_getValue('autoEnabled', true),
        SOUND_ENABLED: GM_getValue('soundEnabled', true),
        DEBUG: true,
        COOLDOWN_MS: 5000,  // Cooldown between trades
        MAX_SIGNAL_AGE_SECONDS: 60  // Max age of signal to consider valid
    };

    // ===========================================
    // STATE
    // ===========================================
    let state = {
        lastProcessedSignalId: GM_getValue('lastProcessedSignalId', null),
        lastProcessedSignalTime: GM_getValue('lastProcessedSignalTime', 0),
        isTrading: false,
        tradeCount: GM_getValue('tradeCount', 0),
        winCount: GM_getValue('winCount', 0),
        lossCount: GM_getValue('lossCount', 0),
        connectionStatus: 'disconnected',
        lastSignal: null,
        lastFetchTime: null,
        lastError: null,
        pollInterval: null,
        apiStatus: 'unknown',
        panelMinimized: GM_getValue('panelMinimized', false),
        panelPosition: GM_getValue('panelPosition', { top: 10, left: null })
    };

    // ===========================================
    // LOGGING SYSTEM
    // ===========================================
    const logHistory = [];
    const MAX_LOG_ENTRIES = 50;

    function log(msg, type = 'info') {
        const ts = new Date().toLocaleTimeString();
        const logEntry = { time: ts, message: msg, type: type };
        logHistory.unshift(logEntry);
        
        if (logHistory.length > MAX_LOG_ENTRIES) {
            logHistory.pop();
        }

        const prefix = '[GPT Bot v3]';
        const emoji = type === 'error' ? '❌' : type === 'success' ? '✅' : type === 'warn' ? '⚠️' : '📡';
        console.log(`${prefix} ${ts} ${emoji}: ${msg}`);
        
        // Update UI log display
        updateLogDisplay(logEntry);
    }

    function updateLogDisplay(entry) {
        const logEl = document.getElementById('gpt-log-text');
        if (logEl) {
            const color = entry.type === 'error' ? '#ef4444' : 
                         entry.type === 'success' ? '#22c55e' : 
                         entry.type === 'warn' ? '#f59e0b' : '#94a3b8';
            logEl.innerHTML = `<span style="color:${color}">[${entry.time}] ${entry.message}</span>`;
        }
    }

    // ===========================================
    // UI PANEL CREATION
    // ===========================================
    function createPanel() {
        // Remove existing panel if present
        const existing = document.getElementById('gpt-panel');
        if (existing) existing.remove();

        const panel = document.createElement('div');
        panel.id = 'gpt-panel';
        panel.innerHTML = `
            <style>
                #gpt-panel {
                    position: fixed;
                    top: 10px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    border: 2px solid #7c3aed;
                    border-radius: 12px;
                    padding: 0;
                    z-index: 999999;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    color: white;
                    box-shadow: 0 8px 32px rgba(124, 58, 237, 0.4);
                    min-width: 320px;
                    max-width: 420px;
                    user-select: none;
                    transition: box-shadow 0.2s, border-color 0.2s;
                }
                #gpt-panel.dragging {
                    box-shadow: 0 12px 48px rgba(124, 58, 237, 0.6);
                    border-color: #a78bfa;
                }
                #gpt-panel.minimized .panel-body {
                    display: none;
                }
                #gpt-panel.minimized {
                    min-width: 200px;
                    max-width: 250px;
                }
                #gpt-panel * {
                    user-select: none;
                }
                
                /* Drag Handle */
                #gpt-panel .drag-handle {
                    background: linear-gradient(90deg, #7c3aed 0%, #6366f1 100%);
                    padding: 8px 12px;
                    border-radius: 10px 10px 0 0;
                    cursor: move;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                #gpt-panel .drag-handle:active {
                    cursor: grabbing;
                }
                #gpt-panel .drag-handle .grip {
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                    margin-right: 8px;
                }
                #gpt-panel .drag-handle .grip span {
                    width: 16px;
                    height: 2px;
                    background: rgba(255,255,255,0.5);
                    border-radius: 1px;
                }
                #gpt-panel .drag-handle .title-area {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    flex: 1;
                }
                #gpt-panel .drag-handle .title {
                    font-weight: bold;
                    color: white;
                    font-size: 13px;
                }
                #gpt-panel .drag-handle .controls-area {
                    display: flex;
                    gap: 6px;
                }
                #gpt-panel .drag-handle .mini-btn {
                    width: 24px;
                    height: 24px;
                    border-radius: 4px;
                    border: none;
                    background: rgba(255,255,255,0.2);
                    color: white;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 14px;
                    transition: background 0.2s;
                }
                #gpt-panel .drag-handle .mini-btn:hover {
                    background: rgba(255,255,255,0.3);
                }
                
                #gpt-panel .panel-body {
                    padding: 12px 16px;
                }
                
                #gpt-panel .status-dot {
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    background: #ef4444;
                    animation: pulse 2s infinite;
                }
                #gpt-panel .status-dot.connected { background: #22c55e; }
                #gpt-panel .status-dot.trading { background: #f59e0b; animation: blink 0.3s infinite; }
                #gpt-panel .status-dot.error { background: #ef4444; }
                @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
                @keyframes blink { 50% { opacity: 0.2; } }
                
                #gpt-panel .data-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 8px;
                    margin-bottom: 10px;
                }
                #gpt-panel .data-item {
                    background: rgba(0,0,0,0.3);
                    padding: 8px;
                    border-radius: 6px;
                    font-size: 11px;
                }
                #gpt-panel .data-label {
                    color: #94a3b8;
                    font-size: 10px;
                    margin-bottom: 2px;
                }
                #gpt-panel .data-value {
                    font-weight: bold;
                    font-size: 13px;
                }
                #gpt-panel .data-value.call { color: #22c55e; }
                #gpt-panel .data-value.put { color: #ef4444; }
                #gpt-panel .data-value.hold { color: #f59e0b; }
                #gpt-panel .data-value.none { color: #64748b; }
                
                #gpt-panel .signal-box {
                    background: rgba(0,0,0,0.4);
                    border-radius: 8px;
                    padding: 10px;
                    margin-bottom: 10px;
                    text-align: center;
                }
                #gpt-panel .signal-direction {
                    font-size: 24px;
                    font-weight: bold;
                    margin-bottom: 4px;
                }
                #gpt-panel .signal-direction.call { color: #22c55e; text-shadow: 0 0 10px rgba(34,197,94,0.5); }
                #gpt-panel .signal-direction.put { color: #ef4444; text-shadow: 0 0 10px rgba(239,68,68,0.5); }
                #gpt-panel .signal-direction.waiting { color: #64748b; }
                #gpt-panel .signal-meta {
                    font-size: 11px;
                    color: #94a3b8;
                }
                
                #gpt-panel .controls {
                    display: flex;
                    gap: 8px;
                    margin-bottom: 10px;
                }
                #gpt-panel button {
                    flex: 1;
                    padding: 8px 12px;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 11px;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                #gpt-panel button:hover {
                    transform: translateY(-1px);
                    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                }
                #gpt-panel button:active {
                    transform: translateY(0);
                }
                #gpt-panel .btn-auto {
                    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
                    color: white;
                }
                #gpt-panel .btn-auto.off {
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                }
                #gpt-panel .btn-fetch {
                    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                    color: white;
                }
                #gpt-panel .btn-reset {
                    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                    color: white;
                }
                #gpt-panel .btn-sound {
                    background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
                    color: white;
                    max-width: 70px;
                }
                
                #gpt-panel .stats-row {
                    display: flex;
                    justify-content: space-between;
                    font-size: 11px;
                    margin-bottom: 8px;
                    padding: 6px 8px;
                    background: rgba(0,0,0,0.2);
                    border-radius: 4px;
                }
                #gpt-panel .stat {
                    display: flex;
                    align-items: center;
                    gap: 4px;
                }
                #gpt-panel .stat-label { color: #94a3b8; }
                #gpt-panel .stat-value { font-weight: bold; }
                #gpt-panel .stat-value.win { color: #22c55e; }
                #gpt-panel .stat-value.loss { color: #ef4444; }
                
                #gpt-panel .log-box {
                    background: rgba(0,0,0,0.4);
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 10px;
                    max-height: 60px;
                    overflow-y: auto;
                }
                #gpt-panel .log-box::-webkit-scrollbar {
                    width: 4px;
                }
                #gpt-panel .log-box::-webkit-scrollbar-thumb {
                    background: #7c3aed;
                    border-radius: 2px;
                }
                
                #gpt-panel .footer {
                    margin-top: 8px;
                    font-size: 9px;
                    color: #64748b;
                    text-align: center;
                }
                
                /* Minimized state indicator */
                #gpt-panel .mini-signal {
                    display: none;
                    padding: 8px 12px;
                    text-align: center;
                }
                #gpt-panel.minimized .mini-signal {
                    display: block;
                }
                #gpt-panel .mini-signal .direction {
                    font-weight: bold;
                    font-size: 16px;
                }
                #gpt-panel .mini-signal .direction.call { color: #22c55e; }
                #gpt-panel .mini-signal .direction.put { color: #ef4444; }
                #gpt-panel .mini-signal .direction.waiting { color: #64748b; }
            </style>
            
            <!-- Drag Handle -->
            <div class="drag-handle" id="gpt-drag-handle">
                <div class="grip">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
                <div class="title-area">
                    <span class="status-dot" id="gpt-status-dot"></span>
                    <span class="title">GPT Bot v3.0</span>
                </div>
                <div class="controls-area">
                    <button class="mini-btn" id="gpt-btn-minimize" title="Minimize/Expand">−</button>
                    <button class="mini-btn" id="gpt-btn-pin" title="Pin to corner">📌</button>
                </div>
            </div>
            
            <!-- Minimized View -->
            <div class="mini-signal">
                <span class="direction waiting" id="gpt-mini-direction">WAITING</span>
            </div>
            
            <!-- Full Panel Body -->
            <div class="panel-body">
                <div class="signal-box">
                    <div class="signal-direction waiting" id="gpt-signal-direction">WAITING</div>
                    <div class="signal-meta" id="gpt-signal-meta">No signal received yet</div>
                </div>
                
                <div class="data-grid">
                    <div class="data-item">
                        <div class="data-label">Symbol</div>
                        <div class="data-value" id="gpt-symbol">--</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Confidence</div>
                        <div class="data-value" id="gpt-confidence">--%</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Signal Age</div>
                        <div class="data-value" id="gpt-signal-age">--</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Last Fetch</div>
                        <div class="data-value" id="gpt-last-fetch">--</div>
                    </div>
                </div>
                
                <div class="stats-row">
                    <div class="stat">
                        <span class="stat-label">Trades:</span>
                        <span class="stat-value" id="gpt-trade-count">0</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Wins:</span>
                        <span class="stat-value win" id="gpt-win-count">0</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Losses:</span>
                        <span class="stat-value loss" id="gpt-loss-count">0</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Win Rate:</span>
                        <span class="stat-value" id="gpt-win-rate">--%</span>
                    </div>
                </div>
                
                <div class="controls">
                    <button class="btn-auto" id="gpt-btn-auto">AUTO: ON</button>
                    <button class="btn-fetch" id="gpt-btn-fetch">FETCH</button>
                    <button class="btn-reset" id="gpt-btn-reset">RESET</button>
                    <button class="btn-sound" id="gpt-btn-sound">🔊</button>
                </div>
                
                <div class="log-box" id="gpt-log-box">
                    <div id="gpt-log-text">Initializing bot...</div>
                </div>
                
                <div class="footer">
                    Drag header to move | Click − to minimize
                </div>
            </div>
        `;
        
        document.body.appendChild(panel);
        
        // Restore saved position
        if (state.panelPosition.left !== null) {
            panel.style.left = state.panelPosition.left + 'px';
            panel.style.top = state.panelPosition.top + 'px';
            panel.style.transform = 'none';
        }
        
        // Restore minimized state
        if (state.panelMinimized) {
            panel.classList.add('minimized');
            document.getElementById('gpt-btn-minimize').textContent = '+';
        }
        
        // Make panel draggable (only via drag handle)
        makeDraggable(panel, document.getElementById('gpt-drag-handle'));
        
        // Attach button handlers
        document.getElementById('gpt-btn-auto').addEventListener('click', toggleAutoTrade);
        document.getElementById('gpt-btn-fetch').addEventListener('click', () => fetchSignal(true));
        document.getElementById('gpt-btn-reset').addEventListener('click', resetBot);
        document.getElementById('gpt-btn-sound').addEventListener('click', toggleSound);
        document.getElementById('gpt-btn-minimize').addEventListener('click', toggleMinimize);
        document.getElementById('gpt-btn-pin').addEventListener('click', pinToCorner);
        
        // Initialize button states
        updateAutoButton();
        updateSoundButton();
        
        log('Panel created - drag header to move', 'success');
    }

    function toggleMinimize() {
        const panel = document.getElementById('gpt-panel');
        const btn = document.getElementById('gpt-btn-minimize');
        
        state.panelMinimized = !state.panelMinimized;
        GM_setValue('panelMinimized', state.panelMinimized);
        
        if (state.panelMinimized) {
            panel.classList.add('minimized');
            btn.textContent = '+';
        } else {
            panel.classList.remove('minimized');
            btn.textContent = '−';
        }
        
        log(state.panelMinimized ? 'Panel minimized' : 'Panel expanded');
    }

    function pinToCorner() {
        const panel = document.getElementById('gpt-panel');
        
        // Cycle through corners: top-left, top-right, bottom-right, bottom-left, center
        const corners = [
            { top: 10, left: 10 },
            { top: 10, left: window.innerWidth - panel.offsetWidth - 10 },
            { top: window.innerHeight - panel.offsetHeight - 10, left: window.innerWidth - panel.offsetWidth - 10 },
            { top: window.innerHeight - panel.offsetHeight - 10, left: 10 },
            { top: 10, left: (window.innerWidth - panel.offsetWidth) / 2 }
        ];
        
        // Find current closest corner and move to next
        let currentCorner = 0;
        let minDist = Infinity;
        const currentTop = panel.offsetTop;
        const currentLeft = panel.offsetLeft;
        
        corners.forEach((corner, i) => {
            const dist = Math.abs(corner.top - currentTop) + Math.abs(corner.left - currentLeft);
            if (dist < minDist) {
                minDist = dist;
                currentCorner = i;
            }
        });
        
        const nextCorner = (currentCorner + 1) % corners.length;
        const newPos = corners[nextCorner];
        
        panel.style.top = newPos.top + 'px';
        panel.style.left = newPos.left + 'px';
        panel.style.transform = 'none';
        
        // Save position
        state.panelPosition = { top: newPos.top, left: newPos.left };
        GM_setValue('panelPosition', state.panelPosition);
        
        log(`Pinned to ${['top-left', 'top-right', 'bottom-right', 'bottom-left', 'center'][nextCorner]}`);
    }

    function makeDraggable(element, handle) {
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
        let isDragging = false;
        
        const dragTarget = handle || element;
        
        dragTarget.onmousedown = dragMouseDown;
        dragTarget.ontouchstart = dragTouchStart;
        
        function dragMouseDown(e) {
            if (e.target.tagName === 'BUTTON') return;
            e.preventDefault();
            isDragging = true;
            element.classList.add('dragging');
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;
        }
        
        function dragTouchStart(e) {
            if (e.target.tagName === 'BUTTON') return;
            isDragging = true;
            element.classList.add('dragging');
            const touch = e.touches[0];
            pos3 = touch.clientX;
            pos4 = touch.clientY;
            document.ontouchend = closeDragElement;
            document.ontouchmove = elementTouchDrag;
        }
        
        function elementDrag(e) {
            if (!isDragging) return;
            e.preventDefault();
            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;
            
            let newTop = element.offsetTop - pos2;
            let newLeft = element.offsetLeft - pos1;
            
            // Keep within viewport bounds
            newTop = Math.max(0, Math.min(newTop, window.innerHeight - 50));
            newLeft = Math.max(0, Math.min(newLeft, window.innerWidth - 50));
            
            element.style.top = newTop + "px";
            element.style.left = newLeft + "px";
            element.style.transform = 'none';
        }
        
        function elementTouchDrag(e) {
            if (!isDragging) return;
            const touch = e.touches[0];
            pos1 = pos3 - touch.clientX;
            pos2 = pos4 - touch.clientY;
            pos3 = touch.clientX;
            pos4 = touch.clientY;
            
            let newTop = element.offsetTop - pos2;
            let newLeft = element.offsetLeft - pos1;
            
            // Keep within viewport bounds
            newTop = Math.max(0, Math.min(newTop, window.innerHeight - 50));
            newLeft = Math.max(0, Math.min(newLeft, window.innerWidth - 50));
            
            element.style.top = newTop + "px";
            element.style.left = newLeft + "px";
            element.style.transform = 'none';
        }
        
        function closeDragElement() {
            isDragging = false;
            element.classList.remove('dragging');
            document.onmouseup = null;
            document.onmousemove = null;
            document.ontouchend = null;
            document.ontouchmove = null;
            
            // Save position
            state.panelPosition = { 
                top: element.offsetTop, 
                left: element.offsetLeft 
            };
            GM_setValue('panelPosition', state.panelPosition);
        }
    }

    // ===========================================
    // UI UPDATE FUNCTIONS
    // ===========================================
    function updateUI() {
        // Update status dot
        const dot = document.getElementById('gpt-status-dot');
        if (dot) {
            dot.className = 'status-dot';
            if (state.isTrading) {
                dot.classList.add('trading');
            } else if (state.connectionStatus === 'connected') {
                dot.classList.add('connected');
            } else {
                dot.classList.add('error');
            }
        }
        
        // Update connection status text
        const connStatus = document.getElementById('gpt-connection-status');
        if (connStatus) {
            if (state.isTrading) {
                connStatus.textContent = 'Executing trade...';
                connStatus.style.color = '#f59e0b';
            } else if (state.connectionStatus === 'connected') {
                connStatus.textContent = 'Connected';
                connStatus.style.color = '#22c55e';
            } else {
                connStatus.textContent = state.lastError || 'Disconnected';
                connStatus.style.color = '#ef4444';
            }
        }
        
        // Update signal display
        updateSignalDisplay();
        
        // Update stats
        const tradeCount = document.getElementById('gpt-trade-count');
        const winCount = document.getElementById('gpt-win-count');
        const lossCount = document.getElementById('gpt-loss-count');
        const winRate = document.getElementById('gpt-win-rate');
        
        if (tradeCount) tradeCount.textContent = state.tradeCount;
        if (winCount) winCount.textContent = state.winCount;
        if (lossCount) lossCount.textContent = state.lossCount;
        if (winRate) {
            const total = state.winCount + state.lossCount;
            winRate.textContent = total > 0 ? `${Math.round((state.winCount / total) * 100)}%` : '--%';
        }
        
        // Update last fetch time
        const lastFetch = document.getElementById('gpt-last-fetch');
        if (lastFetch && state.lastFetchTime) {
            const secondsAgo = Math.round((Date.now() - state.lastFetchTime) / 1000);
            lastFetch.textContent = `${secondsAgo}s ago`;
        }
    }

    function updateSignalDisplay() {
        const directionEl = document.getElementById('gpt-signal-direction');
        const metaEl = document.getElementById('gpt-signal-meta');
        const symbolEl = document.getElementById('gpt-symbol');
        const confidenceEl = document.getElementById('gpt-confidence');
        const ageEl = document.getElementById('gpt-signal-age');
        const miniDirectionEl = document.getElementById('gpt-mini-direction');
        
        if (!state.lastSignal) {
            if (directionEl) {
                directionEl.textContent = 'WAITING';
                directionEl.className = 'signal-direction waiting';
            }
            if (miniDirectionEl) {
                miniDirectionEl.textContent = 'WAITING';
                miniDirectionEl.className = 'direction waiting';
            }
            if (metaEl) metaEl.textContent = 'Polling for new signals...';
            if (symbolEl) symbolEl.textContent = '--';
            if (confidenceEl) confidenceEl.textContent = '--%';
            if (ageEl) ageEl.textContent = '--';
            return;
        }
        
        const signal = state.lastSignal;
        const isCall = signal.direction === 'CALL' || signal.direction === 'BUY';
        
        if (directionEl) {
            directionEl.textContent = isCall ? 'CALL' : 'PUT';
            directionEl.className = `signal-direction ${isCall ? 'call' : 'put'}`;
        }
        
        // Update minimized view
        if (miniDirectionEl) {
            const conf = signal.confidence || signal.probability || 0;
            miniDirectionEl.textContent = `${isCall ? 'CALL' : 'PUT'} ${Math.round(conf)}%`;
            miniDirectionEl.className = `direction ${isCall ? 'call' : 'put'}`;
        }
        
        if (symbolEl) {
            symbolEl.textContent = signal.symbol || '--';
        }
        
        if (confidenceEl) {
            const conf = signal.confidence || signal.probability || 0;
            confidenceEl.textContent = `${Math.round(conf)}%`;
            confidenceEl.style.color = conf >= 80 ? '#22c55e' : conf >= 60 ? '#f59e0b' : '#ef4444';
        }
        
        // Calculate and display signal age
        if (ageEl && signal.timestamp) {
            try {
                const signalTime = new Date(signal.timestamp).getTime();
                const ageSeconds = Math.round((Date.now() - signalTime) / 1000);
                ageEl.textContent = `${ageSeconds}s`;
                ageEl.style.color = ageSeconds < 30 ? '#22c55e' : ageSeconds < 60 ? '#f59e0b' : '#ef4444';
            } catch (e) {
                ageEl.textContent = '--';
            }
        }
        
        if (metaEl) {
            const strategy = signal.strategy || 'Unknown Strategy';
            const timestamp = signal.timestamp ? new Date(signal.timestamp).toLocaleTimeString() : '--';
            metaEl.textContent = `${strategy} | ${timestamp}`;
        }
    }

    function updateAutoButton() {
        const btn = document.getElementById('gpt-btn-auto');
        if (btn) {
            btn.textContent = CONFIG.AUTO_TRADE_ENABLED ? 'AUTO: ON' : 'AUTO: OFF';
            btn.className = CONFIG.AUTO_TRADE_ENABLED ? 'btn-auto' : 'btn-auto off';
        }
    }

    function updateSoundButton() {
        const btn = document.getElementById('gpt-btn-sound');
        if (btn) {
            btn.textContent = CONFIG.SOUND_ENABLED ? '🔊' : '🔇';
            btn.style.opacity = CONFIG.SOUND_ENABLED ? '1' : '0.6';
        }
    }

    // ===========================================
    // CONTROL FUNCTIONS
    // ===========================================
    function toggleAutoTrade() {
        CONFIG.AUTO_TRADE_ENABLED = !CONFIG.AUTO_TRADE_ENABLED;
        GM_setValue('autoEnabled', CONFIG.AUTO_TRADE_ENABLED);
        updateAutoButton();
        log(`Auto-trade ${CONFIG.AUTO_TRADE_ENABLED ? 'ENABLED' : 'DISABLED'}`, CONFIG.AUTO_TRADE_ENABLED ? 'success' : 'warn');
        
        if (CONFIG.AUTO_TRADE_ENABLED) {
            // Immediately check for signals when enabled
            fetchSignal(true);
        }
    }

    function toggleSound() {
        CONFIG.SOUND_ENABLED = !CONFIG.SOUND_ENABLED;
        GM_setValue('soundEnabled', CONFIG.SOUND_ENABLED);
        updateSoundButton();
        log(`Sound ${CONFIG.SOUND_ENABLED ? 'enabled' : 'disabled'}`);
        
        // Play test sound if enabled
        if (CONFIG.SOUND_ENABLED) {
            playSound('test');
        }
    }

    function resetBot() {
        log('Resetting bot...', 'warn');
        
        // Reset state
        state.lastProcessedSignalId = null;
        state.lastProcessedSignalTime = 0;
        state.lastSignal = null;
        state.isTrading = false;
        state.lastError = null;
        
        // Save reset state
        GM_setValue('lastProcessedSignalId', null);
        GM_setValue('lastProcessedSignalTime', 0);
        
        // Update UI
        updateUI();
        
        log('Bot reset complete - ready for new signals', 'success');
        
        // Fetch immediately after reset
        setTimeout(() => fetchSignal(true), 500);
    }

    function resetStats() {
        state.tradeCount = 0;
        state.winCount = 0;
        state.lossCount = 0;
        
        GM_setValue('tradeCount', 0);
        GM_setValue('winCount', 0);
        GM_setValue('lossCount', 0);
        
        updateUI();
        log('Stats reset', 'success');
    }

    // ===========================================
    // SIGNAL FETCHING
    // ===========================================
    function fetchSignal(force = false) {
        if (state.isTrading && !force) {
            log('Busy trading, skipping fetch');
            return;
        }

        log('Fetching signal from API...');
        state.lastFetchTime = Date.now();
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: `${CONFIG.API_URL}/signals/latest?use_enhanced=true`,
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            timeout: 15000,
            onload: function(response) {
                handleSignalResponse(response, force);
            },
            onerror: function(error) {
                state.connectionStatus = 'error';
                state.lastError = 'Connection failed';
                log('API connection error', 'error');
                updateUI();
            },
            ontimeout: function() {
                state.connectionStatus = 'error';
                state.lastError = 'Request timeout';
                log('API request timeout', 'error');
                updateUI();
            }
        });
    }

    function handleSignalResponse(response, force) {
        try {
            if (response.status !== 200) {
                state.connectionStatus = 'error';
                state.lastError = `HTTP ${response.status}`;
                log(`API error: HTTP ${response.status}`, 'error');
                updateUI();
                return;
            }

            const data = JSON.parse(response.responseText);
            state.connectionStatus = 'connected';
            state.lastError = null;
            
            log(`API response: success=${data.success}`);

            if (!data.success || !data.signal) {
                log(data.message || 'No signal available');
                state.lastSignal = null;
                updateUI();
                return;
            }

            const signal = data.signal;
            const signalId = signal.id;
            
            // Get signal timestamp
            let signalTime = 0;
            if (signal.timestamp) {
                try {
                    signalTime = new Date(signal.timestamp).getTime();
                } catch (e) {
                    signalTime = Date.now();
                }
            }
            
            // Calculate signal age
            const signalAgeSeconds = (Date.now() - signalTime) / 1000;
            
            // Update display regardless of whether we trade
            state.lastSignal = signal;
            updateUI();
            
            // Check if signal is too old
            if (signalAgeSeconds > CONFIG.MAX_SIGNAL_AGE_SECONDS) {
                log(`Signal too old (${Math.round(signalAgeSeconds)}s > ${CONFIG.MAX_SIGNAL_AGE_SECONDS}s)`, 'warn');
                return;
            }

            // Check if this is a new signal we haven't processed
            const isNewSignal = signalId !== state.lastProcessedSignalId || force;
            const isNewerTime = signalTime > state.lastProcessedSignalTime;
            
            if ((isNewSignal && isNewerTime) || force) {
                log(`NEW signal: ${signal.direction} ${signal.symbol} (${Math.round(signal.confidence || signal.probability || 0)}%)`, 'success');
                
                // Mark as processed BEFORE executing
                state.lastProcessedSignalId = signalId;
                state.lastProcessedSignalTime = signalTime;
                GM_setValue('lastProcessedSignalId', signalId);
                GM_setValue('lastProcessedSignalTime', signalTime);
                
                // Execute trade if auto-trade is enabled
                if (CONFIG.AUTO_TRADE_ENABLED) {
                    executeTrade(signal);
                } else {
                    log('Auto-trade OFF - signal displayed only', 'warn');
                    playSound('signal');
                }
            } else {
                log(`Same signal (${signalId}) - waiting for new signal`);
            }
            
        } catch (error) {
            state.connectionStatus = 'error';
            state.lastError = 'Parse error';
            log(`Response parse error: ${error.message}`, 'error');
        }
        
        updateUI();
    }

    // ===========================================
    // TRADE EXECUTION
    // ===========================================
    function executeTrade(signal) {
        if (state.isTrading) {
            log('Already executing a trade', 'warn');
            return;
        }

        state.isTrading = true;
        updateUI();
        
        const isCall = signal.direction === 'CALL' || signal.direction === 'BUY';
        const direction = isCall ? 'CALL' : 'PUT';
        
        log(`Executing ${direction} trade...`, 'success');
        
        // Play trade sound
        playSound(isCall ? 'call' : 'put');
        
        // Show notification
        try {
            GM_notification({
                title: `${direction} Signal`,
                text: `${signal.symbol} - ${Math.round(signal.confidence || signal.probability || 0)}% confidence`,
                timeout: 5000
            });
        } catch (e) {
            // Notification may not be available
        }
        
        // Try to click the trade button
        const clicked = clickTradeButton(isCall);
        
        if (clicked) {
            state.tradeCount++;
            GM_setValue('tradeCount', state.tradeCount);
            log(`Trade executed: ${direction}`, 'success');
        } else {
            log('Trade button not found - manual action required', 'error');
        }
        
        // Reset trading state after cooldown
        setTimeout(() => {
            state.isTrading = false;
            updateUI();
            log('Ready for next signal');
        }, CONFIG.COOLDOWN_MS);
    }

    function clickTradeButton(isCall) {
        // Pocket Option specific button selectors (mobile and desktop)
        const callSelectors = [
            '.btn-call',
            '.call-btn', 
            '[class*="btn-call"]',
            '[class*="call"]button',
            '#put-call-buttons-chart-1 .btn-call',
            '.trading-panel__call',
            '[data-testid="call-button"]',
            'button.green',
            '[class*="green"][class*="btn"]'
        ];
        
        const putSelectors = [
            '.btn-put',
            '.put-btn',
            '[class*="btn-put"]',
            '[class*="put"]button',
            '#put-call-buttons-chart-1 .btn-put',
            '.trading-panel__put',
            '[data-testid="put-button"]',
            'button.red',
            '[class*="red"][class*="btn"]'
        ];
        
        const selectors = isCall ? callSelectors : putSelectors;
        
        for (const selector of selectors) {
            try {
                const btn = document.querySelector(selector);
                if (btn && btn.offsetParent !== null) {
                    log(`Found ${isCall ? 'CALL' : 'PUT'} button: ${selector}`);
                    btn.click();
                    return true;
                }
            } catch (e) {
                // Continue to next selector
            }
        }
        
        // Fallback: Find button by text content
        const allButtons = document.querySelectorAll('button, .btn, [role="button"]');
        for (const btn of allButtons) {
            if (btn.offsetParent === null) continue;
            
            const text = (btn.textContent || '').toLowerCase();
            const classes = (btn.className || '').toLowerCase();
            
            if (isCall) {
                if (text.includes('call') || text.includes('up') || text.includes('higher') ||
                    classes.includes('call') || classes.includes('green') || classes.includes('up')) {
                    if (!classes.includes('put') && !text.includes('put')) {
                        log('Found CALL button via fallback');
                        btn.click();
                        return true;
                    }
                }
            } else {
                if (text.includes('put') || text.includes('down') || text.includes('lower') ||
                    classes.includes('put') || classes.includes('red') || classes.includes('down')) {
                    if (!classes.includes('call') && !text.includes('call')) {
                        log('Found PUT button via fallback');
                        btn.click();
                        return true;
                    }
                }
            }
        }
        
        return false;
    }

    // ===========================================
    // SOUND FUNCTIONS
    // ===========================================
    function playSound(type) {
        if (!CONFIG.SOUND_ENABLED) return;
        
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            
            osc.connect(gain);
            gain.connect(ctx.destination);
            
            // Different sounds for different events
            switch (type) {
                case 'call':
                    osc.frequency.value = 880;  // High pitch for CALL
                    gain.gain.value = 0.3;
                    osc.start();
                    setTimeout(() => osc.stop(), 200);
                    break;
                case 'put':
                    osc.frequency.value = 440;  // Low pitch for PUT
                    gain.gain.value = 0.3;
                    osc.start();
                    setTimeout(() => osc.stop(), 200);
                    break;
                case 'signal':
                    osc.frequency.value = 660;  // Medium pitch for new signal
                    gain.gain.value = 0.2;
                    osc.start();
                    setTimeout(() => { osc.frequency.value = 880; }, 100);
                    setTimeout(() => osc.stop(), 200);
                    break;
                case 'test':
                    osc.frequency.value = 523;  // C note
                    gain.gain.value = 0.1;
                    osc.start();
                    setTimeout(() => osc.stop(), 100);
                    break;
            }
        } catch (e) {
            // Audio context may not be available
        }
    }

    // ===========================================
    // POLLING
    // ===========================================
    function startPolling() {
        if (state.pollInterval) {
            clearInterval(state.pollInterval);
        }
        
        state.pollInterval = setInterval(() => {
            fetchSignal(false);
        }, CONFIG.POLL_INTERVAL);
        
        log(`Polling started (every ${CONFIG.POLL_INTERVAL/1000}s)`);
    }

    function stopPolling() {
        if (state.pollInterval) {
            clearInterval(state.pollInterval);
            state.pollInterval = null;
        }
    }

    // ===========================================
    // MANUAL WIN/LOSS RECORDING
    // ===========================================
    window.recordWin = function() {
        state.winCount++;
        GM_setValue('winCount', state.winCount);
        updateUI();
        log('Win recorded!', 'success');
    };

    window.recordLoss = function() {
        state.lossCount++;
        GM_setValue('lossCount', state.lossCount);
        updateUI();
        log('Loss recorded', 'warn');
    };

    // ===========================================
    // INITIALIZATION
    // ===========================================
    function init() {
        log('Initializing GPT Signal Bot v3.0...');
        
        // Wait for page to fully load
        setTimeout(() => {
            createPanel();
            
            // Initial fetch
            fetchSignal(false);
            
            // Start polling
            startPolling();
            
            // Update UI periodically (for signal age, etc.)
            setInterval(updateUI, 1000);
            
            log('Bot initialized and ready!', 'success');
        }, 2500);
    }

    // Start initialization
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
