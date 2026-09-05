/**
 * Iter 123 — Trade outcome parser regression tests
 *
 * We can't run Jest against the compiled bundle easily, but we CAN pull the
 * scanDOMForTradeResult function into Node via jsdom and verify the 8
 * false-positive scenarios that were flipping losses → wins under the old
 * implementation.
 *
 * Run with:
 *   cd /app/tampermonkey-src && node __tests__/outcomeParser.test.js
 */

const { JSDOM } = require('jsdom');

// Load the fresh source (not the compiled bundle — we want the current code)
// We inject scanDOMForTradeResult into a scope with a fake `document`.
function loadParser(dom) {
  global.document = dom.window.document;
  global.window = dom.window;
  // Extract just the function body by requiring a shim
  const fs = require('fs');
  const src = fs.readFileSync(__dirname + '/../src/utils/dom.js', 'utf8');
  // Grab the scanDOMForTradeResult function definition using a delimiter match
  const match = src.match(/export function scanDOMForTradeResult\(\)\s*\{[\s\S]*?\n\}/);
  if (!match) throw new Error('scanDOMForTradeResult not found in dom.js');
  // Wrap and eval as a plain function
  // eslint-disable-next-line no-new-func
  const fnBody = match[0].replace(/^export /, '');
  const factory = new Function(fnBody + '\nreturn scanDOMForTradeResult;');
  return factory();
}

const cases = [
  // --- Losses that previously misclassified as wins ---
  {
    name: 'zero-payout loss shown as "$0.00" — must be LOSS',
    html: `<div class="deals-list"><div class="deals-item"><div class="deal-profit">$0.00</div></div></div>`,
    expect: false,
  },
  {
    name: 'zero-payout loss shown as "0.00" — must be LOSS',
    html: `<div class="deals-list"><div class="deals-item"><div class="deal-amount">0.00</div></div></div>`,
    expect: false,
  },
  {
    name: 'neutral "profit-container" wrapper on a LOSS — must not read as WIN',
    // Deal container has "profit-container" (layout class) but profit element shows -$1.85
    html: `<div class="deals-list"><div class="deals-item profit-container"><div class="deal-profit">-$1.85</div></div></div>`,
    expect: false,
  },
  {
    name: 'popup with "+Stake returned" copy on a LOSS — must be LOSS (largest signed number wins)',
    html: `<div class="notification-deal"><span>Trade closed. +Stake returned: $2.00. Profit: -$2.00</span></div>`,
    expect: false,
  },
  {
    name: 'LOSS with a "5%" bonus mention in the toast — must be LOSS',
    html: `<div class="notification-deal"><span>Loss -$3.50 (used +5% bonus)</span></div>`,
    expect: false,
  },

  // --- Real wins should still be detected ---
  {
    name: 'clean WIN "+$1.85"',
    html: `<div class="deals-list"><div class="deals-item"><div class="deal-profit">+$1.85</div></div></div>`,
    expect: true,
  },
  {
    name: 'WIN by explicit class marker "success"',
    html: `<div class="deals-list"><div class="deals-item"><div class="profit success">1.85</div></div></div>`,
    expect: true,
  },
  {
    name: 'WIN via popup "+$1.20"',
    html: `<div class="notification-deal"><span>Trade closed. +$1.20</span></div>`,
    expect: true,
  },

  // --- Explicit LOSS class markers ---
  {
    name: 'LOSS by "loss" class marker',
    html: `<div class="deals-list"><div class="deals-item loss"><div class="deal-profit">-2</div></div></div>`,
    expect: false,
  },
  {
    name: 'LOSS by "failed" class on profit element',
    html: `<div class="deals-list"><div class="deals-item"><div class="profit failed">-2</div></div></div>`,
    expect: false,
  },

  // --- Ambiguous → null (never guess) ---
  {
    name: 'no deal container present → null',
    html: `<div>irrelevant</div>`,
    expect: null,
  },
  {
    name: 'deal with bare "1.85" no sign no class → null (unsigned+profit neutral class)',
    html: `<div class="deals-list"><div class="deals-item"><div class="deal-amount">1.85</div></div></div>`,
    expect: null,
  },
];

let passed = 0, failed = 0;
for (const c of cases) {
  const dom = new JSDOM(`<!DOCTYPE html><html><body>${c.html}</body></html>`);
  // JSDOM's default offsetParent is null (no layout). Patch offsetParent so our
  // visibility guard passes.
  Object.defineProperty(dom.window.HTMLElement.prototype, 'offsetParent', {
    configurable: true,
    get() { return this.parentElement; },
  });
  const scan = loadParser(dom);
  const got = scan();
  const ok = got === c.expect;
  const tag = ok ? '✓' : '✗';
  const gotStr = got === null ? 'null' : String(got);
  const expStr = c.expect === null ? 'null' : String(c.expect);
  console.log(`${tag} ${c.name}\n    expected=${expStr} got=${gotStr}`);
  if (ok) passed++; else failed++;
}
console.log(`\n${passed}/${passed + failed} passed${failed ? ' — FAILURES ABOVE' : ''}`);
process.exit(failed ? 1 : 0);
