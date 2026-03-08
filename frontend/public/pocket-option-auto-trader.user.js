// ==UserScript==
// @name         GPT Signal Bot - Pocket Option Auto Trader
// @namespace    https://gpt-signal-bot-2.preview.emergentagent.com
// @version      5.4.0
// @description  Auto-trade OTC forex on Pocket Option. v5.4.0 - Fixed double trade bug with stronger locks and 5s trade debounce
// @author       GPT Signal Bot
// @match        *://*.pocketoption.com/*
// @match        *://pocketoption.com/*
// @match        *://*.po.trade/*
// @match        *://po.trade/*
// @match        *://*.pocket-option.com/*
// @match        *://pocket-option.com/*
// @match        *://*.po.market/*
// @match        *://po.market/*
// @grant        GM_notification
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_log
// @connect      signal-generator-pro.preview.emergentagent.com
// @connect      *
// @run-at       document-idle
// @noframes
// ==/UserScript==

(function() {
    'use strict';

    // ===========================================
    // CONFIGURATION
    // ===========================================
    const CONFIG = {
        API_URL: 'https://gpt-signal-bot-2.preview.emergentagent.com/api',
        POLL_INTERVAL: 5000,  // 5 seconds between checks
        AUTO_TRADE_ENABLED: true,
        AUTO_SWITCH_ASSET: true,  // When ON: scan multiple assets. When OFF: scan current asset only
        SCAN_MODE: false,
        SCAN_ASSETS: 'EURUSD_OTC,GBPUSD_OTC,USDJPY_OTC,AUDUSD_OTC,EURJPY_OTC,GBPJPY_OTC,EURGBP_OTC,USDCAD_OTC,USDCHF_OTC,NZDUSD_OTC',
        MIN_CONFIDENCE: 70,
        MIN_PAYOUT: 65,  // Minimum payout percentage required (65%+)
        SCAN_FAVORITES_ONLY: true,  // Only scan assets marked as favorites in Pocket Option
        TRADE_COOLDOWN: 3000,  // 3 seconds cooldown between trades
        SOUND_ENABLED: true,
        AUTO_SWITCH_TIMEFRAME: true,  // Auto-switch Pocket Option timeframe to match signal expiry
        PREFERRED_EXPIRY: null,  // null = auto-select best, or set to 5, 15, 30, 60
        DEBUG: true
    };

    // Expiry to Pocket Option timeframe mapping (in seconds)
    const EXPIRY_TO_PO_TIMEFRAME = {
        5: 5,
        15: 15,
        30: 30,
        60: 60,
        120: 120,
        180: 180,
        300: 300
    };

    // Asset mappings for OTC pairs
    const ASSET_MAPPINGS = {
        'EURUSD_OTC': 'EUR/USD OTC', 'EURUSD': 'EUR/USD OTC',
        'GBPUSD_OTC': 'GBP/USD OTC', 'GBPUSD': 'GBP/USD OTC',
        'USDJPY_OTC': 'USD/JPY OTC', 'USDJPY': 'USD/JPY OTC',
        'AUDUSD_OTC': 'AUD/USD OTC', 'AUDUSD': 'AUD/USD OTC',
        'USDCAD_OTC': 'USD/CAD OTC', 'USDCAD': 'USD/CAD OTC',
        'USDCHF_OTC': 'USD/CHF OTC', 'USDCHF': 'USD/CHF OTC',
        'NZDUSD_OTC': 'NZD/USD OTC', 'NZDUSD': 'NZD/USD OTC',
        'EURGBP_OTC': 'EUR/GBP OTC', 'EURGBP': 'EUR/GBP OTC',
        'EURJPY_OTC': 'EUR/JPY OTC', 'EURJPY': 'EUR/JPY OTC',
        'GBPJPY_OTC': 'GBP/JPY OTC', 'GBPJPY': 'GBP/JPY OTC',
        'EURCAD_OTC': 'EUR/CAD OTC', 'EURCAD': 'EUR/CAD OTC',
        'EUR_USD': 'EUR/USD OTC', 'GBP_USD': 'GBP/USD OTC',
        'USD_JPY': 'USD/JPY OTC', 'AUD_USD': 'AUD/USD OTC',
        'EUR_JPY': 'EUR/JPY OTC', 'GBP_JPY': 'GBP/JPY OTC'
    };

    // ===========================================
    // STATE
    // ===========================================
    let lastProcessedSignalId = '';
    let lastProcessedSignalTimestamp = 0;  // Track when last signal was processed
    let lastTradeExecutionTime = 0;  // Track actual trade execution time
    let isTrading = false;
    let isScanning = false;  // Prevent concurrent scans
    let tradeCount = 0;
    let currentAsset = null;
    let buttonsReady = false;
    let recentlyTradedAssets = {};  // Track recently traded assets with timestamps {asset: timestamp}
    let lastTradeTime = 0;
    let failedSwitchAttempts = {};  // Track failed switches to avoid retrying {asset: attempts}
    let invertSignals = false;      // Invert signals: CALL becomes PUT, PUT becomes CALL
    
    // Constants for asset cycling
    const ASSET_COOLDOWN_MS = 60000;  // 60 seconds cooldown per asset after trading
    const MAX_SWITCH_ATTEMPTS = 2;     // Max times to try switching to a failing asset
    const MIN_SIGNAL_INTERVAL_MS = 10000;  // Minimum 10 seconds between processing same signal type
    const MIN_TRADE_INTERVAL_MS = 5000;  // Minimum 5 seconds between actual trades (prevents double click)
    
    // Load saved settings
    try {
        invertSignals = GM_getValue('invertSignals', false);
    } catch (e) {
        invertSignals = false;
    }

    // ===========================================
    // LOGGING
    // ===========================================
    function log(msg, type = 'info') {
        const ts = new Date().toLocaleTimeString();
        const prefix = '[GPT v5.4.0]';
        console.log(`${prefix} ${ts}: ${msg}`);
        
        const logEl = document.getElementById('gpt-log');
        if (logEl) {
            logEl.textContent = msg;
        }
    }

    // ===========================================
    // UI PANEL
    // ===========================================
    function createPanel() {
        const existing = document.getElementById('gpt-panel');
        if (existing) existing.remove();

        const panel = document.createElement('div');
        panel.id = 'gpt-panel';
        panel.innerHTML = `
            <style>
                #gpt-panel {
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    border: 2px solid #7c3aed;
                    border-radius: 12px;
                    padding: 10px 15px;
                    z-index: 999999;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    color: white;
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                    box-shadow: 0 4px 25px rgba(124, 58, 237, 0.4);
                    min-width: 340px;
                    user-select: none;
                    touch-action: none;
                }
                #gpt-panel .drag-header {
                    cursor: move;
                    cursor: grab;
                    padding: 2px 0 6px 0;
                    margin: -2px 0 4px 0;
                    border-bottom: 1px solid rgba(124, 58, 237, 0.3);
                }
                #gpt-panel .drag-header:active {
                    cursor: grabbing;
                }
                #gpt-panel .row { display: flex; align-items: center; gap: 10px; }
                #gpt-panel .dot { width: 10px; height: 10px; border-radius: 50%; background: #ef4444; flex-shrink: 0; }
                #gpt-panel .dot.connected { background: #22c55e; }
                #gpt-panel .dot.trading { background: #f59e0b; animation: blink 0.5s infinite; }
                @keyframes blink { 50% { opacity: 0.3; } }
                #gpt-panel .title { font-weight: bold; color: #a78bfa; font-size: 14px; }
                #gpt-panel .signal { padding: 4px 12px; border-radius: 5px; font-weight: bold; font-size: 12px; min-width: 60px; text-align: center; }
                #gpt-panel .signal.call { background: #22c55e; }
                #gpt-panel .signal.put { background: #ef4444; }
                #gpt-panel .signal.wait { background: #64748b; }
                #gpt-panel button { padding: 5px 10px; border: none; border-radius: 5px; font-weight: bold; font-size: 11px; cursor: pointer; transition: all 0.2s; }
                #gpt-panel button:hover { transform: scale(1.05); }
                #gpt-panel .btn-auto { background: #22c55e; color: white; }
                #gpt-panel .btn-auto.off { background: #ef4444; }
                #gpt-panel .btn-switch { background: #8b5cf6; color: white; }
                #gpt-panel .btn-switch.off { background: #6b7280; }
                #gpt-panel .btn-scan { background: #ec4899; color: white; }
                #gpt-panel .btn-scan.on { background: #22c55e; }
                #gpt-panel .btn-invert { background: #6b7280; color: white; }
                #gpt-panel .btn-invert.on { background: #f59e0b; animation: pulse 1s infinite; }
                @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
                #gpt-panel .btn-fetch { background: #3b82f6; color: white; }
                #gpt-panel .btn-reset { background: #f59e0b; color: white; }
                #gpt-panel .info { font-size: 11px; color: #94a3b8; }
                #gpt-panel .asset-info { font-size: 11px; color: #fbbf24; background: rgba(251, 191, 36, 0.1); padding: 3px 8px; border-radius: 4px; }
                #gpt-log { font-size: 10px; color: #22c55e; background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
                #gpt-panel .status-badge { padding: 2px 6px; border-radius: 3px; background: #374151; font-size: 10px; }
                #gpt-panel .status-badge.ok { background: #065f46; color: #6ee7b7; }
                #gpt-panel .status-badge.no { background: #7f1d1d; color: #fca5a5; }
            </style>
            <div class="drag-header" id="gpt-drag-handle">
                <div class="row">
                    <span class="dot" id="gpt-dot"></span>
                    <span class="title">GPT Bot v5.4.0</span>
                    <span style="flex:1"></span>
                    <span style="font-size:10px;color:#94a3b8;">☰ drag</span>
                </div>
            </div>
            <div class="row">
                <span class="signal wait" id="gpt-signal">INIT...</span>
                <span class="info">Trades: <span id="gpt-trades">0</span></span>
            </div>
            <div class="row">
                <span class="asset-info" id="gpt-asset">Asset: --</span>
                <span class="asset-info" id="gpt-payout" style="background: rgba(34, 197, 94, 0.2);">Pay: --%</span>
                <span class="asset-info" id="gpt-expiry" style="background: rgba(139, 92, 246, 0.2);">Exp: --</span>
            </div>
            <div class="row">
                <div style="display:flex;gap:6px;">
                    <span class="status-badge" id="gpt-btn-status">BTN: ?</span>
                    <span class="status-badge" id="gpt-mode-status">SINGLE</span>
                    <span class="status-badge" id="gpt-switch-status">SW: ON</span>
                </div>
            </div>
            <div class="row">
                <button class="btn-auto" id="gpt-auto">AUTO ON</button>
                <button class="btn-switch" id="gpt-switch">SWITCH ON</button>
                <button class="btn-scan" id="gpt-scan">SCAN</button>
                <button class="btn-invert" id="gpt-invert">INVERT</button>
            </div>
            <div class="row">
                <button class="btn-fetch" id="gpt-fetch">FETCH</button>
                <button class="btn-reset" id="gpt-reset">RESET</button>
            </div>
            <div id="gpt-log">Initializing v4.8.1...</div>
        `;
        document.body.appendChild(panel);

        document.getElementById('gpt-auto').addEventListener('click', toggleAuto);
        document.getElementById('gpt-switch').addEventListener('click', toggleAssetSwitch);
        document.getElementById('gpt-scan').addEventListener('click', toggleScanMode);
        document.getElementById('gpt-invert').addEventListener('click', toggleInvertSignals);
        document.getElementById('gpt-fetch').addEventListener('click', () => checkSignal(true));
        document.getElementById('gpt-reset').addEventListener('click', resetBot);
        
        // Set initial invert button state
        updateInvertButton();

        makeDraggable(panel);
        log('Panel ready v5.4.0');
    }
    
    function toggleInvertSignals() {
        invertSignals = !invertSignals;
        try {
            GM_setValue('invertSignals', invertSignals);
        } catch (e) {}
        updateInvertButton();
        log(`Signal inversion ${invertSignals ? 'ENABLED' : 'DISABLED'}`);
        
        if (invertSignals) {
            try {
                GM_notification({
                    title: '🔄 SIGNAL INVERSION ACTIVE',
                    text: 'CALL → PUT, PUT → CALL',
                    timeout: 3000
                });
            } catch (e) {}
        }
    }
    
    function updateInvertButton() {
        const btn = document.getElementById('gpt-invert');
        if (btn) {
            if (invertSignals) {
                btn.textContent = '🔄 INVERT ON';
                btn.classList.add('on');
            } else {
                btn.textContent = 'INVERT';
                btn.classList.remove('on');
            }
        }
    }

    function makeDraggable(el) {
        const dragHandle = document.getElementById('gpt-drag-handle') || el;
        let isDragging = false;
        let startX, startY, startLeft, startTop;
        
        // Get initial position
        const rect = el.getBoundingClientRect();
        el.style.left = rect.left + 'px';
        el.style.top = rect.top + 'px';
        el.style.right = 'auto';
        
        function onStart(e) {
            // Ignore if clicking a button
            if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') return;
            
            isDragging = true;
            
            // Get start position
            if (e.type === 'touchstart') {
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
            } else {
                startX = e.clientX;
                startY = e.clientY;
            }
            
            startLeft = el.offsetLeft;
            startTop = el.offsetTop;
            
            // Prevent text selection and default behavior
            e.preventDefault();
            
            // Add move and end listeners to document
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onEnd);
            document.addEventListener('touchmove', onMove, { passive: false });
            document.addEventListener('touchend', onEnd);
        }
        
        function onMove(e) {
            if (!isDragging) return;
            
            e.preventDefault();
            
            let currentX, currentY;
            if (e.type === 'touchmove') {
                currentX = e.touches[0].clientX;
                currentY = e.touches[0].clientY;
            } else {
                currentX = e.clientX;
                currentY = e.clientY;
            }
            
            // Calculate new position
            const deltaX = currentX - startX;
            const deltaY = currentY - startY;
            
            let newLeft = startLeft + deltaX;
            let newTop = startTop + deltaY;
            
            // Keep panel within viewport
            const maxLeft = window.innerWidth - el.offsetWidth;
            const maxTop = window.innerHeight - el.offsetHeight;
            
            newLeft = Math.max(0, Math.min(newLeft, maxLeft));
            newTop = Math.max(0, Math.min(newTop, maxTop));
            
            el.style.left = newLeft + 'px';
            el.style.top = newTop + 'px';
        }
        
        function onEnd() {
            isDragging = false;
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onEnd);
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', onEnd);
            
            // Save position
            try {
                GM_setValue('panelLeft', el.style.left);
                GM_setValue('panelTop', el.style.top);
            } catch (e) {}
        }
        
        // Add event listeners to drag handle
        dragHandle.addEventListener('mousedown', onStart);
        dragHandle.addEventListener('touchstart', onStart, { passive: false });
        
        // Restore saved position
        try {
            const savedLeft = GM_getValue('panelLeft', null);
            const savedTop = GM_getValue('panelTop', null);
            if (savedLeft && savedTop) {
                el.style.left = savedLeft;
                el.style.top = savedTop;
            }
        } catch (e) {}
    }

    function updateUI(status, signal = null) {
        const dot = document.getElementById('gpt-dot');
        const sigEl = document.getElementById('gpt-signal');
        const tradesEl = document.getElementById('gpt-trades');
        const btnStatus = document.getElementById('gpt-btn-status');
        const modeStatus = document.getElementById('gpt-mode-status');
        const switchStatus = document.getElementById('gpt-switch-status');
        const assetInfo = document.getElementById('gpt-asset');
        const payoutInfo = document.getElementById('gpt-payout');
        const expiryInfo = document.getElementById('gpt-expiry');
        
        if (dot) {
            dot.className = 'dot';
            if (status === 'connected') dot.classList.add('connected');
            else if (status === 'trading') dot.classList.add('trading');
        }
        
        if (signal && sigEl) {
            let isCall = signal.direction === 'CALL' || signal.direction === 'BUY';
            // Apply inversion for display
            if (invertSignals) {
                isCall = !isCall;
            }
            const invLabel = invertSignals ? '🔄' : '';
            sigEl.textContent = invLabel + (isCall ? 'CALL' : 'PUT');
            sigEl.className = 'signal ' + (isCall ? 'call' : 'put');
        }
        
        if (tradesEl) tradesEl.textContent = tradeCount;
        if (btnStatus) {
            btnStatus.textContent = buttonsReady ? 'BTN: OK' : 'BTN: NO';
            btnStatus.className = 'status-badge ' + (buttonsReady ? 'ok' : 'no');
        }
        if (assetInfo && signal && signal.symbol) {
            assetInfo.textContent = `Asset: ${signal.symbol.replace('_OTC', '')}`;
        }
        if (payoutInfo) {
            if (signal && signal.payout) {
                payoutInfo.textContent = `Pay: ${signal.payout}%`;
                payoutInfo.style.background = signal.payout >= CONFIG.MIN_PAYOUT ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)';
            } else {
                // Try to get current payout from UI
                const currentPay = getCurrentPayout();
                if (currentPay !== null) {
                    payoutInfo.textContent = `Pay: ${currentPay}%`;
                    payoutInfo.style.background = currentPay >= CONFIG.MIN_PAYOUT ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)';
                }
            }
        }
        if (expiryInfo && signal && signal.expiry_seconds) {
            const expSec = signal.expiry_seconds;
            const expDisplay = expSec >= 60 ? `${Math.floor(expSec/60)}m` : `${expSec}s`;
            expiryInfo.textContent = `Exp: ${expDisplay}`;
        }
        if (modeStatus) {
            let modeText = CONFIG.SCAN_MODE ? (CONFIG.SCAN_FAVORITES_ONLY ? 'FAV' : 'ALL') : 'SINGLE';
            if (invertSignals) modeText += ' 🔄';
            modeStatus.textContent = modeText;
            modeStatus.className = 'status-badge ' + (CONFIG.SCAN_MODE ? 'ok' : '');
        }
        if (switchStatus) {
            switchStatus.textContent = CONFIG.AUTO_SWITCH_ASSET ? 'SW: MULTI' : 'SW: CURR';
            switchStatus.className = 'status-badge ' + (CONFIG.AUTO_SWITCH_ASSET ? 'ok' : 'no');
        }
    }

    // ===========================================
    // ASSET FUNCTIONS
    // ===========================================
    function getCurrentAsset() {
        const selectors = ['.pair-number-wrap .pair-title', '.pair-number-wrap', '.current-pair'];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.textContent) {
                const text = el.textContent.trim();
                if (text.includes('/') || text.includes('OTC')) {
                    currentAsset = text;
                    return text;
                }
            }
        }
        return null;
    }
    
    // Get current asset's payout percentage from Pocket Option UI
    function getCurrentPayout() {
        // Try multiple selectors for payout display
        const payoutSelectors = [
            '.pair-number-wrap .pair-profit',
            '.pair-profit',
            '.profit-percent',
            '.payout',
            '[class*="profit"]',
            '[class*="payout"]'
        ];
        
        for (const sel of payoutSelectors) {
            const el = document.querySelector(sel);
            if (el && el.textContent) {
                const text = el.textContent.trim();
                // Extract number from text like "+85%" or "85%"
                const match = text.match(/(\d+)\s*%/);
                if (match) {
                    return parseInt(match[1]);
                }
            }
        }
        return null;
    }
    
    // Get list of favorite assets from Pocket Option
    async function getFavoriteAssets() {
        const favorites = [];
        
        try {
            // Open asset selector
            const pairSelector = document.querySelector('.pair-number-wrap');
            if (!pairSelector) {
                log('Cannot open asset selector for favorites');
                return null;
            }
            
            pairSelector.click();
            await sleep(1000);
            
            // Look for favorites section or starred items
            // Pocket Option typically shows favorites with a star icon or in a "Favorites" tab
            const favoriteSelectors = [
                '.alist__item--favorite',
                '.alist__item.favorite',
                '[class*="favorite"]',
                '.asset-item.starred',
                '.alist__item:has(.star-icon.active)',
                '.alist__item:has([class*="star"][class*="active"])'
            ];
            
            let favoriteItems = [];
            
            // First try to click on Favorites tab if it exists
            const favTabs = document.querySelectorAll('.alist__tab, .tab-item, [class*="tab"]');
            for (const tab of favTabs) {
                const tabText = tab.textContent.toLowerCase();
                if (tabText.includes('favor') || tabText.includes('star')) {
                    log('Found Favorites tab, clicking...');
                    tab.click();
                    await sleep(500);
                    break;
                }
            }
            
            // Now get visible items (should be favorites if tab was clicked)
            for (const sel of favoriteSelectors) {
                favoriteItems = document.querySelectorAll(sel);
                if (favoriteItems.length > 0) break;
            }
            
            // If no favorites found via class, look for starred items
            if (favoriteItems.length === 0) {
                const allItems = document.querySelectorAll('.alist__item:not(.alist__item--no-active)');
                for (const item of allItems) {
                    // Check if item has an active star
                    const star = item.querySelector('[class*="star"], [class*="fav"], .ico-star');
                    if (star) {
                        const starClasses = star.className || '';
                        const isActive = starClasses.includes('active') || 
                                        starClasses.includes('filled') ||
                                        starClasses.includes('selected') ||
                                        star.style.color === 'gold' ||
                                        star.style.color === 'yellow';
                        if (isActive) {
                            favoriteItems = [...favoriteItems, item];
                        }
                    }
                }
            }
            
            // Extract asset names and payouts from favorite items
            for (const item of favoriteItems) {
                if (item.style.display === 'none' || item.offsetParent === null) continue;
                
                const nameEl = item.querySelector('.alist__label, .asset-name, [class*="name"]');
                const payoutEl = item.querySelector('.alist__profit, .profit, [class*="profit"], [class*="payout"]');
                
                if (nameEl) {
                    const assetName = nameEl.textContent.trim();
                    let payout = 0;
                    
                    if (payoutEl) {
                        const payoutText = payoutEl.textContent.trim();
                        const match = payoutText.match(/(\d+)/);
                        if (match) payout = parseInt(match[1]);
                    }
                    
                    // Convert to API format
                    const apiFormat = assetName.replace('/', '').replace(' ', '_').toUpperCase();
                    
                    favorites.push({
                        name: assetName,
                        apiSymbol: apiFormat,
                        payout: payout
                    });
                }
            }
            
            // Close dropdown
            closeDropdown();
            
            log(`Found ${favorites.length} favorites`);
            return favorites;
            
        } catch (e) {
            log(`Error getting favorites: ${e.message}`);
            closeDropdown();
            return null;
        }
    }
    
    // Get payout for a specific asset by opening selector and finding it
    async function getAssetPayout(assetSymbol) {
        try {
            const pairSelector = document.querySelector('.pair-number-wrap');
            if (!pairSelector) return null;
            
            pairSelector.click();
            await sleep(800);
            
            // Search for the asset
            const searchField = document.querySelector('.search__field') || 
                               document.querySelector('input[type="search"]');
            
            if (searchField) {
                const searchTerm = assetSymbol.replace('_OTC', '').replace('_', '').substring(0, 6);
                searchField.value = '';
                searchField.focus();
                
                for (const char of searchTerm) {
                    searchField.value += char;
                    searchField.dispatchEvent(new Event('input', { bubbles: true }));
                    await sleep(50);
                }
                await sleep(500);
            }
            
            // Find the asset and its payout
            const items = document.querySelectorAll('.alist__item:not(.alist__item--no-active)');
            for (const item of items) {
                if (item.style.display === 'none' || item.offsetParent === null) continue;
                
                const nameEl = item.querySelector('.alist__label, .asset-name');
                const payoutEl = item.querySelector('.alist__profit, .profit, [class*="profit"]');
                
                if (nameEl && nameEl.textContent.toUpperCase().includes(assetSymbol.substring(0, 3))) {
                    let payout = 0;
                    if (payoutEl) {
                        const match = payoutEl.textContent.match(/(\d+)/);
                        if (match) payout = parseInt(match[1]);
                    }
                    closeDropdown();
                    return payout;
                }
            }
            
            closeDropdown();
            return null;
            
        } catch (e) {
            closeDropdown();
            return null;
        }
    }

    function normalizeAssetSymbol(symbol) {
        if (!symbol) return null;
        const mapped = ASSET_MAPPINGS[symbol.toUpperCase()];
        if (mapped) return mapped;
        
        let clean = symbol.toUpperCase().replace('_OTC', '').replace('_', '');
        if (clean.length === 6) {
            clean = clean.substring(0, 3) + '/' + clean.substring(3);
        }
        return clean + ' OTC';
    }

    // ===========================================
    // ASSET SWITCHING - IMPROVED v4.7
    // ===========================================
    async function switchToAsset(targetSymbol) {
        const targetDisplayName = normalizeAssetSymbol(targetSymbol);
        if (!targetDisplayName) {
            log(`Cannot parse: ${targetSymbol}`);
            return false;
        }
        
        // Extract components
        const isOTC = targetSymbol.includes('OTC') || targetDisplayName.includes('OTC');
        const baseSymbol = targetDisplayName.replace(' OTC', '').replace('/', '').toUpperCase();
        const searchTerm = baseSymbol.substring(0, 6);
        
        log(`=== SWITCHING TO: ${targetSymbol} ===`);
        log(`Base: ${baseSymbol}, OTC: ${isOTC}, Search: ${searchTerm}`);
        
        const current = getCurrentAsset();
        log(`Current asset: "${current}"`);
        
        // Check if already on correct asset
        if (current) {
            const currentBase = current.replace(' OTC', '').replace('/', '').replace(/[^A-Z0-9]/gi, '').toUpperCase();
            const currentIsOTC = current.toLowerCase().includes('otc');
            
            if (currentBase === baseSymbol && currentIsOTC === isOTC) {
                log(`Already on correct asset: ${current}`);
                return true;
            }
        }
        
        try {
            // Step 1: Click pair selector to open dropdown
            const pairSelector = document.querySelector('.pair-number-wrap');
            if (!pairSelector) {
                log('ERROR: Pair selector not found');
                return false;
            }
            
            log('Opening asset selector...');
            pairSelector.click();
            await sleep(1200); // Wait for dropdown to fully open
            
            // Step 2: Find search field (try multiple selectors)
            let searchField = document.querySelector('.search__field') || 
                             document.querySelector('input[type="search"]') ||
                             document.querySelector('input.input-search') ||
                             document.querySelector('[placeholder*="Search"]');
            
            if (!searchField) {
                log('ERROR: Search field not found, trying alternative...');
                // Try to find any input in the dropdown
                const dropdown = document.querySelector('.alist, .asset-list, [class*="dropdown"]');
                if (dropdown) {
                    searchField = dropdown.querySelector('input');
                }
            }
            
            if (!searchField) {
                log('ERROR: No search field found');
                closeDropdown();
                return false;
            }
            
            // Step 3: Clear and focus search field
            log('Clearing search field...');
            searchField.value = '';
            searchField.focus();
            searchField.click();
            await sleep(200);
            
            // Step 4: Type search term character by character
            log(`Typing search: "${searchTerm}"`);
            for (const char of searchTerm) {
                searchField.value += char;
                searchField.dispatchEvent(new Event('input', { bubbles: true }));
                searchField.dispatchEvent(new Event('change', { bubbles: true }));
                searchField.dispatchEvent(new Event('keyup', { bubbles: true }));
                await sleep(100);
            }
            
            await sleep(1000); // Wait for search results
            
            // Step 5: Find all visible asset items
            const assetItems = document.querySelectorAll(
                '.alist__item:not(.alist__item--no-active), ' +
                '.asset-item:not(.hidden), ' +
                '[class*="asset-list"] > div:not(.hidden)'
            );
            log(`Found ${assetItems.length} asset items`);
            
            // Step 6: Score and find best match
            let bestMatch = null;
            let bestMatchScore = 0;
            let bestMatchText = '';
            
            for (const item of assetItems) {
                // Skip hidden items
                if (item.style.display === 'none' || item.offsetParent === null) {
                    continue;
                }
                
                const itemText = item.textContent.trim().toUpperCase();
                const itemIsOTC = itemText.includes('OTC');
                const itemBase = itemText.replace(/OTC/gi, '').replace(/[^A-Z0-9]/g, '').substring(0, 6);
                
                // Calculate match score
                let score = 0;
                
                // Full base symbol match = highest priority
                if (itemBase === baseSymbol) {
                    score += 100;
                } else if (itemBase.startsWith(baseSymbol.substring(0, 3))) {
                    // Partial match (first 3 chars)
                    score += 30;
                } else {
                    continue; // Skip non-matching items
                }
                
                // OTC preference - critical for correct selection
                if (isOTC && itemIsOTC) {
                    score += 50; // We want OTC and this is OTC
                } else if (!isOTC && !itemIsOTC) {
                    score += 50; // We want regular and this is regular
                } else if (isOTC && !itemIsOTC) {
                    score -= 100; // We want OTC but this is regular - big penalty
                } else if (!isOTC && itemIsOTC) {
                    score -= 100; // We want regular but this is OTC - big penalty
                }
                
                if (score > bestMatchScore) {
                    bestMatchScore = score;
                    bestMatch = item;
                    bestMatchText = itemText;
                    log(`Match candidate: "${itemText}" (score: ${score})`);
                }
            }
            
            // Step 7: Click best match if found
            if (bestMatch && bestMatchScore >= 100) {
                log(`Selecting: "${bestMatchText}" (score: ${bestMatchScore})`);
                
                // Try different click targets
                const clickTargets = [
                    bestMatch.querySelector('.alist__label'),
                    bestMatch.querySelector('[class*="name"]'),
                    bestMatch.querySelector('span'),
                    bestMatch
                ];
                
                for (const target of clickTargets) {
                    if (target) {
                        // Multiple click methods for reliability
                        target.click();
                        await sleep(50);
                        
                        // Dispatch proper mouse events
                        const mouseDown = new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window });
                        const mouseUp = new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window });
                        const click = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                        
                        target.dispatchEvent(mouseDown);
                        target.dispatchEvent(mouseUp);
                        target.dispatchEvent(click);
                        
                        await sleep(100);
                    }
                }
                
                await sleep(600);
                
                // Verify switch was successful
                const newAsset = getCurrentAsset();
                log(`After switch: "${newAsset}"`);
                
                if (newAsset) {
                    const newBase = newAsset.replace(' OTC', '').replace('/', '').replace(/[^A-Z0-9]/gi, '').toUpperCase();
                    const newIsOTC = newAsset.toLowerCase().includes('otc');
                    
                    if (newBase === baseSymbol && newIsOTC === isOTC) {
                        currentAsset = newAsset;
                        log(`SUCCESS: Now on ${newAsset}`);
                        return true;
                    }
                }
                
                log('WARNING: Asset may not have switched correctly');
            } else {
                log(`No good OTC match found (best score: ${bestMatchScore})`);
            }
            
            // Step 8: Fallback - try clicking first visible OTC item
            if (isOTC) {
                log('Fallback: Looking for any visible OTC item...');
                for (const item of assetItems) {
                    if (item.style.display !== 'none' && item.offsetParent !== null) {
                        const text = item.textContent.trim().toUpperCase();
                        if (text.includes('OTC') && text.includes(searchTerm.substring(0, 3))) {
                            log(`Fallback clicking: ${text}`);
                            item.click();
                            await sleep(400);
                            
                            const newAsset = getCurrentAsset();
                            if (newAsset && newAsset.toLowerCase().includes('otc')) {
                                currentAsset = newAsset;
                                log(`Fallback SUCCESS: ${newAsset}`);
                                return true;
                            }
                        }
                    }
                }
            }
            
            // Step 9: Last resort - press Enter
            log('Last resort: pressing Enter...');
            const enterEvent = new KeyboardEvent('keydown', {
                key: 'Enter',
                keyCode: 13,
                which: 13,
                bubbles: true,
                cancelable: true
            });
            searchField.dispatchEvent(enterEvent);
            await sleep(400);
            
            closeDropdown();
            return false;
            
        } catch (e) {
            log(`Switch error: ${e.message}`);
            closeDropdown();
            return false;
        }
    }
    
    function closeDropdown() {
        try {
            // Press Escape
            document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
            
            // Click outside dropdown
            const overlays = document.querySelectorAll('.modal-backdrop, .dropdown-backdrop, .overlay, .alist__backdrop');
            for (const overlay of overlays) {
                overlay.click();
            }
        } catch (e) {}
    }

    // ===========================================
    // TIMEFRAME SWITCHING
    // ===========================================
    // ===========================================
    // TRADE EXPIRATION SWITCHING - NOT CHART TIMEFRAME
    // ===========================================
    // This changes the TRADE EXPIRATION (near amount section), not chart timeframe (M1, M5, etc.)
    
    async function switchToTimeframe(expirySeconds) {
        if (!CONFIG.AUTO_SWITCH_TIMEFRAME || !expirySeconds) {
            return true; // Skip if disabled
        }
        
        log(`⏱️ Setting trade expiration to ${expirySeconds}s...`);
        
        try {
            // IMPORTANT: We need the TRADE EXPIRATION selector, not chart timeframe
            // Trade expiration is in the trading panel near the amount input
            // It shows values like "1:00", "0:30", "5:00" (minutes:seconds)
            
            // First, find the trading panel / trade controls area
            const tradingPanelSelectors = [
                '.trading-panel',
                '.trade-panel', 
                '.option-panel',
                '.deals-group',
                '.trading-block',
                '[class*="trading-panel"]',
                '[class*="trade-controls"]'
            ];
            
            let tradingPanel = null;
            for (const sel of tradingPanelSelectors) {
                tradingPanel = document.querySelector(sel);
                if (tradingPanel) break;
            }
            
            // Look for amount input to help locate the trade expiration nearby
            const amountInput = document.querySelector('input[name*="amount"]') ||
                               document.querySelector('input[class*="amount"]') ||
                               document.querySelector('.amount-input') ||
                               document.querySelector('[class*="deal-amount"] input');
            
            // Trade expiration is typically ABOVE or NEAR the amount input
            // Look for time display specifically in trade panel area
            
            // Specific selectors for TRADE EXPIRATION (not chart timeframe)
            const expirationSelectors = [
                // Most common PO trade expiration selectors
                '.deal-time__value',
                '.deal-time',
                '.option__time-item',
                '.option-time-item',
                '.trading-panel__time',
                '.time-wrapper__item',
                '.time-wrap__value',
                // Near amount section
                '.deals-group .time-item',
                '.trading-panel .time-item',
                // Generic but within trade panel
                '[class*="deal"][class*="time"]',
                '[class*="expir"][class*="value"]',
                '[class*="trade"][class*="time"]'
            ];
            
            let expirationElement = null;
            
            // Try specific selectors first
            for (const sel of expirationSelectors) {
                expirationElement = document.querySelector(sel);
                if (expirationElement && expirationElement.offsetParent !== null) {
                    log(`Found expiration element: ${sel}`);
                    break;
                }
            }
            
            // If not found, look within trading panel for time display
            if (!expirationElement && tradingPanel) {
                const panelElements = tradingPanel.querySelectorAll('*');
                for (const el of panelElements) {
                    if (el.offsetParent === null) continue;
                    const text = el.textContent.trim();
                    const classes = el.className || '';
                    
                    // Skip if it looks like chart timeframe (M1, M5, H1, etc.)
                    if (/^[MHD]\d+$/i.test(text)) continue;
                    
                    // Match trade expiration format: "0:30", "1:00", "5:00"
                    if (/^\d{1,2}:\d{2}$/.test(text) && !classes.includes('chart')) {
                        expirationElement = el;
                        log(`Found expiration in panel: "${text}"`);
                        break;
                    }
                }
            }
            
            // Fallback: Look near amount input
            if (!expirationElement && amountInput) {
                const parent = amountInput.closest('.deals-group, .trading-panel, .option-panel, [class*="trade"]');
                if (parent) {
                    const timeElements = parent.querySelectorAll('[class*="time"]');
                    for (const el of timeElements) {
                        const text = el.textContent.trim();
                        if (/^\d{1,2}:\d{2}$/.test(text)) {
                            expirationElement = el;
                            log(`Found expiration near amount: "${text}"`);
                            break;
                        }
                    }
                }
            }
            
            // Last resort: Find clickable time display that's NOT in chart area
            if (!expirationElement) {
                const allTimeElements = document.querySelectorAll('[class*="time"]');
                for (const el of allTimeElements) {
                    if (el.offsetParent === null) continue;
                    
                    // Skip chart timeframe elements
                    const isChart = el.closest('.chart, [class*="chart"], .candles, [class*="candle"]');
                    if (isChart) continue;
                    
                    const text = el.textContent.trim();
                    // Trade expiration format: "0:30", "1:00", etc. (not "M1", "M5")
                    if (/^\d{1,2}:\d{2}$/.test(text)) {
                        expirationElement = el;
                        log(`Found expiration (fallback): "${text}"`);
                        break;
                    }
                }
            }
            
            if (!expirationElement) {
                log('⚠️ Trade expiration selector not found');
                return false;
            }
            
            // Click to open expiration dropdown
            log('Opening expiration picker...');
            expirationElement.click();
            await sleep(600);
            
            // Try parent if dropdown didn't open
            const dropdownOpened = document.querySelector('[class*="time-list"], [class*="dropdown"]:not([class*="chart"]), [class*="picker-list"]');
            if (!dropdownOpened) {
                const parent = expirationElement.parentElement;
                if (parent) {
                    parent.click();
                    await sleep(600);
                }
            }
            
            // Find and click the correct expiration time
            const targetTime = formatExpirationTime(expirySeconds);
            log(`Looking for expiration: ${targetTime}`);
            
            // Get expiration options (NOT chart timeframe options)
            let options = [];
            const optionSelectors = [
                '.time-list__item',
                '.time-item:not([class*="chart"])',
                '[class*="time-option"]',
                '[class*="dropdown"]:not([class*="chart"]) [class*="item"]',
                '.option-time-item'
            ];
            
            for (const sel of optionSelectors) {
                options = document.querySelectorAll(sel);
                // Filter out chart timeframe options
                options = Array.from(options).filter(opt => {
                    const text = opt.textContent.trim();
                    // Exclude M1, M5, H1, D1 style (chart timeframes)
                    return !/^[MHD]\d+$/i.test(text);
                });
                if (options.length > 0) {
                    log(`Found ${options.length} expiration options`);
                    break;
                }
            }
            
            if (options.length === 0) {
                log('⚠️ No expiration options found');
                closeDropdowns();
                return false;
            }
            
            // Click matching expiration option
            let clicked = false;
            const targetFormats = getExpirationFormats(expirySeconds);
            
            for (const opt of options) {
                if (opt.offsetParent === null) continue;
                const text = opt.textContent.trim();
                
                for (const target of targetFormats) {
                    if (text === target || text.includes(target)) {
                        log(`✓ Clicking expiration: "${text}"`);
                        opt.click();
                        clicked = true;
                        await sleep(300);
                        break;
                    }
                }
                if (clicked) break;
            }
            
            closeDropdowns();
            
            if (clicked) {
                log(`✓ Trade expiration set to ${expirySeconds}s`);
                return true;
            } else {
                log(`⚠️ Could not find ${expirySeconds}s expiration option`);
                return false;
            }
            
        } catch (e) {
            log(`Expiration switch error: ${e.message}`);
            closeDropdowns();
            return false;
        }
    }
    
    // Format seconds to expiration display format (mm:ss)
    function formatExpirationTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    
    // Generate various expiration time formats to match
    function getExpirationFormats(seconds) {
        const formats = [];
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        
        // Primary format: "0:30", "1:00", "5:00"
        formats.push(`${mins}:${secs.toString().padStart(2, '0')}`);
        
        // Alternative formats
        if (seconds < 60) {
            formats.push(`0:${seconds.toString().padStart(2, '0')}`);
            formats.push(`${seconds}s`);
            formats.push(`${seconds} sec`);
        } else {
            formats.push(`${mins}m`);
            formats.push(`${mins} min`);
            if (secs === 0) {
                formats.push(`${mins}:00`);
            }
        }
        
        return formats;
    }
    
    // Close any open dropdowns
    function closeDropdowns() {
        try {
            // Click outside
            document.body.click();
            // Press Escape
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
            // Click any overlay/backdrop
            const overlays = document.querySelectorAll('[class*="overlay"], [class*="backdrop"]');
            overlays.forEach(o => o.click());
        } catch (e) {}
    }
    
    // Get current trade expiration from PO UI
    function getCurrentTimeframe() {
        // Look for trade expiration display (NOT chart timeframe)
        const selectors = [
            '.deal-time__value',
            '.deal-time',
            '.option__time-item',
            '.time-wrap__value',
            '.trading-panel .time-item'
        ];
        
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.textContent) {
                const text = el.textContent.trim();
                // Skip chart timeframes (M1, M5, H1, etc.)
                if (/^[MHD]\d+$/i.test(text)) continue;
                return parseTimeToSeconds(text);
            }
        }
        
        return null;
    }
    
    // Parse time text to seconds
    function parseTimeToSeconds(text) {
        if (!text) return 0;
        text = text.trim().toLowerCase();
        
        // "1:30" or "0:30" format
        const colonMatch = text.match(/^(\d{1,2}):(\d{2})$/);
        if (colonMatch) {
            return parseInt(colonMatch[1]) * 60 + parseInt(colonMatch[2]);
        }
        
        // "30s"
        if (text.endsWith('s')) {
            return parseInt(text) || 0;
        }
        
        // "1m" or "2min"
        if (text.includes('m')) {
            return (parseInt(text) || 0) * 60;
        }
        
        return 0;
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ===========================================
    // BUTTON DETECTION
    // ===========================================
    function findTradeButtons() {
        const callBtn = document.querySelector('.btn-call');
        const putBtn = document.querySelector('.btn-put');
        buttonsReady = callBtn && putBtn && callBtn.offsetParent !== null;
        return { callBtn, putBtn, ready: buttonsReady };
    }

    async function waitForButtons(timeout = 5000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            const { ready } = findTradeButtons();
            if (ready) return true;
            await sleep(300);
        }
        return false;
    }

    // ===========================================
    // TOGGLE FUNCTIONS
    // ===========================================
    function toggleAuto() {
        CONFIG.AUTO_TRADE_ENABLED = !CONFIG.AUTO_TRADE_ENABLED;
        const btn = document.getElementById('gpt-auto');
        if (btn) {
            btn.textContent = CONFIG.AUTO_TRADE_ENABLED ? 'AUTO ON' : 'AUTO OFF';
            btn.className = 'btn-auto' + (CONFIG.AUTO_TRADE_ENABLED ? '' : ' off');
        }
        log('Auto: ' + (CONFIG.AUTO_TRADE_ENABLED ? 'ON' : 'OFF'));
    }

    function toggleAssetSwitch() {
        CONFIG.AUTO_SWITCH_ASSET = !CONFIG.AUTO_SWITCH_ASSET;
        const btn = document.getElementById('gpt-switch');
        if (btn) {
            btn.textContent = CONFIG.AUTO_SWITCH_ASSET ? 'SWITCH ON' : 'SWITCH OFF';
            btn.className = 'btn-switch' + (CONFIG.AUTO_SWITCH_ASSET ? '' : ' off');
        }
        log('Switch: ' + (CONFIG.AUTO_SWITCH_ASSET ? 'ON' : 'OFF'));
    }

    function toggleScanMode() {
        CONFIG.SCAN_MODE = !CONFIG.SCAN_MODE;
        const btn = document.getElementById('gpt-scan');
        if (btn) {
            btn.textContent = CONFIG.SCAN_MODE ? 'SCAN ON' : 'SCAN';
            btn.className = 'btn-scan' + (CONFIG.SCAN_MODE ? ' on' : '');
        }
        updateUI('connected');
        log('Scan: ' + (CONFIG.SCAN_MODE ? 'ON' : 'OFF'));
        if (CONFIG.SCAN_MODE) scanMarkets();
    }

    function resetBot() {
        log('RESETTING...');
        isTrading = false;
        lastProcessedSignalId = '';
        recentlyTradedAssets = {};  // Clear cooldown timestamps
        failedSwitchAttempts = {};  // Clear failed switch tracking
        lastTradeTime = 0;
        
        const sigEl = document.getElementById('gpt-signal');
        if (sigEl) { sigEl.textContent = 'RESET'; sigEl.className = 'signal wait'; }
        
        findTradeButtons();
        getCurrentAsset();
        updateUI('connected');
        
        setTimeout(() => checkSignal(true), 500);
    }
    
    // Check if an asset is on cooldown (recently traded)
    function isAssetOnCooldown(assetBase) {
        const tradedTime = recentlyTradedAssets[assetBase];
        if (!tradedTime) return false;
        
        const elapsed = Date.now() - tradedTime;
        if (elapsed > ASSET_COOLDOWN_MS) {
            // Cooldown expired, remove from tracking
            delete recentlyTradedAssets[assetBase];
            return false;
        }
        return true;
    }
    
    // Check if we've failed to switch to this asset too many times
    function hasExceededSwitchAttempts(assetBase) {
        return (failedSwitchAttempts[assetBase] || 0) >= MAX_SWITCH_ATTEMPTS;
    }
    
    // Mark asset as recently traded
    function markAssetTraded(assetBase) {
        recentlyTradedAssets[assetBase] = Date.now();
        // Clear any failed switch attempts since we successfully traded
        delete failedSwitchAttempts[assetBase];
    }
    
    // Record a failed switch attempt
    function recordFailedSwitch(assetBase) {
        failedSwitchAttempts[assetBase] = (failedSwitchAttempts[assetBase] || 0) + 1;
        log(`Switch attempts for ${assetBase}: ${failedSwitchAttempts[assetBase]}/${MAX_SWITCH_ATTEMPTS}`);
    }

    // ===========================================
    // MARKET SCANNING - FAVORITES + PAYOUT FILTER
    // ===========================================
    
    // Cache for favorites and payouts (refresh periodically)
    let cachedFavorites = null;
    let favoritesLastUpdate = 0;
    const FAVORITES_CACHE_MS = 60000; // Refresh favorites every 60 seconds
    
    async function scanMarkets() {
        if (isTrading) {
            log('Busy trading, skip scan');
            return;
        }
        
        if (isScanning) {
            log('Already scanning, skip');
            return;
        }

        // Check cooldown
        const now = Date.now();
        if (now - lastTradeTime < CONFIG.TRADE_COOLDOWN) {
            log(`Cooldown: ${((CONFIG.TRADE_COOLDOWN - (now - lastTradeTime)) / 1000).toFixed(1)}s`);
            return;
        }
        
        isScanning = true;  // Lock scanning

        // Determine assets to scan
        let assetsToScan = CONFIG.SCAN_ASSETS;
        let assetPayouts = {}; // {symbol: payout}
        
        if (!CONFIG.AUTO_SWITCH_ASSET) {
            // SWITCH OFF - Only scan current asset
            const currentAssetRaw = getCurrentAsset();
            if (currentAssetRaw) {
                const normalized = currentAssetRaw.replace('/', '').replace(' ', '_').toUpperCase();
                assetsToScan = normalized;
                
                // Get current asset's payout
                const currentPayout = getCurrentPayout();
                if (currentPayout !== null) {
                    assetPayouts[normalized] = currentPayout;
                    log(`SWITCH OFF - Current: ${normalized} (${currentPayout}%)`);
                    
                    // Check payout requirement
                    if (currentPayout < CONFIG.MIN_PAYOUT) {
                        log(`⚠️ Payout ${currentPayout}% < ${CONFIG.MIN_PAYOUT}% required. Skipping.`);
                        const sigEl = document.getElementById('gpt-signal');
                        if (sigEl) { sigEl.textContent = 'LOW PAY'; sigEl.className = 'signal wait'; }
                        return;
                    }
                } else {
                    log(`SWITCH OFF - Current: ${normalized} (payout unknown)`);
                }
            } else {
                log('Cannot detect current asset, using defaults');
            }
        } else {
            // SWITCH ON - Scan favorites with 65%+ payout
            if (CONFIG.SCAN_FAVORITES_ONLY) {
                // Check if we need to refresh favorites cache
                if (!cachedFavorites || (now - favoritesLastUpdate > FAVORITES_CACHE_MS)) {
                    log('Refreshing favorites list...');
                    cachedFavorites = await getFavoriteAssets();
                    favoritesLastUpdate = now;
                }
                
                if (cachedFavorites && cachedFavorites.length > 0) {
                    // Filter by minimum payout
                    const eligibleAssets = cachedFavorites.filter(a => a.payout >= CONFIG.MIN_PAYOUT);
                    
                    if (eligibleAssets.length > 0) {
                        assetsToScan = eligibleAssets.map(a => a.apiSymbol).join(',');
                        eligibleAssets.forEach(a => { assetPayouts[a.apiSymbol] = a.payout; });
                        log(`FAVORITES: ${eligibleAssets.length}/${cachedFavorites.length} with ${CONFIG.MIN_PAYOUT}%+ payout`);
                    } else {
                        log(`⚠️ No favorites with ${CONFIG.MIN_PAYOUT}%+ payout found`);
                        const sigEl = document.getElementById('gpt-signal');
                        if (sigEl) { sigEl.textContent = 'NO FAV'; sigEl.className = 'signal wait'; }
                        return;
                    }
                } else {
                    log('No favorites found, using default assets');
                }
            } else {
                const cooldownCount = Object.keys(recentlyTradedAssets).filter(a => isAssetOnCooldown(a)).length;
                log(`SWITCH ON - Scanning all (${cooldownCount} on cooldown)`);
            }
        }
        
        // Build URL with optional preferred expiry
        let url = `${CONFIG.API_URL}/signals/scan-markets?assets=${assetsToScan}&min_confidence=${CONFIG.MIN_CONFIDENCE}&max_signals=10`;
        if (CONFIG.PREFERRED_EXPIRY) {
            url += `&preferred_expiry=${CONFIG.PREFERRED_EXPIRY}`;
        }
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: url,
            headers: { 'Accept': 'application/json' },
            timeout: 20000,
            onload: function(res) {
                isScanning = false;  // Release scan lock
                
                try {
                    if (res.status !== 200) {
                        log('Scan error: ' + res.status);
                        return;
                    }
                    
                    const data = JSON.parse(res.responseText);
                    updateUI('connected');
                    
                    if (data.success && data.top_signals && data.top_signals.length > 0) {
                        log(`Found ${data.top_signals.length} signals`);
                        
                        // Find the best signal that:
                        // 1. Meets payout requirement (65%+)
                        // 2. Is not on cooldown (recently traded)
                        // 3. Has not exceeded switch attempt limit
                        // 4. If SWITCH OFF, must match current asset
                        let selectedSignal = null;
                        let skippedReasons = [];
                        
                        for (const signal of data.top_signals) {
                            const assetBase = signal.symbol.replace('_OTC', '').replace('_', '');
                            const assetKey = signal.symbol;
                            
                            // Generate unique signal ID for deduplication
                            const signalId = `${signal.symbol}_${signal.direction}_${signal.timestamp || Date.now()}`;
                            
                            // Check if this is a duplicate signal (same asset+direction within interval)
                            if (signalId === lastProcessedSignalId && (Date.now() - lastProcessedSignalTimestamp) < MIN_SIGNAL_INTERVAL_MS) {
                                skippedReasons.push(`${assetBase}: duplicate`);
                                continue;
                            }
                            
                            // Check payout requirement
                            const payout = assetPayouts[assetKey] || assetPayouts[assetBase];
                            if (payout !== undefined && payout < CONFIG.MIN_PAYOUT) {
                                skippedReasons.push(`${assetBase}: payout ${payout}%`);
                                continue;
                            }
                            
                            // If SWITCH OFF, only accept signals for current asset
                            if (!CONFIG.AUTO_SWITCH_ASSET) {
                                const currentAssetBase = getCurrentAsset()?.replace('/', '').replace(' OTC', '').replace(/[^A-Z0-9]/gi, '').toUpperCase();
                                if (currentAssetBase && assetBase !== currentAssetBase) {
                                    skippedReasons.push(`${assetBase}: not current`);
                                    continue;
                                }
                            }
                            
                            // Check time-based cooldown
                            if (isAssetOnCooldown(assetBase)) {
                                const remaining = Math.ceil((ASSET_COOLDOWN_MS - (Date.now() - recentlyTradedAssets[assetBase])) / 1000);
                                skippedReasons.push(`${assetBase}: cooldown ${remaining}s`);
                                continue;
                            }
                            
                            // Check if switch has failed too many times (only relevant if SWITCH ON)
                            if (CONFIG.AUTO_SWITCH_ASSET && hasExceededSwitchAttempts(assetBase)) {
                                skippedReasons.push(`${assetBase}: switch failed`);
                                continue;
                            }
                            
                            // Add payout info to signal for display
                            if (payout !== undefined) {
                                signal.payout = payout;
                            }
                            
                            // Store signal ID to prevent duplicates
                            signal._signalId = signalId;
                            
                            selectedSignal = signal;
                            break;
                        }
                        
                        // Log skipped assets for debugging
                        if (skippedReasons.length > 0) {
                            log(`Skipped: ${skippedReasons.slice(0, 3).join(', ')}${skippedReasons.length > 3 ? '...' : ''}`);
                        }
                        
                        // If all assets are blocked, wait for cooldowns to expire
                        if (!selectedSignal) {
                            log('No eligible signals. Waiting...');
                            const sigEl = document.getElementById('gpt-signal');
                            if (sigEl) { sigEl.textContent = 'WAIT'; sigEl.className = 'signal wait'; }
                            return;
                        }
                        
                        // Check if already trading to prevent double execution
                        if (isTrading) {
                            log('Trade already in progress, skip');
                            isScanning = false;  // Release scan lock
                            return;
                        }
                        
                        // Set trading lock IMMEDIATELY before any async operations
                        isTrading = true;
                        isScanning = false;  // Release scan lock since we're moving to trading
                        
                        // Mark signal as processed BEFORE execution
                        lastProcessedSignalId = selectedSignal._signalId;
                        lastProcessedSignalTimestamp = Date.now();
                        
                        // Log selected signal with expiry and payout info
                        const expiry = selectedSignal.expiry_seconds || 60;
                        const payoutInfo = selectedSignal.payout ? ` ${selectedSignal.payout}%` : '';
                        log(`✓ ${selectedSignal.direction} ${selectedSignal.symbol} (${selectedSignal.confidence.toFixed(0)}%${payoutInfo}) @ ${expiry}s`);
                        
                        updateUI('trading', selectedSignal);
                        
                        if (CONFIG.AUTO_TRADE_ENABLED) {
                            executeTradeWithAssetSwitch(selectedSignal);
                        } else {
                            log('Auto OFF');
                            isTrading = false;  // Release if not executing
                            updateUI('connected', selectedSignal);
                        }
                    } else {
                        log('No signals found');
                        isScanning = false;  // Release scan lock
                        const sigEl = document.getElementById('gpt-signal');
                        if (sigEl) { sigEl.textContent = 'WAIT'; sigEl.className = 'signal wait'; }
                    }
                } catch (e) {
                    isScanning = false;  // Release scan lock on error
                    log('Parse error: ' + e.message);
                }
            },
            onerror: function() { 
                isScanning = false;  // Release scan lock on error
                log('Connection error'); 
            },
            ontimeout: function() { 
                isScanning = false;  // Release scan lock on timeout
                log('Timeout'); 
            }
        });
    }

    // ===========================================
    // SIGNAL FETCHING
    // ===========================================
    function checkSignal(force = false) {
        if (isTrading && !force) {
            log('Busy trading...');
            return;
        }
        
        if (isScanning) {
            log('Busy scanning...');
            return;
        }

        findTradeButtons();
        getCurrentAsset();

        if (CONFIG.SCAN_MODE) {
            scanMarkets();
            return;
        }

        log('Fetching signal...');
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: CONFIG.API_URL + '/signals/latest',
            headers: { 'Accept': 'application/json' },
            timeout: 10000,
            onload: function(res) {
                try {
                    if (res.status !== 200) {
                        log('API Error: ' + res.status);
                        updateUI('disconnected');
                        return;
                    }
                    
                    const data = JSON.parse(res.responseText);
                    updateUI('connected');
                    
                    if (data.success && data.signal) {
                        const signal = data.signal;
                        const signalId = signal.signal_id || signal.id || signal.timestamp;
                        
                        log(`Signal: ${signal.direction} ${signal.symbol}`);
                        
                        // Check if same signal and within minimum interval
                        const now = Date.now();
                        const isSameSignal = signalId === lastProcessedSignalId;
                        const withinInterval = (now - lastProcessedSignalTimestamp) < MIN_SIGNAL_INTERVAL_MS;
                        
                        if (isSameSignal && withinInterval && !force) {
                            log('Same signal, waiting...');
                            updateUI('connected', signal);
                            return;
                        }
                        
                        // Double-check not already trading
                        if (isTrading) {
                            log('Trade in progress, skip');
                            return;
                        }
                        
                        log('NEW SIGNAL!');
                        lastProcessedSignalId = signalId;
                        lastProcessedSignalTimestamp = now;
                        updateUI('trading', signal);
                        
                        if (CONFIG.AUTO_TRADE_ENABLED) {
                            executeTradeWithAssetSwitch(signal);
                        } else {
                            updateUI('connected', signal);
                        }
                    } else {
                        log(data.message || 'No signal');
                    }
                } catch (e) {
                    log('Error: ' + e.message);
                }
            },
            onerror: function() { log('Connection error'); updateUI('disconnected'); },
            ontimeout: function() { log('Timeout'); }
        });
    }

    // ===========================================
    // TRADE EXECUTION - WITH ASSET + TIMEFRAME SWITCHING
    // ===========================================
    async function executeTradeWithAssetSwitch(signal) {
        // Double-check trading lock (should already be true from caller)
        if (!isTrading) {
            log('WARNING: Trading lock not set, setting now');
            isTrading = true;
        }
        
        lastTradeTime = Date.now();
        updateUI('trading', signal);
        
        // Determine original direction
        let originalIsCall = signal.direction === 'CALL' || signal.direction === 'BUY';
        
        // Apply inversion if enabled
        let isCall = originalIsCall;
        if (invertSignals) {
            isCall = !originalIsCall;
            log(`🔄 INVERTED: ${originalIsCall ? 'CALL' : 'PUT'} → ${isCall ? 'CALL' : 'PUT'}`);
        }
        
        const assetBase = signal.symbol.replace('_OTC', '').replace('_', '');
        const signalExpiry = signal.expiry_seconds || 60;
        log(`Executing: ${isCall ? 'CALL' : 'PUT'} on ${signal.symbol} @ ${signalExpiry}s${invertSignals ? ' (INVERTED)' : ''}`);
        
        try {
            // Step 1: Switch asset if SWITCH is enabled
            if (CONFIG.AUTO_SWITCH_ASSET && signal.symbol) {
                const switched = await switchToAsset(signal.symbol);
                if (!switched) {
                    log(`Switch to ${assetBase} FAILED - recording attempt`);
                    recordFailedSwitch(assetBase);
                    
                    // Release trading lock and let next scan try a different asset
                    isTrading = false;
                    updateUI('connected');
                    log('Will try different asset on next scan');
                    return;  // Don't trade on wrong asset
                }
                await sleep(300);
            }
            
            // Step 2: Switch timeframe if enabled and expiry differs from current
            if (CONFIG.AUTO_SWITCH_TIMEFRAME && signalExpiry) {
                const currentTF = getCurrentTimeframe();
                if (currentTF !== signalExpiry) {
                    log(`Timeframe mismatch: current=${currentTF}s, signal=${signalExpiry}s`);
                    const tfSwitched = await switchToTimeframe(signalExpiry);
                    if (!tfSwitched) {
                        log(`WARNING: Could not switch to ${signalExpiry}s timeframe`);
                        // Continue anyway - some timeframes might not be available
                    }
                    await sleep(300);
                } else {
                    log(`Timeframe OK: ${signalExpiry}s`);
                }
            }
            
            // Step 3: Wait for buttons
            const buttonsFound = await waitForButtons(3000);
            if (!buttonsFound) {
                log('Buttons not found!');
                isTrading = false;
                updateUI('connected');
                return;
            }
            
            // Play sound (different tone for inverted)
            if (CONFIG.SOUND_ENABLED) {
                try {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const osc = ctx.createOscillator();
                    // Higher pitch if inverted, different tones for CALL/PUT
                    const baseFreq = isCall ? 800 : 400;
                    osc.frequency.value = invertSignals ? baseFreq + 200 : baseFreq;
                    osc.connect(ctx.destination);
                    osc.start();
                    setTimeout(() => osc.stop(), invertSignals ? 200 : 150);
                } catch(e) {}
            }
            
            // Step 4: Click trade button
            const clicked = clickTradeButton(isCall);
            
            if (clicked) {
                tradeCount++;
                
                // Mark this asset as traded with timestamp
                markAssetTraded(assetBase);
                
                const tradeType = isCall ? 'CALL' : 'PUT';
                const invLabel = invertSignals ? ' [INV]' : '';
                log(`TRADE #${tradeCount}: ${tradeType}${invLabel} on ${assetBase} @ ${signalExpiry}s`);
                
                try {
                    GM_notification({
                        title: `${tradeType} Executed${invLabel}`,
                        text: `${signal.symbol} - ${signal.confidence || 85}% @ ${signalExpiry}s${invertSignals ? ' (Inverted)' : ''}`,
                        timeout: 2000
                    });
                } catch(e) {}
            } else {
                log('Click failed!');
            }
            
        } catch (e) {
            log(`Error: ${e.message}`);
        }
        
        // Short cooldown
        setTimeout(() => {
            isTrading = false;
            updateUI('connected');
            log('Ready for next trade');
        }, CONFIG.TRADE_COOLDOWN);
    }

    function clickTradeButton(isCall) {
        // Prevent double clicks - check if we just executed a trade
        const now = Date.now();
        if (now - lastTradeExecutionTime < MIN_TRADE_INTERVAL_MS) {
            log(`⚠️ Trade blocked - too soon (${Math.round((MIN_TRADE_INTERVAL_MS - (now - lastTradeExecutionTime))/1000)}s cooldown)`);
            return false;
        }
        
        const selector = isCall ? '.btn-call' : '.btn-put';
        const btn = document.querySelector(selector);
        
        if (btn && btn.offsetParent !== null) {
            // Mark execution time BEFORE clicking
            lastTradeExecutionTime = now;
            
            log(`Clicking ${selector}`);
            
            // Single click only - avoid double execution
            btn.click();
            
            return true;
        }
        
        log(`Button ${selector} not found`);
        return false;
    }

    // ===========================================
    // INITIALIZATION
    // ===========================================
    function init() {
        log('Initializing v5.4.0...');
        
        setTimeout(() => {
            createPanel();
            
            // Restore settings
            CONFIG.AUTO_TRADE_ENABLED = GM_getValue('autoEnabled', true);
            CONFIG.AUTO_SWITCH_ASSET = GM_getValue('autoSwitch', true);
            CONFIG.SCAN_MODE = GM_getValue('scanMode', false);
            CONFIG.AUTO_SWITCH_TIMEFRAME = GM_getValue('autoSwitchTimeframe', true);
            CONFIG.SCAN_FAVORITES_ONLY = GM_getValue('scanFavoritesOnly', true);
            CONFIG.MIN_PAYOUT = GM_getValue('minPayout', 65);
            
            // Update buttons based on saved settings
            if (!CONFIG.AUTO_TRADE_ENABLED) {
                const btn = document.getElementById('gpt-auto');
                if (btn) { btn.textContent = 'AUTO OFF'; btn.className = 'btn-auto off'; }
            }
            if (!CONFIG.AUTO_SWITCH_ASSET) {
                const btn = document.getElementById('gpt-switch');
                if (btn) { btn.textContent = 'SWITCH OFF'; btn.className = 'btn-switch off'; }
            }
            if (CONFIG.SCAN_MODE) {
                const btn = document.getElementById('gpt-scan');
                if (btn) { btn.textContent = 'SCAN ON'; btn.className = 'btn-scan on'; }
            }
            
            findTradeButtons();
            getCurrentAsset();
            updateUI('connected');
            
            // Start polling
            setInterval(checkSignal, CONFIG.POLL_INTERVAL);
            checkSignal();
            
            log(`Ready! FAV=${CONFIG.SCAN_FAVORITES_ONLY} PAY>=${CONFIG.MIN_PAYOUT}%`);
        }, 2000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
