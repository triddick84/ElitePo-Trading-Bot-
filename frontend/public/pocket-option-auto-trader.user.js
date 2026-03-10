// ==UserScript==
// @name         GPT Signal Bot - Pocket Option Auto Trader
// @namespace    https://signal-executor-7.preview.emergentagent.com
// @version      6.3.0
// @description  Auto-trade OTC forex on Pocket Option. v6.3.0 - Completely rewrote asset switching with verification
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
// @connect      signal-executor-7.preview.emergentagent.com
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
        API_URL: 'https://signal-executor-7.preview.emergentagent.com/api',
        APP_POLL_INTERVAL: 3000,     // 3 seconds for app signals
        SCAN_INTERVAL: 5000,         // 5 seconds for scanning
        TRADE_COOLDOWN_SCAN: 30000,  // 30 seconds between SCAN trades
        TRADE_COOLDOWN_APP: 5000,    // 5 seconds between APP trades
        MIN_CONFIDENCE: 70,
        MIN_PAYOUT: 65,
        DEBUG: true
    };

    // ===========================================
    // STATE - ALL BUTTONS DEFAULT TO OFF
    // ===========================================
    // AUTO = Only for incoming APP signals (does NOT generate trades)
    // SCAN = Tampermonkey generates and places trades
    // SWITCH = Asset switching during SCAN
    // INVERT = Local toggle for direction inversion
    
    let autoEnabled = false;    // Receive APP signals only
    let scanEnabled = false;    // Tampermonkey generates trades
    let switchEnabled = false;  // Switch assets during SCAN
    let invertEnabled = false;  // Local invert toggle
    
    // Trading state
    let isTrading = false;
    let lastAppTradeTime = 0;
    let lastScanTradeTime = 0;
    let lastAppSignalId = '';
    let tradeCount = 0;
    let currentAsset = null;
    
    // Intervals
    let appPollingInterval = null;
    let scanInterval = null;

    // ===========================================
    // SOUND NOTIFICATIONS - TWO DIFFERENT SOUNDS
    // ===========================================
    function playAppSignalSound() {
        // High-pitched beep for APP signals
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 880; // A5 - higher pitch
            osc.type = 'sine';
            gain.gain.value = 0.3;
            osc.start();
            setTimeout(() => { osc.stop(); ctx.close(); }, 150);
        } catch(e) {}
    }

    function playScanSignalSound() {
        // Low-pitched beep for SCAN signals
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 440; // A4 - lower pitch
            osc.type = 'square';
            gain.gain.value = 0.2;
            osc.start();
            setTimeout(() => { osc.stop(); ctx.close(); }, 300);
        } catch(e) {}
    }

    // ===========================================
    // LOGGING
    // ===========================================
    function log(msg) {
        const ts = new Date().toLocaleTimeString();
        console.log(`[GPT v6.3.0] ${ts}: ${msg}`);
        const logEl = document.getElementById('gpt-log');
        if (logEl) logEl.textContent = msg;
    }

    // ===========================================
    // UTILITY FUNCTIONS
    // ===========================================
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function getCurrentAsset() {
        const selectors = ['.pair-title', '.asset-name', '[data-testid="asset-name"]',
                          '.trading-pair-name', '.chart-header-pair'];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.textContent) {
                currentAsset = el.textContent.trim();
                return currentAsset;
            }
        }
        return null;
    }

    function findTradeButtons() {
        const callBtn = document.querySelector('.btn-call');
        const putBtn = document.querySelector('.btn-put');
        return callBtn && putBtn && callBtn.offsetParent !== null;
    }

    // ===========================================
    // UI PANEL
    // ===========================================
    let isMinimized = false;
    
    function createPanel() {
        const existing = document.getElementById('gpt-panel');
        if (existing) existing.remove();

        // Load minimized state
        isMinimized = GM_getValue('isMinimized', false);

        const panel = document.createElement('div');
        panel.id = 'gpt-panel';
        panel.innerHTML = `
            <style>
                #gpt-panel {
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    border: 2px solid #7c3aed;
                    border-radius: 12px;
                    padding: 12px 15px;
                    z-index: 999999;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    color: white;
                    min-width: 320px;
                    box-shadow: 0 4px 25px rgba(124, 58, 237, 0.4);
                    transition: all 0.3s ease;
                    user-select: none;
                }
                #gpt-panel.minimized {
                    min-width: auto;
                    width: auto;
                    padding: 8px 12px;
                }
                #gpt-panel.minimized .panel-content {
                    display: none;
                }
                #gpt-panel .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid rgba(124, 58, 237, 0.3);
                    padding-bottom: 8px;
                    margin-bottom: 10px;
                    cursor: move;
                }
                #gpt-panel.minimized .header {
                    border-bottom: none;
                    padding-bottom: 0;
                    margin-bottom: 0;
                }
                #gpt-panel .header-left {
                    display: flex;
                    align-items: center;
                }
                #gpt-panel .header-right {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                #gpt-panel .title { font-weight: bold; color: #a78bfa; font-size: 14px; }
                #gpt-panel .status-dot { 
                    width: 10px; height: 10px; border-radius: 50%; 
                    background: #ef4444; display: inline-block; margin-right: 8px;
                }
                #gpt-panel .status-dot.connected { background: #22c55e; }
                #gpt-panel .status-dot.trading { background: #f59e0b; animation: blink 0.5s infinite; }
                @keyframes blink { 50% { opacity: 0.3; } }
                
                #gpt-panel .minimize-btn {
                    background: rgba(124, 58, 237, 0.3);
                    border: 1px solid #7c3aed;
                    color: #a78bfa;
                    width: 24px;
                    height: 24px;
                    border-radius: 4px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 14px;
                    font-weight: bold;
                    transition: all 0.2s;
                }
                #gpt-panel .minimize-btn:hover {
                    background: rgba(124, 58, 237, 0.5);
                    transform: scale(1.1);
                }
                
                #gpt-panel .signal-display {
                    background: rgba(0,0,0,0.3);
                    border-radius: 8px;
                    padding: 8px 12px;
                    margin-bottom: 10px;
                    text-align: center;
                }
                #gpt-panel .signal-direction {
                    font-size: 18px;
                    font-weight: bold;
                    padding: 4px 16px;
                    border-radius: 5px;
                    display: inline-block;
                }
                #gpt-panel .signal-direction.call { background: #22c55e; }
                #gpt-panel .signal-direction.put { background: #ef4444; }
                #gpt-panel .signal-direction.wait { background: #64748b; }
                
                #gpt-panel .btn-row {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 8px;
                    margin-bottom: 8px;
                }
                #gpt-panel button {
                    padding: 8px 12px;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 11px;
                    cursor: pointer;
                    transition: all 0.2s;
                    text-transform: uppercase;
                }
                #gpt-panel button:hover { transform: scale(1.02); opacity: 0.9; }
                
                #gpt-panel .btn-auto { background: #6b7280; color: white; }
                #gpt-panel .btn-auto.on { background: #22c55e; }
                #gpt-panel .btn-scan { background: #6b7280; color: white; }
                #gpt-panel .btn-scan.on { background: #ec4899; }
                #gpt-panel .btn-switch { background: #6b7280; color: white; }
                #gpt-panel .btn-switch.on { background: #8b5cf6; }
                #gpt-panel .btn-invert { background: #6b7280; color: white; }
                #gpt-panel .btn-invert.on { background: #f59e0b; }
                #gpt-panel .btn-fetch { background: #3b82f6; color: white; }
                #gpt-panel .btn-reset { background: #ef4444; color: white; }
                
                #gpt-log {
                    font-size: 10px;
                    color: #22c55e;
                    background: rgba(0,0,0,0.3);
                    padding: 6px 10px;
                    border-radius: 4px;
                    margin-top: 8px;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                #gpt-panel .mode-indicator {
                    font-size: 10px;
                    padding: 4px 8px;
                    border-radius: 4px;
                    background: #374151;
                    margin-top: 8px;
                    text-align: center;
                    line-height: 1.4;
                }
                #gpt-panel .mode-indicator.app { background: #065f46; color: #6ee7b7; }
                #gpt-panel .mode-indicator.scan { background: #7c2d12; color: #fed7aa; }
                #gpt-panel .mode-indicator.both { background: #4c1d95; color: #ddd6fe; }
                #gpt-panel .mode-indicator.idle { background: #374151; color: #9ca3af; }
            </style>
            
            <div class="header" id="gpt-drag">
                <div class="header-left">
                    <span class="status-dot" id="gpt-dot"></span>
                    <span class="title">GPT Bot v6.3.0</span>
                </div>
                <div class="header-right">
                    <span style="font-size:10px;color:#64748b;">Trades: <span id="gpt-trades">0</span></span>
                    <button class="minimize-btn" id="gpt-minimize" title="Minimize/Expand">−</button>
                </div>
            </div>
            
            <div class="panel-content" id="gpt-content">
                <div class="signal-display">
                    <div class="signal-direction wait" id="gpt-signal">READY</div>
                    <div style="font-size:11px;color:#94a3b8;margin-top:4px;" id="gpt-asset">-</div>
                    <div style="font-size:10px;color:#64748b;margin-top:2px;" id="gpt-source">-</div>
                </div>
                
                <div class="btn-row">
                    <button class="btn-auto" id="gpt-auto" title="Receive APP signals only">AUTO OFF</button>
                    <button class="btn-scan" id="gpt-scan" title="Tampermonkey generates trades">SCAN OFF</button>
                </div>
                <div class="btn-row">
                    <button class="btn-switch" id="gpt-switch" title="Switch assets during SCAN">SWITCH OFF</button>
                    <button class="btn-invert" id="gpt-invert" title="Invert signal direction">INVERT OFF</button>
                </div>
                <div class="btn-row">
                    <button class="btn-fetch" id="gpt-fetch">FETCH</button>
                    <button class="btn-reset" id="gpt-reset">RESET</button>
                </div>
                
                <div class="mode-indicator idle" id="gpt-mode">IDLE - All buttons OFF</div>
                
                <div id="gpt-log">Ready - v6.2.2</div>
            </div>
        `;

        document.body.appendChild(panel);

        // Button handlers
        document.getElementById('gpt-auto').addEventListener('click', toggleAuto);
        document.getElementById('gpt-scan').addEventListener('click', toggleScan);
        document.getElementById('gpt-switch').addEventListener('click', toggleSwitch);
        document.getElementById('gpt-invert').addEventListener('click', toggleInvert);
        document.getElementById('gpt-fetch').addEventListener('click', handleFetch);
        document.getElementById('gpt-reset').addEventListener('click', resetToDefaults);
        document.getElementById('gpt-minimize').addEventListener('click', toggleMinimize);

        // Make draggable with touch support
        makeDraggable(panel, document.getElementById('gpt-drag'));
        
        // Apply saved position
        const savedPos = GM_getValue('panelPosition', null);
        if (savedPos) {
            panel.style.top = savedPos.top;
            panel.style.left = savedPos.left;
            panel.style.right = 'auto';
        }
        
        // Apply minimized state
        if (isMinimized) {
            panel.classList.add('minimized');
            document.getElementById('gpt-minimize').textContent = '+';
        }
        
        updateAllUI();
    }

    function toggleMinimize() {
        const panel = document.getElementById('gpt-panel');
        const btn = document.getElementById('gpt-minimize');
        
        isMinimized = !isMinimized;
        GM_setValue('isMinimized', isMinimized);
        
        if (isMinimized) {
            panel.classList.add('minimized');
            btn.textContent = '+';
        } else {
            panel.classList.remove('minimized');
            btn.textContent = '−';
        }
    }

    function makeDraggable(panel, handle) {
        let isDragging = false;
        let startX, startY, startLeft, startTop;

        // Mouse events
        handle.addEventListener('mousedown', startDrag);
        document.addEventListener('mousemove', drag);
        document.addEventListener('mouseup', endDrag);
        
        // Touch events for mobile
        handle.addEventListener('touchstart', startDragTouch, { passive: false });
        document.addEventListener('touchmove', dragTouch, { passive: false });
        document.addEventListener('touchend', endDrag);

        function startDrag(e) {
            // Don't drag if clicking minimize button
            if (e.target.id === 'gpt-minimize') return;
            
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            startLeft = panel.offsetLeft;
            startTop = panel.offsetTop;
            e.preventDefault();
        }

        function startDragTouch(e) {
            if (e.target.id === 'gpt-minimize') return;
            
            isDragging = true;
            const touch = e.touches[0];
            startX = touch.clientX;
            startY = touch.clientY;
            startLeft = panel.offsetLeft;
            startTop = panel.offsetTop;
            e.preventDefault();
        }

        function drag(e) {
            if (!isDragging) return;
            
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            
            panel.style.left = (startLeft + dx) + 'px';
            panel.style.top = (startTop + dy) + 'px';
            panel.style.right = 'auto';
        }

        function dragTouch(e) {
            if (!isDragging) return;
            
            const touch = e.touches[0];
            const dx = touch.clientX - startX;
            const dy = touch.clientY - startY;
            
            panel.style.left = (startLeft + dx) + 'px';
            panel.style.top = (startTop + dy) + 'px';
            panel.style.right = 'auto';
            e.preventDefault();
        }

        function endDrag() {
            if (isDragging) {
                isDragging = false;
                // Save position
                GM_setValue('panelPosition', {
                    top: panel.style.top,
                    left: panel.style.left
                });
            }
        }
    }

    // ===========================================
    // BUTTON HANDLERS
    // ===========================================
    function toggleAuto() {
        autoEnabled = !autoEnabled;
        GM_setValue('autoEnabled', autoEnabled);
        updateAllUI();
        manageIntervals();
        log(`AUTO: ${autoEnabled ? 'ON (receiving app signals)' : 'OFF'}`);
    }

    function toggleScan() {
        scanEnabled = !scanEnabled;
        GM_setValue('scanEnabled', scanEnabled);
        updateAllUI();
        manageIntervals();
        log(`SCAN: ${scanEnabled ? 'ON (generating trades)' : 'OFF'}`);
    }

    function toggleSwitch() {
        switchEnabled = !switchEnabled;
        GM_setValue('switchEnabled', switchEnabled);
        updateAllUI();
        log(`SWITCH: ${switchEnabled ? 'ON (scan all favorites)' : 'OFF (current asset only)'}`);
    }

    function toggleInvert() {
        invertEnabled = !invertEnabled;
        GM_setValue('invertEnabled', invertEnabled);
        updateAllUI();
        log(`INVERT: ${invertEnabled ? 'ON' : 'OFF'}`);
    }

    function handleFetch() {
        if (scanEnabled) {
            log('FETCH: Forcing scan...');
            doScan(true);
        } else if (autoEnabled) {
            log('FETCH: Checking app signals...');
            checkAppSignals(true);
        } else {
            log('FETCH: Enable AUTO or SCAN first');
        }
    }

    function resetToDefaults() {
        autoEnabled = false;
        scanEnabled = false;
        switchEnabled = false;
        invertEnabled = false;
        isTrading = false;
        lastAppSignalId = '';
        lastAppTradeTime = 0;
        lastScanTradeTime = 0;
        
        GM_setValue('autoEnabled', false);
        GM_setValue('scanEnabled', false);
        GM_setValue('switchEnabled', false);
        GM_setValue('invertEnabled', false);
        
        updateAllUI();
        manageIntervals();
        updateSignalDisplay('READY', null, 'wait', '-');
        
        log('RESET: All buttons OFF');
    }

    // ===========================================
    // UI UPDATES
    // ===========================================
    function updateAllUI() {
        updateButtonStates();
        updateModeIndicator();
    }

    function updateButtonStates() {
        const autoBtn = document.getElementById('gpt-auto');
        const scanBtn = document.getElementById('gpt-scan');
        const switchBtn = document.getElementById('gpt-switch');
        const invertBtn = document.getElementById('gpt-invert');

        if (autoBtn) {
            autoBtn.textContent = autoEnabled ? 'AUTO ON' : 'AUTO OFF';
            autoBtn.className = 'btn-auto' + (autoEnabled ? ' on' : '');
        }
        if (scanBtn) {
            scanBtn.textContent = scanEnabled ? 'SCAN ON' : 'SCAN OFF';
            scanBtn.className = 'btn-scan' + (scanEnabled ? ' on' : '');
        }
        if (switchBtn) {
            switchBtn.textContent = switchEnabled ? 'SWITCH ON' : 'SWITCH OFF';
            switchBtn.className = 'btn-switch' + (switchEnabled ? ' on' : '');
        }
        if (invertBtn) {
            invertBtn.textContent = invertEnabled ? 'INVERT ON' : 'INVERT OFF';
            invertBtn.className = 'btn-invert' + (invertEnabled ? ' on' : '');
        }
    }

    function updateModeIndicator() {
        const modeEl = document.getElementById('gpt-mode');
        if (!modeEl) return;

        if (autoEnabled && scanEnabled && switchEnabled) {
            // All three ON - only Tampermonkey trades (SWITCH changes assets)
            modeEl.textContent = '🔍 SCAN ONLY MODE (SWITCH overrides APP)';
            modeEl.className = 'mode-indicator scan';
        } else if (autoEnabled && scanEnabled) {
            // AUTO + SCAN - both sources on current asset
            modeEl.textContent = '📡+🔍 BOTH: App signals + Tampermonkey scan';
            modeEl.className = 'mode-indicator both';
        } else if (scanEnabled && switchEnabled) {
            // SCAN + SWITCH - Tampermonkey scans all favorites
            modeEl.textContent = '🔍 SCAN: All favorites (switching assets)';
            modeEl.className = 'mode-indicator scan';
        } else if (scanEnabled) {
            // SCAN only - Tampermonkey on current asset
            modeEl.textContent = '🔍 SCAN: Current asset only';
            modeEl.className = 'mode-indicator scan';
        } else if (autoEnabled) {
            // AUTO only - app signals
            modeEl.textContent = '📡 APP SIGNALS: Waiting for incoming signals';
            modeEl.className = 'mode-indicator app';
        } else {
            modeEl.textContent = 'IDLE - Enable AUTO or SCAN to start';
            modeEl.className = 'mode-indicator idle';
        }
    }

    function updateSignalDisplay(direction, asset, type, source) {
        const sigEl = document.getElementById('gpt-signal');
        const assetEl = document.getElementById('gpt-asset');
        const sourceEl = document.getElementById('gpt-source');
        
        if (sigEl) {
            sigEl.textContent = direction;
            sigEl.className = 'signal-direction ' + type;
        }
        if (assetEl) {
            assetEl.textContent = asset || getCurrentAsset() || '-';
        }
        if (sourceEl) {
            sourceEl.textContent = source || '-';
        }
    }

    function updateStatusDot(status) {
        const dot = document.getElementById('gpt-dot');
        if (dot) dot.className = 'status-dot ' + status;
    }

    function incrementTradeCount() {
        tradeCount++;
        const el = document.getElementById('gpt-trades');
        if (el) el.textContent = tradeCount;
    }

    // ===========================================
    // INTERVAL MANAGEMENT
    // ===========================================
    function manageIntervals() {
        // Clear existing intervals
        if (appPollingInterval) {
            clearInterval(appPollingInterval);
            appPollingInterval = null;
        }
        if (scanInterval) {
            clearInterval(scanInterval);
            scanInterval = null;
        }

        // Start APP signal polling if AUTO is enabled
        // (regardless of SCAN/SWITCH, unless all three are ON)
        if (autoEnabled && !(autoEnabled && scanEnabled && switchEnabled)) {
            log('Starting app signal polling...');
            appPollingInterval = setInterval(() => checkAppSignals(false), CONFIG.APP_POLL_INTERVAL);
            checkAppSignals(false);
        }

        // Start SCAN if enabled
        if (scanEnabled) {
            log('Starting scan...');
            scanInterval = setInterval(() => doScan(false), CONFIG.SCAN_INTERVAL);
            doScan(false);
        }

        updateStatusDot(autoEnabled || scanEnabled ? 'connected' : '');
    }

    // ===========================================
    // APP SIGNAL HANDLING (AUTO button)
    // ===========================================
    function checkAppSignals(force = false) {
        // Skip if all three buttons are ON (SWITCH overrides)
        if (autoEnabled && scanEnabled && switchEnabled) {
            return;
        }

        if (!autoEnabled) return;
        if (isTrading && !force) return;

        // Check cooldown
        const now = Date.now();
        if (!force && (now - lastAppTradeTime) < CONFIG.TRADE_COOLDOWN_APP) {
            return;
        }

        GM_xmlhttpRequest({
            method: 'GET',
            url: CONFIG.API_URL + '/signals/latest',
            headers: { 'Accept': 'application/json' },
            timeout: 5000,
            onload: function(res) {
                try {
                    if (res.status !== 200) return;

                    const data = JSON.parse(res.responseText);
                    
                    if (data.success && data.signal) {
                        const signal = data.signal;
                        const signalId = signal.id || signal.timestamp || `${signal.symbol}_${Date.now()}`;
                        
                        // Check if new signal
                        if (signalId === lastAppSignalId && !force) {
                            return;
                        }

                        log(`📡 APP SIGNAL: ${signal.direction} ${signal.symbol}`);
                        lastAppSignalId = signalId;

                        executeAppTrade(signal);
                    }
                } catch (e) {
                    log('Parse error: ' + e.message);
                }
            },
            onerror: function() {
                updateStatusDot('');
            }
        });
    }

    async function executeAppTrade(signal) {
        if (isTrading) {
            log('Already trading');
            return;
        }

        isTrading = true;
        updateStatusDot('trading');
        
        // Determine direction with local invert
        let direction = (signal.direction || '').toUpperCase();
        let isCall = direction === 'CALL' || direction === 'BUY' || direction === 'UP';
        
        if (invertEnabled) {
            isCall = !isCall;
            log(`🔄 INVERTED: ${direction} → ${isCall ? 'CALL' : 'PUT'}`);
        }

        const finalDirection = isCall ? 'CALL' : 'PUT';
        updateSignalDisplay(finalDirection, signal.symbol, isCall ? 'call' : 'put', '📡 APP');

        // Play APP sound
        playAppSignalSound();

        // Wait for buttons
        if (!findTradeButtons()) {
            await sleep(1000);
            if (!findTradeButtons()) {
                log('Buttons not found');
                isTrading = false;
                updateStatusDot('connected');
                return;
            }
        }

        // Click button
        const clicked = clickTradeButton(isCall);
        
        if (clicked) {
            incrementTradeCount();
            lastAppTradeTime = Date.now();
            log(`✅ APP TRADE: ${finalDirection} on ${signal.symbol}`);
            
            try {
                GM_notification({
                    title: `📡 App Signal: ${finalDirection}`,
                    text: `${signal.symbol}`,
                    timeout: 3000
                });
            } catch(e) {}
        }

        setTimeout(() => {
            isTrading = false;
            updateStatusDot('connected');
        }, 2000);
    }

    // ===========================================
    // SCAN HANDLING (SCAN button)
    // ===========================================
    function doScan(force = false) {
        if (!scanEnabled) return;
        if (isTrading && !force) return;

        // Check 30-second cooldown for scan
        const now = Date.now();
        if (!force && (now - lastScanTradeTime) < CONFIG.TRADE_COOLDOWN_SCAN) {
            const remaining = Math.round((CONFIG.TRADE_COOLDOWN_SCAN - (now - lastScanTradeTime)) / 1000);
            if (remaining % 10 === 0) log(`Scan cooldown: ${remaining}s`);
            return;
        }

        log('🔍 Scanning markets...');
        updateStatusDot('trading');

        // Determine scope based on SWITCH
        const scope = switchEnabled ? 'favorites' : 'current';
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: CONFIG.API_URL + `/signals/scan-markets?scope=${scope}&min_confidence=${CONFIG.MIN_CONFIDENCE}&min_payout=${CONFIG.MIN_PAYOUT}`,
            headers: { 'Accept': 'application/json' },
            timeout: 15000,
            onload: function(res) {
                try {
                    if (res.status !== 200) {
                        log('Scan API error: ' + res.status);
                        updateStatusDot('connected');
                        return;
                    }

                    const data = JSON.parse(res.responseText);
                    
                    // API returns top_signals not signals
                    const signals = data.top_signals || data.signals || [];
                    
                    if (data.success && signals.length > 0) {
                        log(`Found ${signals.length} signals`);
                        
                        let bestSignal = null;
                        
                        if (switchEnabled) {
                            // Can use any signal from favorites - pick highest confidence
                            bestSignal = signals[0];
                            log(`SWITCH ON: Using best signal from ${bestSignal.symbol}`);
                        } else {
                            // Must match current asset
                            const currentNorm = normalizeAsset(getCurrentAsset());
                            log(`SWITCH OFF: Looking for signals matching ${currentNorm}`);
                            
                            for (const sig of signals) {
                                const sigNorm = normalizeAsset(sig.symbol);
                                if (sigNorm === currentNorm || sigNorm.includes(currentNorm) || currentNorm.includes(sigNorm)) {
                                    bestSignal = sig;
                                    break;
                                }
                            }
                            
                            if (!bestSignal) {
                                log(`No signal for current asset. Available: ${signals.map(s => s.symbol).join(', ')}`);
                                updateStatusDot('connected');
                                return;
                            }
                        }

                        if (bestSignal) {
                            log(`🔍 SCAN SIGNAL: ${bestSignal.direction} ${bestSignal.symbol} (${bestSignal.confidence}%)`);
                            executeScanTrade(bestSignal);
                        }
                    } else {
                        log('No signals found in scan');
                        updateStatusDot('connected');
                    }
                } catch (e) {
                    log('Scan error: ' + e.message);
                    console.error('[GPT SCAN ERROR]', e);
                    updateStatusDot('connected');
                }
            },
            onerror: function(e) {
                log('Scan connection error');
                console.error('[GPT SCAN]', e);
                updateStatusDot('connected');
            },
            ontimeout: function() {
                log('Scan timeout');
                updateStatusDot('connected');
            }
        });
    }

    function normalizeAsset(asset) {
        if (!asset) return '';
        return asset.replace(/[^A-Z0-9]/gi, '').toUpperCase();
    }

    async function executeScanTrade(signal) {
        if (isTrading) {
            log('Already trading');
            return;
        }

        isTrading = true;
        updateStatusDot('trading');

        // Switch asset if SWITCH enabled
        if (switchEnabled && signal.symbol) {
            const switched = await switchToAsset(signal.symbol);
            if (!switched) {
                log('Asset switch failed');
                isTrading = false;
                updateStatusDot('connected');
                return;
            }
            await sleep(500);
        }

        // Determine direction with local invert
        let direction = (signal.direction || '').toUpperCase();
        let isCall = direction === 'CALL' || direction === 'BUY' || direction === 'UP';
        
        if (invertEnabled) {
            isCall = !isCall;
            log(`🔄 INVERTED: ${direction} → ${isCall ? 'CALL' : 'PUT'}`);
        }

        const finalDirection = isCall ? 'CALL' : 'PUT';
        updateSignalDisplay(finalDirection, signal.symbol, isCall ? 'call' : 'put', '🔍 SCAN');

        // Play SCAN sound (different from APP)
        playScanSignalSound();

        // Wait for buttons
        if (!findTradeButtons()) {
            await sleep(1000);
            if (!findTradeButtons()) {
                log('Buttons not found');
                isTrading = false;
                updateStatusDot('connected');
                return;
            }
        }

        // Click button
        const clicked = clickTradeButton(isCall);
        
        if (clicked) {
            incrementTradeCount();
            lastScanTradeTime = Date.now();
            log(`✅ SCAN TRADE: ${finalDirection} on ${signal.symbol}`);
            
            try {
                GM_notification({
                    title: `🔍 Scan Signal: ${finalDirection}`,
                    text: `${signal.symbol}`,
                    timeout: 3000
                });
            } catch(e) {}
        }

        setTimeout(() => {
            isTrading = false;
            updateStatusDot('connected');
        }, 2000);
    }

    // ===========================================
    // TRADE EXECUTION
    // ===========================================
    function clickTradeButton(isCall) {
        const selector = isCall ? '.btn-call' : '.btn-put';
        const btn = document.querySelector(selector);
        
        if (btn && btn.offsetParent !== null) {
            log(`Clicking ${isCall ? 'CALL' : 'PUT'}`);
            btn.click();
            return true;
        }
        
        log('Button not found: ' + selector);
        return false;
    }

    // ===========================================
    // ASSET SWITCHING - For Pocket Option
    // ===========================================
    async function switchToAsset(targetAsset) {
        log(`🔄 Switching to ${targetAsset}...`);
        
        // Get current asset before switch attempt
        const assetBefore = getCurrentAsset();
        log(`Current asset: ${assetBefore}`);
        
        // Clean up asset name for matching
        const searchTerm = targetAsset.replace('_OTC', '').replace('_', '');
        const targetNorm = normalizeAsset(targetAsset);
        
        // Check if already on correct asset
        if (assetBefore && normalizeAsset(assetBefore).includes(targetNorm.substring(0, 6))) {
            log(`Already on ${assetBefore}, no switch needed`);
            return true;
        }
        
        try {
            // Step 1: Click the asset selector to open dropdown
            log('Step 1: Opening asset selector...');
            
            // Find clickable element showing current pair
            let selectorClicked = false;
            const allElements = document.querySelectorAll('*');
            
            for (const el of allElements) {
                if (el && el.offsetParent !== null && 
                    el.children.length <= 3 &&
                    el.textContent && 
                    el.textContent.trim().length < 30) {
                    
                    const text = el.textContent.trim().toUpperCase();
                    // Look for element showing current asset
                    if ((text.includes('/') && (text.includes('USD') || text.includes('EUR') || text.includes('GBP'))) ||
                        text.includes('OTC')) {
                        
                        // Make sure it's clickable (has cursor pointer or is a button-like element)
                        const style = window.getComputedStyle(el);
                        if (style.cursor === 'pointer' || el.tagName === 'BUTTON' || el.onclick || 
                            el.classList.contains('pair') || el.classList.contains('asset')) {
                            
                            log(`Clicking: "${text.substring(0, 20)}"`);
                            el.click();
                            selectorClicked = true;
                            await sleep(1000);
                            break;
                        }
                    }
                }
            }
            
            if (!selectorClicked) {
                // Fallback: try common selectors
                const fallbackSelectors = ['.pair-title', '.current-symbol', '[class*="pair"]', '[class*="asset-name"]'];
                for (const sel of fallbackSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.offsetParent !== null) {
                        log(`Fallback click: ${sel}`);
                        el.click();
                        selectorClicked = true;
                        await sleep(1000);
                        break;
                    }
                }
            }
            
            if (!selectorClicked) {
                log('❌ Could not open asset selector');
                return false;
            }
            
            // Step 2: Find and use search input
            log('Step 2: Looking for search input...');
            await sleep(500);
            
            // Find any visible input field
            const inputs = document.querySelectorAll('input');
            let searchInput = null;
            
            for (const inp of inputs) {
                if (inp && inp.offsetParent !== null && !inp.disabled && inp.offsetWidth > 30) {
                    searchInput = inp;
                    log(`Found input: type="${inp.type}", placeholder="${inp.placeholder}"`);
                    break;
                }
            }
            
            if (searchInput) {
                // Clear and type
                searchInput.focus();
                searchInput.value = '';
                await sleep(100);
                
                // Type the search term
                log(`Typing: ${searchTerm}`);
                searchInput.value = searchTerm;
                searchInput.dispatchEvent(new Event('input', { bubbles: true }));
                searchInput.dispatchEvent(new Event('change', { bubbles: true }));
                
                await sleep(800);
                log(`Input value: ${searchInput.value}`);
            } else {
                log('No search input found');
            }
            
            // Step 3: Find and click the target asset in results
            log('Step 3: Looking for asset in list...');
            await sleep(500);
            
            // Look for any element containing the asset name
            let assetClicked = false;
            const searchTermUpper = searchTerm.toUpperCase();
            const allElems = document.querySelectorAll('*');
            
            for (const el of allElems) {
                if (!el || !el.offsetParent || el.children.length > 5) continue;
                
                const text = (el.textContent || '').toUpperCase().trim();
                if (text.length > 50 || text.length < 3) continue;
                
                // Check if this element contains our asset
                if (text.includes(searchTermUpper) || 
                    text.includes(searchTerm.substring(0,3) + '/' + searchTerm.substring(3))) {
                    
                    // Make sure it's in a list/dropdown area (not the header)
                    const rect = el.getBoundingClientRect();
                    if (rect.top > 100 && rect.height < 100 && rect.height > 10) {
                        log(`Clicking result: "${text.substring(0, 25)}"`);
                        
                        // Click it
                        el.click();
                        await sleep(300);
                        
                        // Try double click too
                        el.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
                        await sleep(500);
                        
                        assetClicked = true;
                        break;
                    }
                }
            }
            
            if (!assetClicked) {
                log('❌ Could not find asset in list');
                // Try pressing Escape to close dropdown
                document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
                return false;
            }
            
            // Step 4: Verify the switch worked
            await sleep(1000);
            const assetAfter = getCurrentAsset();
            log(`Asset after switch: ${assetAfter}`);
            
            if (assetAfter && normalizeAsset(assetAfter).includes(targetNorm.substring(0, 6))) {
                log(`✅ Successfully switched to ${assetAfter}`);
                return true;
            } else {
                log(`❌ Switch failed - still on ${assetAfter}`);
                return false;
            }
            
        } catch (e) {
            log(`Switch error: ${e.message}`);
            console.error('[GPT SWITCH]', e);
            return false;
        }
    }

    // ===========================================
    // INITIALIZATION
    // ===========================================
    function init() {
        log('Initializing v6.3.0...');

        // Load saved settings (all default to false)
        autoEnabled = GM_getValue('autoEnabled', false);
        scanEnabled = GM_getValue('scanEnabled', false);
        switchEnabled = GM_getValue('switchEnabled', false);
        invertEnabled = GM_getValue('invertEnabled', false);

        setTimeout(() => {
            createPanel();
            getCurrentAsset();
            manageIntervals();
            log('Ready! All buttons OFF by default');
        }, 2000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
