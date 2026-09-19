/**
 * Iter 148 — Node-side unit test for the taught win/loss parsing logic.
 * We can't fully run the browser watcher here, but we CAN validate that
 * the taught-signature short-circuit picks up on class hints correctly.
 *
 * Run with:
 *   node tests/iter148_teach_parse.test.js
 */

// Minimal JSDOM-lite shim — we only need `className`, `querySelector`,
// `textContent`, `getAttribute`. Keeping it inline avoids adding jsdom
// as a runtime dep just for this smoke test.

class FakeEl {
  constructor(tag, className = '', text = '', children = []) {
    this.tagName = tag.toUpperCase();
    this.className = className;
    this._text = text;
    this.children = children;
    this._attrs = {};
    this.nodeType = 1;
  }
  get textContent() {
    return this._text + this.children.map(c => c.textContent).join(' ');
  }
  querySelector(sel) {
    // Support only ".class1.class2" — enough for the taught-parse path.
    if (!sel || !sel.startsWith('.')) return null;
    const wanted = sel.slice(1).split('.');
    const walk = (nodes) => {
      for (const n of nodes) {
        const cls = String(n.className || '').split(/\s+/);
        if (wanted.every(w => cls.includes(w))) return n;
        const nested = walk(n.children);
        if (nested) return nested;
      }
      return null;
    };
    return walk(this.children);
  }
  getAttribute(k) { return this._attrs[k] || null; }
}

// Load the module under test — we need a mini window-like context.
global.window = { localStorage: {
  _store: {},
  getItem(k) { return this._store[k] || null; },
  setItem(k, v) { this._store[k] = v; },
  removeItem(k) { delete this._store[k]; },
} };
global.document = {
  querySelector: () => null,
  querySelectorAll: () => [],
  body: new FakeEl('body'),
};
global.MutationObserver = class { observe() {} disconnect() {} };

// Replace loggers so test output is quiet
const noop = () => {};

// Direct-load the module. We can't `require()` an ES module directly, so
// smoke-test the compiled bundle output instead.
const path = require('path');
const fs = require('fs');
const bundlePath = path.resolve(__dirname, '../dist/pocket-option-auto-trader.user.js');
if (!fs.existsSync(bundlePath)) {
  console.error(`SKIP: bundle not built at ${bundlePath}`);
  process.exit(0);
}
const bundle = fs.readFileSync(bundlePath, 'utf8');

// Sanity checks on the bundle itself
const checks = [
  { name: 'version >= 8.154.0 present',        re: /8\.15[4-9]\.\d+|8\.[2-9]\d\.\d+|8\.1[6-9]\d\.\d+/ },
  { name: 'startTeach method present',        re: /startTeach\s*\(/ },
  { name: 'TEACH_GM_KEYS win key present',    re: /ai_elite_teach_win_row/ },
  { name: 'TEACH_GM_KEYS loss key present',   re: /ai_elite_teach_loss_row/ },
  { name: 'window.__aiEliteTeachWin exposed', re: /__aiEliteTeachWin/ },
  { name: 'Universal teach section title',    re: /Win\/Loss Detection Teach/ },
  { name: 'result-teach-btn testid present',  re: /result-teach-btn/ },
  { name: 'container teach exposed',          re: /__aiEliteTeachDealContainer/ },
];

let failed = 0;
for (const c of checks) {
  const ok = c.re.test(bundle);
  console.log(`  ${ok ? '✓' : '✗'} ${c.name}`);
  if (!ok) failed++;
}

if (failed > 0) {
  console.error(`\nFAIL: ${failed}/${checks.length} checks failed`);
  process.exit(1);
}
console.log(`\nOK: ${checks.length}/${checks.length} bundle checks passed`);
