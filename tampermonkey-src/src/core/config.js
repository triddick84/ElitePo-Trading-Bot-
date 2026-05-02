/**
 * Configuration module for AI's Elite PO Traders Bot
 * Central configuration for all bot settings
 */

export const CONFIG = {
  // Bot Info
  BOT_NAME: "AI's Elite PO Traders Bot",
  // Sourced from /app/tampermonkey-src/version.txt at build time so the
  // @version in the userscript header and BOT_VERSION here can never drift.
  BOT_VERSION: typeof __SCRIPT_VERSION__ !== 'undefined' ? __SCRIPT_VERSION__ : '0.0.0-dev',

  // API Settings
  API_URL: 'https://pocket-option-ai-9.preview.emergentagent.com/api',
  
  // Polling Intervals
  APP_POLL_INTERVAL: 3000,
  SCAN_INTERVAL: 5000,
  
  // Trade Cooldowns
  TRADE_COOLDOWN_SCAN: 30000,
  TRADE_COOLDOWN_APP: 5000,
  
  // Signal Thresholds
  MIN_CONFIDENCE: 65,
  MIN_PAYOUT: 65,
  
  // Feature Flags
  DEBUG: true,
  USE_LOCAL_SIGNALS: true,
  LOCAL_CANDLE_COUNT: 50,
  
  // Money Management
  DEFAULT_TRADE_AMOUNT: 1,
  MAX_TRADE_AMOUNT: 100,
  MARTINGALE_MULTIPLIER: 2.5,
  MAX_MARTINGALE_STEPS: 3,
  
  // Data Collection
  DATA_COLLECTION_ENABLED: false,
  DATA_SEND_INTERVAL: 60000,

  // Auto-Invert System
  AUTO_INVERT_ENABLED: true,
  INVERT_AFTER_CONSECUTIVE_LOSSES: 2,
  INVERT_COOLDOWN_MS: 10000,
  INVERT_MAX_INVERTED_TRADES: 5,
  LOSS_MEMORY_SIZE: 10,

  // CYCLE Mode
  CYCLE_ENABLED: false,
  CYCLE_DWELL_TIME: 30000,
  CYCLE_ASSETS: [
    'EURUSD_OTC', 'GBPUSD_OTC', 'USDJPY_OTC', 'AUDUSD_OTC',
    'EURJPY_OTC', 'GBPJPY_OTC', 'AUDCAD_OTC', 'NZDUSD_OTC',
    'CADCHF_OTC', 'EURGBP_OTC',
  ],
};

/**
 * Update configuration at runtime
 * @param {Object} newConfig - Partial config to merge
 */
export function updateConfig(newConfig) {
  Object.assign(CONFIG, newConfig);
}

/**
 * Get current API URL
 * @returns {string} API URL
 */
export function getApiUrl() {
  return CONFIG.API_URL;
}

export default CONFIG;
