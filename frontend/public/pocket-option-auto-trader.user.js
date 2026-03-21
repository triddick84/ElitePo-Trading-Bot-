// ==UserScript==
// @name         GPT Signal Bot - Pocket Option Auto Trader
// @namespace    https://pocket-option-trader-1.preview.emergentagent.com
// @version      7.1.0
// @description  Auto-trade OTC forex on Pocket Option. v7.1.0 - LOCAL signal generation using actual OTC prices
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
// @connect      auto-trade-hub-25.preview.emergentagent.com
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
        API_URL: 'https://pocket-option-trader-1.preview.emergentagent.com/api',
        APP_POLL_INTERVAL: 3000,     // 3 seconds for app signals
        SCAN_INTERVAL: 5000,         // 5 seconds for scanning
        TRADE_COOLDOWN_SCAN: 30000,  // 30 seconds between SCAN trades
        TRADE_COOLDOWN_APP: 5000,    // 5 seconds between APP trades
        MIN_CONFIDENCE: 70,
        MIN_PAYOUT: 65,
        DEBUG: true,
        USE_LOCAL_SIGNALS: true,  // v7.1.0: Generate signals locally using actual OTC prices
        LOCAL_CANDLE_COUNT: 50,   // Number of candles to analyze
    };

    // ===========================================
    // v7.1.0 LOCAL SIGNAL GENERATION ENGINE
    // Uses actual Pocket Option OTC prices
    // ===========================================
    const LocalSignalEngine = {
        candles: [],           // Scraped candle data
        lastPrice: null,       // Last known price
        lastUpdate: 0,         // Timestamp of last price update
        
        // RSI calculation
        calculateRSI(prices, period = 2) {
            if (prices.length < period + 1) return 50;
            
            let gains = 0, losses = 0;
            for (let i = prices.length - period; i < prices.length; i++) {
                const change = prices[i] - prices[i - 1];
                if (change > 0) gains += change;
                else losses -= change;
            }
            
            if (losses === 0) return 100;
            const rs = gains / losses;
            return 100 - (100 / (1 + rs));
        },
        
        // EMA calculation
        calculateEMA(prices, period) {
            if (prices.length < period) return prices[prices.length - 1];
            
            const k = 2 / (period + 1);
            let ema = prices.slice(0, period).reduce((a, b) => a + b, 0) / period;
            
            for (let i = period; i < prices.length; i++) {
                ema = prices[i] * k + ema * (1 - k);
            }
            return ema;
        },
        
        // Stochastic calculation
        calculateStochastic(highs, lows, closes, period = 5) {
            if (closes.length < period) return { k: 50, d: 50 };
            
            const recentHighs = highs.slice(-period);
            const recentLows = lows.slice(-period);
            const highestHigh = Math.max(...recentHighs);
            const lowestLow = Math.min(...recentLows);
            const currentClose = closes[closes.length - 1];
            
            const k = ((currentClose - lowestLow) / (highestHigh - lowestLow + 0.00001)) * 100;
            return { k, d: k }; // Simplified - d is smoothed k
        },
        
        // Bollinger Bands
        calculateBollingerBands(prices, period = 20, stdDev = 2) {
            if (prices.length < period) {
                const last = prices[prices.length - 1];
                return { upper: last, middle: last, lower: last };
            }
            
            const slice = prices.slice(-period);
            const sma = slice.reduce((a, b) => a + b, 0) / period;
            const variance = slice.reduce((sum, p) => sum + Math.pow(p - sma, 2), 0) / period;
            const std = Math.sqrt(variance);
            
            return {
                upper: sma + stdDev * std,
                middle: sma,
                lower: sma - stdDev * std
            };
        },
        
        // Detect candlestick patterns
        detectPattern(candles) {
            if (candles.length < 3) return { bullish: false, bearish: false, name: null };
            
            const curr = candles[candles.length - 1];
            const prev = candles[candles.length - 2];
            
            const body = Math.abs(curr.close - curr.open);
            const upperWick = curr.high - Math.max(curr.open, curr.close);
            const lowerWick = Math.min(curr.open, curr.close) - curr.low;
            const range = curr.high - curr.low || 0.00001;
            
            // Hammer (bullish)
            if (lowerWick > body * 2 && upperWick < body * 0.5 && body < range * 0.4) {
                return { bullish: true, bearish: false, name: 'HAMMER' };
            }
            
            // Shooting Star (bearish)
            if (upperWick > body * 2 && lowerWick < body * 0.5 && body < range * 0.4) {
                return { bullish: false, bearish: true, name: 'SHOOTING_STAR' };
            }
            
            // Bullish Engulfing
            if (curr.close > curr.open && prev.close < prev.open && 
                curr.close > prev.open && curr.open < prev.close) {
                return { bullish: true, bearish: false, name: 'BULLISH_ENGULFING' };
            }
            
            // Bearish Engulfing
            if (curr.close < curr.open && prev.close > prev.open && 
                curr.close < prev.open && curr.open > prev.close) {
                return { bullish: false, bearish: true, name: 'BEARISH_ENGULFING' };
            }
            
            // Doji
            if (body < range * 0.1) {
                return { bullish: false, bearish: false, name: 'DOJI' };
            }
            
            return { bullish: false, bearish: false, name: null };
        },
        
        // MAIN: Generate signal from candle data
        generateSignal(candles) {
            if (!candles || candles.length < 20) {
                return null;
            }
            
            const closes = candles.map(c => c.close);
            const highs = candles.map(c => c.high);
            const lows = candles.map(c => c.low);
            const currentPrice = closes[closes.length - 1];
            
            // Calculate indicators
            const rsi2 = this.calculateRSI(closes, 2);
            const rsi14 = this.calculateRSI(closes, 14);
            const ema5 = this.calculateEMA(closes, 5);
            const ema10 = this.calculateEMA(closes, 10);
            const ema20 = this.calculateEMA(closes, 20);
            const stoch = this.calculateStochastic(highs, lows, closes, 5);
            const bb = this.calculateBollingerBands(closes, 20, 2);
            const pattern = this.detectPattern(candles);
            
            // Count confirmations
            let callConfs = [];
            let putConfs = [];
            
            // RSI extremes
            if (rsi2 < 10) callConfs.push('RSI2_EXTREME');
            else if (rsi2 < 20) callConfs.push('RSI2_OVERSOLD');
            
            if (rsi2 > 90) putConfs.push('RSI2_EXTREME');
            else if (rsi2 > 80) putConfs.push('RSI2_OVERBOUGHT');
            
            // Stochastic
            if (stoch.k < 20) callConfs.push('STOCH_OVERSOLD');
            if (stoch.k > 80) putConfs.push('STOCH_OVERBOUGHT');
            
            // Bollinger Bands
            if (currentPrice <= bb.lower) callConfs.push('BB_LOWER');
            if (currentPrice >= bb.upper) putConfs.push('BB_UPPER');
            
            // EMA trend
            if (ema5 > ema10 && ema10 > ema20) putConfs.push('TREND_UP_REVERSAL');
            if (ema5 < ema10 && ema10 < ema20) callConfs.push('TREND_DOWN_REVERSAL');
            
            // Candlestick patterns
            if (pattern.bullish) callConfs.push(pattern.name);
            if (pattern.bearish) putConfs.push(pattern.name);
            
            // Momentum
            if (closes.length > 5) {
                const momentum = closes[closes.length - 1] - closes[closes.length - 5];
                if (momentum < 0 && rsi2 < 30) callConfs.push('MOMENTUM_REVERSAL');
                if (momentum > 0 && rsi2 > 70) putConfs.push('MOMENTUM_REVERSAL');
            }
            
            // Determine signal (need 3+ confirmations)
            const minConfs = 3;
            
            if (callConfs.length >= minConfs && callConfs.length > putConfs.length) {
                const confidence = Math.min(95, 60 + callConfs.length * 8);
                return {
                    direction: 'CALL',
                    confidence,
                    confirmations: callConfs,
                    count: callConfs.length,
                    price: currentPrice,
                    indicators: { rsi2, rsi14, stoch: stoch.k, bb_pos: 'lower' }
                };
            }
            
            if (putConfs.length >= minConfs && putConfs.length > callConfs.length) {
                const confidence = Math.min(95, 60 + putConfs.length * 8);
                return {
                    direction: 'PUT',
                    confidence,
                    confirmations: putConfs,
                    count: putConfs.length,
                    price: currentPrice,
                    indicators: { rsi2, rsi14, stoch: stoch.k, bb_pos: 'upper' }
                };
            }
            
            return null;
        }
    };

    // ===========================================
    // v7.1.0 POCKET OPTION PRICE SCRAPER
    // ===========================================
    const PriceScraperV2 = {
        priceHistory: [],
        candleHistory: [],
        maxCandles: 100,
        lastScrapedPrice: null,
        
        // Scrape current price from Pocket Option UI
        scrapeCurrentPrice() {
            // Try multiple selectors for price display
            const selectors = [
                '.chart-area .price',
                '.current-price',
                '[class*="current-price"]',
                '[class*="chart"] [class*="price"]',
                '.trading-chart .value',
                '[data-testid="current-price"]',
                '.chart-header .price',
                '.price-display',
                '.live-price'
            ];
            
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    if (!el || !el.offsetParent) continue;
                    
                    const text = (el.textContent || el.innerText || '').trim();
                    // Match forex prices like 1.08234 or 108.234
                    const match = text.match(/(\d{1,3}\.\d{3,5})/);
                    if (match) {
                        const price = parseFloat(match[1]);
                        if (price > 0.1 && price < 300) {
                            this.lastScrapedPrice = price;
                            return price;
                        }
                    }
                }
            }
            
            // Try finding price in SVG chart text elements
            const svgTexts = document.querySelectorAll('svg text, svg tspan');
            for (const el of svgTexts) {
                const text = el.textContent?.trim() || '';
                const match = text.match(/^(\d{1,3}\.\d{3,5})$/);
                if (match) {
                    const price = parseFloat(match[1]);
                    if (price > 0.1 && price < 300) {
                        this.lastScrapedPrice = price;
                        return price;
                    }
                }
            }
            
            return null;
        },
        
        // Build candle from price updates
        buildCandle(price, intervalMs = 1000) {
            const now = Date.now();
            
            // Add to price history
            this.priceHistory.push({ price, time: now });
            
            // Keep only recent prices (last 2 minutes)
            const cutoff = now - 120000;
            this.priceHistory = this.priceHistory.filter(p => p.time > cutoff);
            
            // Build candle every second (or specified interval)
            if (this.priceHistory.length < 2) return null;
            
            const recentPrices = this.priceHistory.filter(p => p.time > now - intervalMs);
            if (recentPrices.length === 0) return null;
            
            const open = recentPrices[0].price;
            const close = recentPrices[recentPrices.length - 1].price;
            const high = Math.max(...recentPrices.map(p => p.price));
            const low = Math.min(...recentPrices.map(p => p.price));
            
            return { open, high, low, close, time: now };
        },
        
        // Add a new candle to history
        addCandle(candle) {
            if (!candle) return;
            
            this.candleHistory.push(candle);
            
            // Keep only recent candles
            if (this.candleHistory.length > this.maxCandles) {
                this.candleHistory.shift();
            }
        },
        
        // Get candle history for analysis
        getCandles() {
            return this.candleHistory;
        },
        
        // Clear history
        reset() {
            this.priceHistory = [];
            this.candleHistory = [];
        }
    };

    // ===========================================
    // STATE - ALL BUTTONS DEFAULT TO OFF
    // ===========================================
    // v7.1.0 - Local signal generation using actual OTC prices
    // AUTO = Receives APP signals and places trades
    // SCAN = Generates LOCAL signals using scraped OTC prices
    //   - If AUTO ON: SCAN only checks currently selected asset (no switching)
    //   - If AUTO OFF: SCAN checks ALL favorites, auto-switches to best signal asset
    // INVERT = Local toggle for direction inversion
    
    let autoEnabled = false;    // Receive APP signals only
    let scanEnabled = false;    // Tampermonkey generates trades
    let invertEnabled = false;  // Local invert toggle
    
    // Trading state - v6.8.4 uses globalTradeLock exclusively
    let lastAppTradeTime = 0;
    let lastScanTradeTime = 0;
    let lastAppSignalId = '';
    let tradeCount = 0;
    let currentAsset = null;
    
    // CRITICAL: Global trade lock to prevent double trades
    let globalTradeLock = false;
    let lastTradeClickTime = 0;
    const TRADE_LOCK_MS = 5000;  // 5 second absolute lock after any trade
    
    // v6.8.2: Trade execution queue to prevent race conditions
    let tradeQueue = [];
    let isProcessingQueue = false;
    let lastTradeDirection = null;  // Track last trade direction
    let lastTradeTimestamp = 0;     // Track last trade time for duplicate detection
    const DUPLICATE_TRADE_WINDOW_MS = 3000;  // Reject same-direction trade within 3s
    
    // v6.8.3: Safety timeout to prevent isTrading getting stuck
    // v6.8.4: Removed isTrading flag entirely - using only globalTradeLock
    let tradingFlagTimeout = null;
    const TRADING_FLAG_TIMEOUT_MS = 10000;  // Legacy - kept for reference
    
    // NEW: Enhanced control settings from backend
    let selectedStrategy = 'auto';
    let selectedTimeframe = '1m';
    let signalSource = 'app_ai';  // app_ai, tradingview, mt4, mt5, tampermonkey_scan
    let favoritesFromBar = [];    // Detected from PO favorites bar
    let currentFavoriteIndex = 0; // For cycling through favorites
    
    // ===========================================
    // MANUAL WIN/LOSS + MARTINGALE SYSTEM - v6.7.0
    // ===========================================
    let winLossStats = {
        totalWins: 0,
        totalLosses: 0,
        consecutiveWins: 0,
        consecutiveLosses: 0,
        sessionProfit: 0,
        lastTradeResult: null,
        tradeHistory: []
    };
    
    // Manual invert on loss
    let manualInvertActive = false;     // User pressed LOSS button - signals inverted
    
    // ===========================================
    // MONEY MANAGEMENT SYSTEM - v6.8.0
    // ===========================================
    let moneyManagement = {
        // Account settings
        accountBalance: 100,            // User's account balance
        riskPercentage: 2,              // Risk % per trade (1-10%)
        
        // Payout tracking (per asset)
        currentPayout: 92,              // Current asset payout %
        payoutByAsset: {},              // Cache of payouts by asset
        
        // Session settings
        sessionTarget: 10,              // Target trades per session
        sessionTrades: 0,               // Trades completed this session
        sessionStartBalance: 100,       // Balance at session start
        profitTarget: 10,               // Target profit % for session
        stopLossPercent: 20,            // Stop loss % of balance
        
        // Calculated values
        baseTradeAmount: 1,             // Calculated base trade amount
        currentTradeAmount: 1,          // Current trade amount (with martingale)
        totalInvested: 0,               // Total amount invested in martingale chain
        
        // Session tracking
        sessionActive: false,
        sessionStartTime: null
    };
    
    // Smart Martingale (payout-aware)
    let smartMartingale = {
        enabled: false,
        step: 0,
        maxSteps: 6,
        totalLoss: 0,                   // Accumulated loss to recover
        targetProfit: 0.5,              // Target profit after recovery ($)
        sequence: []                    // Array of trade amounts for recovery
    };
    
    // Legacy martingale (keep for compatibility)
    let martingaleEnabled = false;
    let martingaleStep = 0;
    let martingaleBaseAmount = 1;
    let martingaleMultiplier = 2;
    let martingaleMaxSteps = 5;
    let currentTradeAmount = 1;
    
    // Sound notifications
    let soundNotificationsEnabled = true;
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
    // ===========================================
    // CONSOLE LOG SYSTEM - v7.0.0
    // ===========================================
    const consoleLog = [];
    const MAX_LOG_LINES = 50;
    
    function log(msg) {
        const ts = new Date().toLocaleTimeString();
        const logEntry = `${ts}: ${msg}`;
        
        // Add to console log array
        consoleLog.push(logEntry);
        if (consoleLog.length > MAX_LOG_LINES) {
            consoleLog.shift();
        }
        
        // Update console window if visible
        updateConsoleWindow();
        
        // Also log to browser console
        console.log(`[GPT v7.0.0] ${logEntry}`);
        
        // Update status bar
        const logEl = document.getElementById('gpt-log');
        if (logEl) logEl.textContent = msg;
    }
    
    function updateConsoleWindow() {
        const consoleEl = document.getElementById('gpt-console-content');
        if (consoleEl) {
            consoleEl.innerHTML = consoleLog.map(line => {
                let color = '#9ca3af';
                if (line.includes('✅') || line.includes('TRADE:')) color = '#22c55e';
                else if (line.includes('❌') || line.includes('BLOCKED') || line.includes('error')) color = '#ef4444';
                else if (line.includes('⚠️') || line.includes('WARNING')) color = '#f59e0b';
                else if (line.includes('🔍') || line.includes('SCAN')) color = '#3b82f6';
                else if (line.includes('🔄') || line.includes('SWITCH')) color = '#a78bfa';
                else if (line.includes('📡') || line.includes('API')) color = '#60a5fa';
                return `<div style="color:${color};margin:1px 0;word-break:break-all;">${line}</div>`;
            }).join('');
            consoleEl.scrollTop = consoleEl.scrollHeight;
        }
    }
    
    function toggleConsoleWindow() {
        const consoleWin = document.getElementById('gpt-console-window');
        if (consoleWin) {
            const isVisible = consoleWin.style.display !== 'none';
            consoleWin.style.display = isVisible ? 'none' : 'block';
            log(isVisible ? 'Console hidden' : 'Console shown');
        }
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
    // SET TRADE AMOUNT ON POCKET OPTION UI - v6.8.0
    // ===========================================
    function setTradeAmountOnUI(amount) {
        // Round to 2 decimal places, minimum $1
        const finalAmount = Math.max(1, Math.round(amount * 100) / 100);
        
        log(`💰 Setting trade amount: $${finalAmount}`);
        
        // Find the trade amount input on Pocket Option
        const amountSelectors = [
            'input[type="number"][class*="amount"]',
            'input.amount-input',
            'input[data-testid="amount"]',
            '.trade-amount input',
            'input[type="number"]',
            '[class*="input-amount"] input',
            '[class*="trade"] input[type="number"]'
        ];
        
        let inputField = null;
        
        // Try specific selectors first
        for (const sel of amountSelectors) {
            const inputs = document.querySelectorAll(sel);
            for (const inp of inputs) {
                if (inp && inp.offsetParent !== null) {
                    // Check if it's likely the trade amount input (near buttons, reasonable position)
                    const rect = inp.getBoundingClientRect();
                    // Trade amount is usually on the right side or in trading area
                    if (rect.right > window.innerWidth / 2 || rect.top > 100) {
                        inputField = inp;
                        break;
                    }
                }
            }
            if (inputField) break;
        }
        
        // Fallback: find any number input in trading area
        if (!inputField) {
            const allInputs = document.querySelectorAll('input[type="number"]');
            for (const inp of allInputs) {
                if (!inp || !inp.offsetParent) continue;
                
                const rect = inp.getBoundingClientRect();
                // Skip if it's too small (likely a quantity spinner) or in header area
                if (rect.width < 60 || rect.top < 50) continue;
                
                // Check if near trade buttons
                const callBtn = document.querySelector('.btn-call');
                const putBtn = document.querySelector('.btn-put');
                
                if (callBtn || putBtn) {
                    const btnRect = (callBtn || putBtn).getBoundingClientRect();
                    // Input should be relatively close to trade buttons (within 300px)
                    if (Math.abs(rect.top - btnRect.top) < 300) {
                        inputField = inp;
                        break;
                    }
                }
            }
        }
        
        if (inputField) {
            // Save old value for logging
            const oldValue = inputField.value;
            
            // Set the new value
            inputField.focus();
            inputField.value = finalAmount;
            
            // Dispatch events to trigger any listeners
            inputField.dispatchEvent(new Event('input', { bubbles: true }));
            inputField.dispatchEvent(new Event('change', { bubbles: true }));
            inputField.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
            
            // Blur to finalize
            inputField.blur();
            
            log(`✅ Trade amount updated: $${oldValue} → $${finalAmount}`);
            return true;
        } else {
            log(`⚠️ Trade amount input not found - please set manually to $${finalAmount}`);
            return false;
        }
    }
    
    // Detect current trade amount from UI
    function getCurrentTradeAmountFromUI() {
        const amountSelectors = [
            'input[type="number"][class*="amount"]',
            'input.amount-input',
            '.trade-amount input',
            'input[type="number"]'
        ];
        
        for (const sel of amountSelectors) {
            const inputs = document.querySelectorAll(sel);
            for (const inp of inputs) {
                if (inp && inp.offsetParent !== null && inp.value) {
                    const value = parseFloat(inp.value);
                    if (value >= 1 && value <= 10000) {
                        return value;
                    }
                }
            }
        }
        
        return null;
    }
    
    // Detect current account balance from UI
    function detectAccountBalance() {
        // Look for balance display on Pocket Option
        const balanceSelectors = [
            '[class*="balance"]',
            '[class*="account-value"]',
            '[class*="user-balance"]',
            '[data-testid="balance"]',
            '.balance',
            '.account-balance'
        ];
        
        for (const sel of balanceSelectors) {
            const elements = document.querySelectorAll(sel);
            for (const el of elements) {
                if (!el || !el.offsetParent) continue;
                
                const text = el.textContent || '';
                // Match patterns like "$1,234.56" or "1234.56" or "$ 1,234.56"
                const match = text.match(/\$?\s?([\d,]+\.?\d*)/);
                if (match) {
                    const balance = parseFloat(match[1].replace(/,/g, ''));
                    if (balance >= 1 && balance <= 1000000) {
                        log(`📊 Detected balance: $${balance}`);
                        moneyManagement.accountBalance = balance;
                        
                        // Update session start balance if session is starting
                        if (!moneyManagement.sessionActive) {
                            moneyManagement.sessionStartBalance = balance;
                        }
                        
                        return balance;
                    }
                }
            }
        }
        
        return moneyManagement.accountBalance; // Return cached value
    }

    // ===========================================
    // MANUAL WIN/LOSS HANDLERS - v6.8.0 (with Money Management)
    // User presses buttons to record wins/losses
    // ===========================================
    
    // Called when user presses WIN button
    function handleManualWin() {
        // Get current trade amount (what was actually wagered)
        const tradeAmount = moneyManagement.currentTradeAmount || currentTradeAmount;
        
        // Update stats
        winLossStats.totalWins++;
        winLossStats.consecutiveWins++;
        winLossStats.consecutiveLosses = 0;
        winLossStats.lastTradeResult = 'win';
        
        // Detect current payout from UI
        detectCurrentPayout();
        
        // Calculate profit based on actual payout
        const payout = moneyManagement.currentPayout / 100;
        const profit = tradeAmount * payout;
        winLossStats.sessionProfit += profit;
        
        // Update balance tracking
        moneyManagement.accountBalance += profit;
        moneyManagement.sessionTrades++;
        
        // Reset inversion on win (if it was active)
        if (manualInvertActive) {
            manualInvertActive = false;
            invertEnabled = false;
            GM_setValue('invertEnabled', false);
            log(`✅ WIN +$${profit.toFixed(2)} - Inversion RESET`);
        } else {
            log(`✅ WIN +$${profit.toFixed(2)}`);
        }
        
        // Reset martingale/smart martingale on win
        if (smartMartingale.enabled) {
            // Reset smart martingale
            resetSmartMartingale();
            
            // Recalculate base amount with new balance
            calculateBaseTradeAmount();
            
            log(`💰 Martingale reset. New base: $${moneyManagement.baseTradeAmount.toFixed(2)}`);
        } else if (martingaleEnabled) {
            // Legacy martingale
            martingaleStep = 0;
            currentTradeAmount = martingaleBaseAmount;
        }
        
        // Update trade amount on Pocket Option UI
        const newAmount = smartMartingale.enabled ? 
            moneyManagement.currentTradeAmount : 
            (martingaleEnabled ? martingaleBaseAmount : currentTradeAmount);
        setTradeAmountOnUI(newAmount);
        
        // Play sound
        if (soundNotificationsEnabled) playWinSound();
        
        // Update all displays
        updateWinLossDisplay();
        updateMartingaleDisplay();
        updateMoneyManagementDisplay();
        updateInvertButton();
        
        // Check session limits
        checkSessionLimits();
        
        // Sync to backend
        syncStatsToBackend();
    }
    
    // Called when user presses LOSS button
    function handleManualLoss() {
        // Get current trade amount (what was lost)
        const tradeAmount = moneyManagement.currentTradeAmount || currentTradeAmount;
        
        // Update stats
        winLossStats.totalLosses++;
        winLossStats.consecutiveLosses++;
        winLossStats.consecutiveWins = 0;
        winLossStats.lastTradeResult = 'loss';
        winLossStats.sessionProfit -= tradeAmount;
        
        // Update balance tracking
        moneyManagement.accountBalance -= tradeAmount;
        moneyManagement.sessionTrades++;
        
        // Toggle inversion on loss
        manualInvertActive = !manualInvertActive;
        invertEnabled = manualInvertActive;
        GM_setValue('invertEnabled', invertEnabled);
        
        // Detect current payout for next trade calculation
        detectCurrentPayout();
        
        let nextAmount = tradeAmount;
        
        if (smartMartingale.enabled) {
            // Smart Martingale: Calculate exact amount to recover losses + profit
            smartMartingale.totalLoss += tradeAmount;
            smartMartingale.step++;
            moneyManagement.totalInvested += tradeAmount;
            
            if (smartMartingale.step < smartMartingale.maxSteps) {
                // Calculate next trade to recover all losses + target profit
                const payout = moneyManagement.currentPayout;
                nextAmount = calculateSmartMartingale(
                    smartMartingale.totalLoss, 
                    smartMartingale.targetProfit,
                    payout
                );
                
                moneyManagement.currentTradeAmount = nextAmount;
                smartMartingale.sequence.push(nextAmount);
                
                log(`❌ LOSS -$${tradeAmount.toFixed(2)} | INVERTED: ${manualInvertActive ? 'ON' : 'OFF'}`);
                log(`📈 Martingale Step ${smartMartingale.step}: $${nextAmount.toFixed(2)} to recover $${smartMartingale.totalLoss.toFixed(2)}`);
            } else {
                log(`🛑 MAX MARTINGALE STEPS (${smartMartingale.maxSteps}) - Total loss: $${smartMartingale.totalLoss.toFixed(2)}`);
                playStopSound();
                resetSmartMartingale();
                nextAmount = moneyManagement.baseTradeAmount;
            }
        } else if (martingaleEnabled) {
            // Legacy Martingale: Simple multiplier
            if (martingaleStep < martingaleMaxSteps) {
                martingaleStep++;
                nextAmount = martingaleBaseAmount * Math.pow(martingaleMultiplier, martingaleStep);
                currentTradeAmount = nextAmount;
                
                log(`❌ LOSS -$${tradeAmount.toFixed(2)} | INVERTED: ${manualInvertActive ? 'ON' : 'OFF'} | Martingale Step ${martingaleStep}: $${nextAmount.toFixed(2)}`);
            } else {
                log(`🛑 MAX MARTINGALE REACHED! Step ${martingaleStep}`);
                playStopSound();
            }
        } else {
            log(`❌ LOSS -$${tradeAmount.toFixed(2)} | INVERTED: ${manualInvertActive ? 'ON' : 'OFF'}`);
        }
        
        // Update trade amount on Pocket Option UI
        setTradeAmountOnUI(nextAmount);
        
        // Play sound
        if (soundNotificationsEnabled) playLossSound();
        
        // Update all displays
        updateInvertButton();
        updateWinLossDisplay();
        updateMartingaleDisplay();
        updateMoneyManagementDisplay();
        
        // Check session limits
        checkSessionLimits();
        
        // Sync to backend
        syncStatsToBackend();
    }
    
    // Calculate current martingale amount
    function calculateMartingaleAmount() {
        if (!martingaleEnabled) return martingaleBaseAmount;
        return martingaleBaseAmount * Math.pow(martingaleMultiplier, martingaleStep);
    }
    
    // Reset martingale to base
    function resetMartingale() {
        martingaleStep = 0;
        currentTradeAmount = martingaleBaseAmount;
        manualInvertActive = false;
        invertEnabled = false;
        GM_setValue('invertEnabled', false);
        updateInvertButton();
        updateMartingaleDisplay();
        log(`🔄 Martingale reset to $${martingaleBaseAmount}`);
    }
    
    // Update martingale display
    function updateMartingaleDisplay() {
        const stepEl = document.getElementById('gpt-martingale-step');
        const amountEl = document.getElementById('gpt-martingale-amount');
        const statusEl = document.getElementById('gpt-martingale-status');
        
        if (stepEl) stepEl.textContent = martingaleStep;
        if (amountEl) amountEl.textContent = `$${currentTradeAmount.toFixed(2)}`;
        if (statusEl) {
            if (martingaleStep >= martingaleMaxSteps) {
                statusEl.textContent = '⚠️ MAX';
                statusEl.style.color = '#ef4444';
            } else if (martingaleStep > 0) {
                statusEl.textContent = `Step ${martingaleStep}/${martingaleMaxSteps}`;
                statusEl.style.color = '#f59e0b';
            } else {
                statusEl.textContent = 'Base';
                statusEl.style.color = '#22c55e';
            }
        }
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
            profitEl.style.color = profit >= 0 ? '#22c55e' : '#ef4444';
        }
        
        // Update invert indicator
        const invertIndicator = document.getElementById('gpt-invert-status');
        if (invertIndicator) {
            invertIndicator.textContent = manualInvertActive ? '🔄 INVERTED' : '';
            invertIndicator.style.color = '#f59e0b';
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
                manual_invert_active: manualInvertActive,
                martingale_step: martingaleStep,
                current_trade_amount: currentTradeAmount
            }),
            timeout: 5000,
            onload: function(res) {},
            onerror: function() {}
        });
    }
    
    // Reset all stats
    function resetAllStats() {
        winLossStats = {
            totalWins: 0,
            totalLosses: 0,
            consecutiveWins: 0,
            consecutiveLosses: 0,
            sessionProfit: 0,
            lastTradeResult: null,
            tradeHistory: []
        };
        resetMartingale();
        resetSmartMartingale();
        updateWinLossDisplay();
        updateMoneyManagementDisplay();
        syncStatsToBackend();
        log('📊 All stats reset');
    }

    // ===========================================
    // MONEY MANAGEMENT FUNCTIONS - v6.8.0
    // ===========================================
    
    // Calculate base trade amount from balance and risk %
    function calculateBaseTradeAmount() {
        const balance = moneyManagement.accountBalance;
        const riskPercent = moneyManagement.riskPercentage;
        
        // Base trade = Balance * Risk% / 100
        moneyManagement.baseTradeAmount = Math.max(1, Math.round((balance * riskPercent / 100) * 100) / 100);
        moneyManagement.currentTradeAmount = moneyManagement.baseTradeAmount;
        
        log(`💰 Base trade: $${moneyManagement.baseTradeAmount} (${riskPercent}% of $${balance})`);
        
        return moneyManagement.baseTradeAmount;
    }
    
    // Detect payout percentage from Pocket Option UI
    function detectCurrentPayout() {
        // Look for payout percentage on the trading interface
        const payoutSelectors = [
            '[class*="payout"]',
            '[class*="percent"]',
            '[class*="profit-percent"]',
            '.trading-payout',
            '[data-testid="payout"]'
        ];
        
        for (const sel of payoutSelectors) {
            try {
                const elements = document.querySelectorAll(sel);
                for (const el of elements) {
                    const text = el.textContent || '';
                    const match = text.match(/(\d{1,3})%/);
                    if (match) {
                        const payout = parseInt(match[1]);
                        if (payout >= 50 && payout <= 100) {
                            moneyManagement.currentPayout = payout;
                            
                            // Cache by asset
                            const asset = getCurrentAsset();
                            if (asset) {
                                moneyManagement.payoutByAsset[asset] = payout;
                            }
                            
                            return payout;
                        }
                    }
                }
            } catch(e) {}
        }
        
        // Fallback: search for any % value near trading area
        const allText = document.body.innerText || '';
        const matches = allText.match(/(\d{2})%\s*(payout|profit)?/gi);
        if (matches) {
            for (const m of matches) {
                const num = parseInt(m);
                if (num >= 70 && num <= 95) {
                    moneyManagement.currentPayout = num;
                    return num;
                }
            }
        }
        
        return moneyManagement.currentPayout; // Return cached value
    }
    
    // Calculate smart martingale sequence based on payout
    function calculateSmartMartingale(totalLoss, targetProfit, payout) {
        // To recover loss + make profit with given payout:
        // Required win = (totalLoss + targetProfit) / (payout / 100)
        
        const payoutDecimal = payout / 100;
        const required = (totalLoss + targetProfit) / payoutDecimal;
        
        return Math.ceil(required * 100) / 100; // Round up to cents
    }
    
    // Start a new trading session
    function startSession() {
        moneyManagement.sessionActive = true;
        moneyManagement.sessionStartTime = Date.now();
        moneyManagement.sessionStartBalance = moneyManagement.accountBalance;
        moneyManagement.sessionTrades = 0;
        
        // Reset stats for new session
        winLossStats.sessionProfit = 0;
        winLossStats.totalWins = 0;
        winLossStats.totalLosses = 0;
        
        calculateBaseTradeAmount();
        resetSmartMartingale();
        
        log(`🎯 Session started: Target ${moneyManagement.sessionTarget} trades, $${moneyManagement.baseTradeAmount}/trade`);
        updateMoneyManagementDisplay();
        updateSessionDisplay();
    }
    
    // End trading session
    function endSession() {
        moneyManagement.sessionActive = false;
        const duration = Date.now() - moneyManagement.sessionStartTime;
        const durationMins = Math.round(duration / 60000);
        
        const profit = winLossStats.sessionProfit;
        const roi = ((profit / moneyManagement.sessionStartBalance) * 100).toFixed(2);
        
        log(`🏁 Session ended: ${moneyManagement.sessionTrades} trades, P/L: $${profit.toFixed(2)} (${roi}% ROI) in ${durationMins}min`);
        
        updateSessionDisplay();
    }
    
    // Check session limits (profit target, stop loss)
    function checkSessionLimits() {
        const balance = moneyManagement.accountBalance;
        const startBalance = moneyManagement.sessionStartBalance;
        const profitTarget = startBalance * (moneyManagement.profitTarget / 100);
        const stopLoss = startBalance * (moneyManagement.stopLossPercent / 100);
        
        // Check profit target
        if (winLossStats.sessionProfit >= profitTarget) {
            log(`🎉 PROFIT TARGET REACHED: $${winLossStats.sessionProfit.toFixed(2)}`);
            playWinSound();
            endSession();
            return true;
        }
        
        // Check stop loss
        if (winLossStats.sessionProfit <= -stopLoss) {
            log(`🛑 STOP LOSS HIT: $${winLossStats.sessionProfit.toFixed(2)}`);
            playStopSound();
            endSession();
            return true;
        }
        
        // Check trade count
        if (moneyManagement.sessionTrades >= moneyManagement.sessionTarget) {
            log(`📊 SESSION TARGET REACHED: ${moneyManagement.sessionTrades} trades`);
            endSession();
            return true;
        }
        
        return false;
    }
    
    // Reset smart martingale
    function resetSmartMartingale() {
        smartMartingale.step = 0;
        smartMartingale.totalLoss = 0;
        smartMartingale.sequence = [];
        moneyManagement.currentTradeAmount = moneyManagement.baseTradeAmount;
        moneyManagement.totalInvested = 0;
    }
    
    // Handle WIN with money management
    function handleMoneyManagementWin(tradeAmount) {
        const payout = moneyManagement.currentPayout / 100;
        const profit = tradeAmount * payout;
        
        // Update balance
        moneyManagement.accountBalance += profit;
        winLossStats.sessionProfit += profit;
        moneyManagement.sessionTrades++;
        
        // Reset smart martingale on win
        resetSmartMartingale();
        
        // Recalculate base amount with new balance
        calculateBaseTradeAmount();
        
        log(`✅ WIN +$${profit.toFixed(2)} | Balance: $${moneyManagement.accountBalance.toFixed(2)}`);
        
        updateMoneyManagementDisplay();
        checkSessionLimits();
    }
    
    // Handle LOSS with money management
    function handleMoneyManagementLoss(tradeAmount) {
        // Update balance
        moneyManagement.accountBalance -= tradeAmount;
        winLossStats.sessionProfit -= tradeAmount;
        moneyManagement.sessionTrades++;
        
        if (smartMartingale.enabled) {
            // Add to total loss to recover
            smartMartingale.totalLoss += tradeAmount;
            smartMartingale.step++;
            moneyManagement.totalInvested += tradeAmount;
            
            if (smartMartingale.step < smartMartingale.maxSteps) {
                // Calculate next trade to recover all losses + profit
                const payout = moneyManagement.currentPayout;
                const nextAmount = calculateSmartMartingale(
                    smartMartingale.totalLoss, 
                    smartMartingale.targetProfit,
                    payout
                );
                
                moneyManagement.currentTradeAmount = nextAmount;
                smartMartingale.sequence.push(nextAmount);
                
                log(`❌ LOSS -$${tradeAmount.toFixed(2)} | Next: $${nextAmount.toFixed(2)} to recover $${smartMartingale.totalLoss.toFixed(2)} + $${smartMartingale.targetProfit} profit`);
            } else {
                log(`🛑 MAX MARTINGALE STEPS (${smartMartingale.maxSteps}) - Total loss: $${smartMartingale.totalLoss.toFixed(2)}`);
                playStopSound();
                resetSmartMartingale();
            }
        } else {
            log(`❌ LOSS -$${tradeAmount.toFixed(2)} | Balance: $${moneyManagement.accountBalance.toFixed(2)}`);
        }
        
        updateMoneyManagementDisplay();
        checkSessionLimits();
    }
    
    // Update money management display
    function updateMoneyManagementDisplay() {
        // Balance
        const balanceEl = document.getElementById('gpt-mm-balance');
        if (balanceEl) balanceEl.textContent = `$${moneyManagement.accountBalance.toFixed(2)}`;
        
        // Current trade amount
        const tradeAmtEl = document.getElementById('gpt-mm-trade-amount');
        if (tradeAmtEl) tradeAmtEl.textContent = `$${moneyManagement.currentTradeAmount.toFixed(2)}`;
        
        // Payout
        const payoutEl = document.getElementById('gpt-mm-payout');
        if (payoutEl) payoutEl.textContent = `${moneyManagement.currentPayout}%`;
        
        // Session P/L
        const plEl = document.getElementById('gpt-mm-session-pl');
        if (plEl) {
            const pl = winLossStats.sessionProfit;
            plEl.textContent = `${pl >= 0 ? '+' : ''}$${pl.toFixed(2)}`;
            plEl.style.color = pl >= 0 ? '#22c55e' : '#ef4444';
        }
        
        // Smart martingale info
        const martEl = document.getElementById('gpt-mm-martingale');
        if (martEl && smartMartingale.enabled) {
            if (smartMartingale.step > 0) {
                martEl.textContent = `Step ${smartMartingale.step}/${smartMartingale.maxSteps} | Recover: $${smartMartingale.totalLoss.toFixed(2)}`;
                martEl.style.color = '#f59e0b';
            } else {
                martEl.textContent = 'Ready';
                martEl.style.color = '#22c55e';
            }
        }
    }
    
    // Update session display
    function updateSessionDisplay() {
        const sessionEl = document.getElementById('gpt-mm-session');
        if (sessionEl) {
            if (moneyManagement.sessionActive) {
                sessionEl.textContent = `${moneyManagement.sessionTrades}/${moneyManagement.sessionTarget}`;
                sessionEl.style.color = '#22c55e';
            } else {
                sessionEl.textContent = 'Not active';
                sessionEl.style.color = '#9ca3af';
            }
        }
    }

    // ===========================================
    // TRADE RESULT MONITOR (Manual Mode) - v6.7.0
    // ===========================================
    // Since we now use manual WIN/LOSS buttons, this just logs the trade
    function startTradeResultMonitor(direction, tradeAmount, expirySeconds) {
        // Log the pending trade for manual result entry
        log(`📊 Trade placed: ${direction} $${tradeAmount} - Press WIN or LOSS when closed`);
        
        // Store pending trade info for reference
        window.lastPendingTrade = {
            direction: direction,
            amount: tradeAmount,
            expiry: expirySeconds,
            timestamp: Date.now()
        };
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
        // Pocket Option favorites bar detection - v6.8.5
        // The favorites bar contains asset buttons like "EUR/USD OTC"
        
        const favorites = [];
        
        console.log('[GPT] Detecting favorites bar...');
        
        // Method 1: Look for the assets container/tabs at the top
        // Pocket Option typically uses classes like 'assets-list', 'pair-row', 'asset', etc.
        const selectors = [
            '.assets-list .asset',
            '.pair-row',
            '.assets-tab',
            '.favorites-bar .item',
            '[class*="asset-item"]',
            '[class*="pair-item"]',
            '[class*="currency-pair"]',
            '.trading-pair',
            '[data-testid*="asset"]',
            '.assets-bar button',
            '.assets-bar span',
            // Generic fallback selectors
            'header button',
            'nav button',
            '.top-bar span',
            '.top-bar button'
        ];
        
        for (const selector of selectors) {
            try {
                const elements = document.querySelectorAll(selector);
                for (const el of elements) {
                    if (!el || !el.offsetParent) continue;
                    
                    const text = (el.textContent || el.innerText || '').trim().toUpperCase();
                    
                    // Check if it looks like a currency pair
                    if (text.match(/[A-Z]{3}[\/\s]?[A-Z]{3}/)) {
                        favorites.push({
                            element: el,
                            symbol: text,
                            normalized: normalizeAsset(text),
                            selector: selector
                        });
                    }
                }
            } catch (e) {
                console.log(`[GPT] Selector ${selector} failed:`, e);
            }
        }
        
        // Method 2: Find ANY clickable elements with currency text in the top 200px
        if (favorites.length === 0) {
            console.log('[GPT] Method 1 failed, trying broad search...');
            
            const allElements = document.querySelectorAll('*');
            for (const el of allElements) {
                if (!el || !el.offsetParent) continue;
                
                const rect = el.getBoundingClientRect();
                // Must be in top portion of screen
                if (rect.top > 200 || rect.bottom < 0) continue;
                // Must be reasonable size for a button
                if (rect.width < 40 || rect.width > 250) continue;
                if (rect.height < 15 || rect.height > 80) continue;
                
                const text = (el.textContent || '').trim().toUpperCase();
                
                // Match currency pair patterns
                if (text.match(/^[A-Z]{3}[\/\s\-]?[A-Z]{3}[\s]*(OTC)?$/i) ||
                    text.match(/EUR|USD|GBP|JPY|AUD|CAD|CHF/) && text.length >= 6 && text.length <= 15) {
                    
                    // Check if clickable
                    const style = window.getComputedStyle(el);
                    const isClickable = style.cursor === 'pointer' || 
                                       el.onclick !== null || 
                                       el.tagName === 'BUTTON' ||
                                       el.tagName === 'A' ||
                                       el.getAttribute('role') === 'button';
                    
                    if (isClickable || el.closest('button') || el.closest('a')) {
                        favorites.push({
                            element: el.closest('button') || el.closest('a') || el,
                            symbol: text,
                            normalized: normalizeAsset(text),
                            selector: 'broad-search'
                        });
                    }
                }
            }
        }
        
        // Remove duplicates
        const uniqueFavorites = [];
        const seen = new Set();
        
        for (const fav of favorites) {
            const key = fav.normalized.substring(0, 6);
            if (!seen.has(key)) {
                seen.add(key);
                uniqueFavorites.push(fav);
            }
        }
        
        favoritesFromBar = uniqueFavorites;
        
        if (uniqueFavorites.length > 0) {
            log(`📊 Found ${uniqueFavorites.length} favorites: ${uniqueFavorites.map(f => f.symbol).slice(0, 5).join(', ')}`);
            console.log('[GPT] Favorites:', uniqueFavorites.map(f => ({ symbol: f.symbol, selector: f.selector })));
        } else {
            log('⚠️ No favorites detected in bar');
            console.log('[GPT] No favorites found - check if you have assets in favorites bar');
        }
        
        return uniqueFavorites;
    }

    // Click an asset in the favorites bar - v7.0.0
    async function clickFavoriteAsset(favorite) {
        if (!favorite || !favorite.element) {
            log('❌ Invalid favorite object');
            return false;
        }
        
        try {
            let el = favorite.element;
            const targetBase = favorite.normalized.substring(0, 6);
            const initialAsset = getCurrentAsset();
            
            log(`🔄 SWITCH: ${favorite.symbol} (from ${initialAsset})`);
            
            // Re-find the element if it's stale
            if (!document.body.contains(el)) {
                log('⚠️ Element stale, re-detecting...');
                detectFavoritesBar();
                
                const newFav = favoritesFromBar.find(f => f.normalized.substring(0, 6) === targetBase);
                if (!newFav) {
                    log('❌ Could not re-find favorite');
                    return false;
                }
                el = newFav.element;
            }
            
            // Method 1: Direct click
            log('🔄 Method 1: Direct click');
            el.click();
            await sleep(600);
            
            let newAsset = getCurrentAsset();
            if (newAsset && normalizeAsset(newAsset).substring(0, 6) === targetBase) {
                log(`✅ SWITCHED to ${newAsset}`);
                return true;
            }
            
            // Method 2: Full mouse event simulation
            log('🔄 Method 2: Mouse simulation');
            const rect = el.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            
            // Hover first
            el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
            el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
            await sleep(100);
            
            // Full click sequence
            for (const eventType of ['mousedown', 'mouseup', 'click']) {
                el.dispatchEvent(new MouseEvent(eventType, {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: centerX,
                    clientY: centerY
                }));
            }
            await sleep(600);
            
            newAsset = getCurrentAsset();
            if (newAsset && normalizeAsset(newAsset).substring(0, 6) === targetBase) {
                log(`✅ SWITCHED to ${newAsset}`);
                return true;
            }
            
            // Method 3: Click parents (up to 3 levels)
            log('🔄 Method 3: Parent clicks');
            let parent = el.parentElement;
            for (let i = 0; i < 3 && parent && parent.tagName !== 'BODY'; i++) {
                parent.click();
                await sleep(400);
                newAsset = getCurrentAsset();
                if (newAsset && normalizeAsset(newAsset).substring(0, 6) === targetBase) {
                    log(`✅ SWITCHED to ${newAsset} (parent ${i})`);
                    return true;
                }
                parent = parent.parentElement;
            }
            
            // Method 4: Find element at coordinates and click
            log('🔄 Method 4: Coordinate click');
            const clickTarget = document.elementFromPoint(centerX, centerY);
            if (clickTarget) {
                clickTarget.click();
                await sleep(400);
                newAsset = getCurrentAsset();
                if (newAsset && normalizeAsset(newAsset).substring(0, 6) === targetBase) {
                    log(`✅ SWITCHED to ${newAsset} (coordinate)`);
                    return true;
                }
            }
            
            // Method 5: Focus and enter key
            log('🔄 Method 5: Focus + Enter');
            el.focus();
            el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
            el.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', bubbles: true }));
            await sleep(400);
            
            newAsset = getCurrentAsset();
            if (newAsset && normalizeAsset(newAsset).substring(0, 6) === targetBase) {
                log(`✅ SWITCHED to ${newAsset} (Enter key)`);
                return true;
            }
            
            log(`❌ ALL METHODS FAILED. Current: ${newAsset}, Target: ${favorite.symbol}`);
            return false;
            
        } catch (e) {
            log(`❌ Click error: ${e.message}`);
            console.error('[GPT] Click error:', e);
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
    // HEARTBEAT & SETTINGS SYNC - v6.9.0
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
                invert_enabled: invertEnabled,
                trade_count: tradeCount,
                version: '6.9.0'
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

    // ===========================================
    // PRICE VERIFICATION - v6.9.4
    // Get current price from Pocket Option UI
    // ===========================================
    function getCurrentPrice() {
        // Try multiple selectors to find the current price display
        const priceSelectors = [
            '.current-price',
            '.price-value',
            '[data-testid="current-price"]',
            '.chart-price',
            '.bid-price',
            '.ask-price',
            '[class*="price"]',
            '[class*="quote"]'
        ];
        
        for (const sel of priceSelectors) {
            const els = document.querySelectorAll(sel);
            for (const el of els) {
                if (!el || !el.offsetParent) continue;
                
                const text = el.textContent?.trim() || '';
                // Look for price patterns like "1.08234" or "108.234"
                const priceMatch = text.match(/(\d+\.\d{3,5})/);
                if (priceMatch) {
                    const price = parseFloat(priceMatch[1]);
                    // Validate it looks like a forex price
                    if (price > 0.1 && price < 200) {
                        return price;
                    }
                }
            }
        }
        
        // Try to find price in chart overlay or tooltip
        const chartArea = document.querySelector('[class*="chart"]');
        if (chartArea) {
            const priceElements = chartArea.querySelectorAll('text, span, div');
            for (const el of priceElements) {
                const text = el.textContent?.trim() || '';
                const priceMatch = text.match(/^(\d+\.\d{3,5})$/);
                if (priceMatch) {
                    const price = parseFloat(priceMatch[1]);
                    if (price > 0.1 && price < 200) {
                        return price;
                    }
                }
            }
        }
        
        return null;
    }
    
    // Verify signal price matches current market (within tolerance)
    function verifySignalPrice(signalPrice, tolerance = 0.001) {
        const currentPrice = getCurrentPrice();
        
        if (!currentPrice || !signalPrice) {
            log('⚠️ Price verification skipped (no price available)');
            return { valid: true, reason: 'no_price_data' };
        }
        
        const priceDiff = Math.abs(currentPrice - signalPrice);
        const percentDiff = (priceDiff / currentPrice) * 100;
        
        if (percentDiff > (tolerance * 100)) {
            log(`⚠️ Price mismatch: Signal=${signalPrice}, Current=${currentPrice} (${percentDiff.toFixed(3)}% diff)`);
            return { 
                valid: false, 
                reason: 'price_mismatch',
                signalPrice,
                currentPrice,
                diff: percentDiff
            };
        }
        
        log(`✓ Price verified: ${currentPrice} (${percentDiff.toFixed(3)}% diff)`);
        return { valid: true, currentPrice, diff: percentDiff };
    }

    function findTradeButtons() {
        // Use STRICT selectors only - avoid wildcards that match both buttons
        const callBtn = document.querySelector('.btn-call') || 
                       document.querySelector('button.call') ||
                       document.querySelector('[data-testid="call-button"]');
        const putBtn = document.querySelector('.btn-put') || 
                      document.querySelector('button.put') ||
                      document.querySelector('[data-testid="put-button"]');
        
        // Both buttons must exist and be visible
        return callBtn && putBtn && 
               callBtn.offsetParent !== null && 
               putBtn.offsetParent !== null;
    }

    // ===========================================
    // UI PANEL
    // ===========================================
    let isMinimized = false;
    
    function createPanel() {
        const existing = document.getElementById('gpt-panel');
        if (existing) existing.remove();

        isMinimized = GM_getValue('isMinimized', false);

        const panel = document.createElement('div');
        panel.id = 'gpt-panel';
        panel.innerHTML = `
            <style>
                #gpt-panel {
                    position: fixed;
                    top: auto;
                    bottom: 10px;
                    left: 10px;
                    right: auto;
                    background: rgba(20, 20, 35, 0.95);
                    border: 1px solid #7c3aed;
                    border-radius: 6px;
                    padding: 4px 8px;
                    z-index: 999999;
                    font-family: Arial, sans-serif;
                    font-size: 10px;
                    color: white;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    flex-wrap: wrap;
                    max-width: 520px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.5);
                    cursor: default;
                }
                #gpt-panel.minimized { max-width: 120px; }
                #gpt-panel.minimized .expandable { display: none; }
                
                #gpt-panel button {
                    padding: 3px 6px;
                    border: none;
                    border-radius: 3px;
                    font-size: 9px;
                    font-weight: bold;
                    cursor: pointer;
                    text-transform: uppercase;
                }
                #gpt-panel button:hover { opacity: 0.8; }
                
                #gpt-panel .title { 
                    color: #a78bfa; 
                    font-weight: bold; 
                    font-size: 10px; 
                    cursor: move;
                    padding: 2px 4px;
                    user-select: none;
                }
                #gpt-panel .title:hover { background: rgba(124,58,237,0.3); border-radius: 3px; }
                
                #gpt-panel .dot { width: 6px; height: 6px; border-radius: 50%; background: #ef4444; }
                #gpt-panel .dot.on { background: #22c55e; }
                #gpt-panel .dot.trading { background: #f59e0b; animation: pulse 0.5s infinite; }
                @keyframes pulse { 50% { opacity: 0.4; } }
                
                #gpt-panel .sig { padding: 2px 8px; border-radius: 3px; font-weight: bold; }
                #gpt-panel .sig.call { background: #22c55e; }
                #gpt-panel .sig.put { background: #ef4444; }
                #gpt-panel .sig.wait { background: #4b5563; }
                
                #gpt-panel .on { background: #22c55e !important; }
                #gpt-panel .off { background: #4b5563; }
                #gpt-panel .auto-btn { background: #4b5563; color: white; }
                #gpt-panel .scan-btn { background: #4b5563; color: white; }
                #gpt-panel .switch-btn { background: #4b5563; color: white; }
                #gpt-panel .switch-btn.disabled { opacity: 0.4; }
                #gpt-panel .inv-btn { background: #4b5563; color: white; }
                #gpt-panel .fetch-btn { background: #3b82f6; color: white; }
                #gpt-panel .win-btn { background: #22c55e; color: white; }
                #gpt-panel .loss-btn { background: #ef4444; color: white; }
                #gpt-panel .min-btn { background: #6b7280; color: white; width: 18px; }
                
                #gpt-panel .stat { color: #9ca3af; }
                #gpt-panel .val { font-weight: bold; }
                #gpt-panel .win { color: #22c55e; }
                #gpt-panel .loss { color: #ef4444; }
                
                #gpt-panel input {
                    background: rgba(0,0,0,0.4);
                    border: 1px solid #4b5563;
                    border-radius: 2px;
                    color: white;
                    width: 35px;
                    font-size: 9px;
                    padding: 2px;
                    text-align: center;
                }
                
                #gpt-panel .log {
                    color: #22c55e;
                    font-size: 8px;
                    max-width: 150px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                
                #gpt-panel .console-btn { background: #6366f1; color: white; }
                
                /* Console Window */
                #gpt-console-window {
                    position: fixed;
                    bottom: 50px;
                    left: 10px;
                    width: 400px;
                    height: 250px;
                    background: rgba(15, 15, 25, 0.98);
                    border: 1px solid #7c3aed;
                    border-radius: 8px;
                    z-index: 999998;
                    display: none;
                    font-family: 'Consolas', 'Monaco', monospace;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.6);
                }
                #gpt-console-header {
                    background: linear-gradient(90deg, #7c3aed, #6366f1);
                    padding: 6px 10px;
                    border-radius: 7px 7px 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    cursor: move;
                }
                #gpt-console-header span { font-weight: bold; color: white; font-size: 11px; }
                #gpt-console-header button { 
                    background: rgba(255,255,255,0.2); 
                    border: none; 
                    color: white; 
                    padding: 2px 8px; 
                    border-radius: 3px;
                    cursor: pointer;
                }
                #gpt-console-content {
                    padding: 8px;
                    height: calc(100% - 40px);
                    overflow-y: auto;
                    font-size: 10px;
                    line-height: 1.4;
                }
                #gpt-console-content::-webkit-scrollbar { width: 6px; }
                #gpt-console-content::-webkit-scrollbar-thumb { background: #7c3aed; border-radius: 3px; }
            </style>
            
            <span class="dot" id="gpt-dot"></span>
            <span class="title" id="gpt-drag">GPT</span>
            <span class="sig wait" id="gpt-signal">-</span>
            
            <span class="expandable">
                <button class="auto-btn" id="gpt-auto">AUTO</button>
                <button class="scan-btn" id="gpt-scan">SCAN</button>
                <button class="inv-btn" id="gpt-invert">INV</button>
                <button class="fetch-btn" id="gpt-fetch">GO</button>
                <button class="console-btn" id="gpt-console-toggle">LOG</button>
            </span>
            
            <span class="expandable">
                <button class="win-btn" id="gpt-win-btn">W</button>
                <button class="loss-btn" id="gpt-loss-btn">L</button>
            </span>
            
            <span class="expandable stat">
                <span class="val win" id="gpt-wins">0</span>/<span class="val loss" id="gpt-losses">0</span>
                <span class="val" id="gpt-profit">$0</span>
            </span>
            
            <span class="expandable">
                $<input type="number" id="gpt-mm-balance-input" value="100">
                <input type="number" id="gpt-mm-risk" value="2" style="width:25px;">%
            </span>
            
            <span class="log expandable" id="gpt-log">Ready</span>
            <button class="min-btn" id="gpt-minimize">−</button>
        `;

        document.body.appendChild(panel);
        
        // Create Console Window
        const consoleWindow = document.createElement('div');
        consoleWindow.id = 'gpt-console-window';
        consoleWindow.innerHTML = `
            <div id="gpt-console-header">
                <span>GPT Signal Bot Console v7.0</span>
                <button id="gpt-console-close">✕</button>
            </div>
            <div id="gpt-console-content"></div>
        `;
        document.body.appendChild(consoleWindow);

        // Apply minimized state
        if (isMinimized) {
            panel.classList.add('minimized');
            document.getElementById('gpt-minimize').textContent = '+';
        }

        // Button handlers
        document.getElementById('gpt-auto').addEventListener('click', toggleAuto);
        document.getElementById('gpt-scan').addEventListener('click', toggleScan);
        document.getElementById('gpt-invert').addEventListener('click', toggleInvert);
        document.getElementById('gpt-fetch').addEventListener('click', handleFetch);
        document.getElementById('gpt-minimize').addEventListener('click', toggleMinimize);
        document.getElementById('gpt-console-toggle').addEventListener('click', toggleConsoleWindow);
        document.getElementById('gpt-console-close').addEventListener('click', toggleConsoleWindow);
        
        // Win/Loss handlers
        document.getElementById('gpt-win-btn').addEventListener('click', handleManualWin);
        document.getElementById('gpt-loss-btn').addEventListener('click', handleManualLoss);
        
        // Money Management
        document.getElementById('gpt-mm-balance-input').addEventListener('change', (e) => {
            moneyManagement.accountBalance = parseFloat(e.target.value) || 100;
            moneyManagement.sessionStartBalance = moneyManagement.accountBalance;
            calculateBaseTradeAmount();
            GM_setValue('mmAccountBalance', moneyManagement.accountBalance);
            updateMoneyManagementDisplay();
            log(`Bal: $${moneyManagement.accountBalance}`);
        });
        document.getElementById('gpt-mm-risk').addEventListener('change', (e) => {
            moneyManagement.riskPercentage = parseFloat(e.target.value) || 2;
            calculateBaseTradeAmount();
            GM_setValue('mmRiskPercentage', moneyManagement.riskPercentage);
            updateMoneyManagementDisplay();
            log(`Risk: ${moneyManagement.riskPercentage}%`);
        });

        // Make draggable
        makeDraggable(panel, document.getElementById('gpt-drag'));
        
        // Apply saved position (convert bottom to top if needed)
        const savedPos = GM_getValue('panelPosition', null);
        if (savedPos && savedPos.top && savedPos.left) {
            panel.style.top = savedPos.top;
            panel.style.left = savedPos.left;
            panel.style.bottom = 'auto';
            panel.style.right = 'auto';
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
            // Don't drag if clicking minimize button or other buttons
            if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') return;
            
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            
            // Get computed position (handles bottom positioning)
            const rect = panel.getBoundingClientRect();
            startLeft = rect.left;
            startTop = rect.top;
            
            // Convert to top/left positioning
            panel.style.bottom = 'auto';
            panel.style.right = 'auto';
            panel.style.top = startTop + 'px';
            panel.style.left = startLeft + 'px';
            
            e.preventDefault();
        }

        function startDragTouch(e) {
            if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') return;
            
            isDragging = true;
            const touch = e.touches[0];
            startX = touch.clientX;
            startY = touch.clientY;
            
            // Get computed position
            const rect = panel.getBoundingClientRect();
            startLeft = rect.left;
            startTop = rect.top;
            
            // Convert to top/left positioning
            panel.style.bottom = 'auto';
            panel.style.right = 'auto';
            panel.style.top = startTop + 'px';
            panel.style.left = startLeft + 'px';
            
            e.preventDefault();
        }

        function drag(e) {
            if (!isDragging) return;
            
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            
            panel.style.left = (startLeft + dx) + 'px';
            panel.style.top = (startTop + dy) + 'px';
            panel.style.right = 'auto';
            panel.style.bottom = 'auto';
        }

        function dragTouch(e) {
            if (!isDragging) return;
            
            const touch = e.touches[0];
            const dx = touch.clientX - startX;
            const dy = touch.clientY - startY;
            
            panel.style.left = (startLeft + dx) + 'px';
            panel.style.top = (startTop + dy) + 'px';
            panel.style.right = 'auto';
            panel.style.bottom = 'auto';
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
    // BUTTON HANDLERS - v6.9.0 SIMPLIFIED
    // ===========================================
    
    /*
    v6.9.0 BUTTON LOGIC:
    - AUTO: Receives APP signals and places trades
    - SCAN: Scans for signals and places trades
      * If AUTO ON: SCAN only checks current asset (no switching)
      * If AUTO OFF: SCAN checks ALL favorites and auto-switches to best signal
    - INVERT: Local toggle for direction inversion
    - FETCH: Force scan generation
    - SWITCH REMOVED: Switching is now automatic when AUTO is OFF
    */
    
    function toggleAuto() {
        autoEnabled = !autoEnabled;
        GM_setValue('autoEnabled', autoEnabled);
        
        updateAllUI();
        manageIntervals();
        
        if (autoEnabled) {
            log(`AUTO: ON - App signals + SCAN on current asset only`);
        } else {
            log(`AUTO: OFF - SCAN will check ALL favorites and auto-switch`);
        }
    }

    function toggleScan() {
        scanEnabled = !scanEnabled;
        GM_setValue('scanEnabled', scanEnabled);
        updateAllUI();
        manageIntervals();
        
        if (scanEnabled) {
            if (autoEnabled) {
                log(`SCAN: ON - Scanning CURRENT asset only (AUTO mode)`);
            } else {
                log(`SCAN: ON - Scanning ALL favorites (will auto-switch)`);
            }
        } else {
            log(`SCAN: OFF`);
        }
    }

    function toggleInvert() {
        invertEnabled = !invertEnabled;
        GM_setValue('invertEnabled', invertEnabled);
        updateAllUI();
        log(`INVERT: ${invertEnabled ? 'ON' : 'OFF'}`);
    }

    function handleFetch() {
        // GO button forces signal generation for CURRENT ASSET only
        log('🔄 GO: Force scan current asset...');
        doScan(true, true);  // force=true, currentAssetOnly=true
    }

    function resetToDefaults() {
        autoEnabled = false;
        scanEnabled = false;
        invertEnabled = false;
        lastAppSignalId = '';
        lastAppTradeTime = 0;
        lastScanTradeTime = 0;
        manualInvertActive = false;
        
        GM_setValue('autoEnabled', false);
        GM_setValue('scanEnabled', false);
        GM_setValue('invertEnabled', false);
        
        updateAllUI();
        manageIntervals();
        updateSignalDisplay('READY', null, 'wait', '-');
        
        log('RESET: All buttons OFF');
    }

    // ===========================================
    // MARTINGALE & SOUND TOGGLE HANDLERS - v6.7.0
    // ===========================================
    function toggleMartingale() {
        martingaleEnabled = !martingaleEnabled;
        GM_setValue('martingaleEnabled', martingaleEnabled);
        
        const btn = document.getElementById('gpt-martingale-toggle');
        if (btn) {
            btn.textContent = martingaleEnabled ? 'ON' : 'OFF';
            btn.style.background = martingaleEnabled ? '#22c55e' : '#6b7280';
        }
        
        updateMartingaleDisplay();
        log(`MARTINGALE: ${martingaleEnabled ? 'ON' : 'OFF'}`);
    }
    
    // Toggle Smart Martingale (money management system) - v6.8.0
    function toggleSmartMartingale() {
        smartMartingale.enabled = !smartMartingale.enabled;
        GM_setValue('smartMartingaleEnabled', smartMartingale.enabled);
        
        const btn = document.getElementById('gpt-mm-toggle');
        if (btn) {
            btn.textContent = smartMartingale.enabled ? 'ON' : 'OFF';
            btn.style.background = smartMartingale.enabled ? '#22c55e' : '#6b7280';
        }
        
        if (smartMartingale.enabled) {
            // Initialize money management
            calculateBaseTradeAmount();
            detectCurrentPayout();
            
            // Disable legacy martingale when smart is enabled
            martingaleEnabled = false;
            GM_setValue('martingaleEnabled', false);
            const legacyBtn = document.getElementById('gpt-martingale-toggle');
            if (legacyBtn) {
                legacyBtn.textContent = 'OFF';
                legacyBtn.style.background = '#6b7280';
            }
        }
        
        updateMoneyManagementDisplay();
        updateMartingaleDisplay();
        log(`SMART MONEY MANAGEMENT: ${smartMartingale.enabled ? 'ON' : 'OFF'}`);
    }

    function toggleSoundNotifications() {
        soundNotificationsEnabled = !soundNotificationsEnabled;
        GM_setValue('soundNotificationsEnabled', soundNotificationsEnabled);
        
        const btn = document.getElementById('gpt-sound-toggle');
        if (btn) {
            btn.textContent = soundNotificationsEnabled ? '🔊 SOUND ON' : '🔇 SOUND OFF';
            btn.style.background = soundNotificationsEnabled ? '#8b5cf6' : '#6b7280';
        }
        
        log(`SOUND: ${soundNotificationsEnabled ? 'ON' : 'OFF'}`);
    }
    
    // Update invert button UI
    function updateInvertButton() {
        const btn = document.getElementById('gpt-invert');
        if (btn) {
            if (manualInvertActive) {
                btn.textContent = 'INVERT ON (LOSS)';
                btn.classList.add('on');
            } else {
                btn.textContent = invertEnabled ? 'INVERT ON' : 'INVERT OFF';
                btn.classList.toggle('on', invertEnabled);
            }
        }
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
        const invertBtn = document.getElementById('gpt-invert');

        if (autoBtn) {
            autoBtn.textContent = autoEnabled ? 'AUTO✓' : 'AUTO';
            autoBtn.className = 'auto-btn' + (autoEnabled ? ' on' : '');
        }
        if (scanBtn) {
            scanBtn.textContent = scanEnabled ? 'SCAN✓' : 'SCAN';
            scanBtn.className = 'scan-btn' + (scanEnabled ? ' on' : '');
        }
        if (invertBtn) {
            invertBtn.textContent = invertEnabled ? 'INV✓' : 'INV';
            invertBtn.className = 'inv-btn' + (invertEnabled ? ' on' : '');
        }
    }

    function updateModeIndicator() {
        // Mode indicator removed in compact UI - status shown via button states
    }

    function updateSignalDisplay(direction, asset, type, source) {
        const sigEl = document.getElementById('gpt-signal');
        
        if (sigEl) {
            sigEl.textContent = direction || '-';
            sigEl.className = 'sig ' + (type || 'wait');
        }
    }

    function updateStatusDot(status) {
        const dot = document.getElementById('gpt-dot');
        if (dot) {
            dot.className = 'dot';
            if (status === 'connected') dot.classList.add('on');
            if (status === 'trading') dot.classList.add('trading');
        }
    }

    function incrementTradeCount() {
        tradeCount++;
        // No trades counter in compact UI
    }

    // ===========================================
    // INTERVAL MANAGEMENT - v7.1.0
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

        // AUTO ON: Poll for APP signals
        if (autoEnabled) {
            log('📡 Starting app signal polling...');
            appPollingInterval = setInterval(() => checkAppSignals(false), CONFIG.APP_POLL_INTERVAL);
            checkAppSignals(false);
        }

        // v7.1.0: Start price scraping for local signal generation
        if (scanEnabled && CONFIG.USE_LOCAL_SIGNALS) {
            startPriceScraping();
            log('🔍 LOCAL SCAN: Using actual OTC prices');
        } else {
            stopPriceScraping();
        }

        // SCAN: Generate signals locally or via backend
        if (scanEnabled) {
            const scanMode = CONFIG.USE_LOCAL_SIGNALS ? 'LOCAL OTC' : 'BACKEND OANDA';
            log(`🔍 Starting scan (${scanMode})`);
            scanInterval = setInterval(() => doScan(false), CONFIG.SCAN_INTERVAL);
            doScan(false);
        }

        updateStatusDot(autoEnabled || scanEnabled ? 'connected' : '');
        updateModeIndicator();
    }

    // ===========================================
    // APP SIGNAL HANDLING (AUTO button) - v6.8.2
    // ===========================================
    function checkAppSignals(force = false) {
        // Only check if AUTO is enabled
        if (!autoEnabled) return;
        
        // Use globalTradeLock instead of isTrading
        if (globalTradeLock && !force) return;

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

                        log(`📡 APP: ${signal.direction} ${signal.symbol}`);
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
        // Use globalTradeLock - no separate isTrading flag needed
        if (globalTradeLock) {
            log('⏳ Trade in progress');
            return;
        }

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
                // Flag removed - using globalTradeLock
                updateStatusDot('connected');
                return;
            }
        }

        // Click button - v6.8.1 pass source for logging
        const clicked = clickTradeButton(isCall, 'APP');
        
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

        // Just update status after trade attempt
        setTimeout(() => {
            updateStatusDot('connected');
        }, 2000);
    }

    // ===========================================
    // SCAN HANDLING - v7.1.0 LOCAL SIGNAL GENERATION
    // Uses actual Pocket Option OTC prices
    // ===========================================
    let priceScrapingInterval = null;
    
    function startPriceScraping() {
        if (priceScrapingInterval) return;
        
        log('📊 Starting OTC price scraping...');
        
        // Scrape price every 500ms to build candle data
        priceScrapingInterval = setInterval(() => {
            const price = PriceScraperV2.scrapeCurrentPrice();
            if (price) {
                const candle = PriceScraperV2.buildCandle(price, 1000);
                if (candle) {
                    PriceScraperV2.addCandle(candle);
                }
            }
        }, 500);
    }
    
    function stopPriceScraping() {
        if (priceScrapingInterval) {
            clearInterval(priceScrapingInterval);
            priceScrapingInterval = null;
        }
    }
    
    function doScan(force = false, currentAssetOnly = false) {
        log(`doScan: force=${force}, currentOnly=${currentAssetOnly}, local=${CONFIG.USE_LOCAL_SIGNALS}`);
        
        // Allow scan if forced (GO button) or if SCAN is enabled
        if (!scanEnabled && !force) {
            log('doScan: Skipped (SCAN not enabled)');
            return;
        }
        
        // Check trade lock (skip if forced)
        if (globalTradeLock && !force) {
            log('doScan: Skipped (trade lock)');
            return;
        }

        // Check cooldown (skip if forced)
        const now = Date.now();
        if (!force && (now - lastScanTradeTime) < CONFIG.TRADE_COOLDOWN_SCAN) {
            log('doScan: Skipped (cooldown)');
            return;
        }

        // Determine switching behavior
        let willSwitchAssets = !autoEnabled && !currentAssetOnly;
        
        if (CONFIG.USE_LOCAL_SIGNALS) {
            // v7.1.0: Use LOCAL signal generation with scraped OTC prices
            doLocalScan(force, currentAssetOnly, willSwitchAssets);
        } else {
            // Fallback: Use backend API (OANDA data)
            doBackendScan(force, currentAssetOnly, willSwitchAssets);
        }
    }
    
    // v7.1.0: Local signal generation using actual OTC prices
    function doLocalScan(force, currentAssetOnly, willSwitchAssets) {
        updateStatusDot('trading');
        
        const currentAsset = getCurrentAsset() || 'Unknown';
        log(`🔍 LOCAL SCAN: ${currentAsset} (OTC prices)`);
        
        // Scrape current price
        const currentPrice = PriceScraperV2.scrapeCurrentPrice();
        if (!currentPrice) {
            log('⚠️ Cannot scrape price - trying backup method');
            // Try getting price from any visible element
            const priceEl = document.querySelector('[class*="price"], [class*="value"], [class*="quote"]');
            if (priceEl) {
                log(`Found price element: ${priceEl.textContent}`);
            }
        } else {
            log(`💰 Current price: ${currentPrice}`);
        }
        
        // Build candle from current price
        if (currentPrice) {
            const candle = PriceScraperV2.buildCandle(currentPrice, 1000);
            if (candle) {
                PriceScraperV2.addCandle(candle);
            }
        }
        
        // Get candle history
        const candles = PriceScraperV2.getCandles();
        log(`📊 Candles available: ${candles.length}`);
        
        if (candles.length < 10) {
            log(`⏳ Need more data (${candles.length}/10 candles). Waiting...`);
            updateStatusDot('connected');
            return;
        }
        
        // Generate signal using local engine
        const signal = LocalSignalEngine.generateSignal(candles);
        
        if (signal) {
            log(`✅ LOCAL SIGNAL: ${signal.direction} (${signal.confidence}%)`);
            log(`📊 Confirmations: ${signal.confirmations.join(', ')}`);
            log(`📈 RSI2=${signal.indicators.rsi2.toFixed(1)}, Stoch=${signal.indicators.stoch.toFixed(1)}`);
            
            // Check minimum confidence
            if (signal.confidence < CONFIG.MIN_CONFIDENCE) {
                log(`⚠️ Confidence too low: ${signal.confidence}% < ${CONFIG.MIN_CONFIDENCE}%`);
                updateStatusDot('connected');
                return;
            }
            
            // Build signal object for execution
            const tradeSignal = {
                direction: signal.direction,
                symbol: currentAsset.replace(/\s+/g, '').replace('/', '').toUpperCase(),
                confidence: signal.confidence,
                confirmations: signal.confirmations,
                price: signal.price,
                source: 'LOCAL_OTC',
                _willSwitch: willSwitchAssets
            };
            
            // Execute trade
            executeScanTrade(tradeSignal).catch(err => {
                log(`❌ Trade error: ${err.message}`);
                updateStatusDot('connected');
            });
        } else {
            log('⚠️ No signal (conditions not met)');
            updateStatusDot('connected');
        }
    }
    
    // Fallback: Backend API scan (uses OANDA data)
    function doBackendScan(force, currentAssetOnly, willSwitchAssets) {
        let assetsToScan = '';
        
        if (currentAssetOnly || autoEnabled) {
            const currentAssetRaw = getCurrentAsset();
            if (!currentAssetRaw) {
                assetsToScan = 'EURUSD_OTC';
            } else {
                assetsToScan = currentAssetRaw
                    .replace(/\s+/g, '')
                    .replace('/', '')
                    .replace('OTC', '_OTC')
                    .toUpperCase();
                if (!assetsToScan.includes('_OTC')) {
                    assetsToScan += '_OTC';
                }
            }
            log(`🔍 BACKEND SCAN: ${assetsToScan}`);
        } else {
            detectFavoritesBar();
            if (favoritesFromBar.length > 0) {
                const assetList = favoritesFromBar.map(f => {
                    let norm = f.normalized;
                    if (!norm.includes('_OTC')) norm += '_OTC';
                    return norm;
                });
                assetsToScan = assetList.join(',');
                log(`🔍 BACKEND SCAN: ${favoritesFromBar.length} favorites`);
            } else {
                assetsToScan = 'EURUSD_OTC,GBPUSD_OTC,USDJPY_OTC,AUDUSD_OTC';
            }
        }

        const apiUrl = CONFIG.API_URL + `/signals/scan-markets?assets=${assetsToScan}&min_confidence=${CONFIG.MIN_CONFIDENCE}`;
        log(`📡 API: ${apiUrl}`);
        updateStatusDot('trading');
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: apiUrl,
            headers: { 'Accept': 'application/json' },
            timeout: 15000,
            onload: function(res) {
                log(`📡 Response: ${res.status}`);
                try {
                    if (res.status !== 200) {
                        log(`❌ API error: ${res.status}`);
                        updateStatusDot('connected');
                        return;
                    }

                    const data = JSON.parse(res.responseText);
                    const signals = data.top_signals || data.signals || [];
                    
                    log(`📊 ${signals.length} signal(s)`);
                    
                    if (data.success && signals.length > 0) {
                        const bestSignal = signals[0];
                        bestSignal._willSwitch = willSwitchAssets;
                        bestSignal.source = 'BACKEND_OANDA';
                        
                        log(`✅ ${bestSignal.direction} ${bestSignal.symbol} (${Math.round(bestSignal.confidence)}%)`);
                        
                        executeScanTrade(bestSignal).catch(err => {
                            log(`❌ Trade error: ${err.message}`);
                            updateStatusDot('connected');
                        });
                    } else {
                        log('⚠️ No signals');
                        updateStatusDot('connected');
                    }
                } catch (e) {
                    log(`❌ Parse error: ${e.message}`);
                    updateStatusDot('connected');
                }
            },
            onerror: function(e) {
                log('❌ Connection error');
                updateStatusDot('connected');
            },
            ontimeout: function() {
                log('❌ Timeout');
                updateStatusDot('connected');
            }
        });
    }

    function normalizeAsset(asset) {
        if (!asset) return '';
        return asset.replace(/[^A-Z0-9]/gi, '').toUpperCase();
    }

    async function executeScanTrade(signal) {
        log(`📥 executeScanTrade: ${signal.direction} ${signal.symbol} (${signal.confidence}%)`);
        console.log('[GPT executeScanTrade] Signal:', JSON.stringify(signal, null, 2));
        
        if (globalTradeLock) {
            log('⏳ BLOCKED: Trade lock active');
            return;
        }

        updateStatusDot('trading');

        // Only switch if signal has _willSwitch flag (set by doScan when scanning multiple assets)
        const shouldSwitch = signal._willSwitch === true;
        log(`📍 shouldSwitch=${shouldSwitch}, _willSwitch=${signal._willSwitch}`);
        
        if (shouldSwitch && signal.symbol) {
            const targetNorm = normalizeAsset(signal.symbol);
            const currentAssetNow = getCurrentAsset();
            const currentNorm = normalizeAsset(currentAssetNow);
            
            const targetBase = targetNorm.substring(0, 6);
            const currentBase = currentNorm.substring(0, 6);
            
            if (targetBase !== currentBase) {
                log(`🔄 Switching to ${signal.symbol}...`);
                let switched = false;
                
                detectFavoritesBar();
                
                const matchingFav = favoritesFromBar.find(f => {
                    const favBase = f.normalized.substring(0, 6);
                    return favBase === targetBase;
                });
                
                if (matchingFav) {
                    switched = await clickFavoriteAsset(matchingFav);
                    if (switched) {
                        log(`✅ Switched to ${matchingFav.symbol}`);
                        await sleep(1000);
                    }
                }
                
                if (!switched) {
                    switched = await switchToAsset(signal.symbol);
                }
                
                if (!switched) {
                    log(`❌ Switch failed - skipping trade`);
                    updateStatusDot('connected');
                    return;
                }
                
                await sleep(500);
            }
        }

        // Determine direction
        let direction = (signal.direction || '').toUpperCase();
        let isCall = direction === 'CALL' || direction === 'BUY' || direction === 'UP';
        
        if (invertEnabled) {
            isCall = !isCall;
            log(`🔄 Inverted → ${isCall ? 'CALL' : 'PUT'}`);
        }

        const finalDirection = isCall ? 'CALL' : 'PUT';
        log(`📊 Placing ${finalDirection}...`);
        updateSignalDisplay(finalDirection, signal.symbol, isCall ? 'call' : 'put', '🔍');

        playScanSignalSound();

        // Find buttons
        if (!findTradeButtons()) {
            await sleep(1000);
            if (!findTradeButtons()) {
                log('❌ Buttons not found');
                updateStatusDot('connected');
                return;
            }
        }

        // Click trade button
        const clicked = clickTradeButton(isCall, 'SCAN');
        
        if (clicked) {
            incrementTradeCount();
            lastScanTradeTime = Date.now();
            log(`✅ TRADE: ${finalDirection} ${signal.symbol}`);
            
            const expirySeconds = signal.expiration_seconds || signal.expiry || signal.expiry_seconds || 60;
            startTradeResultMonitor(finalDirection, signal.amount || 1, expirySeconds);
            
            try {
                GM_notification({
                    title: `Trade: ${finalDirection}`,
                    text: signal.symbol,
                    timeout: 3000
                });
            } catch(e) {}
        } else {
            log(`❌ Click failed`);
        }

        setTimeout(() => updateStatusDot('connected'), 2000);
    }

    // ===========================================
    // TRADE EXECUTION - v6.9.5 FIXED DOUBLE-CLICK
    // ===========================================
    function clickTradeButton(isCall, source = 'unknown') {
        const now = Date.now();
        const direction = isCall ? 'CALL' : 'PUT';
        
        // GUARD 1: Global trade lock (primary protection)
        if (globalTradeLock) {
            log(`🛑 BLOCKED [${source}]: Trade lock active`);
            return false;
        }
        
        // GUARD 2: Time-based lock (5 seconds between ANY trades)
        if (now - lastTradeClickTime < TRADE_LOCK_MS) {
            const remaining = Math.round((TRADE_LOCK_MS - (now - lastTradeClickTime)) / 1000);
            log(`🛑 BLOCKED [${source}]: Cooldown ${remaining}s`);
            return false;
        }
        
        // GUARD 3: Prevent rapid duplicate trades
        if (now - lastTradeTimestamp < DUPLICATE_TRADE_WINDOW_MS) {
            log(`🛑 BLOCKED [${source}]: Too fast (${now - lastTradeTimestamp}ms)`);
            return false;
        }
        
        // SET LOCK IMMEDIATELY to prevent any race conditions
        globalTradeLock = true;
        
        // Find the EXACT button - be very specific to avoid double clicks
        let btn = null;
        
        // STRICT selectors - only exact matches
        if (isCall) {
            // Try CALL/UP/BUY buttons in order of specificity
            btn = document.querySelector('.btn-call') ||
                  document.querySelector('button.call') ||
                  document.querySelector('[data-testid="call-button"]') ||
                  document.querySelector('[data-testid="buy-button"]');
        } else {
            // Try PUT/DOWN/SELL buttons in order of specificity
            btn = document.querySelector('.btn-put') ||
                  document.querySelector('button.put') ||
                  document.querySelector('[data-testid="put-button"]') ||
                  document.querySelector('[data-testid="sell-button"]');
        }
        
        // If strict selectors didn't work, try finding by exact class name
        if (!btn) {
            const allButtons = document.querySelectorAll('button');
            for (const b of allButtons) {
                if (!b || !b.offsetParent) continue;
                
                const classes = (b.className || '').toLowerCase().split(/\s+/);
                const text = (b.textContent || '').toLowerCase().trim();
                
                if (isCall) {
                    // Only match if class is EXACTLY 'call', 'btn-call', 'up', 'buy'
                    // OR text is exactly 'call', 'up', 'buy'
                    const isCallButton = classes.some(c => c === 'call' || c === 'btn-call' || c === 'up' || c === 'buy' || c === 'call-btn' || c === 'up-btn') ||
                                        (text === 'call' || text === 'up' || text === 'buy' || text === 'higher');
                    if (isCallButton) {
                        btn = b;
                        break;
                    }
                } else {
                    // Only match if class is EXACTLY 'put', 'btn-put', 'down', 'sell'
                    // OR text is exactly 'put', 'down', 'sell'
                    const isPutButton = classes.some(c => c === 'put' || c === 'btn-put' || c === 'down' || c === 'sell' || c === 'put-btn' || c === 'down-btn') ||
                                       (text === 'put' || text === 'down' || text === 'sell' || text === 'lower');
                    if (isPutButton) {
                        btn = b;
                        break;
                    }
                }
            }
        }
        
        if (btn && btn.offsetParent !== null) {
            // Final validation - make sure we're not clicking both buttons
            lastTradeClickTime = now;
            lastTradeDirection = direction;
            lastTradeTimestamp = now;
            
            log(`✅ CLICKING ${direction} [${source}]`);
            console.log(`[GPT TRADE] ${new Date().toISOString()} - ${direction} - Source: ${source} - Button: ${btn.className}`);
            
            // SINGLE CLICK ONLY
            btn.click();
            
            // Release global lock after delay
            setTimeout(() => {
                globalTradeLock = false;
                log('🔓 Lock released');
            }, TRADE_LOCK_MS);
            
            return true;
        }
        
        // Button not found - release lock
        globalTradeLock = false;
        log(`❌ ${direction} button NOT FOUND`);
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
    // INITIALIZATION - v6.9.0
    // ===========================================
    function init() {
        console.log('[GPT Bot] Starting initialization v6.9.0...');
        
        try {
            // Load saved settings (all default to false)
            autoEnabled = GM_getValue('autoEnabled', false);
            scanEnabled = GM_getValue('scanEnabled', false);
            invertEnabled = GM_getValue('invertEnabled', false);
            
            // Load martingale settings
            martingaleEnabled = GM_getValue('martingaleEnabled', false);
            martingaleBaseAmount = GM_getValue('martingaleBaseAmount', 1);
            martingaleMultiplier = GM_getValue('martingaleMultiplier', 2);
            martingaleMaxSteps = GM_getValue('martingaleMaxSteps', 5);
            martingaleStep = GM_getValue('martingaleStep', 0);
            currentTradeAmount = calculateMartingaleAmount();
            
            // Load Money Management settings
            smartMartingale.enabled = GM_getValue('smartMartingaleEnabled', false);
            smartMartingale.targetProfit = GM_getValue('mmTargetProfit', 0.5);
            smartMartingale.maxSteps = GM_getValue('mmMaxSteps', 6);
            moneyManagement.accountBalance = GM_getValue('mmAccountBalance', 100);
            moneyManagement.riskPercentage = GM_getValue('mmRiskPercentage', 2);
            moneyManagement.sessionStartBalance = moneyManagement.accountBalance;
            
            // Calculate initial base trade amount
            calculateBaseTradeAmount();
            
            // Load sound settings
            soundNotificationsEnabled = GM_getValue('soundNotificationsEnabled', true);
            
            // Load stats if any
            const savedStats = GM_getValue('winLossStats', null);
            if (savedStats) {
                try {
                    winLossStats = JSON.parse(savedStats);
                } catch(e) {
                    console.log('[GPT Bot] Failed to parse saved stats');
                }
            }

            console.log('[GPT Bot] Creating panel...');
            console.log('[GPT Bot] v7.0.0 - Console window + improved asset switching');
            
            // Create panel immediately, don't wait
            createPanel();
            console.log('[GPT Bot] Panel created');
            
            getCurrentAsset();
            detectFavoritesBar();
            
            // Initialize UI
            initMartingaleUI();
            initMoneyManagementUI();
            updateWinLossDisplay();
            updateAllUI();
            
            manageIntervals();
            
            // Start heartbeat
            heartbeatInterval = setInterval(() => {
                sendHeartbeat();
                GM_setValue('winLossStats', JSON.stringify(winLossStats));
                GM_setValue('martingaleStep', martingaleStep);
            }, 10000);
            
            sendHeartbeat();
            console.log('[GPT Bot] Initialization complete');
            
        } catch(e) {
            console.error('[GPT Bot] Initialization error:', e);
        }
    }
    
    // Initialize martingale UI elements
    function initMartingaleUI() {
        // Legacy martingale UI removed in compact redesign
    }
    
    // Initialize Money Management UI elements
    function initMoneyManagementUI() {
        const balanceInput = document.getElementById('gpt-mm-balance-input');
        const riskInput = document.getElementById('gpt-mm-risk');
        
        if (balanceInput) balanceInput.value = moneyManagement.accountBalance;
        if (riskInput) riskInput.value = moneyManagement.riskPercentage;
    }
    
    // Update settings display from synced settings - v6.8.3 (compact UI)
    function updateSettingsDisplay() {
        // Settings display removed in compact UI
        // Settings are still tracked internally for signal generation
    }
    
    // Update favorites count display
    function updateFavoritesDisplay() {
        // Favorites count display removed in compact UI
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
