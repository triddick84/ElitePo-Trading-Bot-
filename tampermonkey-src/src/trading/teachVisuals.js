/**
 * Iter 100 — Shared visual helpers for TEACH modes.
 *
 * Provides:
 *   - flashCaptureConfirmation(el, label): Draws a 2-second green "capture"
 *     pulse around a DOM element with a small label so the user gets a
 *     tight visual confirmation that TM captured the right container.
 *   - showTeachToast(text, kind): Renders a lightweight toast in the top-
 *     right corner. Kinds: 'success' | 'info' | 'warn'.
 *
 * All overlays are absolutely positioned with z-index 2147483646, self-
 * clean after their animation completes, and are safe to call while
 * other teach overlays are up.
 */

const _mkPulseAnim = (() => {
  let installed = false;
  return () => {
    if (installed) return;
    installed = true;
    try {
      const style = document.createElement('style');
      style.id = 'pobot_teach_visuals_css';
      style.textContent = `
        @keyframes pobot_capture_pulse {
          0%   { box-shadow:0 0 0 0 rgba(52,211,153,0.9), 0 0 40px rgba(52,211,153,0.4); }
          70%  { box-shadow:0 0 0 24px rgba(52,211,153,0), 0 0 60px rgba(52,211,153,0.3); }
          100% { box-shadow:0 0 0 0 rgba(52,211,153,0), 0 0 40px rgba(52,211,153,0.0); }
        }
        @keyframes pobot_toast_in {
          0%   { opacity:0; transform:translateX(20px); }
          100% { opacity:1; transform:translateX(0); }
        }
        @keyframes pobot_toast_out {
          0%   { opacity:1; transform:translateX(0); }
          100% { opacity:0; transform:translateX(20px); }
        }
      `;
      document.head.appendChild(style);
    } catch (_e) { /* silent */ }
  };
})();

/**
 * Draw a 2-second confirmation pulse around `el` with `label` in a badge.
 * Non-blocking, self-cleaning.
 */
export function flashCaptureConfirmation(el, label) {
  if (!el || !el.getBoundingClientRect) return;
  _mkPulseAnim();
  const rect = el.getBoundingClientRect();
  if (rect.width < 4 || rect.height < 4) return;

  const box = document.createElement('div');
  box.style.cssText = [
    'position:fixed', 'pointer-events:none', 'z-index:2147483646',
    `top:${rect.top - 4}px`, `left:${rect.left - 4}px`,
    `width:${rect.width + 8}px`, `height:${rect.height + 8}px`,
    'border:3px solid #34d399', 'border-radius:8px',
    'background:rgba(52,211,153,0.10)',
    'animation:pobot_capture_pulse 1400ms ease-out 1',
  ].join(';');

  const badge = document.createElement('div');
  badge.style.cssText = [
    'position:absolute', 'top:-28px', 'left:0',
    'background:#065f46', 'color:#ecfdf5',
    'font:700 12px system-ui,sans-serif',
    'padding:4px 10px', 'border-radius:6px',
    'box-shadow:0 4px 14px rgba(0,0,0,0.35)',
    'white-space:nowrap',
  ].join(';');
  badge.textContent = label || '✓ Captured';
  box.appendChild(badge);

  document.body.appendChild(box);
  setTimeout(() => {
    try {
      box.style.animation = 'pobot_toast_out 220ms ease-in forwards';
      setTimeout(() => { try { box.remove(); } catch (_e) {} }, 260);
    } catch (_e) { try { box.remove(); } catch (_ee) {} }
  }, 1900);
}

/**
 * Small top-right toast. Auto-dismisses after `durationMs` (default 2400).
 * kind ∈ 'success' | 'info' | 'warn' — colours only.
 */
export function showTeachToast(text, kind = 'success', durationMs = 2400) {
  _mkPulseAnim();
  const palette = {
    success: { bg: '#065f46', fg: '#ecfdf5', accent: '#34d399' },
    info:    { bg: '#0e3a5f', fg: '#e0f2fe', accent: '#38bdf8' },
    warn:    { bg: '#7c2d12', fg: '#fff7ed', accent: '#fb923c' },
  }[kind] || { bg: '#082f38', fg: '#ecfeff', accent: '#22d3ee' };

  // Stack toasts vertically — offset by any siblings already on screen
  const siblings = document.querySelectorAll('.pobot_teach_toast');
  const topOffset = 18 + siblings.length * 48;

  const t = document.createElement('div');
  t.className = 'pobot_teach_toast';
  t.style.cssText = [
    'position:fixed', `top:${topOffset}px`, 'right:18px',
    'z-index:2147483647',
    `background:${palette.bg}`, `color:${palette.fg}`,
    `border-left:4px solid ${palette.accent}`,
    'padding:10px 14px', 'border-radius:8px',
    'font:600 13px system-ui,sans-serif',
    'box-shadow:0 8px 24px rgba(0,0,0,0.45)',
    'max-width:340px', 'pointer-events:none',
    'animation:pobot_toast_in 220ms ease-out 1',
  ].join(';');
  t.textContent = text || '';
  document.body.appendChild(t);

  setTimeout(() => {
    try {
      t.style.animation = 'pobot_toast_out 220ms ease-in forwards';
      setTimeout(() => { try { t.remove(); } catch (_e) {} }, 250);
    } catch (_e) { try { t.remove(); } catch (_ee) {} }
  }, durationMs);
}

export default { flashCaptureConfirmation, showTeachToast };
