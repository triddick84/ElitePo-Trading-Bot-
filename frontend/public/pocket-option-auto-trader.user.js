// ==UserScript==
// @name         GPT Signal Bot - Pocket Option Auto Trader
// @namespace    https://auto-trader-pro-3.preview.emergentagent.com
// @version      2.0.1
// @description  Auto-trade on Pocket Option. v2.0.1 - Enhanced debugging and connection.
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
// @connect      auto-trader-pro-3.preview.emergentagent.com
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
        API_URL: 'https://auto-trader-pro-3.preview.emergentagent.com/api',
        POLL_INTERVAL: 3000,
        AUTO_TRADE_ENABLED: true,
        SOUND_ENABLED: true,
        DEBUG: true
    };

    // ===========================================
    // STATE
    // ===========================================
    let lastProcessedSignalTime = GM_getValue('lastProcessedSignalTime', 0);
    let isTrading = false;
    let tradeCount = 0;

    // ===========================================
    // LOGGING
    // ===========================================
    function log(msg, type = 'info') {
        const ts = new Date().toLocaleTimeString();
        const prefix = '[GPT Bot]';
        console.log(`${prefix} ${ts}: ${msg}`);
        
        // Update UI log
        const logEl = document.getElementById('gpt-log');
        if (logEl) {
            logEl.textContent = msg;
        }
    }

    // ===========================================
    // UI PANEL
    // ===========================================
    function createPanel() {
        const panel = document.createElement('div');
        panel.id = 'gpt-panel';
        panel.innerHTML = `
            <style>
                #gpt-panel {
                    position: fixed;
                    top: 10px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: #1a1a2e;
                    border: 2px solid #7c3aed;
                    border-radius: 10px;
                    padding: 8px 15px;
                    z-index: 999999;
                    font-family: Arial, sans-serif;
                    color: white;
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    box-shadow: 0 4px 20px rgba(124, 58, 237, 0.5);
                }
                #gpt-panel .dot {
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    background: #ef4444;
                }
                #gpt-panel .dot.connected { background: #22c55e; }
                #gpt-panel .dot.trading { background: #f59e0b; animation: blink 0.5s infinite; }
                @keyframes blink { 50% { opacity: 0.3; } }
                #gpt-panel .title { font-weight: bold; color: #a78bfa; font-size: 13px; }
                #gpt-panel .signal { 
                    padding: 4px 10px; 
                    border-radius: 5px; 
                    font-weight: bold;
                    font-size: 12px;
                }
                #gpt-panel .signal.call { background: #22c55e; }
                #gpt-panel .signal.put { background: #ef4444; }
                #gpt-panel .signal.wait { background: #64748b; }
                #gpt-panel button {
                    padding: 5px 12px;
                    border: none;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 11px;
                    cursor: pointer;
                }
                #gpt-panel .btn-auto { background: #22c55e; color: white; }
                #gpt-panel .btn-auto.off { background: #ef4444; }
                #gpt-panel .btn-fetch { background: #3b82f6; color: white; }
                #gpt-panel .btn-reset { background: #f59e0b; color: white; }
                #gpt-panel .info { font-size: 11px; color: #94a3b8; }
                #gpt-log { 
                    font-size: 10px; 
                    color: #22c55e; 
                    max-width: 250px; 
                    overflow: hidden; 
                    text-overflow: ellipsis; 
                    white-space: nowrap;
                    background: rgba(0,0,0,0.3);
                    padding: 3px 8px;
                    border-radius: 4px;
                }
            </style>
            <span class="dot" id="gpt-dot"></span>
            <span class="title">🤖 GPT Bot v2.0</span>
            <span class="signal wait" id="gpt-signal">CONNECTING...</span>
            <span class="info">Trades: <span id="gpt-trades">0</span></span>
            <button class="btn-auto" id="gpt-auto" onclick="window.toggleAuto()">AUTO ON</button>
            <button class="btn-fetch" onclick="window.fetchNow()">FETCH</button>
            <button class="btn-reset" onclick="window.resetBot()">RESET</button>
            <span id="gpt-log">Initializing...</span>
        `;
        document.body.appendChild(panel);
        log('Panel created v2.0.1');
    }

    function updateUI(status, signal = null) {
        const dot = document.getElementById('gpt-dot');
        const sigEl = document.getElementById('gpt-signal');
        const tradesEl = document.getElementById('gpt-trades');
        
        if (dot) {
            dot.className = 'dot';
            if (status === 'connected') dot.classList.add('connected');
            else if (status === 'trading') dot.classList.add('trading');
        }
        
        if (signal && sigEl) {
            const isCall = signal.direction === 'CALL' || signal.direction === 'BUY';
            sigEl.textContent = isCall ? '📈 CALL' : '📉 PUT';
            sigEl.className = 'signal ' + (isCall ? 'call' : 'put');
        }
        
        if (tradesEl) tradesEl.textContent = tradeCount;
    }

    // ===========================================
    // TOGGLE FUNCTIONS
    // ===========================================
    window.toggleAuto = function() {
        CONFIG.AUTO_TRADE_ENABLED = !CONFIG.AUTO_TRADE_ENABLED;
        const btn = document.getElementById('gpt-auto');
        if (btn) {
            btn.textContent = CONFIG.AUTO_TRADE_ENABLED ? 'AUTO ON' : 'AUTO OFF';
            btn.className = 'btn-auto' + (CONFIG.AUTO_TRADE_ENABLED ? '' : ' off');
        }
        GM_setValue('autoEnabled', CONFIG.AUTO_TRADE_ENABLED);
        log('Auto-trade: ' + (CONFIG.AUTO_TRADE_ENABLED ? 'ON' : 'OFF'));
    };

    window.resetBot = function() {
        isTrading = false;
        lastProcessedSignalTime = 0;
        GM_setValue('lastProcessedSignalTime', 0);
        updateUI('connected');
        log('Bot reset - ready for signals');
    };

    window.fetchNow = function() {
        log('Manual fetch...');
        checkSignal(true);
    };

    // ===========================================
    // SIGNAL FETCHING
    // ===========================================
    function checkSignal(force = false) {
        if (isTrading && !force) {
            log('Busy trading...');
            return;
        }

        log('Checking API...');
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: CONFIG.API_URL + '/signals/latest',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            timeout: 10000,
            onload: function(res) {
                try {
                    log('API Response: ' + res.status);
                    
                    if (res.status !== 200) {
                        log('API Error: ' + res.status);
                        updateUI('disconnected');
                        return;
                    }
                    
                    const data = JSON.parse(res.responseText);
                    updateUI('connected');
                    
                    if (data.success && data.signal) {
                        const signal = data.signal;
                        const signalTime = new Date(signal.timestamp).getTime();
                        
                        log('Signal: ' + signal.direction + ' ' + signal.symbol);
                        
                        // Check if this is a NEW signal (newer than last processed)
                        if (signalTime > lastProcessedSignalTime || force) {
                            log('🚨 NEW SIGNAL DETECTED!');
                            
                            // Update UI immediately
                            updateUI('trading', signal);
                            
                            // Mark as processed BEFORE executing
                            lastProcessedSignalTime = signalTime;
                            GM_setValue('lastProcessedSignalTime', signalTime);
                            
                            if (CONFIG.AUTO_TRADE_ENABLED) {
                                executeTrade(signal);
                            } else {
                                log('Auto OFF - signal shown only');
                                updateUI('connected', signal);
                            }
                        } else {
                            log('Same signal (age: ' + Math.round((Date.now() - signalTime)/1000) + 's)');
                            updateUI('connected', signal);
                        }
                    } else {
                        log(data.message || 'No signal available');
                        const sigEl = document.getElementById('gpt-signal');
                        if (sigEl) {
                            sigEl.textContent = 'NO SIGNAL';
                            sigEl.className = 'signal wait';
                        }
                    }
                } catch (e) {
                    log('Parse error: ' + e.message);
                    updateUI('disconnected');
                }
            },
            onerror: function(err) {
                log('Connection error!');
                updateUI('disconnected');
            },
            ontimeout: function() {
                log('Request timeout!');
                updateUI('disconnected');
            }
        });
    }

    // ===========================================
    // TRADE EXECUTION
    // ===========================================
    function executeTrade(signal) {
        if (isTrading) {
            log('Already trading...');
            return;
        }
        
        isTrading = true;
        updateUI('trading', signal);
        
        const isCall = signal.direction === 'CALL' || signal.direction === 'BUY';
        log(`Executing ${isCall ? 'CALL' : 'PUT'}...`);
        
        // Play sound
        if (CONFIG.SOUND_ENABLED) {
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                osc.frequency.value = isCall ? 800 : 400;
                osc.connect(ctx.destination);
                osc.start();
                setTimeout(() => osc.stop(), 200);
            } catch(e) {}
        }
        
        // Try to click the trade button
        const clicked = clickButton(isCall);
        
        if (clicked) {
            tradeCount++;
            updateUI('trading', signal);
            log('✅ Trade executed!');
            
            // Show notification
            try {
                GM_notification({
                    title: isCall ? '📈 CALL Executed' : '📉 PUT Executed',
                    text: signal.symbol + ' - ' + (signal.confidence || 85) + '%',
                    timeout: 3000
                });
            } catch(e) {}
        } else {
            log('❌ Button not found!');
        }
        
        // Reset after cooldown
        setTimeout(() => {
            isTrading = false;
            updateUI('connected');
            log('Ready for next signal');
        }, 5000);
    }

    function clickButton(isCall) {
        // Pocket Option specific selectors
        const selectors = isCall 
            ? ['.btn-call', '.call-btn', '#put-call-buttons-chart-1 .btn-call', '[class*="btn-call"]']
            : ['.btn-put', '.put-btn', '#put-call-buttons-chart-1 .btn-put', '[class*="btn-put"]'];
        
        for (const sel of selectors) {
            const btn = document.querySelector(sel);
            if (btn && btn.offsetParent !== null) {
                log('Found button: ' + sel);
                btn.click();
                return true;
            }
        }
        
        // Fallback: look for green/red buttons
        const allBtns = document.querySelectorAll('button, .btn');
        for (const btn of allBtns) {
            const classes = (btn.className || '').toLowerCase();
            const text = (btn.textContent || '').toLowerCase();
            
            if (isCall && (classes.includes('call') || classes.includes('green') || text.includes('call') || text.includes('higher'))) {
                if (btn.offsetParent !== null && !classes.includes('put')) {
                    log('Found CALL via fallback');
                    btn.click();
                    return true;
                }
            }
            if (!isCall && (classes.includes('put') || classes.includes('red') || text.includes('put') || text.includes('lower'))) {
                if (btn.offsetParent !== null && !classes.includes('call')) {
                    log('Found PUT via fallback');
                    btn.click();
                    return true;
                }
            }
        }
        
        return false;
    }

    // ===========================================
    // INITIALIZATION
    // ===========================================
    function init() {
        log('Initializing v2.0...');
        
        setTimeout(() => {
            createPanel();
            
            // Restore settings
            CONFIG.AUTO_TRADE_ENABLED = GM_getValue('autoEnabled', true);
            if (!CONFIG.AUTO_TRADE_ENABLED) {
                const btn = document.getElementById('gpt-auto');
                if (btn) {
                    btn.textContent = 'AUTO OFF';
                    btn.className = 'btn-auto off';
                }
            }
            
            // Start polling
            setInterval(checkSignal, CONFIG.POLL_INTERVAL);
            checkSignal();
            
            log('Ready! Polling every ' + (CONFIG.POLL_INTERVAL/1000) + 's');
        }, 2000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
