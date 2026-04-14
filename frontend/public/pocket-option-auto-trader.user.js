// ==UserScript==
// @name         Elite Pocket Option Trading Bot (Legacy)
// @namespace    https://momentum-trade-test.preview.emergentagent.com
// @version      8.7.2
// @description  Elite AI-powered trading bot - Auto-invert stays on same asset after loss for immediate retry
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
// @connect      signal-bot-staging.preview.emergentagent.com
// @connect      pocket-option-auto-2.preview.emergentagent.com
// @connect      *.preview.emergentagent.com
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
        API_URL: 'https://momentum-trade-test.preview.emergentagent.com/api',
        APP_POLL_INTERVAL: 3000,     // 3 seconds for app signals
        SCAN_INTERVAL: 5000,         // 5 seconds for scanning
        TRADE_COOLDOWN_SCAN: 30000,  // 30 seconds between SCAN trades
        TRADE_COOLDOWN_APP: 5000,    // 5 seconds between APP trades
        CYCLE_DWELL_TIME: 30000,     // 30 seconds per asset in CYCLE mode
        CYCLE_SCAN_INTERVAL: 3000,   // scan every 3s while dwelling on an asset
        MIN_CONFIDENCE: 65,
        MIN_PAYOUT: 65,
        DEBUG: true,
        USE_LOCAL_SIGNALS: true,  // v7.1.0: Generate signals locally using actual OTC prices
        LOCAL_CANDLE_COUNT: 50,   // Number of candles to analyze
        
        // ===========================================
        // v8.7.2 LATENCY & TIMING CONFIGURATION
        // Syncs the script timing with Pocket Option's platform
        // ===========================================
        RESULT_LATENCY_OFFSET: 0,       // Fine-tune result detection (-5 to +5 seconds)
        BET_DEDUCTION_DELAY: 2000,      // Wait after click for bet deduction (ms)
        POST_EXPIRY_BUFFER: 3000,       // Wait after expiry for PO balance update (ms)
        BALANCE_STABILITY_CHECKS: 2,    // Stable readings before confirming result
        BALANCE_POLL_INTERVAL: 500,     // Balance polling interval (ms)
        MAX_BALANCE_POLLS: 20,          // Max polls before timeout
        IMMEDIATE_RETRY_DELAY: 1500,    // Delay before inverted retry (ms)
        
        // v8.5.1 AI/ML DATA COLLECTION
        COLLECT_TRAINING_DATA: true,   // Send trade data to backend for ML training
        ADAPTIVE_MODEL_UPDATE: true,   // Request model updates based on recent performance
        BACKTEST_WINDOW: 100,          // Number of trades to use for local backtesting
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
        
        // MACD calculation (12, 26, 9 default - optimized: 10, 19, 7 for short-term)
        calculateMACD(prices, fastPeriod = 10, slowPeriod = 19, signalPeriod = 7) {
            if (prices.length < slowPeriod + signalPeriod) {
                return { macd: 0, signal: 0, histogram: 0, crossover: null };
            }
            
            // Calculate fast and slow EMAs
            const fastEMA = this.calculateEMA(prices, fastPeriod);
            const slowEMA = this.calculateEMA(prices, slowPeriod);
            const macd = fastEMA - slowEMA;
            
            // Calculate signal line (EMA of MACD)
            // Build MACD history for signal calculation
            const macdHistory = [];
            for (let i = slowPeriod; i <= prices.length; i++) {
                const slicedPrices = prices.slice(0, i);
                const fast = this.calculateEMA(slicedPrices, fastPeriod);
                const slow = this.calculateEMA(slicedPrices, slowPeriod);
                macdHistory.push(fast - slow);
            }
            
            const signal = macdHistory.length >= signalPeriod 
                ? this.calculateEMA(macdHistory, signalPeriod) 
                : macd;
            const histogram = macd - signal;
            
            // Detect crossover
            let crossover = null;
            if (macdHistory.length >= 2) {
                const prevMACD = macdHistory[macdHistory.length - 2];
                const prevSignal = macdHistory.length > signalPeriod 
                    ? this.calculateEMA(macdHistory.slice(0, -1), signalPeriod)
                    : prevMACD;
                
                if (prevMACD <= prevSignal && macd > signal) {
                    crossover = 'bullish';
                } else if (prevMACD >= prevSignal && macd < signal) {
                    crossover = 'bearish';
                }
            }
            
            return { macd, signal, histogram, crossover };
        },
        
        // RSI Divergence detection (powerful reversal signal)
        detectRSIDivergence(prices, rsiPeriod = 14, lookback = 10) {
            if (prices.length < rsiPeriod + lookback) {
                return { type: null, strength: 0 };
            }
            
            // Calculate RSI for recent periods
            const rsiValues = [];
            for (let i = rsiPeriod; i <= prices.length; i++) {
                rsiValues.push(this.calculateRSI(prices.slice(0, i), rsiPeriod));
            }
            
            if (rsiValues.length < lookback) return { type: null, strength: 0 };
            
            const recentPrices = prices.slice(-lookback);
            const recentRSI = rsiValues.slice(-lookback);
            
            // Find price and RSI extremes
            const priceLowest = Math.min(...recentPrices);
            const priceHighest = Math.max(...recentPrices);
            const rsiLowest = Math.min(...recentRSI);
            const rsiHighest = Math.max(...recentRSI);
            
            const currentPrice = prices[prices.length - 1];
            const currentRSI = rsiValues[rsiValues.length - 1];
            const prevPrice = prices[prices.length - 3]; // Look back a few bars
            const prevRSI = rsiValues[rsiValues.length - 3];
            
            // REGULAR BULLISH: Price lower low, RSI higher low (reversal UP)
            if (currentPrice <= priceLowest * 1.002 && currentRSI > rsiLowest + 3) {
                return { type: 'bullish_regular', strength: Math.abs(currentRSI - rsiLowest) };
            }
            
            // REGULAR BEARISH: Price higher high, RSI lower high (reversal DOWN)  
            if (currentPrice >= priceHighest * 0.998 && currentRSI < rsiHighest - 3) {
                return { type: 'bearish_regular', strength: Math.abs(rsiHighest - currentRSI) };
            }
            
            // HIDDEN BULLISH: Price higher low, RSI lower low (continuation UP)
            if (currentPrice > prevPrice && currentRSI < prevRSI - 5 && currentRSI < 40) {
                return { type: 'bullish_hidden', strength: Math.abs(prevRSI - currentRSI) };
            }
            
            // HIDDEN BEARISH: Price lower high, RSI higher high (continuation DOWN)
            if (currentPrice < prevPrice && currentRSI > prevRSI + 5 && currentRSI > 60) {
                return { type: 'bearish_hidden', strength: Math.abs(currentRSI - prevRSI) };
            }
            
            return { type: null, strength: 0 };
        },
        
        // ADX (Average Directional Index) - trend strength
        calculateADX(highs, lows, closes, period = 14) {
            if (closes.length < period + 1) return 25; // Default moderate trend
            
            let plusDM = 0, minusDM = 0, tr = 0;
            
            for (let i = closes.length - period; i < closes.length; i++) {
                const high = highs[i], low = lows[i];
                const prevHigh = highs[i-1], prevLow = lows[i-1], prevClose = closes[i-1];
                
                // True Range
                const trueRange = Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose));
                tr += trueRange;
                
                // Directional Movement
                const upMove = high - prevHigh;
                const downMove = prevLow - low;
                
                if (upMove > downMove && upMove > 0) plusDM += upMove;
                if (downMove > upMove && downMove > 0) minusDM += downMove;
            }
            
            // Simplified ADX approximation
            const plusDI = (plusDM / (tr + 0.00001)) * 100;
            const minusDI = (minusDM / (tr + 0.00001)) * 100;
            const dx = Math.abs(plusDI - minusDI) / (plusDI + minusDI + 0.00001) * 100;
            
            return dx; // Higher = stronger trend
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
        
        // MOMENTUM BUSTER 15s STRATEGY
        // Momentum indicator period 3 - green bars = buy, red bars = sell
        calculateMomentum(prices, period = 3) {
            if (prices.length < period + 1) return [];
            const momentum = [];
            for (let i = period; i < prices.length; i++) {
                momentum.push(prices[i] - prices[i - period]);
            }
            return momentum;
        },
        
        getMomentumBusterSignal(candles) {
            if (!candles || candles.length < 10) return null;
            
            const closes = candles.map(c => c.close);
            const momentum = this.calculateMomentum(closes, 3);
            
            if (momentum.length < 3) return null;
            
            const currentMom = momentum[momentum.length - 1];
            const prevMom = momentum[momentum.length - 2];
            const prevPrevMom = momentum[momentum.length - 3];
            
            // Detect bar colors
            const currentColor = currentMom > 0 ? 'green' : (currentMom < 0 ? 'red' : 'neutral');
            const prevColor = prevMom > 0 ? 'green' : (prevMom < 0 ? 'red' : 'neutral');
            const prevPrevColor = prevPrevMom > 0 ? 'green' : (prevPrevMom < 0 ? 'red' : 'neutral');
            
            // Count consecutive bars
            let consecutiveGreen = 0, consecutiveRed = 0;
            for (let i = momentum.length - 1; i >= 0; i--) {
                if (momentum[i] > 0) {
                    if (consecutiveRed > 0) break;
                    consecutiveGreen++;
                } else if (momentum[i] < 0) {
                    if (consecutiveGreen > 0) break;
                    consecutiveRed++;
                } else {
                    break;
                }
            }
            
            // Calculate strength
            const strength = Math.min(100, Math.abs(currentMom) * 10000);
            
            // Detect reversals
            let reversal = null;
            if (prevPrevColor === 'red' && prevColor === 'red' && currentColor === 'green') {
                reversal = 'bullish_reversal';
            } else if (prevPrevColor === 'green' && prevColor === 'green' && currentColor === 'red') {
                reversal = 'bearish_reversal';
            }
            
            let direction = null;
            let confidence = 60;
            const confirmations = [];
            
            // BUY: Green bars (positive momentum)
            if (currentColor === 'green') {
                direction = 'CALL';
                confirmations.push('momentum_positive');
                
                if (consecutiveGreen >= 2) {
                    confidence += 10;
                    confirmations.push(`consecutive_green_${consecutiveGreen}`);
                }
                if (reversal === 'bullish_reversal') {
                    confidence += 15;
                    confirmations.push('bullish_reversal');
                }
                if (strength > 30) {
                    confidence += 5;
                    confirmations.push('strong_momentum');
                }
            }
            // SELL: Red bars (negative momentum)
            else if (currentColor === 'red') {
                direction = 'PUT';
                confirmations.push('momentum_negative');
                
                if (consecutiveRed >= 2) {
                    confidence += 10;
                    confirmations.push(`consecutive_red_${consecutiveRed}`);
                }
                if (reversal === 'bearish_reversal') {
                    confidence += 15;
                    confirmations.push('bearish_reversal');
                }
                if (strength > 30) {
                    confidence += 5;
                    confirmations.push('strong_momentum');
                }
            }
            
            if (!direction || confidence < 65) return null;
            
            return {
                direction,
                confidence: Math.min(95, confidence),
                strategy: 'Momentum Buster 15s',
                expiration: 15,
                confirmations,
                indicators: {
                    momentum: currentMom,
                    momentumColor: currentColor,
                    strength,
                    consecutiveBars: currentColor === 'green' ? consecutiveGreen : consecutiveRed,
                    reversal
                }
            };
        },
        
        // =====================================================
        // KELTNER-MACD 5-SECOND STRATEGY
        // =====================================================
        // Keltner Channel: EMA(20), ATR(60), Multiplier 4
        // MACD: Fast(13), Slow(24), Signal(11)
        // BUY: Price above KC middle + MACD bullish cross
        // SELL: Price below KC middle + MACD bearish cross
        
        calculateATR(highs, lows, closes, period = 60) {
            if (closes.length < period + 1) return null;
            
            const trueRanges = [];
            for (let i = 1; i < closes.length; i++) {
                const hl = highs[i] - lows[i];
                const hc = Math.abs(highs[i] - closes[i - 1]);
                const lc = Math.abs(lows[i] - closes[i - 1]);
                trueRanges.push(Math.max(hl, hc, lc));
            }
            
            if (trueRanges.length < period) return null;
            
            // Simple moving average of TR for ATR
            const recentTR = trueRanges.slice(-period);
            return recentTR.reduce((a, b) => a + b, 0) / period;
        },
        
        calculateKeltnerChannel(highs, lows, closes) {
            const emaPeriod = 20;
            const atrPeriod = 60;
            const multiplier = 4;
            
            if (closes.length < Math.max(emaPeriod, atrPeriod) + 1) {
                return null;
            }
            
            // Middle line = EMA(20)
            const middle = this.calculateEMA(closes, emaPeriod);
            
            // ATR(60)
            const atr = this.calculateATR(highs, lows, closes, atrPeriod);
            if (!atr) return null;
            
            // Previous values for crossover detection
            const prevCloses = closes.slice(0, -1);
            const prevMiddle = this.calculateEMA(prevCloses, emaPeriod);
            
            return {
                middle,
                upper: middle + (multiplier * atr),
                lower: middle - (multiplier * atr),
                prevMiddle,
                atr
            };
        },
        
        calculateMACDKeltner(prices) {
            // MACD settings for this strategy: 13, 24, 11
            const fastPeriod = 13;
            const slowPeriod = 24;
            const signalPeriod = 11;
            
            if (prices.length < slowPeriod + signalPeriod) {
                return null;
            }
            
            // Build MACD line history
            const macdHistory = [];
            for (let i = slowPeriod; i <= prices.length; i++) {
                const sliced = prices.slice(0, i);
                const fast = this.calculateEMA(sliced, fastPeriod);
                const slow = this.calculateEMA(sliced, slowPeriod);
                macdHistory.push(fast - slow);
            }
            
            // Current MACD
            const macd = macdHistory[macdHistory.length - 1];
            const prevMacd = macdHistory[macdHistory.length - 2];
            
            // Signal line (EMA of MACD)
            if (macdHistory.length < signalPeriod) return null;
            
            const k = 2 / (signalPeriod + 1);
            let signal = macdHistory.slice(0, signalPeriod).reduce((a, b) => a + b, 0) / signalPeriod;
            for (let i = signalPeriod; i < macdHistory.length; i++) {
                signal = macdHistory[i] * k + signal * (1 - k);
            }
            
            // Previous signal
            const prevMacdHistory = macdHistory.slice(0, -1);
            let prevSignal = prevMacdHistory.slice(0, signalPeriod).reduce((a, b) => a + b, 0) / signalPeriod;
            for (let i = signalPeriod; i < prevMacdHistory.length; i++) {
                prevSignal = prevMacdHistory[i] * k + prevSignal * (1 - k);
            }
            
            const histogram = macd - signal;
            const prevHistogram = prevMacd - prevSignal;
            
            return {
                macd,
                signal,
                histogram,
                prevMacd,
                prevSignal,
                prevHistogram,
                bullishCross: prevMacd <= prevSignal && macd > signal,
                bearishCross: prevMacd >= prevSignal && macd < signal,
                bullishMomentum: macd > signal && macd > prevMacd,
                bearishMomentum: macd < signal && macd < prevMacd
            };
        },
        
        getKeltnerMACDSignal(candles) {
            // Requires at least 65 candles for ATR(60) calculation
            if (!candles || candles.length < 65) return null;
            
            const closes = candles.map(c => c.close);
            const highs = candles.map(c => c.high || c.close);
            const lows = candles.map(c => c.low || c.close);
            
            // Calculate Keltner Channel
            const kc = this.calculateKeltnerChannel(highs, lows, closes);
            if (!kc) return null;
            
            // Calculate MACD
            const macd = this.calculateMACDKeltner(closes);
            if (!macd) return null;
            
            const currentClose = closes[closes.length - 1];
            const prevClose = closes[closes.length - 2];
            
            let direction = null;
            let confidence = 60;
            const confirmations = [];
            
            // ===== CALL (BUY) CONDITIONS =====
            // Price breaks above Keltner middle line
            const priceAboveKC = currentClose > kc.middle && prevClose <= kc.prevMiddle;
            
            if (priceAboveKC) {
                confirmations.push('PRICE_ABOVE_KC_MIDDLE');
                confidence += 15;
            }
            
            if (macd.bullishCross) {
                confirmations.push('MACD_BULLISH_CROSS');
                confidence += 20;
            } else if (macd.bullishMomentum) {
                confirmations.push('MACD_BULLISH_MOMENTUM');
                confidence += 10;
            }
            
            // CALL when both conditions met
            if (priceAboveKC && (macd.bullishCross || macd.bullishMomentum)) {
                direction = 'CALL';
                if (macd.bullishCross) confidence += 5;
                
                // Bonus: histogram rising
                if (macd.histogram > macd.prevHistogram) {
                    confirmations.push('MACD_HIST_RISING');
                    confidence += 5;
                }
                
                // Bonus: room to upper band
                if (currentClose < kc.upper) {
                    confirmations.push('ROOM_TO_UPPER');
                    confidence += 3;
                }
            }
            
            // ===== PUT (SELL) CONDITIONS =====
            if (!direction) {
                // Price breaks below Keltner middle line
                const priceBelowKC = currentClose < kc.middle && prevClose >= kc.prevMiddle;
                
                if (priceBelowKC) {
                    confirmations.push('PRICE_BELOW_KC_MIDDLE');
                    confidence += 15;
                }
                
                if (macd.bearishCross) {
                    confirmations.push('MACD_BEARISH_CROSS');
                    confidence += 20;
                } else if (macd.bearishMomentum) {
                    confirmations.push('MACD_BEARISH_MOMENTUM');
                    confidence += 10;
                }
                
                // PUT when both conditions met
                if (priceBelowKC && (macd.bearishCross || macd.bearishMomentum)) {
                    direction = 'PUT';
                    if (macd.bearishCross) confidence += 5;
                    
                    // Bonus: histogram falling
                    if (macd.histogram < macd.prevHistogram) {
                        confirmations.push('MACD_HIST_FALLING');
                        confidence += 5;
                    }
                    
                    // Bonus: room to lower band
                    if (currentClose > kc.lower) {
                        confirmations.push('ROOM_TO_LOWER');
                        confidence += 3;
                    }
                }
            }
            
            if (!direction || confirmations.length < 2) return null;
            
            return {
                direction,
                confidence: Math.min(95, confidence),
                strategy: 'Keltner-MACD 5s',
                expiration: 5,
                confirmations,
                price: currentClose,
                indicators: {
                    keltner: {
                        middle: kc.middle,
                        upper: kc.upper,
                        lower: kc.lower
                    },
                    macd: {
                        macd: macd.macd,
                        signal: macd.signal,
                        histogram: macd.histogram
                    }
                }
            };
        },
        
        // IQ-720 ENSEMBLE STRATEGY (Advanced Multi-Indicator)
        // Combines: RSI, MACD, Stochastic, EMA alignment, BB, ADX, Keltner, Patterns
        // With market regime detection and session weighting
        getIQ720EnsembleSignal(candles) {
            if (!candles || candles.length < 50) return null;
            
            const closes = candles.map(c => c.close);
            const highs = candles.map(c => c.high || c.close);
            const lows = candles.map(c => c.low || c.close);
            const currentPrice = closes[closes.length - 1];
            
            // === Market Regime Detection ===
            const emaFast = this.calculateEMA(closes, 12);
            const emaSlow = this.calculateEMA(closes, 26);
            const trendDir = emaFast > emaSlow ? 1 : -1;
            
            // Volatility check
            const returns = [];
            for (let i = Math.max(1, closes.length - 20); i < closes.length; i++) {
                returns.push(Math.abs((closes[i] - closes[i-1]) / closes[i-1]));
            }
            const avgVol = returns.reduce((s, v) => s + v, 0) / returns.length;
            const recentVol = returns.slice(-5).reduce((s, v) => s + v, 0) / 5;
            const isHighVol = recentVol > avgVol * 1.5;
            
            // === Session Weight ===
            const hour = new Date().getUTCHours();
            let sessionWeight = 1.0;
            if (hour >= 13 && hour < 16) sessionWeight = 1.2;        // London/NY overlap
            else if (hour >= 8 && hour < 16) sessionWeight = 1.0;    // London
            else if (hour >= 13 && hour < 21) sessionWeight = 1.0;   // NY
            else if (hour >= 0 && hour < 8) sessionWeight = 0.8;     // Asian
            else sessionWeight = 0.6;                                  // Off hours
            
            let callScore = 0, putScore = 0;
            const confirmations = [];
            
            // 1. RSI (weight: 20%)
            const rsi = this.calculateRSI(closes, 14);
            if (rsi < 30) { callScore += 15; confirmations.push('RSI_OVERSOLD'); }
            else if (rsi > 70) { putScore += 15; confirmations.push('RSI_OVERBOUGHT'); }
            else if (rsi < 40) { callScore += 5; }
            else if (rsi > 60) { putScore += 5; }
            
            // 2. MACD (weight: 20%)
            const macd = this.calculateMACD(closes, 12, 26, 9);
            if (macd) {
                if (macd.crossover === 'bullish') { callScore += 20; confirmations.push('MACD_BULL_CROSS'); }
                else if (macd.histogram > 0) { callScore += 10; confirmations.push('MACD_BULLISH'); }
                if (macd.crossover === 'bearish') { putScore += 20; confirmations.push('MACD_BEAR_CROSS'); }
                else if (macd.histogram < 0) { putScore += 10; confirmations.push('MACD_BEARISH'); }
            }
            
            // 3. Stochastic (weight: 15%)
            const stoch = this.calculateStochastic(highs, lows, closes, 14);
            if (stoch.k < 20) { callScore += 15; confirmations.push('STOCH_OVERSOLD'); }
            else if (stoch.k > 80) { putScore += 15; confirmations.push('STOCH_OVERBOUGHT'); }
            if (stoch.k < 25 && stoch.k > stoch.d) { callScore += 10; confirmations.push('STOCH_BULL_CROSS'); }
            if (stoch.k > 75 && stoch.k < stoch.d) { putScore += 10; confirmations.push('STOCH_BEAR_CROSS'); }
            
            // 4. EMA Alignment (weight: 15%)
            const ema5 = this.calculateEMA(closes, 5);
            const ema10 = this.calculateEMA(closes, 10);
            const ema20 = this.calculateEMA(closes, 20);
            if (ema5 > ema10 && ema10 > ema20) { callScore += 15; confirmations.push('EMA_ALIGNED_BULL'); }
            else if (ema5 < ema10 && ema10 < ema20) { putScore += 15; confirmations.push('EMA_ALIGNED_BEAR'); }
            
            // 5. Bollinger Band Position (weight: 10%)
            const bb = this.calculateBollingerBands(closes, 20, 2);
            if (bb) {
                const bbRange = bb.upper - bb.lower;
                const bbPos = bbRange > 0 ? (currentPrice - bb.lower) / bbRange : 0.5;
                if (bbPos < 0.1) { callScore += 10; confirmations.push('BB_OVERSOLD'); }
                else if (bbPos > 0.9) { putScore += 10; confirmations.push('BB_OVERBOUGHT'); }
            }
            
            // 6. ADX Trend Strength (weight: 10%)
            const adx = this.calculateADX(highs, lows, closes, 14);
            if (adx > 25) {
                if (trendDir > 0) { callScore += 10; confirmations.push('ADX_STRONG_UP'); }
                else { putScore += 10; confirmations.push('ADX_STRONG_DOWN'); }
            }
            
            // 7. Candlestick patterns (bonus)
            const pattern = this.detectPattern(candles);
            if (pattern && pattern.type === 'hammer') { callScore += 8; confirmations.push('HAMMER'); }
            if (pattern && pattern.type === 'shooting_star') { putScore += 8; confirmations.push('SHOOTING_STAR'); }
            if (pattern && pattern.type === 'bullish_engulfing') { callScore += 8; confirmations.push('BULL_ENGULF'); }
            if (pattern && pattern.type === 'bearish_engulfing') { putScore += 8; confirmations.push('BEAR_ENGULF'); }
            
            // === Market Regime Adjustments ===
            if (trendDir > 0) { callScore += 10; }
            else { putScore += 10; }
            if (isHighVol) { callScore -= 10; putScore -= 10; } // Penalty for high volatility
            
            // === Determine Direction ===
            const minScoreDiff = 15;
            let direction = null;
            let rawConf = 0;
            
            if (callScore > putScore + minScoreDiff) {
                direction = 'CALL';
                rawConf = 50 + callScore;
            } else if (putScore > callScore + minScoreDiff) {
                direction = 'PUT';
                rawConf = 50 + putScore;
            } else {
                return null;
            }
            
            // === Calibrate Confidence ===
            let confidence = rawConf * 0.85 * sessionWeight;
            if (isHighVol) confidence -= 10;
            if (confirmations.length >= 3) confidence += 5;
            else if (confirmations.length <= 1) confidence -= 5;
            
            confidence = Math.max(0, Math.min(95, confidence));
            
            if (confidence < 65) return null;
            
            return {
                direction,
                confidence: Math.round(confidence),
                strategy: 'IQ-720 Ensemble',
                expiration: 5,
                confirmations,
                price: currentPrice,
                indicators: {
                    rsi, stoch_k: stoch.k, adx,
                    call_score: callScore, put_score: putScore,
                    session_weight: sessionWeight
                }
            };
        },
        
        // HOLLY CROSSOVER STRATEGY (5s/15s/30s)
        // EMA(12) x WMA(23) reversal crossover with S/R confirmation
        calculateWMA(prices, period) {
            if (prices.length < period) return null;
            const slice = prices.slice(-period);
            let weightSum = 0, valueSum = 0;
            for (let i = 0; i < period; i++) {
                const w = i + 1;
                valueSum += slice[i] * w;
                weightSum += w;
            }
            return valueSum / weightSum;
        },

        calculateEMAFull(prices, period) {
            // Returns array of EMA values (NaN where insufficient data)
            if (prices.length < period) return [null, null];
            const k = 2 / (period + 1);
            let ema = prices.slice(0, period).reduce((a, b) => a + b, 0) / period;
            const result = new Array(period - 1).fill(null);
            result.push(ema);
            for (let i = period; i < prices.length; i++) {
                ema = prices[i] * k + ema * (1 - k);
                result.push(ema);
            }
            return result;
        },

        calculateWMAFull(prices, period) {
            if (prices.length < period) return [null, null];
            const weights = [];
            let wSum = 0;
            for (let i = 1; i <= period; i++) { weights.push(i); wSum += i; }
            const result = new Array(period - 1).fill(null);
            for (let i = period - 1; i < prices.length; i++) {
                let val = 0;
                for (let j = 0; j < period; j++) val += prices[i - period + 1 + j] * weights[j];
                result.push(val / wSum);
            }
            return result;
        },

        detectTrendSimple(closes, lookback = 10) {
            if (closes.length < lookback) return 'neutral';
            const recent = closes.slice(-lookback);
            const n = recent.length;
            let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
            for (let i = 0; i < n; i++) {
                sumX += i; sumY += recent[i]; sumXY += i * recent[i]; sumXX += i * i;
            }
            const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
            const std = Math.sqrt(recent.reduce((s, v) => s + (v - sumY / n) ** 2, 0) / n);
            const threshold = std * 0.01;
            if (slope > threshold) return 'uptrend';
            if (slope < -threshold) return 'downtrend';
            return 'neutral';
        },

        findSRLevels(highs, lows, closes) {
            const n = closes.length;
            const lookback = Math.min(50, n);
            const rH = highs.slice(-lookback);
            const rL = lows.slice(-lookback);
            const current = closes[closes.length - 1];
            const supports = [], resistances = [];
            for (let i = 2; i < lookback - 2; i++) {
                if (rH[i] > rH[i-1] && rH[i] > rH[i-2] && rH[i] > rH[i+1] && rH[i] > rH[i+2])
                    resistances.push(rH[i]);
                if (rL[i] < rL[i-1] && rL[i] < rL[i-2] && rL[i] < rL[i+1] && rL[i] < rL[i+2])
                    supports.push(rL[i]);
            }
            const nearSup = supports.filter(s => s < current).sort((a, b) => b - a)[0] || null;
            const nearRes = resistances.filter(r => r > current).sort((a, b) => a - b)[0] || null;
            const tol = 0.05; // percent
            return {
                support: nearSup,
                resistance: nearRes,
                atSupport: nearSup !== null && Math.abs(current - nearSup) / current * 100 < tol,
                atResistance: nearRes !== null && Math.abs(nearRes - current) / current * 100 < tol,
            };
        },

        getHollyCrossoverSignal(candles) {
            if (!candles || candles.length < 28) return null;

            const closes = candles.map(c => c.close);
            const highs = candles.map(c => c.high);
            const lows = candles.map(c => c.low);

            const emaArr = this.calculateEMAFull(closes, 12);
            const wmaArr = this.calculateWMAFull(closes, 23);

            const emaCurr = emaArr[emaArr.length - 1];
            const emaPrev = emaArr[emaArr.length - 2];
            const wmaCurr = wmaArr[wmaArr.length - 1];
            const wmaPrev = wmaArr[wmaArr.length - 2];

            if (emaCurr == null || emaPrev == null || wmaCurr == null || wmaPrev == null) return null;

            const bullishCross = emaPrev <= wmaPrev && emaCurr > wmaCurr;
            const bearishCross = emaPrev >= wmaPrev && emaCurr < wmaCurr;
            if (!bullishCross && !bearishCross) return null;

            const trend = this.detectTrendSimple(closes);
            const sr = this.findSRLevels(highs, lows, closes);

            let direction = null;
            let confidence = 70;
            const confirmations = [];

            // CALL: bullish cross during downtrend
            if (bullishCross && trend === 'downtrend') {
                direction = 'CALL';
                confirmations.push('ema12_crosses_above_wma23', 'downtrend_reversal');
                if (sr.atSupport) { confidence += 10; confirmations.push('at_support'); }
                if (sr.support !== null) { confidence += 5; confirmations.push('support_nearby'); }
            }
            // PUT: bearish cross during uptrend
            else if (bearishCross && trend === 'uptrend') {
                direction = 'PUT';
                confirmations.push('ema12_crosses_below_wma23', 'uptrend_reversal');
                if (sr.atResistance) { confidence += 10; confirmations.push('at_resistance'); }
                if (sr.resistance !== null) { confidence += 5; confirmations.push('resistance_nearby'); }
            }

            if (!direction) return null;

            // Crossover strength bonus
            const gap = Math.abs(emaCurr - wmaCurr);
            if (gap / closes[closes.length - 1] * 100 > 0.01) {
                confidence += 5;
                confirmations.push('strong_crossover');
            }

            return {
                direction,
                confidence: Math.min(95, confidence),
                strategy: 'Holly Crossover',
                expiration: 5,
                confirmations,
                indicators: {
                    ema12: emaCurr,
                    wma23: wmaCurr,
                    trend,
                    support: sr.support,
                    resistance: sr.resistance
                }
            };
        },

        // GOLDEN ONE MOMENT 30s STRATEGY
        // RSI(2) + Stochastic(4,3,3) mean reversion crossover
        calculateStochasticFull(highs, lows, closes, kPeriod = 4, kSlow = 3, dPeriod = 3) {
            const n = closes.length;
            if (n < kPeriod) return { k: 50, d: 50, kPrev: 50 };
            
            // Calculate raw %K
            const rawK = new Array(n).fill(0);
            for (let i = kPeriod - 1; i < n; i++) {
                let hh = -Infinity, ll = Infinity;
                for (let j = i - kPeriod + 1; j <= i; j++) {
                    if (highs[j] > hh) hh = highs[j];
                    if (lows[j] < ll) ll = lows[j];
                }
                rawK[i] = (hh !== ll) ? ((closes[i] - ll) / (hh - ll)) * 100 : 50;
            }
            
            // Slow %K (SMA of raw K)
            const slowK = new Array(n).fill(0);
            for (let i = kPeriod + kSlow - 2; i < n; i++) {
                let sum = 0;
                for (let j = i - kSlow + 1; j <= i; j++) sum += rawK[j];
                slowK[i] = sum / kSlow;
            }
            
            // %D (SMA of slow K)
            const d = new Array(n).fill(0);
            for (let i = kPeriod + kSlow + dPeriod - 3; i < n; i++) {
                let sum = 0;
                for (let j = i - dPeriod + 1; j <= i; j++) sum += slowK[j];
                d[i] = sum / dPeriod;
            }
            
            return {
                k: slowK[n - 1] || 50,
                d: d[n - 1] || 50,
                kPrev: (n > 1 ? slowK[n - 2] : 50) || 50
            };
        },
        
        getGoldenOneMomentSignal(candles) {
            if (!candles || candles.length < 15) return null;
            
            const closes = candles.map(c => c.close);
            const highs = candles.map(c => c.high);
            const lows = candles.map(c => c.low);
            
            // RSI(2)
            const rsiCurr = this.calculateRSI(closes, 2);
            // Calculate RSI for previous bar
            const rsiPrev = this.calculateRSI(closes.slice(0, -1), 2);
            
            // Stochastic(4,3,3)
            const stoch = this.calculateStochasticFull(highs, lows, closes, 4, 3, 3);
            const stochPrev = this.calculateStochasticFull(
                highs.slice(0, -1), lows.slice(0, -1), closes.slice(0, -1), 4, 3, 3
            );
            
            const OB = 80, OS = 20;
            let direction = null;
            let confidence = 70;
            const confirmations = [];
            
            // CALL: prev RSI & Stoch below oversold, current RSI crosses above
            const prevOversold = (rsiPrev < OS && stochPrev.k < OS);
            const rsiCrossUp = (rsiPrev < OS && rsiCurr >= OS);
            
            if (prevOversold && rsiCrossUp) {
                direction = 'CALL';
                confirmations.push('rsi_oversold_crossover', 'stoch_oversold');
                if (stoch.k > stoch.d) {
                    confidence += 10;
                    confirmations.push('stoch_bullish_cross');
                }
                if (rsiCurr > 25 && rsiCurr < 40) confidence += 5;
                if (stoch.k >= OS) confidence += 5;
            }
            
            // PUT: prev RSI & Stoch above overbought, current RSI crosses below
            const prevOverbought = (rsiPrev > OB && stochPrev.k > OB);
            const rsiCrossDown = (rsiPrev > OB && rsiCurr <= OB);
            
            if (!direction && prevOverbought && rsiCrossDown) {
                direction = 'PUT';
                confirmations.push('rsi_overbought_crossover', 'stoch_overbought');
                if (stoch.k < stoch.d) {
                    confidence += 10;
                    confirmations.push('stoch_bearish_cross');
                }
                if (rsiCurr < 75 && rsiCurr > 60) confidence += 5;
                if (stoch.k <= OB) confidence += 5;
            }
            
            if (!direction) return null;
            
            return {
                direction,
                confidence: Math.min(95, confidence),
                strategy: 'Golden One Moment',
                expiration: 30,
                confirmations,
                indicators: {
                    rsi2: rsiCurr,
                    rsiPrev: rsiPrev,
                    stoch: stoch.k,
                    stochD: stoch.d,
                    stochPrev: stochPrev.k
                }
            };
        },
        
        // MAIN: Generate signal from candle data (OPTIMIZED v7.4)
        generateSignal(candles) {
            if (!candles || candles.length < 20) {
                return null;
            }
            
            const closes = candles.map(c => c.close);
            const highs = candles.map(c => c.high);
            const lows = candles.map(c => c.low);
            const currentPrice = closes[closes.length - 1];
            
            // === VOLATILITY FILTER ===
            // Skip signals during extreme volatility (noisy markets)
            const returns = [];
            for (let i = 1; i < Math.min(closes.length, 21); i++) {
                returns.push((closes[i] - closes[i-1]) / closes[i-1]);
            }
            const avgVol = returns.length > 0 ? Math.sqrt(returns.reduce((s, r) => s + r*r, 0) / returns.length) : 0;
            const recentVol = returns.length >= 5 ? Math.sqrt(returns.slice(-5).reduce((s, r) => s + r*r, 0) / 5) : 0;
            
            // Block signals if short-term vol is 2x+ long-term (choppy/news spike)
            if (avgVol > 0 && recentVol > avgVol * 2.0) {
                return null; // Too volatile, skip
            }
            
            // Calculate indicators
            const rsi2 = this.calculateRSI(closes, 2);
            const rsi14 = this.calculateRSI(closes, 14);
            const ema5 = this.calculateEMA(closes, 5);
            const ema10 = this.calculateEMA(closes, 10);
            const ema20 = this.calculateEMA(closes, 20);
            const ema50 = this.calculateEMA(closes, 50);
            const stoch = this.calculateStochastic(highs, lows, closes, 5);
            const bb = this.calculateBollingerBands(closes, 20, 2);
            const pattern = this.detectPattern(candles);
            
            // NEW: MACD and RSI Divergence (high-accuracy signals)
            const macd = this.calculateMACD(closes, 10, 19, 7);
            const divergence = this.detectRSIDivergence(closes, 14, 10);
            const adx = this.calculateADX(highs, lows, closes, 14);
            
            // Count confirmations (tighter thresholds for higher accuracy)
            let callConfs = [];
            let putConfs = [];
            
            // === HIGH-PRIORITY SIGNALS (Divergence + MACD) ===
            // RSI Divergence - VERY powerful reversal signal (2 confirmations each)
            if (divergence.type === 'bullish_regular' || divergence.type === 'bullish_hidden') {
                callConfs.push('RSI_DIVERGENCE_BULL');
                callConfs.push('DIVERGENCE_STRONG');
            }
            if (divergence.type === 'bearish_regular' || divergence.type === 'bearish_hidden') {
                putConfs.push('RSI_DIVERGENCE_BEAR');
                putConfs.push('DIVERGENCE_STRONG');
            }
            
            // MACD crossover - reliable momentum signal
            if (macd.crossover === 'bullish') {
                callConfs.push('MACD_BULLISH_CROSS');
                if (macd.histogram > 0) callConfs.push('MACD_HISTOGRAM_POS');
            }
            if (macd.crossover === 'bearish') {
                putConfs.push('MACD_BEARISH_CROSS');
                if (macd.histogram < 0) putConfs.push('MACD_HISTOGRAM_NEG');
            }
            
            // MACD histogram direction (momentum)
            if (macd.macd > macd.signal && macd.histogram > 0) callConfs.push('MACD_MOMENTUM_UP');
            if (macd.macd < macd.signal && macd.histogram < 0) putConfs.push('MACD_MOMENTUM_DOWN');
            
            // === TREND FILTER (EMA 50) ===
            // Only take calls when price > EMA50 trend, puts when price < EMA50
            const trendBias = currentPrice > ema50 ? 'bullish' : 'bearish';
            if (trendBias === 'bullish' && adx > 20) callConfs.push('TREND_ALIGNED');
            if (trendBias === 'bearish' && adx > 20) putConfs.push('TREND_ALIGNED');
            
            // RSI extremes (tightened: 15/85 instead of 20/80)
            if (rsi2 < 8) { callConfs.push('RSI2_EXTREME'); callConfs.push('RSI2_DEEP_OVERSOLD'); }
            else if (rsi2 < 15) callConfs.push('RSI2_OVERSOLD');
            
            if (rsi2 > 92) { putConfs.push('RSI2_EXTREME'); putConfs.push('RSI2_DEEP_OVERBOUGHT'); }
            else if (rsi2 > 85) putConfs.push('RSI2_OVERBOUGHT');
            
            // Stochastic (tightened)
            if (stoch.k < 15 && stoch.d < 20) callConfs.push('STOCH_OVERSOLD');
            if (stoch.k > 85 && stoch.d > 80) putConfs.push('STOCH_OVERBOUGHT');
            
            // Stochastic cross (stronger signal)
            if (stoch.k < 25 && stoch.k > stoch.d) callConfs.push('STOCH_BULLISH_CROSS');
            if (stoch.k > 75 && stoch.k < stoch.d) putConfs.push('STOCH_BEARISH_CROSS');
            
            // Bollinger Bands
            if (currentPrice <= bb.lower) callConfs.push('BB_LOWER');
            if (currentPrice >= bb.upper) putConfs.push('BB_UPPER');
            
            // EMA trend (reversal context)
            if (ema5 > ema10 && ema10 > ema20) putConfs.push('TREND_UP_REVERSAL');
            if (ema5 < ema10 && ema10 < ema20) callConfs.push('TREND_DOWN_REVERSAL');
            
            // EMA crossover (fresh cross is stronger signal)
            const prevEma5 = this.calculateEMA(closes.slice(0, -1), 5);
            const prevEma10 = this.calculateEMA(closes.slice(0, -1), 10);
            if (prevEma5 <= prevEma10 && ema5 > ema10) callConfs.push('EMA_BULLISH_CROSS');
            if (prevEma5 >= prevEma10 && ema5 < ema10) putConfs.push('EMA_BEARISH_CROSS');
            
            // Candlestick patterns
            if (pattern.bullish) callConfs.push(pattern.name);
            if (pattern.bearish) putConfs.push(pattern.name);
            
            // Momentum reversal
            if (closes.length > 5) {
                const momentum = closes[closes.length - 1] - closes[closes.length - 5];
                if (momentum < 0 && rsi2 < 25) callConfs.push('MOMENTUM_REVERSAL');
                if (momentum > 0 && rsi2 > 75) putConfs.push('MOMENTUM_REVERSAL');
            }
            
            // RSI14 confluence
            if (rsi14 < 35) callConfs.push('RSI14_OVERSOLD');
            if (rsi14 > 65) putConfs.push('RSI14_OVERBOUGHT');
            
            // === MINIMUM CONFIRMATIONS ===
            const minConfs = 3; // Reduced from 4 to 3 for better signal flow
            
            // === CONFLICT PENALTY ===
            // If both sides have 3+ confirmations, market is conflicted — skip
            if (callConfs.length >= 3 && putConfs.length >= 3) {
                return null; // Conflicting signals
            }
            
            if (callConfs.length >= minConfs && callConfs.length > putConfs.length + 1) {
                // Boost confidence for divergence signals (proven high accuracy)
                let confidence = Math.min(95, 58 + callConfs.length * 7);
                if (callConfs.includes('RSI_DIVERGENCE_BULL')) confidence = Math.min(95, confidence + 5);
                if (callConfs.includes('MACD_BULLISH_CROSS')) confidence = Math.min(95, confidence + 3);
                
                if (confidence < CONFIG.MIN_CONFIDENCE) return null;
                return {
                    direction: 'CALL',
                    confidence,
                    strategy: 'Local Engine v8.5',
                    confirmations: callConfs,
                    count: callConfs.length,
                    price: currentPrice,
                    indicators: { 
                        rsi2, rsi14, stoch: stoch.k, 
                        macd: macd.histogram.toFixed(5), 
                        adx: Math.round(adx),
                        divergence: divergence.type,
                        trend: trendBias,
                        volatility: recentVol 
                    }
                };
            }
            
            if (putConfs.length >= minConfs && putConfs.length > callConfs.length + 1) {
                // Boost confidence for divergence signals
                let confidence = Math.min(95, 58 + putConfs.length * 7);
                if (putConfs.includes('RSI_DIVERGENCE_BEAR')) confidence = Math.min(95, confidence + 5);
                if (putConfs.includes('MACD_BEARISH_CROSS')) confidence = Math.min(95, confidence + 3);
                
                if (confidence < CONFIG.MIN_CONFIDENCE) return null;
                return {
                    direction: 'PUT',
                    confidence,
                    strategy: 'Local Engine v8.5',
                    confirmations: putConfs,
                    count: putConfs.length,
                    price: currentPrice,
                    indicators: { 
                        rsi2, rsi14, stoch: stoch.k, 
                        macd: macd.histogram.toFixed(5), 
                        adx: Math.round(adx),
                        divergence: divergence.type,
                        trend: trendBias,
                        volatility: recentVol 
                    }
                };
            }
            
            return null;
        }
    };

    // ===========================================
    // v7.3.2 POCKET OPTION PRICE SCRAPER - SUPER AGGRESSIVE
    // ===========================================
    const PriceScraperV2 = {
        priceHistory: [],
        candleHistory: [],
        maxCandles: 100,
        lastScrapedPrice: null,
        debugMode: true,
        lastDebugTime: 0,
        foundSelector: null,
        scanCount: 0,
        
        // Scrape current price from Pocket Option UI
        scrapeCurrentPrice() {
            this.scanCount++;
            const now = Date.now();
            const shouldDebug = this.debugMode && (now - this.lastDebugTime > 3000);
            
            if (shouldDebug) {
                this.lastDebugTime = now;
                log(`🔍 Price scan #${this.scanCount}...`);
            }
            
            // If we found a working selector before, try it first
            if (this.foundSelector) {
                const price = this._trySelector(this.foundSelector, false);
                if (price) return price;
                this.foundSelector = null;
                if (shouldDebug) log('⚠️ Previous selector stopped working, rescanning...');
            }
            
            // STRATEGY 1: Look for numbers that look like forex prices ANYWHERE on page
            const allPrices = this._findAllPricesOnPage();
            if (allPrices.length > 0) {
                // Pick the most likely price (center of screen, reasonable size)
                const best = this._pickBestPrice(allPrices);
                if (best) {
                    if (shouldDebug) log(`💰 Found price: ${best.price} from "${best.context}"`);
                    this.lastScrapedPrice = best.price;
                    return best.price;
                }
            }
            
            // STRATEGY 2: Search the entire page text for price patterns
            const pagePrice = this._searchPageText();
            if (pagePrice) {
                if (shouldDebug) log(`💰 Found from page text: ${pagePrice}`);
                this.lastScrapedPrice = pagePrice;
                return pagePrice;
            }
            
            // STRATEGY 3: Check iframe content (some platforms use iframes)
            const iframePrice = this._searchIframes();
            if (iframePrice) {
                if (shouldDebug) log(`💰 Found from iframe: ${iframePrice}`);
                this.lastScrapedPrice = iframePrice;
                return iframePrice;
            }
            
            if (shouldDebug) {
                log('⚠️ NO PRICE FOUND - Dumping page info:');
                this._dumpPageInfo();
            }
            
            return null;
        },
        
        _findAllPricesOnPage() {
            const prices = [];
            
            // Get ALL elements that might contain prices
            const elements = document.querySelectorAll('*');
            
            for (const el of elements) {
                // Skip hidden elements
                if (!el.offsetParent && el.tagName !== 'BODY') continue;
                
                // Skip script, style, etc.
                const tag = el.tagName.toLowerCase();
                if (['script', 'style', 'meta', 'link', 'noscript'].includes(tag)) continue;
                
                // Get direct text content (not children)
                const text = this._getDirectText(el);
                if (!text) continue;
                
                // Find all price-like patterns
                const pricePatterns = [
                    /\b(\d{1,3}\.\d{2,6})\b/g,  // 1.08, 1.0823, 108.23, etc.
                    /\b(\d{2,3}[.,]\d{2,5})\b/g // European format 108,234
                ];
                
                for (const pattern of pricePatterns) {
                    let match;
                    while ((match = pattern.exec(text)) !== null) {
                        const numStr = match[1].replace(',', '.');
                        const num = parseFloat(numStr);
                        
                        if (this._isValidPrice(num)) {
                            const rect = el.getBoundingClientRect();
                            prices.push({
                                price: num,
                                element: el,
                                text: text.substring(0, 50),
                                context: el.className || el.tagName,
                                rect: rect,
                                score: this._calculateScore(el, rect, num)
                            });
                        }
                    }
                }
            }
            
            return prices;
        },
        
        _getDirectText(el) {
            // Get only direct text content, not from children
            let text = '';
            for (const node of el.childNodes) {
                if (node.nodeType === Node.TEXT_NODE) {
                    text += node.textContent;
                }
            }
            return text.trim();
        },
        
        _isValidPrice(num) {
            if (isNaN(num) || num <= 0) return false;
            
            // Forex major pairs ranges
            if (num >= 0.5 && num <= 2.0) return true;    // EUR/USD, GBP/USD, etc.
            if (num >= 0.6 && num <= 1.5) return true;    // AUD, NZD, etc.
            if (num >= 100 && num <= 160) return true;    // JPY pairs
            if (num >= 0.85 && num <= 0.99) return true;  // EUR/GBP type
            
            // OTC might have different ranges - be more permissive
            if (num >= 0.1 && num <= 10) return true;
            if (num >= 50 && num <= 200) return true;
            
            return false;
        },
        
        _calculateScore(el, rect, price) {
            let score = 0;
            
            // Prefer elements in the visible viewport
            if (rect.top > 0 && rect.top < window.innerHeight * 0.7) score += 50;
            
            // Prefer elements near center horizontally
            const centerX = rect.left + rect.width / 2;
            if (centerX > window.innerWidth * 0.3 && centerX < window.innerWidth * 0.7) score += 30;
            
            // Prefer larger text
            const fontSize = parseFloat(window.getComputedStyle(el).fontSize);
            if (fontSize >= 16) score += 20;
            if (fontSize >= 24) score += 20;
            
            // Prefer elements with price-related class names
            const className = (el.className || '').toLowerCase();
            if (className.includes('price')) score += 40;
            if (className.includes('value')) score += 30;
            if (className.includes('rate')) score += 30;
            if (className.includes('quote')) score += 30;
            if (className.includes('current')) score += 20;
            if (className.includes('chart')) score += 20;
            
            // Prefer prices that changed recently (if we have history)
            if (this.lastScrapedPrice && Math.abs(price - this.lastScrapedPrice) < 0.01) {
                score += 25; // Similar to last price = more likely correct
            }
            
            return score;
        },
        
        _pickBestPrice(prices) {
            if (prices.length === 0) return null;
            
            // Sort by score descending
            prices.sort((a, b) => b.score - a.score);
            
            return prices[0];
        },
        
        _searchPageText() {
            // Search the entire body text
            const bodyText = document.body.innerText || '';
            
            // Look for price patterns
            const patterns = [
                /(?:price|rate|quote|value)[:\s]*(\d{1,3}\.\d{2,6})/gi,
                /(\d{1,3}\.\d{4,6})/g  // Strict forex format
            ];
            
            for (const pattern of patterns) {
                const match = pattern.exec(bodyText);
                if (match) {
                    const price = parseFloat(match[1]);
                    if (this._isValidPrice(price)) {
                        return price;
                    }
                }
            }
            
            return null;
        },
        
        _searchIframes() {
            try {
                const iframes = document.querySelectorAll('iframe');
                for (const iframe of iframes) {
                    try {
                        const doc = iframe.contentDocument || iframe.contentWindow?.document;
                        if (doc) {
                            const text = doc.body?.innerText || '';
                            const match = text.match(/(\d{1,3}\.\d{4,6})/);
                            if (match) {
                                const price = parseFloat(match[1]);
                                if (this._isValidPrice(price)) {
                                    return price;
                                }
                            }
                        }
                    } catch (e) {
                        // Cross-origin iframe, skip
                    }
                }
            } catch (e) {}
            return null;
        },
        
        _dumpPageInfo() {
            // Find all numbers on the page for debugging
            const bodyText = document.body.innerText || '';
            const allNumbers = bodyText.match(/\d+\.\d{2,}/g) || [];
            const uniqueNumbers = [...new Set(allNumbers)].slice(0, 20);
            
            log(`📊 All numbers found on page: ${uniqueNumbers.join(', ')}`);
            
            // Check for common trading platform elements
            const tradingElements = [
                '.chart', '[class*="chart"]',
                '.price', '[class*="price"]',
                '.trade', '[class*="trade"]',
                '.call', '.put', '.buy', '.sell'
            ];
            
            for (const sel of tradingElements) {
                const count = document.querySelectorAll(sel).length;
                if (count > 0) {
                    log(`Found ${count} elements matching: ${sel}`);
                }
            }
        },
        
        _trySelector(selector, debug) {
            try {
                const els = document.querySelectorAll(selector);
                for (const el of els) {
                    if (!el.offsetParent) continue;
                    const text = (el.textContent || '').trim();
                    const match = text.match(/(\d{1,3}\.\d{2,6})/);
                    if (match) {
                        const price = parseFloat(match[1]);
                        if (this._isValidPrice(price)) {
                            return price;
                        }
                    }
                }
            } catch (e) {}
            return null;
        },
        
        _isValidForexPrice(price) {
            return this._isValidPrice(price);
        },
        
        _logAllPotentialPrices() {
            this._dumpPageInfo();
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
    // v7.6.1 HISTORICAL DATA COLLECTOR
    // Collects and sends candle data to backend for ML training
    // ===========================================
    const HistoricalDataCollector = {
        enabled: false,
        collectionInterval: null,
        candleBuffer: [],
        maxBufferSize: 100,
        lastSentTime: 0,
        sendIntervalMs: 60000, // Send every 60 seconds
        
        // Timeframe in seconds for candle aggregation
        candleTimeframes: {
            '5s': 5000,
            '15s': 15000,
            '30s': 30000,
            'M1': 60000
        },
        
        currentCandle: null,
        currentTimeframe: '5s',
        candleStartTime: 0,
        
        start(timeframe = '5s') {
            if (this.collectionInterval) {
                clearInterval(this.collectionInterval);
            }
            
            this.enabled = true;
            this.currentTimeframe = timeframe;
            const tfMs = this.candleTimeframes[timeframe] || 5000;
            
            log(`📊 Data collector started: ${timeframe} candles`);
            
            // Collect price data every 500ms
            this.collectionInterval = setInterval(() => {
                this.collectPrice();
            }, 500);
            
            // Send buffer to backend periodically
            setInterval(() => {
                this.sendToBackend();
            }, this.sendIntervalMs);
        },
        
        stop() {
            this.enabled = false;
            if (this.collectionInterval) {
                clearInterval(this.collectionInterval);
                this.collectionInterval = null;
            }
            log('📊 Data collector stopped');
        },
        
        collectPrice() {
            if (!this.enabled) return;
            
            const price = PriceScraperV2.scrapeCurrentPrice();
            if (!price) return;
            
            const now = Date.now();
            const tfMs = this.candleTimeframes[this.currentTimeframe] || 5000;
            
            // Start new candle
            if (!this.currentCandle || (now - this.candleStartTime >= tfMs)) {
                // Save completed candle
                if (this.currentCandle) {
                    this.candleBuffer.push({
                        timestamp: new Date(this.candleStartTime).toISOString(),
                        open: this.currentCandle.open,
                        high: this.currentCandle.high,
                        low: this.currentCandle.low,
                        close: this.currentCandle.close,
                        volume: this.currentCandle.ticks
                    });
                    
                    // Trim buffer if too large
                    if (this.candleBuffer.length > this.maxBufferSize) {
                        this.candleBuffer = this.candleBuffer.slice(-this.maxBufferSize);
                    }
                }
                
                // Start new candle
                this.currentCandle = {
                    open: price,
                    high: price,
                    low: price,
                    close: price,
                    ticks: 1
                };
                this.candleStartTime = now;
            } else {
                // Update current candle
                this.currentCandle.high = Math.max(this.currentCandle.high, price);
                this.currentCandle.low = Math.min(this.currentCandle.low, price);
                this.currentCandle.close = price;
                this.currentCandle.ticks++;
            }
        },
        
        async sendToBackend() {
            if (!this.enabled || this.candleBuffer.length === 0) return;
            
            const currentAssetNow = getCurrentAsset() || 'UNKNOWN_OTC';
            const candles = [...this.candleBuffer];
            this.candleBuffer = [];
            
            try {
                GM_xmlhttpRequest({
                    method: 'POST',
                    url: `${CONFIG.API_URL}/tampermonkey/candles?symbol=${encodeURIComponent(currentAssetNow)}&timeframe=${this.currentTimeframe}`,
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    data: JSON.stringify(candles),
                    timeout: 10000,
                    onload: (res) => {
                        if (res.status === 200) {
                            const data = JSON.parse(res.responseText);
                            if (data.success) {
                                log(`📊 Sent ${candles.length} candles to backend (stored: ${data.stored})`);
                            }
                        }
                    },
                    onerror: (e) => {
                        // Silently fail - will retry next interval
                        this.candleBuffer = candles.concat(this.candleBuffer);
                    }
                });
            } catch (e) {
                // Re-add candles to buffer for retry
                this.candleBuffer = candles.concat(this.candleBuffer);
            }
        },
        
        getStats() {
            return {
                enabled: this.enabled,
                timeframe: this.currentTimeframe,
                bufferedCandles: this.candleBuffer.length,
                currentCandle: this.currentCandle
            };
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
    let cycleEnabled = false;   // CYCLE mode: physically click through favorites
    let cycleRunning = false;   // Whether the cycle loop is actively running
    let cycleAbort = false;     // Signal to stop the cycle loop
    
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
    let selectedStrategy = 'default';
    let selectedTimeframe = '5s';
    let signalSource = 'app_ai';  // app_ai, tradingview, mt4, mt5, tampermonkey_scan
    let favoritesFromBar = [];    // Detected from PO favorites bar
    let currentFavoriteIndex = 0; // For cycling through favorites

    // ===========================================
    // SMART AUTO-INVERT SYSTEM - v8.2
    // Simple: WIN = keep state, LOSS = toggle state
    // Audio detection for automatic outcome tracking
    // ===========================================
    let smartAutoInvert = {
        enabled: false,        // User toggles this via INVERT button
        invertActive: false,   // Current invert state (signals flipped when true)
    };

    // Track last trade info for premium result recording and ML training
    let lastTradeInfo = {
        symbol: '',
        direction: '',
        confidence: 0,
        strategy: 'unknown',
        indicators: {}
    };
    
    // Store indicators globally for ML training
    window.lastTradeIndicators = {};
    window.lastTradeStrategy = 'unknown';

    // Trade outcome detection state
    let audioDetection = {
        enabled: true,
        lastDetectedOutcome: null,   // 'win' or 'loss'
        lastDetectionTime: 0,
        cooldownMs: 3000,            // Ignore duplicate detections within 3s
        pendingTrade: false,         // Whether we have an open trade waiting for result
        tradeOpenedAt: 0,
        tradeExpirySeconds: 60,      // The actual expiry time for the current trade
        tradeAmount: 1,              // The bet amount for the current trade
        minWaitAfterTrade: 3000,     // Buffer after expiry before checking
        balanceBeforeTrade: 0,       // Balance before trade (pre-click)
        balanceAfterBet: 0,          // Balance AFTER bet deducted (2s after click)
        ourSoundPlaying: false,      // Flag to ignore our own notification sounds
    };
    
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
    
    // Auto-invert uses smartAutoInvert.invertActive (see above)
    
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
        audioDetection.ourSoundPlaying = true;
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
            setTimeout(() => { osc.stop(); ctx.close(); audioDetection.ourSoundPlaying = false; }, 150);
        } catch(e) { audioDetection.ourSoundPlaying = false; }
    }

    function playScanSignalSound() {
        // Low-pitched beep for SCAN signals
        audioDetection.ourSoundPlaying = true;
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
            setTimeout(() => { osc.stop(); ctx.close(); audioDetection.ourSoundPlaying = false; }, 300);
        } catch(e) { audioDetection.ourSoundPlaying = false; }
    }

    // ===========================================
    // WIN/LOSS SOUND NOTIFICATIONS - v6.6.0
    // ===========================================
    function playWinSound() {
        if (!soundNotificationsEnabled) return;
        audioDetection.ourSoundPlaying = true;
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
            setTimeout(() => { osc.stop(); ctx.close(); audioDetection.ourSoundPlaying = false; }, 400);
        } catch(e) { audioDetection.ourSoundPlaying = false; }
    }

    function playLossSound() {
        if (!soundNotificationsEnabled) return;
        audioDetection.ourSoundPlaying = true;
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
            setTimeout(() => { osc.stop(); ctx.close(); audioDetection.ourSoundPlaying = false; }, 500);
        } catch(e) { audioDetection.ourSoundPlaying = false; }
    }

    function playStopSound() {
        if (!soundNotificationsEnabled) return;
        audioDetection.ourSoundPlaying = true;
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
            setTimeout(() => { osc.stop(); ctx.close(); audioDetection.ourSoundPlaying = false; }, 800);
        } catch(e) { audioDetection.ourSoundPlaying = false; }
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
    // DETECT CURRENT TIMEFRAME FROM POCKET OPTION UI - v8.4.1
    // ===========================================
    function detectCurrentTimeframe() {
        // Pocket Option shows the selected timeframe in various places
        // Try to detect from the UI
        
        const timeframeSelectors = [
            // Common PO timeframe display locations
            '[class*="time-option"].active',
            '[class*="expiration"].selected',
            '[class*="time-button"].active',
            '[class*="expiry-time"] .active',
            '[data-testid*="time"] .selected',
            '.deal-duration .active',
            '.expiry-control .active',
            // Look for common timeframe buttons that are selected
            'button.time-option.active',
            '.time-selector .active',
        ];
        
        for (const sel of timeframeSelectors) {
            try {
                const el = document.querySelector(sel);
                if (el) {
                    const text = (el.textContent || '').trim();
                    // Parse text like "5s", "30s", "1m", "5:00", etc.
                    const seconds = parseTimeframeText(text);
                    if (seconds > 0) {
                        log(`TIMEFRAME: Detected ${text} = ${seconds}s from UI`);
                        return seconds;
                    }
                }
            } catch (e) {}
        }
        
        // Try to find any visible timeframe indicator
        const allButtons = document.querySelectorAll('button, [role="button"], [class*="time"]');
        for (const btn of allButtons) {
            if (!btn || !btn.offsetParent) continue;
            
            const text = (btn.textContent || '').trim();
            const classes = (btn.className || '').toLowerCase();
            
            // Look for active/selected state
            if ((classes.includes('active') || classes.includes('selected')) && 
                (text.match(/^\d+s?$/) || text.match(/^\d+:\d{2}$/) || text.match(/^\d+m$/))) {
                const seconds = parseTimeframeText(text);
                if (seconds > 0 && seconds <= 3600) {
                    log(`TIMEFRAME: Detected ${text} = ${seconds}s from button`);
                    return seconds;
                }
            }
        }
        
        // Default to 60 seconds
        log('TIMEFRAME: Could not detect, using default 60s');
        return 60;
    }
    
    function parseTimeframeText(text) {
        if (!text) return 0;
        
        // Handle "5s", "30s", "1m", "5m" format
        const match1 = text.match(/^(\d+)(s|m)$/i);
        if (match1) {
            const value = parseInt(match1[1]);
            return match1[2].toLowerCase() === 'm' ? value * 60 : value;
        }
        
        // Handle "1:00", "5:00" format (mm:ss)
        const match2 = text.match(/^(\d+):(\d{2})$/);
        if (match2) {
            return parseInt(match2[1]) * 60 + parseInt(match2[2]);
        }
        
        // Handle just number (assume seconds if small, minutes if larger)
        const num = parseInt(text);
        if (!isNaN(num)) {
            if (num <= 60) return num;  // Assume seconds
            if (num <= 300) return num; // Still seconds
            return num;
        }
        
        return 0;
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
    
    // ===========================================
    // BALANCE SYNC SYSTEM - v8.4
    // Primary: Scrape PO UI | Fallback: Backend API
    // Auto-recalculates bet from live balance
    // ===========================================
    let balanceSync = {
        lastUIBalance: 0,
        lastAPIBalance: 0,
        lastSyncTime: 0,
        syncIntervalMs: 5000,     // Sync every 5 seconds
        apiFailCount: 0,
        maxAPIFails: 3,
    };
    
    // Detect current account balance from UI
    function detectAccountBalance(forceRefresh = false) {
        // Look for balance display on Pocket Option
        // PO shows balance in various formats depending on version/layout
        const balanceSelectors = [
            // Primary PO balance selectors
            '.balance__value',
            '.balance-value',
            '[class*="balance__value"]',
            '[class*="balance-value"]',
            '.js-balance',
            '[data-testid="balance"]',
            
            // Secondary selectors
            '.balance span',
            '.balance',
            '[class*="balances"] [class*="amount"]',
            '[class*="balance"] [class*="value"]',
            '[class*="user-balance"]',
            '[class*="account-value"]',
            '.account-balance',
            
            // Demo/Real balance specific
            '[class*="demo-balance"]',
            '[class*="real-balance"]',
            '[class*="current-balance"]',
            
            // Header balance area
            'header [class*="balance"]',
            '.header__balance',
            '[class*="header"] [class*="amount"]',
        ];
        
        for (const sel of balanceSelectors) {
            try {
                const elements = document.querySelectorAll(sel);
                for (const el of elements) {
                    if (!el || !el.offsetParent) continue; // Skip hidden elements
                    
                    const text = el.textContent || '';
                    // Match patterns like "$1,234.56" or "1234.56" or "$ 1,234.56" or "1 234.56"
                    const match = text.match(/\$?\s?([\d\s,]+\.?\d*)/);
                    if (match) {
                        const cleanNumber = match[1].replace(/[\s,]/g, '');
                        const balance = parseFloat(cleanNumber);
                        if (balance >= 0.01 && balance <= 10000000) {
                            // Only cache if not force refresh
                            if (!forceRefresh) {
                                balanceSync.lastUIBalance = balance;
                                moneyManagement.accountBalance = balance;
                            }
                            return balance;
                        }
                    }
                }
            } catch(e) {}
        }
        
        // If no balance found in DOM and not forcing refresh, return cached value
        if (!forceRefresh && moneyManagement.accountBalance > 0) {
            return moneyManagement.accountBalance;
        }
        
        return 0;
    }
    
    // Fetch balance from backend API (fallback)
    function fetchBackendBalance() {
        if (balanceSync.apiFailCount >= balanceSync.maxAPIFails) return;
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: CONFIG.API_URL + '/pocket-option/balance',
            headers: { 'Accept': 'application/json' },
            timeout: 5000,
            onload: function(res) {
                try {
                    if (res.status !== 200) {
                        balanceSync.apiFailCount++;
                        return;
                    }
                    const data = JSON.parse(res.responseText);
                    if (data.success && data.balance > 0) {
                        balanceSync.lastAPIBalance = data.balance;
                        balanceSync.apiFailCount = 0;
                        
                        // Only use API balance if UI balance seems stale
                        const uiAge = Date.now() - balanceSync.lastSyncTime;
                        if (uiAge > 10000 || balanceSync.lastUIBalance === 0) {
                            moneyManagement.accountBalance = data.balance;
                            recalculateBetSize();
                        }
                    }
                } catch(e) {
                    balanceSync.apiFailCount++;
                }
            },
            onerror: function() { balanceSync.apiFailCount++; }
        });
    }
    
    // Recalculate bet size from current live balance
    function recalculateBetSize() {
        const balance = moneyManagement.accountBalance;
        if (balance <= 0) return;
        
        const riskPct = moneyManagement.riskPercentage || 2;
        const newBase = Math.max(1, Math.round(balance * (riskPct / 100) * 100) / 100);
        
        // Only update base amount (don't override martingale step amount)
        if (Math.abs(newBase - moneyManagement.baseTradeAmount) > 0.1) {
            moneyManagement.baseTradeAmount = newBase;
            
            // If not in a martingale sequence, update current trade amount too
            if (!smartMartingale.enabled || smartMartingale.step === 0) {
                moneyManagement.currentTradeAmount = newBase;
                if (!martingaleEnabled || martingaleStep === 0) {
                    currentTradeAmount = newBase;
                }
            }
        }
    }
    
    // Balance sync loop - runs on an interval
    function startBalanceSync() {
        setInterval(() => {
            // Primary: UI scrape
            const uiBalance = detectAccountBalance();
            balanceSync.lastSyncTime = Date.now();
            
            if (uiBalance > 0) {
                recalculateBetSize();
            }
            
            // Fallback: backend API (every 3rd cycle to avoid spam)
            if (Date.now() % 3 === 0) {
                fetchBackendBalance();
            }
            
            // Update display
            updateMoneyManagementDisplay();
        }, balanceSync.syncIntervalMs);
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
        const invertState = smartAutoInvert.enabled ? (smartAutoInvert.invertActive ? 'INVERTED' : 'NORMAL') : 'OFF';
        log(`WIN +$${profit.toFixed(2)} | AUTO-INV: ${invertState}`);
        
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
        
        // Record premium result for backend learning
        recordPremiumResult(true);
        
        // Update smart auto-invert system
        updateSmartAutoInvertOnResult(true);
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
                
                const invertState = smartAutoInvert.enabled ? (smartAutoInvert.invertActive ? 'INVERTED' : 'NORMAL') : 'OFF';
                log(`LOSS -$${tradeAmount.toFixed(2)} | AUTO-INV: ${invertState}`);
                log(`Martingale Step ${smartMartingale.step}: $${nextAmount.toFixed(2)} to recover $${smartMartingale.totalLoss.toFixed(2)}`);
            } else {
                log(`MAX MARTINGALE STEPS (${smartMartingale.maxSteps}) - Total loss: $${smartMartingale.totalLoss.toFixed(2)}`);
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
                
                const invertState = smartAutoInvert.enabled ? (smartAutoInvert.invertActive ? 'INVERTED' : 'NORMAL') : 'OFF';
                log(`LOSS -$${tradeAmount.toFixed(2)} | AUTO-INV: ${invertState} | Martingale Step ${martingaleStep}: $${nextAmount.toFixed(2)}`);
            } else {
                log(`MAX MARTINGALE REACHED! Step ${martingaleStep}`);
                playStopSound();
            }
        } else {
            const invertState = smartAutoInvert.enabled ? (smartAutoInvert.invertActive ? 'INVERTED' : 'NORMAL') : 'OFF';
            log(`LOSS -$${tradeAmount.toFixed(2)} | AUTO-INV: ${invertState}`);
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
        
        // Record premium result for backend learning
        recordPremiumResult(false);
        
        // Update auto-invert (LOSS = toggle state)
        updateSmartAutoInvertOnResult(false);
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
        smartAutoInvert.invertActive = false;
        invertEnabled = false;
        GM_setValue('invertEnabled', false);
        GM_setValue('smartAutoInvertActive', false);
        updateInvertButton();
        updateMartingaleDisplay();
        log(`Martingale reset to $${martingaleBaseAmount}`);
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
            if (smartAutoInvert.enabled) {
                invertIndicator.textContent = smartAutoInvert.invertActive ? 'AI: INVERTED' : 'AI: NORMAL';
                invertIndicator.style.color = smartAutoInvert.invertActive ? '#f59e0b' : '#22c55e';
            } else {
                invertIndicator.textContent = '';
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
                manual_invert_active: smartAutoInvert.invertActive,
                martingale_step: martingaleStep,
                current_trade_amount: currentTradeAmount
            }),
            timeout: 5000,
            onload: function(res) {},
            onerror: function() {}
        });
    }
    
    // ===========================================
    // STRATEGY DROPDOWN LOADER - v8.0
    // ===========================================
    function loadStrategiesDropdown() {
        GM_xmlhttpRequest({
            method: 'GET',
            url: CONFIG.API_URL + '/strategies/available/5s',
            headers: { 'Accept': 'application/json' },
            timeout: 8000,
            onload: function(res) {
                try {
                    if (res.status !== 200) return;
                    const data = JSON.parse(res.responseText);
                    if (!data.success || !data.strategies) return;
                    
                    const select = document.getElementById('gpt-strategy-select');
                    if (!select) return;
                    
                    // Clear existing options except first
                    select.innerHTML = '<option value="default">All Strategies (Auto)</option>';
                    
                    data.strategies.forEach(s => {
                        if (s.id === 'default') return; // Already added
                        const opt = document.createElement('option');
                        opt.value = s.id;
                        opt.textContent = s.name + (s.win_rate ? ' (' + s.win_rate + ')' : '');
                        select.appendChild(opt);
                    });
                    
                    // Now load user's current selection
                    loadSelectedStrategy(select);
                    log('Strategies loaded: ' + data.strategies.length + ' available');
                } catch(e) {
                    console.error('[GPT] Load strategies error:', e);
                }
            },
            onerror: function() {}
        });
    }
    
    function loadSelectedStrategy(select) {
        GM_xmlhttpRequest({
            method: 'GET',
            url: CONFIG.API_URL + '/strategies/selected',
            headers: { 'Accept': 'application/json' },
            timeout: 5000,
            onload: function(res) {
                try {
                    if (res.status !== 200) return;
                    const data = JSON.parse(res.responseText);
                    if (!data.success || !data.selections) return;
                    
                    // Selections are {timeframe: strategy_id_string}
                    const sel5s = data.selections['5s'];
                    if (sel5s && typeof sel5s === 'string') {
                        selectedStrategy = sel5s;
                        if (select) select.value = selectedStrategy;
                        log('Active strategy: ' + selectedStrategy);
                    } else if (sel5s && sel5s.strategy_id) {
                        selectedStrategy = sel5s.strategy_id;
                        if (select) select.value = selectedStrategy;
                        log('Active strategy: ' + selectedStrategy);
                    }
                } catch(e) {}
            },
            onerror: function() {}
        });
    }
    
    function onStrategyChange(strategyId) {
        selectedStrategy = strategyId;
        GM_setValue('selectedStrategy', strategyId);
        log('Strategy changed to: ' + strategyId);
        
        // Save to backend
        GM_xmlhttpRequest({
            method: 'POST',
            url: CONFIG.API_URL + '/strategies/select',
            headers: { 
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            data: JSON.stringify({
                timeframe: '5s',
                strategy_id: strategyId
            }),
            timeout: 5000,
            onload: function(res) {
                try {
                    const data = JSON.parse(res.responseText);
                    if (data.success) {
                        log('Strategy saved: ' + strategyId);
                    }
                } catch(e) {}
            },
            onerror: function() {}
        });
    }

    // ===========================================
    // RECORD PREMIUM RESULT - v8.0
    // Sends WIN/LOSS data to backend learning system
    // ===========================================
    function recordPremiumResult(isWin) {
        const symbol = lastTradeInfo.symbol || getCurrentAsset() || 'UNKNOWN';
        const direction = lastTradeInfo.direction || 'CALL';
        const confidence = lastTradeInfo.confidence || 0;
        
        const normalizedSymbol = symbol.replace(/\s+/g, '').replace('/', '').toUpperCase();
        
        GM_xmlhttpRequest({
            method: 'POST',
            url: CONFIG.API_URL + '/signals/record-premium-result',
            headers: { 
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            data: JSON.stringify({
                symbol: normalizedSymbol,
                direction: direction,
                is_win: isWin,
                confidence: confidence
            }),
            timeout: 5000,
            onload: function(res) {
                try {
                    const data = JSON.parse(res.responseText);
                    if (data.success && data.updated_stats) {
                        const stats = data.updated_stats;
                        log(`Premium: ${normalizedSymbol} WR=${stats.asset_win_rate}% (${stats.asset_total_trades} trades) | Hour WR=${stats.hour_win_rate}%`);
                    }
                } catch(e) {}
            },
            onerror: function() {}
        });
    }

    // ===========================================
    // AUTO-INVERT v8.4 - Momentum & Trend Aware
    // After LOSS: checks local RSI/EMA + backend momentum
    // Only inverts if momentum has shifted (pullback/reversal)
    // If trend intact, stays in current direction
    // ===========================================
    function processSmartAutoInvert(signal) {
        // If auto-invert is enabled AND currently inverted, flip direction
        if (smartAutoInvert.enabled && smartAutoInvert.invertActive) {
            const original = signal.direction;
            signal.direction = (signal.direction === 'CALL') ? 'PUT' : 'CALL';
            signal._smartInverted = true;
            signal._originalDirection = original;
            log(`AUTO-INVERT: ${original} -> ${signal.direction} (inverted)`);
        }
        return signal;
    }
    
    // ===========================================
    // SMART AUTO-INVERT - v8.6.2
    // On LOSS: Stay on same asset + invert + retry immediately
    // On WIN: AI decides to ride trend OR proceed to next asset
    // ===========================================
    
    // Track last trade result for cycle integration
    let lastTradeResult = {
        isWin: null,
        timestamp: 0,
        asset: '',
        direction: '',
        wasInverted: false,
        shouldRetry: false,       // True if LOSS + should stay & invert
        shouldRideTrend: false,   // True if WIN + AI suggests continuing
        consecutiveWins: 0,       // Track win streak for trend riding
        consecutiveLosses: 0      // Track loss streak for recovery
    };
    
    function updateSmartAutoInvertOnResult(isWin) {
        if (!smartAutoInvert.enabled) return;
        
        // Store the result
        lastTradeResult.isWin = isWin;
        lastTradeResult.timestamp = Date.now();
        lastTradeResult.asset = lastTradeInfo.symbol || '';
        lastTradeResult.direction = lastTradeInfo.direction || '';
        lastTradeResult.wasInverted = smartAutoInvert.invertActive;
        
        if (isWin) {
            // WIN: Track streak and turn off invert
            lastTradeResult.consecutiveWins++;
            lastTradeResult.consecutiveLosses = 0;
            lastTradeResult.shouldRetry = false;
            
            if (smartAutoInvert.invertActive) {
                smartAutoInvert.invertActive = false;
                invertEnabled = false;
                GM_setValue('invertEnabled', false);
                GM_setValue('smartAutoInvertActive', false);
                log(`AUTO-INVERT: ✅ WIN while inverted → Back to NORMAL`);
            } else {
                log(`AUTO-INVERT: ✅ WIN (normal) → Stay NORMAL`);
            }
            
            // AI Decision: Should we ride the trend?
            // If we have 2+ consecutive wins, suggest riding
            if (lastTradeResult.consecutiveWins >= 2) {
                lastTradeResult.shouldRideTrend = true;
                log(`AUTO-INVERT: 🚀 ${lastTradeResult.consecutiveWins} wins in a row - AI suggests RIDING TREND`);
            } else {
                // Single win after losses - might be reversal, don't ride yet
                lastTradeResult.shouldRideTrend = false;
            }
        } else {
            // LOSS: Track streak and turn ON invert
            lastTradeResult.consecutiveLosses++;
            lastTradeResult.consecutiveWins = 0;
            lastTradeResult.shouldRideTrend = false;
            
            if (!smartAutoInvert.invertActive) {
                smartAutoInvert.invertActive = true;
                invertEnabled = true;
                GM_setValue('invertEnabled', true);
                GM_setValue('smartAutoInvertActive', true);
                log(`AUTO-INVERT: ❌ LOSS (normal) → Switching to INVERTED`);
            } else {
                // Already inverted and still losing
                log(`AUTO-INVERT: ❌ LOSS (inverted) → Staying INVERTED (attempt ${lastTradeResult.consecutiveLosses})`);
            }
            
            // Signal that we should retry on same asset (for CYCLE mode)
            lastTradeResult.shouldRetry = true;
            
            // Safety: After 5 consecutive inverted losses, reset and move on
            if (lastTradeResult.consecutiveLosses >= 5) {
                log(`AUTO-INVERT: ⚠️ 5 consecutive losses - resetting invert and moving to next asset`);
                smartAutoInvert.invertActive = false;
                lastTradeResult.shouldRetry = false;
                lastTradeResult.consecutiveLosses = 0;
                GM_setValue('smartAutoInvertActive', false);
            }
        }
        
        // v8.6.4: SAVE STATE for persistence across refresh
        saveAutoInvertState();
        
        updateInvertDisplay();
    }
    
    // Save auto-invert state to persist across page refresh
    function saveAutoInvertState() {
        GM_setValue('smartAutoInvertEnabled', smartAutoInvert.enabled);
        GM_setValue('smartAutoInvertActive', smartAutoInvert.invertActive);
        GM_setValue('invertEnabled', invertEnabled);
        
        // Save lastTradeResult state
        const stateToSave = {
            isWin: lastTradeResult.isWin,
            consecutiveWins: lastTradeResult.consecutiveWins,
            consecutiveLosses: lastTradeResult.consecutiveLosses,
            wasInverted: lastTradeResult.wasInverted,
            timestamp: lastTradeResult.timestamp
        };
        GM_setValue('lastTradeResultState', JSON.stringify(stateToSave));
        
        log(`STATE SAVED: Invert=${smartAutoInvert.invertActive}, Wins=${lastTradeResult.consecutiveWins}, Losses=${lastTradeResult.consecutiveLosses}`);
    }
    
    function updateInvertDisplay() {
        const invertIndicator = document.getElementById('gpt-invert-indicator');
        if (invertIndicator) {
            if (smartAutoInvert.enabled) {
                invertIndicator.textContent = smartAutoInvert.invertActive ? 'AI: INVERTED' : 'AI: NORMAL';
                invertIndicator.style.color = smartAutoInvert.invertActive ? '#f59e0b' : '#22c55e';
            } else {
                invertIndicator.textContent = invertEnabled ? 'MANUAL INVERT' : '';
            }
        }
    }

    // ===========================================
    // TRADE OUTCOME DETECTION SYSTEM - v8.3
    // Uses balance change monitoring + DOM scanning
    // to reliably detect wins and losses
    // ===========================================
    function setupOutcomeDetection() {
        log('OUTCOME: Setting up simplified trade result detection...');
        log('OUTCOME: Will poll balance + DOM after trades expire');
    }
    
    // Check if element is likely a balance display
    function isBalanceElement(el) {
        const classes = (el.className || '').toLowerCase();
        const id = (el.id || '').toLowerCase();
        return classes.includes('balance') || 
               id.includes('balance') || 
               el.matches('[data-balance], [class*="account"], [class*="money"]');
    }
    
    // Detect result from a specific element
    function detectResultFromElement(el) {
        const text = (el.textContent || '').toLowerCase();
        const classes = (el.className || '').toLowerCase();
        const style = el.getAttribute('style') || '';
        
        // Check classes
        if (classes.includes('win') || classes.includes('success') || classes.includes('profit')) return true;
        if (classes.includes('loss') || classes.includes('lose') || classes.includes('fail')) return false;
        
        // Check text
        if (text.match(/\+\s*\$?\s*[\d,.]+/)) return true;
        if (text.match(/-\s*\$?\s*[\d,.]+/)) return false;
        
        // Check colors (green = win, red = loss)
        if (style.includes('green') || style.includes('#0f0') || style.includes('rgb(0, 255')) return true;
        if (style.includes('red') || style.includes('#f00') || style.includes('rgb(255, 0')) return false;
        
        return null;
    }
    
    // Handle when a trade result is detected (from any method)
    function handleTradeResultDetected(isWin, source) {
        if (!audioDetection.pendingTrade) {
            log(`OUTCOME: Ignoring ${source} detection - no pending trade`);
            return;
        }
        
        const elapsed = Math.round((Date.now() - audioDetection.tradeOpenedAt) / 1000);
        const expectedExpiry = audioDetection.tradeExpirySeconds || 60;
        const latencyOffset = CONFIG.RESULT_LATENCY_OFFSET || 0;
        
        // v8.5.2 FIX: More lenient timing - allow detection any time after 3 seconds
        // The latency offset adjusts how early we accept results relative to expiry
        // With offset=0 and expiry=30, minElapsed = max(3, 30-10+0) = 20s
        // With offset=-5 and expiry=30, minElapsed = max(3, 30-10-5) = 15s
        const minElapsed = Math.max(3, expectedExpiry - 10 + latencyOffset);
        
        // ALWAYS log what we're seeing for debugging
        log(`OUTCOME CHECK: ${source} at ${elapsed}s, expiry=${expectedExpiry}s, min=${minElapsed}s, offset=${latencyOffset}s`);
        
        if (elapsed < minElapsed) {
            log(`OUTCOME: Too early (${elapsed}s < ${minElapsed}s) - waiting...`);
            return;
        }
        
        // ACCEPT THE RESULT!
        audioDetection.pendingTrade = false;
        audioDetection.lastDetectionTime = Date.now();
        
        log(`✅ TRADE RESULT [${source}]: ${isWin ? 'WIN' : 'LOSS'} after ${elapsed}s`);
        
        // Record for AI/ML training (non-blocking)
        try {
            recordTradeForML(isWin, elapsed, expectedExpiry, source);
        } catch(e) {
            log(`ML record error: ${e.message}`);
        }
        
        // UPDATE WIN/LOSS STATS - this is critical!
        handleAutoDetectedResult(isWin);
    }
    
    // Record trade outcome for AI/ML training and backtesting
    function recordTradeForML(isWin, elapsed, expiry, detectionSource) {
        if (!CONFIG.COLLECT_TRAINING_DATA) return;
        
        const tradeData = {
            timestamp: new Date().toISOString(),
            symbol: lastTradeInfo.symbol || getCurrentAsset() || 'UNKNOWN',
            direction: lastTradeInfo.direction || 'UNKNOWN',
            confidence: lastTradeInfo.confidence || 0,
            outcome: isWin ? 'WIN' : 'LOSS',
            expiry_seconds: expiry,
            actual_elapsed: elapsed,
            detection_source: detectionSource,
            latency_offset: CONFIG.RESULT_LATENCY_OFFSET,
            indicators: window.lastTradeIndicators || {},
            balance_before: audioDetection.balanceBeforeTrade,
            balance_after: detectAccountBalance(),
            invert_active: smartAutoInvert.invertActive,
            strategy: window.lastTradeStrategy || 'unknown'
        };
        
        // Store locally for backtest analysis
        if (!window.mlTradeHistory) window.mlTradeHistory = [];
        window.mlTradeHistory.push(tradeData);
        
        // Keep only last N trades for local analysis
        if (window.mlTradeHistory.length > CONFIG.BACKTEST_WINDOW) {
            window.mlTradeHistory = window.mlTradeHistory.slice(-CONFIG.BACKTEST_WINDOW);
        }
        
        // Send to backend for model training
        try {
            GM_xmlhttpRequest({
                method: 'POST',
                url: CONFIG.API_URL + '/ml/record-trade',
                headers: { 'Content-Type': 'application/json' },
                data: JSON.stringify(tradeData),
                timeout: 5000,
                onload: function(res) {
                    if (res.status === 200) {
                        try {
                            const data = JSON.parse(res.responseText);
                            if (data.model_update_available) {
                                log(`ML: Model update available - ${data.update_reason}`);
                                if (CONFIG.ADAPTIVE_MODEL_UPDATE) {
                                    requestModelUpdate();
                                }
                            }
                        } catch(e) {}
                    }
                },
                onerror: function() {}
            });
        } catch(e) {}
        
        // Update local performance metrics
        updateLocalBacktest(tradeData);
    }
    
    // Local backtesting and performance analysis
    function updateLocalBacktest(trade) {
        if (!window.localBacktest) {
            window.localBacktest = {
                totalTrades: 0,
                wins: 0,
                losses: 0,
                bySymbol: {},
                byStrategy: {},
                byConfidenceRange: { low: {w:0,l:0}, medium: {w:0,l:0}, high: {w:0,l:0} },
                recentPerformance: [] // Last 20 trades for adaptive adjustments
            };
        }
        
        const bt = window.localBacktest;
        bt.totalTrades++;
        
        if (trade.outcome === 'WIN') {
            bt.wins++;
        } else {
            bt.losses++;
        }
        
        // By symbol
        if (!bt.bySymbol[trade.symbol]) bt.bySymbol[trade.symbol] = { w: 0, l: 0 };
        if (trade.outcome === 'WIN') bt.bySymbol[trade.symbol].w++;
        else bt.bySymbol[trade.symbol].l++;
        
        // By confidence range
        const confRange = trade.confidence < 70 ? 'low' : trade.confidence < 80 ? 'medium' : 'high';
        if (trade.outcome === 'WIN') bt.byConfidenceRange[confRange].w++;
        else bt.byConfidenceRange[confRange].l++;
        
        // Recent performance (for adaptive logic)
        bt.recentPerformance.push({ outcome: trade.outcome, ts: Date.now() });
        if (bt.recentPerformance.length > 20) bt.recentPerformance.shift();
        
        // Log performance summary every 10 trades
        if (bt.totalTrades % 10 === 0) {
            const winRate = ((bt.wins / bt.totalTrades) * 100).toFixed(1);
            log(`📊 BACKTEST: ${bt.wins}W/${bt.losses}L (${winRate}% WR) over ${bt.totalTrades} trades`);
            
            // Check for adaptive adjustments
            checkAdaptiveAdjustments();
        }
    }
    
    // Request updated model parameters from backend
    function requestModelUpdate() {
        GM_xmlhttpRequest({
            method: 'POST',
            url: CONFIG.API_URL + '/ml/request-update',
            headers: { 'Content-Type': 'application/json' },
            data: JSON.stringify({
                recent_trades: window.mlTradeHistory?.slice(-20) || [],
                current_settings: {
                    min_confidence: CONFIG.MIN_CONFIDENCE,
                    latency_offset: CONFIG.RESULT_LATENCY_OFFSET
                }
            }),
            timeout: 10000,
            onload: function(res) {
                try {
                    const data = JSON.parse(res.responseText);
                    if (data.success && data.adjustments) {
                        applyModelAdjustments(data.adjustments);
                    }
                } catch(e) {}
            }
        });
    }
    
    // Apply AI-recommended adjustments
    function applyModelAdjustments(adjustments) {
        if (adjustments.min_confidence !== undefined) {
            const oldConf = CONFIG.MIN_CONFIDENCE;
            CONFIG.MIN_CONFIDENCE = Math.max(50, Math.min(90, adjustments.min_confidence));
            log(`ML ADJUST: Min confidence ${oldConf} → ${CONFIG.MIN_CONFIDENCE}`);
        }
        
        if (adjustments.latency_offset !== undefined) {
            const oldOffset = CONFIG.RESULT_LATENCY_OFFSET;
            CONFIG.RESULT_LATENCY_OFFSET = Math.max(-5, Math.min(5, adjustments.latency_offset));
            log(`ML ADJUST: Latency offset ${oldOffset} → ${CONFIG.RESULT_LATENCY_OFFSET}`);
        }
        
        if (adjustments.strategy_weights) {
            window.strategyWeights = adjustments.strategy_weights;
            log(`ML ADJUST: Strategy weights updated`);
        }
    }
    
    // Check if we need to make adaptive adjustments locally
    function checkAdaptiveAdjustments() {
        const bt = window.localBacktest;
        if (!bt || bt.recentPerformance.length < 10) return;
        
        // Calculate recent win rate
        const recent = bt.recentPerformance.slice(-10);
        const recentWins = recent.filter(t => t.outcome === 'WIN').length;
        const recentWR = (recentWins / 10) * 100;
        
        // If recent performance is bad (<40%), suggest increasing confidence threshold
        if (recentWR < 40) {
            log(`⚠️ ADAPTIVE: Poor recent performance (${recentWR}% WR) - consider increasing MIN_CONFIDENCE`);
        }
        
        // If recent performance is excellent (>70%), can be more aggressive
        if (recentWR > 70) {
            log(`✅ ADAPTIVE: Strong recent performance (${recentWR}% WR) - strategy working well`);
        }
    }
    
    // Check balance change triggered by mutation
    function checkBalanceChangeFromMutation() {
        if (!audioDetection.pendingTrade) return;
        
        // v8.6.2 FIX: Don't use mutation-based detection - it conflicts with the 
        // post-bet balance comparison system. The mutation observer detects the 
        // bet deduction as a "loss" before the trade even expires.
        // We rely ONLY on startOutcomePolling() for outcome detection.
        return;
        
        const currentBalance = detectAccountBalance();
        const balanceBefore = audioDetection.balanceBeforeTrade;
        
        if (balanceBefore > 0 && currentBalance > 0) {
            const diff = currentBalance - balanceBefore;
            
            if (Math.abs(diff) > 0.01) {
                const isWin = diff > 0;
                log(`OBSERVER: Balance change detected: $${diff > 0 ? '+' : ''}${diff.toFixed(2)}`);
                handleTradeResultDetected(isWin, 'balance-mutation');
            }
        }
    }
    
    // Called when a trade is placed - starts monitoring for the result
    // v8.7.2: Uses configurable timing settings
    function markTradePending(expirySeconds = 60) {
        audioDetection.pendingTrade = true;
        audioDetection.tradeOpenedAt = Date.now();
        audioDetection.tradeExpirySeconds = expirySeconds;
        audioDetection.tradeAmount = moneyManagement.currentTradeAmount || currentTradeAmount || 1;
        
        // Capture balance BEFORE trade
        if (audioDetection.balanceBeforeTrade <= 0) {
            audioDetection.balanceBeforeTrade = detectAccountBalance(true);
        }
        
        log(`════════════════════════════════`);
        log(`   TRADE PLACED`);
        log(`════════════════════════════════`);
        log(`Expiry: ${expirySeconds}s`);
        log(`Bet Amount: $${audioDetection.tradeAmount.toFixed(2)}`);
        log(`Balance Before: $${audioDetection.balanceBeforeTrade.toFixed(2)}`);
        
        // v8.7.2: Use configurable delay for bet deduction
        const betDeductionDelay = CONFIG.BET_DEDUCTION_DELAY || 2000;
        
        setTimeout(() => {
            if (!audioDetection.pendingTrade) return;
            
            // Capture balance AFTER bet is deducted
            audioDetection.balanceAfterBet = detectAccountBalance(true);
            log(`Balance AFTER BET: $${audioDetection.balanceAfterBet.toFixed(2)} (waited ${betDeductionDelay}ms)`);
            log(`════════════════════════════════`);
            
            // Now wait for trade to expire
            startOutcomePolling(expirySeconds);
        }, betDeductionDelay);
    }
    
    // v8.7.2: Improved outcome polling with configurable timing
    function startOutcomePolling(expirySeconds = 60) {
        const latencyOffset = CONFIG.RESULT_LATENCY_OFFSET || 0;
        const postExpiryBuffer = CONFIG.POST_EXPIRY_BUFFER || 3000;
        
        // Total wait: expiry + buffer + latency offset
        const waitMs = (expirySeconds * 1000) + postExpiryBuffer + (latencyOffset * 1000);
        
        log(`════════════════════════════════`);
        log(`TIMING SYNC:`);
        log(`  Expiry: ${expirySeconds}s`);
        log(`  Buffer: ${postExpiryBuffer}ms`);
        log(`  Latency Offset: ${latencyOffset}s`);
        log(`  Total Wait: ${Math.round(waitMs/1000)}s`);
        log(`════════════════════════════════`);
        
        setTimeout(() => {
            if (!audioDetection.pendingTrade) {
                log('OUTCOME: Trade already resolved');
                return;
            }
            
            const balanceAfterBet = audioDetection.balanceAfterBet;
            
            if (!balanceAfterBet || balanceAfterBet <= 0) {
                log('OUTCOME: No post-bet balance recorded. Use +W/-L buttons.');
                audioDetection.pendingTrade = false;
                return;
            }
            
            log(`OUTCOME: Trade expired. Checking balance...`);
            log(`OUTCOME: Post-bet balance was: $${balanceAfterBet.toFixed(2)}`);
            
            // Use configurable polling settings
            const pollInterval = CONFIG.BALANCE_POLL_INTERVAL || 500;
            const maxPolls = CONFIG.MAX_BALANCE_POLLS || 20;
            const requiredStableChecks = CONFIG.BALANCE_STABILITY_CHECKS || 2;
            
            let pollCount = 0;
            let lastBalance = 0;
            let stableCount = 0;
            
            const poller = setInterval(() => {
                pollCount++;
                
                if (!audioDetection.pendingTrade) {
                    clearInterval(poller);
                    return;
                }
                
                if (pollCount > maxPolls) {
                    clearInterval(poller);
                    audioDetection.pendingTrade = false;
                    log(`OUTCOME: Timeout after ${pollCount} polls. Use +W or -L buttons.`);
                    return;
                }
                
                const currentBalance = detectAccountBalance(true);
                const change = currentBalance - balanceAfterBet;
                
                log(`POLL #${pollCount}: Balance=$${currentBalance.toFixed(2)}, Change=$${change >= 0 ? '+' : ''}${change.toFixed(2)}`);
                
                // Check if balance is stable
                if (Math.abs(currentBalance - lastBalance) < 0.01) {
                    stableCount++;
                } else {
                    stableCount = 0;
                }
                lastBalance = currentBalance;
                
                // Need balance to be stable for required checks before deciding
                if (stableCount >= requiredStableChecks) {
                    clearInterval(poller);
                    audioDetection.pendingTrade = false;
                    
                    const elapsed = Math.round((Date.now() - audioDetection.tradeOpenedAt) / 1000);
                    
                    // WIN/LOSS LOGIC:
                    // - Balance increased → WIN (payout received)
                    // - Balance unchanged → LOSS (no payout)
                    // - Balance decreased → LOSS
                    
                    let isWin = false;
                    let resultReason = '';
                    
                    if (change > 0.01) {
                        isWin = true;
                        resultReason = `Balance INCREASED by $${change.toFixed(2)} (payout received)`;
                    } else if (Math.abs(change) < 0.01) {
                        isWin = false;
                        resultReason = `Balance UNCHANGED (no payout = loss)`;
                    } else {
                        isWin = false;
                        resultReason = `Balance DECREASED by $${Math.abs(change).toFixed(2)} (loss)`;
                    }
                    
                    log(`════════════════════════════════`);
                    log(`   TRADE RESULT: ${isWin ? '✅ WIN' : '❌ LOSS'}`);
                    log(`════════════════════════════════`);
                    log(`Post-Bet:  $${balanceAfterBet.toFixed(2)}`);
                    log(`Current:   $${currentBalance.toFixed(2)}`);
                    log(`Change:    $${change >= 0 ? '+' : ''}${change.toFixed(2)}`);
                    log(`Reason:    ${resultReason}`);
                    log(`Duration:  ${elapsed}s`);
                    log(`════════════════════════════════`);
                    
                    // Record for ML
                    try { recordTradeForML(isWin, elapsed, expirySeconds, 'balance'); } catch(e) {}
                    
                    // Update stats
                    handleAutoDetectedResult(isWin);
                    return;
                }
            }, pollInterval);
        }, waitMs);
    }
    
    // Actively scan the DOM for trade result indicators
    function scanDOMForResult() {
        // Look for recently appeared deal result elements
        // PO typically shows results in deal history or popup notifications
        
        // First priority: Check the MOST RECENT closed deal in deals list
        try {
            const closedDealsSelectors = [
                '.deals-list .deals-item:first-child',
                '[class*="closed-deals"] [class*="item"]:first-child',
                '[class*="deals"] [class*="closed"]:first-child',
                '.closed-deals-list > div:first-child',
            ];
            
            for (const sel of closedDealsSelectors) {
                const deal = document.querySelector(sel);
                if (!deal || !deal.offsetParent) continue;
                
                // Check if this deal was created recently (within last minute)
                const text = (deal.textContent || '').trim();
                const className = (deal.className || '').toLowerCase();
                
                // Look for profit indicator
                const profitEl = deal.querySelector('[class*="profit"], [class*="payout"], [class*="result"]');
                if (profitEl) {
                    const profitText = profitEl.textContent || '';
                    const profitClass = (profitEl.className || '').toLowerCase();
                    
                    // Green/profit class or + sign = WIN
                    if (profitClass.includes('success') || profitClass.includes('profit') || profitClass.includes('win') || profitClass.includes('green')) {
                        log(`DOM: Found winning deal element`);
                        return true;
                    }
                    // Red/loss class or - sign = LOSS
                    if (profitClass.includes('fail') || profitClass.includes('loss') || profitClass.includes('lose') || profitClass.includes('red')) {
                        log(`DOM: Found losing deal element`);
                        return false;
                    }
                    // Check text for +/- amount
                    if (profitText.match(/^\s*\+/)) return true;
                    if (profitText.match(/^\s*-/)) return false;
                }
                
                // Check entire deal element
                if (className.includes('success') || className.includes('win') || className.includes('profit')) {
                    return true;
                }
                if (className.includes('fail') || className.includes('loss') || className.includes('lose')) {
                    return false;
                }
            }
        } catch(e) {}
        
        // Second priority: Check for popup notifications
        try {
            const popupSelectors = [
                '[class*="notification"][class*="deal"]',
                '[class*="trade-result"]',
                '[class*="popup"][class*="result"]',
            ];
            
            for (const sel of popupSelectors) {
                const popup = document.querySelector(sel);
                if (!popup || !popup.offsetParent) continue;
                
                const text = (popup.textContent || '').trim();
                const className = (popup.className || '').toLowerCase();
                
                if (className.includes('success') || className.includes('win') || text.match(/\+\s*\$?\s*[\d,.]+/)) {
                    log(`DOM: Found win notification popup`);
                    return true;
                }
                if (className.includes('fail') || className.includes('loss') || text.match(/-\s*\$?\s*[\d,.]+/)) {
                    log(`DOM: Found loss notification popup`);
                    return false;
                }
            }
        } catch(e) {}
        
        return null; // No result found yet
    }
    
    function handleAutoDetectedResult(isWin) {
        // v8.6.2 FIX: Add timestamp guard to prevent double-counting
        const now = Date.now();
        if (window._lastAutoResultTime && (now - window._lastAutoResultTime) < 3000) {
            log(`⚠️ BLOCKED: Duplicate result detection (${now - window._lastAutoResultTime}ms since last)`);
            return;
        }
        window._lastAutoResultTime = now;
        
        // Trigger the same flow as manual +W/-L buttons
        if (isWin) {
            handleManualWin();
        } else {
            handleManualLoss();
        }
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
        
        // Reset auto-invert state
        lastTradeResult.isWin = null;
        lastTradeResult.consecutiveWins = 0;
        lastTradeResult.consecutiveLosses = 0;
        lastTradeResult.shouldRetry = false;
        lastTradeResult.shouldRideTrend = false;
        smartAutoInvert.invertActive = false;
        invertEnabled = false;
        
        // Save reset state
        saveAutoInvertState();
        GM_setValue('winLossStats', JSON.stringify(winLossStats));
        
        resetMartingale();
        resetSmartMartingale();
        updateWinLossDisplay();
        updateMoneyManagementDisplay();
        updateInvertDisplay();
        syncStatsToBackend();
        log('📊 All stats reset (including Auto-Invert state)');
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
    // UI PANEL - v7.3.0 REDESIGNED
    // Clean, modern, organized layout
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
                /* ============================================
                   ELITE POCKET OPTION BOT v8.0
                   ============================================ */
                #gpt-panel {
                    position: fixed !important;
                    bottom: 15px;
                    left: 15px;
                    background: linear-gradient(145deg, rgba(15,15,30,0.98), rgba(25,25,45,0.98)) !important;
                    border: 1px solid rgba(124,58,237,0.6) !important;
                    border-radius: 12px !important;
                    padding: 0 !important;
                    z-index: 2147483647 !important;
                    font-family: 'Segoe UI', system-ui, sans-serif !important;
                    font-size: 11px !important;
                    color: #e2e8f0 !important;
                    width: 280px !important;
                    height: auto !important;
                    max-height: 90vh !important;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05) !important;
                    overflow: visible !important;
                    transition: width 0.3s ease, border-radius 0.3s ease !important;
                    touch-action: none !important;
                    user-select: none !important;
                    -webkit-user-select: none !important;
                    resize: none !important;
                }
                #gpt-panel.minimized { 
                    width: 110px; 
                    padding: 0;
                }
                #gpt-panel.minimized .gpt-body { display: none; }
                #gpt-panel.minimized .gpt-header { border-radius: 12px; cursor: pointer; }
                #gpt-panel.minimized .gpt-version { display: none; }
                #gpt-panel.minimized .gpt-minimize-btn { 
                    background: rgba(34,197,94,0.8); 
                    font-weight: bold;
                }
                
                /* Header */
                .gpt-header {
                    background: linear-gradient(90deg, #7c3aed, #6366f1);
                    padding: 8px 12px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    cursor: move;
                    user-select: none;
                }
                .gpt-header-left {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .gpt-logo {
                    font-weight: 700;
                    font-size: 13px;
                    color: white;
                    letter-spacing: 0.5px;
                }
                .gpt-version {
                    font-size: 9px;
                    color: rgba(255,255,255,0.7);
                    background: rgba(0,0,0,0.2);
                    padding: 2px 5px;
                    border-radius: 4px;
                }
                .gpt-status-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: #ef4444;
                    box-shadow: 0 0 6px #ef4444;
                    transition: all 0.3s;
                }
                .gpt-status-dot.connected { background: #22c55e; box-shadow: 0 0 6px #22c55e; }
                .gpt-status-dot.trading { background: #f59e0b; box-shadow: 0 0 8px #f59e0b; animation: gptPulse 0.5s infinite; }
                .gpt-status-dot.error { background: #ef4444; box-shadow: 0 0 6px #ef4444; }
                @keyframes gptPulse { 50% { opacity: 0.4; transform: scale(1.2); } }
                
                .gpt-minimize-btn {
                    background: rgba(255,255,255,0.15);
                    border: none;
                    color: white;
                    width: 22px;
                    height: 22px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: background 0.2s;
                }
                .gpt-minimize-btn:hover { background: rgba(255,255,255,0.25); }
                
                /* Body */
                .gpt-body { padding: 10px; }
                
                /* Signal Display */
                .gpt-signal-box {
                    background: rgba(0,0,0,0.3);
                    border-radius: 8px;
                    padding: 10px;
                    margin-bottom: 10px;
                    text-align: center;
                }
                .gpt-signal-label { font-size: 9px; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase; }
                .gpt-signal-value {
                    font-size: 18px;
                    font-weight: 700;
                    padding: 4px 16px;
                    border-radius: 6px;
                    display: inline-block;
                }
                .gpt-signal-value.call { background: linear-gradient(135deg, #22c55e, #16a34a); color: white; }
                .gpt-signal-value.put { background: linear-gradient(135deg, #ef4444, #dc2626); color: white; }
                .gpt-signal-value.wait { background: rgba(71,85,105,0.5); color: #94a3b8; }
                
                /* Button Groups */
                .gpt-btn-row {
                    display: flex;
                    gap: 6px;
                    margin-bottom: 8px;
                }
                .gpt-btn {
                    flex: 1;
                    padding: 8px 4px;
                    border: none;
                    border-radius: 6px;
                    font-size: 10px;
                    font-weight: 600;
                    cursor: pointer;
                    text-transform: uppercase;
                    transition: all 0.2s;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 2px;
                }
                .gpt-btn:hover { transform: translateY(-1px); filter: brightness(1.1); }
                .gpt-btn:active { transform: translateY(0); }
                
                .gpt-btn-icon { font-size: 14px; }
                
                .gpt-btn-auto { background: #475569; color: white; }
                .gpt-btn-auto.active { background: linear-gradient(135deg, #22c55e, #16a34a); }
                .gpt-btn-scan { background: #475569; color: white; }
                .gpt-btn-scan.active { background: linear-gradient(135deg, #3b82f6, #2563eb); }
                .gpt-btn-go { background: linear-gradient(135deg, #8b5cf6, #7c3aed); color: white; }
                .gpt-btn-inv { background: #475569; color: white; }
                .gpt-btn-inv.active { background: linear-gradient(135deg, #f59e0b, #d97706); }
                .gpt-btn-cycle { background: #475569; color: white; }
                .gpt-btn-cycle.active { background: linear-gradient(135deg, #38bdf8, #0284c7); animation: gpt-cycle-pulse 2s ease-in-out infinite; }
                @keyframes gpt-cycle-pulse { 0%,100%{opacity:1} 50%{opacity:0.7} }
                .gpt-btn-log { background: #475569; color: white; }
                .gpt-btn-log.active { background: linear-gradient(135deg, #6366f1, #4f46e5); }
                
                /* Stats Row */
                .gpt-stats-row {
                    display: flex;
                    gap: 8px;
                    margin-bottom: 8px;
                }
                .gpt-stat-box {
                    flex: 1;
                    background: rgba(0,0,0,0.2);
                    border-radius: 6px;
                    padding: 6px 8px;
                    text-align: center;
                }
                .gpt-stat-label { font-size: 8px; color: #64748b; text-transform: uppercase; }
                .gpt-stat-value { font-size: 14px; font-weight: 700; }
                .gpt-stat-value.win { color: #22c55e; }
                .gpt-stat-value.loss { color: #ef4444; }
                .gpt-stat-value.profit { color: #a78bfa; }
                
                /* Settings Row */
                .gpt-settings-row {
                    display: flex;
                    gap: 8px;
                    align-items: center;
                    background: rgba(0,0,0,0.2);
                    border-radius: 6px;
                    padding: 8px;
                    margin-bottom: 8px;
                }
                .gpt-input-group {
                    display: flex;
                    align-items: center;
                    gap: 4px;
                }
                .gpt-input-label { font-size: 9px; color: #94a3b8; }
                .gpt-input {
                    background: rgba(0,0,0,0.4);
                    border: 1px solid rgba(124,58,237,0.3);
                    border-radius: 4px;
                    color: white;
                    width: 50px;
                    font-size: 11px;
                    padding: 4px 6px;
                    text-align: center;
                }
                .gpt-input:focus { outline: none; border-color: #7c3aed; }
                
                /* Win/Loss Buttons */
                .gpt-result-btns {
                    display: flex;
                    gap: 6px;
                }
                .gpt-result-btn {
                    flex: 1;
                    padding: 6px;
                    border: none;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 600;
                    cursor: pointer;
                }
                .gpt-result-btn.win { background: rgba(34,197,94,0.2); color: #22c55e; border: 1px solid rgba(34,197,94,0.3); }
                .gpt-result-btn.loss { background: rgba(239,68,68,0.2); color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }
                .gpt-result-btn:hover { filter: brightness(1.2); }
                
                /* Status Log */
                .gpt-log-bar {
                    background: rgba(0,0,0,0.3);
                    border-radius: 4px;
                    padding: 6px 8px;
                    font-size: 9px;
                    color: #22c55e;
                    font-family: 'Consolas', monospace;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                
                /* Console Window */
                #gpt-console-window {
                    position: fixed;
                    bottom: 60px;
                    left: 15px;
                    width: 420px;
                    height: 280px;
                    background: rgba(10,10,20,0.98);
                    border: 1px solid rgba(124,58,237,0.5);
                    border-radius: 12px;
                    z-index: 999998;
                    display: none;
                    font-family: 'Consolas', 'Monaco', monospace;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
                    overflow: hidden;
                }
                #gpt-console-header {
                    background: linear-gradient(90deg, #7c3aed, #6366f1);
                    padding: 8px 12px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    cursor: move;
                }
                #gpt-console-header span { font-weight: 600; color: white; font-size: 11px; }
                #gpt-console-close { 
                    background: rgba(255,255,255,0.15); 
                    border: none; 
                    color: white; 
                    width: 22px;
                    height: 22px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 12px;
                }
                #gpt-console-close:hover { background: rgba(255,255,255,0.25); }
                #gpt-console-content {
                    padding: 10px;
                    height: calc(100% - 40px);
                    overflow-y: auto;
                    font-size: 10px;
                    line-height: 1.5;
                    color: #94a3b8;
                }
                #gpt-console-content::-webkit-scrollbar { width: 6px; }
                #gpt-console-content::-webkit-scrollbar-thumb { background: #7c3aed; border-radius: 3px; }
                #gpt-console-content .log-line { margin-bottom: 2px; }
                #gpt-console-content .log-line.success { color: #22c55e; }
                #gpt-console-content .log-line.error { color: #ef4444; }
                #gpt-console-content .log-line.warning { color: #f59e0b; }
                #gpt-console-content .log-line.info { color: #3b82f6; }
            </style>
            
            <!-- Header -->
            <div class="gpt-header" id="gpt-drag">
                <div class="gpt-header-left">
                    <div class="gpt-status-dot" id="gpt-dot"></div>
                    <span class="gpt-logo">GPT Bot</span>
                    <span class="gpt-version">v8.6.1</span>
                </div>
                <button class="gpt-minimize-btn" id="gpt-minimize">−</button>
            </div>
            
            <!-- Body -->
            <div class="gpt-body">
                <!-- Signal Display -->
                <div class="gpt-signal-box">
                    <div class="gpt-signal-label">Current Signal</div>
                    <div class="gpt-signal-value wait" id="gpt-signal">WAITING</div>
                </div>
                
                <!-- Strategy Selector -->
                <div class="gpt-settings-row" style="margin-bottom:8px; padding:6px 8px;">
                    <span class="gpt-input-label" style="white-space:nowrap;">Strategy:</span>
                    <select id="gpt-strategy-select" class="gpt-input" style="width:100%; text-align:left; font-size:10px; padding:4px;">
                        <option value="default">All Strategies</option>
                    </select>
                </div>
                
                <!-- Main Control Buttons -->
                <div class="gpt-btn-row">
                    <button class="gpt-btn gpt-btn-auto" id="gpt-auto">
                        <span class="gpt-btn-icon">📡</span>
                        <span>AUTO</span>
                    </button>
                    <button class="gpt-btn gpt-btn-scan" id="gpt-scan">
                        <span class="gpt-btn-icon">🔍</span>
                        <span>SCAN</span>
                    </button>
                    <button class="gpt-btn gpt-btn-go" id="gpt-fetch">
                        <span class="gpt-btn-icon">⚡</span>
                        <span>GO</span>
                    </button>
                </div>
                
                <!-- Secondary Buttons -->
                <div class="gpt-btn-row">
                    <button class="gpt-btn gpt-btn-cycle" id="gpt-cycle">
                        <span class="gpt-btn-icon">🔁</span>
                        <span>CYCLE</span>
                    </button>
                    <button class="gpt-btn" id="gpt-kc-macd" style="background:linear-gradient(135deg,#06b6d4,#0891b2);color:white;">
                        <span class="gpt-btn-icon">📊</span>
                        <span>KC-5s</span>
                    </button>
                    <button class="gpt-btn gpt-btn-log" id="gpt-console-toggle">
                        <span class="gpt-btn-icon">📋</span>
                        <span>LOG</span>
                    </button>
                </div>
                <div class="gpt-btn-row">
                    <button class="gpt-btn gpt-btn-reset" id="gpt-reset-stats" style="background:#991b1b;">
                        <span class="gpt-btn-icon">🗑</span>
                        <span>RESET</span>
                    </button>
                </div>
                
                <!-- Invert Control: OFF / AUTO / ON -->
                <div class="gpt-settings-row" style="margin-bottom:6px; padding:4px 8px;">
                    <span class="gpt-input-label" style="white-space:nowrap; font-size:9px;">INVERT:</span>
                    <div style="display:flex; gap:2px; flex:1;">
                        <button class="gpt-inv-mode" id="gpt-inv-off" style="flex:1; padding:3px 0; border:1px solid #475569; border-radius:4px; background:#1e293b; color:#94a3b8; font-size:9px; cursor:pointer;">OFF</button>
                        <button class="gpt-inv-mode" id="gpt-inv-auto" style="flex:1; padding:3px 0; border:1px solid #475569; border-radius:4px; background:#1e293b; color:#94a3b8; font-size:9px; cursor:pointer;">AUTO</button>
                        <button class="gpt-inv-mode" id="gpt-inv-on" style="flex:1; padding:3px 0; border:1px solid #475569; border-radius:4px; background:#1e293b; color:#94a3b8; font-size:9px; cursor:pointer;">ON</button>
                    </div>
                </div>
                <div id="gpt-invert-status" style="font-size:9px; color:#94a3b8; padding:0 8px 4px; display:none;"></div>
                
                <!-- Latency Adjustment Control -->
                <div class="gpt-settings-row" style="margin-bottom:6px; padding:4px 8px;">
                    <span class="gpt-input-label" style="white-space:nowrap; font-size:9px;">TIMING:</span>
                    <div style="display:flex; align-items:center; gap:4px; flex:1;">
                        <button id="gpt-lat-minus" style="width:24px; height:20px; border:1px solid #475569; border-radius:4px; background:#1e293b; color:#94a3b8; font-size:12px; cursor:pointer;">-</button>
                        <span id="gpt-lat-value" style="font-size:10px; color:#e2e8f0; min-width:35px; text-align:center;">0s</span>
                        <button id="gpt-lat-plus" style="width:24px; height:20px; border:1px solid #475569; border-radius:4px; background:#1e293b; color:#94a3b8; font-size:12px; cursor:pointer;">+</button>
                        <span style="font-size:8px; color:#64748b; margin-left:4px;">±5s</span>
                    </div>
                </div>
                
                <!-- Signal Status Display -->
                <div id="gpt-signal-status" style="padding:4px 8px; margin-bottom:4px; display:none;">
                    <div style="background:rgba(30,41,59,0.8); border:1px solid rgba(71,85,105,0.4); border-radius:6px; padding:6px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:3px;">
                            <span style="color:#94a3b8; font-size:8px; text-transform:uppercase;">LAST SIGNAL</span>
                            <span id="gpt-sig-inv-badge" style="font-size:8px; padding:1px 5px; border-radius:3px; background:#475569; color:#e2e8f0;">—</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                            <span id="gpt-sig-direction" style="font-weight:bold; font-size:12px; color:#e2e8f0;">—</span>
                            <span id="gpt-sig-symbol" style="color:#a78bfa; font-size:10px;">—</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; font-size:9px; color:#94a3b8;">
                            <span>Conf: <span id="gpt-sig-confidence" style="color:#22c55e;">—</span></span>
                            <span>RSI: <span id="gpt-sig-rsi" style="color:#38bdf8;">—</span></span>
                            <span>EMA: <span id="gpt-sig-trend" style="color:#f59e0b;">—</span></span>
                        </div>
                        <div style="font-size:8px; color:#64748b; margin-top:2px;" id="gpt-sig-source">—</div>
                    </div>
                </div>
                
                <!-- Cycle Status -->
                <div id="gpt-cycle-status" class="gpt-log-bar" style="display:none; color:#38bdf8; font-size:9px; margin-bottom:4px;">
                    CYCLE: Idle
                </div>
                
                <!-- Stats -->
                <div class="gpt-stats-row">
                    <div class="gpt-stat-box">
                        <div class="gpt-stat-label">Wins</div>
                        <div class="gpt-stat-value win" id="gpt-wins">0</div>
                    </div>
                    <div class="gpt-stat-box">
                        <div class="gpt-stat-label">Losses</div>
                        <div class="gpt-stat-value loss" id="gpt-losses">0</div>
                    </div>
                    <div class="gpt-stat-box">
                        <div class="gpt-stat-label">Profit</div>
                        <div class="gpt-stat-value profit" id="gpt-profit">$0</div>
                    </div>
                </div>
                
                <!-- Settings -->
                <div class="gpt-settings-row">
                    <div class="gpt-input-group">
                        <span class="gpt-input-label">Balance $</span>
                        <input type="number" class="gpt-input" id="gpt-mm-balance-input" value="100">
                    </div>
                    <div class="gpt-input-group">
                        <span class="gpt-input-label">Risk %</span>
                        <input type="number" class="gpt-input" id="gpt-mm-risk" value="2" style="width:40px;">
                    </div>
                    <div class="gpt-result-btns">
                        <button class="gpt-result-btn win" id="gpt-win-btn">+W</button>
                        <button class="gpt-result-btn loss" id="gpt-loss-btn">-L</button>
                    </div>
                </div>
                
                <!-- Status Log -->
                <div class="gpt-log-bar" id="gpt-log">Ready - Click SCAN to start</div>
            </div>
        `;

        document.body.appendChild(panel);
        
        // Create Console Window
        const consoleWindow = document.createElement('div');
        consoleWindow.id = 'gpt-console-window';
        consoleWindow.innerHTML = `
            <div id="gpt-console-header">
                <span>📊 GPT Signal Bot Console</span>
                <button id="gpt-console-close">✕</button>
            </div>
            <div id="gpt-console-content"></div>
        `;
        document.body.appendChild(consoleWindow);

        // Apply minimized state
        if (isMinimized) {
            panel.classList.add('minimized');
            document.getElementById('gpt-minimize').textContent = '+';
        } else {
            panel.classList.remove('minimized');
            document.getElementById('gpt-minimize').textContent = '−';
        }

        // Button handlers
        document.getElementById('gpt-auto').addEventListener('click', toggleAuto);
        document.getElementById('gpt-scan').addEventListener('click', toggleScan);
        document.getElementById('gpt-inv-off').addEventListener('click', () => setInvertMode('off'));
        document.getElementById('gpt-inv-auto').addEventListener('click', () => setInvertMode('auto'));
        document.getElementById('gpt-inv-on').addEventListener('click', () => setInvertMode('on'));
        document.getElementById('gpt-reset-stats').addEventListener('click', resetAllStats);
        document.getElementById('gpt-cycle').addEventListener('click', toggleCycle);
        document.getElementById('gpt-fetch').addEventListener('click', handleFetch);
        
        // KC-MACD 5s dedicated button — force scan using Keltner-MACD strategy only
        document.getElementById('gpt-kc-macd').addEventListener('click', async () => {
            log('KC-MACD 5s: Force scanning with Keltner-MACD strategy...');
            const candles = PriceScraperV2.getCandles();
            if (!candles || candles.length < 65) {
                log('KC-MACD 5s: Not enough candles (need 65+), trying backend...');
                doBackendScan(true, true, false);
                return;
            }
            const signal = LocalSignalEngine.getKeltnerMACDSignal(candles);
            if (signal && signal.confidence >= CONFIG.MIN_CONFIDENCE) {
                log(`KC-MACD 5s: ${signal.direction} (${signal.confidence}%) - placing trade`);
                executeTrade(signal);
            } else {
                log('KC-MACD 5s: No signal from local engine, trying IQ-720 Ensemble...');
                const iq720Signal = LocalSignalEngine.getIQ720EnsembleSignal(candles);
                if (iq720Signal && iq720Signal.confidence >= CONFIG.MIN_CONFIDENCE) {
                    log(`IQ-720 Ensemble: ${iq720Signal.direction} (${iq720Signal.confidence}%) - placing trade`);
                    executeTrade(iq720Signal);
                } else {
                    log('KC-MACD 5s: No clear signal at this time');
                }
            }
        });
        
        document.getElementById('gpt-minimize').addEventListener('click', toggleMinimize);
        document.getElementById('gpt-console-toggle').addEventListener('click', toggleConsoleWindow);
        document.getElementById('gpt-console-close').addEventListener('click', toggleConsoleWindow);
        
        // Latency adjustment handlers
        document.getElementById('gpt-lat-minus').addEventListener('click', () => adjustLatency(-1));
        document.getElementById('gpt-lat-plus').addEventListener('click', () => adjustLatency(1));
        
        // Double-click header to expand (for stuck minimized state)
        document.getElementById('gpt-drag').addEventListener('dblclick', (e) => {
            if (isMinimized) {
                toggleMinimize();
            }
        });
        
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
            log(`Balance updated: $${moneyManagement.accountBalance}`);
        });
        document.getElementById('gpt-mm-risk').addEventListener('change', (e) => {
            moneyManagement.riskPercentage = parseFloat(e.target.value) || 2;
            calculateBaseTradeAmount();
            GM_setValue('mmRiskPercentage', moneyManagement.riskPercentage);
            updateMoneyManagementDisplay();
            log(`Risk updated: ${moneyManagement.riskPercentage}%`);
        });

        // Strategy dropdown handler
        document.getElementById('gpt-strategy-select').addEventListener('change', (e) => {
            onStrategyChange(e.target.value);
        });
        
        // Load strategies from API
        loadStrategiesDropdown();

        // Make draggable
        makeDraggable(panel, document.getElementById('gpt-drag'));
        
        // Make console window draggable
        makeDraggable(consoleWindow, document.getElementById('gpt-console-header'));
        
        // Apply saved position (with validation)
        const savedPos = GM_getValue('panelPosition', null);
        if (savedPos && savedPos.top && savedPos.left) {
            const topVal = parseInt(savedPos.top);
            const leftVal = parseInt(savedPos.left);
            // Validate position is within viewport
            if (topVal >= 0 && topVal < window.innerHeight - 30 && 
                leftVal > -200 && leftVal < window.innerWidth - 40) {
                panel.style.setProperty('top', savedPos.top, 'important');
                panel.style.setProperty('left', savedPos.left, 'important');
                panel.style.setProperty('bottom', 'auto', 'important');
                panel.style.setProperty('right', 'auto', 'important');
            } else {
                // Invalid position, clear it
                GM_setValue('panelPosition', null);
            }
        }
        
        // Triple-click header = reset panel position to default bottom-left
        let clickCount = 0;
        let clickTimer = null;
        document.getElementById('gpt-drag').addEventListener('click', () => {
            clickCount++;
            if (clickTimer) clearTimeout(clickTimer);
            clickTimer = setTimeout(() => { clickCount = 0; }, 500);
            if (clickCount >= 3) {
                clickCount = 0;
                panel.style.removeProperty('top');
                panel.style.removeProperty('right');
                panel.style.setProperty('left', '15px');
                panel.style.setProperty('bottom', '15px');
                GM_setValue('panelPosition', null);
                log('Panel position reset to default');
            }
        });
        
        updateAllUI();
    }

    function toggleMinimize() {
        const panel = document.getElementById('gpt-panel');
        const btn = document.getElementById('gpt-minimize');
        
        if (!panel || !btn) {
            console.error('[GPT] Panel or button not found');
            return;
        }
        
        isMinimized = !isMinimized;
        GM_setValue('isMinimized', isMinimized);
        
        if (isMinimized) {
            panel.classList.add('minimized');
            btn.textContent = '+';
            btn.title = 'Expand panel';
        } else {
            panel.classList.remove('minimized');
            btn.textContent = '−';
            btn.title = 'Minimize panel';
        }
        
        log(`Panel ${isMinimized ? 'minimized' : 'expanded'}`);
    }
    
    // Force expand function (for stuck states)
    function forceExpand() {
        const panel = document.getElementById('gpt-panel');
        const btn = document.getElementById('gpt-minimize');
        
        if (panel) {
            panel.classList.remove('minimized');
            isMinimized = false;
            GM_setValue('isMinimized', false);
            if (btn) {
                btn.textContent = '−';
                btn.title = 'Minimize panel';
            }
            log('Panel force expanded');
        }
    }
    
    // Expose forceExpand globally for debugging
    window.gptForceExpand = forceExpand;

    function makeDraggable(panel, handle) {
        let isDragging = false;
        let startX, startY, startLeft, startTop;

        // Mouse events - use capture phase to beat Pocket Option's event handlers
        handle.addEventListener('mousedown', startDrag, true);
        document.addEventListener('mousemove', drag, true);
        document.addEventListener('mouseup', endDrag, true);
        
        // Touch events for mobile
        handle.addEventListener('touchstart', startDragTouch, { passive: false, capture: true });
        document.addEventListener('touchmove', dragTouch, { passive: false, capture: true });
        document.addEventListener('touchend', endDrag, true);

        function startDrag(e) {
            // Don't drag if clicking minimize button or other buttons
            if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
            
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            
            // Get computed position
            const rect = panel.getBoundingClientRect();
            startLeft = rect.left;
            startTop = rect.top;
            
            // Convert to top/left positioning - use setProperty with important
            panel.style.setProperty('bottom', 'auto', 'important');
            panel.style.setProperty('right', 'auto', 'important');
            panel.style.setProperty('top', startTop + 'px', 'important');
            panel.style.setProperty('left', startLeft + 'px', 'important');
            
            // Disable transition during drag for instant response
            panel.style.setProperty('transition', 'none', 'important');
            
            e.preventDefault();
            e.stopPropagation();
        }

        function startDragTouch(e) {
            if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
            
            isDragging = true;
            const touch = e.touches[0];
            startX = touch.clientX;
            startY = touch.clientY;
            
            // Get computed position
            const rect = panel.getBoundingClientRect();
            startLeft = rect.left;
            startTop = rect.top;
            
            // Convert to top/left positioning
            panel.style.setProperty('bottom', 'auto', 'important');
            panel.style.setProperty('right', 'auto', 'important');
            panel.style.setProperty('top', startTop + 'px', 'important');
            panel.style.setProperty('left', startLeft + 'px', 'important');
            
            // Disable transition during drag
            panel.style.setProperty('transition', 'none', 'important');
            
            e.preventDefault();
            e.stopPropagation();
        }

        function drag(e) {
            if (!isDragging) return;
            
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            
            // Calculate new position with bounds checking
            let newLeft = startLeft + dx;
            let newTop = startTop + dy;
            
            // Keep panel within viewport
            const panelRect = panel.getBoundingClientRect();
            const maxLeft = window.innerWidth - 40;
            const maxTop = window.innerHeight - 30;
            newLeft = Math.max(-panelRect.width + 40, Math.min(newLeft, maxLeft));
            newTop = Math.max(0, Math.min(newTop, maxTop));
            
            panel.style.setProperty('left', newLeft + 'px', 'important');
            panel.style.setProperty('top', newTop + 'px', 'important');
            panel.style.setProperty('right', 'auto', 'important');
            panel.style.setProperty('bottom', 'auto', 'important');
            
            e.preventDefault();
            e.stopPropagation();
        }

        function dragTouch(e) {
            if (!isDragging) return;
            
            const touch = e.touches[0];
            const dx = touch.clientX - startX;
            const dy = touch.clientY - startY;
            
            // Calculate new position with bounds checking
            let newLeft = startLeft + dx;
            let newTop = startTop + dy;
            
            const panelRect = panel.getBoundingClientRect();
            const maxLeft = window.innerWidth - 40;
            const maxTop = window.innerHeight - 30;
            newLeft = Math.max(-panelRect.width + 40, Math.min(newLeft, maxLeft));
            newTop = Math.max(0, Math.min(newTop, maxTop));
            
            panel.style.setProperty('left', newLeft + 'px', 'important');
            panel.style.setProperty('top', newTop + 'px', 'important');
            panel.style.setProperty('right', 'auto', 'important');
            panel.style.setProperty('bottom', 'auto', 'important');
            
            e.preventDefault();
            e.stopPropagation();
        }

        function endDrag(e) {
            if (isDragging) {
                isDragging = false;
                // Restore transition
                panel.style.setProperty('transition', 'width 0.3s ease, border-radius 0.3s ease', 'important');
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

    // ===========================================
    // INVERT MODE CONTROL - OFF / AUTO / ON
    // ===========================================
    function setInvertMode(mode) {
        // mode: 'off', 'auto', 'on'
        GM_setValue('invertMode', mode);
        
        if (mode === 'off') {
            smartAutoInvert.enabled = false;
            smartAutoInvert.invertActive = false;
            invertEnabled = false;
            log('INVERT: OFF - Signals trade as-is');
        } else if (mode === 'auto') {
            smartAutoInvert.enabled = true;
            // Keep current invertActive state OR restore from saved
            const savedActive = GM_getValue('smartAutoInvertActive', false);
            if (!smartAutoInvert.invertActive && savedActive) {
                smartAutoInvert.invertActive = savedActive;
            }
            invertEnabled = smartAutoInvert.invertActive;
            log(`INVERT: AUTO - Momentum-aware (currently ${smartAutoInvert.invertActive ? 'INVERTED' : 'NORMAL'})`);
        } else if (mode === 'on') {
            smartAutoInvert.enabled = false;
            smartAutoInvert.invertActive = true;
            invertEnabled = true;
            log('INVERT: ON - All signals inverted');
        }
        
        // Save ALL invert-related state
        saveAutoInvertState();
        
        updateInvertModeUI(mode);
        updateInvertDisplay();
    }
    
    function updateInvertModeUI(mode) {
        const offBtn = document.getElementById('gpt-inv-off');
        const autoBtn = document.getElementById('gpt-inv-auto');
        const onBtn = document.getElementById('gpt-inv-on');
        const statusEl = document.getElementById('gpt-invert-status');
        
        if (!offBtn) return;
        
        // Reset all
        [offBtn, autoBtn, onBtn].forEach(b => {
            b.style.background = '#1e293b';
            b.style.color = '#94a3b8';
            b.style.borderColor = '#475569';
        });
        
        if (mode === 'off') {
            offBtn.style.background = '#475569';
            offBtn.style.color = '#e2e8f0';
            if (statusEl) statusEl.style.display = 'none';
        } else if (mode === 'auto') {
            autoBtn.style.background = 'linear-gradient(135deg, #f59e0b, #d97706)';
            autoBtn.style.color = '#fff';
            autoBtn.style.borderColor = '#f59e0b';
            if (statusEl) {
                statusEl.style.display = 'block';
                statusEl.textContent = smartAutoInvert.invertActive ? 'AUTO: INVERTED (momentum shift)' : 'AUTO: NORMAL (trend intact)';
                statusEl.style.color = smartAutoInvert.invertActive ? '#f59e0b' : '#22c55e';
            }
        } else if (mode === 'on') {
            onBtn.style.background = 'linear-gradient(135deg, #ef4444, #b91c1c)';
            onBtn.style.color = '#fff';
            onBtn.style.borderColor = '#ef4444';
            if (statusEl) {
                statusEl.style.display = 'block';
                statusEl.textContent = 'ALWAYS INVERTED - All signals flipped';
                statusEl.style.color = '#ef4444';
            }
        }
    }
    
    function getCurrentInvertMode() {
        if (smartAutoInvert.enabled) return 'auto';
        if (invertEnabled) return 'on';
        return 'off';
    }
    
    // ===========================================
    // LATENCY ADJUSTMENT - +/- 5 seconds for timing
    // ===========================================
    function adjustLatency(delta) {
        const newValue = Math.max(-5, Math.min(5, CONFIG.RESULT_LATENCY_OFFSET + delta));
        CONFIG.RESULT_LATENCY_OFFSET = newValue;
        GM_setValue('resultLatencyOffset', newValue);
        
        // Update display
        const valueEl = document.getElementById('gpt-lat-value');
        if (valueEl) {
            valueEl.textContent = (newValue >= 0 ? '+' : '') + newValue + 's';
            valueEl.style.color = newValue === 0 ? '#e2e8f0' : newValue > 0 ? '#22c55e' : '#f59e0b';
        }
        
        log(`TIMING: Latency offset set to ${newValue}s (${newValue > 0 ? 'wait longer' : newValue < 0 ? 'detect earlier' : 'default'})`);
    }
    
    function initLatencyDisplay() {
        const savedLatency = GM_getValue('resultLatencyOffset', 0);
        CONFIG.RESULT_LATENCY_OFFSET = savedLatency;
        
        const valueEl = document.getElementById('gpt-lat-value');
        if (valueEl) {
            valueEl.textContent = (savedLatency >= 0 ? '+' : '') + savedLatency + 's';
            valueEl.style.color = savedLatency === 0 ? '#e2e8f0' : savedLatency > 0 ? '#22c55e' : '#f59e0b';
        }
    }
    
    // ===========================================
    // SIGNAL STATUS DISPLAY - Shows current signal info
    // ===========================================
    function updateSignalStatusDisplay(signal) {
        const container = document.getElementById('gpt-signal-status');
        if (!container) return;
        
        container.style.display = 'block';
        
        const dirEl = document.getElementById('gpt-sig-direction');
        const symEl = document.getElementById('gpt-sig-symbol');
        const confEl = document.getElementById('gpt-sig-confidence');
        const rsiEl = document.getElementById('gpt-sig-rsi');
        const trendEl = document.getElementById('gpt-sig-trend');
        const srcEl = document.getElementById('gpt-sig-source');
        const invBadge = document.getElementById('gpt-sig-inv-badge');
        
        if (dirEl) {
            dirEl.textContent = signal.direction || '—';
            dirEl.style.color = signal.direction === 'CALL' ? '#22c55e' : signal.direction === 'PUT' ? '#ef4444' : '#e2e8f0';
        }
        if (symEl) symEl.textContent = signal.symbol || '—';
        if (confEl) {
            const conf = Math.round(signal.confidence || 0);
            confEl.textContent = conf + '%';
            confEl.style.color = conf >= 70 ? '#22c55e' : conf >= 50 ? '#f59e0b' : '#ef4444';
        }
        
        // Show local RSI if available
        if (rsiEl) {
            const candles = PriceScraperV2.getCandles();
            if (candles && candles.length >= 5) {
                const closes = candles.map(c => c.close);
                const rsi = LocalSignalEngine.calculateRSI(closes, 5);
                rsiEl.textContent = rsi.toFixed(0);
                rsiEl.style.color = rsi > 70 ? '#ef4444' : rsi < 30 ? '#22c55e' : '#38bdf8';
            } else {
                rsiEl.textContent = '—';
            }
        }
        
        // Show EMA trend
        if (trendEl) {
            const candles = PriceScraperV2.getCandles();
            if (candles && candles.length >= 10) {
                const closes = candles.map(c => c.close);
                const ema5 = LocalSignalEngine.calculateEMA(closes, 5);
                const ema10 = LocalSignalEngine.calculateEMA(closes, 10);
                if (ema5 > ema10) {
                    trendEl.textContent = 'BULL';
                    trendEl.style.color = '#22c55e';
                } else {
                    trendEl.textContent = 'BEAR';
                    trendEl.style.color = '#ef4444';
                }
            } else {
                trendEl.textContent = '—';
            }
        }
        
        if (srcEl) srcEl.textContent = `Source: ${signal.source || '—'}`;
        
        if (invBadge) {
            if (signal._smartInverted) {
                invBadge.textContent = 'INVERTED';
                invBadge.style.background = '#f59e0b';
                invBadge.style.color = '#000';
            } else {
                invBadge.textContent = 'NORMAL';
                invBadge.style.background = '#22c55e';
                invBadge.style.color = '#000';
            }
        }
    }

    function handleFetch() {
        // GO button forces signal generation for CURRENT ASSET using backend API
        const currentAssetRaw = getCurrentAsset() || 'EURUSD';
        let assetSymbol = currentAssetRaw
            .replace(/\s+/g, '')
            .replace('/', '')
            .toUpperCase();
        
        // Remove trailing OTC or REGULAR (without underscore) then add proper suffix
        assetSymbol = assetSymbol.replace(/OTC$/i, '').replace(/REGULAR$/i, '');
        
        // Ensure proper _OTC suffix
        if (!assetSymbol.includes('_OTC') && !assetSymbol.includes('_REGULAR')) {
            assetSymbol += '_OTC';
        }
        
        log(`🔄 GO: Generating signal for ${assetSymbol}...`);
        updateStatusDot('trading');
        
        // PRIMARY: Use scan-markets GET (simpler, more reliable)
        const scanUrl = CONFIG.API_URL + `/signals/scan-markets?assets=${assetSymbol}&min_confidence=60`;
        log(`📡 Calling: ${scanUrl}`);
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: scanUrl,
            headers: { 'Accept': 'application/json' },
            timeout: 20000,
            onload: function(res) {
                try {
                    log(`📡 Scan response: ${res.status}`);
                    if (res.status === 200) {
                        const data = JSON.parse(res.responseText);
                        const signals = data.top_signals || data.signals || [];
                        
                        if (data.success && signals.length > 0) {
                            const signal = signals[0];
                            log(`✅ GO SIGNAL: ${signal.direction} ${signal.symbol} (${Math.round(signal.confidence)}%) [${signal.analysis_type}]`);
                            
                            const tradeSignal = {
                                direction: signal.direction,
                                symbol: signal.symbol || assetSymbol,
                                confidence: signal.confidence || 85,
                                source: 'GO_SCAN',
                                expiration_seconds: signal.expiry_seconds || 60,
                                _willSwitch: false
                            };
                            
                            executeScanTrade(tradeSignal).catch(err => {
                                log(`❌ Trade execution error: ${err.message}`);
                                updateStatusDot('connected');
                            });
                            return;
                        }
                    }
                    
                    // No signal from scan - try force-generate
                    log('⚠️ No scan signal, trying force-generate...');
                    _goForceGenerate(assetSymbol);
                    
                } catch (e) {
                    log(`❌ Parse error: ${e.message}`);
                    _goForceGenerate(assetSymbol);
                }
            },
            onerror: function(e) {
                log(`❌ Scan connection error - trying force-generate...`);
                log(`   Error: ${e?.message || 'Unknown error'}`);
                _goForceGenerate(assetSymbol);
            },
            ontimeout: function() {
                log('❌ Scan timeout - trying force-generate...');
                _goForceGenerate(assetSymbol);
            }
        });
    }
    
    function _goForceGenerate(assetSymbol) {
        const forceUrl = CONFIG.API_URL + `/signals/force-generate/asset/${encodeURIComponent(assetSymbol)}?wait_for_candle=false`;
        log(`Force-generate: ${forceUrl}`);
        
        GM_xmlhttpRequest({
            method: 'POST',
            url: forceUrl,
            headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
            timeout: 20000,
            onload: function(res) {
                try {
                    log(`Force response: ${res.status}`);
                    const data = JSON.parse(res.responseText);
                    
                    if (data.success) {
                        const signals = data.signals || [];
                        const signal = signals[0] || data.signal;
                        
                        if (signal) {
                            // Normalize direction: BUY/SELL → CALL/PUT
                            let direction = (signal.direction || '').toUpperCase();
                            if (direction === 'BUY' || direction === 'LONG') direction = 'CALL';
                            if (direction === 'SELL' || direction === 'SHORT') direction = 'PUT';
                            
                            const conf = signal.confidence || signal.probability || 85;
                            log(`FORCED: ${direction} ${signal.symbol || assetSymbol} (${conf}%)`);
                            
                            const tradeSignal = {
                                direction: direction,
                                symbol: signal.symbol || assetSymbol,
                                confidence: conf,
                                source: 'FORCE_GENERATE',
                                expiration_seconds: signal.expiry_seconds || (signal.expiration_minutes ? signal.expiration_minutes * 60 : 60),
                                _willSwitch: false,
                                technical_analysis: signal.technical_analysis || null,
                            };
                            
                            // Apply auto-invert if enabled
                            const processed = processSmartAutoInvert(tradeSignal);
                            
                            lastTradeInfo.symbol = processed.symbol;
                            lastTradeInfo.direction = processed.direction;
                            lastTradeInfo.confidence = processed.confidence;
                            
                            updateSignalStatusDisplay(processed);
                            
                            executeScanTrade(processed).catch(err => {
                                log(`Trade error: ${err.message}`);
                                updateStatusDot('connected');
                            });
                            return;
                        }
                    }
                    
                    log(`Force-generate returned no signal`);
                    updateStatusDot('connected');
                } catch (e) {
                    log(`Force parse error: ${e.message}`);
                    updateStatusDot('connected');
                }
            },
            onerror: function(e) {
                log(`BOTH scan & force-generate failed. Check API connection.`);
                log(`   API URL: ${CONFIG.API_URL}`);
                updateStatusDot('error');
            },
            ontimeout: function() {
                log(`Force-generate timeout. API may be slow.`);
                updateStatusDot('error');
            }
        });
    }

    // ===========================================
    // ===========================================
    // CYCLE MODE - v8.7.0 (Simplified + Fixed)
    // ===========================================
    // SIMPLIFIED WORKFLOW:
    // 1. Cycle through favorites (30s scan per asset)
    // 2. Signal found → Place trade immediately
    // 3. Wait trade expiry → Check balance for win/loss
    // 4. LOSS + Auto-Invert → Flip direction, trade immediately
    // 5. WIN → Continue to next asset
    // ===========================================
    function toggleCycle() {
        cycleEnabled = !cycleEnabled;
        GM_setValue('cycleEnabled', cycleEnabled);
        
        if (cycleEnabled) {
            scanEnabled = false;
            autoEnabled = false;
            GM_setValue('scanEnabled', false);
            GM_setValue('autoEnabled', false);
            manageIntervals();
            
            cycleAbort = false;
            log('CYCLE: ON');
            updateCycleStatus('Starting...');
            startCycleLoop();
        } else {
            cycleAbort = true;
            log('CYCLE: OFF');
            updateCycleStatus('');
        }
        
        updateAllUI();
    }
    
    function updateCycleStatus(text) {
        const el = document.getElementById('gpt-cycle-status');
        if (el) {
            if (text) {
                el.style.display = 'block';
                el.textContent = 'CYCLE: ' + text;
            } else {
                el.style.display = 'none';
            }
        }
    }
    
    // Get expiry from UI or default
    function getTradeExpiry() {
        const tf = detectCurrentTimeframe();
        return tf > 0 ? tf : 5;
    }
    
    // Simplified balance-based win/loss check
    async function checkTradeResult(preTradeBalance, expirySeconds) {
        // Wait for trade to expire + small buffer
        const waitMs = (expirySeconds * 1000) + 3000;
        log(`RESULT: Waiting ${Math.round(waitMs/1000)}s for trade to complete...`);
        
        await sleep(waitMs);
        
        // Check balance now
        const currentBalance = detectAccountBalance(true);
        const diff = currentBalance - preTradeBalance;
        
        log(`RESULT: Pre=$${preTradeBalance.toFixed(2)}, Now=$${currentBalance.toFixed(2)}, Diff=$${diff >= 0 ? '+' : ''}${diff.toFixed(2)}`);
        
        // If balance increased, it's a win
        const isWin = diff > 0.5;
        
        return { isWin, diff, currentBalance };
    }
    
    async function startCycleLoop() {
        if (cycleRunning) {
            log('CYCLE: Already running');
            return;
        }
        cycleRunning = true;
        
        try {
            while (cycleEnabled && !cycleAbort) {
                detectFavoritesBar();
                
                if (favoritesFromBar.length === 0) {
                    log('CYCLE: No favorites. Retrying...');
                    updateCycleStatus('No favorites - retrying...');
                    await sleep(5000);
                    continue;
                }
                
                log(`CYCLE: ${favoritesFromBar.length} favorites found`);
                
                for (let i = 0; i < favoritesFromBar.length; i++) {
                    if (!cycleEnabled || cycleAbort) break;
                    
                    const favorite = favoritesFromBar[i];
                    const assetName = favorite.symbol || favorite.normalized;
                    
                    log(`════════ CYCLE [${i+1}/${favoritesFromBar.length}]: ${assetName} ════════`);
                    updateCycleStatus(`${assetName} (${i+1}/${favoritesFromBar.length})`);
                    
                    // Switch to asset
                    const switched = await clickFavoriteAsset(favorite);
                    if (!switched) {
                        log(`CYCLE: Failed to switch to ${assetName}`);
                        await sleep(1000);
                        continue;
                    }
                    
                    await sleep(2000);
                    
                    // Clear candle data for new asset
                    PriceScraperV2.priceHistory = [];
                    PriceScraperV2.candleHistory = [];
                    
                    // Scan for signal (30 seconds max)
                    let signal = null;
                    let lastDirection = null;
                    let retryCount = 0;
                    const maxRetries = 5;
                    
                    // === SCAN PHASE ===
                    const scanStart = Date.now();
                    updateCycleStatus(`${assetName} - Scanning...`);
                    
                    while (Date.now() - scanStart < CONFIG.CYCLE_DWELL_TIME) {
                        if (!cycleEnabled || cycleAbort) break;
                        
                        const price = PriceScraperV2.scrapeCurrentPrice();
                        if (price) {
                            const candle = PriceScraperV2.buildCandle(price, 1000);
                            if (candle) PriceScraperV2.addCandle(candle);
                        }
                        
                        const candles = PriceScraperV2.getCandles();
                        
                        if (candles.length >= 10) {
                            signal = LocalSignalEngine.generateSignal(candles);
                            if (!signal) signal = LocalSignalEngine.getKeltnerMACDSignal(candles);
                            if (!signal) signal = LocalSignalEngine.getHollyCrossoverSignal(candles);
                            if (!signal) signal = LocalSignalEngine.getMomentumBusterSignal(candles);
                            if (!signal) signal = LocalSignalEngine.getIQ720EnsembleSignal(candles);
                            
                            if (signal && signal.confidence >= CONFIG.MIN_CONFIDENCE) {
                                log(`CYCLE: Signal ${signal.direction} (${signal.confidence}%)`);
                                break;
                            }
                        }
                        
                        await sleep(CONFIG.CYCLE_SCAN_INTERVAL);
                    }
                    
                    if (!signal) {
                        log(`CYCLE: No signal on ${assetName}`);
                        continue; // Next asset
                    }
                    
                    // === TRADE + INVERT RETRY LOOP ===
                    let continueTrading = true;
                    lastDirection = signal.direction;
                    
                    while (continueTrading && cycleEnabled && !cycleAbort && retryCount < maxRetries) {
                        retryCount++;
                        
                        // Apply invert if active
                        let tradeDirection = lastDirection;
                        if (smartAutoInvert.invertActive) {
                            tradeDirection = lastDirection === 'CALL' ? 'PUT' : 'CALL';
                            log(`INVERT: Flipping ${lastDirection} → ${tradeDirection}`);
                        }
                        
                        const expiry = getTradeExpiry();
                        const preBalance = detectAccountBalance(true);
                        
                        log(`TRADE #${retryCount}: ${tradeDirection} on ${assetName} (${expiry}s expiry)`);
                        updateCycleStatus(`${assetName} - ${tradeDirection} (${retryCount})`);
                        
                        // Place trade
                        const isCall = tradeDirection === 'CALL';
                        const clicked = clickTradeButton(isCall, 'CYCLE', expiry);
                        
                        if (!clicked) {
                            log(`CYCLE: Trade click failed`);
                            continueTrading = false;
                            break;
                        }
                        
                        // Wait and check result
                        const result = await checkTradeResult(preBalance, expiry);
                        
                        if (result.isWin) {
                            log(`✅ WIN! +$${result.diff.toFixed(2)}`);
                            
                            // Update stats
                            winLossStats.totalWins++;
                            winLossStats.consecutiveWins++;
                            winLossStats.consecutiveLosses = 0;
                            lastTradeResult.isWin = true;
                            lastTradeResult.consecutiveWins++;
                            lastTradeResult.consecutiveLosses = 0;
                            
                            // Turn off invert on win
                            if (smartAutoInvert.enabled && smartAutoInvert.invertActive) {
                                smartAutoInvert.invertActive = false;
                                invertEnabled = false;
                                log(`AUTO-INVERT: WIN → Back to NORMAL`);
                            }
                            
                            saveAutoInvertState();
                            updateWinLossDisplay();
                            
                            // Exit retry loop, move to next asset
                            continueTrading = false;
                            
                        } else {
                            log(`❌ LOSS! $${result.diff.toFixed(2)}`);
                            
                            // Update stats
                            winLossStats.totalLosses++;
                            winLossStats.consecutiveLosses++;
                            winLossStats.consecutiveWins = 0;
                            lastTradeResult.isWin = false;
                            lastTradeResult.consecutiveLosses++;
                            lastTradeResult.consecutiveWins = 0;
                            
                            updateWinLossDisplay();
                            
                            // Check if auto-invert should retry
                            if (smartAutoInvert.enabled) {
                                // Turn on invert
                                if (!smartAutoInvert.invertActive) {
                                    smartAutoInvert.invertActive = true;
                                    invertEnabled = true;
                                    log(`AUTO-INVERT: LOSS → Switching to INVERTED`);
                                }
                                
                                saveAutoInvertState();
                                
                                // Safety limit
                                if (lastTradeResult.consecutiveLosses >= 5) {
                                    log(`AUTO-INVERT: 5 losses - stopping`);
                                    smartAutoInvert.invertActive = false;
                                    lastTradeResult.consecutiveLosses = 0;
                                    continueTrading = false;
                                } else {
                                    // Continue retry loop with inverted direction
                                    log(`AUTO-INVERT: Retrying inverted immediately...`);
                                    await sleep(1500);
                                    continueTrading = true;
                                }
                            } else {
                                // No auto-invert, move to next asset
                                continueTrading = false;
                            }
                        }
                    }
                    
                } // End favorites loop
                
                if (cycleEnabled && !cycleAbort) {
                    log(`CYCLE: Round complete. Restarting...`);
                    updateCycleStatus('Round complete...');
                    await sleep(3000);
                }
            }
        } catch (err) {
            log(`CYCLE ERROR: ${err.message}`);
            console.error('[CYCLE]', err);
        }
        
        cycleRunning = false;
        updateCycleStatus('');
        log('CYCLE: Stopped');
    }
    
    // Quick backend scan for a single asset during CYCLE mode
    function cycleBackendScan(assetName) {
        return new Promise((resolve) => {
            let symbol = assetName.replace(/\s+/g, '').replace('/', '').replace('OTC', '_OTC').toUpperCase();
            if (!symbol.includes('_OTC')) symbol += '_OTC';
            
            const strategyParam = selectedStrategy !== 'default' ? `&strategy=${selectedStrategy}` : '';
            const url = CONFIG.API_URL + `/signals/scan-markets?assets=${symbol}&min_confidence=${CONFIG.MIN_CONFIDENCE}${strategyParam}`;
            
            GM_xmlhttpRequest({
                method: 'GET',
                url: url,
                headers: { 'Accept': 'application/json' },
                timeout: 10000,
                onload: function(res) {
                    try {
                        if (res.status !== 200) { resolve(null); return; }
                        const data = JSON.parse(res.responseText);
                        const signals = data.top_signals || data.signals || [];
                        if (data.success && signals.length > 0) {
                            const sig = signals[0];
                            sig.source = 'CYCLE_BACKEND';
                            sig._willSwitch = false;
                            resolve(sig);
                        } else {
                            resolve(null);
                        }
                    } catch(e) { resolve(null); }
                },
                onerror: function() { resolve(null); },
                ontimeout: function() { resolve(null); }
            });
        });
    }

    function resetToDefaults() {
        autoEnabled = false;
        scanEnabled = false;
        invertEnabled = false;
        cycleEnabled = false;
        cycleAbort = true;
        smartAutoInvert.enabled = false;
        smartAutoInvert.invertActive = false;
        lastAppSignalId = '';
        lastAppTradeTime = 0;
        lastScanTradeTime = 0;
        
        GM_setValue('autoEnabled', false);
        GM_setValue('scanEnabled', false);
        GM_setValue('invertEnabled', false);
        GM_setValue('cycleEnabled', false);
        GM_setValue('smartAutoInvertEnabled', false);
        GM_setValue('smartAutoInvertActive', false);
        
        updateAllUI();
        manageIntervals();
        updateSignalDisplay('READY', null, 'wait', '-');
        updateCycleStatus('');
        
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
            // Do not override button text - it's set by createPanel HTML
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
        const logBtn = document.getElementById('gpt-console-toggle');
        const cycleBtn = document.getElementById('gpt-cycle');

        if (autoBtn) {
            autoBtn.className = 'gpt-btn gpt-btn-auto' + (autoEnabled ? ' active' : '');
        }
        if (scanBtn) {
            scanBtn.className = 'gpt-btn gpt-btn-scan' + (scanEnabled ? ' active' : '');
        }
        if (invertBtn) {
            invertBtn.className = 'gpt-btn gpt-btn-inv' + (smartAutoInvert.enabled ? ' active' : '');
        }
        if (cycleBtn) {
            cycleBtn.className = 'gpt-btn gpt-btn-cycle' + (cycleEnabled ? ' active' : '');
        }
        if (logBtn) {
            const consoleWindow = document.getElementById('gpt-console-window');
            const isConsoleVisible = consoleWindow && consoleWindow.style.display === 'block';
            logBtn.className = 'gpt-btn gpt-btn-log' + (isConsoleVisible ? ' active' : '');
        }
    }

    function updateModeIndicator() {
        // Mode indicator removed in compact UI - status shown via button states
    }

    function updateSignalDisplay(direction, asset, type, source) {
        const sigEl = document.getElementById('gpt-signal');
        
        if (sigEl) {
            sigEl.textContent = direction || 'WAITING';
            sigEl.className = 'gpt-signal-value ' + (type || 'wait');
        }
    }

    function updateStatusDot(status) {
        const dot = document.getElementById('gpt-dot');
        if (dot) {
            dot.className = 'gpt-status-dot';
            if (status === 'connected') dot.classList.add('connected');
            if (status === 'trading') dot.classList.add('trading');
            if (status === 'error') dot.classList.add('error');
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

        // v7.1.0: Start price scraping for local signal generation (only needed for single-asset mode)
        if (scanEnabled && CONFIG.USE_LOCAL_SIGNALS && autoEnabled) {
            startPriceScraping();
            log('🔍 LOCAL SCAN: Using actual OTC prices (current asset only)');
        } else if (scanEnabled && !autoEnabled) {
            // Multi-asset mode uses backend API, but start scraping anyway for fallback
            startPriceScraping();
            log('🔍 MULTI-ASSET SCAN: Backend API scans ALL favorites, switches to best signal');
        } else {
            stopPriceScraping();
        }

        // SCAN: Generate signals locally or via backend
        if (scanEnabled) {
            const isMultiAsset = !autoEnabled;
            const scanMode = isMultiAsset ? 'MULTI-ASSET (Backend API)' : (CONFIG.USE_LOCAL_SIGNALS ? 'LOCAL OTC' : 'BACKEND OANDA');
            log(`🔍 Starting scan: ${scanMode}`);
            if (isMultiAsset) {
                log('📊 Will scan ALL favorites and switch to best signal asset');
            }
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

        // Track trade info for premium result recording
        lastTradeInfo.symbol = (signal.symbol || '').replace(/\s+/g, '').replace('/', '').toUpperCase();
        lastTradeInfo.direction = finalDirection;
        lastTradeInfo.confidence = signal.confidence || 0;

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
        // Pass expiry time from signal or use default based on timeframe
        const expirySeconds = signal.expiration_seconds || signal.expiry || getExpiryFromTimeframe(signal.timeframe) || 60;
        const clicked = clickTradeButton(isCall, 'APP', expirySeconds);
        
        if (clicked) {
            incrementTradeCount();
            lastAppTradeTime = Date.now();
            log(`✅ APP TRADE: ${finalDirection} on ${signal.symbol} (${expirySeconds}s expiry)`);
            
            // Store trade info for manual result entry if needed
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
        // AUTO OFF + not currentAssetOnly = scan ALL favorites and switch to best
        let willSwitchAssets = !autoEnabled && !currentAssetOnly;
        
        // MULTI-ASSET MODE: Always use backend scan when scanning all favorites
        // Local scan can only see the current asset's price on the page
        if (willSwitchAssets) {
            log('🔍 Multi-asset scan → using backend API (scans all favorites at once)');
            doBackendScan(force, currentAssetOnly, willSwitchAssets);
        } else if (CONFIG.USE_LOCAL_SIGNALS) {
            // SINGLE-ASSET MODE: Use local scan for current asset only
            doLocalScan(force, currentAssetOnly, willSwitchAssets);
        } else {
            // Backend scan for single asset
            doBackendScan(force, currentAssetOnly, willSwitchAssets);
        }
    }
    
    // v7.2.0: Local signal generation using actual OTC prices
    function doLocalScan(force, currentAssetOnly, willSwitchAssets) {
        updateStatusDot('trading');
        
        const currentAsset = getCurrentAsset() || 'Unknown';
        log(`🔍 LOCAL SCAN: ${currentAsset} (OTC prices)`);
        
        // Scrape current price with enhanced detection
        const currentPrice = PriceScraperV2.scrapeCurrentPrice();
        if (!currentPrice) {
            log('⚠️ PRICE SCRAPER FAILED - Debugging...');
            // Log what we can see on the page
            const bodyText = document.body.innerText.substring(0, 500);
            log(`Page preview: ${bodyText.substring(0, 200)}...`);
            
            // Try to find ANY numbers that look like prices
            PriceScraperV2._logAllPotentialPrices();
            
            // FALLBACK: If forced (GO button), use backend API instead of giving up
            if (force) {
                log('🔄 GO: Falling back to backend API signal...');
                doBackendScan(force, currentAssetOnly, willSwitchAssets);
                return;
            }
            
            updateStatusDot('error');
            return;
        }
        
        log(`💰 Current price: ${currentPrice}`);
        if (PriceScraperV2.foundSelector) {
            log(`📍 Using selector: ${PriceScraperV2.foundSelector}`);
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
            // FALLBACK: If forced (GO button), use backend API instead of waiting
            if (force) {
                log('🔄 GO: Not enough local candles, falling back to backend API...');
                doBackendScan(force, currentAssetOnly, willSwitchAssets);
                return;
            }
            updateStatusDot('connected');
            return;
        }
        
        // Generate signal using local engine - try multiple strategies
        let signal = LocalSignalEngine.generateSignal(candles);
        
        // Try Holly Crossover (reversal) if general strategy found nothing
        // Try Keltner-MACD 5s first (priority strategy)
        if (!signal) {
            signal = LocalSignalEngine.getKeltnerMACDSignal(candles);
            if (signal) log(`Keltner-MACD 5s triggered`);
        }
        
        // Try Holly Crossover
        if (!signal) {
            signal = LocalSignalEngine.getHollyCrossoverSignal(candles);
            if (signal) log(`Holly Crossover triggered`);
        }
        
        // Try Golden One Moment (30s) if still no signal
        if (!signal) {
            signal = LocalSignalEngine.getGoldenOneMomentSignal(candles);
            if (signal) log(`Golden One Moment triggered`);
        }
        
        // Try Momentum Buster (15s) if still no signal
        if (!signal) {
            signal = LocalSignalEngine.getMomentumBusterSignal(candles);
            if (signal) log(`Momentum Buster 15s triggered`);
        }
        
        // Try IQ-720 Ensemble (advanced multi-indicator) if still no signal
        if (!signal) {
            signal = LocalSignalEngine.getIQ720EnsembleSignal(candles);
            if (signal) log(`IQ-720 Ensemble triggered`);
        }
        
        if (signal) {
            log(`✅ LOCAL SIGNAL: ${signal.direction} (${signal.confidence}%) [${signal.strategy || 'Local'}]`);
            log(`📊 Confirmations: ${signal.confirmations.join(', ')}`);
            
            // Check minimum confidence
            if (signal.confidence < CONFIG.MIN_CONFIDENCE) {
                log(`⚠️ Confidence too low: ${signal.confidence}% < ${CONFIG.MIN_CONFIDENCE}%`);
                updateStatusDot('connected');
                return;
            }
            
            // Build signal object for execution
            // Detect the current timeframe from PO UI for proper outcome timing
            const detectedExpiry = detectCurrentTimeframe();
            
            const tradeSignal = {
                direction: signal.direction,
                symbol: currentAsset.replace(/\s+/g, '').replace('/', '').toUpperCase(),
                confidence: signal.confidence,
                confirmations: signal.confirmations,
                price: signal.price,
                source: 'LOCAL_OTC',
                expiration_seconds: detectedExpiry,
                _willSwitch: willSwitchAssets
            };
            
            // Apply Smart Auto-Invert
            const processedSignal = processSmartAutoInvert(tradeSignal);
            
            // Track trade info for premium result recording and ML training
            lastTradeInfo.symbol = processedSignal.symbol || '';
            lastTradeInfo.direction = processedSignal.direction || '';
            lastTradeInfo.confidence = processedSignal.confidence || 0;
            lastTradeInfo.strategy = signal.strategy || 'Local Engine v8.5';
            lastTradeInfo.indicators = signal.indicators || {};
            
            // Store globally for ML training
            window.lastTradeIndicators = signal.indicators || {};
            window.lastTradeStrategy = signal.strategy || 'Local Engine v8.5';
            
            if (processedSignal._smartInverted) {
                log(`SMART INVERT applied: ${processedSignal._originalDirection} -> ${processedSignal.direction}`);
            }
            
            // Execute trade
            executeScanTrade(processedSignal).catch(err => {
                log(`❌ Trade error: ${err.message}`);
                updateStatusDot('connected');
            });
        } else {
            log('⚠️ No signal (conditions not met)');
            // FALLBACK: If forced (GO button), try backend API as last resort
            if (force) {
                log('🔄 GO: No local signal found, trying backend API...');
                doBackendScan(force, currentAssetOnly, willSwitchAssets);
                return;
            }
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
                log(`🔍 MULTI-ASSET SCAN: ${favoritesFromBar.length} favorites`);
            } else {
                // Fallback: default popular pairs
                assetsToScan = 'EURUSD_OTC,GBPUSD_OTC,USDJPY_OTC,AUDUSD_OTC,EURGBP_OTC,EURJPY_OTC';
                log(`🔍 MULTI-ASSET SCAN: Using default 6 pairs (no favorites detected)`);
            }
        }

        const strategyParam = selectedStrategy !== 'default' ? `&strategy=${selectedStrategy}` : '';
        const apiUrl = CONFIG.API_URL + `/signals/scan-markets?assets=${assetsToScan}&min_confidence=${CONFIG.MIN_CONFIDENCE}${strategyParam}`;
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
                    
                    log(`📊 ${signals.length} signal(s) from ${data.scanned_assets || '?'} assets`);
                    
                    if (data.success && signals.length > 0) {
                        // Log all signals found
                        signals.forEach((s, i) => {
                            log(`  #${i+1}: ${s.direction} ${s.symbol} (${Math.round(s.confidence)}%)`);
                        });
                        
                        let bestSignal = signals[0];
                        bestSignal._willSwitch = willSwitchAssets;
                        // Store OTHER signals for fallback (excluding best to avoid circular ref)
                        bestSignal._allSignals = signals.slice(1);
                        bestSignal.source = 'BACKEND_OANDA';
                        
                        // Ensure expiration is set from UI timeframe if not in signal
                        if (!bestSignal.expiration_seconds && !bestSignal.expiry) {
                            bestSignal.expiration_seconds = detectCurrentTimeframe();
                        }
                        
                        // Apply Smart Auto-Invert
                        bestSignal = processSmartAutoInvert(bestSignal);
                        
                        // Track trade info for premium result recording
                        lastTradeInfo.symbol = bestSignal.symbol || '';
                        lastTradeInfo.direction = bestSignal.direction || '';
                        lastTradeInfo.confidence = bestSignal.confidence || 0;
                        
                        log(`✅ Best: ${bestSignal.direction} ${bestSignal.symbol} (${Math.round(bestSignal.confidence)}%)${bestSignal._smartInverted ? ' [INVERTED]' : ''}`);
                        
                        executeScanTrade(bestSignal).catch(err => {
                            log(`❌ Trade error: ${err.message}`);
                            updateStatusDot('connected');
                        });
                    } else {
                        log('⚠️ No signals met confidence threshold');
                        updateStatusDot('connected');
                    }
                } catch (e) {
                    log(`❌ Parse error: ${e.message}`);
                    updateStatusDot('connected');
                }
            },
            onerror: function(e) {
                log(`❌ Scan connection error: ${e?.message || 'Unknown'}`);
                log(`   API URL: ${apiUrl.substring(0, 100)}`);
                updateStatusDot('error');
            },
            ontimeout: function() {
                log('❌ Scan timeout (15s)');
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
        
        // Safe stringify to avoid cyclic reference errors
        const safeStringify = (obj) => {
            const seen = new WeakSet();
            return JSON.stringify(obj, (key, value) => {
                if (key === '_allSignals') return '[signals array]'; // Skip to avoid circular ref
                if (typeof value === 'object' && value !== null) {
                    if (seen.has(value)) return '[Circular]';
                    seen.add(value);
                }
                return value;
            }, 2);
        };
        console.log('[GPT executeScanTrade] Signal:', safeStringify(signal));
        
        if (globalTradeLock) {
            log('⏳ BLOCKED: Trade lock active');
            return;
        }

        updateStatusDot('trading');

        // Asset switching disabled - always trade current asset for reliability
        const shouldSwitch = false;
        log(`Trading on current asset (switch disabled for stability)`);
        
        let activeSignal = signal; // The signal we'll actually trade
        
        if (false && shouldSwitch && signal.symbol) {
            const targetNorm = normalizeAsset(signal.symbol);
            const currentAssetNow = getCurrentAsset();
            const currentNorm = normalizeAsset(currentAssetNow);
            
            const targetBase = targetNorm.substring(0, 6);
            const currentBase = currentNorm.substring(0, 6);
            
            if (targetBase !== currentBase) {
                log(`🔄 Best signal is for ${signal.symbol}, currently on ${currentAssetNow}`);
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
                    // FALLBACK: Can't switch assets - try to find a signal for current asset
                    log(`⚠️ Switch failed - looking for signal matching current asset ${currentAssetNow}...`);
                    const allSignals = signal._allSignals || [];
                    
                    if (allSignals.length > 0) {
                        const currentAssetSignal = allSignals.find(s => {
                            const sBase = normalizeAsset(s.symbol).substring(0, 6);
                            return sBase === currentBase;
                        });
                        
                        if (currentAssetSignal) {
                            log(`✅ FALLBACK: Found signal for current asset: ${currentAssetSignal.direction} ${currentAssetSignal.symbol} (${Math.round(currentAssetSignal.confidence)}%)`);
                            activeSignal = currentAssetSignal;
                            // Don't return - continue to execute trade on current asset
                        } else {
                            // No signal for current asset either - try next best regardless
                            log(`⚠️ No signal for ${currentAssetNow}. Trading best signal on current chart anyway.`);
                            // Continue with original signal direction on current asset
                        }
                    } else {
                        log(`⚠️ No fallback signals available. Trading best direction on current chart.`);
                    }
                }
                
                await sleep(500);
            }
        }

        // Determine direction (use activeSignal which may have been changed by fallback)
        let direction = (activeSignal.direction || '').toUpperCase();
        let isCall = direction === 'CALL' || direction === 'BUY' || direction === 'UP';
        
        if (invertEnabled) {
            isCall = !isCall;
            log(`🔄 Inverted → ${isCall ? 'CALL' : 'PUT'}`);
        }

        const finalDirection = isCall ? 'CALL' : 'PUT';
        log(`📊 Placing ${finalDirection} on ${activeSignal.symbol || 'current asset'}...`);
        updateSignalDisplay(finalDirection, activeSignal.symbol, isCall ? 'call' : 'put', '🔍');

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

        // Click trade button - pass expiry for proper outcome timing
        const expirySeconds = signal.expiration_seconds || signal.expiry || signal.expiry_seconds || 60;
        const clicked = clickTradeButton(isCall, 'SCAN', expirySeconds);
        
        if (clicked) {
            incrementTradeCount();
            lastScanTradeTime = Date.now();
            log(`✅ TRADE: ${finalDirection} ${signal.symbol} (${expirySeconds}s expiry)`);
            
            // Store trade info for manual result entry if needed
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
    function clickTradeButton(isCall, source = 'unknown', expirySeconds = 60) {
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
            
            // Mark trade as pending for outcome detection
            // Balance will be captured 2 seconds after click (after bet deduction)
            markTradePending(expirySeconds);
            
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
    // INITIALIZATION - v8.7.0
    // ===========================================
    function init() {
        console.log('[GPT Bot] Starting initialization v8.7.0...');
        
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
            
            // Load saved strategy selection
            selectedStrategy = GM_getValue('selectedStrategy', 'default');
            
            // Load cycle mode state (default off - user must manually enable)
            cycleEnabled = GM_getValue('cycleEnabled', false);
            
            // ===========================================
            // RESTORE AUTO-INVERT STATE (v8.6.4 FIX)
            // ===========================================
            const savedInvertMode = GM_getValue('invertMode', 'off');
            smartAutoInvert.enabled = GM_getValue('smartAutoInvertEnabled', false);
            smartAutoInvert.invertActive = GM_getValue('smartAutoInvertActive', false);
            invertEnabled = GM_getValue('invertEnabled', false);
            
            // Restore lastTradeResult state for streak tracking
            const savedLastTradeResult = GM_getValue('lastTradeResultState', null);
            if (savedLastTradeResult) {
                try {
                    const parsed = JSON.parse(savedLastTradeResult);
                    lastTradeResult.consecutiveWins = parsed.consecutiveWins || 0;
                    lastTradeResult.consecutiveLosses = parsed.consecutiveLosses || 0;
                    lastTradeResult.isWin = parsed.isWin;
                    lastTradeResult.wasInverted = parsed.wasInverted || false;
                } catch(e) {
                    console.log('[GPT Bot] Failed to parse lastTradeResult');
                }
            }
            
            // Sync invertEnabled with smartAutoInvert state
            if (smartAutoInvert.enabled) {
                invertEnabled = smartAutoInvert.invertActive;
            }
            
            // Log restored state
            console.log(`[GPT Bot] Restored Invert Mode: ${savedInvertMode}`);
            console.log(`[GPT Bot] Auto-Invert Enabled: ${smartAutoInvert.enabled}`);
            console.log(`[GPT Bot] Invert Active: ${smartAutoInvert.invertActive}`);
            console.log(`[GPT Bot] Loss Streak: ${lastTradeResult.consecutiveLosses}`);
            
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
            console.log('[GPT Bot] v8.7.2 - Improved Latency Sync + Keltner-MACD 5s');
            
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
            
            // Restore invert mode UI after panel is created
            updateInvertModeUI(savedInvertMode);
            updateInvertDisplay();
            
            manageIntervals();
            
            // Setup trade outcome detection (balance monitor + DOM scanning)
            setupOutcomeDetection();
            
            // Initialize latency display from saved value
            initLatencyDisplay();
            
            // v8.7.2: Sync timing config with backend
            syncTimingWithBackend();
            
            // Start balance sync loop (PO UI scrape + backend API fallback)
            startBalanceSync();
            
            // Resume CYCLE mode if it was saved as enabled
            if (cycleEnabled) {
                cycleAbort = false;
                log('CYCLE: Resuming from saved state');
                updateCycleStatus('Resuming...');
                startCycleLoop();
            }
            
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
    
    // v8.7.2: Sync timing configuration with backend
    async function syncTimingWithBackend() {
        try {
            log('TIMING SYNC: Fetching config from backend...');
            
            const clientTime = Date.now();
            
            // Try to sync with backend
            const response = await fetch(`${CONFIG.API_URL}/signals/timing-config`);
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.success && data.timing) {
                    // Apply timing configuration
                    CONFIG.BET_DEDUCTION_DELAY = data.timing.bet_deduction_delay_ms || 2000;
                    CONFIG.POST_EXPIRY_BUFFER = data.timing.post_expiry_buffer_ms || 3000;
                    CONFIG.BALANCE_POLL_INTERVAL = data.timing.balance_poll_interval_ms || 500;
                    CONFIG.BALANCE_STABILITY_CHECKS = data.timing.balance_stability_checks || 2;
                    CONFIG.MAX_BALANCE_POLLS = data.timing.max_balance_polls || 20;
                    CONFIG.IMMEDIATE_RETRY_DELAY = data.timing.immediate_retry_delay_ms || 1500;
                    
                    // Calculate latency
                    const responseTime = Date.now();
                    const latency = responseTime - clientTime;
                    
                    log(`TIMING SYNC: Success!`);
                    log(`  Bet Deduction Delay: ${CONFIG.BET_DEDUCTION_DELAY}ms`);
                    log(`  Post-Expiry Buffer: ${CONFIG.POST_EXPIRY_BUFFER}ms`);
                    log(`  Balance Poll Interval: ${CONFIG.BALANCE_POLL_INTERVAL}ms`);
                    log(`  Network Latency: ${latency}ms`);
                    log(`  Server Time: ${data.server_time}`);
                    
                    // Adjust for high latency
                    if (latency > 500) {
                        const extraBuffer = Math.min(latency, 2000);
                        CONFIG.POST_EXPIRY_BUFFER += extraBuffer;
                        log(`  High latency detected - adding ${extraBuffer}ms to buffer`);
                    }
                    
                    return true;
                }
            }
            
            log('TIMING SYNC: Using default timing values');
            return false;
            
        } catch (e) {
            log(`TIMING SYNC: Error - ${e.message}`);
            log('TIMING SYNC: Using default timing values');
            return false;
        }
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
