/**
 * Configuration module for GPT Signal Bot
 * Central configuration for all bot settings
 */

export const CONFIG = {
  // API Settings
  API_URL: 'https://ai-broker-dev.preview.emergentagent.com/api',
  
  // Polling Intervals
  APP_POLL_INTERVAL: 3000,      // 3 seconds for app signals
  SCAN_INTERVAL: 5000,          // 5 seconds for scanning
  
  // Trade Cooldowns
  TRADE_COOLDOWN_SCAN: 30000,   // 30 seconds between SCAN trades
  TRADE_COOLDOWN_APP: 5000,     // 5 seconds between APP trades
  
  // Signal Thresholds
  MIN_CONFIDENCE: 65,
  MIN_PAYOUT: 65,
  
  // Feature Flags
  DEBUG: true,
  USE_LOCAL_SIGNALS: true,      // Generate signals locally using actual OTC prices
  LOCAL_CANDLE_COUNT: 50,       // Number of candles to analyze
  
  // Money Management
  DEFAULT_TRADE_AMOUNT: 1,
  MAX_TRADE_AMOUNT: 100,
  MARTINGALE_MULTIPLIER: 2.5,
  MAX_MARTINGALE_STEPS: 3,
  
  // Data Collection
  DATA_COLLECTION_ENABLED: false,
  DATA_SEND_INTERVAL: 60000,    // Send data every 60 seconds
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
