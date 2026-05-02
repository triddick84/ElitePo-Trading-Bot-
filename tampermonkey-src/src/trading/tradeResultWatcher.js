/**
 * Trade Result Watcher
 * --------------------
 * Auto-detects WIN/LOSS for placed trades using THREE independent sources
 * combined for high confidence:
 *
 *   1. MutationObserver on closed-deals/history panel — fires when a new
 *      deal row is appended, parses outcome class/text/profit-sign.
 *   2. Balance delta — polls `getAccountBalance()` every 1s; balance UP
 *      vs pre-trade snapshot = WIN, balance unchanged from post-deduct = LOSS.
 *   3. DOM scan via existing `scanDOMForTradeResult()` — toast/notification
 *      and deals-list scrape fallback.
 *
 * The first source to confirm wins. Resolves once per arm; timeout after
 * `expiry + 10s` auto-fires LOSS-or-skip per config.
 *
 * Wires directly into `tradeExecutor.recordResult(isWin, {autoResolved:true})`
 * which already drives stats, smartInvert, /api/trades/outcome, etc.
 */

import { log, info, warn, success, error } from '../core/logger.js';
import { getAccountBalance, scanDOMForTradeResult } from '../utils/dom.js';
import { tradeExecutor } from './executor.js';

const POLL_INTERVAL_MS = 800;
const SAFETY_BUFFER_MS = 4_000;          // wait this long after expiry before declaring TIMEOUT
const ABANDON_AFTER_TIMEOUT = false;     // if true, count timeouts as LOSS; otherwise just skip

class TradeResultWatcher {
  constructor() {
    this.enabled = false;
    this.observer = null;
    this.pollId = null;
    this.armed = null;        // { trade, preBalance, deadline, resolved }
    this.lastDealsHash = '';  // detect new deal-rows
  }

  enable() {
    if (this.enabled) return;
    this.enabled = true;
    this._installObserver();
    success('[ResultWatcher] enabled — auto-detecting WIN/LOSS via DOM mutations + balance + scan');
  }

  disable() {
    if (!this.enabled) return;
    this.enabled = false;
    if (this.observer) { this.observer.disconnect(); this.observer = null; }
    if (this.pollId) { clearInterval(this.pollId); this.pollId = null; }
    this.armed = null;
  }

  isEnabled() { return this.enabled; }

  /**
   * Arm the watcher to resolve the next outcome event for `trade`.
   * Caller passes the trade object that was just placed.
   * @param {Object} trade - { asset, direction, amount, expirySeconds, ... }
   */
  armResolver(trade) {
    if (!this.enabled) return;
    if (!trade) return;

    // Bump global fire count + update active-asset indicator on the panel.
    // Imported lazily to avoid a circular dep with ui/panel.js.
    try {
      // eslint-disable-next-line no-undef
      const w = (typeof window !== 'undefined') ? window : null;
      if (w && typeof w.__eliteBotIncFireCount === 'function') {
        w.__eliteBotIncFireCount(trade.asset);
      }
    } catch (_e) { /* ignore */ }

    // Cancel any prior arm
    this._clearArm('superseded');

    const expirySec = Number(trade.expirySeconds) || 5;
    this.armed = {
      trade,
      preBalance: 0,
      armedAt: Date.now(),
      deadline: Date.now() + (expirySec * 1000) + SAFETY_BUFFER_MS,
      resolved: false,
    };

    // Snapshot balance ~1.2s post-place (after bet deducted)
    setTimeout(() => {
      if (!this.armed || this.armed.trade !== trade) return;
      this.armed.preBalance = getAccountBalance();
      log(`[ResultWatcher] armed for ${trade.direction} ${trade.asset} expires=${expirySec}s preBalance=${this.armed.preBalance}`);
    }, 1_200);

    // Start polling loop if not already
    if (!this.pollId) {
      this.pollId = setInterval(() => this._poll(), POLL_INTERVAL_MS);
    }
  }

  // -- Internals ------------------------------------------------------------

  _installObserver() {
    if (this.observer) return;
    try {
      this.observer = new MutationObserver(() => {
        if (!this.armed || this.armed.resolved) return;

        // v8.56.0: HARD expiry gate — never resolve a trade before its
        // actual expiry. Previous versions let any DOM mutation (a prior
        // trade's result animation, a toast, etc.) fire a premature
        // WIN/LOSS, poisoning the auto-invert engine with outcomes from
        // trades that hadn't closed yet.
        const now = Date.now();
        const expiryMs = (this.armed.trade.expirySeconds || 5) * 1000;
        const tradeExpiresAt = this.armed.armedAt + expiryMs;
        // Require a small grace period AFTER expiry before we trust any
        // DOM/toast signal — PO sometimes refreshes the deals panel during
        // placement and those mutations look like outcomes.
        const MIN_GRACE_MS = 1_000;
        if (now < tradeExpiresAt + MIN_GRACE_MS) return;

        // Throttle: scanDOMForTradeResult is ~10ms, can run on every batch
        const isWin = scanDOMForTradeResult();
        if (isWin === true) this._resolve(true, 'mutation-scan');
        else if (isWin === false) this._resolve(false, 'mutation-scan');
      });
      this.observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: false,
        characterData: false,
      });
    } catch (e) {
      warn(`[ResultWatcher] could not install MutationObserver: ${e.message}`);
    }
  }

  _poll() {
    if (!this.armed) {
      // No active arm — stop the poll loop until next armResolver()
      clearInterval(this.pollId);
      this.pollId = null;
      return;
    }
    if (this.armed.resolved) return;

    // Don't try to resolve before the trade has actually expired
    const now = Date.now();
    const tradeExpiresAt = this.armed.armedAt + (this.armed.trade.expirySeconds || 5) * 1000;
    if (now < tradeExpiresAt) return;

    // 1. DOM scan (deals list / toast)
    const domResult = scanDOMForTradeResult();
    if (domResult === true) return this._resolve(true, 'dom-scan');
    if (domResult === false) return this._resolve(false, 'dom-scan');

    // 2. Balance delta
    if (this.armed.preBalance > 0) {
      const cur = getAccountBalance();
      if (cur > 0) {
        if (cur > this.armed.preBalance + 0.005) return this._resolve(true, 'balance-up');
        // LOSS = balance unchanged from post-deduct snapshot
        if (Math.abs(cur - this.armed.preBalance) < 0.005) {
          // Wait until at least 2s past expiry to be confident
          if (now > tradeExpiresAt + 2_000) return this._resolve(false, 'balance-flat');
        }
      }
    }

    // 3. Timeout
    if (now > this.armed.deadline) {
      warn(`[ResultWatcher] timeout for ${this.armed.trade.direction} ${this.armed.trade.asset} — no result detected`);
      if (ABANDON_AFTER_TIMEOUT) {
        this._resolve(false, 'timeout-loss');
      } else {
        this._clearArm('timeout');
      }
    }
  }

  _resolve(isWin, source) {
    if (!this.armed || this.armed.resolved) return;
    this.armed.resolved = true;
    const t = this.armed.trade;
    success(`[ResultWatcher] ${isWin ? '✓ WIN' : '✗ LOSS'} on ${t.direction} ${t.asset} (via ${source})`);
    try {
      // Forward to executor; this triggers stats, asset-history, smartInvert,
      // and POSTs /api/trades/outcome via the existing recordResult chain.
      tradeExecutor.recordResult(isWin, { autoResolved: true });
    } catch (e) {
      error(`[ResultWatcher] recordResult failed: ${e.message}`);
    }
    this._clearArm('resolved');
  }

  _clearArm(reason) {
    if (this.armed) log(`[ResultWatcher] arm cleared (${reason})`);
    this.armed = null;
  }
}

export const tradeResultWatcher = new TradeResultWatcher();
export default tradeResultWatcher;
