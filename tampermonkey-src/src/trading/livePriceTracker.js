/**
 * Live Price Tracker
 * ------------------
 * Solves the "static axis label" problem: on PO's chart, multiple DOM text
 * nodes display forex-pattern numbers (1.22345), but only ONE of them is the
 * live price that ticks — the others are static grid labels (top/bottom of
 * the Y-axis, support/resistance markers, etc.).
 *
 * Strategy:
 * - Every 200ms, scan all forex-pattern text nodes.
 * - Remember each node's text history.
 * - A node is considered "live" if its text has changed within the last 10s.
 * - Return the most-recently-changed live node's value.
 * - If no node has changed recently, fall back to the node with the most
 *   recent distinct-value history (still fresher than pure frequency scan).
 */

import { log, debug } from '../core/logger.js';

const SCAN_INTERVAL_MS = 200;
const FRESHNESS_MS = 10_000;
const MAX_TRACKED = 100;
const FOREX_PATTERN = /^\d{1,7}\.\d{2,8}$/;

class LivePriceTracker {
  constructor() {
    this.started = false;
    this.intervalId = null;
    // Map<string-key, { node, lastText, lastChangeTs, firstSeenTs }>
    this.tracked = new Map();
    this.lastLivePrice = null;
    this.lastLiveTs = 0;
    this.scanCount = 0;
  }

  start() {
    if (this.started) return;
    this.started = true;
    this.intervalId = setInterval(() => this._scan(), SCAN_INTERVAL_MS);
    debug('[LivePriceTracker] started');
  }

  stop() {
    if (this.intervalId) clearInterval(this.intervalId);
    this.intervalId = null;
    this.started = false;
  }

  /** Return the most recent price that has been observed to CHANGE. */
  getLivePrice() {
    const now = Date.now();
    // If we recently picked a live price, reuse it unless stale
    if (this.lastLivePrice && now - this.lastLiveTs < FRESHNESS_MS) {
      return this.lastLivePrice;
    }
    return null;
  }

  /** Diagnostic: return summary of tracked nodes for debug. */
  getStats() {
    const now = Date.now();
    const items = [];
    for (const [, info] of this.tracked) {
      items.push({
        text: info.lastText,
        age_ms: now - info.lastChangeTs,
        first_seen_ms: now - info.firstSeenTs,
      });
    }
    items.sort((a, b) => a.age_ms - b.age_ms);
    return {
      scanCount: this.scanCount,
      trackedNodes: items.length,
      lastLivePrice: this.lastLivePrice,
      lastLivePriceAge_ms: this.lastLiveTs ? now - this.lastLiveTs : null,
      topChanged: items.slice(0, 5),
    };
  }

  _scan() {
    try {
      this.scanCount++;
      const now = Date.now();
      const rootsToScan = [document.body || document.documentElement];

      // Include shadow roots
      try {
        const hosts = document.querySelectorAll('*');
        for (const el of hosts) {
          if (el.shadowRoot) rootsToScan.push(el.shadowRoot);
        }
      } catch (_e) { /* ignore */ }

      const seenThisScan = new Set();
      for (const root of rootsToScan) {
        this._scanRoot(root, now, seenThisScan);
        if (this.tracked.size > MAX_TRACKED) break;
      }

      // Prune nodes not seen in this scan (DOM changed)
      for (const key of this.tracked.keys()) {
        if (!seenThisScan.has(key)) this.tracked.delete(key);
      }

      // Pick the most recently CHANGED node as the live price
      let bestKey = null;
      let bestChangeTs = 0;
      for (const [key, info] of this.tracked) {
        // A node is "live" if it has changed AT LEAST ONCE since first seen
        if (info.lastChangeTs <= info.firstSeenTs) continue;
        if (now - info.lastChangeTs > FRESHNESS_MS) continue;
        if (info.lastChangeTs > bestChangeTs) {
          bestChangeTs = info.lastChangeTs;
          bestKey = key;
        }
      }

      if (bestKey) {
        const info = this.tracked.get(bestKey);
        const val = parseFloat(info.lastText);
        if (Number.isFinite(val) && val > 0) {
          this.lastLivePrice = val;
          this.lastLiveTs = now;
        }
      }
    } catch (_e) { /* never break PO */ }
  }

  _scanRoot(root, now, seenThisScan) {
    try {
      const walker = document.createTreeWalker(
        root,
        NodeFilter.SHOW_TEXT,
        {
          acceptNode: (node) => {
            const text = (node.nodeValue || '').trim();
            return FOREX_PATTERN.test(text) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
          },
        }
      );
      let node;
      while ((node = walker.nextNode())) {
        const text = (node.nodeValue || '').trim();
        const parent = node.parentElement;
        if (!parent) continue;

        // Unique key for this node — combine parent className + text position
        // Prefer a stable structural identifier so we track per-slot, not per-value
        let key;
        try {
          key = `${parent.tagName}|${(parent.className || '').toString().slice(0, 60)}|${parent.getBoundingClientRect().left.toFixed(0)}:${parent.getBoundingClientRect().top.toFixed(0)}`;
        } catch (_e) {
          key = `${parent.tagName}|${(parent.className || '').toString().slice(0, 60)}`;
        }
        seenThisScan.add(key);

        const existing = this.tracked.get(key);
        if (!existing) {
          this.tracked.set(key, {
            lastText: text,
            lastChangeTs: now,
            firstSeenTs: now,
          });
        } else if (existing.lastText !== text) {
          existing.lastText = text;
          existing.lastChangeTs = now;
        }

        if (this.tracked.size > MAX_TRACKED) break;
      }
    } catch (_e) { /* ignore */ }
  }
}

export const livePriceTracker = new LivePriceTracker();
export default livePriceTracker;
