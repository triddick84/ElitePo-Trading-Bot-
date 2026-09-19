/**
 * UI Panel Component - AI's Elite PO Traders Bot
 * 
 * Mobile + Desktop compatible.
 * Uses direct DOM injection with !important inline styles.
 * All CSS classes use __epb__ prefix to avoid Pocket Option conflicts.
 * Touch events for mobile drag. Responsive sizing.
 */

import { CONFIG } from '../core/config.js';
import { state, setState, saveState } from '../core/state.js';
import { log, setLogContainer } from '../core/logger.js';
import { stealthMode } from '../core/stealthMode.js';
import { forexOrderPoller } from '../trading/forexOrderPoller.js';
import { mt5Adapter } from '../trading/mt5Adapter.js';
import { tradeResultWatcher } from '../trading/tradeResultWatcher.js';
import { get as apiGet } from '../utils/api.js';

let panelEl = null;
let watchdogInterval = null;
const P = '__epb__';

function isMobile() {
  return /Android|iPhone|iPad|iPod|Opera Mini|IEMobile|WPDesktop/i.test(navigator.userAgent)
    || window.innerWidth < 500;
}

/**
 * Inject CSS
 */
function injectCSS() {
  const mobile = isMobile();
  // Iter 141 — Compact 320 px default (user request "small UI").
  // Users retain full resize via the new dual-edge handles (left + right).
  const W = mobile ? 290 : 320;
  const FONT = mobile ? 11 : 12;
  const BTN_PAD = mobile ? '10px 6px' : '7px 6px';
  const BTN_FONT = mobile ? 12 : 11;

  const css = `
    #${P}host {
      position: fixed !important;
      top: 5px !important;
      right: 5px !important;
      z-index: 2147483647 !important;
      display: block !important;
      visibility: visible !important;
      opacity: 1 !important;
      pointer-events: auto !important;
      width: ${W}px !important;
      max-width: 90vw !important;
      min-width: 180px !important;
      transform: none !important;
      font-family: -apple-system, 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
      font-size: ${FONT}px !important;
      line-height: 1.4 !important;
      color: #e6edf3 !important;
      box-sizing: border-box !important;
      -webkit-tap-highlight-color: transparent !important;
    }
    /* Resize handle (Iter 59) — bottom-right corner grip for panel width */
    .${P}resize {
      position: absolute !important;
      bottom: 0 !important;
      right: 0 !important;
      width: ${mobile ? 22 : 16}px !important;
      height: ${mobile ? 22 : 16}px !important;
      cursor: nwse-resize !important;
      z-index: 10 !important;
      background:
        linear-gradient(135deg, transparent 0%, transparent 50%,
        rgba(139,148,158,0.5) 50%, rgba(139,148,158,0.5) 60%,
        transparent 60%, transparent 70%,
        rgba(139,148,158,0.5) 70%, rgba(139,148,158,0.5) 80%,
        transparent 80%) !important;
      border-bottom-right-radius: ${mobile ? 8 : 12}px !important;
      touch-action: none !important;
      -webkit-tap-highlight-color: transparent !important;
    }
    .${P}resize:hover {
      background:
        linear-gradient(135deg, transparent 0%, transparent 50%,
        #58a6ff 50%, #58a6ff 60%,
        transparent 60%, transparent 70%,
        #58a6ff 70%, #58a6ff 80%,
        transparent 80%) !important;
    }
    .${P}resize.active {
      background:
        linear-gradient(135deg, transparent 0%, transparent 50%,
        #3b82f6 50%, #3b82f6 60%,
        transparent 60%, transparent 70%,
        #3b82f6 70%, #3b82f6 80%,
        transparent 80%) !important;
    }
    /* Iter 141 — side resize handles (left + right edges). Thin invisible
       strips that show a blue vertical bar on hover. */
    .${P}sideresize {
      position: absolute !important;
      top: 32px !important;
      bottom: 20px !important;
      width: 6px !important;
      cursor: ew-resize !important;
      z-index: 9 !important;
      background: transparent !important;
      touch-action: none !important;
      -webkit-tap-highlight-color: transparent !important;
    }
    .${P}sideresize.left { left: -3px !important; }
    .${P}sideresize.right { right: -3px !important; }
    .${P}sideresize:hover {
      background: linear-gradient(90deg, transparent, #58a6ff, transparent) !important;
    }
    .${P}sideresize.active {
      background: linear-gradient(90deg, transparent, #3b82f6, transparent) !important;
    }
    #${P}host * {
      box-sizing: border-box !important;
      margin: 0 !important;
      padding: 0 !important;
      font-family: inherit !important;
      line-height: inherit !important;
    }
    #${P}panel {
      width: 100% !important;
      background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%) !important;
      border: 1px solid #30363d !important;
      border-radius: ${mobile ? 8 : 12}px !important;
      box-shadow: 0 8px 32px rgba(0,0,0,0.6), 0 0 1px rgba(88,166,255,0.3) !important;
      user-select: none !important;
      overflow: hidden !important;
      -webkit-user-select: none !important;
      touch-action: none !important;
      position: relative !important;
    }
    .${P}header {
      display: flex !important;
      justify-content: space-between !important;
      align-items: center !important;
      padding: ${mobile ? '8px 10px' : '10px 12px'} !important;
      background: linear-gradient(90deg, rgba(56,139,253,0.15) 0%, rgba(0,0,0,0.3) 100%) !important;
      cursor: move !important;
      border-bottom: 1px solid #21262d !important;
      touch-action: none !important;
    }
    .${P}title {
      font-weight: 700 !important;
      font-size: ${mobile ? 11 : 12}px !important;
      background: linear-gradient(90deg, #58a6ff, #79c0ff) !important;
      -webkit-background-clip: text !important;
      -webkit-text-fill-color: transparent !important;
      background-clip: text !important;
    }
    .${P}hright {
      display: flex !important;
      align-items: center !important;
      gap: 8px !important;
    }
    .${P}minbtn {
      background: none !important;
      border: 1px solid #30363d !important;
      color: #8b949e !important;
      width: ${mobile ? 28 : 20}px !important;
      height: ${mobile ? 28 : 20}px !important;
      border-radius: 4px !important;
      cursor: pointer !important;
      font-size: ${mobile ? 14 : 12}px !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      -webkit-tap-highlight-color: transparent !important;
    }
    .${P}minbtn:hover, .${P}minbtn:active {
      background: #30363d !important;
      color: #e6edf3 !important;
    }
    /* Iter 110 — Master Auto-Trade pill */
    .${P}masterbtn {
      display: inline-flex !important;
      align-items: center !important;
      gap: 5px !important;
      padding: ${mobile ? '4px 10px' : '3px 9px'} !important;
      height: ${mobile ? 28 : 22}px !important;
      background: #21262d !important;
      border: 1px solid #f85149 !important;
      color: #f85149 !important;
      border-radius: 999px !important;
      font-size: ${mobile ? 10 : 9}px !important;
      font-weight: 800 !important;
      letter-spacing: 0.6px !important;
      cursor: pointer !important;
      transition: all 0.2s !important;
      -webkit-tap-highlight-color: transparent !important;
    }
    .${P}masterbtn.active {
      background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
      border-color: #10b981 !important;
      color: #ffffff !important;
      box-shadow: 0 0 8px rgba(16,185,129,0.55) !important;
    }
    .${P}masterbtn:hover { filter: brightness(1.15) !important; }
    .${P}masterled {
      width: 7px !important;
      height: 7px !important;
      border-radius: 50% !important;
      background: currentColor !important;
      box-shadow: 0 0 4px currentColor !important;
    }
    .${P}masterbtn.active .${P}masterled { animation: ${P}pulse 1.4s infinite !important; }
    /* Big Master toggle inside the Trade tab */
    .${P}masterbig {
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      gap: 8px !important;
      width: 100% !important;
      padding: ${mobile ? '12px' : '10px'} !important;
      background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%) !important;
      border: 1.5px solid #f87171 !important;
      color: #fecaca !important;
      border-radius: 8px !important;
      font-weight: 800 !important;
      font-size: ${mobile ? 14 : 13}px !important;
      letter-spacing: 1px !important;
      text-transform: uppercase !important;
      cursor: pointer !important;
      transition: all 0.25s !important;
      -webkit-tap-highlight-color: transparent !important;
    }
    .${P}masterbig.active {
      background: linear-gradient(135deg, #065f46 0%, #10b981 100%) !important;
      border-color: #34d399 !important;
      color: #ffffff !important;
      box-shadow: 0 0 12px rgba(16,185,129,0.5) !important;
    }
    .${P}masterbig:hover { filter: brightness(1.1) !important; }
    .${P}dot {
      width: ${mobile ? 12 : 10}px !important;
      height: ${mobile ? 12 : 10}px !important;
      border-radius: 50% !important;
      background: #484f58 !important;
      display: inline-block !important;
      transition: background 0.3s !important;
    }
    .${P}dot.connected { background: #3fb950 !important; box-shadow: 0 0 6px rgba(63,185,80,0.4) !important; }
    .${P}dot.scanning { background: #58a6ff !important; animation: ${P}pulse 1s infinite !important; }
    .${P}dot.trading { background: #d29922 !important; }
    .${P}dot.error { background: #f85149 !important; }
    @keyframes ${P}pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }
    .${P}body {
      padding: ${mobile ? '8px' : '10px'} !important;
    }
    .${P}body.collapsed {
      display: none !important;
    }
    .${P}row {
      display: flex !important;
      gap: ${mobile ? '4px' : '6px'} !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
      align-items: center !important;
    }
    .${P}btn {
      flex: 1 !important;
      padding: ${BTN_PAD} !important;
      border: 1px solid #30363d !important;
      border-radius: 6px !important;
      background: #21262d !important;
      color: #e6edf3 !important;
      font-size: ${BTN_FONT}px !important;
      font-weight: 600 !important;
      cursor: pointer !important;
      transition: all 0.15s !important;
      text-align: center !important;
      -webkit-tap-highlight-color: transparent !important;
      min-height: ${mobile ? 36 : 28}px !important;
    }
    .${P}btn:hover, .${P}btn:active {
      background: #30363d !important;
      border-color: #58a6ff !important;
    }
    .${P}btn.active {
      background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%) !important;
      border-color: #58a6ff !important;
      box-shadow: 0 0 8px rgba(56,139,253,0.3) !important;
    }
    /* LED indicator on every button — small green dot when active, grey when off */
    .${P}btn { position: relative !important; }
    .${P}btn::before {
      content: '' !important;
      position: absolute !important;
      top: 4px !important;
      left: 4px !important;
      width: 6px !important;
      height: 6px !important;
      border-radius: 50% !important;
      background: rgba(255,255,255,0.10) !important;
      border: 1px solid rgba(0,0,0,0.4) !important;
      transition: background 0.2s, box-shadow 0.2s !important;
      pointer-events: none !important;
    }
    .${P}btn.active::before {
      background: #3fb950 !important;
      box-shadow: 0 0 4px rgba(63,185,80,0.7) !important;
    }
    .${P}btn-go {
      background: linear-gradient(135deg, #238636 0%, #2ea043 100%) !important;
      border-color: #3fb950 !important;
    }
    .${P}btn-go:hover, .${P}btn-go:active {
      background: linear-gradient(135deg, #2ea043 0%, #3fb950 100%) !important;
    }
    .${P}btn-inv {
      flex: 0 0 ${mobile ? 70 : 80}px !important;
    }
    .${P}btn-inv.active {
      background: linear-gradient(135deg, #9e6a03 0%, #d29922 100%) !important;
      border-color: #d29922 !important;
      box-shadow: 0 0 8px rgba(210,153,34,0.3) !important;
    }
    .${P}btn-r21s {
      flex: 0 0 ${mobile ? 60 : 70}px !important;
      background: linear-gradient(135deg, #4c1d95 0%, #6d28d9 100%) !important;
      border-color: #7c3aed !important;
      font-size: ${mobile ? 10 : 11}px !important;
    }
    .${P}btn-r21s.active {
      background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%) !important;
      border-color: #a855f7 !important;
      box-shadow: 0 0 10px rgba(168,85,247,0.5) !important;
    }
    .${P}timing-row {
      display: flex !important;
      align-items: center !important;
      gap: 8px !important;
      padding: 4px 6px !important;
      background: rgba(124, 58, 237, 0.06) !important;
      border-left: 2px solid #7c3aed !important;
      border-radius: 4px !important;
      margin-top: 2px !important;
    }
    .${P}timing-label {
      font-size: ${mobile ? 9 : 10}px !important;
      color: #c9b6ff !important;
      flex: 0 0 auto !important;
      white-space: nowrap !important;
      font-weight: 600 !important;
    }
    .${P}timing-slider {
      flex: 1 !important;
      width: auto !important;
      height: 14px !important;
      -webkit-appearance: none !important;
      appearance: none !important;
      background: linear-gradient(90deg, #312e81 0%, #7c3aed 100%) !important;
      border-radius: 4px !important;
      outline: none !important;
      cursor: pointer !important;
      margin: 0 !important;
    }
    .${P}timing-slider::-webkit-slider-thumb {
      -webkit-appearance: none !important;
      appearance: none !important;
      width: 14px !important;
      height: 14px !important;
      background: #f0abfc !important;
      border: 2px solid #ffffff !important;
      border-radius: 50% !important;
      cursor: grab !important;
      box-shadow: 0 0 4px rgba(168,85,247,0.8) !important;
    }
    .${P}timing-slider::-moz-range-thumb {
      width: 14px !important;
      height: 14px !important;
      background: #f0abfc !important;
      border: 2px solid #ffffff !important;
      border-radius: 50% !important;
      cursor: grab !important;
      box-shadow: 0 0 4px rgba(168,85,247,0.8) !important;
    }
    .${P}timing-value {
      flex: 0 0 auto !important;
      font-size: ${mobile ? 10 : 11}px !important;
      color: #f0abfc !important;
      font-weight: 700 !important;
      min-width: 32px !important;
      text-align: right !important;
      font-variant-numeric: tabular-nums !important;
    }
    .${P}btn-cycle, .${P}btn-app, .${P}btn-ainv {
      font-size: ${mobile ? 10 : 11}px !important;
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 100%) !important;
      border-color: #2563eb !important;
    }
    .${P}btn-cycle.active, .${P}btn-app.active, .${P}btn-ainv.active {
      background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%) !important;
      border-color: #60a5fa !important;
      box-shadow: 0 0 10px rgba(59,130,246,0.5) !important;
    }
    .${P}invst {
      flex: 1 !important;
      font-size: ${mobile ? 9 : 10}px !important;
      color: #8b949e !important;
      overflow: hidden !important;
      text-overflow: ellipsis !important;
      white-space: nowrap !important;
      padding-left: 4px !important;
    }
    .${P}invst.on { color: #d29922 !important; font-weight: 600 !important; }
    .${P}stats {
      display: flex !important;
      justify-content: space-between !important;
      padding: ${mobile ? '6px' : '8px'} !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-radius: 6px !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
      position: relative !important;
    }
    .${P}statsreset {
      position: absolute !important;
      top: 2px !important;
      right: 2px !important;
      width: ${mobile ? 16 : 14}px !important;
      height: ${mobile ? 16 : 14}px !important;
      border: none !important;
      background: rgba(248,81,73,0.10) !important;
      color: #f85149 !important;
      border-radius: 3px !important;
      cursor: pointer !important;
      font-size: ${mobile ? 10 : 9}px !important;
      font-weight: 700 !important;
      line-height: 1 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      padding: 0 !important;
      -webkit-tap-highlight-color: transparent !important;
      transition: all 0.15s !important;
    }
    .${P}statsreset:hover, .${P}statsreset:active {
      background: rgba(248,81,73,0.30) !important;
      color: #ffffff !important;
    }
    .${P}stat {
      text-align: center !important;
      flex: 1 !important;
    }
    .${P}stlbl {
      display: block !important;
      font-size: ${mobile ? 8 : 9}px !important;
      color: #8b949e !important;
      text-transform: uppercase !important;
      letter-spacing: 0.5px !important;
    }
    .${P}stval {
      font-weight: 700 !important;
      font-size: ${mobile ? 12 : 13}px !important;
      color: #e6edf3 !important;
    }
    .${P}btn-win {
      background: linear-gradient(135deg, #238636 0%, #2ea043 100%) !important;
      border-color: #3fb950 !important;
    }
    .${P}btn-loss {
      background: linear-gradient(135deg, #da3633 0%, #f85149 100%) !important;
      border-color: #f85149 !important;
    }
    .${P}mmrow {
      display: flex !important;
      align-items: center !important;
      gap: ${mobile ? '4px' : '6px'} !important;
      padding: ${mobile ? '5px 6px' : '6px 8px'} !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-radius: 6px !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
      font-size: ${mobile ? 10 : 11}px !important;
    }
    .${P}mmlbl { color: #8b949e !important; }
    .${P}mminp {
      width: ${mobile ? 48 : 55}px !important;
      padding: ${mobile ? '4px' : '3px 4px'} !important;
      border: 1px solid #30363d !important;
      border-radius: 4px !important;
      background: #0d1117 !important;
      color: #e6edf3 !important;
      font-size: ${mobile ? 12 : 11}px !important;
      -webkit-appearance: none !important;
    }
    .${P}stratrow {
      display: flex !important;
      align-items: center !important;
      gap: 4px !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
      padding: 4px 6px !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-radius: 6px !important;
    }
    .${P}thresholds {
      margin-top: ${mobile ? '6px' : '8px'} !important;
      padding: 6px !important;
      background: rgba(56, 189, 248, 0.06) !important;
      border: 1px solid rgba(56, 189, 248, 0.25) !important;
      border-radius: 6px !important;
    }
    .${P}thrhdr {
      font-size: ${mobile ? 9 : 10}px !important;
      color: #7dd3fc !important;
      font-weight: 700 !important;
      letter-spacing: 0.5px !important;
      margin-bottom: 4px !important;
      text-transform: uppercase !important;
    }
    .${P}thrrow {
      display: grid !important;
      grid-template-columns: auto 1fr auto 1fr !important;
      gap: 4px 6px !important;
      align-items: center !important;
      margin-bottom: 4px !important;
    }
    .${P}thrlbl {
      font-size: ${mobile ? 9 : 10}px !important;
      color: #94a3b8 !important;
      font-weight: 600 !important;
    }
    .${P}thrInp {
      width: 100% !important;
      padding: 2px 4px !important;
      background: #0d1117 !important;
      border: 1px solid #21262d !important;
      border-radius: 4px !important;
      color: #e6edf3 !important;
      font-size: ${mobile ? 10 : 11}px !important;
      font-variant-numeric: tabular-nums !important;
      text-align: center !important;
      -webkit-appearance: textfield !important;
    }
    .${P}thrInp:focus { outline: 1px solid #38bdf8 !important; }
    .${P}latencyrow {
      display: grid !important;
      grid-template-columns: auto 1fr auto !important;
      align-items: center !important;
      gap: 6px !important;
      margin-top: ${mobile ? '6px' : '8px'} !important;
      padding: 5px 7px !important;
      background: rgba(251, 191, 36, 0.06) !important;
      border: 1px solid rgba(251, 191, 36, 0.25) !important;
      border-radius: 6px !important;
    }
    /* Iter 103 — Network Latency widget */
    .${P}netlatrow {
      display: grid !important;
      grid-template-columns: repeat(4, 1fr) !important;
      gap: 6px !important;
      align-items: stretch !important;
    }
    .${P}netlatpair {
      display: flex !important;
      flex-direction: column !important;
      align-items: center !important;
      padding: ${mobile ? '3px 4px' : '4px 6px'} !important;
      background: rgba(56, 189, 248, 0.06) !important;
      border: 1px solid rgba(56, 189, 248, 0.25) !important;
      border-radius: 5px !important;
    }
    .${P}netlatk {
      font-size: ${mobile ? 8 : 9}px !important;
      font-weight: 700 !important;
      letter-spacing: 0.4px !important;
      color: #64748b !important;
      text-transform: uppercase !important;
    }
    .${P}netlatv {
      font-size: ${mobile ? 11 : 12}px !important;
      font-weight: 800 !important;
      color: #38bdf8 !important;
      font-variant-numeric: tabular-nums !important;
      margin-top: 1px !important;
    }
    .${P}netlatv.warn { color: #fbbf24 !important; }
    .${P}netlatv.bad  { color: #f87171 !important; }
    .${P}netlatv.good { color: #4ade80 !important; }
    .${P}netlatmeta {
      display: flex !important;
      align-items: center !important;
      margin-top: 4px !important;
      font-size: ${mobile ? 9 : 10}px !important;
      color: #64748b !important;
      font-weight: 600 !important;
    }
    .${P}netlatstate {
      padding: 1px 6px !important;
      border-radius: 3px !important;
      background: rgba(100, 116, 139, 0.15) !important;
      color: #94a3b8 !important;
      text-transform: uppercase !important;
      letter-spacing: 0.4px !important;
    }
    .${P}netlatstate.good  { background: rgba(74, 222, 128, 0.12) !important; color: #4ade80 !important; }
    .${P}netlatstate.warn  { background: rgba(251, 191, 36, 0.14) !important; color: #fbbf24 !important; }
    .${P}netlatstate.bad   { background: rgba(248, 113, 113, 0.14) !important; color: #f87171 !important; }
    .${P}netlatspacer { flex: 1; }
    .${P}netlatstats { color: #64748b !important; font-variant-numeric: tabular-nums !important; }
    /* Iter 104 — SNS Direction Mode segmented buttons */
    .${P}snsdir {
      margin-top: ${mobile ? '6px' : '8px'} !important;
      padding: ${mobile ? '6px 7px' : '7px 8px'} !important;
      background: rgba(139, 92, 246, 0.06) !important;
      border: 1px solid rgba(139, 92, 246, 0.25) !important;
      border-radius: 6px !important;
    }
    .${P}snsdirrow {
      display: grid !important;
      grid-template-columns: 1fr 1fr !important;
      gap: 6px !important;
    }
    .${P}snsdirbtn {
      cursor: pointer !important;
      padding: ${mobile ? '6px 4px' : '7px 6px'} !important;
      font-size: ${mobile ? 10 : 11}px !important;
      font-weight: 700 !important;
      letter-spacing: 0.3px !important;
      border-radius: 5px !important;
      border: 1px solid rgba(148, 163, 184, 0.35) !important;
      background: rgba(30, 41, 59, 0.55) !important;
      color: #94a3b8 !important;
      transition: transform 100ms ease, background-color 150ms ease, color 150ms ease, border-color 150ms ease !important;
    }
    .${P}snsdirbtn:hover { transform: translateY(-1px) !important; background: rgba(51, 65, 85, 0.7) !important; }
    .${P}snsdirbtn.active {
      background: linear-gradient(135deg, rgba(139, 92, 246, 0.35), rgba(56, 189, 248, 0.28)) !important;
      color: #e0e7ff !important;
      border-color: rgba(139, 92, 246, 0.7) !important;
      box-shadow: 0 0 0 1px rgba(139, 92, 246, 0.35) inset !important;
    }
    /* Iter 107 — AI Analysis tab */
    .${P}aigauge {
      padding: ${mobile ? '8px 6px' : '10px 8px'} !important;
      background: rgba(15, 23, 42, 0.55) !important;
      border: 1px solid rgba(148, 163, 184, 0.2) !important;
      border-radius: 8px !important;
    }
    .${P}aigaugebar {
      height: ${mobile ? 10 : 12}px !important;
      background: rgba(148, 163, 184, 0.15) !important;
      border-radius: 6px !important;
      overflow: hidden !important;
      position: relative !important;
    }
    .${P}aigaugefill {
      height: 100% !important;
      background: linear-gradient(90deg, #f87171, #fbbf24 50%, #4ade80) !important;
      transition: width 250ms ease !important;
    }
    .${P}aigaugestats {
      display: flex !important;
      justify-content: space-between !important;
      align-items: baseline !important;
      margin-top: 8px !important;
    }
    .${P}aiconfval {
      font-family: ui-monospace, SFMono-Regular, monospace !important;
      font-size: ${mobile ? 22 : 26}px !important;
      font-weight: 800 !important;
      color: #e2e8f0 !important;
      letter-spacing: -0.02em !important;
    }
    .${P}aiconfdir {
      font-size: ${mobile ? 13 : 14}px !important;
      font-weight: 800 !important;
      letter-spacing: 0.5px !important;
      color: #94a3b8 !important;
    }
    .${P}aiconfdir.CALL { color: #4ade80 !important; }
    .${P}aiconfdir.PUT  { color: #f87171 !important; }
    .${P}aiconfarrow { font-size: ${mobile ? 14 : 16}px !important; color: #94a3b8 !important; }
    .${P}aivotes {
      display: flex !important;
      flex-direction: column !important;
      gap: 5px !important;
    }
    .${P}aivoterow {
      display: grid !important;
      grid-template-columns: 1fr auto auto !important;
      gap: 8px !important;
      align-items: center !important;
      padding: ${mobile ? '6px 7px' : '5px 8px'} !important;
      background: rgba(30, 41, 59, 0.5) !important;
      border-radius: 6px !important;
      border-left: 3px solid transparent !important;
    }
    .${P}aivoterow.CALL { border-left-color: #4ade80 !important; }
    .${P}aivoterow.PUT  { border-left-color: #f87171 !important; }
    .${P}aivotename {
      font-size: ${mobile ? 10 : 11}px !important;
      color: #cbd5e1 !important;
      font-weight: 600 !important;
      overflow: hidden !important;
      text-overflow: ellipsis !important;
      white-space: nowrap !important;
    }
    .${P}aivotedir {
      font-size: ${mobile ? 10 : 11}px !important;
      font-weight: 800 !important;
      letter-spacing: 0.4px !important;
      padding: 2px 6px !important;
      border-radius: 3px !important;
    }
    .${P}aivotedir.CALL { color: #052e16 !important; background: #4ade80 !important; }
    .${P}aivotedir.PUT  { color: #450a0a !important; background: #f87171 !important; }
    .${P}aivoteconf {
      font-family: ui-monospace, monospace !important;
      font-size: ${mobile ? 11 : 12}px !important;
      color: #22d3ee !important;
      font-weight: 700 !important;
    }
    .${P}aivotempty {
      color: #64748b !important;
      font-style: italic !important;
      font-size: ${mobile ? 10 : 11}px !important;
      padding: 8px 4px !important;
      text-align: center !important;
    }
    .${P}aiindgrid {
      display: grid !important;
      grid-template-columns: repeat(2, 1fr) !important;
      gap: 6px !important;
    }
    .${P}aiindpair {
      display: flex !important;
      justify-content: space-between !important;
      align-items: center !important;
      padding: ${mobile ? '5px 7px' : '6px 8px'} !important;
      background: rgba(30, 41, 59, 0.5) !important;
      border: 1px solid rgba(148, 163, 184, 0.15) !important;
      border-radius: 5px !important;
    }
    .${P}aiindk {
      font-size: ${mobile ? 9 : 10}px !important;
      color: #94a3b8 !important;
      font-weight: 700 !important;
      letter-spacing: 0.4px !important;
      text-transform: uppercase !important;
    }
    .${P}aiindv {
      font-family: ui-monospace, monospace !important;
      font-size: ${mobile ? 11 : 12}px !important;
      color: #22d3ee !important;
      font-weight: 700 !important;
    }
    .${P}airecent {
      display: flex !important;
      flex-direction: column !important;
      gap: 4px !important;
    }
    .${P}airecentrow {
      display: grid !important;
      grid-template-columns: auto auto 1fr auto !important;
      gap: 8px !important;
      align-items: center !important;
      padding: ${mobile ? '5px 7px' : '4px 8px'} !important;
      background: rgba(30, 41, 59, 0.5) !important;
      border-radius: 5px !important;
      border-left: 3px solid transparent !important;
      font-size: ${mobile ? 10 : 11}px !important;
    }
    .${P}airecentrow.WIN  { border-left-color: #4ade80 !important; }
    .${P}airecentrow.LOSS { border-left-color: #f87171 !important; }
    .${P}airecentdir { font-weight: 800 !important; color: #cbd5e1 !important; }
    .${P}airecentdir.CALL { color: #4ade80 !important; }
    .${P}airecentdir.PUT  { color: #f87171 !important; }
    .${P}airecentres  { font-weight: 800 !important; padding: 1px 5px !important; border-radius: 3px !important; }
    .${P}airecentres.WIN  { color: #052e16 !important; background: #4ade80 !important; }
    .${P}airecentres.LOSS { color: #450a0a !important; background: #f87171 !important; }
    .${P}airecentsym { color: #cbd5e1 !important; font-family: ui-monospace, monospace !important; overflow: hidden !important; text-overflow: ellipsis !important; white-space: nowrap !important; }
    .${P}airecenttime { color: #64748b !important; font-family: ui-monospace, monospace !important; }
    .${P}latlbl {
      font-size: ${mobile ? 9 : 10}px !important;
      color: #fbbf24 !important;
      font-weight: 700 !important;
      letter-spacing: 0.5px !important;
      text-transform: uppercase !important;
    }
    .${P}latslider {
      width: 100% !important;
      height: 14px !important;
      -webkit-appearance: none !important;
      appearance: none !important;
      background: linear-gradient(90deg, #b91c1c 0%, #fbbf24 50%, #16a34a 100%) !important;
      border-radius: 4px !important;
      outline: none !important;
      cursor: pointer !important;
      margin: 0 !important;
    }
    .${P}latslider::-webkit-slider-thumb {
      -webkit-appearance: none !important;
      appearance: none !important;
      width: 14px !important;
      height: 14px !important;
      background: #fde68a !important;
      border: 2px solid #ffffff !important;
      border-radius: 50% !important;
      cursor: grab !important;
      box-shadow: 0 0 4px rgba(251,191,36,0.8) !important;
    }
    .${P}latslider::-moz-range-thumb {
      width: 14px !important;
      height: 14px !important;
      background: #fde68a !important;
      border: 2px solid #ffffff !important;
      border-radius: 50% !important;
      cursor: grab !important;
      box-shadow: 0 0 4px rgba(251,191,36,0.8) !important;
    }
    .${P}latvalue {
      font-size: ${mobile ? 10 : 11}px !important;
      color: #fde68a !important;
      font-weight: 700 !important;
      min-width: 38px !important;
      text-align: right !important;
      font-variant-numeric: tabular-nums !important;
    }
    .${P}assetrow {
      display: flex !important;
      align-items: center !important;
      gap: 6px !important;
      padding: 4px 8px !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
      background: linear-gradient(90deg, rgba(34,197,94,0.08), rgba(34,197,94,0.02)) !important;
      border: 1px solid rgba(34,197,94,0.25) !important;
      border-left: 3px solid #22c55e !important;
      border-radius: 6px !important;
    }
    .${P}assetlbl {
      font-size: ${mobile ? 9 : 10}px !important;
      color: #86efac !important;
      font-weight: 700 !important;
      letter-spacing: 0.5px !important;
      flex: 0 0 auto !important;
    }
    .${P}assetval {
      flex: 1 !important;
      font-size: ${mobile ? 11 : 12}px !important;
      color: #f0fdf4 !important;
      font-weight: 700 !important;
      font-variant-numeric: tabular-nums !important;
      white-space: nowrap !important;
      overflow: hidden !important;
      text-overflow: ellipsis !important;
    }
    .${P}assetcount {
      font-size: ${mobile ? 9 : 10}px !important;
      color: #4ade80 !important;
      flex: 0 0 auto !important;
      font-variant-numeric: tabular-nums !important;
    }
    /* Status strip — top-of-panel always-visible state summary (Iter 57) */
    .${P}strip {
      display: grid !important;
      grid-template-columns: repeat(${mobile ? 4 : 5}, 1fr) !important;
      gap: 4px !important;
      padding: 6px 8px !important;
      background: rgba(0,0,0,0.4) !important;
      border-bottom: 1px solid #21262d !important;
    }
    .${P}stripcell {
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      gap: 4px !important;
      padding: 3px 4px !important;
      background: rgba(255,255,255,0.02) !important;
      border: 1px solid rgba(255,255,255,0.05) !important;
      border-radius: 4px !important;
      font-size: ${mobile ? 9 : 10}px !important;
      font-weight: 700 !important;
      color: #8b949e !important;
      letter-spacing: 0.5px !important;
      transition: color 0.2s, border-color 0.2s, background 0.2s !important;
    }
    .${P}stripcell.on {
      color: #3fb950 !important;
      border-color: rgba(63,185,80,0.4) !important;
      background: rgba(63,185,80,0.08) !important;
    }
    .${P}stripled {
      width: 6px !important;
      height: 6px !important;
      border-radius: 50% !important;
      background: rgba(255,255,255,0.10) !important;
      flex: 0 0 auto !important;
      transition: background 0.2s, box-shadow 0.2s !important;
    }
    .${P}stripcell.on .${P}stripled {
      background: #3fb950 !important;
      box-shadow: 0 0 3px rgba(63,185,80,0.7) !important;
    }
    /* Live candle-timer readout (v8.51.0) */
    .${P}timerow {
      display: flex !important;
      align-items: center !important;
      gap: 4px !important;
      padding: 4px 8px !important;
      background: rgba(0,0,0,0.35) !important;
      border-bottom: 1px solid #21262d !important;
      font-size: ${mobile ? 9 : 10}px !important;
      font-variant-numeric: tabular-nums !important;
      color: #8b949e !important;
      letter-spacing: 0.3px !important;
    }
    .${P}timelbl {
      color: #6e7681 !important;
      font-weight: 600 !important;
      text-transform: uppercase !important;
    }
    .${P}timeval {
      color: #58a6ff !important;
      font-weight: 700 !important;
      min-width: ${mobile ? 24 : 28}px !important;
      text-align: right !important;
    }
    .${P}timeval.hit {
      color: #3fb950 !important;
      animation: ${P}hitflash 0.6s ease-out 1 !important;
    }
    .${P}timeval.stale { color: #d29922 !important; }
    .${P}timeval.offline { color: #6e7681 !important; }
    .${P}timetrg {
      color: #f0abfc !important;
      font-weight: 700 !important;
    }
    .${P}timetfval {
      color: #79c0ff !important;
      font-weight: 700 !important;
      background: rgba(88,166,255,0.10) !important;
      padding: 1px 4px !important;
      border-radius: 3px !important;
      font-variant-numeric: tabular-nums !important;
    }
    .${P}timesep { color: #30363d !important; }
    .${P}timestatus {
      flex: 1 !important;
      text-align: right !important;
      font-weight: 700 !important;
      font-size: ${mobile ? 9 : 10}px !important;
      color: #6e7681 !important;
      letter-spacing: 0.5px !important;
      text-transform: uppercase !important;
    }
    .${P}timestatus.armed { color: #3fb950 !important; }
    .${P}timestatus.firing { color: #f85149 !important; animation: ${P}hitflash 0.6s ease-out infinite !important; }
    .${P}timestatus.cooldown { color: #8b949e !important; }
    @keyframes ${P}hitflash {
      0%   { text-shadow: 0 0 0 rgba(63,185,80,0); }
      50%  { text-shadow: 0 0 6px rgba(63,185,80,0.8); }
      100% { text-shadow: 0 0 0 rgba(63,185,80,0); }
    }
    /* Compact-mode collapsibles (Iter 57) */
    .${P}advanced { display: block !important; }
    .${P}advanced.hidden { display: none !important; }
    .${P}morebtn {
      width: 100% !important;
      padding: ${mobile ? '5px' : '4px'} !important;
      border: 1px dashed #30363d !important;
      border-radius: 4px !important;
      background: transparent !important;
      color: #8b949e !important;
      font-size: ${mobile ? 10 : 10}px !important;
      font-weight: 600 !important;
      cursor: pointer !important;
      letter-spacing: 0.5px !important;
      transition: all 0.15s !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
      -webkit-tap-highlight-color: transparent !important;
    }
    .${P}morebtn:hover, .${P}morebtn:active {
      border-color: #58a6ff !important;
      color: #e6edf3 !important;
    }
    /* Reset-to-defaults button (Iter 58) */
    .${P}resetbtn {
      width: 100% !important;
      margin-top: ${mobile ? '6px' : '8px'} !important;
      padding: ${mobile ? '5px' : '4px'} !important;
      border: 1px solid rgba(248,81,73,0.3) !important;
      border-radius: 4px !important;
      background: rgba(248,81,73,0.06) !important;
      color: #f85149 !important;
      font-size: ${mobile ? 10 : 10}px !important;
      font-weight: 700 !important;
      cursor: pointer !important;
      letter-spacing: 0.5px !important;
      transition: all 0.15s !important;
      -webkit-tap-highlight-color: transparent !important;
    }
    .${P}resetbtn:hover, .${P}resetbtn:active {
      background: rgba(248,81,73,0.15) !important;
      border-color: #f85149 !important;
    }
    /* Click-to-fire when quality is HIGH (Iter 58) */
    .${P}qualrow.high {
      cursor: pointer !important;
    }
    .${P}qualrow.high:hover {
      filter: brightness(1.15) !important;
    }
    .${P}qualrow.high::after {
      content: '↩ tap to fire GO' !important;
      position: absolute !important;
      right: 6px !important;
      top: 50% !important;
      transform: translateY(-50%) !important;
      font-size: ${mobile ? 8 : 9}px !important;
      color: rgba(34,197,94,0.65) !important;
      font-weight: 600 !important;
      pointer-events: none !important;
    }
    /* Fresh-update pulse (v8.46.0) — 1s flash on every successful poll */
    @keyframes ${P}freshpulse {
      0%   { box-shadow: 0 0 0 0 rgba(88,166,255,0.55); }
      70%  { box-shadow: 0 0 0 6px rgba(88,166,255,0); }
      100% { box-shadow: 0 0 0 0 rgba(88,166,255,0); }
    }
    .${P}qualrow.fresh {
      animation: ${P}freshpulse 1s ease-out 1 !important;
    }
    /* Age pip (v8.46.0) — small dot showing data freshness in seconds */
    .${P}qualage {
      flex: 0 0 auto !important;
      font-size: ${mobile ? 8 : 9}px !important;
      font-variant-numeric: tabular-nums !important;
      color: #6e7681 !important;
      font-weight: 600 !important;
      margin-left: 4px !important;
      letter-spacing: 0.3px !important;
    }
    .${P}qualage.stale { color: #d29922 !important; }
    .${P}qualage.veryold { color: #f85149 !important; }
    /* Sub-row: ML count + strategies evaluated + vote ratio (v8.46.0) */
    .${P}qualsub {
      display: flex !important;
      align-items: center !important;
      gap: 4px !important;
      padding: 0 8px 4px 8px !important;
      margin-top: -4px !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
      background: rgba(0,0,0,0.18) !important;
      border-left: 3px solid #21262d !important;
      border-right: 1px solid #21262d !important;
      border-bottom: 1px solid #21262d !important;
      border-radius: 0 0 6px 6px !important;
      font-size: ${mobile ? 8 : 9}px !important;
      color: #8b949e !important;
      letter-spacing: 0.3px !important;
      min-height: ${mobile ? 14 : 12}px !important;
    }
    .${P}qualsub.high { border-left-color: #22c55e !important; }
    .${P}qualsub.medium { border-left-color: #d29922 !important; }
    .${P}qualsub.low { border-left-color: #f85149 !important; }
    .${P}qualpill {
      padding: 1px 5px !important;
      border-radius: 3px !important;
      background: rgba(255,255,255,0.05) !important;
      font-weight: 700 !important;
      font-variant-numeric: tabular-nums !important;
    }
    .${P}qualpill.ml { color: #58a6ff !important; background: rgba(88,166,255,0.08) !important; }
    .${P}qualpill.strats { color: #a5d6ff !important; }
    .${P}qualpill.votes { color: #c9b6ff !important; }
    /* Iter 56b — abstain source chip (which threshold tier fired) */
    .${P}qualpill.abstainsrc { background: rgba(255,255,255,0.04) !important; border: 1px solid rgba(255,255,255,0.12) !important; }
    .${P}qualpill.abstainsrc.src-strategy { color: #6effa6 !important; border-color: rgba(110,255,166,0.4) !important; background: rgba(110,255,166,0.08) !important; }
    .${P}qualpill.abstainsrc.src-asset    { color: #6bb5ff !important; border-color: rgba(107,181,255,0.4) !important; background: rgba(107,181,255,0.08) !important; }
    .${P}qualpill.abstainsrc.src-default  { color: #b8b8b8 !important; }
    .${P}qualpill.abstainsrc.src-latency  { color: #ff8a6e !important; border-color: rgba(255,138,110,0.5) !important; background: rgba(255,138,110,0.10) !important; }
    /* Iter 56b — server latency chip (% of timeframe budget consumed) */
    .${P}qualpill.srvlat { font-variant-numeric: tabular-nums !important; }
    .${P}qualpill.srvlat.lat-good { color: #6effa6 !important; background: rgba(110,255,166,0.08) !important; }
    .${P}qualpill.srvlat.lat-warn { color: #ffcc66 !important; background: rgba(255,204,102,0.10) !important; }
    .${P}qualpill.srvlat.lat-bad  { color: #ff8a6e !important; background: rgba(255,138,110,0.14) !important; }
    .${P}qualspacer { flex: 1 !important; }
    .${P}quallat { color: #6e7681 !important; }
    .${P}qualrow { position: relative !important; }
    .${P}qualrow {
      display: flex !important;
      align-items: center !important;
      gap: 6px !important;
      padding: 3px 8px !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-left: 3px solid #484f58 !important;
      border-radius: 6px !important;
      transition: border-color 0.3s, background 0.3s !important;
    }
    .${P}qualrow.high {
      border-left-color: #22c55e !important;
      background: linear-gradient(90deg, rgba(34,197,94,0.10), rgba(34,197,94,0.02)) !important;
    }
    .${P}qualrow.medium {
      border-left-color: #d29922 !important;
      background: linear-gradient(90deg, rgba(210,153,34,0.10), rgba(210,153,34,0.02)) !important;
    }
    .${P}qualrow.low {
      border-left-color: #f85149 !important;
      background: linear-gradient(90deg, rgba(248,81,73,0.08), rgba(248,81,73,0.02)) !important;
    }
    .${P}quallbl {
      font-size: ${mobile ? 9 : 10}px !important;
      color: #8b949e !important;
      font-weight: 700 !important;
      letter-spacing: 0.5px !important;
      flex: 0 0 auto !important;
      text-transform: uppercase !important;
    }
    .${P}qualbar {
      flex: 0 0 60px !important;
      height: 6px !important;
      background: rgba(255,255,255,0.06) !important;
      border-radius: 3px !important;
      overflow: hidden !important;
      position: relative !important;
    }
    .${P}qualfill {
      display: block !important;
      height: 100% !important;
      width: 0% !important;
      background: #484f58 !important;
      transition: width 0.4s, background 0.3s !important;
    }
    .${P}qualrow.high .${P}qualfill { background: #22c55e !important; }
    .${P}qualrow.medium .${P}qualfill { background: #d29922 !important; }
    .${P}qualrow.low .${P}qualfill { background: #f85149 !important; }
    .${P}qualval {
      flex: 1 !important;
      font-size: ${mobile ? 10 : 11}px !important;
      color: #e6edf3 !important;
      font-weight: 700 !important;
      font-variant-numeric: tabular-nums !important;
      white-space: nowrap !important;
      overflow: hidden !important;
      text-overflow: ellipsis !important;
    }
    .${P}stratlbl {
      font-size: ${mobile ? 9 : 10}px !important;
      color: #8b949e !important;
      white-space: nowrap !important;
    }
    .${P}stratsel {
      flex: 1 !important;
      padding: ${mobile ? '5px 4px' : '3px 4px'} !important;
      border: 1px solid #30363d !important;
      border-radius: 4px !important;
      background: #0d1117 !important;
      color: #e6edf3 !important;
      font-size: ${mobile ? 11 : 10}px !important;
      -webkit-appearance: none !important;
      appearance: none !important;
      cursor: pointer !important;
      min-height: ${mobile ? 30 : 24}px !important;
    }
    .${P}stratsel option {
      background: #0d1117 !important;
      color: #e6edf3 !important;
    }
    .${P}loghdr {
      padding: 5px 8px !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-radius: 6px 6px 0 0 !important;
      cursor: pointer !important;
      font-size: ${mobile ? 10 : 11}px !important;
      color: #8b949e !important;
    }
    .${P}logbox {
      max-height: ${mobile ? 80 : 120}px !important;
      overflow-y: auto !important;
      background: rgba(0,0,0,0.4) !important;
      border: 1px solid #21262d !important;
      border-top: none !important;
      border-radius: 0 0 6px 6px !important;
      font-family: 'Consolas', 'Courier New', monospace !important;
      font-size: ${mobile ? 9 : 10}px !important;
      padding: 4px !important;
      color: #8b949e !important;
      -webkit-overflow-scrolling: touch !important;
    }
    .${P}logbox::-webkit-scrollbar { width: 4px !important; }
    .${P}logbox::-webkit-scrollbar-thumb { background: #30363d !important; border-radius: 2px !important; }

    /* ═══════════════════════════════════════════════════════════════════
     * Iter 96 — MODERN TABBED REDESIGN
     * Deep charcoal · Cyan primary · Emerald success · Rose danger
     * Auto-adapts: compact FAB on mobile · spacious dashboard on desktop
     * All existing IDs are retained — event wiring stays intact.
     * ═══════════════════════════════════════════════════════════════════ */

    /* Panel chrome override — glassmorphic dark with cyan accent glow */
    #${P}host {
      width: ${mobile ? '260' : '360'}px !important;
      max-width: 94vw !important;
      transition: width 0.28s cubic-bezier(0.16, 1, 0.3, 1),
                  height 0.28s cubic-bezier(0.16, 1, 0.3, 1),
                  top 0.28s ease, right 0.28s ease, left 0.28s ease !important;
    }
    /* Fullscreen expand mode (mobile) — added via .expanded class on host */
    #${P}host.expanded {
      width: 100vw !important;
      height: 100vh !important;
      top: 0 !important;
      right: 0 !important;
      left: 0 !important;
      max-width: 100vw !important;
      border-radius: 0 !important;
    }
    #${P}host.expanded #${P}panel {
      width: 100% !important;
      height: 100% !important;
      max-height: 100vh !important;
      border-radius: 0 !important;
      display: flex !important;
      flex-direction: column !important;
    }
    #${P}host.expanded .${P}body {
      flex: 1 !important;
      overflow-y: auto !important;
      max-height: none !important;
    }
    #${P}panel {
      background: linear-gradient(180deg, rgba(10,14,20,0.98) 0%, rgba(8,11,17,0.98) 100%) !important;
      border: 1px solid rgba(34,211,238,0.18) !important;
      border-radius: 14px !important;
      box-shadow: 0 8px 32px rgba(0,0,0,0.6),
                  0 0 0 1px rgba(255,255,255,0.02),
                  inset 0 1px 0 rgba(255,255,255,0.04) !important;
      backdrop-filter: blur(20px) saturate(140%) !important;
      -webkit-backdrop-filter: blur(20px) saturate(140%) !important;
      overflow: hidden !important;
    }
    /* Header — refined gradient with subtle accent line */
    .${P}header {
      background: linear-gradient(90deg,
        rgba(34,211,238,0.10) 0%,
        rgba(52,211,153,0.06) 50%,
        rgba(34,211,238,0.10) 100%) !important;
      border-bottom: 1px solid rgba(34,211,238,0.20) !important;
      padding: 10px 12px !important;
      cursor: grab !important;
      display: flex !important;
      align-items: center !important;
      justify-content: space-between !important;
      gap: 8px !important;
    }
    .${P}header::after {
      content: '' !important;
      position: absolute !important;
      left: 12px !important; right: 12px !important; bottom: 0 !important;
      height: 1px !important;
      background: linear-gradient(90deg, transparent, rgba(34,211,238,0.4), transparent) !important;
    }
    .${P}title {
      font-size: ${mobile ? '13' : '14'}px !important;
      font-weight: 700 !important;
      letter-spacing: 0.3px !important;
      color: #e6edf3 !important;
      display: inline-flex !important;
      align-items: center !important;
      gap: 6px !important;
    }
    .${P}title::before {
      content: '' !important;
      width: 6px !important; height: 6px !important;
      border-radius: 50% !important;
      background: radial-gradient(circle, #22d3ee, #0891b2) !important;
      box-shadow: 0 0 8px rgba(34,211,238,0.7) !important;
    }
    .${P}hright { display: flex !important; align-items: center !important; gap: 6px !important; }
    .${P}dot {
      width: 8px !important; height: 8px !important;
      border-radius: 50% !important;
      background: #10b981 !important;
      box-shadow: 0 0 8px rgba(16,185,129,0.6) !important;
      transition: all 0.3s !important;
    }
    .${P}dot.off { background: #6b7280 !important; box-shadow: none !important; }
    /* Header buttons (minimize, expand, close) — larger tap targets */
    .${P}minbtn, .${P}expandbtn {
      background: rgba(255,255,255,0.05) !important;
      border: 1px solid rgba(255,255,255,0.10) !important;
      color: #cbd5e1 !important;
      width: 26px !important; height: 26px !important;
      border-radius: 6px !important;
      font-size: 14px !important;
      font-weight: 700 !important;
      line-height: 1 !important;
      cursor: pointer !important;
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      transition: all 0.15s !important;
      padding: 0 !important;
    }
    .${P}minbtn:hover, .${P}expandbtn:hover {
      background: rgba(34,211,238,0.15) !important;
      border-color: rgba(34,211,238,0.4) !important;
      color: #22d3ee !important;
    }

    /* Tab bar — sticky, glass, active-bar underline */
    .${P}tabbar {
      display: grid !important;
      grid-template-columns: repeat(4, 1fr) !important;
      gap: 0 !important;
      background: rgba(0,0,0,0.30) !important;
      border-bottom: 1px solid rgba(255,255,255,0.05) !important;
      padding: 0 !important;
      position: relative !important;
    }
    .${P}tabbtn {
      background: transparent !important;
      border: none !important;
      color: #64748b !important;
      font-size: ${mobile ? '10' : '11'}px !important;
      font-weight: 700 !important;
      letter-spacing: 0.4px !important;
      text-transform: uppercase !important;
      padding: ${mobile ? '10px 4px' : '9px 6px'} !important;
      cursor: pointer !important;
      position: relative !important;
      transition: color 0.2s !important;
      display: flex !important;
      flex-direction: column !important;
      align-items: center !important;
      gap: 2px !important;
      font-family: inherit !important;
    }
    .${P}tabbtn:hover { color: #cbd5e1 !important; }
    .${P}tabbtn.active { color: #22d3ee !important; }
    .${P}tabbtn.active::after {
      content: '' !important;
      position: absolute !important;
      bottom: 0 !important; left: 15% !important; right: 15% !important;
      height: 2px !important;
      background: linear-gradient(90deg, transparent, #22d3ee, transparent) !important;
      box-shadow: 0 0 6px rgba(34,211,238,0.7) !important;
      border-radius: 2px !important;
    }
    .${P}tabicon { font-size: ${mobile ? '13' : '14'}px !important; line-height: 1 !important; }

    /* Tab panels */
    .${P}tabpanel {
      display: none !important;
      padding: 10px 10px !important;
      animation: ${P}tabin 0.22s ease-out !important;
    }
    .${P}tabpanel.active { display: block !important; }
    @keyframes ${P}tabin {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Section groups — visual grouping inside tabs */
    .${P}section {
      background: rgba(255,255,255,0.02) !important;
      border: 1px solid rgba(255,255,255,0.05) !important;
      border-radius: 10px !important;
      padding: 8px !important;
      margin-bottom: 8px !important;
    }
    .${P}section:last-child { margin-bottom: 0 !important; }
    .${P}sectionttl {
      font-size: ${mobile ? '9' : '10'}px !important;
      font-weight: 700 !important;
      color: #64748b !important;
      letter-spacing: 0.6px !important;
      text-transform: uppercase !important;
      margin-bottom: 6px !important;
      padding-left: 2px !important;
      display: flex !important;
      align-items: center !important;
      gap: 4px !important;
    }
    .${P}sectionttl::before {
      content: '' !important;
      width: 3px !important; height: 10px !important;
      background: linear-gradient(180deg, #22d3ee, #0891b2) !important;
      border-radius: 2px !important;
    }

    /* Upgrade all .btn class buttons: modern pill, tap-friendly */
    .${P}btn {
      background: rgba(255,255,255,0.04) !important;
      border: 1px solid rgba(255,255,255,0.08) !important;
      color: #cbd5e1 !important;
      font-weight: 700 !important;
      border-radius: 8px !important;
      padding: ${mobile ? '11px 6px' : '9px 6px'} !important;
      font-size: ${mobile ? '11' : '11'}px !important;
      letter-spacing: 0.4px !important;
      cursor: pointer !important;
      transition: all 0.15s ease !important;
      position: relative !important;
      overflow: hidden !important;
    }
    .${P}btn:hover {
      background: rgba(34,211,238,0.10) !important;
      border-color: rgba(34,211,238,0.30) !important;
      color: #e6edf3 !important;
      transform: translateY(-1px) !important;
    }
    .${P}btn:active { transform: translateY(0) !important; }
    .${P}btn.active {
      background: linear-gradient(135deg, rgba(34,211,238,0.20), rgba(16,185,129,0.15)) !important;
      border-color: rgba(34,211,238,0.5) !important;
      color: #22d3ee !important;
      box-shadow: 0 0 12px rgba(34,211,238,0.25), inset 0 1px 0 rgba(255,255,255,0.08) !important;
    }
    .${P}btn-go {
      background: linear-gradient(135deg, #22d3ee 0%, #0891b2 100%) !important;
      border-color: #22d3ee !important;
      color: #082f38 !important;
      font-weight: 800 !important;
      box-shadow: 0 4px 12px rgba(34,211,238,0.35) !important;
    }
    .${P}btn-go:hover {
      background: linear-gradient(135deg, #67e8f9 0%, #22d3ee 100%) !important;
      color: #041f26 !important;
      box-shadow: 0 6px 18px rgba(34,211,238,0.5) !important;
    }
    .${P}btn-win.active { background: linear-gradient(135deg, rgba(16,185,129,0.25), rgba(52,211,153,0.15)) !important; border-color: rgba(16,185,129,0.5) !important; color: #34d399 !important; }
    .${P}btn-loss.active, .${P}btn-inv.active { background: linear-gradient(135deg, rgba(244,63,94,0.25), rgba(251,113,133,0.15)) !important; border-color: rgba(244,63,94,0.5) !important; color: #fb7185 !important; }

    /* Stats — big numeric tiles */
    .${P}stats {
      display: grid !important;
      grid-template-columns: repeat(4, 1fr) !important;
      gap: 6px !important;
      position: relative !important;
    }
    .${P}stat {
      background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01)) !important;
      border: 1px solid rgba(255,255,255,0.06) !important;
      border-radius: 8px !important;
      padding: 8px 4px !important;
      text-align: center !important;
      display: flex !important;
      flex-direction: column !important;
      align-items: center !important;
      gap: 3px !important;
    }
    .${P}stlbl {
      font-size: ${mobile ? '9' : '9'}px !important;
      color: #64748b !important;
      font-weight: 700 !important;
      letter-spacing: 0.5px !important;
      text-transform: uppercase !important;
    }
    .${P}stval {
      font-size: ${mobile ? '14' : '15'}px !important;
      font-weight: 800 !important;
      color: #e6edf3 !important;
      font-variant-numeric: tabular-nums !important;
      line-height: 1 !important;
    }

    /* Inputs / selects — cleaner treatment */
    .${P}stratsel, .${P}mminp, .${P}thrInp, .${P}latslider, .${P}timing-slider {
      background: rgba(0,0,0,0.35) !important;
      border: 1px solid rgba(255,255,255,0.10) !important;
      color: #e6edf3 !important;
      border-radius: 6px !important;
      padding: 6px 8px !important;
      font-size: ${mobile ? '11' : '12'}px !important;
      font-family: inherit !important;
    }
    .${P}stratsel:focus, .${P}mminp:focus, .${P}thrInp:focus {
      outline: none !important;
      border-color: rgba(34,211,238,0.5) !important;
      box-shadow: 0 0 0 3px rgba(34,211,238,0.15) !important;
    }

    /* Live-tab strip: bigger LEDs, nicer chips */
    .${P}strip {
      display: grid !important;
      grid-template-columns: repeat(5, 1fr) !important;
      gap: 4px !important;
      padding: 6px !important;
      background: rgba(0,0,0,0.30) !important;
      border-radius: 8px !important;
      margin-bottom: 8px !important;
      border: 1px solid rgba(255,255,255,0.04) !important;
    }
    .${P}stripcell {
      display: flex !important;
      flex-direction: column !important;
      align-items: center !important;
      gap: 3px !important;
      padding: 3px 2px !important;
      font-size: ${mobile ? '9' : '10'}px !important;
      color: #64748b !important;
      font-weight: 700 !important;
      letter-spacing: 0.4px !important;
    }
    .${P}stripcell.active { color: #22d3ee !important; }
    .${P}stripled {
      width: 8px !important; height: 8px !important;
      border-radius: 50% !important;
      background: #374151 !important;
      transition: all 0.25s !important;
    }
    .${P}stripcell.active .${P}stripled {
      background: #22d3ee !important;
      box-shadow: 0 0 8px rgba(34,211,238,0.7) !important;
    }

    /* Time row — LIVE countdown big and prominent */
    .${P}timerow {
      background: linear-gradient(90deg, rgba(34,211,238,0.06), transparent) !important;
      border: 1px solid rgba(34,211,238,0.15) !important;
      border-radius: 8px !important;
      padding: 8px 10px !important;
      margin-bottom: 8px !important;
      display: flex !important;
      align-items: center !important;
      justify-content: space-between !important;
      gap: 8px !important;
    }
    #${P}timeval {
      font-size: ${mobile ? '18' : '20'}px !important;
      font-weight: 800 !important;
      color: #22d3ee !important;
      font-variant-numeric: tabular-nums !important;
      letter-spacing: 0.5px !important;
    }

    /* Log box — cleaner console look */
    .${P}logbox {
      background: rgba(0,0,0,0.5) !important;
      border: 1px solid rgba(255,255,255,0.05) !important;
      border-radius: 8px !important;
      padding: 8px !important;
      font-family: 'SF Mono', 'Menlo', 'Consolas', monospace !important;
      font-size: 10px !important;
      color: #94a3b8 !important;
      line-height: 1.5 !important;
    }
    .${P}resetbtn {
      background: rgba(244,63,94,0.08) !important;
      border: 1px solid rgba(244,63,94,0.25) !important;
      color: #fb7185 !important;
      border-radius: 8px !important;
      padding: 10px !important;
      font-weight: 700 !important;
      letter-spacing: 0.5px !important;
      cursor: pointer !important;
      transition: all 0.15s !important;
      width: 100% !important;
      margin-top: 8px !important;
    }
    .${P}resetbtn:hover {
      background: rgba(244,63,94,0.18) !important;
      border-color: rgba(244,63,94,0.5) !important;
    }

    /* Hide the legacy MORE toggle since we now have tabs */
    .${P}morebtn { display: none !important; }
    /* The legacy .advanced div is now inside the Config tab — show contents always */
    .${P}advanced.hidden { display: block !important; }

    /* Mobile: even bigger tap targets in expanded mode */
    #${P}host.expanded .${P}btn { padding: 14px 10px !important; font-size: 13px !important; }
    #${P}host.expanded .${P}tabbtn { padding: 14px 6px !important; font-size: 12px !important; }
  `;

  if (typeof GM_addStyle === 'function') {
    try { GM_addStyle(css); } catch (e) { _fallbackCSS(css); }
  } else {
    _fallbackCSS(css);
  }
}

function _fallbackCSS(css) {
  const existing = document.getElementById(`${P}style`);
  if (existing) existing.remove();
  const el = document.createElement('style');
  el.setAttribute('type', 'text/css');
  el.setAttribute('id', `${P}style`);
  el.textContent = css;
  (document.head || document.documentElement).appendChild(el);
}

/**
 * Create panel
 */
export function createPanel() {
  console.log('[Elite Bot] Creating panel (mobile=' + isMobile() + ')...');
  injectCSS();
  console.log('[Elite Bot] CSS injected');

  const mobile = isMobile();

  panelEl = document.createElement('div');
  panelEl.id = `${P}host`;

  const titleShort = isMobile() ? 'AI Elite Bot' : CONFIG.BOT_NAME;

  panelEl.innerHTML = `
    <div id="${P}panel">
      <!-- Header -->
      <div class="${P}header" id="${P}header" data-testid="tm-panel-header">
        <span class="${P}title">${titleShort}</span>
        <div class="${P}hright">
          <!-- Iter 110 — Master Auto-Trade toggle: ONE tap enables/disables
               SCAN + AUTO + APP + CYCLE together. Big pill for quick access. -->
          <button class="${P}masterbtn" id="${P}master" data-testid="tm-master-toggle" title="Master switch — turns SCAN, AUTO, APP and CYCLE all ON or all OFF at once.">
            <span class="${P}masterled"></span><span id="${P}masterlbl">OFF</span>
          </button>
          <span class="${P}dot" id="${P}dot" title="Bot connection status"></span>
          <button class="${P}expandbtn" id="${P}expandbtn" data-testid="tm-panel-expand" title="Expand to fullscreen / restore compact view">⛶</button>
          <button class="${P}minbtn" id="${P}minbtn" data-testid="tm-panel-minimize" title="Minimize panel">_</button>
        </div>
      </div>

      <!-- Tab bar (Iter 96) -->
      <div class="${P}tabbar" data-testid="tm-tabbar">
        <button class="${P}tabbtn active" data-tab="live" data-testid="tab-live"><span class="${P}tabicon">◉</span>Live</button>
        <button class="${P}tabbtn" data-tab="trade" data-testid="tab-trade"><span class="${P}tabicon">▲</span>Trade</button>
        <button class="${P}tabbtn" data-tab="ai" data-testid="tab-ai" title="AI Technical Analysis — model votes, indicators, Kyle λ, mini-chart, recent trades"><span class="${P}tabicon">✧</span>AI</button>
        <button class="${P}tabbtn" data-tab="config" data-testid="tab-config"><span class="${P}tabicon">⚙</span>Config</button>
        <button class="${P}tabbtn" data-tab="stats" data-testid="tab-stats"><span class="${P}tabicon">▨</span>Stats</button>
        <button class="${P}tabbtn" data-tab="forex" data-testid="tab-forex" title="Forex MT5 automation — poller + point-to-teach DOM selectors"><span class="${P}tabicon">₣</span>Forex</button>
      </div>

      <div class="${P}body" id="${P}body">
        <!-- ═════════════════ TAB: LIVE ═════════════════ -->
        <div class="${P}tabpanel active" data-tab-panel="live" data-testid="tab-panel-live">
          <div class="${P}strip" id="${P}strip" data-testid="status-strip" title="Live state of all toggles. Green dot = ON, grey = OFF.">
            <div class="${P}stripcell" id="${P}stripscan"><span class="${P}stripled"></span><span>SCAN</span></div>
            <div class="${P}stripcell" id="${P}stripauto"><span class="${P}stripled"></span><span>AUTO</span></div>
            <div class="${P}stripcell" id="${P}stripainv"><span class="${P}stripled"></span><span>A-INV</span></div>
            <div class="${P}stripcell" id="${P}strip51s" title="Seconds Number Strategy toggle — fires at a fixed second of every 1m candle"><span class="${P}stripled"></span><span>SNS</span></div>
            <div class="${P}stripcell" id="${P}stripcycle"><span class="${P}stripled"></span><span>CYCLE</span></div>
          </div>
          <div id="${P}detectHealth" data-testid="detect-health" title="Trade outcome detection health. Turns red when trades time out without a WIN/LOSS being recorded — click to open the teach flow." style="display:none;margin:4px 0;padding:6px 10px;background:#450a0a;border:1px solid #7f1d1d;border-radius:4px;color:#fca5a5;font-size:10px;line-height:1.4;cursor:pointer;">
            <b>⚠️ Win/Loss detection unhealthy</b> — <span id="${P}detectHealthMsg">click to teach the WIN/LOSS row markers</span>
          </div>
          <div class="${P}timerow" id="${P}timerow" data-testid="live-candle-timer" title="Live PO candle countdown and Seconds Number Strategy trigger status. Works on any chart timeframe.">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-size:${mobile ? 9 : 10}px;color:#64748b;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">LIVE</span>
              <span id="${P}timeval">--:--</span>
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px;">
              <span id="${P}timetfval" style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;font-weight:600;">--</span>
              <span id="${P}timestatus" style="font-size:${mobile ? 9 : 10}px;color:#64748b;">idle</span>
              <span id="${P}timetrg" style="display:none;"></span>
            </div>
          </div>
          <div class="${P}qualrow" id="${P}qualrow" data-testid="signal-quality-preview" title="Live signal preview from backend (refreshes every 3s). Tells you whether it's worth pulling GO right now.">
            <span class="${P}quallbl">Signal</span>
            <span class="${P}qualval" id="${P}qualval">—</span>
            <span class="${P}qualage" id="${P}qualage"></span>
            <span class="${P}qualspacer"></span>
            <span class="${P}quallat" id="${P}quallat"></span>
            <div class="${P}qualbar"><div class="${P}qualfill" id="${P}qualfill"></div></div>
          </div>
          <div class="${P}qualsub" id="${P}qualsub" data-testid="signal-quality-sub" title="Strategy & ML model participation in the current force-generated signal">
            <span class="${P}qualpill ml" id="${P}qualml">ML —</span>
            <span class="${P}qualpill strats" id="${P}qualstrats">— strats</span>
            <span class="${P}qualpill votes" id="${P}qualvotes">— votes</span>
            <span class="${P}qualspacer"></span>
            <span class="${P}qualpill abstainsrc" id="${P}qualabstainsrc" style="display:none;"></span>
            <span class="${P}qualpill srvlat" id="${P}qualsrvlat" style="display:none;"></span>
          </div>
          <div class="${P}section">
            <div class="${P}sectionttl">Active Asset</div>
            <div class="${P}assetrow" data-testid="active-asset-indicator" title="Active asset and rotation count. Updates on every CYCLE switch / SNS fire.">
              <span id="${P}asset">—</span>
              <span class="${P}assetsp"></span>
              <span id="${P}assetcnt" class="${P}assetcnt">0</span>
            </div>
          </div>
          <!-- Iter 103 — Network Latency widget -->
          <div class="${P}section" data-testid="network-latency-widget" title="Backend-measured TCP round-trip to Pocket Option hosts. Rolling percentiles refresh every 5s.">
            <div class="${P}sectionttl">Network Latency <span id="${P}netlatlbl" style="color:#64748b;font-weight:500;font-size:9px;margin-left:4px;">(pocketoption.com)</span></div>
            <div class="${P}netlatrow" data-testid="netlat-current">
              <span class="${P}netlatpair"><span class="${P}netlatk">now</span><span id="${P}netlatnow" class="${P}netlatv">—</span></span>
              <span class="${P}netlatpair"><span class="${P}netlatk">p50</span><span id="${P}netlatp50" class="${P}netlatv">—</span></span>
              <span class="${P}netlatpair"><span class="${P}netlatk">p99</span><span id="${P}netlatp99" class="${P}netlatv">—</span></span>
              <span class="${P}netlatpair"><span class="${P}netlatk">p99.9</span><span id="${P}netlatp999" class="${P}netlatv">—</span></span>
            </div>
            <div class="${P}netlatmeta" data-testid="netlat-meta">
              <span id="${P}netlatstate" class="${P}netlatstate">—</span>
              <span class="${P}netlatspacer"></span>
              <span id="${P}netlatstats" class="${P}netlatstats">— samples</span>
            </div>
          </div>
        </div>

        <!-- ═════════════════ TAB: TRADE ═════════════════ -->
        <div class="${P}tabpanel" data-tab-panel="trade" data-testid="tab-panel-trade">
          <!-- Iter 110 — Master Auto-Trade toggle: single tap flips SCAN + AUTO + APP + CYCLE together. -->
          <div class="${P}section" data-testid="master-toggle-section" title="Turn EVERYTHING on: SCAN, AUTO, APP, and CYCLE. Tap again to instantly halt every auto-trading module.">
            <div class="${P}sectionttl">Master Auto-Trade</div>
            <button id="${P}masterBig" class="${P}masterbig" data-testid="tm-master-toggle-big">
              <span class="${P}masterled"></span>
              <span id="${P}masterBigLbl">TAP TO GO LIVE</span>
            </button>
            <div id="${P}masterBigSub" style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;text-align:center;margin-top:6px;line-height:1.4;">
              SCAN · AUTO · APP · CYCLE — all off. Tap the button to enable them all.
            </div>
          </div>
          <div class="${P}section">
            <div class="${P}sectionttl">Primary Controls</div>
            <div class="${P}row">
              <button id="${P}scan" class="${P}btn" data-testid="btn-scan" title="Scan markets for best asset">SCAN</button>
              <button id="${P}auto" class="${P}btn" data-testid="btn-auto" title="Enable/disable automatic trade execution">AUTO</button>
              <button id="${P}go" class="${P}btn ${P}btn-go" data-testid="btn-go" title="Force-generate a signal now (with full technical analysis)">GO</button>
            </div>
            <div class="${P}row" style="margin-top:6px;">
              <button id="${P}r21s" data-testid="seconds-number-strategy-toggle" class="${P}btn ${P}btn-r21s" title="Seconds Number Strategy — fires an opposite 5s trade at a chosen second of every 1m candle.">SNS</button>
              <button id="${P}ainv" class="${P}btn ${P}btn-ainv" title="Auto-invert on 2 consecutive losses">A-INV</button>
              <button id="${P}inv" class="${P}btn ${P}btn-inv" data-testid="btn-invert" title="Flip CALL↔PUT globally">INVERT</button>
            </div>
            <div class="${P}row" style="margin-top:6px;">
              <button id="${P}cycle" class="${P}btn ${P}btn-cycle" data-testid="btn-cycle" title="Rotate through favorites, scan each, auto-trade best">CYCLE</button>
              <button id="${P}app" class="${P}btn ${P}btn-app" data-testid="btn-app" title="Poll backend /signals/latest and auto-execute">APP</button>
            </div>
          </div>

          <div class="${P}section">
            <div class="${P}sectionttl">Money Management</div>
            <div class="${P}mmrow" title="Bot's internal MM tracker — for stats only. Set actual trade amount manually in Pocket Option's UI.">
              <span class="${P}mmlbl">MM $</span>
              <input type="number" id="${P}amt" class="${P}mminp" value="1" min="1" max="1000" data-testid="mm-amount-input" style="flex:1;">
              <span class="${P}mmlbl">Step:</span>
              <span id="${P}step" style="font-weight:700;color:#e6edf3;">0</span>
            </div>
            <div class="${P}row" style="margin-top:8px;">
              <button id="${P}win" class="${P}btn ${P}btn-win" data-testid="btn-win-manual" title="Manually record a WIN">WIN</button>
              <button id="${P}loss" class="${P}btn ${P}btn-loss" data-testid="btn-loss-manual" title="Manually record a LOSS">LOSS</button>
            </div>
            <div class="${P}invst" id="${P}invst" style="padding:6px 8px !important;margin-top:6px;background:rgba(0,0,0,0.25);border-radius:6px;">Invert: Normal</div>
            <div class="${P}invst" id="${P}r21st" style="padding:6px 8px !important;margin-top:6px;background:rgba(0,0,0,0.25);border-radius:6px;">SNS: Off</div>
          </div>
        </div>

        <!-- ═════════════════ TAB: AI (Iter 107) ═════════════════ -->
        <div class="${P}tabpanel" data-tab-panel="ai" data-testid="tab-panel-ai">
          <!-- Confidence gauge -->
          <div class="${P}section" data-testid="ai-confidence-card">
            <div class="${P}sectionttl">Signal Confidence</div>
            <div class="${P}aigauge">
              <div class="${P}aigaugebar">
                <div id="${P}aiConfFill" class="${P}aigaugefill" style="width:0%;"></div>
              </div>
              <div class="${P}aigaugestats">
                <span id="${P}aiConfVal" class="${P}aiconfval">— %</span>
                <span id="${P}aiConfDir" class="${P}aiconfdir">—</span>
                <span id="${P}aiConfArrow" class="${P}aiconfarrow"></span>
              </div>
            </div>
          </div>

          <!-- Top model votes -->
          <div class="${P}section" data-testid="ai-votes-card">
            <div class="${P}sectionttl">Top Model Votes</div>
            <div id="${P}aiVotes" class="${P}aivotes">
              <div class="${P}aivotempty">no signal yet — waiting…</div>
            </div>
          </div>

          <!-- Indicators readout -->
          <div class="${P}section" data-testid="ai-indicators-card">
            <div class="${P}sectionttl">Indicators</div>
            <div class="${P}aiindgrid">
              <div class="${P}aiindpair"><span class="${P}aiindk">RSI</span><span id="${P}aiIndRSI" class="${P}aiindv">—</span></div>
              <div class="${P}aiindpair"><span class="${P}aiindk">MACD H</span><span id="${P}aiIndMACD" class="${P}aiindv">—</span></div>
              <div class="${P}aiindpair"><span class="${P}aiindk">BB pos</span><span id="${P}aiIndBB" class="${P}aiindv">—</span></div>
              <div class="${P}aiindpair"><span class="${P}aiindk">ATR %</span><span id="${P}aiIndATR" class="${P}aiindv">—</span></div>
            </div>
          </div>

          <!-- Microstructure -->
          <div class="${P}section" data-testid="ai-microstructure-card">
            <div class="${P}sectionttl">Microstructure <span style="color:#64748b;font-weight:500;font-size:9px;margin-left:4px;">(Kyle · Glosten-Milgrom)</span></div>
            <div class="${P}aiindgrid">
              <div class="${P}aiindpair"><span class="${P}aiindk">Kyle λ</span><span id="${P}aiKyleLambda" class="${P}aiindv">—</span></div>
              <div class="${P}aiindpair"><span class="${P}aiindk">Adv Sel</span><span id="${P}aiGMAdv" class="${P}aiindv">—</span></div>
              <div class="${P}aiindpair"><span class="${P}aiindk">Informed</span><span id="${P}aiGMInf" class="${P}aiindv">—</span></div>
              <div class="${P}aiindpair"><span class="${P}aiindk">Illiq bps</span><span id="${P}aiKyleBps" class="${P}aiindv">—</span></div>
            </div>
          </div>

          <!-- Recent trades log -->
          <div class="${P}section" data-testid="ai-trades-card">
            <div class="${P}sectionttl">Recent Trades <span style="color:#64748b;font-weight:500;font-size:9px;margin-left:4px;">(last 5)</span></div>
            <div id="${P}aiRecentTrades" class="${P}airecent">
              <div class="${P}aivotempty">no trades yet</div>
            </div>
          </div>
        </div>

        <!-- ═════════════════ TAB: CONFIG ═════════════════ -->
        <div class="${P}tabpanel" data-tab-panel="config" data-testid="tab-panel-config">
          <div class="${P}advanced" id="${P}advanced">

            <!-- Iter 138 — Stealth Mode toggle -->
            <div class="${P}section" data-testid="stealth-mode-section" title="Reduces the bot's observable footprint on PocketOption's tab: 3× longer poll intervals for heartbeat/latency/settings, and background probes pause entirely while auto-trade is OFF. Turn ON if PO's WAF has been rate-limiting or 403'ing your session.">
              <div class="${P}sectionttl">🥷 Stealth Mode</div>
              <div style="display:flex;gap:8px;align-items:center;justify-content:space-between;">
                <div style="font-size:${mobile ? 10 : 11}px;color:#cbd5e1;flex:1;line-height:1.4;">
                  Slow background traffic to look less bot-like on PO.
                </div>
                <button id="${P}stealthBtn" class="${P}btn" data-testid="btn-stealth-toggle" style="flex:0 0 auto;min-width:64px;">OFF</button>
              </div>
              <div id="${P}stealthStatus" style="margin-top:6px;font-size:${mobile ? 9 : 10}px;color:#94a3b8;padding:6px 8px;background:rgba(0,0,0,0.25);border-radius:6px;">
                Multiplier: <span id="${P}stealthMult" style="color:#e6edf3;font-weight:700;">1×</span> · Probes skip while idle: <span id="${P}stealthSkip" style="color:#e6edf3;font-weight:700;">no</span>
              </div>
            </div>
            <div class="${P}section">
              <div class="${P}sectionttl">Favorites Cycle (Iter 98)</div>
              <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                <button id="${P}teachFav" class="${P}btn" data-testid="btn-teach-favorites" title="Click, then click any tile in Pocket Option's favorites bar. CYCLE will rotate through the tiles found in that container.">🎓 Teach Favorites</button>
                <button id="${P}clearFav" class="${P}btn" data-testid="btn-clear-favorites" title="Forget the taught favorites container — you'll need to teach again">🗑 Clear</button>
              </div>
              <div class="${P}timing-row" style="margin-top:8px;" title="How often (seconds) CYCLE clicks the next tile in the taught favorites bar.">
                <input id="${P}cycleInt" class="${P}timing-slider" type="range" min="5" max="120" step="5" value="30" style="width:100%;" />
                <div style="display:flex;justify-content:space-between;font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-top:4px;">
                  <span>rotate every</span>
                  <span id="${P}cycleIntV" style="color:#22d3ee;font-weight:700;">30s</span>
                  <span>through favorites</span>
                </div>
              </div>
              <div id="${P}favStatus" style="margin-top:6px;font-size:${mobile ? 9 : 10}px;color:#94a3b8;padding:6px 8px;background:rgba(0,0,0,0.25);border-radius:6px;">
                Status: <span id="${P}favStatusText" style="color:#e6edf3;">not taught yet</span>
              </div>
            </div>

            <div class="${P}section">
              <div class="${P}sectionttl">Chart Type Sync (Iter 99)</div>
              <div style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-bottom:6px;line-height:1.5;">
                When the app has a chart type selected (Japanese/Heikin/Line/Bars), TM will switch PO's chart type on every signal. First, open PO's chart-type menu, then click Teach → click any chart type in that menu.
              </div>
              <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                <button id="${P}teachChart" class="${P}btn" data-testid="btn-teach-charttype" title="Open PO's chart-type menu, then click Teach. Next click on any chart-type button in that menu will record the menu container.">🎓 Teach Chart Types</button>
                <button id="${P}clearChart" class="${P}btn" data-testid="btn-clear-charttype" title="Forget the taught chart-type menu">🗑 Clear</button>
              </div>
              <div id="${P}chartStatus" style="margin-top:6px;font-size:${mobile ? 9 : 10}px;color:#94a3b8;padding:6px 8px;background:rgba(0,0,0,0.25);border-radius:6px;">
                Status: <span id="${P}chartStatusText" style="color:#e6edf3;">not taught yet</span>
              </div>
              <!-- Iter 107 — Manual Chart Type dropdown (in addition to auto-sync) -->
              <div style="margin-top:8px;padding-top:8px;border-top:1px dashed rgba(148,163,184,0.2);">
                <div style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-bottom:4px;font-weight:600;">
                  Manual Chart Type <span style="color:#64748b;font-weight:500;">(overrides app until "auto")</span>
                </div>
                <select id="${P}chartTypeSel" class="${P}stratsel" data-testid="chart-type-manual-select" style="width:100%;" title="Pick a chart type and TM will switch PO to it once. Choose 'Auto (follow app)' to defer to whatever the React dashboard selects.">
                  <option value="auto">Auto (follow app)</option>
                  <option value="candles">Japanese Candles</option>
                  <option value="heikin_ashi">Heikin Ashi</option>
                  <option value="line">Line</option>
                  <option value="bars">Bars</option>
                  <option value="area">Area</option>
                </select>
              </div>
            </div>

            <!-- Iter 107 — Auto-Invert Threshold slider -->
            <div class="${P}section" data-testid="autoinvert-threshold-section" title="How many consecutive losses before AUTO-INVERT flips the signal direction. Lower = snappier reaction, higher = more tolerant of noise.">
              <div class="${P}sectionttl">Auto-Invert Sensitivity</div>
              <div style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-bottom:6px;line-height:1.5;">
                Flip after <span id="${P}invThreshVal" style="color:#22d3ee;font-weight:800;">1</span> consecutive loss<span id="${P}invThreshS"></span>. Same threshold also flips BACK when the inverted direction starts losing.
              </div>
              <input id="${P}invThresh" data-testid="invert-threshold-slider" type="range" min="1" max="5" step="1" value="1" style="width:100%;" />
              <div style="display:flex;justify-content:space-between;font-size:${mobile ? 8 : 9}px;color:#64748b;margin-top:2px;font-weight:600;">
                <span>1 · snappy</span>
                <span>3 · balanced</span>
                <span>5 · tolerant</span>
              </div>
              <!-- Iter 113 — Diagnose + self-test buttons: click "Test" to
                   simulate the threshold-worth of losses and confirm the
                   engine flips. Click "Diag" to see WHY it may not flip. -->
              <div style="display:flex;gap:5px;margin-top:8px;">
                <button id="${P}invDiag" data-testid="btn-invert-diag" class="${P}btn" style="flex:1;font-size:${mobile ? 10 : 9}px;padding:5px 6px;background:#1e293b !important;color:#22d3ee !important;border:1px solid #22d3ee !important;" title="Print a diagnostic snapshot to the console (why auto-invert did or didn't fire)">Diag</button>
                <button id="${P}invSelfTest" data-testid="btn-invert-test" class="${P}btn" style="flex:1;font-size:${mobile ? 10 : 9}px;padding:5px 6px;background:#1e293b !important;color:#f59e0b !important;border:1px solid #f59e0b !important;" title="Simulate the threshold-worth of losses and confirm the engine actually flips">Test Flip</button>
              </div>
              <div id="${P}invDiagOut" style="margin-top:6px;font-size:${mobile ? 9 : 10}px;color:#94a3b8;font-family:ui-monospace,monospace;line-height:1.4;min-height:14px;"></div>
            </div>

            <!-- Iter 108 — Latency-Driven Abstain threshold slider -->
            <div class="${P}section" data-testid="latency-abstain-section" title="Auto-pause NEW trades when the p99 network latency crosses this threshold. Set to OFF to disable. Trades resume automatically when latency normalises.">
              <div class="${P}sectionttl">Latency Abstain</div>
              <div style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-bottom:6px;line-height:1.5;">
                Pause trades if p99 latency > <span id="${P}latAbsVal" style="color:#22d3ee;font-weight:800;">300</span> ms.
                <span id="${P}latAbsOff" style="color:#f87171;font-weight:700;display:none;">Currently OFF</span>
              </div>
              <input id="${P}latAbsThresh" data-testid="latency-abstain-slider" type="range" min="0" max="1000" step="50" value="300" style="width:100%;" />
              <div style="display:flex;justify-content:space-between;font-size:${mobile ? 8 : 9}px;color:#64748b;margin-top:2px;font-weight:600;">
                <span>OFF · 0</span>
                <span>strict · 300ms</span>
                <span>lenient · 1000ms</span>
              </div>
              <div id="${P}latAbsState" data-testid="latency-abstain-state" style="margin-top:6px;padding:5px 8px;border-radius:5px;font-size:${mobile ? 10 : 11}px;font-weight:700;text-align:center;background:rgba(74,222,128,0.1);color:#4ade80;border:1px solid rgba(74,222,128,0.3);">
                ✓ TRADING — latency healthy
              </div>
            </div>

            <!-- Iter 109 — Elite Score Gate (composite quality filter) -->
            <div class="${P}section" data-testid="elite-gate-section" title="Only allow trades when the Elite Composite Score (SMT + Sweep + ATR band + OB/FVG + microstructure) is above this threshold. Set to OFF to disable. When ON, also enforces direction agreement between the signal and the Elite bias.">
              <div class="${P}sectionttl">Elite Score Gate</div>
              <div style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-bottom:6px;line-height:1.5;">
                Only trade when Elite Score ≥ <span id="${P}eliteGateVal" style="color:#34d399;font-weight:800;">0</span>.
                <span id="${P}eliteGateOff" style="color:#f87171;font-weight:700;">Currently OFF</span>
              </div>
              <input id="${P}eliteGateThresh" data-testid="elite-gate-slider" type="range" min="0" max="100" step="5" value="0" style="width:100%;" />
              <div style="display:flex;justify-content:space-between;font-size:${mobile ? 8 : 9}px;color:#64748b;margin-top:2px;font-weight:600;">
                <span>OFF · 0</span>
                <span>balanced · 50</span>
                <span>elite · 80+</span>
              </div>
              <label style="display:flex;align-items:center;gap:6px;margin-top:6px;font-size:${mobile ? 10 : 11}px;color:#cbd5e1;cursor:pointer;" data-testid="elite-gate-enforcedir-label">
                <input id="${P}eliteGateEnforceDir" data-testid="elite-gate-enforce-direction" type="checkbox" checked style="cursor:pointer;" />
                Enforce direction agreement (block CALL/PUT mismatches)
              </label>
              <div id="${P}eliteGateState" data-testid="elite-gate-state" style="margin-top:6px;padding:5px 8px;border-radius:5px;font-size:${mobile ? 10 : 11}px;font-weight:700;text-align:center;background:rgba(100,116,139,0.15);color:#94a3b8;border:1px solid rgba(100,116,139,0.3);">
                ○ Gate disabled
              </div>
            </div>

            <div class="${P}section">
              <div class="${P}sectionttl">Strategy Selector</div>
              <div class="${P}stratrow" style="display:flex;gap:6px;align-items:center;">
                <select id="${P}stratTf" class="${P}stratsel" data-testid="strategy-tf-select" title="Iter 96 — Choose a chart timeframe to browse strategies for." style="flex:0 0 78px;">
                  <option value="5s">5s</option>
                  <option value="15s">15s</option>
                  <option value="30s">30s</option>
                  <option value="1m">1m</option>
                  <option value="2m">2m</option>
                  <option value="3m">3m</option>
                  <option value="5m">5m</option>
                </select>
                <select id="${P}strat" class="${P}stratsel" data-testid="strategy-select" style="flex:1;">
                  <option value="default">All Strategies</option>
                </select>
              </div>
            </div>

            <div class="${P}section">
              <div class="${P}sectionttl">Seconds-Number Timing</div>
              <div class="${P}timing-row" data-testid="sns-timing-slider-row" title="Drag to choose which second of the 1m candle triggers the SNS trade. Range 5–55s remaining.">
                <input id="${P}timing" data-testid="sns-timing-slider" class="${P}timing-slider" type="range" min="5" max="55" step="1" value="49" style="width:100%;" />
                <div style="display:flex;justify-content:space-between;font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-top:4px;">
                  <span>fires at</span>
                  <span id="${P}timingv" style="color:#22d3ee;font-weight:700;">:49</span>
                  <span>of the 1m candle</span>
                </div>
              </div>
              <!-- Iter 117 — Multi-second SNS chip picker (max 3) -->
              <div class="${P}snsmulti" data-testid="sns-multi-picker" style="margin-top:8px;padding:6px;background:rgba(0,0,0,0.25);border-radius:6px;">
                <div style="display:flex;justify-content:space-between;align-items:center;font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-bottom:4px;">
                  <span style="font-weight:600;">Multi-second targets <span style="color:#64748b;">(tap up to 3)</span></span>
                  <button type="button" id="${P}snsMultiClear" data-testid="sns-multi-clear" style="background:transparent;border:1px solid #334155;color:#94a3b8;padding:1px 6px;border-radius:4px;font-size:9px;cursor:pointer;">Clear</button>
                </div>
                <div id="${P}snsMultiChips" data-testid="sns-multi-chips" style="display:flex;flex-wrap:wrap;gap:3px;"></div>
                <div style="font-size:9px;color:#64748b;margin-top:4px;" id="${P}snsMultiSummary" data-testid="sns-multi-summary">Using slider (single target)</div>
              </div>
              <!-- Iter 104 — Direction Mode: fire WITH or AGAINST current 1m candle -->
              <div class="${P}snsdir" data-testid="sns-direction-mode" title="Choose whether SNS fires WITH the current 1m candle direction (with-trend) or AGAINST it (contrarian). Default: AGAINST.">
                <div style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-bottom:4px;font-weight:600;">Direction Mode</div>
                <div class="${P}snsdirrow">
                  <button type="button" id="${P}snsDirAgainst" data-testid="sns-dir-against" class="${P}snsdirbtn active" title="Contrarian — fires OPPOSITE to the current 1m candle body. Default behaviour.">↺ Against Candle</button>
                  <button type="button" id="${P}snsDirWith" data-testid="sns-dir-with" class="${P}snsdirbtn" title="With-trend — fires the SAME direction as the current 1m candle body.">↻ With Candle</button>
                </div>
              </div>
            </div>

            <div class="${P}section">
              <div class="${P}thresholds" id="${P}thresholds" data-testid="model-thresholds-section" title="Per-model minimum confidence gates. Any voter below its threshold is excluded from the ensemble vote. Set to 0 to disable a gate.">
                <div class="${P}sectionttl">Min-Confidence Gates (%)</div>
                <div class="${P}thrrow" style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
                  <div>
                    <div style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-bottom:3px;">Confluence</div>
                    <input id="${P}thrConf" data-testid="thr-confluence" class="${P}thrInp" type="number" min="0" max="100" step="1" value="0" style="width:100%;" />
                  </div>
                  <div>
                    <div style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-bottom:3px;">Improved v2</div>
                    <input id="${P}thrImp" data-testid="thr-improved-v2" class="${P}thrInp" type="number" min="0" max="100" step="1" value="0" style="width:100%;" />
                  </div>
                  <div>
                    <div style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-bottom:3px;">Maximized v3</div>
                    <input id="${P}thrMax" data-testid="thr-maximized-v3" class="${P}thrInp" type="number" min="0" max="100" step="1" value="0" style="width:100%;" />
                  </div>
                  <div>
                    <div style="font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-bottom:3px;">IQ 720</div>
                    <input id="${P}thrIq" data-testid="thr-iq720" class="${P}thrInp" type="number" min="0" max="100" step="1" value="0" style="width:100%;" />
                  </div>
                </div>
              </div>
            </div>

            <div class="${P}section">
              <div class="${P}latencyrow" data-testid="latency-offset-section" title="Trade latency offset. Positive (+N): sleep N seconds before clicking. Negative (-N): widen freshness budget.">
                <div class="${P}sectionttl">Latency Offset</div>
                <input id="${P}latency" data-testid="latency-offset-slider" class="${P}latslider" type="range" min="-15" max="15" step="0.5" value="3.5" style="width:100%;" />
                <div style="display:flex;justify-content:space-between;font-size:${mobile ? 9 : 10}px;color:#94a3b8;margin-top:4px;">
                  <span>-15s</span>
                  <span id="${P}latvalue" style="color:#22d3ee;font-weight:700;">+3.5s</span>
                  <span>+15s</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ═════════════════ TAB: STATS ═════════════════ -->
        <div class="${P}tabpanel" data-tab-panel="stats" data-testid="tab-panel-stats">
          <div class="${P}section">
            <div class="${P}sectionttl" style="display:flex;justify-content:space-between;align-items:center;">
              <span>Trading Stats</span>
              <button id="${P}statsreset" class="${P}statsreset" data-testid="reset-stats-btn" title="Reset W/L counters, win rate, streak, and P/L" style="background:transparent;border:none;color:#64748b;font-size:14px;cursor:pointer;padding:0 4px;">⟲</button>
            </div>
            <div class="${P}stats">
              <div class="${P}stat"><span class="${P}stlbl">W/L</span><span class="${P}stval" id="${P}wl">0/0</span></div>
              <div class="${P}stat"><span class="${P}stlbl">Rate</span><span class="${P}stval" id="${P}rate">0%</span></div>
              <div class="${P}stat"><span class="${P}stlbl">Strk</span><span class="${P}stval" id="${P}streak">0</span></div>
              <div class="${P}stat"><span class="${P}stlbl">P/L</span><span class="${P}stval" id="${P}profit">$0</span></div>
            </div>
          </div>

          <div class="${P}section">
            <div class="${P}sectionttl" style="display:flex;justify-content:space-between;align-items:center;">
              <span>Event Log</span>
              <span id="${P}logtog" style="font-size:${mobile ? 9 : 10}px;color:#64748b;cursor:pointer;user-select:none;">show <span id="${P}arrow">&#9660;</span></span>
            </div>
            <div class="${P}logbox" id="${P}log"></div>
          </div>

          <button class="${P}resetbtn" id="${P}resetbtn" data-testid="reset-defaults-btn" title="Wipe saved settings and reload — restores recommended defaults">⟳ RESET TO DEFAULTS</button>
        </div>

        <!-- ═════════════════ TAB: FOREX (Iter 147) ═════════════════ -->
        <div class="${P}tabpanel" data-tab-panel="forex" data-testid="tab-panel-forex">

          <!-- Iter 148 — Universal Win/Loss teach (applies to binary options too) -->
          <div class="${P}section" data-testid="fx-result-teach-section" title="Point-to-teach the WIN and LOSS row markers from your deal history. Applies to BOTH binary options and Forex trades — fixes win/loss detection permanently for your PO layout.">
            <div class="${P}sectionttl">🎓 Win/Loss Detection Teach (Universal)</div>
            <div style="font-size:10px;color:#94a3b8;margin-bottom:8px;line-height:1.4;">
              If wins/losses aren't being detected, click a <b>resolved WIN row</b> and a <b>resolved LOSS row</b> in your PO deal history to teach the bot exactly how your layout marks them. Also fixes A-INV (which depends on win/loss detection).
            </div>
            <div id="${P}resultTeachGrid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;"></div>
            <div style="display:flex;gap:6px;margin-top:8px;">
              <button id="${P}resultDiagBtn" data-testid="result-diag-btn" class="${P}btn" style="flex:1;font-size:11px;">◉ DIAG</button>
              <button id="${P}resultClearAllBtn" data-testid="result-clear-all-btn" class="${P}btn" style="flex:1;font-size:11px;background:#7c2d12;">✕ CLEAR ALL</button>
            </div>
            <pre id="${P}resultDiagOut" data-testid="result-diag-output" style="margin-top:8px;padding:6px;background:#0b1220;border:1px solid #1e293b;border-radius:4px;font-size:9px;color:#94a3b8;max-height:140px;overflow:auto;white-space:pre-wrap;display:none;"></pre>
          </div>

          <div class="${P}section" data-testid="fx-poller-section" title="Toggle the Tampermonkey → MT5 order poller. When ON, the script long-polls the backend for queued Forex orders and executes them in the PO web-MT5 UI.">
            <div class="${P}sectionttl">Forex Order Poller</div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <button id="${P}fxPollBtn" data-testid="fx-poll-toggle" class="${P}btn" style="flex:1;min-width:110px;">START</button>
              <span id="${P}fxPollStatus" data-testid="fx-poll-status" style="font-size:11px;color:#94a3b8;">idle</span>
            </div>
            <div style="margin-top:8px;display:grid;grid-template-columns:repeat(4,1fr);gap:6px;font-size:10px;color:#cbd5e1;">
              <div>Pending<br><span id="${P}fxStatPending" data-testid="fx-stat-pending" style="color:#22d3ee;font-weight:600;font-size:14px;">–</span></div>
              <div>Picked<br><span id="${P}fxStatPicked" data-testid="fx-stat-picked" style="color:#22d3ee;font-weight:600;font-size:14px;">0</span></div>
              <div>Placed<br><span id="${P}fxStatPlaced" data-testid="fx-stat-placed" style="color:#22c55e;font-weight:600;font-size:14px;">0</span></div>
              <div>Rejected<br><span id="${P}fxStatRejected" data-testid="fx-stat-rejected" style="color:#ef4444;font-weight:600;font-size:14px;">0</span></div>
            </div>
          </div>

          <div class="${P}section" data-testid="fx-teach-section" title="Point-to-teach MT5 controls. Click a Teach button then click the matching element inside PO's web-MT5 iframe — the CSS selector is saved locally and used for every future order.">
            <div class="${P}sectionttl">MT5 Point-to-Teach Selectors <span id="${P}fxTeachProgress" data-testid="fx-teach-progress" style="font-size:10px;color:#22d3ee;font-weight:600;margin-left:6px;">0/6 taught</span></div>
            <div id="${P}fxIframeWarn" data-testid="fx-iframe-warn" style="display:none;margin-bottom:8px;padding:6px 8px;background:#450a0a;border:1px solid #7f1d1d;border-radius:4px;color:#fca5a5;font-size:10px;line-height:1.4;">
              ⚠️ MT5 iframe is <b>cross-origin</b> — the browser is blocking DOM injection. Open MT5 as a top-level tab (not embedded) to use point-to-teach, or run PO in the same origin as MT5.
            </div>
            <div style="font-size:10px;color:#94a3b8;margin-bottom:8px;">
              Click <b>Teach</b>, then within 30 s click the corresponding MT5 control (input field or button). The CSS selector is saved to GM storage. Use <b>DRY RUN</b> to smoke-test lot/SL/TP fills without placing a real order.
            </div>
            <div id="${P}fxTeachGrid" style="display:grid;grid-template-columns:repeat(2,1fr);gap:6px;"></div>
            <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;">
              <button id="${P}fxDryRunBtn" data-testid="fx-dryrun-btn" class="${P}btn" style="flex:1;min-width:120px;font-size:11px;background:#1e3a8a;">🧪 DRY RUN</button>
              <button id="${P}fxDiagBtn" data-testid="fx-diagnose-btn" class="${P}btn" style="flex:1;min-width:110px;font-size:11px;">◉ DIAGNOSE</button>
              <button id="${P}fxClearAllBtn" data-testid="fx-clear-all-btn" class="${P}btn" style="flex:1;min-width:110px;font-size:11px;background:#7c2d12;">✕ CLEAR ALL</button>
            </div>
            <pre id="${P}fxDiagOut" data-testid="fx-diag-output" style="margin-top:8px;padding:6px;background:#0b1220;border:1px solid #1e293b;border-radius:4px;font-size:9px;color:#94a3b8;max-height:160px;overflow:auto;white-space:pre-wrap;display:none;"></pre>
          </div>

          <div class="${P}section" data-testid="fx-help-section">
            <div class="${P}sectionttl">Quick Reference</div>
            <div style="font-size:10px;color:#94a3b8;line-height:1.5;">
              • Forex signals are queued by the backend confluence engine into <code>/api/forex/orders/pending</code>.<br>
              • The poller claims each order, hands it to the MT5 adapter, and reports fill/rejection back.<br>
              • If the MT5 iframe is <b>cross-origin</b>, DOM injection is blocked by the browser — open MT5 as a top-level tab to work around it.<br>
              • Console helpers: <code>__aiEliteForexStart()</code>, <code>__aiEliteForexStats()</code>, <code>__aiEliteMt5Diag()</code>.
            </div>
          </div>

        </div>
        <!-- ═════════════════ /TAB: FOREX ═════════════════ -->
      </div>
      <div class="${P}resize" id="${P}resize" data-testid="resize-handle" title="Drag to resize panel width. Saved across reloads."></div>
      <div class="${P}sideresize left" id="${P}resizeL" data-testid="resize-handle-left" title="Drag left/right to resize (grows toward the left)."></div>
      <div class="${P}sideresize right" id="${P}resizeR" data-testid="resize-handle-right" title="Drag left/right to resize (grows toward the right)."></div>
    </div>
  `;

  startWatchdog();
  // Restore saved width (Iter 59) — applied after innerHTML is set so the
  // rule wins over the CSS default. Validates within sane bounds.
  try {
    if (typeof GM_getValue !== 'undefined') {
      const savedW = parseInt(GM_getValue(`${P}panelW`, '0'), 10);
      if (savedW >= 180 && savedW <= 600) {
        panelEl.style.setProperty('width', `${savedW}px`, 'important');
      }
    }
  } catch (_e) { /* ignore */ }
  console.log('[Elite Bot] Panel created');
  return panelEl;
}

function q(id) {
  return document.getElementById(`${P}${id}`);
}


// ══════════════════════════════════════════════════════════════════════
// Iter 147 — Forex tab: poller toggle + MT5 point-to-teach UI
// Isolated helper so index.js / re-injection paths pick it up cleanly.
// ══════════════════════════════════════════════════════════════════════

const _MT5_CONTROLS = [
  { key: 'symbol_search', label: 'Symbol' },
  { key: 'lot_input',     label: 'Lot / Volume' },
  { key: 'sl_input',      label: 'Stop Loss' },
  { key: 'tp_input',      label: 'Take Profit' },
  { key: 'buy_btn',       label: 'BUY button' },
  { key: 'sell_btn',      label: 'SELL button' },
];

const _RESULT_TEACH_CONTROLS = [
  { key: 'win',       label: '✓ WIN row',   colour: '#22c55e' },
  { key: 'loss',      label: '✗ LOSS row',  colour: '#ef4444' },
  { key: 'container', label: '📦 Container', colour: '#22d3ee' },
];

let _fxRefreshTimer = null;

// Iter 148 — Universal Win/Loss teach section (top of Forex tab). Applies
// to binary options too, since the tradeResultWatcher parses both.
function _initResultTeachSection() {
  const grid = q('resultTeachGrid');
  const diagBtn = q('resultDiagBtn');
  const clearAllBtn = q('resultClearAllBtn');
  const diagOut = q('resultDiagOut');
  if (!grid) return;

  const _render = () => {
    const taught = tradeResultWatcher.getTaught();
    _RESULT_TEACH_CONTROLS.forEach((c) => {
      const cell = document.getElementById(`${P}resultTeachCell_${c.key}`);
      if (!cell) return;
      const sel = document.getElementById(`${P}resultTeachSel_${c.key}`);
      if (sel) {
        const val = taught[c.key];
        sel.textContent = val ? val : 'not taught';
        sel.style.color = val ? c.colour : '#64748b';
      }
    });
  };

  grid.innerHTML = '';
  _RESULT_TEACH_CONTROLS.forEach((c) => {
    const cell = document.createElement('div');
    cell.id = `${P}resultTeachCell_${c.key}`;
    cell.style.cssText = 'display:flex;flex-direction:column;gap:3px;padding:6px;background:#0f172a;border:1px solid #1e293b;border-radius:4px;';
    cell.innerHTML = `
      <div style="font-size:10px;color:${c.colour};font-weight:600;">${c.label}</div>
      <div id="${P}resultTeachSel_${c.key}" data-testid="result-teach-sel-${c.key}" style="font-size:9px;color:#64748b;word-break:break-all;min-height:12px;">not taught</div>
      <div style="display:flex;gap:4px;">
        <button id="${P}resultTeachBtn_${c.key}" data-testid="result-teach-btn-${c.key}" class="${P}btn" style="flex:1;font-size:10px;padding:4px 6px;">Teach</button>
        <button id="${P}resultClearBtn_${c.key}" data-testid="result-clear-btn-${c.key}" class="${P}btn" style="width:28px;font-size:10px;padding:4px 4px;background:#7c2d12;">✕</button>
      </div>
    `;
    grid.appendChild(cell);
  });
  _render();

  _RESULT_TEACH_CONTROLS.forEach((c) => {
    const tBtn = q(`resultTeachBtn_${c.key}`);
    const cBtn = q(`resultClearBtn_${c.key}`);
    if (tBtn) {
      tBtn.addEventListener('click', () => {
        tBtn.textContent = `… click ${c.key}`;
        tBtn.disabled = true;
        tradeResultWatcher.startTeach(c.key, (res) => {
          tBtn.disabled = false;
          tBtn.textContent = res && res.success ? '✓ saved' : 'Teach';
          _render();
          setTimeout(() => { tBtn.textContent = 'Teach'; }, 1500);
        });
      });
    }
    if (cBtn) {
      cBtn.addEventListener('click', () => {
        tradeResultWatcher.clearTaught(c.key);
        _render();
      });
    }
  });

  if (diagBtn) {
    diagBtn.addEventListener('click', () => {
      let diag;
      try { diag = tradeResultWatcher._diag(); }
      catch (e) { diag = { error: e.message }; }
      if (diagOut) {
        diagOut.style.display = 'block';
        diagOut.textContent = JSON.stringify(diag, null, 2);
      }
    });
  }

  if (clearAllBtn) {
    clearAllBtn.addEventListener('click', () => {
      if (!window.confirm('Clear all taught win/loss markers?')) return;
      tradeResultWatcher.clearTaught();
      _render();
    });
  }
}

function _initForexTab() {
  const pollBtn = q('fxPollBtn');
  const pollStatus = q('fxPollStatus');
  const grid = q('fxTeachGrid');
  const diagBtn = q('fxDiagBtn');
  const clearAllBtn = q('fxClearAllBtn');
  const diagOut = q('fxDiagOut');
  if (!pollBtn || !grid) return;   // tab not rendered (e.g. mid-reinject)

  // ---- Iter 148 — Universal WIN/LOSS teach (top of the tab)
  _initResultTeachSection();

  // ---- Poller toggle
  const _renderPoller = () => {
    const running = forexOrderPoller.isRunning();
    pollBtn.textContent = running ? '■ STOP' : '▶ START';
    pollBtn.classList.toggle('active', running);
    pollBtn.style.background = running ? '#166534' : '';
    if (pollStatus) {
      pollStatus.textContent = running ? 'polling every 5 s' : 'idle';
      pollStatus.style.color = running ? '#22c55e' : '#94a3b8';
    }
  };
  pollBtn.addEventListener('click', () => {
    if (forexOrderPoller.isRunning()) forexOrderPoller.stop();
    else forexOrderPoller.start(5000);
    _renderPoller();
  });
  _renderPoller();

  // ---- Live stats refresh (queue-stats from backend + local poller counters)
  const _refreshStats = async () => {
    // Local counters (placed/rejected/picked, running flag)
    const local = forexOrderPoller.getStats();
    const setTxt = (id, val) => { const el = q(id); if (id !== null && q(id)) q(id).textContent = String(val); };
    setTxt('fxStatPicked', local.picked || 0);
    setTxt('fxStatPlaced', local.placed || 0);
    setTxt('fxStatRejected', local.rejected || 0);
    // Backend pending count
    try {
      const qs = await apiGet('/forex/orders/queue-stats');
      if (qs && typeof qs.pending === 'number') setTxt('fxStatPending', qs.pending);
    } catch (_e) { /* backend offline — leave "–" */ }
    // Iter 151 — Re-verify taught selectors so ✓/✗ badges reflect the
    // *current* MT5 iframe state (user may open/close MT5 mid-session).
    try {
      if (typeof _renderVerify === 'function') _renderVerify();
      if (typeof _renderIframeWarn === 'function') _renderIframeWarn();
    } catch (_e) { /* forward-refs before grid mount */ }
  };
  if (_fxRefreshTimer) clearInterval(_fxRefreshTimer);
  _fxRefreshTimer = setInterval(_refreshStats, 3000);
  _refreshStats();

  // ---- Teach grid
  grid.innerHTML = '';
  _MT5_CONTROLS.forEach((c) => {
    const cell = document.createElement('div');
    cell.style.cssText = 'display:flex;flex-direction:column;gap:3px;padding:6px;background:#0f172a;border:1px solid #1e293b;border-radius:4px;';
    cell.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:4px;">
        <div style="font-size:10px;color:#cbd5e1;font-weight:600;">${c.label}</div>
        <span id="${P}fxTeachBadge_${c.key}" data-testid="fx-teach-badge-${c.key}" style="font-size:9px;padding:1px 5px;border-radius:8px;background:#334155;color:#94a3b8;">–</span>
      </div>
      <div id="${P}fxTeachSel_${c.key}" data-testid="fx-teach-sel-${c.key}" style="font-size:9px;color:#64748b;word-break:break-all;min-height:12px;">not taught</div>
      <div style="display:flex;gap:4px;">
        <button id="${P}fxTeachBtn_${c.key}" data-testid="fx-teach-btn-${c.key}" class="${P}btn" style="flex:1;font-size:10px;padding:4px 6px;">Teach</button>
        <button id="${P}fxClearBtn_${c.key}" data-testid="fx-clear-btn-${c.key}" class="${P}btn" style="width:28px;font-size:10px;padding:4px 4px;background:#7c2d12;">✕</button>
      </div>
    `;
    grid.appendChild(cell);
  });

  // Iter 151 — Cross-origin warning banner (only when iframe is unreachable).
  const _renderIframeWarn = () => {
    const warn = q('fxIframeWarn');
    if (!warn) return;
    try {
      const diag = mt5Adapter.diagnose();
      warn.style.display = (diag && diag.doc_kind === 'cross-origin') ? 'block' : 'none';
    } catch (_e) { warn.style.display = 'none'; }
  };

  // Iter 151 — Verify badges + progress counter.
  const _renderVerify = () => {
    let taughtCount = 0;
    let verify = {};
    try { verify = mt5Adapter.verifyAll(); } catch (_e) { verify = {}; }
    _MT5_CONTROLS.forEach((c) => {
      const badge = q(`fxTeachBadge_${c.key}`);
      if (!badge) return;
      const v = verify[c.key] || { found: false };
      if (v.found) {
        badge.textContent = v.taught ? '✓ taught' : '✓ auto';
        badge.style.background = v.taught ? '#166534' : '#0e7490';
        badge.style.color = '#ecfeff';
        if (v.taught) taughtCount++;
      } else {
        badge.textContent = '✗';
        badge.style.background = '#7f1d1d';
        badge.style.color = '#fecaca';
      }
    });
    const prog = q('fxTeachProgress');
    if (prog) {
      prog.textContent = `${taughtCount}/${_MT5_CONTROLS.length} taught`;
      prog.style.color = taughtCount === _MT5_CONTROLS.length ? '#22c55e' : '#22d3ee';
    }
  };

  const _renderTaught = () => {
    _MT5_CONTROLS.forEach((c) => {
      const sel = q(`fxTeachSel_${c.key}`);
      if (!sel) return;
      let val = null;
      try {
        val = (typeof GM_getValue === 'function')
          ? GM_getValue('ai_elite_mt5_' + c.key, null)
          : (window.localStorage.getItem('ai_elite_mt5_' + c.key) || null);
      } catch (_e) { /* ignore */ }
      sel.textContent = val ? val : 'not taught';
      sel.style.color = val ? '#22d3ee' : '#64748b';
    });
    _renderVerify();
    _renderIframeWarn();
  };
  _renderTaught();

  _MT5_CONTROLS.forEach((c) => {
    const tBtn = q(`fxTeachBtn_${c.key}`);
    const cBtn = q(`fxClearBtn_${c.key}`);
    if (tBtn) {
      tBtn.addEventListener('click', () => {
        tBtn.textContent = '… click MT5 control';
        tBtn.disabled = true;
        mt5Adapter.startTeach(c.key, (res) => {
          tBtn.disabled = false;
          tBtn.textContent = res && res.success ? '✓ saved' : 'Teach';
          _renderTaught();
          setTimeout(() => { tBtn.textContent = 'Teach'; }, 1500);
        });
      });
    }
    if (cBtn) {
      cBtn.addEventListener('click', () => {
        mt5Adapter.clearTaught(c.key);
        _renderTaught();
      });
    }
  });

  // ---- Diagnose
  if (diagBtn) {
    diagBtn.addEventListener('click', () => {
      const out = mt5Adapter.diagnose();
      if (diagOut) {
        diagOut.style.display = 'block';
        diagOut.textContent = JSON.stringify(out, null, 2);
      }
      _renderIframeWarn();
    });
  }

  // ---- Iter 151 — Dry run (fills lot/SL/TP, never clicks BUY/SELL)
  const dryBtn = q('fxDryRunBtn');
  if (dryBtn) {
    dryBtn.addEventListener('click', async () => {
      dryBtn.disabled = true;
      const orig = dryBtn.textContent;
      dryBtn.textContent = '… running';
      try {
        const res = await mt5Adapter.dryRun({ lots: 0.01 });
        if (diagOut) {
          diagOut.style.display = 'block';
          diagOut.textContent = JSON.stringify(res, null, 2);
        }
        dryBtn.textContent = res.ok ? '✓ DRY RUN OK' : '✗ FAILED';
        dryBtn.style.background = res.ok ? '#166534' : '#7f1d1d';
      } catch (e) {
        dryBtn.textContent = '✗ ERROR';
        dryBtn.style.background = '#7f1d1d';
        if (diagOut) {
          diagOut.style.display = 'block';
          diagOut.textContent = `dry-run error: ${e.message}`;
        }
      } finally {
        _renderVerify();
        setTimeout(() => {
          dryBtn.textContent = orig;
          dryBtn.style.background = '#1e3a8a';
          dryBtn.disabled = false;
        }, 2500);
      }
    });
  }

  // ---- Clear all
  if (clearAllBtn) {
    clearAllBtn.addEventListener('click', () => {
      if (!window.confirm('Clear all taught MT5 selectors?')) return;
      _MT5_CONTROLS.forEach((c) => mt5Adapter.clearTaught(c.key));
      _renderTaught();
    });
  }
}

function startWatchdog() {
  if (watchdogInterval) clearInterval(watchdogInterval);
  watchdogInterval = setInterval(() => {
    const host = document.getElementById(`${P}host`);
    if (!host || !document.body.contains(host)) {
      console.log('[Elite Bot] Panel removed, re-injecting...');
      reInject();
    }
  }, 2000);
}

function reInject() {
  try {
    const old = document.getElementById(`${P}host`);
    if (old) old.remove();
    const newPanel = createPanel();
    document.body.appendChild(newPanel);
    if (window._epbCallbacks) {
      initPanelEvents(window._epbCallbacks);
    }
  } catch (e) {
    console.error('[Elite Bot] Re-inject failed:', e);
  }
}

/**
 * Init events (mouse + touch)
 */
export function initPanelEvents(callbacks = {}) {
  window._epbCallbacks = callbacks;
  setLogContainer(q('log'));

  // Iter 96 — Tab navigation
  const tabButtons = document.querySelectorAll(`.${P}tabbtn`);
  const tabPanels = document.querySelectorAll(`.${P}tabpanel`);
  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      tabButtons.forEach((b) => b.classList.toggle('active', b.dataset.tab === target));
      tabPanels.forEach((p) => p.classList.toggle('active', p.dataset.tabPanel === target));
      try {
        if (typeof GM_setValue !== 'undefined') GM_setValue(`${P}activeTab`, target);
      } catch (_e) { /* ignore */ }
    });
  });
  // Restore last-active tab
  try {
    if (typeof GM_getValue !== 'undefined') {
      const savedTab = GM_getValue(`${P}activeTab`, 'live');
      if (savedTab && savedTab !== 'live') {
        const btn = document.querySelector(`.${P}tabbtn[data-tab="${savedTab}"]`);
        if (btn) btn.click();
      }
    }
  } catch (_e) { /* ignore */ }

  // Iter 138 — Stealth Mode toggle
  const stealthBtn = q('stealthBtn');
  const stealthMult = q('stealthMult');
  const stealthSkip = q('stealthSkip');
  const _renderStealth = () => {
    const active = stealthMode.isActive();
    if (stealthBtn) {
      stealthBtn.textContent = active ? 'ON' : 'OFF';
      stealthBtn.classList.toggle('active', active);
    }
    if (stealthMult) stealthMult.textContent = `${stealthMode.getMultiplier()}×`;
    if (stealthSkip) stealthSkip.textContent = active ? 'yes' : 'no';
  };
  _renderStealth();
  if (stealthBtn) {
    stealthBtn.addEventListener('click', () => {
      stealthMode.toggle();
      _renderStealth();
    });
  }
  // Keep the UI in sync if another source (DevTools helper) flips the flag
  try { stealthMode.onChange(() => _renderStealth()); } catch (_e) { /* ignore */ }

  // ═══════════════════════════════════════════════════════════════════
  // Iter 147 — Forex tab wiring (poller toggle + MT5 point-to-teach UI)
  // ═══════════════════════════════════════════════════════════════════
  _initForexTab();

  // Iter 96 — Expand-to-fullscreen (mobile/tap-to-focus)
  const expandBtn = q('expandbtn');
  const host = document.getElementById(`${P}host`);
  if (expandBtn && host) {
    expandBtn.addEventListener('click', () => {
      host.classList.toggle('expanded');
      expandBtn.textContent = host.classList.contains('expanded') ? '⛶⁻' : '⛶';
      try {
        if (typeof GM_setValue !== 'undefined') {
          GM_setValue(`${P}expanded`, host.classList.contains('expanded'));
        }
      } catch (_e) { /* ignore */ }
    });
    // Restore expanded state
    try {
      if (typeof GM_getValue !== 'undefined' && GM_getValue(`${P}expanded`, false)) {
        host.classList.add('expanded');
        expandBtn.textContent = '⛶⁻';
      }
    } catch (_e) { /* ignore */ }
  }

  // Minimize
  const minBtn = q('minbtn');
  const body = q('body');
  if (minBtn && body) {
    minBtn.addEventListener('click', () => {
      body.classList.toggle('collapsed');
      minBtn.textContent = body.classList.contains('collapsed') ? '+' : '_';
    });
  }

  // MORE — legacy toggle. Now hidden by CSS (tabs replace it) but the click
  // handler is retained so we don't break external callers that programmatically
  // click #{P}moretog. Iter 96.
  const moreBtn = q('moretog');
  const advanced = q('advanced');
  if (moreBtn && advanced) {
    moreBtn.addEventListener('click', () => {
      const wasHidden = advanced.classList.contains('hidden');
      advanced.classList.toggle('hidden');
      moreBtn.textContent = wasHidden ? '▴ HIDE' : '▾ MORE';
    });
  }

  // RESET TO DEFAULTS — wipe saved botState + reload (Iter 58)
  const resetBtn = q('resetbtn');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      const ok = window.confirm(
        'Reset all bot settings to defaults?\n\n' +
        'This wipes saved toggles, stats, and history.\n' +
        'You will keep: trade history reports already sent to backend.\n' +
        'Page will reload immediately after reset.'
      );
      if (!ok) return;
      try {
        if (typeof GM_setValue !== 'undefined') GM_setValue('botState', null);
      } catch (_e) { /* ignore */ }
      try {
        // Best-effort clear of any stray local persistence
        localStorage.removeItem('botState');
      } catch (_e) { /* ignore */ }
      callbacks.onReset?.();
      setTimeout(() => window.location.reload(), 200);
    });
  }

  // CLICK-TO-FIRE: tapping the live preview row when quality === HIGH
  // is equivalent to pressing GO (Iter 58). Lower-quality previews are
  // non-clickable (cursor stays default, no fire).
  const qualRow = q('qualrow');
  if (qualRow) {
    qualRow.addEventListener('click', () => {
      if (qualRow.classList.contains('high')) {
        callbacks.onGo?.();
      }
    });
  }

  // Iter 62 — Per-model probability threshold inputs
  // Each input (0–100, default 0=disabled) gates one voter in force-generate-v2.
  const thrInputs = [
    { id: 'thrConf', key: 'confluence' },
    { id: 'thrImp', key: 'improved_v2' },
    { id: 'thrMax', key: 'maximized_v3' },
    { id: 'thrIq', key: 'iq720' },
  ];
  // Restore saved values
  if (!state.modelThresholds) {
    state.modelThresholds = { confluence: 0, improved_v2: 0, maximized_v3: 0, iq720: 0 };
  }
  thrInputs.forEach(({ id, key }) => {
    const inp = q(id);
    if (!inp) return;
    inp.value = String(Number(state.modelThresholds[key] || 0));
    inp.addEventListener('change', () => {
      let v = parseFloat(inp.value);
      if (!isFinite(v) || v < 0) v = 0;
      if (v > 100) v = 100;
      inp.value = String(v);
      state.modelThresholds[key] = v;
      try { saveState(); } catch (_e) { /* ignore */ }
      log(`[THR] ${key} threshold set to ${v}%`);
    });
  });

  // Iter 63 / v8.73.0 — Latency offset slider (-15s..+15s, 0.5s precision)
  const latSlider = q('latency');
  const latValue = q('latvalue');
  if (latSlider && latValue) {
    const current = Number(state.latencyOffsetSec ?? 3.5);
    latSlider.value = String(current);
    const fmt = (v) => `${v >= 0 ? '+' : ''}${Number.isInteger(v) ? v.toFixed(0) : v.toFixed(1)}s`;
    latValue.textContent = fmt(current);
    const updateLatency = () => {
      let v = parseFloat(latSlider.value);
      if (!isFinite(v)) v = 0;
      // Snap to 0.5 increments and clamp
      v = Math.round(v * 2) / 2;
      v = Math.max(-15, Math.min(15, v));
      state.latencyOffsetSec = v;
      latValue.textContent = fmt(v);
      try { saveState(); } catch (_e) { /* ignore */ }
    };
    latSlider.addEventListener('input', updateLatency);
    latSlider.addEventListener('change', () => {
      updateLatency();
      log(`[LATENCY] Trade offset set to ${state.latencyOffsetSec >= 0 ? '+' : ''}${state.latencyOffsetSec}s`);
    });
  }

  // RESIZE handle (Iter 59) — drag bottom-right corner to widen/narrow.
  // Mobile-friendly: full pointer + touch event support, persists to GM.
  const resizeEl = q('resize');
  const hostEl = document.getElementById(`${P}host`);
  if (resizeEl && hostEl) {
    let resizing = false;
    let startX = 0;
    let startW = 0;

    const getX = (ev) => (ev.touches && ev.touches[0]) ? ev.touches[0].clientX : ev.clientX;

    const onDown = (ev) => {
      resizing = true;
      resizeEl.classList.add('active');
      startX = getX(ev);
      startW = hostEl.getBoundingClientRect().width;
      ev.preventDefault();
      ev.stopPropagation();
    };

    const onMove = (ev) => {
      if (!resizing) return;
      const dx = getX(ev) - startX;
      // Drag-from-bottom-right widens when going RIGHT but the panel is
      // anchored at right:5px, so increasing width pushes left. Compensate
      // by inverting dx so dragging right grows the panel.
      const newW = Math.max(280, Math.min(720, startW - dx));
      hostEl.style.setProperty('width', `${newW}px`, 'important');
      ev.preventDefault();
    };

    const onUp = () => {
      if (!resizing) return;
      resizing = false;
      resizeEl.classList.remove('active');
      try {
        if (typeof GM_setValue !== 'undefined') {
          const finalW = Math.round(hostEl.getBoundingClientRect().width);
          GM_setValue(`${P}panelW`, String(finalW));
        }
      } catch (_e) { /* ignore */ }
    };

    resizeEl.addEventListener('mousedown', onDown);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    resizeEl.addEventListener('touchstart', onDown, { passive: false });
    document.addEventListener('touchmove', onMove, { passive: false });
    document.addEventListener('touchend', onUp);
  }

  // Iter 141 — Left / Right side resize handles. The panel is anchored at
  // right:5px so we resize width AND also nudge `left`/`right` so the
  // opposite edge stays put visually.
  const _bindSideResize = (id, side) => {
    const el = q(id);
    if (!el || !hostEl) return;
    let resizing = false, startX = 0, startW = 0, startRight = 0, startLeft = 0;
    const getX = (ev) => (ev.touches && ev.touches[0]) ? ev.touches[0].clientX : ev.clientX;
    const onDown = (ev) => {
      resizing = true;
      el.classList.add('active');
      startX = getX(ev);
      const r = hostEl.getBoundingClientRect();
      startW = r.width;
      startRight = window.innerWidth - r.right;
      startLeft = r.left;
      ev.preventDefault();
      ev.stopPropagation();
    };
    const onMove = (ev) => {
      if (!resizing) return;
      const dx = getX(ev) - startX;
      let newW;
      if (side === 'right') {
        newW = Math.max(240, Math.min(720, startW + dx));
        hostEl.style.setProperty('width', `${newW}px`, 'important');
      } else {
        newW = Math.max(240, Math.min(720, startW - dx));
        hostEl.style.setProperty('width', `${newW}px`, 'important');
        // Keep the RIGHT edge visually stable when dragging the LEFT handle
        hostEl.style.setProperty('right', `${startRight}px`, 'important');
        hostEl.style.setProperty('left', 'auto', 'important');
      }
      ev.preventDefault();
    };
    const onUp = () => {
      if (!resizing) return;
      resizing = false;
      el.classList.remove('active');
      try {
        if (typeof GM_setValue !== 'undefined') {
          GM_setValue(`${P}panelW`, String(Math.round(hostEl.getBoundingClientRect().width)));
        }
      } catch (_e) { /* ignore */ }
    };
    el.addEventListener('mousedown', onDown);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    el.addEventListener('touchstart', onDown, { passive: false });
    document.addEventListener('touchmove', onMove, { passive: false });
    document.addEventListener('touchend', onUp);
  };
  _bindSideResize('resizeL', 'left');
  _bindSideResize('resizeR', 'right');

  // Scan
  const scanBtn = q('scan');
  if (scanBtn) {
    scanBtn.addEventListener('click', () => {
      const isActive = scanBtn.classList.contains('active');
      scanBtn.classList.toggle('active');
      setState('scanEnabled', !isActive);
      callbacks.onScanToggle?.(!isActive);
    });
  }

  // Auto
  const autoBtn = q('auto');
  if (autoBtn) {
    autoBtn.addEventListener('click', () => {
      const isActive = autoBtn.classList.contains('active');
      autoBtn.classList.toggle('active');
      setState('autoTradeEnabled', !isActive);
      callbacks.onAutoToggle?.(!isActive);
    });
  }

  q('go')?.addEventListener('click', () => callbacks.onGo?.());
  q('inv')?.addEventListener('click', () => callbacks.onInvertToggle?.());
  q('win')?.addEventListener('click', () => callbacks.onWin?.());
  q('loss')?.addEventListener('click', () => callbacks.onLoss?.());

  // RESET STATS — wipe W/L counters, streak, P/L (v8.45.0)
  q('statsreset')?.addEventListener('click', (e) => {
    e.stopPropagation();
    const ok = window.confirm(
      'Reset stats?\n\n' +
      'This clears W/L counters, win rate, streak, and P/L.\n' +
      'It does NOT affect bot toggles or saved settings.'
    );
    if (!ok) return;
    callbacks.onResetStats?.();
  });

  // CYCLE toggle
  const cycleBtn = q('cycle');
  if (cycleBtn) {
    cycleBtn.addEventListener('click', () => {
      const isActive = cycleBtn.classList.contains('active');
      cycleBtn.classList.toggle('active');
      callbacks.onCycleToggle?.(!isActive);
    });
  }

  // Iter 98 — Favorites-cycle Teach button
  const teachBtn = q('teachFav');
  if (teachBtn) {
    teachBtn.addEventListener('click', () => {
      callbacks.onTeachFavorites?.();
    });
  }
  const clearFavBtn = q('clearFav');
  if (clearFavBtn) {
    clearFavBtn.addEventListener('click', () => {
      callbacks.onClearTaughtFavorites?.();
      const statusEl = q('favStatusText');
      if (statusEl) statusEl.textContent = 'not taught yet';
    });
  }
  // Iter 98 — Cycle interval slider (5-120s)
  const cycleIntSlider = q('cycleInt');
  const cycleIntV = q('cycleIntV');
  if (cycleIntSlider) {
    cycleIntSlider.addEventListener('input', (e) => {
      const secs = parseInt(e.target.value, 10);
      if (cycleIntV) cycleIntV.textContent = `${secs}s`;
      callbacks.onCycleIntervalChange?.(secs * 1000);
    });
  }

  // Iter 99 — Chart-type teach buttons
  const teachChartBtn = q('teachChart');
  if (teachChartBtn) {
    teachChartBtn.addEventListener('click', () => {
      callbacks.onTeachChartType?.();
    });
  }
  const clearChartBtn = q('clearChart');
  if (clearChartBtn) {
    clearChartBtn.addEventListener('click', () => {
      callbacks.onClearTaughtChartType?.();
      const statusEl = q('chartStatusText');
      if (statusEl) statusEl.textContent = 'not taught yet';
    });
  }

  // APP signal poller toggle
  const appBtn = q('app');
  if (appBtn) {
    appBtn.addEventListener('click', () => {
      const isActive = appBtn.classList.contains('active');
      appBtn.classList.toggle('active');
      callbacks.onAppSignalToggle?.(!isActive);
    });
  }

  // Iter 110 — Master Auto-Trade toggle: header pill + big Trade-tab button
  // both flip SCAN + AUTO + APP + CYCLE together. Any of the four already-ON
  // makes the master pill appear active. Tap it and the world lights up.
  const masterBtn = q('master');
  const masterBig = q('masterBig');
  const masterLbl = q('masterlbl');
  const masterBigLbl = q('masterBigLbl');
  const masterBigSub = q('masterBigSub');

  const _allEnabled = () => {
    const scanOn = q('scan')?.classList.contains('active');
    const autoOn = q('auto')?.classList.contains('active');
    const appOn  = q('app')?.classList.contains('active');
    const cycleOn = q('cycle')?.classList.contains('active');
    return { scanOn, autoOn, appOn, cycleOn,
             anyOn: scanOn || autoOn || appOn || cycleOn,
             allOn: scanOn && autoOn && appOn && cycleOn };
  };

  const renderMaster = () => {
    const s = _allEnabled();
    const on = s.anyOn;
    if (masterBtn) {
      masterBtn.classList.toggle('active', on);
      if (masterLbl) masterLbl.textContent = on ? 'LIVE' : 'OFF';
    }
    if (masterBig) {
      masterBig.classList.toggle('active', on);
      if (masterBigLbl) masterBigLbl.textContent = on
        ? (s.allOn ? '🟢 ALL SYSTEMS LIVE — TAP TO STOP' : '⚠ PARTIAL — TAP TO GO FULL')
        : '⏻ TAP TO GO LIVE';
      if (masterBigSub) {
        const parts = [
          `SCAN ${s.scanOn ? '●' : '○'}`,
          `AUTO ${s.autoOn ? '●' : '○'}`,
          `APP ${s.appOn ? '●' : '○'}`,
          `CYCLE ${s.cycleOn ? '●' : '○'}`,
        ];
        masterBigSub.textContent = parts.join(' · ') +
          (on ? '' : ' — tap to enable all');
      }
    }
  };

  const handleMasterTap = () => {
    const s = _allEnabled();
    // If ANY of the four is on → turn ALL off.
    // If ALL four are off → turn ALL on.
    // If some are on but not all → escalate to ALL on (finish the enable).
    const target = !s.anyOn ? true : (s.allOn ? false : true);
    // Sync each toggle button visually + fire its callback so the app-state
    // (state.scanEnabled etc.) stays in lock-step with the UI.
    const setBtn = (id, on, cb) => {
      const btn = q(id);
      if (!btn) return;
      const isOn = btn.classList.contains('active');
      if (isOn === on) return;
      btn.classList.toggle('active', on);
      cb?.(on);
    };
    setBtn('scan',  target, callbacks.onScanToggle);
    setBtn('auto',  target, callbacks.onAutoToggle);
    setBtn('app',   target, callbacks.onAppSignalToggle);
    setBtn('cycle', target, callbacks.onCycleToggle);
    renderMaster();
    callbacks.onMasterToggle?.(target);

    // Iter 150 — On start-of-session, pull Risk Guard config from the
    // backend and push per-trade amount + confidence tiers into the
    // trading engine. Same rules the user set on the web-app Risk Guard
    // page — no manual re-config in the TM panel.
    if (target === true) {
      callbacks.onSessionStart?.();
    }
  };

  if (masterBtn) masterBtn.addEventListener('click', handleMasterTap);
  if (masterBig) masterBig.addEventListener('click', handleMasterTap);

  // Auto-sync the master pill whenever ANY of the 4 sub-toggles changes,
  // so if a user taps SCAN individually the master pill reflects it too.
  ['scan', 'auto', 'app', 'cycle'].forEach((id) => {
    const b = q(id);
    if (b) b.addEventListener('click', () => setTimeout(renderMaster, 0));
  });
  // Initial paint
  setTimeout(renderMaster, 50);

  // Auto-invert toggle
  const ainvBtn = q('ainv');
  if (ainvBtn) {
    ainvBtn.addEventListener('click', () => {
      const isActive = ainvBtn.classList.contains('active');
      ainvBtn.classList.toggle('active');
      callbacks.onAutoInvertToggle?.(!isActive);
    });
  }

  // 21s Reversal toggle (now fires at 51s-left)
  const r21sBtn = q('r21s');
  if (r21sBtn) {
    r21sBtn.addEventListener('click', () => {
      const isActive = r21sBtn.classList.contains('active');
      r21sBtn.classList.toggle('active');
      callbacks.on21sReversalToggle?.(!isActive);
    });
  }

  // Timing slider — adjusts which second of the 1m candle triggers the fire
  const timingSlider = q('timing');
  const timingValue = q('timingv');
  if (timingSlider) {
    const renderTiming = (v) => {
      if (timingValue) timingValue.textContent = `${v}s left`;
    };
    renderTiming(timingSlider.value);
    timingSlider.addEventListener('input', () => {
      const v = parseInt(timingSlider.value, 10);
      renderTiming(v);
      callbacks.on51sTimingChange?.(v);
    });
  }

  // Iter 117 — Multi-second SNS chip picker (max 3 targets)
  const snsMultiChipsEl = q('snsMultiChips');
  const snsMultiSummaryEl = q('snsMultiSummary');
  const snsMultiClearBtn = q('snsMultiClear');
  const snsMultiState = { targets: [] };
  const renderSnsMulti = () => {
    if (!snsMultiChipsEl) return;
    // Popular seconds: every 2s from 5 to 55 (26 chips) — fits mobile.
    const values = [];
    for (let v = 5; v <= 55; v += 2) values.push(v);
    snsMultiChipsEl.innerHTML = values.map((v) => {
      const active = snsMultiState.targets.includes(v);
      const bg = active ? '#0891b2' : 'rgba(255,255,255,0.03)';
      const brd = active ? '#22d3ee' : '#334155';
      const clr = active ? '#e0f2fe' : '#94a3b8';
      const fw = active ? '700' : '500';
      return `<button type="button" data-sns-sec="${v}" data-testid="sns-multi-chip-${v}" style="background:${bg};border:1px solid ${brd};color:${clr};font-weight:${fw};padding:2px 6px;border-radius:4px;font-size:10px;cursor:pointer;min-width:26px;">${v}s</button>`;
    }).join('');
    if (snsMultiSummaryEl) {
      snsMultiSummaryEl.textContent = snsMultiState.targets.length === 0
        ? 'Using slider (single target)'
        : `Fires at ${snsMultiState.targets.map(v => ':' + String(v).padStart(2, '0')).join(' + ')}`;
    }
  };
  if (snsMultiChipsEl) {
    renderSnsMulti();
    snsMultiChipsEl.addEventListener('click', (e) => {
      const btn = e.target && e.target.closest('button[data-sns-sec]');
      if (!btn) return;
      const v = parseInt(btn.getAttribute('data-sns-sec'), 10);
      if (!Number.isFinite(v)) return;
      const idx = snsMultiState.targets.indexOf(v);
      if (idx >= 0) {
        snsMultiState.targets.splice(idx, 1);
      } else {
        if (snsMultiState.targets.length >= 3) {
          snsMultiState.targets.shift(); // drop oldest
        }
        snsMultiState.targets.push(v);
      }
      renderSnsMulti();
      callbacks.onSnsMultiSecondsChange?.([...snsMultiState.targets]);
    });
  }
  if (snsMultiClearBtn) {
    snsMultiClearBtn.addEventListener('click', () => {
      snsMultiState.targets = [];
      renderSnsMulti();
      callbacks.onSnsMultiSecondsChange?.([]);
    });
  }
  // expose for restore-from-persisted-state
  if (typeof window !== 'undefined') {
    window.__snsSetMultiTargets = (arr) => {
      snsMultiState.targets = Array.isArray(arr)
        ? arr.map(v => parseInt(v, 10)).filter(v => Number.isFinite(v) && v >= 1 && v <= 59).slice(0, 3)
        : [];
      renderSnsMulti();
    };
  }

  // Iter 107 — SNS Direction Mode segmented buttons
  const snsAgainstBtn = q('snsDirAgainst');
  const snsWithBtn = q('snsDirWith');
  const setSnsDirActive = (withCandle) => {
    if (snsAgainstBtn) snsAgainstBtn.classList.toggle('active', !withCandle);
    if (snsWithBtn) snsWithBtn.classList.toggle('active', !!withCandle);
  };
  if (snsAgainstBtn) {
    snsAgainstBtn.addEventListener('click', () => {
      setSnsDirActive(false);
      callbacks.onSnsDirectionModeChange?.('against');
    });
  }
  if (snsWithBtn) {
    snsWithBtn.addEventListener('click', () => {
      setSnsDirActive(true);
      callbacks.onSnsDirectionModeChange?.('with');
    });
  }

  // Iter 107 — Manual Chart Type dropdown (Config tab)
  const chartTypeSel = q('chartTypeSel');
  if (chartTypeSel) {
    chartTypeSel.addEventListener('change', () => {
      callbacks.onChartTypeManualChange?.(chartTypeSel.value);
    });
  }

  // Iter 107 — Auto-Invert Threshold slider (Config tab)
  const invThresh = q('invThresh');
  const invThreshVal = q('invThreshVal');
  const invThreshS = q('invThreshS');
  const renderInvThresh = (v) => {
    if (invThreshVal) invThreshVal.textContent = String(v);
    if (invThreshS) invThreshS.textContent = v > 1 ? 'es' : '';
  };
  if (invThresh) {
    renderInvThresh(parseInt(invThresh.value, 10));
    invThresh.addEventListener('input', () => {
      const v = parseInt(invThresh.value, 10);
      renderInvThresh(v);
      callbacks.onInvertThresholdChange?.(v);
    });
  }

  // Iter 113 — Auto-Invert diagnostic + self-test buttons
  const invDiagBtn = q('invDiag');
  const invDiagOut = q('invDiagOut');
  const invSelfTestBtn = q('invSelfTest');
  const renderDiag = (d) => {
    if (!invDiagOut) return;
    if (!d) { invDiagOut.textContent = ''; return; }
    if (d.ok || d.wouldFire) {
      invDiagOut.style.color = '#4ade80';
      invDiagOut.textContent = `✓ Ready · streak ${d.lossStreak}/${d.threshold} · isInverted=${d.isInverted}`;
    } else {
      invDiagOut.style.color = '#f87171';
      invDiagOut.textContent = `⚠ ${d.blockers.join(' · ')} · streak=${d.currentStreak} · isInverted=${d.isInverted}`;
    }
  };
  if (invDiagBtn) {
    invDiagBtn.addEventListener('click', () => {
      const d = callbacks.onAutoInvertDiagnose?.();
      renderDiag(d);
    });
  }
  if (invSelfTestBtn) {
    invSelfTestBtn.addEventListener('click', () => {
      const r = callbacks.onAutoInvertSelfTest?.();
      if (invDiagOut) {
        if (r?.fired) {
          invDiagOut.style.color = '#4ade80';
          invDiagOut.textContent = `✓ Self-test PASSED — flipped after ${r.threshold} simulated loss${r.threshold > 1 ? 'es' : ''}`;
        } else {
          invDiagOut.style.color = '#f87171';
          invDiagOut.textContent = `✗ Self-test FAILED — engine didn't flip. Check A-INV toggle + manualOverride.`;
        }
      }
    });
  }

  // Iter 108 — Latency Abstain threshold slider (Config tab)
  const latAbs = q('latAbsThresh');
  const latAbsVal = q('latAbsVal');
  const latAbsOff = q('latAbsOff');
  const renderLatAbs = (v) => {
    if (latAbsVal) latAbsVal.textContent = String(v);
    if (latAbsOff) latAbsOff.style.display = v === 0 ? 'inline' : 'none';
  };
  if (latAbs) {
    renderLatAbs(parseInt(latAbs.value, 10));
    latAbs.addEventListener('input', () => {
      const v = parseInt(latAbs.value, 10);
      renderLatAbs(v);
      callbacks.onLatencyAbstainThresholdChange?.(v);
    });
  }

  // Iter 109 — Elite Score Gate threshold slider + enforce-direction toggle
  const eliteG = q('eliteGateThresh');
  const eliteGVal = q('eliteGateVal');
  const eliteGOff = q('eliteGateOff');
  const eliteGEnf = q('eliteGateEnforceDir');
  const renderEliteG = (v) => {
    if (eliteGVal) eliteGVal.textContent = String(v);
    if (eliteGOff) eliteGOff.style.display = v === 0 ? 'inline' : 'none';
  };
  if (eliteG) {
    renderEliteG(parseInt(eliteG.value, 10));
    eliteG.addEventListener('input', () => {
      const v = parseInt(eliteG.value, 10);
      renderEliteG(v);
      callbacks.onEliteGateThresholdChange?.(v);
    });
  }
  if (eliteGEnf) {
    eliteGEnf.addEventListener('change', () => {
      callbacks.onEliteGateEnforceDirectionChange?.(!!eliteGEnf.checked);
    });
  }

  // Strategy selector
  const stratSelect = q('strat');
  if (stratSelect) {
    stratSelect.addEventListener('change', (e) => {
      callbacks.onStrategyChange?.(e.target.value);
    });
  }

  // Iter 96 — Strategy timeframe selector (drives which TF's strategies appear)
  const stratTfSelect = q('stratTf');
  if (stratTfSelect) {
    stratTfSelect.addEventListener('change', (e) => {
      callbacks.onStrategyTfChange?.(e.target.value);
    });
  }

  const amtInput = q('amt');
  if (amtInput) {
    amtInput.addEventListener('change', (e) => {
      callbacks.onAmountChange?.(parseFloat(e.target.value) || 1);
    });
  }

  q('logtog')?.addEventListener('click', () => {
    const logEl = q('log');
    const arrow = q('arrow');
    if (logEl && arrow) {
      const expanded = logEl.style.display !== 'none';
      logEl.style.display = expanded ? 'none' : 'block';
      arrow.innerHTML = expanded ? '&#9654;' : '&#9660;';
    }
  });

  makeDraggable();
}

export function updateStatsDisplay() {
  const wlEl = q('wl');
  const rateEl = q('rate');
  const streakEl = q('streak');
  const profitEl = q('profit');
  const stepEl = q('step');

  if (wlEl) wlEl.textContent = `${state.stats.wins}/${state.stats.losses}`;

  if (rateEl) {
    const total = state.stats.wins + state.stats.losses;
    const rate = total > 0 ? (state.stats.wins / total * 100).toFixed(1) : 0;
    rateEl.textContent = `${rate}%`;
    rateEl.style.setProperty('color', parseFloat(rate) >= 55 ? '#3fb950' : parseFloat(rate) < 45 ? '#f85149' : '#e6edf3', 'important');
  }

  if (streakEl) {
    const s = state.stats.currentStreak;
    streakEl.textContent = s > 0 ? `+${s}` : String(s);
    streakEl.style.setProperty('color', s > 0 ? '#3fb950' : s < 0 ? '#f85149' : '#e6edf3', 'important');
  }

  if (profitEl) {
    const p = state.moneyManagement.totalProfit;
    profitEl.textContent = `$${p.toFixed(0)}`;
    profitEl.style.setProperty('color', p > 0 ? '#3fb950' : p < 0 ? '#f85149' : '#e6edf3', 'important');
  }

  if (stepEl) stepEl.textContent = String(state.moneyManagement.currentStep);

  // Iter 151b — Win/Loss detection health indicator. Turns visible when
  // any trade has timed out without a matched deal row. Clicking jumps
  // to the Forex tab so the user can teach WIN/LOSS row markers.
  try {
    const el = q('detectHealth');
    if (el) {
      const st = tradeResultWatcher.getStats();
      if (st && st.enabled && st.timeoutCount > 0) {
        el.style.display = 'block';
        const msg = q('detectHealthMsg');
        if (msg) {
          msg.textContent = `${st.timeoutCount} trade${st.timeoutCount === 1 ? '' : 's'} timed out. Click here to teach the WIN/LOSS row markers.`;
        }
        if (!el._eb_bound) {
          el._eb_bound = true;
          el.addEventListener('click', () => {
            try {
              const forexTab = document.querySelector(`.${P}tabbtn[data-tab="forex"]`);
              if (forexTab) forexTab.click();
            } catch (_e) { /* ignore */ }
          });
        }
      } else {
        el.style.display = 'none';
      }
    }
  } catch (_e) { /* never let the health indicator crash stats display */ }
}

export function updateInvertDisplay(isInverted, reason) {
  const btn = q('inv');
  const st = q('invst');

  if (btn) {
    if (isInverted) btn.classList.add('active');
    else btn.classList.remove('active');
    btn.textContent = isInverted ? 'INV ON' : 'INVERT';
  }

  if (st) {
    st.textContent = isInverted ? `Invert: ${reason || 'Inverted'}` : 'Invert: Normal';
    if (isInverted) st.classList.add('on');
    else st.classList.remove('on');
  }
}

export function update21sReversalDisplay(enabled, stats = null) {
  const btn = q('r21s');
  const st = q('r21st');
  if (btn) {
    if (enabled) btn.classList.add('active');
    else btn.classList.remove('active');
  }
  if (st) {
    if (!enabled) {
      st.textContent = 'SNS: Off';
      st.classList.remove('on');
    } else if (stats) {
      st.textContent = `SNS: On ${stats.wins}/${stats.losses} (${stats.winRate}%)`;
      st.classList.add('on');
    } else {
      st.textContent = 'SNS: On';
      st.classList.add('on');
    }
  }
}

/**
 * v8.51.0 — update the live candle-timer readout row (between the status
 * strip and the main button row). Shows the PO countdown, the configured
 * trigger second, and the current armed/firing/off state.
 *
 * @param {Object} info - {poSecondsLeft, wallSecondsLeft, triggerSec, enabled, firedThisCandle}
 */
export function updateLiveCountdown(info) {
  const valEl = q('timeval');
  const trgEl = q('timetrg');
  const statusEl = q('timestatus');
  const tfEl = q('timetfval');
  if (!valEl) return;

  if (!info || !info.enabled) {
    valEl.textContent = '—';
    valEl.classList.remove('hit', 'stale');
    valEl.classList.add('offline');
    if (trgEl) trgEl.textContent = '—';
    if (tfEl) tfEl.textContent = info?.timeframeLabel || 'M1';
    if (statusEl) {
      statusEl.textContent = 'off';
      statusEl.classList.remove('armed', 'firing', 'cooldown');
    }
    return;
  }

  // Prefer PO countdown, fall back to wall-clock derived seconds-left
  const src = info.poSecondsLeft != null ? info.poSecondsLeft : info.wallSecondsLeft;
  const hasPo = info.poSecondsLeft != null;

  valEl.classList.remove('offline', 'hit', 'stale');

  // Format: for >60s show "m:ss", otherwise "Ns"
  const fmt = (s) => {
    if (s >= 60) {
      const m = Math.floor(s / 60);
      const sec = s % 60;
      return `${m}:${String(sec).padStart(2, '0')}`;
    }
    return `${s}s`;
  };

  if (!hasPo) {
    valEl.classList.add('stale');
    valEl.textContent = `${fmt(src)}*`;   // asterisk = wall-clock fallback
  } else {
    // Flash green inside the trigger window (±2s of target)
    if (Math.abs(src - info.triggerSec) <= 2) {
      valEl.classList.add('hit');
    }
    valEl.textContent = fmt(src);
  }

  if (trgEl) trgEl.textContent = fmt(info.triggerSec);
  if (tfEl) tfEl.textContent = info.timeframeLabel || 'M1';

  if (statusEl) {
    statusEl.classList.remove('armed', 'firing', 'cooldown');
    if (info.firedThisCandle) {
      statusEl.textContent = 'cooldown';
      statusEl.classList.add('cooldown');
    } else if (Math.abs(src - info.triggerSec) <= 2) {
      statusEl.textContent = 'firing';
      statusEl.classList.add('firing');
    } else {
      statusEl.textContent = 'armed';
      statusEl.classList.add('armed');
    }
  }
}

/**
 * Programmatic setter for the 51S timing slider so restore-on-reload
 * can paint the saved value back onto the UI.
 * @param {number} secondsLeft 5..55
 */
export function set51sTimingSlider(secondsLeft) {
  const slider = q('timing');
  const valueEl = q('timingv');
  if (!slider) return;
  const v = Math.max(5, Math.min(55, parseInt(secondsLeft, 10) || 49));
  slider.value = String(v);
  if (valueEl) valueEl.textContent = `${v}s left`;
}

/**
 * Update the active-asset indicator banner. Caller passes the symbol
 * currently in focus (post normalisation) and an optional rotation count.
 * @param {string|null} symbol e.g. "EURUSD_OTC"
 * @param {number} [count]   total rotations / fires this session
 */
export function updateActiveAsset(symbol, count = null) {
  const valEl = q('asset');
  const cntEl = q('assetcnt');
  if (valEl) {
    valEl.textContent = symbol || '—';
    valEl.style.color = symbol ? '#f0fdf4' : '#6b7280';
  }
  if (cntEl && count !== null && count !== undefined) {
    cntEl.textContent = `#${count}`;
  }
}

/**
 * Update the live signal-quality preview row (under the GO button).
 * Polled every 3s by index.js — gives the user a "should I press GO?" cue.
 *
 * @param {Object|null} info - {direction, confidence, quality, agreeing,
 *                              mlCount, evaluated, votes, latencyMs,
 *                              fresh, ageSec, error}
 *                            or null on error
 */
export function setSignalPreview(info) {
  const row = q('qualrow');
  const fill = q('qualfill');
  const valEl = q('qualval');
  const ageEl = q('qualage');
  const subEl = q('qualsub');
  const mlEl = q('qualml');
  const stratsEl = q('qualstrats');
  const votesEl = q('qualvotes');
  const latEl = q('quallat');
  if (!row || !valEl) return;

  // Reset classes
  row.classList.remove('high', 'medium', 'low', 'fresh');
  if (subEl) subEl.classList.remove('high', 'medium', 'low');

  if (!info || !info.direction) {
    valEl.textContent = info?.error || '—';
    if (fill) fill.style.width = '0%';
    if (ageEl) ageEl.textContent = '';
    if (mlEl) mlEl.style.display = 'none';
    if (stratsEl) stratsEl.style.display = 'none';
    if (votesEl) votesEl.style.display = 'none';
    if (latEl) latEl.textContent = '';
    return;
  }

  const conf = Number(info.confidence) || 0;
  const quality = (info.quality || 'LOW').toUpperCase();
  const dir = (info.direction || '').toUpperCase();
  const dirArrow = dir === 'CALL' ? '▲' : (dir === 'PUT' ? '▼' : '');
  const agreeing = info.agreeing != null ? ` · ${info.agreeing} strats` : '';

  // Map quality → CSS class
  if (quality === 'HIGH') { row.classList.add('high'); subEl?.classList.add('high'); }
  else if (quality === 'MEDIUM') { row.classList.add('medium'); subEl?.classList.add('medium'); }
  else { row.classList.add('low'); subEl?.classList.add('low'); }

  if (fill) {
    // Bar fill: 50% conf = 0% bar, 82% conf = 100% bar (52–82% realistic band)
    const pct = Math.max(0, Math.min(100, ((conf - 50) / 32) * 100));
    fill.style.width = `${pct}%`;
  }

  valEl.textContent = `${quality} ${dirArrow} ${dir} ${conf.toFixed(0)}%${agreeing}`;

  // v8.55.0: Abstain overlay — if the backend's confidence-threshold gate
  // marked this signal as abstain, override the row look so the user
  // instantly knows GO would refuse to fire.
  if (info.abstain) {
    row.classList.remove('high', 'medium', 'low');
    row.classList.add('low');
    valEl.textContent = `ABSTAIN · ${conf.toFixed(0)}% < ${info.abstainThreshold ?? '—'}%`;
  }

  // Age pip — green pulse for fresh, gold for stale, red for very old
  if (ageEl) {
    const age = Number(info.ageSec || 0);
    ageEl.classList.remove('stale', 'veryold');
    if (age <= 1) ageEl.textContent = 'now';
    else if (age <= 3) ageEl.textContent = `${age}s`;
    else if (age <= 6) { ageEl.textContent = `${age}s`; ageEl.classList.add('stale'); }
    else { ageEl.textContent = `${age}s`; ageEl.classList.add('veryold'); }
  }

  // Fresh-update pulse animation (re-trigger by removing/adding class)
  if (info.fresh) {
    // Force reflow to restart animation
    row.classList.remove('fresh');
    void row.offsetWidth;
    row.classList.add('fresh');
  }

  // Sub-row: ML model count, strategies evaluated, vote ratio
  if (mlEl) {
    if (info.mlCount && info.mlCount > 0) {
      mlEl.textContent = `${info.mlCount}ML✓`;
      mlEl.style.display = '';
    } else {
      mlEl.style.display = 'none';
    }
  }
  if (stratsEl) {
    if (info.evaluated && info.evaluated > 0) {
      stratsEl.textContent = `${info.agreeing || 0}/${info.evaluated}`;
      stratsEl.style.display = '';
    } else {
      stratsEl.style.display = 'none';
    }
  }
  if (votesEl) {
    const v = info.votes;
    if (v && (v.call != null || v.put != null)) {
      const c = Number(v.call || 0).toFixed(1);
      const p = Number(v.put || 0).toFixed(1);
      votesEl.textContent = `▲${c} ▼${p}`;
      votesEl.style.display = '';
    } else {
      votesEl.style.display = 'none';
    }
  }
  if (latEl) {
    if (info.latencyMs && info.latencyMs > 0) {
      latEl.textContent = `${info.latencyMs}ms`;
    } else {
      latEl.textContent = '';
    }
  }
  
  // Iter 56b — abstain source chip (which threshold tier resolved the gate)
  const abstainSrcEl = q('qualabstainsrc');
  if (abstainSrcEl) {
    abstainSrcEl.classList.remove('src-strategy', 'src-asset', 'src-default', 'src-latency');
    const src = (info.abstainSource || '').toLowerCase();
    const thr = info.abstainThreshold;
    if (src && thr != null) {
      const labels = {
        strategy: `STRAT@${thr}%`,
        asset:    `ASSET@${thr}%`,
        default:  `DFLT@${thr}%`,
        latency:  `LAT-STALE`,
      };
      abstainSrcEl.textContent = labels[src] || `${src.toUpperCase()}@${thr}%`;
      abstainSrcEl.classList.add(`src-${src}`);
      abstainSrcEl.style.display = '';
    } else {
      abstainSrcEl.style.display = 'none';
    }
  }
  
  // Iter 56b — server-side latency chip (% of timeframe budget consumed)
  const srvLatEl = q('qualsrvlat');
  if (srvLatEl) {
    srvLatEl.classList.remove('lat-good', 'lat-warn', 'lat-bad');
    const sm = Number(info.serverLatencyMs);
    const bm = Number(info.serverLatencyBudgetMs);
    if (sm > 0 && bm > 0) {
      const pct = (sm / bm) * 100;
      // Coloured bucket — keep in sync with the auto-abstain trigger (100% = stale)
      if (pct >= 100) srvLatEl.classList.add('lat-bad');
      else if (pct >= 60) srvLatEl.classList.add('lat-warn');
      else srvLatEl.classList.add('lat-good');
      srvLatEl.textContent = `srv ${sm.toFixed(0)}ms (${pct.toFixed(0)}%)`;
      srvLatEl.style.display = '';
    } else if (sm > 0) {
      srvLatEl.classList.add('lat-good');
      srvLatEl.textContent = `srv ${sm.toFixed(0)}ms`;
      srvLatEl.style.display = '';
    } else {
      srvLatEl.style.display = 'none';
    }
  }
}

/**
 * Refresh the top-of-panel status strip with the current toggle states.
 * Called by index.js after every toggle click + on a 1s heartbeat.
 *
 * @param {Object} flags - {scan, auto, ainv, r21s, cycle} booleans
 */
export function updateStatusStrip(flags = {}) {
  const map = {
    stripscan: !!flags.scan,
    stripauto: !!flags.auto,
    stripainv: !!flags.ainv,
    strip51s: !!flags.r21s,
    stripcycle: !!flags.cycle,
  };
  for (const [id, on] of Object.entries(map)) {
    const el = q(id);
    if (!el) continue;
    if (on) el.classList.add('on');
    else el.classList.remove('on');
  }
}

/**
 * Set a toggle button's active class programmatically (without triggering the click callback).
 * Used to restore persisted toggle states after page reload.
 */
export function setToggleActive(buttonId, active) {
  const btn = q(buttonId);
  if (!btn) return;
  if (active) btn.classList.add('active');
  else btn.classList.remove('active');
}

export function updateStatusDot(status) {
  const dot = q('dot');
  if (dot) dot.className = `${P}dot ${status}`;
}

/**
 * Make panel draggable — supports BOTH mouse and touch
 */
function makeDraggable() {
  const header = q('header');
  const host = document.getElementById(`${P}host`);
  const panel = q('panel');
  if (!header || !host) return;

  let dragging = false, startX, startY, origLeft, origTop;
  // Iter 141 — drag from ANY panel surface. Ignore anything the user is
  // interacting with (buttons, inputs, sliders, links, side-resize handles).
  const NO_DRAG = /^(BUTTON|INPUT|TEXTAREA|SELECT|A|LABEL|OPTION)$/;
  function shouldSkipDrag(target) {
    if (!target) return false;
    let el = target;
    while (el && el !== host) {
      if (el.classList && (
        el.classList.contains(`${P}sideresize`)
        || el.classList.contains(`${P}resize`)
        || el.classList.contains(`${P}btn`)
        || el.classList.contains(`${P}tabbtn`)
        || el.classList.contains(`${P}masterbtn`)
        || el.classList.contains(`${P}masterbig`)
        || el.classList.contains(`${P}minbtn`)
      )) return true;
      if (NO_DRAG.test(el.tagName || '')) return true;
      el = el.parentElement;
    }
    return false;
  }

  function getPos(e) {
    if (e.touches && e.touches.length > 0) {
      return { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }
    return { x: e.clientX, y: e.clientY };
  }

  function onStart(e) {
    if (shouldSkipDrag(e.target)) return;
    dragging = true;
    const pos = getPos(e);
    const rect = host.getBoundingClientRect();
    startX = pos.x;
    startY = pos.y;
    origLeft = rect.left;
    origTop = rect.top;
    e.preventDefault();
    e.stopPropagation();
  }

  function onMove(e) {
    if (!dragging) return;
    const pos = getPos(e);
    const dx = pos.x - startX;
    const dy = pos.y - startY;
    const newLeft = Math.max(0, Math.min(window.innerWidth - 50, origLeft + dx));
    const newTop = Math.max(0, Math.min(window.innerHeight - 50, origTop + dy));
    host.style.setProperty('left', newLeft + 'px', 'important');
    host.style.setProperty('top', newTop + 'px', 'important');
    host.style.setProperty('right', 'auto', 'important');
    e.preventDefault();
  }

  function onEnd() {
    dragging = false;
  }

  // Mouse events — attach to the whole PANEL so drag works from anywhere
  const dragSurface = panel || header;
  dragSurface.addEventListener('mousedown', onStart);
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onEnd);

  // Touch events
  dragSurface.addEventListener('touchstart', onStart, { passive: false });
  document.addEventListener('touchmove', onMove, { passive: false });
  document.addEventListener('touchend', onEnd);
}

export function cleanupPanel() {
  if (watchdogInterval) {
    clearInterval(watchdogInterval);
    watchdogInterval = null;
  }
}

/**
 * Populate strategy dropdown from API data
 * @param {Array} strategies - [{id, name, win_rate?}]
 * @param {string} selectedId - Currently active strategy ID
 */
export function populateStrategies(strategies, selectedId) {
  const sel = q('strat');
  if (!sel) return;

  sel.innerHTML = '';

  // Add "All Strategies" default option
  const defOpt = document.createElement('option');
  defOpt.value = 'default';
  defOpt.textContent = 'All Strategies';
  sel.appendChild(defOpt);

  if (strategies && strategies.length > 0) {
    for (const s of strategies) {
      if (s.id === 'default') continue;
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = s.win_rate ? `${s.name} (${s.win_rate})` : s.name;
      sel.appendChild(opt);
    }
  }

  if (selectedId) {
    sel.value = selectedId;
  }
}


/**
 * Iter 96 — Get/set the selected strategy timeframe in the TF dropdown.
 * Reads/writes the DOM directly so callers don't have to know the ID convention.
 */
export function setStrategyTf(tf) {
  const sel = q('stratTf');
  if (sel && tf) sel.value = tf;
}

export function getStrategyTf() {
  const sel = q('stratTf');
  return sel ? sel.value : '5s';
}

/**
 * Iter 104 — Reflect the persisted SNS direction mode ('with' | 'against')
 * on the segmented button so state survives page reloads.
 */
export function setSnsDirectionMode(mode) {
  const withCandle = mode === 'with';
  const againstBtn = document.getElementById(`${P}snsDirAgainst`);
  const withBtn = document.getElementById(`${P}snsDirWith`);
  if (againstBtn) againstBtn.classList.toggle('active', !withCandle);
  if (withBtn) withBtn.classList.toggle('active', withCandle);
}

/**
 * Iter 107 — Reflect the persisted manual chart-type override so state
 * survives page reloads.
 */
export function setChartTypeManual(value) {
  const sel = document.getElementById(`${P}chartTypeSel`);
  if (sel && value) sel.value = value;
}

/**
 * Iter 107 — Reflect the persisted auto-invert threshold slider position.
 */
export function setInvertThreshold(v) {
  const sl = document.getElementById(`${P}invThresh`);
  const val = document.getElementById(`${P}invThreshVal`);
  const suffix = document.getElementById(`${P}invThreshS`);
  const n = Math.max(1, Math.min(5, parseInt(v, 10) || 1));
  if (sl) sl.value = String(n);
  if (val) val.textContent = String(n);
  if (suffix) suffix.textContent = n > 1 ? 'es' : '';
}

/**
 * Iter 108 — Reflect the persisted latency-abstain threshold value on the
 * slider so state survives page reloads.
 */
export function setLatencyAbstainThreshold(v) {
  const sl = document.getElementById(`${P}latAbsThresh`);
  const val = document.getElementById(`${P}latAbsVal`);
  const off = document.getElementById(`${P}latAbsOff`);
  const n = Math.max(0, Math.min(1000, parseInt(v, 10) || 0));
  if (sl) sl.value = String(n);
  if (val) val.textContent = String(n);
  if (off) off.style.display = n === 0 ? 'inline' : 'none';
}

/**
 * Iter 109 — Reflect the persisted Elite-gate threshold + enforce-direction
 * flag on the panel so state survives page reloads.
 */
export function setEliteGateThreshold(v) {
  const sl = document.getElementById(`${P}eliteGateThresh`);
  const val = document.getElementById(`${P}eliteGateVal`);
  const off = document.getElementById(`${P}eliteGateOff`);
  const n = Math.max(0, Math.min(100, parseInt(v, 10) || 0));
  if (sl) sl.value = String(n);
  if (val) val.textContent = String(n);
  if (off) off.style.display = n === 0 ? 'inline' : 'none';
}

export function setEliteGateEnforceDirection(v) {
  const cb = document.getElementById(`${P}eliteGateEnforceDir`);
  if (cb) cb.checked = !!v;
}

/**
 * Iter 109 — Update the Elite-gate status chip based on the last decision.
 * `event` is the last object returned by `eliteScoreGate.check(...)`:
 *   { asset, allow, score, direction, threshold, reason }
 */
export function setEliteGateState(event) {
  const chip = document.getElementById(`${P}eliteGateState`);
  if (!chip) return;
  if (!event) {
    chip.style.background = 'rgba(100,116,139,0.15)';
    chip.style.color = '#94a3b8';
    chip.style.borderColor = 'rgba(100,116,139,0.3)';
    chip.textContent = '○ Gate disabled';
    return;
  }
  if (event.reason === 'gate_off' || event.score == null) {
    chip.style.background = 'rgba(100,116,139,0.15)';
    chip.style.color = '#94a3b8';
    chip.style.borderColor = 'rgba(100,116,139,0.3)';
    chip.textContent = '○ Gate disabled';
    return;
  }
  const s = Number(event.score || 0).toFixed(1);
  if (event.allow) {
    chip.style.background = 'rgba(74,222,128,0.1)';
    chip.style.color = '#4ade80';
    chip.style.borderColor = 'rgba(74,222,128,0.3)';
    chip.textContent = `✓ ALLOW ${event.asset || ''} · Elite ${s} · ${event.direction || 'NEUTRAL'}`;
  } else {
    chip.style.background = 'rgba(248,113,113,0.14)';
    chip.style.color = '#f87171';
    chip.style.borderColor = 'rgba(248,113,113,0.4)';
    chip.textContent = `⛔ BLOCK · ${event.reason || 'below threshold'}`;
  }
}

/**
 * Iter 108 — Update the latency-abstain state chip.
 *   'healthy'  → green ✓ TRADING — latency healthy
 *   'paused'   → red ⛔ PAUSED — latency exceeded
 *   'off'      → grey ○ DISABLED — abstain OFF
 */
export function setLatencyAbstainState(state, extra = '') {
  const chip = document.getElementById(`${P}latAbsState`);
  if (!chip) return;
  const map = {
    healthy: { bg: 'rgba(74,222,128,0.1)', color: '#4ade80', border: 'rgba(74,222,128,0.3)',
               txt: '✓ TRADING — latency healthy' },
    paused:  { bg: 'rgba(248,113,113,0.14)', color: '#f87171', border: 'rgba(248,113,113,0.4)',
               txt: '⛔ PAUSED — latency exceeded' },
    off:     { bg: 'rgba(100,116,139,0.12)', color: '#94a3b8', border: 'rgba(100,116,139,0.3)',
               txt: '○ DISABLED — abstain OFF' },
  };
  const c = map[state] || map.off;
  chip.style.background = c.bg;
  chip.style.color = c.color;
  chip.style.borderColor = c.border;
  chip.textContent = extra ? `${c.txt} · ${extra}` : c.txt;
}

/**
 * Iter 107 — Update the AI Analysis tab with a fresh signal-preview payload.
 * Called by `aiAnalysisPoller.js` every 3s.
 *
 * Payload shape (partial, all fields optional):
 *   {
 *     signal: { direction, confidence, symbol, strategy },
 *     votes:  [{ name, direction, confidence }, ...]  // sorted desc by conf
 *     indicators: { rsi, macd_hist, bb_pos, atr_percentile }
 *     microstructure: { kyle_lambda, kyle_illiq_bps,
 *                       gm_adverse_selection_pct, gm_alpha_informed }
 *     recent_trades: [{ time, asset, direction, result }, ...]
 *   }
 */
export function updateAITab(data) {
  if (!data || typeof data !== 'object') return;

  // Confidence gauge
  const fill = document.getElementById(`${P}aiConfFill`);
  const val  = document.getElementById(`${P}aiConfVal`);
  const dir  = document.getElementById(`${P}aiConfDir`);
  const arr  = document.getElementById(`${P}aiConfArrow`);
  const sig = data.signal || {};
  if (fill && sig.confidence != null) {
    const c = Math.max(0, Math.min(100, Number(sig.confidence) || 0));
    fill.style.width = `${c}%`;
    if (val) val.textContent = `${Math.round(c)}%`;
  }
  if (dir) {
    const d = String(sig.direction || '').toUpperCase();
    dir.textContent = d || '—';
    dir.classList.remove('CALL', 'PUT');
    if (d === 'CALL' || d === 'PUT') dir.classList.add(d);
  }
  if (arr) {
    const d = String(sig.direction || '').toUpperCase();
    arr.textContent = d === 'CALL' ? '▲' : d === 'PUT' ? '▼' : '';
  }

  // Model votes (top 3)
  const votesEl = document.getElementById(`${P}aiVotes`);
  if (votesEl) {
    const votes = Array.isArray(data.votes) ? data.votes.slice(0, 3) : [];
    if (votes.length === 0) {
      votesEl.innerHTML = `<div class="${P}aivotempty">no votes yet — waiting…</div>`;
    } else {
      votesEl.innerHTML = votes.map((v) => {
        const d = String(v.direction || '').toUpperCase();
        const dCls = (d === 'CALL' || d === 'PUT') ? d : '';
        const conf = v.confidence != null ? `${Math.round(v.confidence)}%` : '—';
        const name = String(v.name || 'unknown').slice(0, 26);
        return `<div class="${P}aivoterow ${dCls}">
          <span class="${P}aivotename">${name}</span>
          <span class="${P}aivotedir ${dCls}">${d || '—'}</span>
          <span class="${P}aivoteconf">${conf}</span>
        </div>`;
      }).join('');
    }
  }

  // Indicators
  const ind = data.indicators || {};
  const setInd = (id, v, fmt = (x) => x) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = (v == null || !isFinite(Number(v))) ? '—' : fmt(v);
  };
  setInd(`${P}aiIndRSI`,  ind.rsi,             (v) => Number(v).toFixed(1));
  setInd(`${P}aiIndMACD`, ind.macd_hist,       (v) => Number(v).toFixed(5));
  setInd(`${P}aiIndBB`,   ind.bb_pos,          (v) => `${(Number(v) * 100).toFixed(0)}%`);
  setInd(`${P}aiIndATR`,  ind.atr_percentile,  (v) => `${Math.round(Number(v) * 100)}%`);

  // Microstructure
  const ms = data.microstructure || {};
  setInd(`${P}aiKyleLambda`, ms.kyle_lambda,             (v) => Number(v).toFixed(4));
  setInd(`${P}aiGMAdv`,      ms.gm_adverse_selection_pct, (v) => `${Number(v).toFixed(1)}%`);
  setInd(`${P}aiGMInf`,      ms.gm_alpha_informed,        (v) => `${Math.round(Number(v) * 100)}%`);
  setInd(`${P}aiKyleBps`,    ms.kyle_illiq_bps,           (v) => `${Number(v).toFixed(1)} bps`);

  // Recent trades
  const recent = Array.isArray(data.recent_trades) ? data.recent_trades.slice(0, 5) : [];
  const recentEl = document.getElementById(`${P}aiRecentTrades`);
  if (recentEl) {
    if (recent.length === 0) {
      recentEl.innerHTML = `<div class="${P}aivotempty">no trades yet</div>`;
    } else {
      recentEl.innerHTML = recent.map((t) => {
        const d = String(t.direction || '').toUpperCase();
        const r = String(t.result || '').toUpperCase();
        const dCls = (d === 'CALL' || d === 'PUT') ? d : '';
        const rCls = (r === 'WIN' || r === 'LOSS') ? r : '';
        let time = '';
        try {
          const tt = t.time ? new Date(t.time) : null;
          if (tt && !isNaN(tt.getTime())) {
            const hh = String(tt.getHours()).padStart(2, '0');
            const mm = String(tt.getMinutes()).padStart(2, '0');
            const ss = String(tt.getSeconds()).padStart(2, '0');
            time = `${hh}:${mm}:${ss}`;
          }
        } catch (_e) { /* silent */ }
        const sym = String(t.asset || '').slice(0, 12);
        return `<div class="${P}airecentrow ${rCls}">
          <span class="${P}airecentdir ${dCls}">${d || '—'}</span>
          <span class="${P}airecentres ${rCls}">${r || '—'}</span>
          <span class="${P}airecentsym">${sym}</span>
          <span class="${P}airecenttime">${time}</span>
        </div>`;
      }).join('');
    }
  }
}

/**
 * Iter 103 — Network latency widget renderer.
 *
 * Called by the poller in `networkLatencyPoller.js` on every refresh with
 * the JSON payload from GET /api/latency/network. Renders:
 *   now / p50 / p99 / p99.9  latency values, plus a state chip
 *   (good/warn/bad) and a sample-count footer.
 *
 * Thresholds:
 *   good  : p99  < 120 ms
 *   warn  : 120 <= p99 < 300 ms
 *   bad   : p99 >= 300 ms  OR  failure_count > 0
 */
export function updateNetworkLatency(stats) {
  const nowEl  = document.getElementById(`${P}netlatnow`);
  const p50El  = document.getElementById(`${P}netlatp50`);
  const p99El  = document.getElementById(`${P}netlatp99`);
  const p999El = document.getElementById(`${P}netlatp999`);
  const stateEl = document.getElementById(`${P}netlatstate`);
  const statsEl = document.getElementById(`${P}netlatstats`);
  if (!nowEl || !stateEl) return;

  // Accept either the single-target payload (`{success, stats: {…}}`) or
  // the all-targets payload (`{success, stats: {label: {…}, …}}`). Pick
  // the pocketoption entry when present, else the first row.
  let row = stats;
  if (stats && stats.pocketoption) row = stats.pocketoption;
  else if (stats && typeof stats === 'object' && !('sample_count' in stats)) {
    const keys = Object.keys(stats);
    if (keys.length) row = stats[keys[0]];
  }
  if (!row || typeof row !== 'object') return;

  const fmt = (ms) => (ms == null || !isFinite(ms) ? '—' : ms < 10 ? ms.toFixed(1) : String(Math.round(ms)));
  const now  = row.last_ms;
  const p50  = row.p50_ms;
  const p99  = row.p99_ms;
  const p999 = row.p999_ms;

  nowEl.textContent  = fmt(now)  + (now  != null ? ' ms' : '');
  p50El.textContent  = fmt(p50)  + (p50  != null ? ' ms' : '');
  p99El.textContent  = fmt(p99)  + (p99  != null ? ' ms' : '');
  p999El.textContent = fmt(p999) + (p999 != null ? ' ms' : '');

  // Colour-code each cell
  const paint = (el, v) => {
    el.classList.remove('good', 'warn', 'bad');
    if (v == null || !isFinite(v)) return;
    if (v < 120) el.classList.add('good');
    else if (v < 300) el.classList.add('warn');
    else el.classList.add('bad');
  };
  paint(nowEl, now);
  paint(p50El, p50);
  paint(p99El, p99);
  paint(p999El, p999);

  // Overall state chip
  stateEl.classList.remove('good', 'warn', 'bad');
  let stateTxt = 'idle';
  const fc = Number(row.failure_count || 0);
  if (row.sample_count > 0) {
    if (fc > 0 && (fc / Math.max(row.probe_count || 1, 1)) > 0.15) {
      stateEl.classList.add('bad');
      stateTxt = 'flaky';
    } else if (p99 != null && p99 >= 300) {
      stateEl.classList.add('bad');
      stateTxt = 'slow';
    } else if (p99 != null && p99 >= 120) {
      stateEl.classList.add('warn');
      stateTxt = 'ok';
    } else if (p99 != null) {
      stateEl.classList.add('good');
      stateTxt = 'fast';
    } else {
      stateTxt = 'warming';
    }
  }
  stateEl.textContent = stateTxt;

  if (statsEl) {
    const nS = row.sample_count || 0;
    const nF = row.failure_count || 0;
    statsEl.textContent = `${nS} sample${nS === 1 ? '' : 's'} · ${nF} fail`;
  }
}


export default {
  createPanel,
  initPanelEvents,
  updateStatsDisplay,
  updateInvertDisplay,
  updateStatusDot,
  cleanupPanel,
  populateStrategies,
  setStrategyTf,
  getStrategyTf,
  updateNetworkLatency,
  setSnsDirectionMode,
  setChartTypeManual,
  setInvertThreshold,
  updateAITab,
  setLatencyAbstainThreshold,
  setLatencyAbstainState,
  setEliteGateThreshold,
  setEliteGateEnforceDirection,
  setEliteGateState,
};
