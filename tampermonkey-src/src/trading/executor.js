/**
 * Trade Executor
 * Handles trade execution with cooldowns and validation
 */

import { CONFIG } from '../core/config.js';
import { state, setState, recordTradeResult } from '../core/state.js';
import { log, success, error, warn } from '../core/logger.js';
import { executeTrade, setTradeAmount, getCurrentAsset, getPayout } from '../utils/dom.js';
import { reportTrade } from '../utils/api.js';

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
   * Execute a trade
   * @param {Object} signal - Signal to trade
   * @param {string} source - 'scan' or 'app'
   * @returns {Promise<boolean>} Success
   */
  async execute(signal, source = 'scan') {
    // Validate
    if (!this.validateSignal(signal)) {
      return false;
    }
    
    // Check cooldown
    if (!this.canTrade(source)) {
      return false;
    }
    
    // Check if auto-trade is enabled
    if (!state.autoTradeEnabled) {
      log('Auto-trade disabled, signal received but not executed');
      return false;
    }
    
    try {
      const direction = signal.direction.toUpperCase();
      const amount = state.moneyManagement.currentAmount;
      const asset = getCurrentAsset();
      
      log(`Executing ${direction} trade on ${asset} @ $${amount} (${signal.confidence}%)`);
      
      // Set amount and execute
      setTradeAmount(amount);
      const executed = await executeTrade(direction, amount);
      
      if (executed) {
        // Update state
        const now = Date.now();
        setState('lastTradeTime', now);
        
        if (source === 'scan') {
          setState('lastScanTradeTime', now);
        } else {
          setState('lastAppTradeTime', now);
        }
        
        // Store trade info
        const trade = {
          timestamp: new Date().toISOString(),
          asset,
          direction,
          amount,
          confidence: signal.confidence,
          strategy: signal.strategy || 'Unknown',
          source,
          payout: getPayout(),
        };
        
        this.tradeHistory.push(trade);
        this.pendingTrades.push(trade);
        
        success(`Trade executed: ${direction} ${asset} @ $${amount}`);
        
        // Report to backend
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
   * Record trade result
   * @param {boolean} isWin - Whether trade was won
   */
  recordResult(isWin) {
    recordTradeResult(isWin);
    
    if (this.pendingTrades.length > 0) {
      const trade = this.pendingTrades.shift();
      trade.result = isWin ? 'WIN' : 'LOSS';
      trade.resultTime = new Date().toISOString();
      
      // Update money management
      if (isWin) {
        state.moneyManagement.currentStep = 0;
        state.moneyManagement.currentAmount = state.moneyManagement.baseAmount;
        state.moneyManagement.totalProfit += trade.amount * (trade.payout / 100);
      } else {
        // Martingale
        if (state.moneyManagement.currentStep < CONFIG.MAX_MARTINGALE_STEPS) {
          state.moneyManagement.currentStep++;
          state.moneyManagement.currentAmount = Math.min(
            CONFIG.MAX_TRADE_AMOUNT,
            state.moneyManagement.currentAmount * CONFIG.MARTINGALE_MULTIPLIER
          );
        }
        state.moneyManagement.totalProfit -= trade.amount;
      }
      
      log(`Trade result: ${isWin ? 'WIN' : 'LOSS'} | Streak: ${state.stats.currentStreak} | Profit: $${state.moneyManagement.totalProfit.toFixed(2)}`);
    }
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

// Singleton instance
export const tradeExecutor = new TradeExecutor();

export default tradeExecutor;
