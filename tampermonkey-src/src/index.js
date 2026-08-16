/*
 * AI's Elite PO Traders Bot v8.0.0
 * Main entry point - coordinates all modules
 */

import { CONFIG } from './core/config.js';
import { state, setState, loadState, saveState, resetStats } from './core/state.js';
import { log, info, warn, success, error } from './core/logger.js';
import { createPanel, initPanelEvents, updateStatsDisplay, updateInvertDisplay, updateStatusDot, cleanupPanel, populateStrategies, setStrategyTf, getStrategyTf, update21sReversalDisplay, set51sTimingSlider, updateActiveAsset, setToggleActive, setSignalPreview, updateStatusStrip, updateLiveCountdown, updateNetworkLatency, setSnsDirectionMode, setChartTypeManual, setInvertThreshold, updateAITab, setLatencyAbstainThreshold, setLatencyAbstainState } from './ui/panel.js';
import { strategyManager } from './strategies/manager.js';
import { tradeExecutor } from './trading/executor.js';
import { tradeResultWatcher } from './trading/tradeResultWatcher.js';
import { smartInvert } from './trading/smartInvert.js';
import { twentyOneSecondReversal } from './strategies/twentyOneSecondReversal.js';
import { ssidBridge, poLivePrice } from './trading/ssidBridge.js';
import { liveTickPoster } from './trading/liveTickPoster.js';
import { livePriceTracker } from './trading/livePriceTracker.js';
import { favoritesCycle } from './trading/favoritesCycle.js';
import { chartTypeSwitcher } from './trading/chartTypeSwitcher.js';
import { appSignalPoller } from './trading/appSignalPoller.js';
import { networkLatencyPoller } from './trading/networkLatencyPoller.js';
import { heartbeatReporter } from './trading/heartbeatReporter.js';
import { aiAnalysisPoller } from './trading/aiAnalysisPoller.js';
import { latencyAbstainGate } from './trading/latencyAbstainGate.js';
import { scanMarkets } from './utils/api.js';
import { get, post } from './utils/api.js';
import { getCurrentAsset, getCurrentPrice, waitForElement } from './utils/dom.js';
import * as domUtils from './utils/dom.js';
import { priceScraper } from './trading/priceScraper.js';

// Iter 62 — build query string for per-model thresholds (skips zeros)
function buildThresholdQuery() {
  try {
    const t = state.modelThresholds || {};
    const parts = [];
    const push = (key, paramName) => {
      const v = Number(t[key] || 0);
      if (v > 0) parts.push(`${paramName}=${v}`);
    };
    push('confluence', 'min_conf_confluence');
    push('improved_v2', 'min_conf_improved_v2');
    push('maximized_v3', 'min_conf_maximized_v3');
    push('iq720', 'min_conf_iq720');
    return parts.length ? '&' + parts.join('&') : '';
  } catch (_e) {
    return '';
  }
}

// Install the SSID bridge IMMEDIATELY at module load — before any async init.
// This wraps window.WebSocket so we can capture the first PO auth frame.
// Must run before PO opens its trading socket.
ssidBridge.install();

// Iter 58 — Live tick poster: subscribe to PO's WS price stream and
// aggregate 5s OHLC candles, then POST to /api/signals/collect-otc-candles.
// This keeps `otc_candles_5s.source='po_live'` fresh so ML training sees
// the actual PO microstructure (spreads/liquidity differ from OANDA backfill).
liveTickPoster.start();

class EliteTradingBot {
  constructor() {
    this.initialized = false;
    this.scanInterval = null;
    this.statsInterval = null;
    this.dataCollectionInterval = null;
  }
  
  async init() {
    log(`Initializing ${CONFIG.BOT_NAME} v${CONFIG.BOT_VERSION}...`);
    
    // Wait for page to be interactive
    await waitForElement('body', 15000);
    
    // Small delay to let PO finish rendering
    await new Promise(r => setTimeout(r, 2000));
    
    // Load saved state
    loadState();
    
    // Register smart-invert UI callback
    smartInvert.onInvertChange((isInverted, reason) => {
      updateInvertDisplay(isInverted, reason);
    });
    
    // Create and inject UI panel
    this.createUI();
    
    // Start price scraper
    priceScraper.start(500);

    // Enable global auto-WIN/LOSS detector (mutation-observer + balance-delta + DOM scan)
    tradeResultWatcher.enable();
    
    // Sync strategy selection from app + populate dropdown
    await this.loadStrategies();
    
    // Start stats update interval
    this.statsInterval = setInterval(() => {
      updateStatsDisplay();
      // Refresh status strip from live state every second — cheap, idempotent
      try {
        updateStatusStrip({
          scan: state.scanEnabled,
          auto: state.autoTradeEnabled,
          ainv: state.autoInvertEnabled,
          r21s: !!state._twentyOneSEnabled,
          cycle: state.cycleEnabled,
        });
      } catch (_e) { /* ignore */ }
      // v8.51.0: Live PO candle-countdown readout in status strip so the
      // user can visually confirm Time Strategy is reading PO's timer.
      try {
        const cd = twentyOneSecondReversal.getLiveCountdown?.();
        if (cd) updateLiveCountdown(cd);
      } catch (_e) { /* ignore */ }
    }, 500);

    // Active-asset indicator: refresh every 1.5s from current PO chart
    this._fireCount = 0;
    this.assetIndicatorInterval = setInterval(() => {
      try {
        const cur = getCurrentAsset();
        if (cur) updateActiveAsset(cur, this._fireCount);
      } catch (_e) { /* ignore */ }
    }, 1_500);

    // Live signal-quality preview poller — gives the user a "should I press
    // GO?" cue right above the GO button (Iter 55, Apr 25, 2026).
    this.startSignalPreview();

    // Iter 103 — Network latency poller (updates the Live-tab widget)
    try {
      networkLatencyPoller.start(updateNetworkLatency);
    } catch (_e) { /* non-fatal — widget just stays "—" */ }

    // Iter 106 — Heartbeat reporter (feeds the app's Mobile Auto-Trader
    // connection dashboard so the user can tell if TM is alive without
    // waiting for a trade to fail).
    try {
      heartbeatReporter.start();
    } catch (_e) { /* non-fatal */ }

    // Iter 107 — AI Analysis poller (feeds the new AI tab)
    try {
      aiAnalysisPoller.start(updateAITab);
    } catch (_e) { /* non-fatal */ }

    // Iter 108 — Tick the latency abstain gate every 4s so the state chip
    // reflects reality even when nothing else calls isPaused().
    try {
      this._latAbstainInterval = setInterval(() => {
        try { latencyAbstainGate.isPaused(); } catch (_e) { /* silent */ }
      }, 4000);
    } catch (_e) { /* ignore */ }

    // Allow tradeResultWatcher to bump the count on every arm (= every fire)
    window.__eliteBotIncFireCount = (asset) => {
      try {
        this._fireCount = (this._fireCount || 0) + 1;
        updateActiveAsset(asset || getCurrentAsset() || null, this._fireCount);
      } catch (_e) { /* ignore */ }
    };

    // Periodic auto-save every 15s so stats/inversion/asset-history persist
    // even if the user never clicks a toggle between reloads
    this.autoSaveInterval = setInterval(() => {
      try {
        // Keep config mirrors fresh in case they were tuned via console
        if (twentyOneSecondReversal.config) {
          state._twentyOneSConfig = { ...twentyOneSecondReversal.config };
        }
        state._twentyOneSEnabled = twentyOneSecondReversal.isEnabled();
        saveState();
      } catch (_e) { /* ignore */ }
    }, 15_000);

    // Also save on every page-hide / before-unload — last line of defence
    // when PO triggers a hard refresh or SPA navigation that bypasses our
    // cleanup() handler.
    const flushSave = () => {
      try {
        state._twentyOneSEnabled = twentyOneSecondReversal.isEnabled();
        if (twentyOneSecondReversal.config) state._twentyOneSConfig = { ...twentyOneSecondReversal.config };
        saveState();
      } catch (_e) { /* ignore */ }
    };
    window.addEventListener('pagehide', flushSave, true);
    window.addEventListener('beforeunload', flushSave, true);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') flushSave();
    }, true);
    
    // Restore inversion display from saved state
    if (state.inversion.isInverted) {
      updateInvertDisplay(true, state.inversion.reason);
    }

    // Restore toggle states from saved state (persists across PO reloads)
    this._restoreToggleStates();

    this.initialized = true;
    updateStatusDot('connected');
    success(`${CONFIG.BOT_NAME} initialized successfully`);
    
    // Log available strategies
    const strategies = strategyManager.getStatus();
    info(`Loaded ${strategies.length} strategies: ${strategies.map(s => s.name).join(', ')}`);
  }
  
  createUI() {
    console.log('[Elite Bot] createUI called, appending to body...');
    const panelHost = createPanel();
    document.body.appendChild(panelHost);
    console.log('[Elite Bot] Panel appended to body. Visible:', panelHost.offsetWidth > 0);
    
    initPanelEvents({
      onScanToggle: (enabled) => {
        state.scanEnabled = enabled;
        if (enabled) {
          this.startScanning();
        } else {
          this.stopScanning();
        }
        saveState();
      },
      onAutoToggle: (enabled) => {
        state.autoTradeEnabled = enabled;
        log(`Auto-trade ${enabled ? 'enabled' : 'disabled'}`);
        saveState();
      },
      onGo: () => {
        this.executeSingleScan();
      },
      onInvertToggle: () => {
        smartInvert.manualToggle();
        saveState();
      },
      onStrategyChange: async (strategyId) => {
        log(`Strategy changed to: ${strategyId}`);
        state._selectedStrategy = strategyId;
        strategyManager.applyAppSelection(strategyId);
        saveState();
        try {
          const tf = state._selectedStrategyTf || getStrategyTf() || '5s';
          await post('/strategies/select', { timeframe: tf, strategy_id: strategyId });
          info(`Strategy "${strategyId}" (${tf}) synced to server`);
        } catch (e) {
          warn(`Failed to sync strategy to server: ${e.message}`);
        }
      },
      // Iter 96 — TF change: reload the strategy list for the picked TF
      onStrategyTfChange: async (tf) => {
        log(`Strategy timeframe changed to: ${tf}`);
        state._selectedStrategyTf = tf;
        saveState();
        try {
          await this.loadStrategies(tf);
        } catch (e) {
          warn(`Failed to reload strategies for ${tf}: ${e.message}`);
        }
      },
      onWin: () => {
        tradeExecutor.recordResult(true);
        twentyOneSecondReversal.onResultRecorded(true);
        updateStatsDisplay();
        if (twentyOneSecondReversal.isEnabled()) {
          update21sReversalDisplay(true, twentyOneSecondReversal.getStats());
        }
        saveState();
      },
      onLoss: () => {
        tradeExecutor.recordResult(false);
        twentyOneSecondReversal.onResultRecorded(false);
        updateStatsDisplay();
        if (twentyOneSecondReversal.isEnabled()) {
          update21sReversalDisplay(true, twentyOneSecondReversal.getStats());
        }
        saveState();
      },
      on21sReversalToggle: (enabled) => {
        if (enabled) {
          twentyOneSecondReversal.enable();
        } else {
          twentyOneSecondReversal.disable();
        }
        state._twentyOneSEnabled = enabled;
        state._twentyOneSConfig = { ...twentyOneSecondReversal.config };
        update21sReversalDisplay(enabled, enabled ? twentyOneSecondReversal.getStats() : null);
        saveState();
      },
      on51sTimingChange: (secondsLeft) => {
        const ms = Math.max(5_000, Math.min(55_000, secondsLeft * 1000));
        twentyOneSecondReversal.setConfig({ fireAtMsLeft: ms });
        state._twentyOneSConfig = { ...twentyOneSecondReversal.config };
        info(`[51s] Timing changed → fire at ${secondsLeft}s left`);
        saveState();
      },

      // Iter 104 — SNS Direction Mode: fire WITH or AGAINST current 1m candle body
      onSnsDirectionModeChange: (mode) => {
        const withCandle = mode === 'with';
        // twentyOneSecondReversal's config.invertSignal semantics:
        //   invertSignal:false → strategy's native contrarian pick (AGAINST the candle body)
        //   invertSignal:true  → swap CALL↔PUT → fires WITH the candle body
        twentyOneSecondReversal.setConfig({ invertSignal: withCandle });
        state._twentyOneSConfig = { ...twentyOneSecondReversal.config };
        state._snsDirectionMode = mode;
        info(`[SNS] Direction mode → ${withCandle ? 'WITH candle' : 'AGAINST candle'}`);
        saveState();
      },

      // Iter 107 — Manual chart type override (Config tab dropdown).
      // 'auto' → clear override, defer to the app's config.
      // Anything else → immediately ask chartTypeSwitcher to switch PO's chart.
      onChartTypeManualChange: (value) => {
        state._chartTypeManual = value || 'auto';
        try {
          if (value && value !== 'auto') {
            chartTypeSwitcher.ensure(value).catch((e) => {
              warn(`[chartType] manual switch to ${value} threw: ${e.message}`);
            });
            info(`[chartType] manual override → ${value}`);
          } else {
            info('[chartType] manual override cleared — following app');
          }
        } catch (e) { warn(`[chartType] manual change error: ${e.message}`); }
        saveState();
      },

      // Iter 107 — Auto-Invert threshold slider (1..5). Updates both the
      // "how many losses to flip" AND the "how many to flip back" thresholds
      // so the sensitivity is symmetric.
      onInvertThresholdChange: (n) => {
        const val = Math.max(1, Math.min(5, parseInt(n, 10) || 1));
        CONFIG.INVERT_AFTER_CONSECUTIVE_LOSSES = val;
        CONFIG.INVERT_REVERT_AFTER_LOSSES = val;
        state._invertThreshold = val;
        info(`[AutoInvert] threshold → ${val} loss${val > 1 ? 'es' : ''} (activate + revert both)`);
        saveState();
      },

      // Iter 108 — Latency-Driven Abstain threshold (0..1000 ms; 0 = OFF).
      // Persisted to state so it survives reloads. The gate itself lives in
      // latencyAbstainGate.js and is queried by appSignalPoller before every
      // trade.
      onLatencyAbstainThresholdChange: (n) => {
        const val = Math.max(0, Math.min(1000, parseInt(n, 10) || 0));
        latencyAbstainGate.setThreshold(val);
        state._latencyAbstainThreshold = val;
        info(`[LatAbstain] threshold → ${val === 0 ? 'OFF' : val + 'ms'}`);
        saveState();
      },
      onAmountChange: (amount) => {
        tradeExecutor.setBaseAmount(amount);
        saveState();
      },

      onCycleToggle: async (enabled) => {
        state.cycleEnabled = enabled;
        // Iter 98 — CYCLE now rotates a user-TAUGHT favorites bar (see
        // favoritesCycle.js). If the user hasn't taught yet, the module
        // logs an error and returns false — the button stays visually ON
        // but nothing rotates. UI shows a nudge to click "🎓 Teach".
        if (enabled) {
          const ok = favoritesCycle.start();
          if (!ok) {
            state.cycleEnabled = false;
            // Iter 101 — Also flip the visual toggle back OFF so the user
            // immediately sees CYCLE didn't actually start (previously the
            // button stayed green + user assumed rotation was running).
            try { setToggleActive('cycle', false); } catch (_e) { /* ignore */ }
            warn('[CYCLE] cannot start — click "🎓 Teach Favorites" in Config tab first');
          }
        } else {
          favoritesCycle.stop();
        }
        saveState();
      },

      onTeachFavorites: () => {
        // Iter 98 — Enter point-to-teach mode for the favorites bar.
        favoritesCycle.startTeach((result) => {
          if (result && result.success) {
            success(`[TEACH] ✓ Favorites bar captured (${result.data.tileCount} tiles). Toggle CYCLE to start rotating.`);
          }
        });
      },

      onClearTaughtFavorites: () => {
        favoritesCycle.clearTeachData();
      },

      onCycleIntervalChange: (ms) => {
        favoritesCycle.setInterval(ms);
      },

      // Iter 99 — Chart-type teach mode
      onTeachChartType: () => {
        chartTypeSwitcher.startTeach((result) => {
          if (result && result.success) {
            success(`[TEACH] ✓ Chart-type menu captured (${result.data.childCount} buttons). TM will now sync PO's chart on each signal.`);
          }
        });
      },

      onClearTaughtChartType: () => {
        chartTypeSwitcher.clearTeachData();
      },

      onAppSignalToggle: (enabled) => {
        state.appSignalEnabled = enabled;
        if (enabled) {
          appSignalPoller.start(5_000);
        } else {
          appSignalPoller.stop();
        }
        saveState();
      },

      onAutoInvertToggle: (enabled) => {
        state.autoInvertEnabled = enabled;
        log(`Auto-invert ${enabled ? 'ENABLED' : 'DISABLED'} - smart-invert decisions will ${enabled ? 'apply' : 'be bypassed'}`);
        saveState();
      },

      onResetStats: () => {
        // Reset W/L counters, streak, P/L, and Time-strategy stats (v8.45.0)
        resetStats();
        state.moneyManagement.currentStep = 0;
        state.moneyManagement.currentAmount = state.moneyManagement.baseAmount || 1;
        state.moneyManagement.totalProfit = 0;
        try { twentyOneSecondReversal.resetStats?.(); } catch (_e) { /* optional */ }
        updateStatsDisplay();
        if (twentyOneSecondReversal.isEnabled()) {
          update21sReversalDisplay(true, twentyOneSecondReversal.getStats());
        }
        success('[STATS] Reset — W/L, rate, streak, P/L cleared');
        saveState();
      },
    });
  }
  
  async loadStrategies(tf) {
    try {
      // Iter 96 — accept `tf` from the TF picker so users can browse
      // strategies per timeframe. Falls back to the last-picked TF, then 5s.
      const selectedTf = tf || state._selectedStrategyTf || '5s';
      state._selectedStrategyTf = selectedTf;
      // Reflect the TF in the dropdown (idempotent — safe on repeat call)
      try { setStrategyTf(selectedTf); } catch (_e) { /* UI may not exist yet */ }

      // Fetch available strategies from API for the chosen TF
      const available = await get(`/strategies/available/${selectedTf}`);
      const strategies = available.strategies || [];

      // Fetch the server's last-known selection (multi-device fallback)
      const selected = await get('/strategies/selected');
      const serverId = selected.selections?.[selectedTf] || 'default';

      // v8.72.0 — Local saved strategy wins. Previously the panel always
      // adopted the server's `/strategies/selected` value on every page
      // load, silently discarding whatever the user had picked locally
      // (which is also saved via GM_setValue → state._selectedStrategy).
      // Now we honor the local choice if it still exists in the available
      // list, and re-sync it to the server so other devices catch up.
      const localId = state._selectedStrategy;
      const localExists = !!localId && (
        localId === 'default' ||
        strategies.some((s) => s.id === localId)
      );
      const selectedId = localExists ? localId : serverId;

      // Populate dropdown UI with the resolved selection
      populateStrategies(strategies, selectedId);

      // Apply selection locally
      strategyManager.applyAppSelection(selectedId);

      // Persist the resolved value so subsequent reloads stay sticky
      state._selectedStrategy = selectedId;
      saveState();

      // If local diverged from server, push our pick back up (fire-and-forget)
      if (localExists && localId !== serverId) {
        try {
          await post('/strategies/select', { timeframe: selectedTf, strategy_id: selectedId });
          info(`[Restore] Re-synced local strategy "${selectedId}" (${selectedTf}) to server (was "${serverId}")`);
        } catch (e) {
          warn(`Failed to re-sync strategy to server: ${e.message}`);
        }
      }

      info(`Strategies loaded for ${selectedTf}: ${strategies.length} available, active: ${selectedId}${localExists ? ' (from local save)' : ' (from server)'}`);
    } catch (e) {
      warn(`Strategy load failed (using all): ${e.message}`);
      // Even on API failure, honor the local pick if we have one
      if (state._selectedStrategy) {
        try {
          strategyManager.applyAppSelection(state._selectedStrategy);
          info(`[Restore] API offline — applied locally-saved strategy "${state._selectedStrategy}"`);
        } catch (_e) { /* ignore */ }
      }
    }
  }

  /**
   * Restore persisted toggle states after UI is ready.
   * Runs after loadState() + createUI() so we can both read the saved values
   * AND mutate the visual state of the newly-created buttons.
   */
  _restoreToggleStates() {
    const restored = [];
    try {
      // SCAN toggle
      if (state.scanEnabled) {
        setToggleActive('scan', true);
        this.startScanning();
        restored.push('SCAN');
      }

      // AUTO toggle
      if (state.autoTradeEnabled) {
        setToggleActive('auto', true);
        restored.push('AUTO');
      }

      // AUTO-INVERT toggle (default ON if never saved)
      if (state.autoInvertEnabled) {
        setToggleActive('ainv', true);
        restored.push('A-INV');
      }

      // CYCLE toggle
      if (state.cycleEnabled) {
        setToggleActive('cycle', true);
        // Iter 98 — CYCLE now uses favoritesCycle exclusively.
        // Guard: only auto-restart if a favorites container was previously taught.
        try {
          if (favoritesCycle.getTeachData()) {
            favoritesCycle.start();
            restored.push('CYCLE');
          } else {
            // No teach data yet — turn the visual toggle back OFF so the user
            // isn't confused by a "green" button that isn't cycling anything.
            setToggleActive('cycle', false);
            state.cycleEnabled = false;
            warn('[Restore] CYCLE was ON but no favorites container is taught — turned OFF. Click "🎓 Teach Favorites" then re-enable.');
          }
        } catch (_e) { /* ignore */ }
      }

      // APP signal poller toggle
      if (state.appSignalEnabled) {
        setToggleActive('app', true);
        appSignalPoller.start(5_000);
        restored.push('APP');
      }

      // 21S Reversal
      if (state._twentyOneSConfig) {
        twentyOneSecondReversal.setConfig(state._twentyOneSConfig);
      }
      // Restore the timing slider visual to whatever was saved
      try {
        const savedMs = state._twentyOneSConfig?.fireAtMsLeft ?? 49_000;
        set51sTimingSlider(Math.round(savedMs / 1000));
      } catch (_e) { /* ignore */ }
      // Iter 104 — Restore SNS direction mode button visual
      try {
        const mode = state._snsDirectionMode
          || (state._twentyOneSConfig?.invertSignal ? 'with' : 'against');
        setSnsDirectionMode(mode);
      } catch (_e) { /* ignore */ }
      // Iter 107 — Restore manual chart-type override + auto-invert threshold
      try {
        setChartTypeManual(state._chartTypeManual || 'auto');
      } catch (_e) { /* ignore */ }
      try {
        const thr = Math.max(1, Math.min(5, parseInt(state._invertThreshold, 10) || 1));
        CONFIG.INVERT_AFTER_CONSECUTIVE_LOSSES = thr;
        CONFIG.INVERT_REVERT_AFTER_LOSSES = thr;
        setInvertThreshold(thr);
      } catch (_e) { /* ignore */ }
      // Iter 108 — Restore latency-abstain threshold + register UI subscriber
      try {
        const savedLat = parseInt(state._latencyAbstainThreshold, 10);
        const thr = Number.isFinite(savedLat) ? Math.max(0, Math.min(1000, savedLat)) : 300;
        latencyAbstainGate.setThreshold(thr);
        setLatencyAbstainThreshold(thr);
        latencyAbstainGate.register(setLatencyAbstainState);
      } catch (_e) { /* ignore */ }

      // v8.72.0 — Restore the MM trade-amount input value from saved
      // state.moneyManagement.baseAmount so the field doesn't reset to $1
      // on every page reload. Previously the HTML default `value="1"` won
      // because nothing was syncing the saved baseAmount back into the DOM.
      try {
        const amtEl = document.getElementById('__epb__amt');
        const savedAmt = Number(state.moneyManagement?.baseAmount);
        if (amtEl && isFinite(savedAmt) && savedAmt > 0) {
          amtEl.value = String(savedAmt);
        }
      } catch (_e) { /* ignore */ }
      // Seconds Number Strategy — Iter 64: respect the user's saved toggle.
      // (Previously hard-locked ON at startup; user requested explicit on/off.)
      if (state._twentyOneSEnabled) {
        twentyOneSecondReversal.enable();
        update21sReversalDisplay(true, twentyOneSecondReversal.getStats());
        restored.push('SNS');
      } else {
        twentyOneSecondReversal.disable();
        update21sReversalDisplay(false, twentyOneSecondReversal.getStats());
      }

      // Loud, visible summary so any persistence gap is immediately obvious
      if (restored.length > 0) {
        const ageMin = state._lastSavedAt
          ? Math.round((Date.now() - state._lastSavedAt) / 60000)
          : '?';
        success(
          `[Restore] Re-activated ${restored.length} feature(s) from saved state ` +
          `(saved ${ageMin}m ago): ${restored.join(', ')}`
        );
      } else {
        info('[Restore] No previously-active features found in saved state');
      }
    } catch (e) {
      warn(`[Restore] toggle state restoration failed: ${e.message}`);
    }
  }
  
  startScanning() {
    if (this.scanInterval) return;
    
    log('Starting market scan...');
    updateStatusDot('scanning');
    
    this.scanInterval = setInterval(async () => {
      await this.performScan();
    }, CONFIG.SCAN_INTERVAL);
    
    // Run immediately
    this.performScan();
  }
  
  stopScanning() {
    if (this.scanInterval) {
      clearInterval(this.scanInterval);
      this.scanInterval = null;
    }
    updateStatusDot('connected');
    log('Scanning stopped');
  }

  /**
   * Live signal-quality preview poller (v8.46.0, May 2026).
   * Polls /signals/force-generate-v2 every 3s for the current asset and
   * paints quality + direction + confidence + ML/strategy participation
   * into the preview row above GO so the user can decide whether it's
   * worth pulling the trigger.
   *
   * v8.46.0 upgrades:
   *  - Poll cadence 8s → 3s (debounced, skips overlapping requests)
   *  - Surfaces ML model count + total strategies evaluated
   *  - Asset-change watcher triggers an immediate refetch on switch
   *  - Freshness pulse animation on every successful update
   *  - Age ticker (visible between polls) shows data freshness
   */
  startSignalPreview() {
    if (this.previewInterval) return;
    const POLL_MS = 3000;
    const ABORT_MS = 5500;     // give up if a request hangs longer than this
    let inFlight = false;
    let lastAsset = null;
    let lastUpdateTs = 0;
    let lastSignal = null;

    const tick = async (reason = 'tick') => {
      if (inFlight) return;  // skip overlapping requests
      const asset = getCurrentAsset();
      if (!asset) {
        setSignalPreview({ error: 'no asset' });
        return;
      }
      // Asset changed — invalidate preview immediately for visual feedback
      if (asset !== lastAsset) {
        lastAsset = asset;
        lastSignal = null;
        setSignalPreview({ direction: '', confidence: 0, quality: 'LOW', agreeing: 0, fresh: false, ageSec: 0 });
      }
      inFlight = true;
      const startedAt = Date.now();
      // Hard timeout to avoid stuck in-flight blocking the next tick
      const timeoutId = setTimeout(() => {
        if (inFlight) { inFlight = false; }
      }, ABORT_MS);
      try {
        const resp = await post(`/signals/force-generate-v2?asset=${encodeURIComponent(asset)}&expiry_seconds=60${buildThresholdQuery()}`, {});
        const sig = resp?.signal;
        if (sig) {
          // Count ML model contributions among components
          let mlCount = 0;
          try {
            const comps = sig.components || {};
            for (const k of Object.keys(comps)) {
              const v = comps[k];
              if (k.includes('ml') || k.includes('ML') || v?.model_accuracy != null) {
                if ((v?.direction || '').toUpperCase() === sig.direction) mlCount++;
              }
            }
          } catch (_e) { /* ignore */ }

          const latencyMs = Date.now() - startedAt;
          lastUpdateTs = Date.now();
          lastSignal = {
            direction: sig.direction,
            confidence: sig.confidence,
            quality: sig.quality,
            agreeing: sig.agreeing_strategies,
            mlCount,
            evaluated: resp.strategies_evaluated || Object.keys(sig.components || {}).length,
            votes: sig.votes,
            latencyMs,
            fresh: true,
            ageSec: 0,
            // v8.55.0: BOTAI-inspired abstain gate surfaced to the UI so
            // the user sees at a glance when GO would refuse to fire.
            abstain: sig.abstain === true,
            abstainThreshold: sig.abstain_threshold,
            // v8.61.0 / Iter 56b — abstain source (strategy > asset > default > latency)
            // and server-side generation latency block (Iter 55). Coloured chips in
            // the panel preview let the user inspect threshold tier + processing time
            // at a glance.
            abstainSource: sig.abstain_source,
            serverLatencyMs: (sig.latency && sig.latency.total_ms) || null,
            serverLatencyBudgetMs: (sig.latency && sig.latency.budget_ms) || null,
          };
          setSignalPreview(lastSignal);
        } else {
          setSignalPreview({ error: 'no signal' });
        }
      } catch (e) {
        setSignalPreview({ error: 'offline' });
      } finally {
        clearTimeout(timeoutId);
        inFlight = false;
      }
    };

    // Kick off immediately, then on interval
    tick('initial');
    this.previewInterval = setInterval(() => tick('poll'), POLL_MS);

    // Asset-change watcher — fires an extra refetch within ~250ms of any
    // chart switch (CYCLE rotation, manual click, picker switch). Cheap
    // string compare every 250ms.
    this.previewAssetWatcher = setInterval(() => {
      try {
        const cur = getCurrentAsset();
        if (cur && cur !== lastAsset) {
          lastAsset = cur;
          tick('asset-change');
        }
      } catch (_e) { /* ignore */ }
    }, 250);

    // Age ticker — refreshes the "fresh / Xs old" stamp every 1s without
    // hitting the network. Lets the user see at a glance whether the
    // displayed signal is stale.
    this.previewAgeTicker = setInterval(() => {
      if (!lastSignal || !lastUpdateTs) return;
      const ageSec = Math.round((Date.now() - lastUpdateTs) / 1000);
      lastSignal.ageSec = ageSec;
      // Iter 63 — Negative latency offset widens the freshness window.
      // e.g. offset = -5 lets a signal stay "fresh" for up to 7 seconds.
      const _offset = Number(state.latencyOffsetSec || 0);
      const freshBudget = 2 + Math.max(0, -_offset);
      lastSignal.fresh = ageSec < freshBudget;
      setSignalPreview(lastSignal);
    }, 1000);
  }

  stopSignalPreview() {
    if (this.previewInterval) {
      clearInterval(this.previewInterval);
      this.previewInterval = null;
    }
    if (this.previewAssetWatcher) {
      clearInterval(this.previewAssetWatcher);
      this.previewAssetWatcher = null;
    }
    if (this.previewAgeTicker) {
      clearInterval(this.previewAgeTicker);
      this.previewAgeTicker = null;
    }
  }
  
  async executeSingleScan() {
    info('[GO] Force scan triggered - generating HIGH-ACCURACY signal NOW...');
    try {
      const asset = getCurrentAsset();
      if (!asset) {
        warn('[GO] Could not detect current asset - is a pair selected in PO?');
        return;
      }

      // Call the new force-generate-v2 endpoint — always returns a signal
      log(`[GO] Calling force-generate-v2 for ${asset}...`);
      const resp = await post(`/signals/force-generate-v2?asset=${encodeURIComponent(asset)}&expiry_seconds=60${buildThresholdQuery()}`, {});

      if (!resp || !resp.signal) {
        warn('[GO] force-generate returned no signal - falling back to standard scan');
        await this.performScan({ force: true });
        return;
      }

      const signal = resp.signal;
      state.lastSignal = {
        direction: signal.direction,
        symbol: signal.symbol || asset,
        confidence: signal.confidence,
        strategy: signal.strategy,
      };

      info(
        `[GO] SIGNAL: ${signal.direction} ${signal.symbol || asset} @ ${signal.confidence}% ` +
        `[${signal.quality || 'N/A'}] | confluence=${signal.confluence_score} ` +
        `| agreeing=${signal.agreeing_strategies || 0}/${Object.keys(signal.components || {}).length} ` +
        `| strategy=${signal.strategy}`
      );
      if (signal.reason) log(`[GO] Reason: ${signal.reason}`);
      if (signal.quality === 'LOW') {
        warn('[GO] LOW-quality signal — weak strategy participation. Consider passing.');
      }

      // v8.55.0: BOTAI-inspired abstain gate. Backend's /api/ml/abstain/optimize
      // has tuned a per-asset confidence threshold; any signal below it is
      // marked `abstain=true` and we refuse to fire. Raises win-rate by
      // trading only on high-confidence setups.
      if (signal.abstain === true) {
        warn(
          `[GO] ABSTAIN — confidence ${signal.confidence}% < threshold ${signal.abstain_threshold}% ` +
          `(${signal.abstain_reason || 'below-threshold'})`
        );
        warn('[GO] No trade fired. Use /api/ml/abstain/optimize to re-tune or /api/ml/abstain/threshold to override.');
        return;
      }

      // Always execute via tradeExecutor in force mode (bypasses AUTO gate)
      await tradeExecutor.execute(signal, 'go-force');
    } catch (e) {
      error(`[GO] force-generate error: ${e.message}`);
      console.error('[GO stack]', e);
      // Ultimate fallback — try the old scan path
      try { await this.performScan({ force: true }); } catch (_e) { /* ignore */ }
    }
  }

  async performScan(opts = {}) {
    const isForce = !!opts.force;
    try {
      const asset = getCurrentAsset();
      if (!asset) {
        warn(isForce
          ? '[GO] Could not detect current asset - is a pair selected in PO?'
          : 'Could not detect current asset'
        );
        return;
      }

      // Try local signal generation first
      if (CONFIG.USE_LOCAL_SIGNALS) {
        const candles = priceScraper.getCandles(CONFIG.LOCAL_CANDLE_COUNT);

        if (candles && candles.length >= 30) {
          const signal = strategyManager.analyze(candles);

          if (signal) {
            signal.symbol = asset;
            signal.source = 'local';
            state.lastSignal = { direction: signal.direction, symbol: asset, confidence: signal.confidence, strategy: signal.strategy };

            info(`[${isForce ? 'GO' : 'SCAN'}] Local signal: ${signal.direction} ${asset} @ ${signal.confidence}% [${signal.strategy}]`);

            if (isForce || state.autoTradeEnabled) {
              await tradeExecutor.execute(signal, isForce ? 'go-force' : 'scan');
            } else if (!state.autoTradeEnabled) {
              warn(`[SCAN] Local signal ${signal.direction} ${asset} @ ${signal.confidence}% generated but AUTO is OFF — no trade placed. Enable AUTO to let SCAN fire trades.`);
            }
            return;
          } else if (isForce) {
            log(`[GO] Local candles OK (${candles.length}) but no local strategy produced a signal; trying backend API...`);
          }
        } else if (isForce) {
          log(`[GO] Only ${candles ? candles.length : 0} local candles available (need 30+); falling back to backend API scan...`);
        }
      }

      // Fallback to API scan
      if (isForce) {
        log(`[GO] Querying backend API for ${asset} at min_confidence=${CONFIG.MIN_CONFIDENCE}%...`);
      }
      const response = await scanMarkets([asset], CONFIG.MIN_CONFIDENCE);

      if (!response) {
        if (isForce) warn('[GO] Backend API returned no response (network/CORS issue?)');
        return;
      }
      if (!response.success) {
        if (isForce) warn(`[GO] Backend API rejected scan: ${response.error || 'unknown'}`);
        return;
      }
      if (!response.top_signals || response.top_signals.length === 0) {
        if (isForce) {
          warn(`[GO] Backend API returned no signals (scanned=${response.scanned || 0}, min_conf=${CONFIG.MIN_CONFIDENCE}%). Try lowering MIN_CONFIDENCE or wait for higher confidence setup.`);
        }
        return;
      }

      const signal = response.top_signals[0];
      state.lastSignal = { direction: signal.direction, symbol: signal.symbol || asset, confidence: signal.confidence, strategy: signal.strategy || 'API' };

      info(`[${isForce ? 'GO' : 'SCAN'}] API signal: ${signal.direction} ${signal.symbol || asset} @ ${signal.confidence}% [${signal.strategy || 'API'}]`);

      if (isForce || state.autoTradeEnabled) {
        await tradeExecutor.execute(signal, isForce ? 'go-force' : 'scan');
      } else if (!state.autoTradeEnabled) {
        warn(`[SCAN] Signal generated but AUTO is OFF — no trade placed. Click the AUTO button to let SCAN actually fire trades. (Or use GO for one-shot force-execute.)`);
      }
    } catch (e) {
      error(`[${isForce ? 'GO' : 'Scan'}] error: ${e.message}`);
      console.error('[Scan stack]', e);
    }
  }
  
  startDataCollection() {
    if (this.dataCollectionInterval) return;
    
    setState('dataCollectionEnabled', true);
    log('Data collection started');
    
    this.dataCollectionInterval = setInterval(() => {
      this.collectAndSendData();
    }, CONFIG.DATA_SEND_INTERVAL);
  }
  
  stopDataCollection() {
    if (this.dataCollectionInterval) {
      clearInterval(this.dataCollectionInterval);
      this.dataCollectionInterval = null;
    }
    setState('dataCollectionEnabled', false);
    log('Data collection stopped');
  }
  
  async collectAndSendData() {
    try {
      const asset = getCurrentAsset();
      if (!asset) return;
      
      const candles = priceScraper.getCandles(100);
      if (candles && candles.length > 0) {
        const { sendCandles } = await import('./utils/api.js');
        await sendCandles(candles, asset, '5s');
      }
    } catch (e) {
      warn(`Data collection error: ${e.message}`);
    }
  }
  
  cleanup() {
    // IMPORTANT: save state FIRST so if disable() resets anything, we still capture it
    try {
      if (twentyOneSecondReversal.config) {
        state._twentyOneSConfig = { ...twentyOneSecondReversal.config };
      }
      state._twentyOneSEnabled = twentyOneSecondReversal.isEnabled();
      saveState();
    } catch (_e) { /* ignore */ }

    this.stopScanning();
    this.stopDataCollection();
    priceScraper.stop();
    twentyOneSecondReversal.disable();
    favoritesCycle.stop();
    appSignalPoller.stop();
    try { networkLatencyPoller.stop(); } catch (_e) { /* ignore */ }
    try { heartbeatReporter.stop(); } catch (_e) { /* ignore */ }
    try { aiAnalysisPoller.stop(); } catch (_e) { /* ignore */ }
    try {
      if (this._latAbstainInterval) { clearInterval(this._latAbstainInterval); this._latAbstainInterval = null; }
    } catch (_e) { /* ignore */ }
    cleanupPanel();

    if (this.statsInterval) clearInterval(this.statsInterval);
    if (this.autoSaveInterval) clearInterval(this.autoSaveInterval);
    if (this.assetIndicatorInterval) clearInterval(this.assetIndicatorInterval);
    this.stopSignalPreview();

    log('Bot cleanup complete');
  }
}

// Initialize bot
const bot = new EliteTradingBot();

function startBot() {
  bot.init().catch((e) => {
    console.error(`[${CONFIG.BOT_NAME}] Failed to initialize:`, e);
  });
}

// At @run-at document-start, DOM isn't ready yet.
// Defer bot UI init until DOM is parsed so document.body exists.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startBot, { once: true });
} else {
  startBot();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  bot.cleanup();
});

// Expose for debugging
window.eliteBot = bot;
window.eliteBotTradeExecutor = tradeExecutor;
window.eliteBotSmartInvert = smartInvert;
window.eliteBotPriceScraper = priceScraper;
window.eliteBot21sReversal = twentyOneSecondReversal;
window.eliteBotSsidBridge = ssidBridge;
window.eliteBotLivePrice = poLivePrice;
window.eliteBotLiveTickPoster = liveTickPoster;
window.eliteBotLivePriceTracker = livePriceTracker;
window.eliteBotFavoritesCycle = favoritesCycle;
window.eliteBotChartTypeSwitcher = chartTypeSwitcher;
window.eliteBotAppSignal = appSignalPoller;
window.eliteBotDom = domUtils;

// One-shot diagnostic — run in console and paste output if prices fail to flow
window.eliteBotDiagnose = function () {
  const out = {
    version: CONFIG.BOT_VERSION,
    url: window.location.href,
    ssidBridge: {
      installed: ssidBridge.installed,
      pricesCaptured: ssidBridge.pricesCaptured,
      lastAuthMessagePresent: !!ssidBridge.lastAuthMessage,
    },
    livePrice: {
      latest: poLivePrice.getLatest(),
      age_ms: poLivePrice.getLatestAge(),
      all: poLivePrice.getAll(),
    },
    liveTickPoster: (function () { try { return liveTickPoster.getStats(); } catch (e) { return `ERR: ${e.message}`; } })(),
    livePriceTracker: (function () { try { return livePriceTracker.getStats(); } catch (e) { return `ERR: ${e.message}`; } })(),
    priceScraper: {
      current: (function () { try { return priceScraper.getCurrentPrice(); } catch (e) { return `ERR: ${e.message}`; } })(),
    },
    domPrice: {
      standard: (function () { try { return getCurrentPrice(); } catch (e) { return `ERR: ${e.message}`; } })(),
    },
    currentAsset: (function () { try { return getCurrentAsset(); } catch (e) { return `ERR: ${e.message}`; } })(),
    forexLikeTextNodes: [],
  };
  // Find any text nodes with forex-like numbers for visibility
  try {
    const re = /^\d{1,7}\.\d{2,8}$/;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    let count = 0;
    while ((n = walker.nextNode()) && count < 20) {
      const t = (n.nodeValue || '').trim();
      if (re.test(t)) {
        const el = n.parentElement;
        out.forexLikeTextNodes.push({
          text: t,
          tag: el ? el.tagName : null,
          cls: el ? (el.className || '').toString().slice(0, 80) : null,
        });
        count++;
      }
    }
  } catch (e) { out.forexLikeTextNodes = `ERR: ${e.message}`; }
  // Pretty print
  console.log('%c[Elite Bot Diagnostic]', 'color: #a855f7; font-weight: bold', out);
  return out;
};

export default bot;
