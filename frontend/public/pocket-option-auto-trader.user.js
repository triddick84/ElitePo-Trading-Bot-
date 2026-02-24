// ==UserScript==
// @name         GPT Signal Bot - Pocket Option Auto Trader
// @namespace    https://algo-signal-hub-2.preview.emergentagent.com
// @version      1.0.0
// @description  Automatically execute trades on Pocket Option based on GPT Signal Bot signals. Works on Android (Kiwi Browser) and Desktop.
// @author       GPT Signal Bot
// @match        *://pocketoption.com/*
// @match        *://po.trade/*
// @match        *://pocket-option.com/*
// @grant        GM_notification
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      algo-signal-hub-2.preview.emergentagent.com
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // ===========================================
    // CONFIGURATION - EDIT THESE VALUES
    // ===========================================
    const CONFIG = {
        // Your GPT Signal Bot API URL
        API_URL: 'https://algo-signal-hub-2.preview.emergentagent.com/api',
        
        // How often to check for new signals (milliseconds)
        POLL_INTERVAL: 3000, // 3 seconds
        
        // Auto-trading settings
        AUTO_TRADE_ENABLED: true,
        
        // Default trade amount (will use what's set on PO)
        USE_POCKET_OPTION_AMOUNT: true,
        
        // Show notifications
        NOTIFICATIONS_ENABLED: true,
        
        // Sound alerts
        SOUND_ENABLED: true,
        
        // Debug mode
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
        if (isTrading) return;
        
        try {
            const signal = await fetchLatestSignal();
            
            if (signal) {
                // Create a unique ID based on signal properties
                const signalUniqueId = signal.id || `${signal.symbol}_${signal.direction}_${signal.timestamp}`;
                
                if (signalUniqueId !== lastSignalId) {
                    log(`🚨 NEW SIGNAL: ${signal.direction} ${signal.symbol}`, 'success');
                    lastSignalId = signalUniqueId;
                    GM_setValue('lastSignalId', lastSignalId);
                    
                    updateLastSignal(signal);
                    
                    if (CONFIG.AUTO_TRADE_ENABLED) {
                        await executeTradeFromSignal(signal);
                    } else {
                        log('Auto-trade disabled, signal ignored', 'warn');
                        showNotification('New Signal (Manual)', `${signal.direction} ${signal.symbol} - Auto-trade is OFF`);
                    }
                }
            }
        } catch (error) {
            log(`Check signal error: ${error.message}`, 'error');
        }
    }

    // ===========================================
    // TRADE EXECUTION
    // ===========================================
    async function executeTradeFromSignal(signal) {
        if (isTrading) {
            log('Already trading, skipping...', 'warn');
            return;
        }
        
        isTrading = true;
        updateConnectionStatus('trading');
        
        try {
            const direction = signal.direction?.toUpperCase();
            const isCall = direction === 'CALL' || direction === 'BUY';
            
            log(`Executing ${isCall ? 'CALL' : 'PUT'} trade...`);
            
            // Play sound alert
            if (CONFIG.SOUND_ENABLED) {
                playSound(isCall ? 'call' : 'put');
            }
            
            // Show notification
            showNotification(
                `🚨 Trading: ${isCall ? 'CALL ⬆️' : 'PUT ⬇️'}`,
                `${signal.symbol} | ${signal.confidence || signal.probability}% confidence`
            );
            
            // Find and click the trade button
            const success = await clickTradeButton(isCall);
            
            if (success) {
                tradeCount++;
                updateStats();
                log(`Trade executed: ${isCall ? 'CALL' : 'PUT'}`, 'success');
                
                // Record the trade result after expiration
                setTimeout(() => checkTradeResult(signal), (signal.expiration_seconds || 60) * 1000 + 2000);
            } else {
                log('Failed to click trade button', 'error');
            }
            
        } catch (error) {
            log(`Trade execution error: ${error.message}`, 'error');
        } finally {
            isTrading = false;
            updateConnectionStatus('connected');
        }
    }

    async function clickTradeButton(isCall) {
        // Pocket Option button selectors
        const callSelectors = [
            '.btn-call',
            '.call-btn',
            '[data-testid="call-button"]',
            'button.up',
            '.trading-panel button.call',
            '#put-call-buttons-chart-1 .btn-call',
            '.btn.btn-call'
        ];
        
        const putSelectors = [
            '.btn-put',
            '.put-btn',
            '[data-testid="put-button"]',
            'button.down',
            '.trading-panel button.put',
            '#put-call-buttons-chart-1 .btn-put',
            '.btn.btn-put'
        ];
        
        const selectors = isCall ? callSelectors : putSelectors;
        
        for (const selector of selectors) {
            const button = document.querySelector(selector);
            if (button) {
                log(`Found button: ${selector}`);
                
                // Scroll into view
                button.scrollIntoView({ behavior: 'smooth', block: 'center' });
                await sleep(200);
                
                // Click the button
                button.click();
                
                // Also try dispatching events for stubborn buttons
                button.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                await sleep(50);
                button.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                
                return true;
            }
        }
        
        log('Trade button not found! Make sure you are on the trading page.', 'error');
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
