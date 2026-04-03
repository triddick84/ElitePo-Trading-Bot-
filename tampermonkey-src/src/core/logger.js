/**
 * Logging module
 * Provides unified logging with UI integration
 */

import { state } from './state.js';
import { CONFIG } from './config.js';

const MAX_LOG_ENTRIES = 100;
const logEntries = [];
let logContainer = null;

/**
 * Log levels
 */
export const LogLevel = {
  DEBUG: 'debug',
  INFO: 'info',
  WARN: 'warn',
  ERROR: 'error',
  SUCCESS: 'success',
};

/**
 * Get timestamp string
 * @returns {string} Formatted timestamp
 */
function getTimestamp() {
  return new Date().toLocaleTimeString('en-US', { hour12: false });
}

/**
 * Get emoji for log level
 * @param {string} level - Log level
 * @returns {string} Emoji
 */
function getLevelEmoji(level) {
  const emojis = {
    debug: '🔍',
    info: 'ℹ️',
    warn: '⚠️',
    error: '❌',
    success: '✅',
  };
  return emojis[level] || '📝';
}

/**
 * Get color for log level
 * @param {string} level - Log level
 * @returns {string} CSS color
 */
function getLevelColor(level) {
  const colors = {
    debug: '#888',
    info: '#4fc3f7',
    warn: '#ffd54f',
    error: '#ef5350',
    success: '#66bb6a',
  };
  return colors[level] || '#fff';
}

/**
 * Main log function
 * @param {string} message - Log message
 * @param {string} level - Log level
 */
export function log(message, level = LogLevel.INFO) {
  const timestamp = getTimestamp();
  const emoji = getLevelEmoji(level);
  const color = getLevelColor(level);
  
  // Console log
  const consoleMsg = `[GPT Bot ${timestamp}] ${emoji} ${message}`;
  if (level === LogLevel.ERROR) {
    console.error(consoleMsg);
  } else if (level === LogLevel.WARN) {
    console.warn(consoleMsg);
  } else if (CONFIG.DEBUG || level !== LogLevel.DEBUG) {
    console.log(consoleMsg);
  }
  
  // Store entry
  const entry = { timestamp, message, level, emoji, color };
  logEntries.unshift(entry);
  
  // Trim old entries
  if (logEntries.length > MAX_LOG_ENTRIES) {
    logEntries.pop();
  }
  
  // Update UI if container exists
  updateLogUI(entry);
}

/**
 * Update log UI
 * @param {Object} entry - Log entry
 */
function updateLogUI(entry) {
  // logContainer is set via setLogContainer() from the shadow DOM
  // Do NOT fall back to document.getElementById since the log element lives in a shadow root
  if (logContainer && state.ui.logExpanded) {
    const logLine = document.createElement('div');
    logLine.style.cssText = `
      font-size: 11px;
      padding: 2px 4px;
      border-bottom: 1px solid rgba(255,255,255,0.1);
      color: ${entry.color};
    `;
    logLine.textContent = `${entry.timestamp} ${entry.emoji} ${entry.message}`;
    
    // Insert at top
    if (logContainer.firstChild) {
      logContainer.insertBefore(logLine, logContainer.firstChild);
    } else {
      logContainer.appendChild(logLine);
    }
    
    // Limit displayed entries
    while (logContainer.children.length > 50) {
      logContainer.removeChild(logContainer.lastChild);
    }
  }
}

/**
 * Set log container element
 * @param {HTMLElement} container - Log container element
 */
export function setLogContainer(container) {
  logContainer = container;
}

/**
 * Get all log entries
 * @returns {Array} Log entries
 */
export function getLogEntries() {
  return [...logEntries];
}

/**
 * Clear log entries
 */
export function clearLog() {
  logEntries.length = 0;
  if (logContainer) {
    logContainer.innerHTML = '';
  }
}

// Convenience functions
export const debug = (msg) => log(msg, LogLevel.DEBUG);
export const info = (msg) => log(msg, LogLevel.INFO);
export const warn = (msg) => log(msg, LogLevel.WARN);
export const error = (msg) => log(msg, LogLevel.ERROR);
export const success = (msg) => log(msg, LogLevel.SUCCESS);

export default log;
