/**
 * Strategy Manager
 * Coordinates multiple strategies and selects best signal.
 * Supports syncing enabled strategies from the app's strategy selection API.
 */

import { log, warn, info } from '../core/logger.js';
import { CONFIG } from '../core/config.js';
import { LocalSignalStrategy } from './localSignal.js';
import { MomentumBusterStrategy } from './momentumBuster.js';
import { HollyCrossoverStrategy } from './hollyCrossover.js';
import { GoldenOneMomentStrategy } from './goldenOneMoment.js';
import { EMA20PullbackReversalStrategy } from './ema20PullbackReversal.js';
import { KeltnerMACDStrategy } from './keltnerMACD.js';
import { IQ720EnsembleStrategy } from './iq720Ensemble.js';
import { FibonacciConfluenceStrategy } from './fibonacciConfluence.js';
import { TripleConfirmationStrategy } from './tripleConfirmation.js';
import { get } from '../utils/api.js';

/**
 * Mapping of app strategy IDs -> Tampermonkey strategy names.
 *
 * Every strategy id that can be returned by the backend
 * `/api/strategies/selected` endpoint MUST be mapped here.
 * IDs whose logic isn't implemented natively in Tampermonkey fall back
 * to `Local Signal Engine` (multi-indicator RSI/Stoch/BB/EMA/candles),
 * which is a safe generic single-strategy execution — this prevents the
 * "no local match → run ALL strategies" spam that used to happen when
 * the backend resolved `'default'` to a concrete winner like
 * `5s_heikin_fractal` (Iter 67).
 *
 * Convention: keep this list synced with
 * /app/backend/strategy_selection_service.py::AVAILABLE_STRATEGIES.
 */
const APP_TO_LOCAL_MAP = {
  // 'default' means the user hasn't picked → keep the historical
  // behaviour of enabling every strategy.
  'default': null,

  // ————— 5s —————
  '5s_heikin_fractal': 'Local Signal Engine',
  'ema20_pullback_reversal': 'EMA 20 Pullback Reversal',
  'holly_crossover_5s': 'Holly Crossover',
  'turbo_precision_5s': 'Local Signal Engine',
  'micro_compression_burst': 'Local Signal Engine',
  'keltner_breakout': 'Local Signal Engine',
  'candlestick_patterns': 'Local Signal Engine',
  'rsi_bb_scalp': 'Local Signal Engine',
  'proven_supertrend': 'Local Signal Engine',

  // ————— 15s —————
  'holly_crossover_15s': 'Holly Crossover',
  'momentum_buster_15s': 'Momentum Buster',
  'starc_cci_reversal': 'Local Signal Engine',
  'macd_histogram': 'Local Signal Engine',
  'stochastic_rsi_combo': 'Local Signal Engine',
  'rsi_volume': 'Local Signal Engine',
  'bollinger_ema': 'Local Signal Engine',
  'macd_rsi': 'Local Signal Engine',
  'proven_rsi': 'Local Signal Engine',

  // ————— 30s —————
  'holly_crossover_30s': 'Holly Crossover',
  'golden_one_moment': 'Golden One Moment',
  '30s_fibonacci_confluence': 'Fibonacci Confluence',
  '30s_triple_confirmation': 'Triple Confirmation',
  'dynamic_ema_rsi': 'Local Signal Engine',
  'otc_reverse': 'Local Signal Engine',
  'psar_fractals': 'Local Signal Engine',
  'stochastic_adx': 'Local Signal Engine',
  'psar_stochastic': 'Local Signal Engine',

  // ————— 1m —————
  '1m_21s_reversal': 'Local Signal Engine',
  '1m_fibonacci_confluence': 'Fibonacci Confluence',
  '1m_triple_confirmation': 'Triple Confirmation',
  'turbo_precision_1m': 'Local Signal Engine',
  '1m_momentum_exhaustion': 'Local Signal Engine',
  '1m_quad_crossover': 'Local Signal Engine',
  'zigzag_double_ma': 'Local Signal Engine',
  'triple_supertrend': 'Local Signal Engine',
  'ema_pullback': 'Local Signal Engine',
  'rsi_sr_reversal': 'Local Signal Engine',
  'triple_confirmation': 'Triple Confirmation',
  'smart_money': 'Local Signal Engine',
  '1m_triple_ema': 'Local Signal Engine',

  // ————— 2m/3m/5m —————
  'ema_macd_trend': 'Local Signal Engine',
  'ichimoku_cci': 'Local Signal Engine',
  'atr_sr': 'Local Signal Engine',
  'cci_rsi': 'Local Signal Engine',
  '5m_fibonacci_confluence': 'Fibonacci Confluence',
  '5m_triple_confirmation': 'Triple Confirmation',
  'vwap_momentum': 'Local Signal Engine',

  // Legacy aliases (older builds / on-disk selections)
  'keltner_macd_5s': 'Keltner-MACD 5s',
  'iq720_ensemble': 'IQ-720 Ensemble',
};

class StrategyManager {
  constructor() {
    this.strategies = new Map();
    this.activeAppStrategyId = null;
    this.forceSingle = false;  // When true, only run the matched strategy
    this.initializeStrategies();
  }
  
  initializeStrategies() {
    this.registerStrategy(new LocalSignalStrategy());
    this.registerStrategy(new KeltnerMACDStrategy());
    this.registerStrategy(new IQ720EnsembleStrategy());
    this.registerStrategy(new HollyCrossoverStrategy());
    this.registerStrategy(new GoldenOneMomentStrategy());
    this.registerStrategy(new MomentumBusterStrategy());
    this.registerStrategy(new EMA20PullbackReversalStrategy());
    // BETA strategies (tracked separately via WinRateWidget + signal.beta flag)
    this.registerStrategy(new FibonacciConfluenceStrategy());
    this.registerStrategy(new TripleConfirmationStrategy());
    
    log(`Initialized ${this.strategies.size} trading strategies`);
  }
  
  registerStrategy(strategy) {
    this.strategies.set(strategy.getName(), strategy);
  }
  
  getStrategy(name) {
    return this.strategies.get(name);
  }
  
  getAllStrategies() {
    return Array.from(this.strategies.values());
  }
  
  getEnabledStrategies() {
    return this.getAllStrategies().filter(s => s.isEnabled());
  }
  
  /**
   * Sync strategy selection from the app API.
   *
   * The Tampermonkey userscript can only run ONE selected strategy at a
   * time; the backend exposes per-timeframe selections. We prefer the
   * user's 5s pick (fastest expiry, most common on PO Blitz), but if that
   * timeframe is set to 'default' / unmapped and another timeframe has a
   * concrete mapping, we use that instead. This makes the panel do
   * something useful for users who only care about 30s or 1m.
   */
  async syncFromApp() {
    try {
      const response = await get('/strategies/selected');

      if (response.success && response.selections) {
        const selections = response.selections || {};
        // Preference order — 5s first (most-used PO timeframe), then
        // the next-fastest expiries.
        const TIMEFRAME_PRIORITY = ['5s', '15s', '30s', '1m', '2m', '3m', '5m'];

        let chosenId = null;
        let chosenTf = null;
        for (const tf of TIMEFRAME_PRIORITY) {
          const sid = selections[tf];
          if (!sid || sid === 'default') continue;
          if (APP_TO_LOCAL_MAP[sid]) {
            chosenId = sid;
            chosenTf = tf;
            break;
          }
        }

        // Nothing mapped explicitly — fall back to the raw 5s value so
        // applyAppSelection can log/handle it (and default → all).
        if (!chosenId) {
          chosenId = selections['5s'] || 'default';
          chosenTf = '5s';
        }

        this.applyAppSelection(chosenId);
        info(`Strategy synced from app (${chosenTf}): ${chosenId}`);
        return true;
      }
    } catch (e) {
      warn(`Strategy sync failed (using all strategies): ${e.message}`);
    }
    return false;
  }
  
  /**
   * Apply app strategy selection
   * @param {string} appStrategyId - The strategy ID from the app
   */
  applyAppSelection(appStrategyId) {
    this.activeAppStrategyId = appStrategyId;
    
    if (appStrategyId === 'default' || !appStrategyId) {
      // Enable all strategies
      this.forceSingle = false;
      for (const s of this.getAllStrategies()) {
        s.setEnabled(true);
      }
      return;
    }
    
    const localName = APP_TO_LOCAL_MAP[appStrategyId];
    
    if (localName) {
      // Enable only the matching local strategy
      this.forceSingle = true;
      for (const s of this.getAllStrategies()) {
        s.setEnabled(s.getName() === localName);
      }
      log(`Strategy locked to: ${localName} (app: ${appStrategyId})`);
    } else {
      // Unknown strategy id (e.g. a custom user-built strategy not yet
      // implemented locally). Instead of enabling every strategy (which
      // pollutes signals and was the reported bug), fall back to the
      // safest generic engine — Local Signal Engine — so the panel keeps
      // producing single, coherent signals.
      this.forceSingle = true;
      const fallbackName = 'Local Signal Engine';
      for (const s of this.getAllStrategies()) {
        s.setEnabled(s.getName() === fallbackName);
      }
      warn(`App strategy "${appStrategyId}" has no local match, falling back to ${fallbackName}`);
    }
  }
  
  /**
   * Analyze candles with enabled strategies
   * @param {Object[]} candles - OHLC data
   * @returns {Object|null} Best signal or null
   */
  analyze(candles) {
    const signals = [];
    
    for (const strategy of this.getEnabledStrategies()) {
      try {
        const signal = strategy.analyze(candles);
        if (signal && signal.confidence >= strategy.getMinConfidence()) {
          signals.push(signal);
        }
      } catch (e) {
        warn(`Strategy ${strategy.getName()} error: ${e.message}`);
      }
    }
    
    if (signals.length === 0) {
      return null;
    }
    
    // Sort by confidence and return best
    signals.sort((a, b) => b.confidence - a.confidence);
    
    // If we're using a single forced strategy, just return its signal
    if (this.forceSingle) {
      return signals[0];
    }
    
    // Check for conflicting signals
    const directions = new Set(signals.map(s => s.direction));
    if (directions.size > 1) {
      const topSignal = signals[0];
      const conflictingSignals = signals.filter(s => s.direction !== topSignal.direction);
      
      if (conflictingSignals.length > 0 && conflictingSignals[0].confidence > topSignal.confidence - 10) {
        log(`Conflicting signals detected, skipping`);
        return null;
      }
    }
    
    return signals[0];
  }
  
  /**
   * Get signal from specific strategy
   */
  analyzeWithStrategy(strategyName, candles) {
    const strategy = this.getStrategy(strategyName);
    if (!strategy || !strategy.isEnabled()) {
      return null;
    }
    return strategy.analyze(candles);
  }
  
  /**
   * Enable/disable strategy by name
   */
  setStrategyEnabled(name, enabled) {
    const strategy = this.getStrategy(name);
    if (strategy) {
      strategy.setEnabled(enabled);
    }
  }
  
  /**
   * Get strategy status
   */
  getStatus() {
    return this.getAllStrategies().map(s => ({
      name: s.getName(),
      enabled: s.isEnabled(),
      minConfidence: s.getMinConfidence(),
    }));
  }
  
  /**
   * Get active app strategy ID
   */
  getActiveAppStrategy() {
    return this.activeAppStrategyId;
  }
}

export const strategyManager = new StrategyManager();
export default strategyManager;
