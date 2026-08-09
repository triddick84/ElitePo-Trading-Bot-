/**
 * Iter 94 — Rich Force-Generate ("Go") Signal Analysis Modal.
 *
 * Renders the full analytical stack behind a force-generated signal so
 * traders can see WHY the bot picked its direction — not just a
 * confidence number. Powered by /api/tampermonkey/force-generate which
 * now delegates to /signals/force-generate-v2 (Iter 94 rewire).
 *
 * Surfaces:
 *   - Direction + confidence (with inversion badge)
 *   - Candlestick pattern block: patterns + historical win-rate per
 *     asset + directional bias + strength meter
 *   - Behavioural narrative (last 5 candles: trend / vol / momentum)
 *   - Per-strategy vote breakdown (CALL vs PUT counts)
 *   - ML ensemble agreement + volatility regime
 *   - Multi-timeframe confluence
 *   - Pattern disagreement warning (if any)
 */
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Progress } from '../components/ui/progress';

// ─────────────────────────────────────────────────────────────────────
// Small helpers
// ─────────────────────────────────────────────────────────────────────
const isBullish = (dir) => ['CALL', 'BUY', 'UP'].includes(String(dir || '').toUpperCase());
const dirColor = (dir) => (isBullish(dir) ? 'text-emerald-400' : 'text-rose-400');
const dirGlow = (dir) => (isBullish(dir) ? 'shadow-emerald-500/40' : 'shadow-rose-500/40');
const dirBg = (dir) => (isBullish(dir) ? 'from-emerald-500/20 to-cyan-500/10' : 'from-rose-500/20 to-orange-500/10');
const dirArrow = (dir) => (isBullish(dir) ? '▲' : '▼');
const pct = (v) => (v === null || v === undefined || Number.isNaN(v) ? '—' : `${(v * 100).toFixed(1)}%`);
const num = (v, digits = 1) => (v === null || v === undefined || Number.isNaN(v) ? '—' : Number(v).toFixed(digits));

const PatternRow = ({ p }) => {
  const bull = p.direction === 'bullish';
  const bear = p.direction === 'bearish';
  const wr = p.historical_win_rate;
  const wrColor =
    wr === null || wr === undefined ? 'text-slate-400'
    : wr >= 0.65 ? 'text-emerald-400'
    : wr >= 0.55 ? 'text-cyan-400'
    : wr >= 0.45 ? 'text-amber-400'
    : 'text-rose-400';
  return (
    <div
      className="flex items-center justify-between gap-3 rounded-lg border border-slate-700/60 bg-slate-900/40 px-3 py-2"
      data-testid={`candle-pattern-row-${p.id}`}
    >
      <div className="flex items-center gap-3">
        <span className={`text-lg ${bull ? 'text-emerald-400' : bear ? 'text-rose-400' : 'text-slate-400'}`}>
          {p.icon || (bull ? '▲' : bear ? '▼' : '◇')}
        </span>
        <div>
          <div className="font-medium text-slate-100">{p.name}</div>
          <div className="text-xs text-slate-400 capitalize">{p.direction} pattern</div>
        </div>
      </div>
      <div className="text-right">
        <div className={`font-mono text-sm ${wrColor}`}>
          {wr === null || wr === undefined ? 'cold-start' : `${(wr * 100).toFixed(1)}% WR`}
        </div>
        <div className="text-xs text-slate-500">
          {p.historical_wins}/{p.historical_total} hist · conf {(p.confidence * 100).toFixed(0)}%
        </div>
      </div>
    </div>
  );
};

const MetricPill = ({ label, value, tone = 'slate', testId }) => {
  const toneMap = {
    slate: 'border-slate-700/60 bg-slate-800/40 text-slate-200',
    cyan: 'border-cyan-500/40 bg-cyan-500/10 text-cyan-300',
    emerald: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
    rose: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
    amber: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
    violet: 'border-violet-500/40 bg-violet-500/10 text-violet-300',
  };
  return (
    <div
      className={`flex flex-col rounded-lg border px-3 py-2 text-xs ${toneMap[tone] || toneMap.slate}`}
      data-testid={testId}
    >
      <span className="uppercase tracking-wide opacity-70">{label}</span>
      <span className="mt-1 font-mono text-sm font-semibold">{value}</span>
    </div>
  );
};

const ForceGenerateSignalModal = ({ open, onOpenChange, result }) => {
  if (!result) return null;
  const sig = result.signal || {};
  const ca = sig.candle_analysis || {};
  const bs = ca.behavioural_summary || {};
  const patterns = ca.patterns || [];
  const components = sig.components || {};
  const componentEntries = Object.entries(components).filter(([, v]) => v && typeof v === 'object');
  const inverted = !!sig.inverted;
  const originalDir = sig.original_direction;
  const pd = sig.pattern_disagreement;

  // Vote tally across all components
  let callVotes = 0, putVotes = 0;
  componentEntries.forEach(([, v]) => {
    const d = String(v?.direction || '').toUpperCase();
    if (d === 'CALL') callVotes += 1;
    else if (d === 'PUT') putVotes += 1;
  });

  const confidencePct = Math.max(0, Math.min(100, Number(sig.confidence) || 0));
  const biasStrengthPct = Math.max(0, Math.min(100, Number(ca.pattern_bias_strength || 0) * 100));

  const abstain = !!sig.abstain;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-3xl max-h-[90vh] overflow-y-auto bg-slate-950/95 border-slate-700 backdrop-blur-xl"
        data-testid="force-generate-modal"
      >
        <DialogHeader>
          <DialogTitle className="text-slate-100 flex items-center gap-2">
            <span>⚡ Force-Generated Signal</span>
            <Badge variant="outline" className="border-cyan-500/50 text-cyan-300 text-xs">
              Full Analysis · v2
            </Badge>
          </DialogTitle>
        </DialogHeader>

        {/* Direction hero */}
        <div
          className={`rounded-xl border border-slate-700/60 bg-gradient-to-br ${dirBg(sig.direction)} p-5 shadow-lg ${dirGlow(sig.direction)}`}
          data-testid="force-generate-hero"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className={`text-5xl font-bold ${dirColor(sig.direction)}`} data-testid="force-generate-direction">
                {dirArrow(sig.direction)} {sig.direction}
              </span>
              <div className="flex flex-col">
                <span className="text-lg font-semibold text-slate-100" data-testid="force-generate-symbol">
                  {sig.symbol}
                </span>
                <span className="text-sm text-slate-400">
                  {sig.timeframe} · expires in {sig.expiry_seconds}s
                </span>
              </div>
            </div>
            <div className="text-right">
              <div className={`font-mono text-3xl ${dirColor(sig.direction)}`} data-testid="force-generate-confidence">
                {confidencePct.toFixed(1)}%
              </div>
              <div className="text-xs uppercase tracking-wider text-slate-400">confidence</div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {inverted && (
              <Badge className="bg-amber-500/20 text-amber-300 border border-amber-500/40" data-testid="force-generate-inverted-badge">
                INVERTED (was {originalDir})
              </Badge>
            )}
            {sig.quality && (
              <Badge className="bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 uppercase text-[10px]">
                {sig.quality}
              </Badge>
            )}
            {abstain && (
              <Badge className="bg-rose-500/20 text-rose-300 border border-rose-500/40" data-testid="force-generate-abstain-badge">
                ⚠ Abstain: {sig.abstain_reason || 'gated'}
              </Badge>
            )}
            {sig.vol_regime && (
              <Badge className="bg-violet-500/20 text-violet-300 border border-violet-500/40 uppercase text-[10px]">
                Vol · {sig.vol_regime}
              </Badge>
            )}
          </div>
          <Progress
            value={confidencePct}
            className="mt-4 h-1.5 bg-slate-800"
            data-testid="force-generate-confidence-bar"
          />
        </div>

        {/* Pattern disagreement warning */}
        {pd && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200" data-testid="pattern-disagreement-warning">
            ⚠ {pd.message}
          </div>
        )}

        {/* Candlestick pattern block */}
        <Card className="bg-slate-900/60 border-slate-700/60" data-testid="candle-analysis-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-slate-100 text-base flex items-center gap-2">
              <span>🕯 Candlestick Pattern Analysis</span>
              {ca.pattern_count > 0 && (
                <Badge variant="outline" className="border-cyan-500/40 text-cyan-300 text-xs">
                  {ca.pattern_count} detected
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Pattern bias arrow */}
            <div className="flex items-center justify-between rounded-lg bg-slate-800/40 border border-slate-700/40 px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="text-sm uppercase tracking-wide text-slate-400">Pattern Bias</span>
                <span
                  className={`font-semibold ${
                    ca.pattern_bias === 'bullish' ? 'text-emerald-400'
                    : ca.pattern_bias === 'bearish' ? 'text-rose-400'
                    : 'text-slate-400'
                  }`}
                  data-testid="pattern-bias-value"
                >
                  {ca.pattern_bias === 'bullish' ? '▲ Bullish'
                    : ca.pattern_bias === 'bearish' ? '▼ Bearish'
                    : '◇ Neutral'}
                </span>
              </div>
              <div className="text-xs text-slate-400">
                strength <span className="font-mono text-slate-200">{biasStrengthPct.toFixed(0)}%</span>
              </div>
            </div>
            <Progress value={biasStrengthPct} className="h-1 bg-slate-800" />

            {/* Detected patterns */}
            {patterns.length > 0 ? (
              <div className="space-y-2" data-testid="candle-patterns-list">
                {patterns.map((p) => <PatternRow key={p.id} p={p} />)}
              </div>
            ) : (
              <div className="text-sm text-slate-500 italic px-3 py-4 text-center border border-dashed border-slate-700/60 rounded-lg" data-testid="no-patterns-message">
                No classic patterns fired on the latest bar — decision driven by indicator confluence.
              </div>
            )}

            {/* Behavioural narrative */}
            <div className="rounded-lg bg-slate-800/40 border border-slate-700/40 p-3 text-sm text-slate-200" data-testid="behavioural-narrative">
              {bs.narrative || 'No narrative available.'}
            </div>

            {/* Trend / vol / momentum pills */}
            <div className="grid grid-cols-3 gap-2">
              <MetricPill
                label="Trend (5 bars)"
                value={bs.trend_last_5 || '—'}
                tone={bs.trend_last_5 === 'bullish' ? 'emerald' : bs.trend_last_5 === 'bearish' ? 'rose' : 'slate'}
                testId="metric-trend"
              />
              <MetricPill
                label="Volatility"
                value={bs.volatility || '—'}
                tone={bs.volatility === 'elevated' ? 'amber' : bs.volatility === 'compressed' ? 'cyan' : 'slate'}
                testId="metric-volatility"
              />
              <MetricPill
                label="Momentum"
                value={bs.momentum || '—'}
                tone={bs.momentum?.includes('up') ? 'emerald' : bs.momentum?.includes('down') ? 'rose' : 'slate'}
                testId="metric-momentum"
              />
            </div>
          </CardContent>
        </Card>

        {/* Signal reasoning + strategy block */}
        <Card className="bg-slate-900/60 border-slate-700/60" data-testid="signal-reasoning-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-slate-100 text-base">🧠 Signal Reasoning</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {sig.reason && (
              <div className="rounded-lg bg-slate-800/40 border border-slate-700/40 p-3 text-sm text-slate-200" data-testid="signal-reason-text">
                {sig.reason}
              </div>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <MetricPill label="Strategy" value={sig.strategy || '—'} tone="cyan" testId="metric-strategy" />
              <MetricPill label="Confluence" value={sig.confluence_score !== undefined ? num(sig.confluence_score, 0) : '—'} tone="emerald" testId="metric-confluence" />
              <MetricPill label="MTF Agree" value={sig.mtf_confluence !== undefined ? num(sig.mtf_confluence, 0) : '—'} tone="cyan" testId="metric-mtf" />
              <MetricPill label="ATR %" value={sig.atr_percent !== undefined ? `${num(sig.atr_percent, 3)}%` : '—'} tone="violet" testId="metric-atr" />
            </div>

            {/* Vote tally */}
            {(callVotes + putVotes) > 0 && (
              <div className="rounded-lg bg-slate-800/40 border border-slate-700/40 p-3" data-testid="votes-tally">
                <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Component Votes</div>
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-emerald-400">▲ CALL {callVotes}</span>
                      <span className="text-rose-400">PUT {putVotes} ▼</span>
                    </div>
                    <div className="mt-1 flex h-2 overflow-hidden rounded-full bg-slate-800">
                      <div
                        className="bg-emerald-500 transition-all"
                        style={{ width: `${(callVotes / Math.max(1, callVotes + putVotes)) * 100}%` }}
                      />
                      <div
                        className="bg-rose-500 transition-all"
                        style={{ width: `${(putVotes / Math.max(1, callVotes + putVotes)) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Per-strategy component breakdown */}
            {componentEntries.length > 0 && (
              <div className="space-y-1.5" data-testid="components-list">
                <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">Per-Strategy Vote</div>
                <div className="max-h-56 overflow-y-auto space-y-1 pr-1">
                  {componentEntries.map(([name, v]) => (
                    <div
                      key={name}
                      className="flex items-center justify-between rounded border border-slate-700/50 bg-slate-800/40 px-2 py-1 text-xs"
                      data-testid={`component-${name}`}
                    >
                      <span className="text-slate-300 truncate mr-2">{name}</span>
                      <div className="flex items-center gap-2">
                        {v.confidence !== undefined && (
                          <span className="font-mono text-slate-400">{Number(v.confidence).toFixed(0)}%</span>
                        )}
                        <span className={`font-semibold ${dirColor(v.direction)}`}>
                          {String(v.direction || '—').toUpperCase()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex items-center justify-between pt-2">
          <div className="text-xs text-slate-500">
            Candles: {result.candles_received || '—'} · Strategies: {result.strategies_evaluated || '—'}
            {sig.fire_offset_sec !== undefined && <> · Fire offset {sig.fire_offset_sec}s</>}
          </div>
          <Button
            variant="outline"
            className="border-slate-600 text-slate-200 hover:bg-slate-800"
            onClick={() => onOpenChange(false)}
            data-testid="force-generate-modal-close"
          >
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ForceGenerateSignalModal;
