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
  const W = mobile ? 220 : 300;
  const FONT = mobile ? 11 : 12;
  const BTN_PAD = mobile ? '10px 6px' : '7px 4px';
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
          <span class="${P}dot" id="${P}dot" title="Bot connection status"></span>
          <button class="${P}expandbtn" id="${P}expandbtn" data-testid="tm-panel-expand" title="Expand to fullscreen / restore compact view">⛶</button>
          <button class="${P}minbtn" id="${P}minbtn" data-testid="tm-panel-minimize" title="Minimize panel">_</button>
        </div>
      </div>

      <!-- Tab bar (Iter 96) -->
      <div class="${P}tabbar" data-testid="tm-tabbar">
        <button class="${P}tabbtn active" data-tab="live" data-testid="tab-live"><span class="${P}tabicon">◉</span>Live</button>
        <button class="${P}tabbtn" data-tab="trade" data-testid="tab-trade"><span class="${P}tabicon">▲</span>Trade</button>
        <button class="${P}tabbtn" data-tab="config" data-testid="tab-config"><span class="${P}tabicon">⚙</span>Config</button>
        <button class="${P}tabbtn" data-tab="stats" data-testid="tab-stats"><span class="${P}tabicon">▨</span>Stats</button>
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
        </div>

        <!-- ═════════════════ TAB: TRADE ═════════════════ -->
        <div class="${P}tabpanel" data-tab-panel="trade" data-testid="tab-panel-trade">
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

        <!-- ═════════════════ TAB: CONFIG ═════════════════ -->
        <div class="${P}tabpanel" data-tab-panel="config" data-testid="tab-panel-config">
          <div class="${P}advanced" id="${P}advanced">
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
      </div>
      <div class="${P}resize" id="${P}resize" data-testid="resize-handle" title="Drag to resize panel width. Saved across reloads."></div>
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
      const newW = Math.max(180, Math.min(600, startW - dx));
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

  // APP signal poller toggle
  const appBtn = q('app');
  if (appBtn) {
    appBtn.addEventListener('click', () => {
      const isActive = appBtn.classList.contains('active');
      appBtn.classList.toggle('active');
      callbacks.onAppSignalToggle?.(!isActive);
    });
  }

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
  if (!header || !host) return;

  let dragging = false, startX, startY, origLeft, origTop;

  function getPos(e) {
    if (e.touches && e.touches.length > 0) {
      return { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }
    return { x: e.clientX, y: e.clientY };
  }

  function onStart(e) {
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

  // Mouse events
  header.addEventListener('mousedown', onStart);
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onEnd);

  // Touch events
  header.addEventListener('touchstart', onStart, { passive: false });
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
};
