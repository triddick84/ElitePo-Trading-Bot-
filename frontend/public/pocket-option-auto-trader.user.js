// ==UserScript==
// @name         GPT Signal Bot - Pocket Option Auto Trader
// @namespace    https://signal-bot-preview.preview.emergentagent.com
// @version      6.6.1
// @description  Auto-trade OTC forex on Pocket Option. v6.6.1 - Fixed win/loss detection timing
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
        API_URL: 'https://signal-bot-preview.preview.emergentagent.com/api',
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
    
    // CRITICAL: Global trade lock to prevent double trades
    let globalTradeLock = false;
    let lastTradeClickTime = 0;
    const TRADE_LOCK_MS = 5000;  // 5 second absolute lock after any trade
    
    // NEW: Enhanced control settings from backend
    let selectedStrategy = 'auto';
    let selectedTimeframe = '1m';
    let signalSource = 'app_ai';  // app_ai, tradingview, mt4, mt5, tampermonkey_scan
    let favoritesFromBar = [];    // Detected from PO favorites bar
    let currentFavoriteIndex = 0; // For cycling through favorites
    
    // ===========================================
    // WIN/LOSS RECOGNITION SYSTEM - v6.6.0
    // ===========================================
    let winLossStats = {
        totalWins: 0,
        totalLosses: 0,
        consecutiveWins: 0,
        consecutiveLosses: 0,
        sessionProfit: 0,
        lastTradeResult: null,  // 'win', 'loss', or null
        lastTradeAmount: 0,
        lastBalance: 0,
        tradeHistory: []  // Array of {time, direction, result, amount, balance}
    };
    
    // Auto-invert settings
    let autoInvertEnabled = false;      // Master toggle for auto-invert system
    let autoInvertActive = false;       // Currently in inverted mode due to loss
    let autoPlaceAfterLoss = false;     // Auto-place next trade after loss (vs just invert next signal)
    let maxConsecutiveLosses = 3;       // Stop after this many consecutive losses
    let stopLossAmount = 0;             // Stop if session loss exceeds this (0 = disabled)
    let soundNotificationsEnabled = true; // Sound on win/loss
    
    // Trade result monitoring
    let pendingTradeCheck = null;       // {direction, amount, startBalance, timestamp}
    let resultCheckInterval = null;
    
    // Intervals
    let appPollingInterval = null;
    let scanInterval = null;
    let heartbeatInterval = null;

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
    // WIN/LOSS SOUND NOTIFICATIONS - v6.6.0
    // ===========================================
    function playWinSound() {
        if (!soundNotificationsEnabled) return;
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            // Ascending happy sound
            osc.frequency.value = 523; // C5
            osc.type = 'sine';
            gain.gain.value = 0.3;
            osc.start();
            setTimeout(() => { osc.frequency.value = 659; }, 100); // E5
            setTimeout(() => { osc.frequency.value = 784; }, 200); // G5
            setTimeout(() => { osc.stop(); ctx.close(); }, 400);
        } catch(e) {}
    }

    function playLossSound() {
        if (!soundNotificationsEnabled) return;
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            // Descending sad sound
            osc.frequency.value = 392; // G4
            osc.type = 'sawtooth';
            gain.gain.value = 0.2;
            osc.start();
            setTimeout(() => { osc.frequency.value = 330; }, 150); // E4
            setTimeout(() => { osc.frequency.value = 262; }, 300); // C4
            setTimeout(() => { osc.stop(); ctx.close(); }, 500);
        } catch(e) {}
    }

    function playStopSound() {
        if (!soundNotificationsEnabled) return;
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            // Alert sound for stop condition
            osc.frequency.value = 200;
            osc.type = 'square';
            gain.gain.value = 0.3;
            osc.start();
            setTimeout(() => { osc.frequency.value = 150; }, 200);
            setTimeout(() => { osc.frequency.value = 200; }, 400);
            setTimeout(() => { osc.frequency.value = 150; }, 600);
            setTimeout(() => { osc.stop(); ctx.close(); }, 800);
        } catch(e) {}
    }

    // ===========================================
    // LOGGING
    // ===========================================
    function log(msg) {
        const ts = new Date().toLocaleTimeString();
        console.log(`[GPT v6.6.1] ${ts}: ${msg}`);
        const logEl = document.getElementById('gpt-log');
        if (logEl) logEl.textContent = msg;
    }

    // ===========================================
    // HELPER FUNCTIONS
    // ===========================================
    
    // Convert timeframe string to seconds
    function getExpiryFromTimeframe(timeframe) {
        if (!timeframe) return 60;
        
        const tf = timeframe.toLowerCase().trim();
        
        // Parse formats like "5s", "15s", "30s", "1m", "2m", "5m"
        const match = tf.match(/^(\d+)(s|m|h)?$/);
        if (match) {
            const value = parseInt(match[1]);
            const unit = match[2] || 's';
            
            switch (unit) {
                case 's': return value;
                case 'm': return value * 60;
                case 'h': return value * 3600;
                default: return value;
            }
        }
        
        // Default mappings
        const mappings = {
            '5s': 5, '15s': 15, '30s': 30,
            '1m': 60, '2m': 120, '3m': 180, '5m': 300,
            '15m': 900, '30m': 1800, '1h': 3600
        };
        
        return mappings[tf] || 60;
    }

    // ===========================================
    // WIN/LOSS DETECTION SYSTEM - v6.6.0
    // ===========================================
    
    // Get current balance from Pocket Option UI
    function getCurrentBalance() {
        // Try multiple selectors for balance
        const balanceSelectors = [
            '.balance__value',
            '.balance-value',
            '[class*="balance"] [class*="value"]',
            '.trading-balance',
            '[data-testid="balance"]',
            '.js-balance',
            '.balance span',
            '[class*="Balance"]'
        ];
        
        for (const sel of balanceSelectors) {
            const el = document.querySelector(sel);
            if (el && el.textContent) {
                const text = el.textContent.replace(/[^0-9.,]/g, '').replace(',', '');
                const balance = parseFloat(text);
                if (!isNaN(balance) && balance > 0) {
                    return balance;
                }
            }
        }
        
        // Fallback: search for any element with $ and numbers
        const allElements = document.querySelectorAll('*');
        for (const el of allElements) {
            if (!el || !el.offsetParent) continue;
            if (el.children.length > 2) continue;
            
            const text = el.textContent || '';
            if (text.includes('$') && /\d+\.\d{2}/.test(text)) {
                const match = text.match(/[\d,]+\.\d{2}/);
                if (match) {
                    const balance = parseFloat(match[0].replace(',', ''));
                    if (!isNaN(balance) && balance > 0 && balance < 1000000) {
                        return balance;
                    }
                }
            }
        }
        
        return null;
    }
    
    // Detect trade result from popup notification
    function checkTradeResultPopup() {
        // Pocket Option shows result popups/notifications after trade expires
        // Look for various result indicators
        const popupSelectors = [
            '.notification',
            '.popup',
            '.alert',
            '.toast',
            '[class*="notification"]',
            '[class*="result"]',
            '[class*="profit"]',
            '[class*="loss"]',
            '.deal-result',
            '.trade-result',
            '[class*="payout"]',
            '[class*="expire"]',
            '[class*="closed"]',
            // Pocket Option specific
            '.trading-widget__result',
            '.deal__result',
            '[class*="deal-"]',
            '.history-item'
        ];
        
        for (const sel of popupSelectors) {
            try {
                const popups = document.querySelectorAll(sel);
                for (const popup of popups) {
                    if (!popup || !popup.offsetParent) continue;
                    
                    const text = (popup.textContent || '').toLowerCase();
                    const html = (popup.innerHTML || '').toLowerCase();
                    
                    // Skip if text is too long (likely not a result popup)
                    if (text.length > 200) continue;
                    
                    // Check for WIN indicators
                    // Look for: "profit", "win", "+$", green color indicators, "92%", payout percentages
                    const isWin = 
                        text.includes('profit') || 
                        text.includes('win') || 
                        text.includes('+$') || 
                        text.includes('+ $') ||
                        text.includes('payout') ||
                        (html.includes('green') && text.match(/\$[\d.]+/)) ||
                        (html.includes('#22c55e') || html.includes('#10b981') || html.includes('rgb(34, 197, 94)'));
                    
                    if (isWin && !text.includes('loss') && !text.includes('-$')) {
                        const amountMatch = text.match(/[\+]?\$?\s*([\d,]+\.?\d*)/);
                        const amount = amountMatch ? parseFloat(amountMatch[1].replace(',', '')) : 0;
                        if (amount > 0) {
                            return { result: 'win', amount: amount };
                        }
                    }
                    
                    // Check for LOSS indicators
                    // Look for: "loss", "lose", "-$", red color indicators, "0%"
                    const isLoss = 
                        text.includes('loss') || 
                        text.includes('lose') || 
                        text.includes('-$') || 
                        text.includes('- $') ||
                        text.includes('expired') ||
                        (html.includes('red') && text.match(/\$[\d.]+/)) ||
                        (html.includes('#ef4444') || html.includes('#dc2626') || html.includes('rgb(239, 68, 68)'));
                    
                    if (isLoss && !text.includes('profit') && !text.includes('+$')) {
                        const amountMatch = text.match(/[\-]?\$?\s*([\d,]+\.?\d*)/);
                        const amount = amountMatch ? parseFloat(amountMatch[1].replace(',', '')) : 0;
                        if (amount > 0) {
                            return { result: 'loss', amount: amount };
                        }
                    }
                }
            } catch (e) {
                // Skip selector errors
            }
        }
        
        return null;
    }
    
    // Start monitoring for trade result after placing a trade
    function startTradeResultMonitor(direction, tradeAmount, expirySeconds) {
        // IMPORTANT: Get balance AFTER the trade is placed (amount already deducted)
        // Wait a moment for the balance to update after trade placement
        setTimeout(() => {
            const balanceAfterTrade = getCurrentBalance();
            const estimatedExpiry = expirySeconds || 60; // Default 60 seconds if not provided
            
            pendingTradeCheck = {
                direction: direction,
                amount: tradeAmount || 1,
                balanceAfterTrade: balanceAfterTrade, // Balance AFTER trade placed (amount deducted)
                timestamp: Date.now(),
                expiryTime: Date.now() + (estimatedExpiry * 1000) // When trade should expire
            };
            
            log(`📊 Monitoring trade: ${direction}, Post-trade balance: $${balanceAfterTrade || 'N/A'}, Expiry: ${estimatedExpiry}s`);
            
            // Clear any existing interval
            if (resultCheckInterval) {
                clearInterval(resultCheckInterval);
            }
            
            let checkCount = 0;
            const minWaitSeconds = Math.max(5, estimatedExpiry - 2); // Wait at least until near expiry
            const maxChecks = Math.max(60, estimatedExpiry + 30); // Check for expiry + 30 seconds buffer
            
            resultCheckInterval = setInterval(() => {
                checkCount++;
                
                // Method 1: Check for popup result (can appear anytime after expiry)
                const popupResult = checkTradeResultPopup();
                if (popupResult) {
                    log(`🎯 Popup detected: ${popupResult.result} $${popupResult.amount}`);
                    processTradeResult(popupResult.result, popupResult.amount);
                    clearInterval(resultCheckInterval);
                    resultCheckInterval = null;
                    pendingTradeCheck = null;
                    return;
                }
                
                // Method 2: Check balance change ONLY after trade should have expired
                // This prevents false triggers from the initial trade amount deduction
                if (checkCount >= minWaitSeconds && pendingTradeCheck && pendingTradeCheck.balanceAfterTrade) {
                    const currentBalance = getCurrentBalance();
                    if (currentBalance !== null) {
                        const diff = currentBalance - pendingTradeCheck.balanceAfterTrade;
                        
                        // WIN: Balance increased (got payout)
                        // LOSS: Balance stayed same or very small change (no payout, but trade amount already gone)
                        
                        // Significant positive change = WIN (payout received)
                        if (diff > 0.5) {
                            log(`💰 Balance increased by $${diff.toFixed(2)} = WIN`);
                            processTradeResult('win', diff);
                            clearInterval(resultCheckInterval);
                            resultCheckInterval = null;
                            pendingTradeCheck = null;
                            return;
                        }
                        
                        // After expiry time + buffer, if no increase, it's a LOSS
                        if (checkCount >= estimatedExpiry + 5) {
                            // No payout received after sufficient wait = LOSS
                            const lossAmount = pendingTradeCheck.amount || 1;
                            log(`📉 No payout after expiry = LOSS ($${lossAmount})`);
                            processTradeResult('loss', lossAmount);
                            clearInterval(resultCheckInterval);
                            resultCheckInterval = null;
                            pendingTradeCheck = null;
                            return;
                        }
                    }
                }
                
                // Timeout after maxChecks
                if (checkCount >= maxChecks) {
                    log('⏱️ Trade result check timeout - assuming LOSS');
                    const lossAmount = pendingTradeCheck?.amount || 1;
                    processTradeResult('loss', lossAmount);
                    clearInterval(resultCheckInterval);
                    resultCheckInterval = null;
                    pendingTradeCheck = null;
                }
            }, 1000);
        }, 1500); // Wait 1.5 seconds for balance to settle after trade placement
    }
    
    // Process detected trade result
    function processTradeResult(result, amount) {
        const isWin = result === 'win';
        
        log(`${isWin ? '✅ WIN' : '❌ LOSS'}: $${amount.toFixed(2)}`);
        
        // Update stats
        if (isWin) {
            winLossStats.totalWins++;
            winLossStats.consecutiveWins++;
            winLossStats.consecutiveLosses = 0;
            winLossStats.sessionProfit += amount;
            playWinSound();
        } else {
            winLossStats.totalLosses++;
            winLossStats.consecutiveLosses++;
            winLossStats.consecutiveWins = 0;
            winLossStats.sessionProfit -= amount;
            playLossSound();
        }
        
        winLossStats.lastTradeResult = result;
        winLossStats.lastTradeAmount = amount;
        winLossStats.lastBalance = getCurrentBalance();
        
        // Add to history
        winLossStats.tradeHistory.push({
            time: new Date().toISOString(),
            direction: pendingTradeCheck?.direction || 'unknown',
            result: result,
            amount: amount,
            balance: winLossStats.lastBalance
        });
        
        // Keep only last 50 trades in history
        if (winLossStats.tradeHistory.length > 50) {
            winLossStats.tradeHistory = winLossStats.tradeHistory.slice(-50);
        }
        
        // Update UI
        updateWinLossDisplay();
        
        // Handle auto-invert logic
        if (autoInvertEnabled) {
            handleAutoInvert(isWin, amount);
        }
        
        // Sync stats to backend
        syncStatsToBackend();
    }
    
    // Auto-invert logic
    function handleAutoInvert(isWin, amount) {
        // Check stop conditions first
        if (checkStopConditions()) {
            return;
        }
        
        if (!isWin) {
            // LOSS: Enable/toggle inversion
            if (!autoInvertActive) {
                // First loss - enable invert
                autoInvertActive = true;
                invertEnabled = true;
                GM_setValue('invertEnabled', true);
                log('🔄 AUTO-INVERT: Enabled due to loss');
                updateInvertButton();
                
                // If auto-place mode, place inverted trade
                if (autoPlaceAfterLoss) {
                    log('🔄 AUTO-PLACE: Placing inverted trade...');
                    setTimeout(() => {
                        triggerAutoPlaceTrade();
                    }, 2000);
                }
            } else {
                // Loss while already inverted - flip back to normal
                autoInvertActive = false;
                invertEnabled = false;
                GM_setValue('invertEnabled', false);
                log('🔄 AUTO-INVERT: Disabled (double loss)');
                updateInvertButton();
            }
        }
        // If WIN: Do nothing, keep current invert state
    }
    
    // Check if we should stop trading
    function checkStopConditions() {
        // Check max consecutive losses
        if (maxConsecutiveLosses > 0 && winLossStats.consecutiveLosses >= maxConsecutiveLosses) {
            log(`🛑 STOP: Max consecutive losses (${maxConsecutiveLosses}) reached`);
            playStopSound();
            disableAllTrading();
            
            GM_notification({
                title: '🛑 Trading Stopped',
                text: `Max ${maxConsecutiveLosses} consecutive losses reached`,
                timeout: 10000
            });
            
            return true;
        }
        
        // Check stop loss amount
        if (stopLossAmount > 0 && winLossStats.sessionProfit <= -stopLossAmount) {
            log(`🛑 STOP: Stop loss ($${stopLossAmount}) reached. Session P/L: $${winLossStats.sessionProfit.toFixed(2)}`);
            playStopSound();
            disableAllTrading();
            
            GM_notification({
                title: '🛑 Trading Stopped',
                text: `Stop loss $${stopLossAmount} reached`,
                timeout: 10000
            });
            
            return true;
        }
        
        return false;
    }
    
    // Disable all trading modes
    function disableAllTrading() {
        autoEnabled = false;
        scanEnabled = false;
        autoInvertEnabled = false;
        GM_setValue('autoEnabled', false);
        GM_setValue('scanEnabled', false);
        GM_setValue('autoInvertEnabled', false);
        manageIntervals();
        updateAllUI();
    }
    
    // Trigger an auto-place trade (after loss in auto-place mode)
    function triggerAutoPlaceTrade() {
        if (isTrading || globalTradeLock) {
            log('Cannot auto-place: already trading');
            return;
        }
        
        // Use current SCAN or force a fetch
        if (scanEnabled) {
            doScan(true);
        } else if (autoEnabled) {
            checkAppSignals(true);
        }
    }
    
    // Update invert button UI
    function updateInvertButton() {
        const btn = document.getElementById('gpt-invert');
        if (btn) {
            btn.textContent = invertEnabled ? 'INVERT ON' : 'INVERT OFF';
            btn.classList.toggle('on', invertEnabled);
            
            // Add indicator if auto-invert is active
            if (autoInvertActive && autoInvertEnabled) {
                btn.textContent = 'INVERT ON (AUTO)';
            }
        }
    }
    
    // Sync stats to backend
    function syncStatsToBackend() {
        GM_xmlhttpRequest({
            method: 'POST',
            url: CONFIG.API_URL + '/tampermonkey/stats',
            headers: { 
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            data: JSON.stringify({
                wins: winLossStats.totalWins,
                losses: winLossStats.totalLosses,
                consecutive_wins: winLossStats.consecutiveWins,
                consecutive_losses: winLossStats.consecutiveLosses,
                session_profit: winLossStats.sessionProfit,
                last_result: winLossStats.lastTradeResult,
                auto_invert_active: autoInvertActive,
                trade_history: winLossStats.tradeHistory.slice(-10) // Last 10 trades
            }),
            timeout: 5000,
            onload: function(res) {
                // Stats synced
            },
            onerror: function() {
                // Ignore sync errors
            }
        });
    }
    
    // Reset stats
    function resetWinLossStats() {
        winLossStats = {
            totalWins: 0,
            totalLosses: 0,
            consecutiveWins: 0,
            consecutiveLosses: 0,
            sessionProfit: 0,
            lastTradeResult: null,
            lastTradeAmount: 0,
            lastBalance: getCurrentBalance(),
            tradeHistory: []
        };
        autoInvertActive = false;
        updateWinLossDisplay();
        syncStatsToBackend();
        log('📊 Stats reset');
    }

    // ===========================================
    // UTILITY FUNCTIONS
    // ===========================================
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ===========================================
    // FAVORITES BAR DETECTION - NEW v6.5.0
    // ===========================================
    function detectFavoritesBar() {
        // Pocket Option favorites bar is typically at the top, horizontal scroll
        // Contains clickable asset items like "EUR/USD OTC", "GBP/USD OTC", etc.
        
        const favorites = [];
        
        // Method 1: Look for horizontal scroll container with asset items
        const scrollContainers = document.querySelectorAll('[class*="scroll"], [class*="favorites"], [class*="tabs"], [class*="assets-bar"]');
        
        for (const container of scrollContainers) {
            if (!container || !container.offsetParent) continue;
            
            const rect = container.getBoundingClientRect();
            // Favorites bar should be near top and horizontal
            if (rect.top > 200 || rect.width < 300) continue;
            
            // Find clickable items inside
            const items = container.querySelectorAll('[class*="item"], [class*="tab"], [class*="asset"], button, a, span');
            
            for (const item of items) {
                if (!item || !item.offsetParent) continue;
                
                const text = (item.textContent || '').trim().toUpperCase();
                
                // Check if it looks like a currency pair
                if ((text.includes('/') || text.includes('USD') || text.includes('EUR') || text.includes('GBP')) 
                    && text.length <= 20 && text.length >= 6) {
                    
                    // Store the element and its text
                    favorites.push({
                        element: item,
                        symbol: text,
                        normalized: normalizeAsset(text)
                    });
                }
            }
        }
        
        // Method 2: Direct search for asset-like clickable elements at top
        if (favorites.length === 0) {
            const allItems = document.querySelectorAll('*');
            
            for (const item of allItems) {
                if (!item || !item.offsetParent) continue;
                if (item.children.length > 5) continue;
                
                const rect = item.getBoundingClientRect();
                // Must be in top area and reasonable size
                if (rect.top > 150 || rect.height > 60 || rect.height < 15) continue;
                if (rect.width < 50 || rect.width > 200) continue;
                
                const text = (item.textContent || '').trim().toUpperCase();
                
                // Check for currency pair pattern
                if ((text.includes('/') && (text.includes('USD') || text.includes('EUR') || text.includes('GBP'))) ||
                    /^[A-Z]{6,10}(_OTC)?$/.test(text.replace(/[^A-Z_]/g, ''))) {
                    
                    const style = window.getComputedStyle(item);
                    if (style.cursor === 'pointer' || item.onclick || item.tagName === 'BUTTON') {
                        favorites.push({
                            element: item,
                            symbol: text,
                            normalized: normalizeAsset(text)
                        });
                    }
                }
            }
        }
        
        // Remove duplicates based on normalized symbol
        const uniqueFavorites = [];
        const seen = new Set();
        
        for (const fav of favorites) {
            if (!seen.has(fav.normalized)) {
                seen.add(fav.normalized);
                uniqueFavorites.push(fav);
            }
        }
        
        favoritesFromBar = uniqueFavorites;
        
        if (uniqueFavorites.length > 0) {
            log(`📊 Detected ${uniqueFavorites.length} favorites: ${uniqueFavorites.map(f => f.symbol).join(', ')}`);
        }
        
        return uniqueFavorites;
    }

    // Click an asset in the favorites bar
    async function clickFavoriteAsset(favorite) {
        if (!favorite || !favorite.element) {
            log('❌ Invalid favorite');
            return false;
        }
        
        try {
            const el = favorite.element;
            
            // Check if element is still in DOM and visible
            if (!el.offsetParent) {
                log('❌ Favorite element no longer visible');
                return false;
            }
            
            log(`🔄 Clicking favorite: ${favorite.symbol}`);
            
            // Click the element
            el.click();
            await sleep(500);
            
            // Verify the switch worked
            const newAsset = getCurrentAsset();
            const targetNorm = favorite.normalized.substring(0, 6);
            
            if (newAsset && normalizeAsset(newAsset).includes(targetNorm)) {
                log(`✅ Switched to ${newAsset} via favorites bar`);
                return true;
            } else {
                log(`⚠️ Click may not have worked. Current: ${newAsset}`);
                return false;
            }
        } catch (e) {
            log(`❌ Favorites click error: ${e.message}`);
            return false;
        }
    }

    // Get next favorite in rotation
    function getNextFavorite() {
        if (favoritesFromBar.length === 0) {
            detectFavoritesBar();
        }
        
        if (favoritesFromBar.length === 0) {
            log('No favorites detected');
            return null;
        }
        
        currentFavoriteIndex = (currentFavoriteIndex + 1) % favoritesFromBar.length;
        return favoritesFromBar[currentFavoriteIndex];
    }

    // ===========================================
    // HEARTBEAT & SETTINGS SYNC - NEW v6.5.0
    // ===========================================
    function sendHeartbeat() {
        const currentAssetNow = getCurrentAsset();
        
        GM_xmlhttpRequest({
            method: 'POST',
            url: CONFIG.API_URL + '/tampermonkey/heartbeat',
            headers: { 
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            data: JSON.stringify({
                current_asset: currentAssetNow,
                favorites: favoritesFromBar.map(f => f.symbol),
                auto_enabled: autoEnabled,
                scan_enabled: scanEnabled,
                switch_enabled: switchEnabled,
                invert_enabled: invertEnabled,
                trade_count: tradeCount
            }),
            timeout: 5000,
            onload: function(res) {
                try {
                    if (res.status !== 200) return;
                    
                    const data = JSON.parse(res.responseText);
                    
                    if (data.success && data.settings) {
                        // Sync settings from backend
                        if (data.settings.selected_strategy) {
                            selectedStrategy = data.settings.selected_strategy;
                        }
                        if (data.settings.signal_source) {
                            signalSource = data.settings.signal_source;
                        }
                        if (data.settings.preferred_expiry) {
                            selectedTimeframe = data.settings.preferred_expiry + 's';
                        }
                        
                        // Update connection indicator
                        updateConnectionStatus(true);
                    }
                } catch (e) {
                    console.error('[GPT HEARTBEAT]', e);
                }
            },
            onerror: function() {
                updateConnectionStatus(false);
            }
        });
    }

    function updateConnectionStatus(connected) {
        const indicator = document.getElementById('gpt-connection-status');
        if (indicator) {
            indicator.textContent = connected ? '🟢' : '🔴';
            indicator.title = connected ? 'Connected to app' : 'Disconnected';
        }
    }

    function getCurrentAsset() {
        // Try multiple methods to find the current asset on Pocket Option
        
        // Method 1: Try specific selectors
        const selectors = [
            '.pair-title',
            '.asset-name', 
            '[data-testid="asset-name"]',
            '.trading-pair-name',
            '.chart-header-pair',
            '.current-symbol',
            '.symbol-name',
            '[class*="pair-title"]',
            '[class*="asset-name"]',
            '[class*="symbol"]'
        ];
        
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.textContent) {
                const text = el.textContent.trim();
                if (text.includes('/') || text.includes('USD') || text.includes('EUR') || text.includes('GBP')) {
                    currentAsset = text;
                    log(`Found asset via selector: ${currentAsset}`);
                    return currentAsset;
                }
            }
        }
        
        // Method 2: Search for any element containing currency pair pattern
        const allElements = document.querySelectorAll('*');
        for (const el of allElements) {
            if (!el || !el.offsetParent) continue;
            if (el.children.length > 3) continue;
            
            const text = (el.textContent || '').trim();
            
            // Look for patterns like "EUR/USD" or "EUR/USD OTC" or "EURUSD"
            if (text.length >= 6 && text.length <= 20) {
                // Check for forex pair patterns
                const pairPattern = /^[A-Z]{3}\/[A-Z]{3}(\s*OTC)?$/i;
                const compactPattern = /^[A-Z]{6}(_OTC)?$/i;
                
                if (pairPattern.test(text) || compactPattern.test(text)) {
                    // Make sure it's visible and likely the main pair display
                    const rect = el.getBoundingClientRect();
                    if (rect.top < 150 && rect.width > 50) {  // Near top of page
                        currentAsset = text;
                        log(`Found asset via pattern: ${currentAsset}`);
                        return currentAsset;
                    }
                }
                
                // Also check for "XXX/XXX" pattern anywhere in text
                const match = text.match(/([A-Z]{3})\/([A-Z]{3})/i);
                if (match) {
                    const rect = el.getBoundingClientRect();
                    if (rect.top < 200 && rect.top > 0) {
                        currentAsset = match[0] + (text.toLowerCase().includes('otc') ? ' OTC' : '');
                        log(`Found asset via match: ${currentAsset}`);
                        return currentAsset;
                    }
                }
            }
        }
        
        // Method 3: Check page title or URL
        const title = document.title;
        const titleMatch = title.match(/([A-Z]{3})\/([A-Z]{3})/i);
        if (titleMatch) {
            currentAsset = titleMatch[0];
            log(`Found asset in title: ${currentAsset}`);
            return currentAsset;
        }
        
        // Method 4: Default to EUR/USD OTC if nothing found (common default)
        log('Could not detect asset - using default EUR/USD OTC');
        currentAsset = 'EUR/USD OTC';
        return currentAsset;
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
                
                #gpt-panel .settings-row {
                    display: flex;
                    justify-content: space-between;
                    font-size: 10px;
                    color: #94a3b8;
                    padding: 3px 0;
                    border-top: 1px solid rgba(124, 58, 237, 0.2);
                }
                #gpt-panel .settings-row .label { color: #64748b; }
                #gpt-panel .settings-row .value { color: #a78bfa; font-weight: bold; }
                
                /* Win/Loss Stats Styles */
                #gpt-panel .stats-container {
                    background: rgba(0,0,0,0.4);
                    border-radius: 8px;
                    padding: 8px;
                    margin: 8px 0;
                }
                #gpt-panel .stats-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 4px;
                }
                #gpt-panel .stats-row:last-child { margin-bottom: 0; }
                #gpt-panel .stat-win { color: #22c55e; font-weight: bold; }
                #gpt-panel .stat-loss { color: #ef4444; font-weight: bold; }
                #gpt-panel .stat-profit { font-weight: bold; }
                #gpt-panel .stat-profit.positive { color: #22c55e; }
                #gpt-panel .stat-profit.negative { color: #ef4444; }
                
                #gpt-panel .auto-invert-section {
                    background: linear-gradient(135deg, #7c2d12 0%, #451a03 100%);
                    border: 1px solid #f59e0b;
                    border-radius: 8px;
                    padding: 8px;
                    margin: 8px 0;
                }
                #gpt-panel .auto-invert-section.active {
                    background: linear-gradient(135deg, #065f46 0%, #022c22 100%);
                    border-color: #22c55e;
                }
                
                #gpt-panel .btn-auto-invert { background: #6b7280; color: white; }
                #gpt-panel .btn-auto-invert.on { background: #f59e0b; }
                #gpt-panel .btn-auto-place { background: #6b7280; color: white; font-size: 9px; }
                #gpt-panel .btn-auto-place.on { background: #06b6d4; }
                #gpt-panel .btn-sound { background: #6b7280; color: white; font-size: 9px; }
                #gpt-panel .btn-sound.on { background: #8b5cf6; }
                
                #gpt-panel .settings-input {
                    background: rgba(0,0,0,0.3);
                    border: 1px solid #4b5563;
                    border-radius: 4px;
                    color: white;
                    padding: 2px 6px;
                    width: 50px;
                    font-size: 10px;
                    text-align: center;
                }
            </style>
            
            <div class="header" id="gpt-drag">
                <div class="header-left">
                    <span class="status-dot" id="gpt-dot"></span>
                    <span class="title">GPT Bot v6.6.1</span>
                    <span id="gpt-connection-status" style="margin-left:6px;font-size:12px;" title="App Connection">🔴</span>
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
                
                <!-- WIN/LOSS STATS - v6.6.0 -->
                <div class="stats-container" id="gpt-stats">
                    <div class="stats-row">
                        <span style="font-size:11px;color:#a78bfa;font-weight:bold;">📊 Session Stats</span>
                        <button id="gpt-reset-stats" style="font-size:9px;padding:2px 6px;background:#374151;border:none;border-radius:3px;color:#9ca3af;cursor:pointer;">Reset</button>
                    </div>
                    <div class="stats-row">
                        <span style="font-size:10px;color:#9ca3af;">W/L:</span>
                        <span><span class="stat-win" id="gpt-wins">0</span> / <span class="stat-loss" id="gpt-losses">0</span></span>
                    </div>
                    <div class="stats-row">
                        <span style="font-size:10px;color:#9ca3af;">Streak:</span>
                        <span style="font-size:10px;" id="gpt-streak">-</span>
                    </div>
                    <div class="stats-row">
                        <span style="font-size:10px;color:#9ca3af;">P/L:</span>
                        <span class="stat-profit" id="gpt-profit">$0.00</span>
                    </div>
                </div>
                
                <!-- AUTO-INVERT SECTION - v6.6.0 -->
                <div class="auto-invert-section" id="gpt-auto-invert-section">
                    <div style="font-size:10px;color:#fcd34d;margin-bottom:6px;text-align:center;">🔄 Auto-Invert on Loss</div>
                    <div class="btn-row">
                        <button class="btn-auto-invert" id="gpt-auto-invert" title="Auto-invert signals after loss">AUTO-INV OFF</button>
                        <button class="btn-auto-place" id="gpt-auto-place" title="Auto-place trade after loss">AUTO-PLACE OFF</button>
                    </div>
                    <div class="btn-row" style="margin-top:4px;">
                        <button class="btn-sound" id="gpt-sound-toggle" title="Sound notifications">🔊 SOUND ON</button>
                        <div style="display:flex;align-items:center;gap:4px;justify-content:flex-end;">
                            <span style="font-size:9px;color:#9ca3af;">Max Loss:</span>
                            <input type="number" class="settings-input" id="gpt-max-losses" value="3" min="1" max="10" title="Stop after X consecutive losses">
                        </div>
                    </div>
                    <div class="stats-row" style="margin-top:6px;">
                        <span style="font-size:9px;color:#9ca3af;">Stop Loss $:</span>
                        <input type="number" class="settings-input" id="gpt-stop-loss" value="0" min="0" max="1000" step="10" title="Stop if session loss exceeds this (0=disabled)">
                    </div>
                </div>
                
                <div class="btn-row">
                    <button class="btn-auto" id="gpt-auto" title="Receive APP signals only">AUTO OFF</button>
                    <button class="btn-scan" id="gpt-scan" title="Tampermonkey generates trades">SCAN OFF</button>
                </div>
                <div class="btn-row">
                    <button class="btn-switch" id="gpt-switch" title="Switch through favorites bar">SWITCH OFF</button>
                    <button class="btn-invert" id="gpt-invert" title="Invert signal direction">INVERT OFF</button>
                </div>
                <div class="btn-row">
                    <button class="btn-fetch" id="gpt-fetch">FETCH</button>
                    <button class="btn-reset" id="gpt-reset">RESET</button>
                </div>
                
                <div class="mode-indicator idle" id="gpt-mode">IDLE - All buttons OFF</div>
                
                <!-- Settings display from app -->
                <div class="settings-row">
                    <span class="label">Strategy:</span>
                    <span class="value" id="gpt-strategy">Auto</span>
                </div>
                <div class="settings-row">
                    <span class="label">Timeframe:</span>
                    <span class="value" id="gpt-timeframe">1m</span>
                </div>
                <div class="settings-row">
                    <span class="label">Signal Source:</span>
                    <span class="value" id="gpt-signal-source">App AI</span>
                </div>
                <div class="settings-row">
                    <span class="label">Favorites:</span>
                    <span class="value" id="gpt-favorites-count">0</span>
                </div>
                
                <div id="gpt-log">Ready - v6.6.1</div>
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
        
        // NEW: Win/Loss and Auto-Invert handlers - v6.6.0
        document.getElementById('gpt-reset-stats').addEventListener('click', resetWinLossStats);
        document.getElementById('gpt-auto-invert').addEventListener('click', toggleAutoInvert);
        document.getElementById('gpt-auto-place').addEventListener('click', toggleAutoPlace);
        document.getElementById('gpt-sound-toggle').addEventListener('click', toggleSoundNotifications);
        
        // Settings inputs
        document.getElementById('gpt-max-losses').addEventListener('change', (e) => {
            maxConsecutiveLosses = parseInt(e.target.value) || 3;
            GM_setValue('maxConsecutiveLosses', maxConsecutiveLosses);
            log(`Max consecutive losses set to ${maxConsecutiveLosses}`);
        });
        
        document.getElementById('gpt-stop-loss').addEventListener('change', (e) => {
            stopLossAmount = parseFloat(e.target.value) || 0;
            GM_setValue('stopLossAmount', stopLossAmount);
            log(`Stop loss set to $${stopLossAmount}`);
        });

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
        autoInvertActive = false;
        
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
    // AUTO-INVERT TOGGLE HANDLERS - v6.6.0
    // ===========================================
    function toggleAutoInvert() {
        autoInvertEnabled = !autoInvertEnabled;
        GM_setValue('autoInvertEnabled', autoInvertEnabled);
        
        const btn = document.getElementById('gpt-auto-invert');
        if (btn) {
            btn.textContent = autoInvertEnabled ? 'AUTO-INV ON' : 'AUTO-INV OFF';
            btn.className = 'btn-auto-invert' + (autoInvertEnabled ? ' on' : '');
        }
        
        const section = document.getElementById('gpt-auto-invert-section');
        if (section) {
            section.classList.toggle('active', autoInvertEnabled);
        }
        
        log(`AUTO-INVERT: ${autoInvertEnabled ? 'ON (will invert on loss)' : 'OFF'}`);
    }

    function toggleAutoPlace() {
        autoPlaceAfterLoss = !autoPlaceAfterLoss;
        GM_setValue('autoPlaceAfterLoss', autoPlaceAfterLoss);
        
        const btn = document.getElementById('gpt-auto-place');
        if (btn) {
            btn.textContent = autoPlaceAfterLoss ? 'AUTO-PLACE ON' : 'AUTO-PLACE OFF';
            btn.className = 'btn-auto-place' + (autoPlaceAfterLoss ? ' on' : '');
        }
        
        log(`AUTO-PLACE: ${autoPlaceAfterLoss ? 'ON (will auto-trade after loss)' : 'OFF (just invert next signal)'}`);
    }

    function toggleSoundNotifications() {
        soundNotificationsEnabled = !soundNotificationsEnabled;
        GM_setValue('soundNotificationsEnabled', soundNotificationsEnabled);
        
        const btn = document.getElementById('gpt-sound-toggle');
        if (btn) {
            btn.textContent = soundNotificationsEnabled ? '🔊 SOUND ON' : '🔇 SOUND OFF';
            btn.className = 'btn-sound' + (soundNotificationsEnabled ? ' on' : '');
        }
        
        log(`SOUND: ${soundNotificationsEnabled ? 'ON' : 'OFF'}`);
    }

    // Update win/loss display
    function updateWinLossDisplay() {
        const winsEl = document.getElementById('gpt-wins');
        const lossesEl = document.getElementById('gpt-losses');
        const streakEl = document.getElementById('gpt-streak');
        const profitEl = document.getElementById('gpt-profit');
        
        if (winsEl) winsEl.textContent = winLossStats.totalWins;
        if (lossesEl) lossesEl.textContent = winLossStats.totalLosses;
        
        if (streakEl) {
            if (winLossStats.consecutiveWins > 0) {
                streakEl.textContent = `🔥 ${winLossStats.consecutiveWins}W`;
                streakEl.style.color = '#22c55e';
            } else if (winLossStats.consecutiveLosses > 0) {
                streakEl.textContent = `❄️ ${winLossStats.consecutiveLosses}L`;
                streakEl.style.color = '#ef4444';
            } else {
                streakEl.textContent = '-';
                streakEl.style.color = '#9ca3af';
            }
        }
        
        if (profitEl) {
            const profit = winLossStats.sessionProfit;
            profitEl.textContent = `${profit >= 0 ? '+' : ''}$${profit.toFixed(2)}`;
            profitEl.className = 'stat-profit ' + (profit >= 0 ? 'positive' : 'negative');
        }
        
        // Update auto-invert section style
        const section = document.getElementById('gpt-auto-invert-section');
        if (section) {
            section.classList.toggle('active', autoInvertActive && autoInvertEnabled);
        }
        
        // Update invert button if auto-invert is active
        updateInvertButton();
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
            
            // Start monitoring for win/loss result - v6.6.0
            // Pass expiry time from signal or use default based on timeframe
            const expirySeconds = signal.expiration_seconds || signal.expiry || getExpiryFromTimeframe(signal.timeframe) || 60;
            startTradeResultMonitor(finalDirection, signal.amount || 1, expirySeconds);
            
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
    // SCAN HANDLING (SCAN button) - UPDATED v6.5.0
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

        // Determine which assets to scan based on SWITCH
        let assetsToScan = '';
        
        if (switchEnabled) {
            // SWITCH ON: Use favorites from the favorites bar
            if (favoritesFromBar.length === 0) {
                detectFavoritesBar();
            }
            
            if (favoritesFromBar.length > 0) {
                // Build asset list from detected favorites
                assetsToScan = favoritesFromBar.map(f => {
                    let norm = f.normalized;
                    if (!norm.includes('_OTC')) norm += '_OTC';
                    return norm;
                }).join(',');
                log(`🔍 Scanning ${favoritesFromBar.length} FAVORITES from bar...`);
            } else {
                // Fallback to hardcoded list if no favorites detected
                assetsToScan = 'EURUSD_OTC,GBPUSD_OTC,USDJPY_OTC,AUDUSD_OTC,EURJPY_OTC,GBPJPY_OTC';
                log('🔍 Scanning DEFAULT favorites (bar detection failed)...');
            }
        } else {
            // SWITCH OFF: Scan ONLY current asset
            const currentAssetRaw = getCurrentAsset();
            if (!currentAssetRaw) {
                log('Cannot determine current asset');
                return;
            }
            
            // Convert to API format (e.g., "EUR/USD OTC" -> "EURUSD_OTC")
            assetsToScan = currentAssetRaw
                .replace(/\s+/g, '')
                .replace('/', '')
                .replace('OTC', '_OTC')
                .toUpperCase();
            
            if (!assetsToScan.includes('_OTC')) {
                assetsToScan += '_OTC';
            }
            
            log(`🔍 Scanning CURRENT ASSET: ${assetsToScan}`);
        }

        updateStatusDot('trading');
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: CONFIG.API_URL + `/signals/scan-markets?assets=${assetsToScan}&min_confidence=${CONFIG.MIN_CONFIDENCE}`,
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
                        log(`Found ${signals.length} signal(s)`);
                        
                        // Pick the best signal (first one is highest confidence)
                        const bestSignal = signals[0];
                        
                        log(`🔍 SCAN SIGNAL: ${bestSignal.direction} ${bestSignal.symbol} (${Math.round(bestSignal.confidence)}%)`);
                        executeScanTrade(bestSignal);
                    } else {
                        log('No signals found');
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

        // Switch asset if SWITCH enabled - USE FAVORITES BAR (v6.5.0)
        if (switchEnabled && signal.symbol) {
            const targetNorm = normalizeAsset(signal.symbol);
            
            // First try to find matching favorite in the bar
            let switched = false;
            
            if (favoritesFromBar.length === 0) {
                detectFavoritesBar();
            }
            
            // Look for matching favorite
            const matchingFav = favoritesFromBar.find(f => 
                f.normalized.includes(targetNorm.substring(0, 6)) || 
                targetNorm.includes(f.normalized.substring(0, 6))
            );
            
            if (matchingFav) {
                log(`Found ${signal.symbol} in favorites bar`);
                switched = await clickFavoriteAsset(matchingFav);
            }
            
            // Fallback to search method if favorites bar click failed
            if (!switched) {
                log('Favorites bar click failed, trying search method...');
                switched = await switchToAsset(signal.symbol);
            }
            
            if (!switched) {
                log('Asset switch failed completely');
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
            
            // Start monitoring for win/loss result - v6.6.0
            // Pass expiry time from signal or use default
            const expirySeconds = signal.expiration_seconds || signal.expiry || getExpiryFromTimeframe(signal.timeframe) || 60;
            startTradeResultMonitor(finalDirection, signal.amount || 1, expirySeconds);
            
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
    // TRADE EXECUTION - WITH ABSOLUTE PROTECTION
    // ===========================================
    function clickTradeButton(isCall) {
        const now = Date.now();
        const direction = isCall ? 'CALL' : 'PUT';
        
        // GUARD 1: Global trade lock
        if (globalTradeLock) {
            log(`🛑 BLOCKED: Global trade lock active`);
            return false;
        }
        
        // GUARD 2: Time-based lock (5 seconds between ANY trades)
        if (now - lastTradeClickTime < TRADE_LOCK_MS) {
            const remaining = Math.round((TRADE_LOCK_MS - (now - lastTradeClickTime)) / 1000);
            log(`🛑 BLOCKED: Trade cooldown ${remaining}s`);
            return false;
        }
        
        // NOTE: Opposite trade block removed per user request (v6.4.2)
        // Users can now place opposite trades (BUY after SELL) without restriction
        
        const selector = isCall ? '.btn-call' : '.btn-put';
        const btn = document.querySelector(selector);
        
        if (btn && btn.offsetParent !== null) {
            // SET ALL LOCKS BEFORE CLICKING
            globalTradeLock = true;
            lastTradeClickTime = now;
            
            log(`✅ CLICKING: ${direction} button`);
            console.log(`[GPT TRADE] ${new Date().toISOString()} - ${direction}`);
            
            // Single click only
            btn.click();
            
            // Release global lock after 5 seconds
            setTimeout(() => {
                globalTradeLock = false;
                log(`🔓 Trade lock released`);
            }, TRADE_LOCK_MS);
            
            return true;
        }
        
        log(`❌ Button ${selector} not found`);
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
            
            // Step 2: Find and use search input IN THE DROPDOWN/MODAL ONLY
            log('Step 2: Looking for search input in dropdown...');
            await sleep(800);
            
            // Look for a modal/dropdown that appeared after clicking
            let searchInput = null;
            
            // First, try to find the dropdown/modal container
            const modalSelectors = [
                '.modal', '.dropdown', '.popup', '.dialog', '.overlay',
                '[class*="modal"]', '[class*="dropdown"]', '[class*="popup"]',
                '[class*="assets"]', '[class*="pair"]', '[class*="instrument"]',
                '[role="dialog"]', '[role="listbox"]'
            ];
            
            for (const modalSel of modalSelectors) {
                const modal = document.querySelector(modalSel);
                if (modal && modal.offsetParent !== null) {
                    // Look for input INSIDE this modal
                    const modalInput = modal.querySelector('input[type="search"], input[type="text"], input:not([type="number"])');
                    if (modalInput && modalInput.offsetParent !== null) {
                        searchInput = modalInput;
                        log(`Found search input in ${modalSel}`);
                        break;
                    }
                }
            }
            
            // If no modal input found, look for a search-specific input
            if (!searchInput) {
                const searchSelectors = [
                    'input[type="search"]',
                    'input[placeholder*="search" i]',
                    'input[placeholder*="find" i]',
                    'input[placeholder*="Search" i]',
                    'input[class*="search"]',
                    '.search input',
                    '[class*="search"] input'
                ];
                
                for (const sel of searchSelectors) {
                    const inp = document.querySelector(sel);
                    if (inp && inp.offsetParent !== null && !inp.disabled) {
                        searchInput = inp;
                        log(`Found search input: ${sel}`);
                        break;
                    }
                }
            }
            
            // IMPORTANT: Don't use number inputs or trade amount fields
            if (!searchInput) {
                const allInputs = document.querySelectorAll('input');
                for (const inp of allInputs) {
                    if (!inp || !inp.offsetParent || inp.disabled) continue;
                    
                    // Skip number inputs (trade amount)
                    if (inp.type === 'number') continue;
                    
                    // Skip inputs that look like amount fields
                    const placeholder = (inp.placeholder || '').toLowerCase();
                    const className = (inp.className || '').toLowerCase();
                    if (placeholder.includes('amount') || placeholder.includes('$') ||
                        className.includes('amount') || className.includes('trade')) {
                        continue;
                    }
                    
                    // Skip inputs that are small (likely amount fields)
                    if (inp.offsetWidth < 100) continue;
                    
                    // This might be the search input
                    // Check if it's in upper part of screen (dropdown area)
                    const rect = inp.getBoundingClientRect();
                    if (rect.top > 50 && rect.top < window.innerHeight - 100) {
                        searchInput = inp;
                        log(`Found potential search input at y=${Math.round(rect.top)}`);
                        break;
                    }
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
                log('No search input found - will browse list directly');
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
    // INITIALIZATION - UPDATED v6.6.0
    // ===========================================
    function init() {
        log('Initializing v6.6.0...');

        // Load saved settings (all default to false)
        autoEnabled = GM_getValue('autoEnabled', false);
        scanEnabled = GM_getValue('scanEnabled', false);
        switchEnabled = GM_getValue('switchEnabled', false);
        invertEnabled = GM_getValue('invertEnabled', false);
        
        // Load auto-invert settings - v6.6.0
        autoInvertEnabled = GM_getValue('autoInvertEnabled', false);
        autoPlaceAfterLoss = GM_getValue('autoPlaceAfterLoss', false);
        soundNotificationsEnabled = GM_getValue('soundNotificationsEnabled', true);
        maxConsecutiveLosses = GM_getValue('maxConsecutiveLosses', 3);
        stopLossAmount = GM_getValue('stopLossAmount', 0);
        
        // Load stats if any
        const savedStats = GM_getValue('winLossStats', null);
        if (savedStats) {
            try {
                winLossStats = JSON.parse(savedStats);
            } catch(e) {}
        }

        setTimeout(() => {
            createPanel();
            getCurrentAsset();
            
            // Detect favorites bar
            detectFavoritesBar();
            updateFavoritesDisplay();
            
            // Initialize auto-invert UI
            initAutoInvertUI();
            
            // Update win/loss display
            updateWinLossDisplay();
            
            manageIntervals();
            
            // Start heartbeat to backend (every 10 seconds)
            heartbeatInterval = setInterval(() => {
                sendHeartbeat();
                updateSettingsDisplay();
                // Save stats periodically
                GM_setValue('winLossStats', JSON.stringify(winLossStats));
            }, 10000);
            
            // Initial heartbeat
            sendHeartbeat();
            
            log('Ready! All buttons OFF by default');
        }, 2000);
    }
    
    // Initialize auto-invert UI elements
    function initAutoInvertUI() {
        const autoInvBtn = document.getElementById('gpt-auto-invert');
        const autoPlaceBtn = document.getElementById('gpt-auto-place');
        const soundBtn = document.getElementById('gpt-sound-toggle');
        const maxLossesInput = document.getElementById('gpt-max-losses');
        const stopLossInput = document.getElementById('gpt-stop-loss');
        
        if (autoInvBtn) {
            autoInvBtn.textContent = autoInvertEnabled ? 'AUTO-INV ON' : 'AUTO-INV OFF';
            autoInvBtn.className = 'btn-auto-invert' + (autoInvertEnabled ? ' on' : '');
        }
        if (autoPlaceBtn) {
            autoPlaceBtn.textContent = autoPlaceAfterLoss ? 'AUTO-PLACE ON' : 'AUTO-PLACE OFF';
            autoPlaceBtn.className = 'btn-auto-place' + (autoPlaceAfterLoss ? ' on' : '');
        }
        if (soundBtn) {
            soundBtn.textContent = soundNotificationsEnabled ? '🔊 SOUND ON' : '🔇 SOUND OFF';
            soundBtn.className = 'btn-sound' + (soundNotificationsEnabled ? ' on' : '');
        }
        if (maxLossesInput) {
            maxLossesInput.value = maxConsecutiveLosses;
        }
        if (stopLossInput) {
            stopLossInput.value = stopLossAmount;
        }
        
        const section = document.getElementById('gpt-auto-invert-section');
        if (section) {
            section.classList.toggle('active', autoInvertEnabled);
        }
    }
    
    // Update settings display from synced settings
    function updateSettingsDisplay() {
        const strategyEl = document.getElementById('gpt-strategy');
        const timeframeEl = document.getElementById('gpt-timeframe');
        const sourceEl = document.getElementById('gpt-signal-source');
        
        if (strategyEl) {
            strategyEl.textContent = selectedStrategy === 'auto' ? 'Auto' : selectedStrategy.replace(/_/g, ' ');
        }
        if (timeframeEl) {
            timeframeEl.textContent = selectedTimeframe;
        }
        if (sourceEl) {
            const sourceNames = {
                'app_ai': 'App AI',
                'tradingview': 'TradingView',
                'mt4': 'MetaTrader 4',
                'mt5': 'MetaTrader 5',
                'tampermonkey_scan': 'TM Scan'
            };
            sourceEl.textContent = sourceNames[signalSource] || signalSource;
        }
    }
    
    // Update favorites count display
    function updateFavoritesDisplay() {
        const el = document.getElementById('gpt-favorites-count');
        if (el) {
            el.textContent = favoritesFromBar.length > 0 
                ? `${favoritesFromBar.length} detected`
                : 'None detected';
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
