// ==UserScript==
// @name         GPT Signal Bot - Pocket Option Auto Trader
// @namespace    https://auto-trader-pro-3.preview.emergentagent.com
// @version      1.4.0
// @description  Auto-trade on Pocket Option. v1.4.0 - Compact draggable UI, centered top position.
// @author       GPT Signal Bot
// @match        *://pocketoption.com/*
// @match        *://po.trade/*
// @match        *://pocket-option.com/*
// @grant        GM_notification
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      auto-trader-pro-3.preview.emergentagent.com
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // ===========================================
    // CONFIGURATION - EDIT THESE VALUES
    // ===========================================
    const CONFIG = {
        // Your GPT Signal Bot API URL
        API_URL: 'https://auto-trader-pro-3.preview.emergentagent.com/api',
        
        // How often to check for new signals (milliseconds)
        POLL_INTERVAL: 2000, // 2 seconds (faster polling)
        
        // Auto-trading settings
        AUTO_TRADE_ENABLED: true,
        
        // Default trade amount (will use what's set on PO)
        USE_POCKET_OPTION_AMOUNT: true,
        
        // Show notifications
        NOTIFICATIONS_ENABLED: true,
        
        // Sound alerts
        SOUND_ENABLED: true,
        
        // Debug mode - shows more logs
        DEBUG: true
    };

    // ===========================================
    // STATE
    // ===========================================
    let lastSignalId = GM_getValue('lastSignalId', '');
    let isTrading = false;
    let connectionStatus = 'disconnected';
    let tradeCount = 0;
    let winCount = 0;
    let lossCount = 0;

    // ===========================================
    // LOGGING
    // ===========================================
    function log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const prefix = '[GPT Signal Bot]';
        
        if (type === 'error') {
            console.error(`${prefix} ${timestamp}: ${message}`);
        } else if (type === 'warn') {
            console.warn(`${prefix} ${timestamp}: ${message}`);
        } else if (CONFIG.DEBUG || type === 'success') {
            console.log(`${prefix} ${timestamp}: ${message}`);
        }
        
        updateStatusPanel(message);
    }

    // ===========================================
    // UI PANEL - COMPACT DRAGGABLE TOP CENTER
    // ===========================================
    function createControlPanel() {
        // Load saved position or use default center-top
        const savedPos = GM_getValue('panelPosition', { x: null, y: 5 });
        
        const panel = document.createElement('div');
        panel.id = 'gpt-signal-panel';
        panel.innerHTML = `
            <style>
                #gpt-signal-panel {
                    position: fixed;
                    top: ${savedPos.y}px;
                    left: ${savedPos.x !== null ? savedPos.x + 'px' : '50%'};
                    transform: ${savedPos.x !== null ? 'none' : 'translateX(-50%)'};
                    background: linear-gradient(135deg, #1a1a2e 0%, #0d1421 100%);
                    border: 1px solid #7c3aed;
                    border-radius: 8px;
                    padding: 6px 12px;
                    z-index: 999999;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    box-shadow: 0 2px 15px rgba(124, 58, 237, 0.4);
                    color: white;
                    cursor: move;
                    user-select: none;
                    min-width: 420px;
                    max-width: 600px;
                }
                #gpt-signal-panel.minimized {
                    min-width: auto;
                    max-width: none;
                }
                #gpt-signal-panel.minimized .panel-content {
                    display: none;
                }
                #gpt-signal-panel.minimized .panel-header {
                    margin: 0;
                    padding: 0;
                    border: none;
                }
                .panel-header {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    margin-bottom: 6px;
                    padding-bottom: 6px;
                    border-bottom: 1px solid rgba(124, 58, 237, 0.3);
                }
                .panel-drag-handle {
                    cursor: move;
                    color: #64748b;
                    font-size: 12px;
                    padding: 0 4px;
                }
                .panel-title {
                    font-weight: bold;
                    font-size: 12px;
                    color: #a78bfa;
                    white-space: nowrap;
                }
                .panel-toggle {
                    background: rgba(124, 58, 237, 0.2);
                    border: 1px solid #7c3aed;
                    color: #a78bfa;
                    cursor: pointer;
                    font-size: 14px;
                    padding: 2px 8px;
                    border-radius: 4px;
                    margin-left: auto;
                }
                .panel-toggle:hover {
                    background: rgba(124, 58, 237, 0.4);
                }
                .status-indicator {
                    display: inline-block;
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    animation: pulse 2s infinite;
                }
                .status-connected { background: #22c55e; }
                .status-disconnected { background: #ef4444; }
                .status-trading { background: #f59e0b; animation: pulse 0.5s infinite; }
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
                .panel-content {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    flex-wrap: wrap;
                }
                .panel-section {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    font-size: 11px;
                    background: rgba(15, 23, 42, 0.6);
                    padding: 4px 8px;
                    border-radius: 4px;
                }
                .panel-label { 
                    color: #64748b; 
                    font-size: 10px;
                }
                .panel-value { 
                    color: #e2e8f0; 
                    font-weight: 600;
                    font-size: 11px;
                }
                .panel-value.green { color: #22c55e; }
                .panel-value.red { color: #ef4444; }
                .panel-value.yellow { color: #f59e0b; }
                .compact-btn {
                    padding: 4px 10px;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 10px;
                    cursor: pointer;
                    transition: all 0.2s;
                    white-space: nowrap;
                }
                .compact-btn.enabled {
                    background: linear-gradient(135deg, #22c55e, #16a34a);
                    color: white;
                }
                .compact-btn.disabled {
                    background: linear-gradient(135deg, #ef4444, #dc2626);
                    color: white;
                }
                .compact-btn.blue {
                    background: linear-gradient(135deg, #3b82f6, #1d4ed8);
                    color: white;
                }
                .compact-btn.orange {
                    background: linear-gradient(135deg, #f59e0b, #d97706);
                    color: white;
                }
                .compact-btn:hover {
                    transform: scale(1.05);
                    filter: brightness(1.1);
                }
                .signal-badge {
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 11px;
                }
                .signal-badge.call {
                    background: rgba(34, 197, 94, 0.2);
                    border: 1px solid #22c55e;
                    color: #22c55e;
                }
                .signal-badge.put {
                    background: rgba(239, 68, 68, 0.2);
                    border: 1px solid #ef4444;
                    color: #ef4444;
                }
                .signal-badge.none {
                    background: rgba(100, 116, 139, 0.2);
                    border: 1px solid #64748b;
                    color: #64748b;
                }
                #status-log {
                    display: none;
                }
            </style>
            <div class="panel-header">
                <span class="panel-drag-handle">⋮⋮</span>
                <span class="status-indicator status-disconnected" id="status-dot"></span>
                <span class="panel-title">🤖 GPT Signal Bot</span>
                <span id="connection-text" style="font-size:10px;color:#64748b;">Connecting...</span>
                <button class="panel-toggle" onclick="togglePanel()">−</button>
            </div>
            <div class="panel-content">
                <div class="panel-section">
                    <span class="panel-label">Signal:</span>
                    <span id="last-signal-badge" class="signal-badge none">WAITING</span>
                </div>
                <div class="panel-section">
                    <span class="panel-label">Trades:</span>
                    <span id="trade-count" class="panel-value">0</span>
                </div>
                <div class="panel-section">
                    <span class="panel-label">W/L:</span>
                    <span id="win-count" class="panel-value green">0</span>
                    <span style="color:#64748b">/</span>
                    <span id="loss-count" class="panel-value red">0</span>
                </div>
                <button id="auto-trade-toggle" class="compact-btn enabled" onclick="toggleAutoTrade()">
                    🟢 AUTO ON
                </button>
                <button class="compact-btn blue" onclick="manualFetchSignal()">
                    🔄 Fetch
                </button>
                <button class="compact-btn orange" onclick="resetTrader()">
                    🔧 Reset
                </button>
            </div>
            <div id="status-log"></div>
        `;
        
        document.body.appendChild(panel);
        
        // Make panel draggable
        makeDraggable(panel);
        
        log('Control panel created (v1.4.0 - Compact UI)', 'info');
    }
    
    // Toggle panel minimize/expand
    window.togglePanel = function() {
        const panel = document.getElementById('gpt-signal-panel');
        const btn = panel.querySelector('.panel-toggle');
        panel.classList.toggle('minimized');
        btn.textContent = panel.classList.contains('minimized') ? '+' : '−';
    };
    
    // Make element draggable
    function makeDraggable(element) {
        let isDragging = false;
        let startX, startY, initialX, initialY;
        
        element.addEventListener('mousedown', startDrag);
        element.addEventListener('touchstart', startDrag, { passive: false });
        
        function startDrag(e) {
            // Don't drag if clicking on buttons
            if (e.target.tagName === 'BUTTON') return;
            
            isDragging = true;
            
            if (e.type === 'touchstart') {
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
            } else {
                startX = e.clientX;
                startY = e.clientY;
            }
            
            const rect = element.getBoundingClientRect();
            initialX = rect.left;
            initialY = rect.top;
            
            // Remove transform to use absolute positioning
            element.style.transform = 'none';
            element.style.left = initialX + 'px';
            element.style.top = initialY + 'px';
            
            document.addEventListener('mousemove', drag);
            document.addEventListener('mouseup', stopDrag);
            document.addEventListener('touchmove', drag, { passive: false });
            document.addEventListener('touchend', stopDrag);
            
            e.preventDefault();
        }
        
        function drag(e) {
            if (!isDragging) return;
            
            let currentX, currentY;
            if (e.type === 'touchmove') {
                currentX = e.touches[0].clientX;
                currentY = e.touches[0].clientY;
            } else {
                currentX = e.clientX;
                currentY = e.clientY;
            }
            
            const deltaX = currentX - startX;
            const deltaY = currentY - startY;
            
            let newX = initialX + deltaX;
            let newY = initialY + deltaY;
            
            // Keep within viewport
            const maxX = window.innerWidth - element.offsetWidth - 10;
            const maxY = window.innerHeight - element.offsetHeight - 10;
            
            newX = Math.max(10, Math.min(newX, maxX));
            newY = Math.max(5, Math.min(newY, maxY));
            
            element.style.left = newX + 'px';
            element.style.top = newY + 'px';
            
            e.preventDefault();
        }
        
        function stopDrag() {
            if (isDragging) {
                isDragging = false;
                
                // Save position
                const rect = element.getBoundingClientRect();
                GM_setValue('panelPosition', { x: rect.left, y: rect.top });
            }
            
            document.removeEventListener('mousemove', drag);
            document.removeEventListener('mouseup', stopDrag);
            document.removeEventListener('touchmove', drag);
            document.removeEventListener('touchend', stopDrag);
        }
    }

    function updateStatusPanel(message) {
        const logEl = document.getElementById('status-log');
        if (logEl) {
            const time = new Date().toLocaleTimeString();
            logEl.innerHTML = `<div>${time}: ${message}</div>` + logEl.innerHTML;
            if (logEl.children.length > 5) {
                logEl.removeChild(logEl.lastChild);
            }
        }
    }

    function updateConnectionStatus(status) {
        connectionStatus = status;
        const indicator = document.getElementById('status-dot');
        const statusText = document.getElementById('connection-text');
        
        if (indicator && statusText) {
            indicator.className = 'status-indicator';
            
            if (status === 'connected') {
                indicator.classList.add('status-connected');
                statusText.textContent = 'Connected';
                statusText.style.color = '#22c55e';
            } else if (status === 'trading') {
                indicator.classList.add('status-trading');
                statusText.textContent = 'Trading...';
                statusText.style.color = '#f59e0b';
            } else {
                indicator.classList.add('status-disconnected');
                statusText.textContent = 'Disconnected';
                statusText.style.color = '#ef4444';
            }
        }
    }

    function updateLastSignal(signal) {
        const badgeEl = document.getElementById('last-signal-badge');
        
        if (badgeEl) {
            const isCall = signal.direction === 'CALL' || signal.direction === 'BUY';
            badgeEl.textContent = isCall ? '📈 CALL' : '📉 PUT';
            badgeEl.className = 'signal-badge ' + (isCall ? 'call' : 'put');
            badgeEl.title = `${signal.symbol} | ${signal.confidence || signal.probability}% | ${new Date().toLocaleTimeString()}`;
        }
    }

    function updateStats() {
        const tradeEl = document.getElementById('trade-count');
        const winEl = document.getElementById('win-count');
        const lossEl = document.getElementById('loss-count');
        
        if (tradeEl) tradeEl.textContent = tradeCount;
        if (winEl) winEl.textContent = winCount;
        if (lossEl) lossEl.textContent = lossCount;
    }

    // ===========================================
    // TOGGLE AUTO-TRADE
    // ===========================================
    window.toggleAutoTrade = function() {
        CONFIG.AUTO_TRADE_ENABLED = !CONFIG.AUTO_TRADE_ENABLED;
        const btn = document.getElementById('auto-trade-toggle');
        
        if (btn) {
            if (CONFIG.AUTO_TRADE_ENABLED) {
                btn.className = 'compact-btn enabled';
                btn.textContent = '🟢 AUTO ON';
                log('Auto-trading ENABLED', 'success');
            } else {
                btn.className = 'compact-btn disabled';
                btn.textContent = '🔴 AUTO OFF';
                log('Auto-trading DISABLED', 'warn');
            }
        }
        
        GM_setValue('autoTradeEnabled', CONFIG.AUTO_TRADE_ENABLED);
    };

    // Reset function to unstick the trader
    window.resetTrader = function() {
        log('🔧 RESETTING TRADER...', 'warn');
        isTrading = false;
        lastSignalId = '';
        GM_setValue('lastSignalId', '');
        updateConnectionStatus('connected');
        log('✅ Trader reset complete. Ready for new signals.', 'success');
        showNotification('Trader Reset', 'Auto-trader has been reset and is ready for new signals.');
    };

    // ===========================================
    // SIGNAL FETCHING (using GM_xmlhttpRequest for cross-origin)
    // ===========================================
    function fetchLatestSignal() {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'GET',
                url: `${CONFIG.API_URL}/signals/latest`,
                headers: {
                    'Accept': 'application/json'
                },
                onload: function(response) {
                    try {
                        if (response.status === 200) {
                            const data = JSON.parse(response.responseText);
                            updateConnectionStatus('connected');
                            
                            if (data.success && data.signal) {
                                log(`Signal found: ${data.signal.direction} ${data.signal.symbol}`);
                                resolve(data.signal);
                            } else {
                                // Not an error, just no new signal
                                if (CONFIG.DEBUG && data.message) {
                                    log(data.message, 'info');
                                }
                                resolve(null);
                            }
                        } else {
                            log(`API returned status ${response.status}`, 'error');
                            updateConnectionStatus('disconnected');
                            resolve(null);
                        }
                    } catch (e) {
                        log(`Parse error: ${e.message}`, 'error');
                        resolve(null);
                    }
                },
                onerror: function(error) {
                    log(`API Error: ${error.statusText || 'Connection failed'}`, 'error');
                    updateConnectionStatus('disconnected');
                    resolve(null);
                },
                ontimeout: function() {
                    log('API Timeout', 'error');
                    updateConnectionStatus('disconnected');
                    resolve(null);
                },
                timeout: 10000
            });
        });
    }

    // Manual signal fetch button
    window.manualFetchSignal = async function() {
        // Prevent manual fetch if already trading
        if (isTrading) {
            log('Cannot fetch - trade already in progress', 'warn');
            return;
        }
        
        log('Manual fetch triggered...');
        
        // Set trading flag immediately to prevent race conditions
        isTrading = true;
        
        try {
            const signal = await fetchLatestSignal();
            if (signal) {
                // Update the lastSignalId to prevent double-processing
                const signalId = signal.id || `${signal.symbol}_${signal.direction}_${signal.timestamp}`;
                lastSignalId = signalId;
                GM_setValue('lastSignalId', lastSignalId);
                
                updateLastSignal(signal);
                
                if (CONFIG.AUTO_TRADE_ENABLED) {
                    await executeTradeFromSignal(signal);
                    // Note: executeTradeFromSignal handles resetting isTrading
                    return;
                } else {
                    log('Auto-trade OFF - signal displayed only', 'warn');
                }
            } else {
                log('No signal available', 'warn');
            }
        } catch (error) {
            log(`Manual fetch error: ${error.message}`, 'error');
        }
        
        // Reset if we didn't execute a trade
        isTrading = false;
    };

    async function checkForNewSignals() {
        if (isTrading) {
            log('Trade in progress, skipping signal check', 'info');
            return;
        }
        
        try {
            const signal = await fetchLatestSignal();
            
            if (signal) {
                // Create a unique ID based on the signal's actual ID or timestamp
                // Use the server-generated ID if available (most reliable)
                const signalId = signal.id || '';
                const signalTimestamp = signal.timestamp || '';
                
                // Create unique identifier - prefer server ID, fallback to composite
                let signalUniqueId;
                if (signalId && signalId.length > 10) {
                    // Use server-generated ID (e.g., "EMERGENCY_OTC_20260224_194402_AUDUSD_OTC")
                    signalUniqueId = signalId;
                } else {
                    // Fallback to composite ID
                    signalUniqueId = `${signal.symbol}_${signal.direction}_${signalTimestamp}`;
                }
                
                // Check if we've already processed this exact signal
                if (signalUniqueId === lastSignalId) {
                    // Same signal, don't process again - but this is normal, not an error
                    return;
                }
                
                // NEW SIGNAL DETECTED!
                log(`🚨 NEW SIGNAL DETECTED: ${signal.direction} ${signal.symbol}`, 'success');
                log(`Signal ID: ${signalUniqueId}`, 'info');
                
                // Save the signal ID BEFORE setting isTrading to prevent race conditions
                lastSignalId = signalUniqueId;
                GM_setValue('lastSignalId', lastSignalId);
                
                // Set trading flag
                isTrading = true;
                
                // Update UI
                updateLastSignal(signal);
                
                if (CONFIG.AUTO_TRADE_ENABLED) {
                    await executeTradeFromSignal(signal);
                } else {
                    log('Auto-trade is OFF - signal displayed but not executed', 'warn');
                    showNotification('New Signal (Manual Mode)', `${signal.direction} ${signal.symbol} - Auto-trade is OFF`);
                    isTrading = false; // Reset immediately if not trading
                }
            }
        } catch (error) {
            log(`Signal check error: ${error.message}`, 'error');
            // Reset trading flag on error to prevent getting stuck
            isTrading = false;
        }
    }

    // ===========================================
    // TRADE EXECUTION
    // ===========================================
    async function executeTradeFromSignal(signal) {
        // Safety check
        if (!isTrading) {
            log('executeTradeFromSignal called but isTrading is false - aborting', 'warn');
            return;
        }
        
        updateConnectionStatus('trading');
        
        try {
            const direction = signal.direction?.toUpperCase();
            const isCall = direction === 'CALL' || direction === 'BUY' || direction === 'UP';
            
            log(`🎯 EXECUTING TRADE: ${isCall ? 'CALL ⬆️' : 'PUT ⬇️'} on ${signal.symbol}`);
            
            // Play sound alert
            if (CONFIG.SOUND_ENABLED) {
                playSound(isCall ? 'call' : 'put');
            }
            
            // Show notification
            showNotification(
                `🚨 TRADING: ${isCall ? 'CALL ⬆️' : 'PUT ⬇️'}`,
                `${signal.symbol} | ${signal.confidence || signal.probability}% confidence`
            );
            
            // Find and click the trade button
            const success = await clickTradeButton(isCall);
            
            if (success) {
                tradeCount++;
                updateStats();
                log(`✅ TRADE EXECUTED: ${isCall ? 'CALL' : 'PUT'} on ${signal.symbol}`, 'success');
                
                // Record the trade result after expiration
                const expirationMs = ((signal.expiration_minutes || 1) * 60 * 1000) + 2000;
                log(`Will check trade result in ${Math.round(expirationMs/1000)}s`);
                setTimeout(() => checkTradeResult(signal), expirationMs);
            } else {
                log('❌ TRADE FAILED: Could not find/click trade button', 'error');
                showNotification('Trade Failed', 'Could not find CALL/PUT button. Make sure you are on the trading page.');
            }
            
        } catch (error) {
            log(`❌ Trade execution error: ${error.message}`, 'error');
        } finally {
            // CRITICAL: Reset trading flag with cooldown
            // This ensures we don't get stuck and don't process same signal twice
            const cooldownSeconds = 10; // 10 second cooldown between trades
            log(`Trade complete. ${cooldownSeconds}s cooldown before next trade...`, 'info');
            
            setTimeout(() => {
                isTrading = false;
                updateConnectionStatus('connected');
                log('✅ Ready for new signals', 'success');
            }, cooldownSeconds * 1000);
        }
    }

    async function clickTradeButton(isCall) {
        const buttonType = isCall ? 'CALL' : 'PUT';
        log(`Looking for ${buttonType} button...`);
        
        // ONLY use Pocket Option's actual trade button selectors - be VERY specific
        // These are the EXACT selectors for PO's trading interface
        const callSelectors = [
            '#put-call-buttons-chart-1 .btn-call',
            '.btn-call.btn',
            '.call-btn',
            '.btn-call'
        ];
        
        const putSelectors = [
            '#put-call-buttons-chart-1 .btn-put',
            '.btn-put.btn', 
            '.put-btn',
            '.btn-put'
        ];
        
        const selectors = isCall ? callSelectors : putSelectors;
        
        // Track if we've already clicked to prevent multiple clicks
        let clicked = false;
        
        for (const selector of selectors) {
            if (clicked) break; // Stop if we already clicked
            
            try {
                const buttons = document.querySelectorAll(selector);
                
                for (const button of buttons) {
                    if (clicked) break;
                    
                    // Make sure button is visible and is actually a trade button
                    if (button && 
                        button.offsetParent !== null && 
                        button.offsetWidth > 0 &&
                        button.offsetHeight > 0) {
                        
                        // Extra check: make sure it's not a navigation link
                        const tagName = button.tagName.toLowerCase();
                        if (tagName === 'a' || button.href) {
                            log(`Skipping link element: ${selector}`, 'warn');
                            continue;
                        }
                        
                        log(`Found ${buttonType} button: ${selector}`);
                        
                        // Single click only
                        button.click();
                        clicked = true;
                        
                        log(`✅ CLICKED ${buttonType}`, 'success');
                        return true;
                    }
                }
            } catch (e) {
                log(`Selector error: ${e.message}`, 'warn');
            }
        }
        
        if (!clicked) {
            log(`❌ ${buttonType} button NOT FOUND!`, 'error');
            log('Make sure you are on the Pocket Option TRADING page with the chart visible.', 'warn');
        }
        
        return clicked;
    }

    async function checkTradeResult(signal) {
        // Try to detect win/loss from the page
        // This is a simplified version - in reality you'd check the trades history
        
        try {
            // Look for result indicators on the page
            const closedTrades = document.querySelectorAll('.deals-list__item, .history-item, .trade-result');
            
            if (closedTrades.length > 0) {
                const lastTrade = closedTrades[0];
                const text = lastTrade.textContent || '';
                
                if (text.includes('+') || text.includes('win') || text.includes('Won')) {
                    winCount++;
                    log('Trade WON! ✅', 'success');
                    reportResultToServer(signal.id, true);
                } else if (text.includes('-') || text.includes('lose') || text.includes('Lost')) {
                    lossCount++;
                    log('Trade LOST ❌', 'warn');
                    reportResultToServer(signal.id, false);
                }
                
                updateStats();
            }
        } catch (error) {
            log(`Result check error: ${error.message}`, 'error');
        }
    }

    function reportResultToServer(signalId, isWin) {
        GM_xmlhttpRequest({
            method: 'POST',
            url: `${CONFIG.API_URL}/trading/record-result`,
            headers: {
                'Content-Type': 'application/json'
            },
            data: JSON.stringify({
                signal_id: signalId,
                win: isWin,
                direction: 'CALL',
                symbol: 'EURUSD'
            }),
            onload: function(response) {
                if (response.status === 200) {
                    log('Result reported to server');
                }
            },
            onerror: function() {
                log('Failed to report result', 'error');
            }
        });
    }

    // ===========================================
    // UTILITIES
    // ===========================================
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function playSound(type) {
        try {
            const frequency = type === 'call' ? 800 : 400;
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            oscillator.frequency.value = frequency;
            oscillator.type = 'sine';
            gainNode.gain.value = 0.3;
            
            oscillator.start();
            setTimeout(() => oscillator.stop(), 200);
        } catch (e) {
            // Audio not supported
        }
    }

    function showNotification(title, body) {
        if (!CONFIG.NOTIFICATIONS_ENABLED) return;
        
        try {
            if (typeof GM_notification !== 'undefined') {
                GM_notification({
                    title: title,
                    text: body,
                    timeout: 5000
                });
            } else if (Notification.permission === 'granted') {
                new Notification(title, { body: body });
            } else if (Notification.permission !== 'denied') {
                Notification.requestPermission().then(permission => {
                    if (permission === 'granted') {
                        new Notification(title, { body: body });
                    }
                });
            }
        } catch (e) {
            log('Notification error', 'warn');
        }
    }

    // ===========================================
    // INITIALIZATION
    // ===========================================
    function init() {
        log('Initializing GPT Signal Bot Auto-Trader...', 'success');
        
        // Wait for page to fully load
        setTimeout(() => {
            // Create control panel
            createControlPanel();
            
            // Restore settings
            CONFIG.AUTO_TRADE_ENABLED = GM_getValue('autoTradeEnabled', true);
            if (!CONFIG.AUTO_TRADE_ENABLED) {
                window.toggleAutoTrade();
                window.toggleAutoTrade(); // Reset to match saved state
            }
            
            // Request notification permission
            if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
                Notification.requestPermission();
            }
            
            // Start polling for signals
            log('Starting signal polling...');
            setInterval(checkForNewSignals, CONFIG.POLL_INTERVAL);
            
            // Initial check
            checkForNewSignals();
            
            log('Auto-Trader ready! Waiting for signals...', 'success');
            showNotification('GPT Signal Bot', 'Auto-Trader is now active!');
            
        }, 2000);
    }

    // Start when page is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
