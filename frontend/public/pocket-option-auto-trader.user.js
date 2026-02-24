// ==UserScript==
// @name         GPT Signal Bot - Pocket Option Auto Trader
// @namespace    https://auto-trader-pro-3.preview.emergentagent.com
// @version      1.1.0
// @description  Automatically execute trades on Pocket Option based on GPT Signal Bot signals. Works on Android (Kiwi Browser) and Desktop. v1.1.0 - Fixed button detection, added reset function.
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
    // UI PANEL
    // ===========================================
    function createControlPanel() {
        const panel = document.createElement('div');
        panel.id = 'gpt-signal-panel';
        panel.innerHTML = `
            <style>
                #gpt-signal-panel {
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    width: 280px;
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    border: 2px solid #7c3aed;
                    border-radius: 12px;
                    padding: 15px;
                    z-index: 999999;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    box-shadow: 0 4px 20px rgba(124, 58, 237, 0.3);
                    color: white;
                }
                #gpt-signal-panel.minimized {
                    width: auto;
                    padding: 10px;
                }
                #gpt-signal-panel.minimized .panel-content {
                    display: none;
                }
                .panel-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                    padding-bottom: 10px;
                    border-bottom: 1px solid #7c3aed;
                }
                .panel-title {
                    font-weight: bold;
                    font-size: 14px;
                    color: #a78bfa;
                }
                .panel-toggle {
                    background: none;
                    border: none;
                    color: #a78bfa;
                    cursor: pointer;
                    font-size: 18px;
                    padding: 0 5px;
                }
                .status-indicator {
                    display: inline-block;
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    margin-right: 8px;
                    animation: pulse 2s infinite;
                }
                .status-connected { background: #22c55e; }
                .status-disconnected { background: #ef4444; }
                .status-trading { background: #f59e0b; animation: pulse 0.5s infinite; }
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
                .panel-row {
                    display: flex;
                    justify-content: space-between;
                    margin: 8px 0;
                    font-size: 12px;
                }
                .panel-label { color: #94a3b8; }
                .panel-value { color: #e2e8f0; font-weight: 500; }
                .panel-value.green { color: #22c55e; }
                .panel-value.red { color: #ef4444; }
                .panel-value.yellow { color: #f59e0b; }
                .toggle-btn {
                    width: 100%;
                    padding: 10px;
                    margin-top: 10px;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                .toggle-btn.enabled {
                    background: linear-gradient(135deg, #22c55e, #16a34a);
                    color: white;
                }
                .toggle-btn.disabled {
                    background: linear-gradient(135deg, #ef4444, #dc2626);
                    color: white;
                }
                .toggle-btn:hover {
                    transform: scale(1.02);
                }
                .last-signal {
                    background: #1e293b;
                    border-radius: 8px;
                    padding: 10px;
                    margin-top: 10px;
                    font-size: 11px;
                }
                .signal-direction {
                    font-size: 16px;
                    font-weight: bold;
                    margin-bottom: 5px;
                }
                .signal-direction.call { color: #22c55e; }
                .signal-direction.put { color: #ef4444; }
                #status-log {
                    max-height: 60px;
                    overflow-y: auto;
                    font-size: 10px;
                    color: #64748b;
                    margin-top: 10px;
                    padding: 5px;
                    background: #0f172a;
                    border-radius: 4px;
                }
            </style>
            <div class="panel-header">
                <span class="panel-title">🤖 GPT Signal Bot</span>
                <button class="panel-toggle" onclick="document.getElementById('gpt-signal-panel').classList.toggle('minimized')">−</button>
            </div>
            <div class="panel-content">
                <div class="panel-row">
                    <span class="panel-label">Status:</span>
                    <span class="panel-value">
                        <span id="status-indicator" class="status-indicator status-disconnected"></span>
                        <span id="connection-status">Connecting...</span>
                    </span>
                </div>
                <div class="panel-row">
                    <span class="panel-label">Trades:</span>
                    <span class="panel-value"><span id="trade-count">0</span></span>
                </div>
                <div class="panel-row">
                    <span class="panel-label">Win/Loss:</span>
                    <span class="panel-value">
                        <span id="win-count" class="green">0</span> / 
                        <span id="loss-count" class="red">0</span>
                    </span>
                </div>
                <button id="auto-trade-toggle" class="toggle-btn enabled" onclick="toggleAutoTrade()">
                    🟢 AUTO-TRADE ON
                </button>
                <button class="toggle-btn" style="background: linear-gradient(135deg, #3b82f6, #1d4ed8); margin-top: 5px;" onclick="manualFetchSignal()">
                    🔄 Fetch Signal Now
                </button>
                <button class="toggle-btn" style="background: linear-gradient(135deg, #f59e0b, #d97706); margin-top: 5px;" onclick="resetTrader()">
                    🔧 Reset (if stuck)
                </button>
                <div class="last-signal" id="last-signal-box">
                    <div class="signal-direction" id="last-signal-direction">Waiting for signal...</div>
                    <div id="last-signal-details"></div>
                </div>
                <div id="status-log"></div>
            </div>
        `;
        
        document.body.appendChild(panel);
        log('Control panel created', 'success');
    }

    function updateStatusPanel(message) {
        const logEl = document.getElementById('status-log');
        if (logEl) {
            const time = new Date().toLocaleTimeString();
            logEl.innerHTML = `<div>${time}: ${message}</div>` + logEl.innerHTML;
            if (logEl.children.length > 10) {
                logEl.removeChild(logEl.lastChild);
            }
        }
    }

    function updateConnectionStatus(status) {
        connectionStatus = status;
        const indicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('connection-status');
        
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
        const directionEl = document.getElementById('last-signal-direction');
        const detailsEl = document.getElementById('last-signal-details');
        
        if (directionEl && detailsEl) {
            const isCall = signal.direction === 'CALL' || signal.direction === 'BUY';
            directionEl.textContent = isCall ? '📈 CALL (UP)' : '📉 PUT (DOWN)';
            directionEl.className = 'signal-direction ' + (isCall ? 'call' : 'put');
            detailsEl.innerHTML = `
                <div>Asset: ${signal.symbol}</div>
                <div>Confidence: ${signal.confidence || signal.probability}%</div>
                <div>Time: ${new Date().toLocaleTimeString()}</div>
            `;
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
                btn.className = 'toggle-btn enabled';
                btn.textContent = '🟢 AUTO-TRADE ON';
                log('Auto-trading ENABLED', 'success');
            } else {
                btn.className = 'toggle-btn disabled';
                btn.textContent = '🔴 AUTO-TRADE OFF';
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
    // SIGNAL FETCHING
    // ===========================================
    async function fetchLatestSignal() {
        try {
            const response = await fetch(`${CONFIG.API_URL}/signals/latest`);
            if (!response.ok) throw new Error('API error');
            
            const data = await response.json();
            updateConnectionStatus('connected');
            
            if (data.success && data.signal) {
                log(`Signal found: ${data.signal.direction} ${data.signal.symbol}`);
                return data.signal;
            } else {
                // Not an error, just no new signal
                if (CONFIG.DEBUG && data.message) {
                    log(data.message, 'info');
                }
            }
            return null;
        } catch (error) {
            log(`API Error: ${error.message}`, 'error');
            updateConnectionStatus('disconnected');
            return null;
        }
    }

    // Manual signal fetch button
    window.manualFetchSignal = async function() {
        log('Manual fetch triggered...');
        const signal = await fetchLatestSignal();
        if (signal) {
            updateLastSignal(signal);
            if (CONFIG.AUTO_TRADE_ENABLED) {
                await executeTradeFromSignal(signal);
            }
        } else {
            log('No new signal available', 'warn');
        }
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
        // Pocket Option button selectors - Updated for current PO interface
        const callSelectors = [
            // Primary PO selectors
            '.btn-call',
            '.call-btn', 
            '.btn.btn-call',
            '#put-call-buttons-chart-1 .btn-call',
            // Alternative selectors
            '[class*="btn-call"]',
            '[class*="call"][class*="btn"]',
            'button[class*="call"]',
            'button[class*="green"]',
            'button[class*="up"]',
            '.trading-panel button.call',
            '[data-testid="call-button"]',
            'button.up',
            // Color-based fallback (green = call)
            'button[style*="green"]',
            '.deal-btn--call',
            '.option-call'
        ];
        
        const putSelectors = [
            // Primary PO selectors
            '.btn-put',
            '.put-btn',
            '.btn.btn-put',
            '#put-call-buttons-chart-1 .btn-put',
            // Alternative selectors
            '[class*="btn-put"]',
            '[class*="put"][class*="btn"]',
            'button[class*="put"]',
            'button[class*="red"]',
            'button[class*="down"]',
            '.trading-panel button.put',
            '[data-testid="put-button"]',
            'button.down',
            // Color-based fallback (red = put)
            'button[style*="red"]',
            '.deal-btn--put',
            '.option-put'
        ];
        
        const selectors = isCall ? callSelectors : putSelectors;
        const buttonType = isCall ? 'CALL' : 'PUT';
        
        log(`Looking for ${buttonType} button...`);
        
        for (const selector of selectors) {
            try {
                const button = document.querySelector(selector);
                if (button && button.offsetParent !== null) { // Check if visible
                    log(`Found ${buttonType} button: ${selector}`);
                    
                    // Scroll into view
                    button.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    await sleep(300);
                    
                    // SINGLE CLICK ONLY - Don't use multiple methods!
                    button.click();
                    log(`✅ Clicked ${buttonType} button`, 'success');
                    
                    return true;
                }
            } catch (e) {
                log(`Selector ${selector} error: ${e.message}`, 'warn');
            }
        }
        
        // Last resort: try to find by text content
        log('Trying text-based button search...', 'warn');
        const allButtons = document.querySelectorAll('button, [role="button"], .btn');
        for (const btn of allButtons) {
            const text = (btn.textContent || '').toLowerCase();
            const classes = (btn.className || '').toLowerCase();
            
            if (isCall && (text.includes('call') || text.includes('higher') || (classes.includes('call') && !classes.includes('put')))) {
                log(`Found CALL by text/class: "${text.substring(0,20)}"`);
                btn.click();
                return true;
            }
            if (!isCall && (text.includes('put') || text.includes('lower') || (classes.includes('put') && !classes.includes('call')))) {
                log(`Found PUT by text/class: "${text.substring(0,20)}"`);
                btn.click();
                return true;
            }
        }
        
        log(`${buttonType} button NOT FOUND! Make sure you are on the Pocket Option trading chart page.`, 'error');
        return false;
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

    async function reportResultToServer(signalId, isWin) {
        try {
            await fetch(`${CONFIG.API_URL}/trading/record-result`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    signal_id: signalId,
                    win: isWin,
                    direction: 'CALL', // Will be updated from actual signal
                    symbol: 'EURUSD'
                })
            });
            log('Result reported to server');
        } catch (error) {
            log('Failed to report result', 'error');
        }
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
