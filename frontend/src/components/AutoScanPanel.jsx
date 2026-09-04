import React, { useState, useEffect, useRef, useMemo } from 'react';
import axios from 'axios';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Slider } from './ui/slider';
import {
  Radar, Play, Square, RefreshCw, Target, Zap,
  TrendingUp, TrendingDown, CheckCircle2, XCircle, ArrowRight,
} from 'lucide-react';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * Iter 112 — Auto-Scan & Route panel.
 *
 * Continuously scans the user's `selected_assets` list, ranks by signal
 * confidence + Elite Score, and routes the winner to the TM script via
 * `/api/tampermonkey/active-target` so the userscript switches the chart
 * and executes the winning trade automatically.
 */
const AutoScanPanel = ({ selectedAssets = [], onOpenTMDashboard }) => {
  const [config, setConfig] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [interval_, setInterval_] = useState([15]);
  const [minConfidence, setMinConfidence] = useState([0.65]);
  const [minEliteScore, setMinEliteScore] = useState([0]);
  const timerRef = useRef(null);

  const isRunning = !!status?.running;

  const fetchStatus = async () => {
    try {
      const r = await axios.get(`${API}/api/signals/auto-scan/status`);
      setStatus(r.data);
      if (r.data.config) {
        setConfig(r.data.config);
      }
    } catch (e) {
      // silent
    }
  };

  useEffect(() => {
    fetchStatus();
    // Iter 121 — smart-poll: pause when tab is hidden
    let timerId = null;
    const tick = () => fetchStatus();
    const start = () => {
      if (timerId != null) return;
      timerId = setInterval(tick, 3000);
    };
    const stop = () => {
      if (timerId != null) { clearInterval(timerId); timerId = null; }
    };
    const onVis = () => {
      if (document.visibilityState === 'visible') { tick(); start(); }
      else stop();
    };
    if (document.visibilityState === 'visible') start();
    document.addEventListener('visibilitychange', onVis);
    timerRef.current = { stop, onVis };
    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVis);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync sliders from config once when it first arrives
  useEffect(() => {
    if (!config) return;
    if (typeof config.interval_seconds === 'number') setInterval_([config.interval_seconds]);
    if (typeof config.min_confidence === 'number') setMinConfidence([config.min_confidence]);
    if (typeof config.min_elite_score === 'number') setMinEliteScore([config.min_elite_score]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config?.interval_seconds, config?.min_confidence, config?.min_elite_score]);

  const buildCfg = () => ({
    assets: selectedAssets,
    interval_seconds: interval_[0],
    min_confidence: minConfidence[0],
    min_elite_score: minEliteScore[0],
    chart_timeframe: config?.chart_timeframe || '1m',
    trade_duration_seconds: config?.trade_duration_seconds || 82,
  });

  const startLoop = async () => {
    if (!selectedAssets.length) {
      toast.error('Add assets in the dashboard universe first');
      return;
    }
    setLoading(true);
    try {
      const r = await axios.post(`${API}/api/signals/auto-scan/start`, buildCfg());
      if (r.data.success) {
        toast.success(`🎯 Auto-Scan started — ${selectedAssets.length} assets, every ${interval_[0]}s`);
        await fetchStatus();
      } else {
        toast.error(r.data.message || 'Start failed');
      }
    } catch (e) {
      toast.error(`Start failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const stopLoop = async () => {
    setLoading(true);
    try {
      await axios.post(`${API}/api/signals/auto-scan/stop`);
      toast.success('Auto-Scan stopped');
      await fetchStatus();
    } catch (e) {
      toast.error(`Stop failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const scanNow = async () => {
    if (!selectedAssets.length) {
      toast.error('Add assets in the dashboard universe first');
      return;
    }
    setScanning(true);
    try {
      const r = await axios.post(`${API}/api/signals/auto-scan/scan-now`, {
        assets: selectedAssets,
        config: buildCfg(),
      });
      if (r.data.winner) {
        toast.success(
          `🎯 ROUTED: ${r.data.winner.asset} ${r.data.winner.direction} @ ${(r.data.winner.confidence * 100).toFixed(0)}%`,
        );
      } else {
        toast.info(`No matching signal in ${r.data.universe_size} assets`);
      }
      await fetchStatus();
    } catch (e) {
      toast.error(`Scan failed: ${e.message}`);
    } finally {
      setScanning(false);
    }
  };

  const results = status?.last_scan_results || [];
  const winner = status?.last_winner;
  const lastScanAge = status?.stats?.last_scan_ts
    ? Math.max(0, Math.floor(Date.now() / 1000 - status.stats.last_scan_ts))
    : null;

  const sortedResults = useMemo(() => {
    return [...results].sort((a, b) => {
      if (a.matched !== b.matched) return b.matched - a.matched;
      return (b.confidence || 0) - (a.confidence || 0);
    });
  }, [results]);

  return (
    <Card
      className="border-emerald-500/30 bg-gradient-to-br from-emerald-950/30 via-slate-900/50 to-cyan-950/30"
      data-testid="auto-scan-panel"
    >
      <CardContent className="p-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <Radar
                className={`w-6 h-6 ${isRunning ? 'text-emerald-400 animate-pulse' : 'text-slate-500'}`}
              />
              Auto-Scan &amp; Route
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Continuously scans your selected assets and routes the highest-confidence signal to the Tampermonkey script.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              className={
                isRunning
                  ? 'bg-emerald-500 text-black animate-pulse'
                  : 'bg-slate-700 text-slate-300'
              }
              data-testid="auto-scan-status-badge"
            >
              {isRunning ? '● LIVE' : '○ IDLE'}
            </Badge>
            <Badge className="bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
              Iter 112
            </Badge>
          </div>
        </div>

        {/* Universe chips */}
        <div>
          <Label className="text-xs uppercase tracking-wider text-slate-400">
            Scanning universe · {selectedAssets.length} assets
          </Label>
          <div
            className="flex flex-wrap gap-1 mt-2 max-h-24 overflow-y-auto"
            data-testid="auto-scan-universe"
          >
            {selectedAssets.length === 0 ? (
              <div className="text-xs text-amber-400 py-2">
                ⚠️ No assets in universe. Add some at the top of the dashboard.
              </div>
            ) : (
              selectedAssets.map((a) => (
                <Badge
                  key={a}
                  variant="outline"
                  className="text-[10px] font-mono border-slate-700 bg-slate-800/60"
                >
                  {a}
                </Badge>
              ))
            )}
          </div>
        </div>

        {/* Sliders */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="flex justify-between mb-2">
              <Label className="text-xs">Scan Interval</Label>
              <span className="text-sm font-bold text-emerald-400">{interval_[0]}s</span>
            </div>
            <Slider
              value={interval_}
              onValueChange={setInterval_}
              min={5}
              max={120}
              step={1}
              data-testid="auto-scan-interval-slider"
            />
          </div>
          <div>
            <div className="flex justify-between mb-2">
              <Label className="text-xs">Min Confidence</Label>
              <span className="text-sm font-bold text-emerald-400">
                {(minConfidence[0] * 100).toFixed(0)}%
              </span>
            </div>
            <Slider
              value={minConfidence}
              onValueChange={setMinConfidence}
              min={0.5}
              max={0.95}
              step={0.05}
              data-testid="auto-scan-confidence-slider"
            />
          </div>
          <div>
            <div className="flex justify-between mb-2">
              <Label className="text-xs">Min Elite Score</Label>
              <span className="text-sm font-bold text-emerald-400">
                {minEliteScore[0] === 0 ? 'OFF' : minEliteScore[0]}
              </span>
            </div>
            <Slider
              value={minEliteScore}
              onValueChange={setMinEliteScore}
              min={0}
              max={100}
              step={5}
              data-testid="auto-scan-elite-slider"
            />
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 flex-wrap">
          {!isRunning ? (
            <Button
              onClick={startLoop}
              disabled={loading}
              className="bg-emerald-500 hover:bg-emerald-600 text-black font-bold"
              data-testid="auto-scan-start-btn"
            >
              <Play className="w-4 h-4 mr-2" />
              Start Auto-Scan
            </Button>
          ) : (
            <Button
              onClick={stopLoop}
              disabled={loading}
              className="bg-rose-500 hover:bg-rose-600 text-white font-bold"
              data-testid="auto-scan-stop-btn"
            >
              <Square className="w-4 h-4 mr-2" />
              Stop
            </Button>
          )}
          <Button
            onClick={scanNow}
            disabled={scanning}
            variant="outline"
            className="border-cyan-500/50 text-cyan-300"
            data-testid="auto-scan-scan-now-btn"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? 'Scanning…' : 'Scan Now'}
          </Button>
          {lastScanAge !== null && (
            <div className="text-xs text-slate-500 self-center ml-2">
              Last scan {lastScanAge}s ago · {status?.stats?.total_scans || 0} runs · {status?.stats?.total_routed || 0} routed
            </div>
          )}
        </div>

        {/* Winner banner */}
        {winner && (
          <div
            className="rounded-lg border border-emerald-500/50 bg-emerald-950/40 p-4"
            data-testid="auto-scan-winner-banner"
          >
            <div className="flex items-center gap-3 flex-wrap">
              <Target className="w-5 h-5 text-emerald-400" />
              <span className="text-emerald-300 font-bold text-sm uppercase tracking-wider">
                Currently routed to TM
              </span>
              <ArrowRight className="w-4 h-4 text-emerald-400" />
              <span className="font-mono text-white font-bold text-lg">
                {winner.asset}
              </span>
              <Badge
                className={
                  winner.direction === 'CALL'
                    ? 'bg-emerald-500 text-black'
                    : 'bg-rose-500 text-white'
                }
              >
                {winner.direction === 'CALL' ? (
                  <TrendingUp className="w-3 h-3 mr-1" />
                ) : (
                  <TrendingDown className="w-3 h-3 mr-1" />
                )}
                {winner.direction}
              </Badge>
              <div className="text-sm text-slate-300">
                confidence <span className="font-bold text-emerald-400">
                  {(winner.confidence * 100).toFixed(0)}%
                </span>
              </div>
              {winner.elite_score != null && (
                <div className="text-sm text-slate-300">
                  elite <span className="font-bold text-cyan-400">
                    {winner.elite_score.toFixed(1)}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Results table */}
        {sortedResults.length > 0 && (
          <div className="rounded-lg border border-slate-800 overflow-hidden">
            <div className="bg-slate-950/60 px-4 py-2 border-b border-slate-800 flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-400" />
              <span className="text-sm font-semibold text-white">Last Scan Results</span>
              <span className="text-xs text-slate-400 ml-auto">{sortedResults.length} scanned</span>
            </div>
            <table className="w-full text-sm" data-testid="auto-scan-results-table">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-slate-400 bg-slate-950/40">
                  <th className="px-3 py-2 text-left">Asset</th>
                  <th className="px-3 py-2 text-center">Dir</th>
                  <th className="px-3 py-2 text-right">Conf</th>
                  <th className="px-3 py-2 text-right">Elite</th>
                  <th className="px-3 py-2 text-center">Match</th>
                  <th className="px-3 py-2 text-left">Reason</th>
                </tr>
              </thead>
              <tbody>
                {sortedResults.map((r) => {
                  const isWin = winner && r.asset === winner.asset;
                  return (
                    <tr
                      key={r.asset}
                      className={`border-t border-slate-800 ${isWin ? 'bg-emerald-500/10' : 'hover:bg-slate-800/40'}`}
                      data-testid={`auto-scan-row-${r.asset}`}
                    >
                      <td className="px-3 py-2 font-mono text-white">
                        {isWin && <span className="text-emerald-400 mr-1">🎯</span>}
                        {r.asset}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {r.direction ? (
                          <Badge
                            className={
                              r.direction === 'CALL'
                                ? 'bg-emerald-500 text-black text-[10px]'
                                : 'bg-rose-500 text-white text-[10px]'
                            }
                          >
                            {r.direction}
                          </Badge>
                        ) : (
                          <span className="text-slate-500 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right font-mono">
                        <span className={r.confidence >= minConfidence[0] ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
                          {(r.confidence * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-cyan-300">
                        {r.elite_score != null ? r.elite_score.toFixed(1) : '—'}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {r.matched ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 inline" />
                        ) : (
                          <XCircle className="w-4 h-4 text-slate-600 inline" />
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-400 truncate max-w-[200px]">
                        {r.reason || 'ok'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Help */}
        <div className="text-xs text-slate-500 pt-2 border-t border-slate-800">
          💡 The winning signal is stored as your TM script's <code>active_target</code>. The userscript's <code>appSignalPoller</code>
          reads it, switches the chart to the routed asset, and fires the trade — no manual asset-switching needed.
        </div>
      </CardContent>
    </Card>
  );
};

export default AutoScanPanel;
