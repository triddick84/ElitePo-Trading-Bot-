/**
 * Trade Executor
 * Handles trade execution with cooldowns, validation, and smart inversion
 */

import { CONFIG } from '../core/config.js';
import { state, setState, recordTradeResult, recordAssetResult, saveState } from '../core/state.js';
import { log, success, error, warn, info } from '../core/logger.js';
import { executeTrade, setTradeAmount, getCurrentAsset, getPayout } from '../utils/dom.js';
import { reportTrade, recordPremiumResult } from '../utils/api.js';
import { smartInvert } from './smartInvert.js';

class TradeExecutor {
  constructor() {
    this.pendingTrades = [];
    this.tradeHistory = [];
  }
  
  /**
   * Check if trading is allowed (cooldown check)
   * @param {string} source - 'scan' or 'app'
   * @returns {boolean}
   */
  canTrade(source = 'scan') {
    const now = Date.now();
    const cooldown = source === 'scan' ? CONFIG.TRADE_COOLDOWN_SCAN : CONFIG.TRADE_COOLDOWN_APP;
    const lastTrade = source === 'scan' ? state.lastScanTradeTime : state.lastAppTradeTime;
    
    if (now - lastTrade < cooldown) {
      const remaining = Math.ceil((cooldown - (now - lastTrade)) / 1000);
      log(`Cooldown active: ${remaining}s remaining`);
      return false;
    }
    
    return true;
  }
  
  /**
   * Validate signal before execution
   * @param {Object} signal - Signal object
   * @returns {boolean}
   */
  validateSignal(signal) {
    if (!signal) {
      warn('No signal provided');
      return false;
    }
    
    if (!signal.direction || !['CALL', 'PUT'].includes(signal.direction.toUpperCase())) {
      warn(`Invalid direction: ${signal.direction}`);
      return false;
    }
    
    if (signal.confidence < CONFIG.MIN_CONFIDENCE) {
      log(`Signal confidence ${signal.confidence}% below minimum ${CONFIG.MIN_CONFIDENCE}%`);
      return false;
    }
    
    const payout = getPayout();
    if (payout < CONFIG.MIN_PAYOUT) {
      warn(`Payout ${payout}% below minimum ${CONFIG.MIN_PAYOUT}%`);
      return false;
    }
    
    return true;
  }
  
  /**
   * Execute a trade (with smart inversion applied)
   * @param {Object} signal - Signal to trade
   * @param {string} source - 'scan' or 'app'
   * @returns {Promise<boolean>} Success
   */
  async execute(signal, source = 'scan') {
    if (!this.validateSignal(signal)) {
      return false;
    }
    
    if (!this.canTrade(source)) {
      return false;
    }
    
    if (!state.autoTradeEnabled) {
      log('Auto-trade disabled, signal received but not executed');
      return false;
    }
    
    try {
      const originalDirection = signal.direction.toUpperCase();
      
      // Apply smart inversion
      const direction = smartInvert.applyInversion(originalDirection);
      
      const amount = state.moneyManagement.currentAmount;
      const asset = getCurrentAsset();
      
      if (direction !== originalDirection) {
        info(`Executing INVERTED ${direction} (original: ${originalDirection}) on ${asset} @ $${amount}`);
      } else {
        log(`Executing ${direction} trade on ${asset} @ $${amount} (${signal.confidence}%)`);
      }
      
      setTradeAmount(amount);
      const executed = await executeTrade(direction, amount);
      
      if (executed) {
        const now = Date.now();
        setState('lastTradeTime', now);
        
        if (source === 'scan') {
          setState('lastScanTradeTime', now);
        } else {
          setState('lastAppTradeTime', now);
        }
        
        const trade = {
          timestamp: new Date().toISOString(),
          asset,
          direction,
          originalDirection,
          amount,
          confidence: signal.confidence,
          strategy: signal.strategy || 'Unknown',
          source,
          payout: getPayout(),
          wasInverted: direction !== originalDirection,
        };
        
        this.tradeHistory.push(trade);
        this.pendingTrades.push(trade);
        
        // Store as last trade for result matching
        state.lastTrade = trade;
        
        success(`Trade executed: ${direction} ${asset} @ $${amount}${trade.wasInverted ? ' [INVERTED]' : ''}`);
        
        reportTrade(trade).catch(e => {
          warn(`Failed to report trade: ${e.message}`);
        });
        
        return true;
      } else {
        error('Failed to execute trade - button click failed');
        return false;
      }
    } catch (e) {
      error(`Trade execution error: ${e.message}`);
      return false;
    }
  }
  
  /**
   * Record trade result with premium tracking and smart inversion evaluation
   * @param {boolean} isWin - Whether trade was won
   */
  recordResult(isWin) {
    // Core stats
    recordTradeResult(isWin);
    
    // Get the trade we're recording for. Priority: pending trade > last executed trade > last signal
    const trade = this.pendingTrades.length > 0 ? this.pendingTrades.shift() : state.lastTrade;
    const lastSignal = state.lastSignal || {};
    const asset = trade?.asset || lastSignal.symbol || getCurrentAsset() || 'UNKNOWN';
    const direction = trade?.direction || lastSignal.direction || 'UNKNOWN';
    const confidence = trade?.confidence || lastSignal.confidence || 0;
    
    if (trade) {
      trade.result = isWin ? 'WIN' : 'LOSS';
      trade.resultTime = new Date().toISOString();
    }
    
    log(`Recording ${isWin ? 'WIN' : 'LOSS'}: ${asset} ${direction} (conf: ${confidence})`);
    
    // Record per-asset history (for smart inversion)
    recordAssetResult(asset, direction, isWin);
    
    // Record inverted result tracking
    smartInvert.recordInvertedResult(isWin);
    
    // Send to backend premium result tracker (fire-and-forget)
    recordPremiumResult(asset, direction, isWin, confidence).then(resp => {
      if (resp.success && resp.updated_stats) {
        const stats = resp.updated_stats;
        log(`Premium tracking: Asset WR ${stats.asset_win_rate}% (${stats.asset_total_trades} trades), Hour WR ${stats.hour_win_rate}%`);
      }
    }).catch(() => {
      // Silently fail - don't block trading
    });
    
    // Money management
    if (isWin) {
      state.moneyManagement.currentStep = 0;
      state.moneyManagement.currentAmount = state.moneyManagement.baseAmount;
      if (trade) {
        state.moneyManagement.totalProfit += trade.amount * (trade.payout / 100);
      }
    } else {
      if (state.moneyManagement.currentStep < CONFIG.MAX_MARTINGALE_STEPS) {
        state.moneyManagement.currentStep++;
        state.moneyManagement.currentAmount = Math.min(
          CONFIG.MAX_TRADE_AMOUNT,
          state.moneyManagement.currentAmount * CONFIG.MARTINGALE_MULTIPLIER
        );
      }
      if (trade) {
        state.moneyManagement.totalProfit -= trade.amount;
      }
    }
    
    log(`Trade result: ${isWin ? 'WIN' : 'LOSS'} | Streak: ${state.stats.currentStreak} | Profit: $${state.moneyManagement.totalProfit.toFixed(2)}`);
    
    // Evaluate smart inversion AFTER recording the result
    smartInvert.evaluateInversion(asset);
    
    // Save state after each result
    saveState();
  }
  
  /**
   * Get trade history
   * @param {number} limit - Maximum entries
   * @returns {Object[]}
   */
  getHistory(limit = 50) {
    return this.tradeHistory.slice(-limit);
  }
  
  /**
   * Get pending trade count
   * @returns {number}
   */
  getPendingCount() {
    return this.pendingTrades.length;
  }
  
  /**
   * Reset money management
   */
  resetMoneyManagement() {
    state.moneyManagement.currentStep = 0;
    state.moneyManagement.currentAmount = state.moneyManagement.baseAmount;
    log('Money management reset');
  }
  
  /**
   * Set base trade amount
   * @param {number} amount
   */
  setBaseAmount(amount) {
    state.moneyManagement.baseAmount = amount;
    state.moneyManagement.currentAmount = amount;
    log(`Base amount set to $${amount}`);
  }
}

export const tradeExecutor = new TradeExecutor();

export default tradeExecutor;
