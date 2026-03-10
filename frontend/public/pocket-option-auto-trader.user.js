// ==UserScript==
// @name         GPT Signal Bot - Pocket Option Auto Trader
// @namespace    https://signal-executor-7.preview.emergentagent.com
// @version      6.0.0
// @description  Auto-trade OTC forex on Pocket Option. v6.0.0 - Complete rewrite with proper button logic
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
        POLL_INTERVAL: 3000,      // 3 seconds - fast polling for incoming signals
        SCAN_INTERVAL: 5000,      // 5 seconds for scanning
        TRADE_COOLDOWN_SCAN: 30000,  // 30 seconds between scan trades
        TRADE_COOLDOWN_APP: 5000,    // 5 seconds between app signal trades
        MIN_CONFIDENCE: 70,
        MIN_PAYOUT: 65,
        DEBUG: true
    };

    // ===========================================
    // STATE - ALL BUTTONS DEFAULT TO OFF
    // ===========================================
    let autoTradeEnabled = false;   // Auto Trade button - for app signals only
    let switchEnabled = false;      // Switch button - allows asset switching during scan
    let scanEnabled = false;        // Scan button - Tampermonkey scans for signals
    let invertEnabled = false;      // Invert button - LOCAL toggle (overrides app)
    
    // Trading state
    let isTrading = false;
    let isScanning = false;
    let lastTradeTime = 0;
    let lastAppSignalId = '';
    let lastAppSignalTime = 0;
    let tradeCount = 0;
    let currentAsset = null;
    let buttonsReady = false;
    
    // Intervals
    let pollingInterval = null;
    let scanInterval = null;

    // ===========================================
    // SOUND NOTIFICATIONS - TWO DIFFERENT SOUNDS
    // ===========================================
    function playAppSignalSound() {
        // Higher pitched, shorter beep for app signals
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
            setTimeout(() => {
                osc.stop();
                ctx.close();
            }, 150);
        } catch(e) { console.log('Sound error:', e); }
    }

    function playScanSignalSound() {
        // Lower pitched, longer beep for scan signals
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
            setTimeout(() => {
                osc.stop();
                ctx.close();
            }, 300);
        } catch(e) { console.log('Sound error:', e); }
    }

    // ===========================================
    // LOGGING
    // ===========================================
    function log(msg) {
        const ts = new Date().toLocaleTimeString();
        console.log(`[GPT v6.0.0] ${ts}: ${msg}`);
        const logEl = document.getElementById('gpt-log');
        if (logEl) logEl.textContent = msg;
    }

    // ===========================================
    // ASSET DETECTION
    // ===========================================
    function getCurrentAsset() {
        const selectors = [
            '.pair-title', '.asset-name', '[data-testid="asset-name"]',
            '.trading-pair-name', '.chart-header-pair'
        ];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.textContent) {
                currentAsset = el.textContent.trim();
                return currentAsset;
            }
        }
        return null;
    }

    // ===========================================
    // BUTTON DETECTION
    // ===========================================
    function findTradeButtons() {
        const callBtn = document.querySelector('.btn-call');
        const putBtn = document.querySelector('.btn-put');
        buttonsReady = callBtn && putBtn && callBtn.offsetParent !== null;
        return buttonsReady;
    }

    // ===========================================
    // UI PANEL
    // ===========================================
    function createPanel() {
        const existing = document.getElementById('gpt-panel');
        if (existing) existing.remove();

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
                #gpt-panel .title { font-weight: bold; color: #a78bfa; font-size: 14px; }
                #gpt-panel .status-dot { 
                    width: 10px; height: 10px; border-radius: 50%; 
                    background: #ef4444; display: inline-block; margin-right: 8px;
                }
                #gpt-panel .status-dot.connected { background: #22c55e; }
                #gpt-panel .status-dot.trading { background: #f59e0b; animation: blink 0.5s infinite; }
                @keyframes blink { 50% { opacity: 0.3; } }
                
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
                #gpt-panel .btn-switch { background: #6b7280; color: white; }
                #gpt-panel .btn-switch.on { background: #8b5cf6; }
                #gpt-panel .btn-scan { background: #6b7280; color: white; }
                #gpt-panel .btn-scan.on { background: #ec4899; }
                #gpt-panel .btn-invert { background: #6b7280; color: white; }
                #gpt-panel .btn-invert.on { background: #f59e0b; }
                #gpt-panel .btn-fetch { background: #3b82f6; color: white; }
                #gpt-panel .btn-reset { background: #ef4444; color: white; }
                
                #gpt-panel .info-row {
                    display: flex;
                    justify-content: space-between;
                    font-size: 11px;
                    color: #94a3b8;
                    margin-top: 8px;
                }
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
                    padding: 3px 8px;
                    border-radius: 4px;
                    background: #374151;
                    margin-top: 8px;
                    text-align: center;
                }
                #gpt-panel .mode-indicator.app { background: #065f46; color: #6ee7b7; }
                #gpt-panel .mode-indicator.scan { background: #7c2d12; color: #fed7aa; }
                #gpt-panel .mode-indicator.idle { background: #374151; color: #9ca3af; }
            </style>
            
            <div class="header" id="gpt-drag">
                <div>
                    <span class="status-dot" id="gpt-dot"></span>
                    <span class="title">GPT Bot v6.0.0</span>
                </div>
                <span style="font-size:10px;color:#64748b;">Trades: <span id="gpt-trades">0</span></span>
            </div>
            
            <div class="signal-display">
                <div class="signal-direction wait" id="gpt-signal">READY</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;" id="gpt-asset">-</div>
            </div>
            
            <div class="btn-row">
                <button class="btn-auto" id="gpt-auto">AUTO OFF</button>
                <button class="btn-switch" id="gpt-switch">SWITCH OFF</button>
            </div>
            <div class="btn-row">
                <button class="btn-scan" id="gpt-scan">SCAN OFF</button>
                <button class="btn-invert" id="gpt-invert">INVERT OFF</button>
            </div>
            <div class="btn-row">
                <button class="btn-fetch" id="gpt-fetch">FETCH</button>
                <button class="btn-reset" id="gpt-reset">RESET</button>
            </div>
            
            <div class="mode-indicator idle" id="gpt-mode">IDLE - Enable buttons to start</div>
            
            <div id="gpt-log">Initialized - All buttons OFF by default</div>
        `;

        document.body.appendChild(panel);

        // Button handlers
        document.getElementById('gpt-auto').addEventListener('click', toggleAutoTrade);
        document.getElementById('gpt-switch').addEventListener('click', toggleSwitch);
        document.getElementById('gpt-scan').addEventListener('click', toggleScan);
        document.getElementById('gpt-invert').addEventListener('click', toggleInvert);
        document.getElementById('gpt-fetch').addEventListener('click', handleFetch);
        document.getElementById('gpt-reset').addEventListener('click', resetToDefaults);

        // Make draggable
        makeDraggable(panel, document.getElementById('gpt-drag'));
        
        // Update UI
        updateButtonStates();
        updateModeIndicator();
    }

    function makeDraggable(panel, handle) {
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
        handle.onmousedown = dragMouseDown;

        function dragMouseDown(e) {
            e.preventDefault();
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;
        }

        function elementDrag(e) {
            e.preventDefault();
            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;
            panel.style.top = (panel.offsetTop - pos2) + "px";
            panel.style.left = (panel.offsetLeft - pos1) + "px";
            panel.style.right = 'auto';
        }

        function closeDragElement() {
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }

    // ===========================================
    // BUTTON TOGGLE FUNCTIONS
    // ===========================================
    function toggleAutoTrade() {
        autoTradeEnabled = !autoTradeEnabled;
        GM_setValue('autoTradeEnabled', autoTradeEnabled);
        updateButtonStates();
        updateModeIndicator();
        startOrStopPolling();
        log(`Auto Trade: ${autoTradeEnabled ? 'ON' : 'OFF'}`);
    }

    function toggleSwitch() {
        switchEnabled = !switchEnabled;
        GM_setValue('switchEnabled', switchEnabled);
        updateButtonStates();
        updateModeIndicator();
        log(`Switch: ${switchEnabled ? 'ON' : 'OFF'}`);
    }

    function toggleScan() {
        scanEnabled = !scanEnabled;
        GM_setValue('scanEnabled', scanEnabled);
        updateButtonStates();
        updateModeIndicator();
        startOrStopScanning();
        log(`Scan: ${scanEnabled ? 'ON' : 'OFF'}`);
    }

    function toggleInvert() {
        invertEnabled = !invertEnabled;
        GM_setValue('invertEnabled', invertEnabled);
        updateButtonStates();
        log(`Invert: ${invertEnabled ? 'ON' : 'OFF'} (LOCAL override)`);
    }

    function handleFetch() {
        if (scanEnabled) {
            // Scan mode - force scan for signals
            log('FETCH: Forcing scan...');
            scanForSignals(true);
        } else {
            // Non-scan mode - check for app signals
            log('FETCH: Checking app signals...');
            checkAppSignals(true);
        }
    }

    function resetToDefaults() {
        autoTradeEnabled = false;
        switchEnabled = false;
        scanEnabled = false;
        invertEnabled = false;
        isTrading = false;
        isScanning = false;
        lastAppSignalId = '';
        lastTradeTime = 0;
        
        GM_setValue('autoTradeEnabled', false);
        GM_setValue('switchEnabled', false);
        GM_setValue('scanEnabled', false);
        GM_setValue('invertEnabled', false);
        
        updateButtonStates();
        updateModeIndicator();
        startOrStopPolling();
        startOrStopScanning();
        
        log('RESET: All settings restored to defaults');
        updateSignalDisplay('READY', null, 'wait');
    }

    function updateButtonStates() {
        const autoBtn = document.getElementById('gpt-auto');
        const switchBtn = document.getElementById('gpt-switch');
        const scanBtn = document.getElementById('gpt-scan');
        const invertBtn = document.getElementById('gpt-invert');

        if (autoBtn) {
            autoBtn.textContent = autoTradeEnabled ? 'AUTO ON' : 'AUTO OFF';
            autoBtn.className = 'btn-auto' + (autoTradeEnabled ? ' on' : '');
        }
        if (switchBtn) {
            switchBtn.textContent = switchEnabled ? 'SWITCH ON' : 'SWITCH OFF';
            switchBtn.className = 'btn-switch' + (switchEnabled ? ' on' : '');
        }
        if (scanBtn) {
            scanBtn.textContent = scanEnabled ? 'SCAN ON' : 'SCAN OFF';
            scanBtn.className = 'btn-scan' + (scanEnabled ? ' on' : '');
        }
        if (invertBtn) {
            invertBtn.textContent = invertEnabled ? 'INVERT ON' : 'INVERT OFF';
            invertBtn.className = 'btn-invert' + (invertEnabled ? ' on' : '');
        }
    }

    function updateModeIndicator() {
        const modeEl = document.getElementById('gpt-mode');
        if (!modeEl) return;

        // Determine current mode based on button states
        if (autoTradeEnabled && !scanEnabled && !switchEnabled) {
            modeEl.textContent = '📡 APP SIGNALS MODE - Waiting for signals';
            modeEl.className = 'mode-indicator app';
        } else if (scanEnabled) {
            const scope = switchEnabled ? 'ALL FAVORITES' : 'CURRENT ASSET';
            modeEl.textContent = `🔍 SCAN MODE - Scanning ${scope}`;
            modeEl.className = 'mode-indicator scan';
        } else if (!autoTradeEnabled && !scanEnabled) {
            modeEl.textContent = 'IDLE - Enable AUTO for app signals or SCAN for scanning';
            modeEl.className = 'mode-indicator idle';
        } else {
            modeEl.textContent = 'STANDBY - Adjust settings';
            modeEl.className = 'mode-indicator idle';
        }
    }

    function updateSignalDisplay(direction, asset, type = 'wait') {
        const sigEl = document.getElementById('gpt-signal');
        const assetEl = document.getElementById('gpt-asset');
        
        if (sigEl) {
            sigEl.textContent = direction;
            sigEl.className = 'signal-direction ' + type;
        }
        if (assetEl) {
            assetEl.textContent = asset || getCurrentAsset() || '-';
        }
    }

    function updateStatusDot(status) {
        const dot = document.getElementById('gpt-dot');
        if (dot) {
            dot.className = 'status-dot ' + status;
        }
    }

    function updateTradeCount() {
        const el = document.getElementById('gpt-trades');
        if (el) el.textContent = tradeCount;
    }

    // ===========================================
    // POLLING FOR APP SIGNALS
    // ===========================================
    function startOrStopPolling() {
        // Clear existing interval
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }

        // Only poll for app signals when:
        // - AUTO is ON
        // - SCAN is OFF
        // - SWITCH is OFF
        if (autoTradeEnabled && !scanEnabled && !switchEnabled) {
            log('Starting app signal polling...');
            pollingInterval = setInterval(() => checkAppSignals(false), CONFIG.POLL_INTERVAL);
            checkAppSignals(false); // Immediate check
        }
    }

    function checkAppSignals(force = false) {
        // Only process app signals when AUTO ON, SCAN OFF, SWITCH OFF
        if (!autoTradeEnabled || scanEnabled || switchEnabled) {
            if (force) log('App signals require: AUTO ON, SCAN OFF, SWITCH OFF');
            return;
        }

        if (isTrading && !force) {
            return;
        }

        updateStatusDot('connected');

        GM_xmlhttpRequest({
            method: 'GET',
            url: CONFIG.API_URL + '/signals/latest',
            headers: { 'Accept': 'application/json' },
            timeout: 5000,
            onload: function(res) {
                try {
                    if (res.status !== 200) {
                        updateStatusDot('');
                        return;
                    }

                    const data = JSON.parse(res.responseText);
                    
                    if (data.success && data.signal) {
                        const signal = data.signal;
                        const signalId = signal.id || signal.timestamp || `${signal.symbol}_${Date.now()}`;
                        
                        // Check if new signal
                        const now = Date.now();
                        if (signalId === lastAppSignalId && (now - lastAppSignalTime) < 10000) {
                            // Same signal within 10 seconds
                            return;
                        }

                        // Check trade cooldown
                        if ((now - lastTradeTime) < CONFIG.TRADE_COOLDOWN_APP && !force) {
                            log(`Cooldown: ${Math.round((CONFIG.TRADE_COOLDOWN_APP - (now - lastTradeTime))/1000)}s`);
                            return;
                        }

                        log(`📡 APP SIGNAL: ${signal.direction} ${signal.symbol}`);
                        lastAppSignalId = signalId;
                        lastAppSignalTime = now;

                        // Execute trade
                        executeAppSignalTrade(signal);
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

    // ===========================================
    // SCANNING FOR SIGNALS
    // ===========================================
    function startOrStopScanning() {
        // Clear existing interval
        if (scanInterval) {
            clearInterval(scanInterval);
            scanInterval = null;
        }

        // Only scan when SCAN is ON
        if (scanEnabled) {
            log('Starting signal scanning...');
            scanInterval = setInterval(() => scanForSignals(false), CONFIG.SCAN_INTERVAL);
            scanForSignals(false); // Immediate scan
        }
    }

    function scanForSignals(force = false) {
        if (!scanEnabled) return;
        
        if (isScanning && !force) return;
        if (isTrading && !force) return;

        // Check 30-second cooldown for scan trades
        const now = Date.now();
        if ((now - lastTradeTime) < CONFIG.TRADE_COOLDOWN_SCAN && !force) {
            const remaining = Math.round((CONFIG.TRADE_COOLDOWN_SCAN - (now - lastTradeTime)) / 1000);
            log(`Scan cooldown: ${remaining}s`);
            return;
        }

        isScanning = true;
        updateStatusDot('trading');

        // Determine what to scan
        const scanScope = switchEnabled ? 'favorites' : 'current';
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: CONFIG.API_URL + `/signals/scan-markets?scope=${scanScope}&min_confidence=${CONFIG.MIN_CONFIDENCE}&min_payout=${CONFIG.MIN_PAYOUT}`,
            headers: { 'Accept': 'application/json' },
            timeout: 10000,
            onload: function(res) {
                isScanning = false;
                try {
                    if (res.status !== 200) {
                        updateStatusDot('connected');
                        return;
                    }

                    const data = JSON.parse(res.responseText);
                    
                    if (data.success && data.signals && data.signals.length > 0) {
                        // Find best signal
                        let bestSignal = null;
                        
                        if (switchEnabled) {
                            // Can use any signal from favorites
                            bestSignal = data.signals[0];
                        } else {
                            // Must match current asset
                            const currentAssetNorm = normalizeAsset(getCurrentAsset());
                            for (const sig of data.signals) {
                                if (normalizeAsset(sig.symbol) === currentAssetNorm) {
                                    bestSignal = sig;
                                    break;
                                }
                            }
                        }

                        if (bestSignal) {
                            log(`🔍 SCAN SIGNAL: ${bestSignal.direction} ${bestSignal.symbol}`);
                            executeScanTrade(bestSignal);
                        } else {
                            log('No matching signals for current asset');
                            updateStatusDot('connected');
                        }
                    } else {
                        updateStatusDot('connected');
                    }
                } catch (e) {
                    log('Scan error: ' + e.message);
                    updateStatusDot('connected');
                }
            },
            onerror: function() {
                isScanning = false;
                updateStatusDot('');
                log('Scan connection error');
            }
        });
    }

    function normalizeAsset(asset) {
        if (!asset) return '';
        return asset.replace(/[^A-Z0-9]/gi, '').toUpperCase();
    }

    // ===========================================
    // TRADE EXECUTION
    // ===========================================
    async function executeAppSignalTrade(signal) {
        if (isTrading) {
            log('Already trading');
            return;
        }

        isTrading = true;
        updateStatusDot('trading');
        
        // Determine direction with local invert
        let direction = (signal.direction || '').toUpperCase();
        let isCall = direction === 'CALL' || direction === 'BUY' || direction === 'UP';
        
        // Apply LOCAL invert setting (overrides app)
        if (invertEnabled) {
            isCall = !isCall;
            log(`🔄 INVERTED (local): ${direction} → ${isCall ? 'CALL' : 'PUT'}`);
        }

        const finalDirection = isCall ? 'CALL' : 'PUT';
        updateSignalDisplay(finalDirection, signal.symbol, isCall ? 'call' : 'put');

        // Play APP SIGNAL sound
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

        // Click the button
        const clicked = clickTradeButton(isCall);
        
        if (clicked) {
            tradeCount++;
            updateTradeCount();
            lastTradeTime = Date.now();
            log(`✅ APP TRADE #${tradeCount}: ${finalDirection} on ${signal.symbol}`);
            
            try {
                GM_notification({
                    title: `📡 App Signal: ${finalDirection}`,
                    text: `${signal.symbol} - Trade executed`,
                    timeout: 3000
                });
            } catch(e) {}
        }

        // Cooldown
        setTimeout(() => {
            isTrading = false;
            updateStatusDot('connected');
            updateSignalDisplay('READY', null, 'wait');
        }, 2000);
    }

    async function executeScanTrade(signal) {
        if (isTrading) {
            log('Already trading');
            return;
        }

        isTrading = true;
        updateStatusDot('trading');

        // Switch asset if enabled and needed
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
        
        // Apply LOCAL invert setting
        if (invertEnabled) {
            isCall = !isCall;
            log(`🔄 INVERTED (local): ${direction} → ${isCall ? 'CALL' : 'PUT'}`);
        }

        const finalDirection = isCall ? 'CALL' : 'PUT';
        updateSignalDisplay(finalDirection, signal.symbol, isCall ? 'call' : 'put');

        // Play SCAN SIGNAL sound (different from app)
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

        // Click the button
        const clicked = clickTradeButton(isCall);
        
        if (clicked) {
            tradeCount++;
            updateTradeCount();
            lastTradeTime = Date.now();
            log(`✅ SCAN TRADE #${tradeCount}: ${finalDirection} on ${signal.symbol}`);
            
            try {
                GM_notification({
                    title: `🔍 Scan Signal: ${finalDirection}`,
                    text: `${signal.symbol} - Trade executed`,
                    timeout: 3000
                });
            } catch(e) {}
        }

        // Cooldown
        setTimeout(() => {
            isTrading = false;
            updateStatusDot('connected');
            updateSignalDisplay('READY', null, 'wait');
        }, 2000);
    }

    function clickTradeButton(isCall) {
        const selector = isCall ? '.btn-call' : '.btn-put';
        const btn = document.querySelector(selector);
        
        if (btn && btn.offsetParent !== null) {
            log(`Clicking ${isCall ? 'CALL' : 'PUT'} button`);
            btn.click();
            return true;
        }
        
        log('Button not found: ' + selector);
        return false;
    }

    // ===========================================
    // ASSET SWITCHING
    // ===========================================
    async function switchToAsset(targetAsset) {
        log(`Switching to ${targetAsset}...`);
        
        // Try to find asset selector
        const selectors = [
            '.pair-selector', '.asset-selector', '[data-testid="asset-selector"]',
            '.asset-dropdown', '.trading-pair-selector'
        ];
        
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
                el.click();
                await sleep(500);
                
                // Search for asset
                const searchInput = document.querySelector('input[type="search"], input[type="text"]');
                if (searchInput) {
                    searchInput.value = targetAsset.replace('_OTC', '').replace('_', '');
                    searchInput.dispatchEvent(new Event('input', { bubbles: true }));
                    await sleep(500);
                }
                
                // Click on result
                const items = document.querySelectorAll('.asset-item, .pair-item, [data-asset]');
                for (const item of items) {
                    if (item.textContent.includes(targetAsset.replace('_', '/')) ||
                        item.textContent.includes(targetAsset.replace('_OTC', ''))) {
                        item.click();
                        await sleep(500);
                        return true;
                    }
                }
            }
        }
        
        return false;
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ===========================================
    // INITIALIZATION
    // ===========================================
    function init() {
        log('Initializing v6.0.0...');

        // Load saved settings (all default to false)
        autoTradeEnabled = GM_getValue('autoTradeEnabled', false);
        switchEnabled = GM_getValue('switchEnabled', false);
        scanEnabled = GM_getValue('scanEnabled', false);
        invertEnabled = GM_getValue('invertEnabled', false);

        setTimeout(() => {
            createPanel();
            getCurrentAsset();
            
            // Start appropriate services
            startOrStopPolling();
            startOrStopScanning();
            
            log('Ready! All buttons OFF by default');
        }, 2000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
