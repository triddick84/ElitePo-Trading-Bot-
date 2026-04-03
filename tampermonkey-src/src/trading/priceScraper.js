/**
 * Price Scraper
 * Scrapes live prices from Pocket Option UI
 */

import { log, debug } from '../core/logger.js';
import { getCurrentPrice, getCurrentAsset } from '../utils/dom.js';

class PriceScraper {
  constructor() {
    this.candles = [];
    this.maxCandles = 200;
    this.currentCandle = null;
    this.candleStartTime = 0;
    this.candleInterval = 5000; // 5 second candles
    this.scrapeInterval = null;
    this.lastPrice = null;
    this.tickCount = 0;
  }
  
  /**
   * Start price scraping
   * @param {number} interval - Scrape interval in ms
   */
  start(interval = 500) {
    if (this.scrapeInterval) {
      this.stop();
    }
    
    log('Price scraper started');
    
    this.scrapeInterval = setInterval(() => {
      this.scrape();
    }, interval);
  }
  
  /**
   * Stop price scraping
   */
  stop() {
    if (this.scrapeInterval) {
      clearInterval(this.scrapeInterval);
      this.scrapeInterval = null;
      log('Price scraper stopped');
    }
  }
  
  /**
   * Scrape current price and update candles
   */
  scrape() {
    const price = getCurrentPrice();
    if (!price || price === this.lastPrice) return;
    
    this.lastPrice = price;
    this.tickCount++;
    
    const now = Date.now();
    
    // Check if we need to start a new candle
    if (!this.currentCandle || now - this.candleStartTime >= this.candleInterval) {
      // Save completed candle
      if (this.currentCandle) {
        this.candles.push(this.currentCandle);
        
        // Trim old candles
        if (this.candles.length > this.maxCandles) {
          this.candles.shift();
        }
      }
      
      // Start new candle
      this.currentCandle = {
        timestamp: new Date(now).toISOString(),
        open: price,
        high: price,
        low: price,
        close: price,
        volume: 1,
      };
      this.candleStartTime = now;
    } else {
      // Update current candle
      this.currentCandle.high = Math.max(this.currentCandle.high, price);
      this.currentCandle.low = Math.min(this.currentCandle.low, price);
      this.currentCandle.close = price;
      this.currentCandle.volume++;
    }
  }
  
  /**
   * Get candles
   * @param {number} count - Number of candles to return
   * @returns {Object[]}
   */
  getCandles(count = 50) {
    // Include current candle if it exists
    const allCandles = this.currentCandle 
      ? [...this.candles, this.currentCandle]
      : this.candles;
    
    return allCandles.slice(-count);
  }
  
  /**
   * Get current price
   * @returns {number|null}
   */
  getCurrentPrice() {
    return this.lastPrice;
  }
  
  /**
   * Get tick count
   * @returns {number}
   */
  getTickCount() {
    return this.tickCount;
  }
  
  /**
   * Clear candle history
   */
  clear() {
    this.candles = [];
    this.currentCandle = null;
    this.tickCount = 0;
    log('Price history cleared');
  }
  
  /**
   * Set candle timeframe
   * @param {number} seconds - Candle duration in seconds
   */
  setCandleInterval(seconds) {
    this.candleInterval = seconds * 1000;
    log(`Candle interval set to ${seconds}s`);
  }
}

// Singleton instance
export const priceScraper = new PriceScraper();

export default priceScraper;
