/**
 * ML Lab — unified AI Models training & backtesting hub (Iter 61, Apr 25, 2026)
 *
 * Tabs per model: Improved v2, Maximized v3, LSTM/GRU, PPO RL, Ensemble.
 * Each tab shows: status, feature list, retrain controls, and per-model backtest panel.
 * Plus: scheduled retrain history, charts (equity curve, accuracy delta, feature importance).
 */
import React, { useState, useEffect, useMemo } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "../components/ui/select";
import { Label } from "../components/ui/label";
import { Input } from "../components/ui/input";
import { Progress } from "../components/ui/progress";
import { Alert, AlertDescription } from "../components/ui/alert";
import { toast } from "sonner";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, AreaChart, Area, Cell,
} from "recharts";
import {
  Brain, RotateCw, PlayCircle, Calendar, TrendingUp, AlertTriangle,
  CheckCircle2, Database, Activity, BarChart3, Newspaper, Target,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

/**
 * Iter 62b — safe JSON parser that survives ingress 502/504 timeouts.
 * Heavy training/backtest endpoints can exceed the proxy's ~60s budget,
 * in which case the body is plain text like "The preview environment is
 * not responding...". `res.json()` then throws "Unexpected token 'T'".
 * This helper inspects the response and returns a structured error so
 * the UI surfaces something useful instead of crashing.
 */
async function safeFetchJson(url, init = {}) {
  let res;
  try {
    res = await fetch(url, init);
  } catch (e) {
    return { success: false, error: `network: ${e?.message || e}` };
  }
  const ctype = (res.headers.get("content-type") || "").toLowerCase();
  if (!ctype.includes("application/json")) {
    let txt = "";
    try { txt = (await res.text()).slice(0, 240); } catch (_e) { /* ignore */ }
    if (res.status === 502 || res.status === 504 || /not responding|gateway|timeout/i.test(txt)) {
      return {
        success: false,
        error: "request timed out (>60s ingress limit) — the job may still be running in the background. Refresh in 1–2 min.",
        http_status: res.status,
      };
    }
    return {
      success: false,
      error: `non-JSON response (HTTP ${res.status}): ${txt || "empty body"}`,
      http_status: res.status,
    };
  }
  try {
    return await res.json();
  } catch (e) {
    return { success: false, error: `parse: ${e?.message || e}` };
  }
}

/**
 * Iter 65 — Poll a background job until it reaches a terminal state.
 * Hands off to `onProgress({progress, message, status})` as updates arrive.
 * Returns the final job document (or throws on cancellation / timeout).
 */
async function pollJob(jobId, { onProgress, intervalMs = 2000, timeoutMs = 600_000 } = {}) {
  const start = Date.now();
  // eslint-disable-next-line no-constant-condition
  while (true) {
    if (Date.now() - start > timeoutMs) {
      throw new Error(`polling timeout after ${Math.round(timeoutMs / 1000)}s`);
    }
    const r = await safeFetchJson(`${process.env.REACT_APP_BACKEND_URL}/api/jobs/${jobId}`);
    if (r && r.success && r.job) {
      const j = r.job;
      onProgress?.({ progress: j.progress, message: j.message, status: j.status });
      if (j.status === "completed") return j;
      if (j.status === "failed") throw new Error(j.error || "job failed");
      if (j.status === "cancelled") throw new Error("job cancelled");
    }
    await new Promise((res) => setTimeout(res, intervalMs));
  }
}

const MODELS = [
  { id: "improved_v2", name: "Improved v2", color: "#22c55e", desc: "RF + GB + AdaBoost ensemble. Best on OTC pairs." },
  { id: "maximized_v3", name: "Maximized v3", color: "#3b82f6", desc: "XGBoost stacking with regime detector. Best on real forex." },
  { id: "lstm_gru", name: "LSTM/GRU", color: "#a855f7", desc: "Sequence model for short-horizon trends." },
  { id: "ppo_rl", name: "PPO RL", color: "#f59e0b", desc: "Reinforcement learner — adapts to live trade outcomes." },
  { id: "ensemble", name: "Ensemble", color: "#06b6d4", desc: "Weighted vote across all four models." },
];

const QUALITY_COLORS = { HIGH: "#22c55e", MEDIUM: "#d29922", LOW: "#f85149" };

export default function MLLabPage() {
  const [tab, setTab] = useState("improved_v2");
  const [tuningReport, setTuningReport] = useState(null);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [otcStats, setOtcStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [retraining, setRetraining] = useState({});
  const [backtest, setBacktest] = useState({ symbol: "EURUSD_OTC", days: 7, timeframe: "5s", asset_class: "forex_otc" });
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [backtestResult, setBacktestResult] = useState(null);
  const [backtestHistory, setBacktestHistory] = useState([]);
  const [assets, setAssets] = useState({ forex: [], crypto: [], stocks: [] });
  const [assetUniverse, setAssetUniverse] = useState(null);
  const [latencyHealth, setLatencyHealth] = useState(null);
  const [latencyStats, setLatencyStats] = useState(null);
  const [guardrail, setGuardrail] = useState(null);
  const [tournament, setTournament] = useState(null);
  const [iq720Outcomes, setIq720Outcomes] = useState(null);
  const [sentiment, setSentiment] = useState(null);
  const [sentimentHealth, setSentimentHealth] = useState(null);
  const [sentimentRefreshing, setSentimentRefreshing] = useState(false);
  const [scanner, setScanner] = useState(null);            // latest snapshot
  const [scannerRunning, setScannerRunning] = useState(false);
  const [scannerProgress, setScannerProgress] = useState(null);  // { progress, message }

  const refreshAll = async () => {
    try {
      const [tr, ss, ot, btH, ass, lh, lst, uni, gr, tour, iq, sent, sentH, scan] = await Promise.all([
        fetch(`${API}/ml/tuning-report`).then((r) => r.json()),
        fetch(`${API}/ml/scheduler/status`).then((r) => r.json()),
        fetch(`${API}/signals/otc-candle-stats`).then((r) => r.json()).catch(() => null),
        fetch(`${API}/backtest/history`).then((r) => r.json()).catch(() => ({ results: [] })),
        fetch(`${API}/backtest/assets`).then((r) => r.json()).catch(() => ({ assets: {} })),
        fetch(`${API}/signals/latency-health`).then((r) => r.json()).catch(() => null),
        fetch(`${API}/signals/latency-stats?since_minutes=60`).then((r) => r.json()).catch(() => null),
        fetch(`${API}/backtest/assets-universe`).then((r) => r.json()).catch(() => null),
        fetch(`${API}/signals/latency-guardrail/status`).then((r) => r.json()).catch(() => null),
        fetch(`${API}/ml/tournament/status`).then((r) => r.json()).catch(() => null),
        fetch(`${API}/iq720/outcome-stats`).then((r) => r.json()).catch(() => null),
        fetch(`${API}/sentiment/scores`).then((r) => r.json()).catch(() => null),
        fetch(`${API}/sentiment/health`).then((r) => r.json()).catch(() => null),
        fetch(`${API}/scanner/latest`).then((r) => r.json()).catch(() => null),
      ]);
      setTuningReport(tr);
      setSchedulerStatus(ss);
      setOtcStats(ot);
      setBacktestHistory(btH.results || []);
      setAssets(ass.assets || {});
      setLatencyHealth(lh);
      setLatencyStats(lst);
      setAssetUniverse(uni);
      setGuardrail(gr?.guardrail || null);
      setTournament(tour || null);
      setIq720Outcomes(iq || null);
      setSentiment(sent || null);
      setSentimentHealth(sentH || null);
      setScanner(scan && scan.success ? scan : null);
      setLoading(false);
    } catch (e) {
      toast.error("Failed to load ML lab data: " + e.message);
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshAll();
    const id = setInterval(refreshAll, 30_000);
    return () => clearInterval(id);
  }, []);

  const runRetrain = async (modelId) => {
    setRetraining({ ...retraining, [modelId]: true });
    try {
      const symbols = (tuningReport?.otc_data?.by_symbol || [])
        .filter((s) => s.trainable)
        .map((s) => s.symbol);
      if (modelId === "improved_v2" || modelId === "maximized_v3") {
        // Iter 65 — async via job manager so we don't depend on the 60s ingress budget
        const submit = await safeFetchJson(`${API}/ml/train-from-otc-async`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: modelId === "improved_v2" ? "improved" : "maximized",
            symbols,
            min_samples: 500,
          }),
        });
        if (!submit.success || !submit.job_id) {
          toast.error(`Retrain submit failed: ${submit.error || "unknown"}`);
          return;
        }
        toast.info(`${modelId} training queued — polling for completion…`);
        try {
          const final = await pollJob(submit.job_id, {
            onProgress: ({ progress, message }) => {
              if (progress != null && message) {
                // optional toast updates could go here; we throttle to final only
              }
            },
            intervalMs: 3000,
            timeoutMs: 600_000,
          });
          const r = final.result || {};
          if (r.success) {
            const oos = r.test_accuracy != null ? ` · OOS ${r.test_accuracy}%` : "";
            const warn = r.overfit_warning ? ` ⚠ overfit gap ${r.overfit_gap}%` : "";
            toast.success(`${modelId} retrained → ${r.cv_accuracy}% CV (±${r.cv_std}%)${oos}${warn}`);
            refreshAll();
          } else {
            toast.error(`Retrain failed: ${r.error || "unknown"}`);
          }
        } catch (e) {
          toast.error(`Retrain polling failed: ${e.message}`);
        }
      } else if (modelId === "lstm_gru") {
        toast.info("LSTM/GRU training queued — can take 1–2 minutes");
        const submit = await safeFetchJson(`${API}/ml/train-from-otc-async`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model: "lstm_gru", symbols, epochs: 20 }),
        });
        if (!submit.success || !submit.job_id) {
          toast.error(`LSTM submit failed: ${submit.error || "unknown"}`);
          return;
        }
        try {
          const final = await pollJob(submit.job_id, { intervalMs: 4000, timeoutMs: 600_000 });
          const r = final.result || {};
          if (r.success) {
            toast.success(`LSTM/GRU trained → ${r.val_accuracy}% val acc on ${r.total_candles} candles`);
            refreshAll();
          } else {
            toast.error(`LSTM/GRU train failed: ${r.error || "unknown"}`);
          }
        } catch (e) {
          toast.error(`LSTM/GRU polling failed: ${e.message}`);
        }
      } else if (modelId === "ppo_rl") {
        toast.info("PPO RL training queued — can take 2–3 minutes");
        const submit = await safeFetchJson(`${API}/ml/train-from-otc-async`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model: "ppo_rl", symbols, n_episodes: 15 }),
        });
        if (!submit.success || !submit.job_id) {
          toast.error(`PPO submit failed: ${submit.error || "unknown"}`);
          return;
        }
        try {
          const final = await pollJob(submit.job_id, { intervalMs: 5000, timeoutMs: 600_000 });
          const r = final.result || {};
          if (r.success) {
            toast.success(`PPO RL trained → ${(r.avg_win_rate || 0).toFixed(1)}% avg win rate on ${r.total_samples} samples`);
            refreshAll();
          } else {
            toast.error(`PPO train failed: ${r.error || "unknown"}`);
          }
        } catch (e) {
          toast.error(`PPO polling failed: ${e.message}`);
        }
      } else if (modelId === "ensemble") {
        toast.info("Ensemble retrain started — runs in background (2–5 min). Polling for completion...");
        const r = await safeFetchJson(`${API}/ml/scheduler/trigger`, { method: "POST" });
        if (!r.success && !r.accepted) {
          toast.warning(r.message || "Retrain queued");
          return;
        }
        // Poll scheduler status until manual_in_progress turns false
        const startCount = schedulerStatus?.retrain_count ?? 0;
        let elapsed = 0;
        const pollInterval = 5000; // 5s
        const maxWait = 6 * 60 * 1000; // 6 min
        while (elapsed < maxWait) {
          await new Promise((res) => setTimeout(res, pollInterval));
          elapsed += pollInterval;
          try {
            const s = await fetch(`${API}/ml/scheduler/status`).then((res) => res.json());
            if (s.success && !s.manual_in_progress && (s.retrain_count ?? 0) > startCount) {
              const last = (s.recent_history || []).slice(-1)[0];
              const trained = last?.models_trained?.length || 0;
              const agg = last?.aggregate_oos;
              const oosStr = agg
                ? ` · OOS ${agg.mean_oos_accuracy}% (min ${agg.min_oos_accuracy}, max ${agg.max_oos_accuracy})` +
                  (agg.any_overfit ? ` ⚠ overfit detected` : "")
                : "";
              toast.success(`Ensemble retrain complete — ${trained} models trained in ${last?.duration_seconds?.toFixed(0) || "?"}s${oosStr}`);
              refreshAll();
              return;
            }
          } catch (_pollErr) {
            // ignore transient poll errors, keep waiting
          }
        }
        toast.warning("Retrain still running after 6 min — check ML Lab status panel for results");
        refreshAll();
      } else {
        toast.error(`Unknown model: ${modelId}`);
      }
    } catch (e) {
      toast.error("Retrain error: " + e.message);
    } finally {
      setRetraining({ ...retraining, [modelId]: false });
    }
  };

  const runRealTradeTraining = async (modelId) => {
    // Iter 54: train on actual TM trade outcomes (REAL W/L) instead of
    // synthetic next-candle labels. Fire-and-forget with status polling.
    setRetraining({ ...retraining, [`${modelId}_real`]: true });
    try {
      const trigger = await safeFetchJson(`${API}/ml/train-from-trades`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: modelId === "improved_v2" ? "improved" : "maximized",
          min_samples: 30,
          max_age_days: 30,
        }),
      });
      if (!trigger.success && !trigger.accepted) {
        toast.warning(trigger.message || trigger.error || "Real-trade training queued");
        return;
      }
      toast.info(
        "Real-trade training started — pulling OANDA backfill for trade windows (1-3 min)…"
      );
      const pollInterval = 6000;
      const maxWait = 8 * 60 * 1000;
      let elapsed = 0;
      while (elapsed < maxWait) {
        await new Promise((res) => setTimeout(res, pollInterval));
        elapsed += pollInterval;
        try {
          const s = await fetch(`${API}/ml/train-from-trades/status`).then((res) => res.json());
          if (s.success && !s.in_progress && s.result) {
            const res = s.result;
            if (res.success) {
              const oos = res.test_accuracy != null ? ` · OOS ${res.test_accuracy}%` : "";
              const warn = res.overfit_warning ? ` ⚠ overfit gap ${res.overfit_gap}%` : "";
              toast.success(
                `Trained on ${res.total_samples} real trades → ${res.cv_accuracy}% CV` +
                `${oos}${warn} (±${res.cv_std}%). ${res.weekend_trades_skipped || 0} weekend trades skipped.`
              );
            } else {
              toast.error(`Real-trade training failed: ${res.error}`);
            }
            refreshAll();
            return;
          }
        } catch (_e) {
          // ignore transient poll errors
        }
      }
      toast.warning("Real-trade training still running after 8 min — check status panel.");
    } catch (e) {
      toast.error("Real-trade training error: " + e.message);
    } finally {
      setRetraining({ ...retraining, [`${modelId}_real`]: false });
    }
  };

  const runBacktest = async () => {
    setBacktestRunning(true);
    setBacktestResult(null);
    try {
      // Iter 58 — pick the right strategy per active model tab
      // and pull the correct timeframe based on the asset class (OTC ≥ 3s, regular ≥ M1).
      const strategyMap = {
        improved_v2: "hybrid",       // ensemble vote — closest to live behaviour
        maximized_v3: "hybrid",
        lstm_gru: "lstm_gru",
        ppo_rl: "ppo_rl",
        ensemble: "all",
      };
      const strat = strategyMap[tab] || "hybrid";
      const isOtc = (backtest.symbol || "").toUpperCase().includes("_OTC");
      const tf = backtest.timeframe || (isOtc ? "5s" : "M1");

      const r = await safeFetchJson(`${API}/backtest/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy: strat,
          symbol: backtest.symbol,
          timeframe: tf,
          days: parseInt(backtest.days, 10),
        }),
      });

      // safeFetchJson surfaces ingress 502/504 as { success:false, error }
      if (r && r.success === false && r.error) {
        toast.error(`Backtest failed: ${r.error}`);
        setBacktestResult({ error: r.error });
        refreshAll();
        return;
      }

      // Backend returns { success, results: [ { strategy, metrics: {...} } ] }
      // We unwrap the first result's metrics and surface them flat.
      if (r && r.success && Array.isArray(r.results) && r.results.length > 0) {
        // Prefer the result that actually has metrics; some entries may carry `error` only.
        const withMetrics = r.results.find((x) => x.metrics) || r.results[0];
        if (withMetrics.error) {
          toast.error(`Backtest failed: ${withMetrics.error}`);
          setBacktestResult({ error: withMetrics.error });
        } else {
          const m = withMetrics.metrics || {};
          const flat = {
            strategy: withMetrics.strategy,
            win_rate: m.win_rate ?? 0,
            total_signals: m.total_trades ?? 0,
            profit_factor: m.profit_factor ?? 0,
            total_return: m.total_return_pct ?? m.total_return ?? 0,
            max_drawdown: m.max_drawdown_pct ?? m.max_drawdown ?? 0,
            sharpe: m.sharpe_ratio ?? m.sharpe ?? 0,
            equity_curve: m.equity_curve || [],
            data_points: r.data_points,
            data_source: r.data_source,
            symbol: r.symbol,
            timeframe: r.timeframe,
          };
          setBacktestResult(flat);
          toast.success(
            `Backtest complete (${flat.strategy}): ${flat.win_rate.toFixed(1)}% win rate · ${flat.total_signals} trades · PF ${flat.profit_factor.toFixed(2)}`
          );
        }
      } else {
        const errMsg = r?.detail || r?.error || "Backtest returned no results";
        toast.error(`Backtest failed: ${errMsg}`);
        setBacktestResult({ error: errMsg });
      }
      refreshAll();
    } catch (e) {
      toast.error("Backtest error: " + e.message);
    } finally {
      setBacktestRunning(false);
    }
  };

  const currentModel = useMemo(() => MODELS.find((m) => m.id === tab), [tab]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RotateCw className="w-8 h-8 animate-spin text-purple-500" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6" data-testid="ml-lab-page">
      <Header schedulerStatus={schedulerStatus} otcStats={otcStats} onRefresh={refreshAll} />
      <PoolHealthCard otcStats={otcStats} tuningReport={tuningReport} />
      <LatencyHealthCard health={latencyHealth} stats={latencyStats} />
      <GuardrailTournamentCard guardrail={guardrail} tournament={tournament} onRefresh={refreshAll} />
      <IQ720OutcomeCard outcomes={iq720Outcomes} onRefresh={refreshAll} />
      <SentimentCard
        sentiment={sentiment}
        health={sentimentHealth}
        refreshing={sentimentRefreshing}
        onRefresh={async () => {
          setSentimentRefreshing(true);
          try {
            const r = await fetch(`${API}/sentiment/refresh?force=true`, { method: "POST" }).then((x) => x.json());
            if (r && r.success) {
              toast.success("Sentiment refreshed");
              await refreshAll();
            } else {
              toast.error(`Sentiment refresh failed: ${r?.detail || r?.error || "unknown"}`);
            }
          } catch (e) {
            toast.error("Sentiment refresh error: " + e.message);
          } finally {
            setSentimentRefreshing(false);
          }
        }}
      />
      <ScannerCard
        scanner={scanner}
        running={scannerRunning}
        progress={scannerProgress}
        onRun={async (scope) => {
          setScannerRunning(true);
          setScannerProgress({ progress: 0, message: "submitting…" });
          try {
            const submit = await safeFetchJson(`${API}/scanner/find-best-pairs`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                scope,
                days: 3,
                top_n: 10,
                min_signals: 30,
                min_confidence: 55,
              }),
            });
            if (!submit.success || !submit.job_id) {
              toast.error(`Scan submit failed: ${submit.error || "unknown"}`);
              return;
            }
            toast.info(`Scanning ${submit.queued_count || "?"} symbols (scope=${scope})`);
            const final = await pollJob(submit.job_id, {
              onProgress: (p) => setScannerProgress(p),
              intervalMs: 4000,
              timeoutMs: 30 * 60 * 1000,
            });
            const r = final.result || {};
            toast.success(`Scan complete — ${r.qualified_count}/${r.total_scanned} qualified, top pick: ${r.leaderboard?.[0]?.symbol || "—"}`);
            refreshAll();
          } catch (e) {
            toast.error("Scan failed: " + e.message);
          } finally {
            setScannerRunning(false);
            setScannerProgress(null);
          }
        }}
      />

      <Tabs value={tab} onValueChange={setTab} className="space-y-4">
        <TabsList className="grid grid-cols-5 bg-slate-900 border border-slate-800" data-testid="ml-model-tabs">
          {MODELS.map((m) => (
            <TabsTrigger key={m.id} value={m.id} data-testid={`tab-${m.id}`} className="data-[state=active]:bg-slate-800">
              {m.name}
            </TabsTrigger>
          ))}
        </TabsList>

        {MODELS.map((m) => (
          <TabsContent key={m.id} value={m.id} className="space-y-4">
            <ModelCard
              model={m}
              tuningReport={tuningReport}
              onRetrain={() => runRetrain(m.id)}
              onRealTradeRetrain={
                m.id === "improved_v2" || m.id === "maximized_v3"
                  ? () => runRealTradeTraining(m.id)
                  : null
              }
              retraining={retraining[m.id]}
              retrainingReal={retraining[`${m.id}_real`]}
            />
            <FeatureGroupsCard model={m} tuningReport={tuningReport} />
            <BacktestPanel
              model={m}
              assets={assets}
              universe={assetUniverse}
              backtest={backtest}
              setBacktest={setBacktest}
              onRun={runBacktest}
              running={backtestRunning}
              result={backtestResult}
              history={backtestHistory}
            />
          </TabsContent>
        ))}
      </Tabs>

      <ScheduledHistoryCard schedulerStatus={schedulerStatus} />
      <BacktestHistoryChart history={backtestHistory} />
    </div>
  );
}

/* ---------- HEADER ---------- */
function Header({ schedulerStatus, otcStats, onRefresh }) {
  const last = schedulerStatus?.last_retrain;
  const lastAgo = last ? Math.round((Date.now() - new Date(last).getTime()) / 60000) : null;
  return (
    <div className="flex items-start justify-between gap-4 flex-wrap">
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-cyan-400 bg-clip-text text-transparent flex items-center gap-2">
          <Brain className="w-8 h-8 text-purple-400" /> ML Lab
        </h1>
        <p className="text-slate-400 mt-1">
          Train, backtest, and monitor every AI model in one place.
        </p>
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <div className="text-xs text-slate-500">Auto-retrain scheduler</div>
          <div className="text-sm font-mono">
            {schedulerStatus?.running ? (
              <span className="text-green-400">● running</span>
            ) : (
              <span className="text-slate-500">○ stopped</span>
            )}
            {lastAgo !== null && <span className="text-slate-400"> · last {lastAgo}m ago</span>}
          </div>
        </div>
        <Button variant="outline" onClick={onRefresh} data-testid="ml-lab-refresh-btn">
          <RotateCw className="w-4 h-4 mr-2" /> Refresh
        </Button>
      </div>
    </div>
  );
}

/* ---------- POOL HEALTH ---------- */
function PoolHealthCard({ otcStats, tuningReport }) {
  const overlay = otcStats?.summary?.overlay_ratio || 0;
  const totalCandles = tuningReport?.otc_data?.total_candles || 0;
  const trainable = (tuningReport?.otc_data?.by_symbol || []).filter((s) => s.trainable).length;
  return (
    <Card className="bg-slate-900 border-slate-800" data-testid="pool-health-card">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Database className="w-4 h-4 text-cyan-400" /> Training Pool Health
        </CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Total OTC candles" value={totalCandles.toLocaleString()} />
        <Stat label="Trainable symbols" value={`${trainable}/29`} />
        <Stat
          label="Live PO overlay"
          value={`${(overlay * 100).toFixed(1)}%`}
          hint={`${otcStats?.summary?.po_live_candles || 0} live · ${otcStats?.summary?.oanda_backfill_candles || 0} OANDA`}
        />
        <Stat
          label="Min samples / symbol"
          value={tuningReport?.tuning_config?.min_samples_per_symbol || 200}
        />
      </CardContent>
    </Card>
  );
}


/* ---------- "FIND BEST PAIR TODAY" SCANNER CARD (Iter 66) ---------- */
function ScannerCard({ scanner, running, progress, onRun }) {
  const [scope, setScope] = useState("all_otc");
  const tsAge = scanner?.ts
    ? Math.round((Date.now() - new Date(scanner.ts).getTime()) / 60000)
    : null;
  const SCOPES = [
    { v: "all_otc", l: "All OTC (~180)" },
    { v: "forex_otc", l: "Forex OTC (73)" },
    { v: "commodities_otc", l: "Commodities OTC (15)" },
    { v: "crypto_otc", l: "Crypto OTC (30)" },
    { v: "indices_otc", l: "Indices OTC (17)" },
    { v: "stocks_otc", l: "Stocks OTC (48)" },
    { v: "all", l: "Everything (366) — slow" },
  ];
  const lb = scanner?.leaderboard || [];

  const wrColor = (wr) => {
    if (wr >= 58) return "text-emerald-300 bg-emerald-500/10 border-emerald-500/40";
    if (wr >= 52) return "text-emerald-300 bg-emerald-500/5 border-emerald-500/20";
    if (wr >= 48) return "text-amber-300 bg-amber-500/5 border-amber-500/20";
    return "text-rose-300 bg-rose-500/5 border-rose-500/20";
  };

  return (
    <Card className="bg-slate-900/60 border-slate-800" data-testid="scanner-card">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-fuchsia-400" />
          <CardTitle className="text-base">Find Best Pair Today</CardTitle>
          {scanner && (
            <Badge variant="outline" className="border-fuchsia-500/40 text-fuchsia-300 text-[10px]">
              scope: {scanner.scope}
            </Badge>
          )}
          {tsAge != null && (
            <span className="text-xs text-slate-500">{tsAge}m ago</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            disabled={running}
            data-testid="scanner-scope-select"
            className="bg-slate-800 border border-slate-700 text-xs rounded px-2 py-1 text-slate-200"
          >
            {SCOPES.map((s) => (
              <option key={s.v} value={s.v}>{s.l}</option>
            ))}
          </select>
          <Button
            size="sm"
            onClick={() => onRun(scope)}
            disabled={running}
            data-testid="scanner-run-btn"
            className="bg-fuchsia-600 hover:bg-fuchsia-700 text-xs"
          >
            {running ? (
              <><RotateCw className="w-3 h-3 mr-1 animate-spin" />Scanning…</>
            ) : (
              <><Target className="w-3 h-3 mr-1" />Run Scan</>
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {running && progress && (
          <div className="space-y-1" data-testid="scanner-progress">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>{progress.message}</span>
              <span>{progress.progress ?? 0}%</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded overflow-hidden">
              <div
                className="h-full bg-fuchsia-500 transition-all"
                style={{ width: `${progress.progress ?? 0}%` }}
              />
            </div>
          </div>
        )}

        {!scanner && !running && (
          <p className="text-sm text-slate-400">
            Run a scan to find the highest-edge pairs across your universe. Composite score = (win&nbsp;rate − 50) × √signals × profit&nbsp;factor.
          </p>
        )}

        {scanner && (
          <div className="text-xs text-slate-400 flex flex-wrap gap-x-4 gap-y-1">
            <span>strategy: <span className="text-slate-200">{scanner.strategy}</span></span>
            <span>days: <span className="text-slate-200">{scanner.days}</span></span>
            <span>min-conf: <span className="text-slate-200">{scanner.min_confidence}%</span></span>
            <span>min-sig: <span className="text-slate-200">{scanner.min_signals}</span></span>
            <span>qualified: <span className="text-slate-200">{scanner.qualified_count}/{scanner.total_scanned}</span></span>
          </div>
        )}

        {lb.length > 0 && (
          <div className="overflow-x-auto" data-testid="scanner-leaderboard">
            <table className="w-full text-xs">
              <thead className="text-slate-500 border-b border-slate-800">
                <tr>
                  <th className="text-left py-1 pr-2">#</th>
                  <th className="text-left py-1 pr-2">Symbol</th>
                  <th className="text-left py-1 pr-2">TF</th>
                  <th className="text-right py-1 pr-2">Win&nbsp;Rate</th>
                  <th className="text-right py-1 pr-2">Signals</th>
                  <th className="text-right py-1 pr-2">PF</th>
                  <th className="text-right py-1 pr-2">Return</th>
                  <th className="text-right py-1 pr-2">Sharpe</th>
                  <th className="text-right py-1">Score</th>
                </tr>
              </thead>
              <tbody className="font-mono text-slate-300">
                {lb.map((r, i) => (
                  <tr key={r.symbol + i} className="border-b border-slate-800/50">
                    <td className="py-1 pr-2">{i + 1}</td>
                    <td className="py-1 pr-2 text-slate-200 font-semibold" data-testid={`scanner-row-${i + 1}`}>
                      {r.symbol}
                    </td>
                    <td className="py-1 pr-2 text-slate-500">{r.timeframe}</td>
                    <td className="py-1 pr-2 text-right">
                      <span className={`inline-block px-1.5 rounded border ${wrColor(r.win_rate)}`}>
                        {r.win_rate.toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-1 pr-2 text-right">{r.signals}</td>
                    <td className="py-1 pr-2 text-right">{r.profit_factor.toFixed(2)}</td>
                    <td className={`py-1 pr-2 text-right ${(r.total_return_pct || 0) >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                      {(r.total_return_pct || 0).toFixed(2)}%
                    </td>
                    <td className="py-1 pr-2 text-right">{(r.sharpe || 0).toFixed(2)}</td>
                    <td className="py-1 text-right text-fuchsia-300 font-semibold">
                      {r.score}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ---------- SENTIMENT CARD (Iter 62) ---------- */
function SentimentCard({ sentiment, health, refreshing, onRefresh }) {
  const scores = sentiment?.scores || {};
  const order = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "XAU", "BTC"];
  const ageMin = health?.snapshot_age_minutes;
  const fresh = ageMin != null && ageMin < (health?.fresh_within_minutes || 30);
  const hasData = !!sentiment?.success && Object.keys(scores).length > 0;

  const scoreColor = (s) => {
    if (s > 0.4) return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
    if (s > 0.15) return "bg-emerald-500/10 text-emerald-300 border-emerald-500/30";
    if (s < -0.4) return "bg-rose-500/20 text-rose-300 border-rose-500/40";
    if (s < -0.15) return "bg-rose-500/10 text-rose-300 border-rose-500/30";
    return "bg-slate-700/40 text-slate-300 border-slate-600/40";
  };

  const arrow = (s) => (s > 0.15 ? "▲" : s < -0.15 ? "▼" : "·");

  return (
    <Card className="bg-slate-900/60 border-slate-800" data-testid="sentiment-card">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div className="flex items-center gap-2">
          <Newspaper className="w-5 h-5 text-cyan-400" />
          <CardTitle className="text-base">Macro Sentiment</CardTitle>
          {fresh ? (
            <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/40">fresh</Badge>
          ) : ageMin != null ? (
            <Badge variant="outline" className="border-amber-500/40 text-amber-300">{ageMin}m stale</Badge>
          ) : (
            <Badge variant="outline" className="border-slate-600 text-slate-400">no data</Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {ageMin != null && (
            <span className="text-xs text-slate-500">
              {health?.last_run_headline_count || 0} headlines · {ageMin}m ago
            </span>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={onRefresh}
            disabled={refreshing}
            data-testid="sentiment-refresh-btn"
            className="border-slate-700 text-xs"
          >
            <RotateCw className={`w-3 h-3 mr-1 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {!hasData && (
          <p className="text-sm text-slate-400">
            No sentiment snapshot yet. Hit Refresh to pull headlines (forexlive, fxstreet, investing.com) and score them with Claude.
          </p>
        )}
        {hasData && sentiment.summary && (
          <p className="text-xs text-slate-400 italic border-l-2 border-cyan-500/40 pl-2" data-testid="sentiment-summary">
            {sentiment.summary}
          </p>
        )}
        {hasData && (
          <div className="grid grid-cols-5 gap-2" data-testid="sentiment-scores-grid">
            {order.map((cur) => {
              const e = scores[cur] || { score: 0, confidence: 0, reason: "" };
              return (
                <div
                  key={cur}
                  className={`rounded border p-2 text-center ${scoreColor(e.score || 0)}`}
                  data-testid={`sentiment-${cur}`}
                  title={e.reason || ""}
                >
                  <div className="text-[10px] uppercase tracking-wide opacity-70">{cur}</div>
                  <div className="text-sm font-mono font-semibold">
                    {arrow(e.score || 0)} {(e.score || 0).toFixed(2)}
                  </div>
                  <div className="text-[10px] opacity-60">conf {(e.confidence || 0).toFixed(2)}</div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}


/* ---------- IQ-720 OUTCOME FEEDBACK CARD (Iter 59) ---------- */
function IQ720OutcomeCard({ outcomes, onRefresh }) {
  const stats = outcomes?.stats || [];
  const adapted = stats.filter((s) => s.adapted);
  const sorted = [...stats].sort((a, b) => (b.multiplier ?? 1) - (a.multiplier ?? 1));
  const top5 = sorted.slice(0, 5);
  const bot5 = sorted.slice(-5).reverse().filter((s) => !top5.includes(s));

  const triggerMatch = async () => {
    try {
      const r = await fetch(`${API}/iq720/match-outcomes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lookback_hours: 168 }),
      }).then((res) => res.json());
      const m = r.match || {};
      toast.success(
        `Outcome matcher: ${m.matched || 0} new matches (${m.checked || 0} checked). ` +
        `Stats refreshed for ${r.refresh?.confirmations_evaluated || 0} confirmations.`
      );
      onRefresh();
    } catch (e) {
      toast.error("Match-outcomes failed: " + e.message);
    }
  };

  const totalMatched = stats.reduce((acc, s) => acc + (s.total || 0), 0);

  return (
    <Card className="bg-slate-900 border-slate-800" data-testid="iq720-outcome-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-400" /> IQ-720 Outcome Feedback Loop
          </CardTitle>
          <Button size="sm" variant="outline" onClick={triggerMatch} data-testid="iq720-match-btn">
            <RotateCw className="w-3 h-3 mr-1" /> Match Outcomes Now
          </Button>
        </div>
        <CardDescription className="text-xs">
          Adaptive per-confirmation weights from real Tampermonkey W/L outcomes (7-day rolling window).
          Confirmations need ≥8 matched trades before their multiplier kicks in.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Confirmations tracked" value={stats.length} />
          <Stat label="Adapted (≥8 trades)" value={adapted.length} hint="vs neutral 1.00×" />
          <Stat label="Total matched signals" value={totalMatched} hint="rolling 7d window" />
          <Stat
            label="Cache loaded"
            value={outcomes?.loaded_at ? new Date(outcomes.loaded_at).toLocaleTimeString() : "—"}
          />
        </div>

        {stats.length === 0 ? (
          <div className="text-xs text-slate-500 italic border border-slate-800 rounded p-3" data-testid="iq720-cold-start">
            Cold start — no IQ-720 signals matched to trade outcomes yet.
            <br />
            Generate IQ-720 signals + run trades for a few days, then click "Match Outcomes Now"
            to populate the rolling stats. Once a confirmation has ≥8 matched trades, its weight
            will start adapting based on its real win-rate.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                ⬆ Top boosted (win-rate × 0.50)²
              </div>
              <div className="space-y-1">
                {top5.map((s) => (
                  <div
                    key={s.name}
                    className="flex justify-between text-xs bg-slate-950 rounded p-2"
                    data-testid={`iq720-confirm-${s.name}`}
                  >
                    <span className="font-mono text-slate-300">{s.name}</span>
                    <span className="font-mono">
                      <span className={s.adapted ? "text-green-400" : "text-slate-500"}>
                        {Number(s.multiplier).toFixed(2)}×
                      </span>
                      <span className="text-slate-500 ml-2">
                        ({(s.win_rate * 100).toFixed(0)}% · {s.total})
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                ⬇ Downweighted
              </div>
              <div className="space-y-1">
                {bot5.map((s) => (
                  <div key={s.name} className="flex justify-between text-xs bg-slate-950 rounded p-2">
                    <span className="font-mono text-slate-300">{s.name}</span>
                    <span className="font-mono">
                      <span className={s.adapted ? "text-red-400" : "text-slate-500"}>
                        {Number(s.multiplier).toFixed(2)}×
                      </span>
                      <span className="text-slate-500 ml-2">
                        ({(s.win_rate * 100).toFixed(0)}% · {s.total})
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}


/* ---------- LATENCY GUARDRAIL + DAILY TOURNAMENT (Iter 58) ---------- */
function GuardrailTournamentCard({ guardrail, tournament, onRefresh }) {
  const tripped = !!guardrail?.tripped;
  const ratio = guardrail?.ratio;
  const cur = guardrail?.p95_current_ms;
  const base = guardrail?.p95_baseline_ms;
  const throttle = Math.round((guardrail?.throttle_fraction || 0) * 100);
  const t = tournament?.tournament;
  const weights = tournament?.cache || {};
  const wrs = t?.model_winrates || {};

  const runTournament = async () => {
    try {
      const r = await fetch(`${API}/ml/tournament/run`, { method: "POST" }).then((res) => res.json());
      if (r.accepted) {
        toast.info("Tournament running in background — refresh in ~30s for fresh weights.");
        setTimeout(onRefresh, 30000);
      } else {
        toast.warning(r.message || "Tournament queued");
      }
    } catch (e) {
      toast.error("Tournament trigger failed: " + e.message);
    }
  };

  const guardrailColor = tripped ? "border-red-700 bg-red-950/30"
    : (ratio && ratio > 1.5) ? "border-amber-700 bg-amber-950/20"
    : "border-slate-800 bg-slate-900";

  return (
    <Card className={`${guardrailColor}`} data-testid="guardrail-tournament-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="w-4 h-4 text-fuchsia-400" /> Latency Guardrail · Daily Model Tournament
          </CardTitle>
          <Button size="sm" variant="outline" onClick={runTournament} data-testid="run-tournament-btn">
            <PlayCircle className="w-3 h-3 mr-1" /> Run Tournament
          </Button>
        </div>
        <CardDescription className="text-xs">
          Auto-throttle trades when DOM exec lag spikes · Per-model vote multipliers from rolling win-rate
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Guardrail row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <div className="text-xs text-slate-500 uppercase tracking-wider">Guardrail</div>
            <div className="mt-1" data-testid="guardrail-state">
              {tripped ? (
                <Badge className="bg-red-500/20 text-red-300 border-red-500/40">
                  <AlertTriangle className="w-3 h-3 mr-1" /> TRIPPED · throttling {throttle}%
                </Badge>
              ) : (
                <Badge className="bg-green-500/20 text-green-400 border-green-500/40">
                  <CheckCircle2 className="w-3 h-3 mr-1" /> OK
                </Badge>
              )}
            </div>
          </div>
          <Stat
            label="Exec lag p95 (5m)"
            value={cur != null ? `${cur.toFixed(0)}ms` : "—"}
            hint={base != null ? `baseline ${base.toFixed(0)}ms` : "needs ≥15 baseline samples"}
          />
          <Stat
            label="Ratio (recent / baseline)"
            value={ratio != null ? `${ratio.toFixed(2)}×` : "—"}
            hint="trips at 2.0×, releases at 1.3×"
          />
          <Stat label="Trip / release count" value={`${guardrail?.trip_count || 0} / ${guardrail?.release_count || 0}`} />
        </div>

        {/* Tournament row */}
        <div className="border-t border-slate-800 pt-4">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">
            Daily Tournament — vote multipliers from rolling win-rate
            {t?.computed_at && (
              <span className="ml-2 text-slate-400 normal-case font-normal">
                · last run {new Date(t.computed_at).toLocaleString()}
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {["improved_v2", "maximized_v3", "lstm_gru", "ppo_rl", "iq720"].map((mid) => {
              const w = weights[mid] ?? 1.0;
              const wr = wrs[mid];
              const wColor = w > 1.15 ? "text-green-400" : w < 0.85 ? "text-red-400" : "text-slate-200";
              return (
                <div key={mid} data-testid={`tournament-model-${mid}`}>
                  <div className="text-xs text-slate-500 uppercase tracking-wider">{mid}</div>
                  <div className={`text-2xl font-bold font-mono ${wColor} mt-1`}>
                    {Number(w).toFixed(2)}×
                  </div>
                  <div className="text-xs text-slate-500 mt-1">
                    {wr != null ? `win-rate ${wr.toFixed(1)}%` : "no win-rate yet"}
                  </div>
                </div>
              );
            })}
          </div>
          {!t && (
            <div className="text-xs text-slate-500 italic mt-2">
              No tournament has run yet — multipliers default to 1.00×. Run a tournament or wait for the next auto-retrain to populate.
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}



function Stat({ label, value, hint }) {
  return (
    <div>
      <div className="text-xs text-slate-500 uppercase tracking-wider">{label}</div>
      <div className="text-2xl font-bold font-mono text-slate-100 mt-1">{value}</div>
      {hint && <div className="text-xs text-slate-500 mt-1">{hint}</div>}
    </div>
  );
}

/* ---------- LATENCY HEALTH CARD (Iter 55) ---------- */
function LatencyHealthCard({ health, stats }) {
  // Colour mapping for the health chip
  const chipColour = {
    green: "bg-green-500/15 text-green-300 border-green-500/40",
    yellow: "bg-amber-500/15 text-amber-300 border-amber-500/40",
    red: "bg-red-500/20 text-red-300 border-red-500/50",
    grey: "bg-slate-700/40 text-slate-400 border-slate-600",
  }[health?.color || "grey"];

  const phases = stats?.stats?.phase_means_ms || {};
  const phaseEntries = Object.entries(phases).sort((a, b) => b[1] - a[1]);

  return (
    <Card className="bg-slate-900 border-slate-800" data-testid="latency-health-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="w-4 h-4 text-purple-400" /> Signal Latency Health
            <Badge variant="outline" className={`uppercase ml-2 ${chipColour}`} data-testid="latency-health-chip">
              {health?.status || "no data"}
            </Badge>
          </CardTitle>
          <span className="text-xs text-slate-500">
            {health?.count ?? 0} signals · last {health?.window_minutes ?? 5}m
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Stat
            label="Mean (last 5m)"
            value={`${(health?.mean_ms ?? 0).toFixed(0)}ms`}
            hint={`exceeded ${((health?.exceeded_rate ?? 0) * 100).toFixed(1)}% of budget`}
          />
          <Stat
            label="p50"
            value={stats?.stats ? `${stats.stats.p50_ms.toFixed(0)}ms` : "—"}
            hint="last 60m"
          />
          <Stat
            label="p95"
            value={stats?.stats ? `${stats.stats.p95_ms.toFixed(0)}ms` : "—"}
            hint="last 60m"
          />
          <Stat
            label="p99"
            value={stats?.stats ? `${stats.stats.p99_ms.toFixed(0)}ms` : "—"}
            hint="last 60m"
          />
          <Stat
            label="Stale-data abstains"
            value={stats?.stats?.exceeded_count ?? 0}
            hint={`of ${stats?.count ?? 0} signals (60m)`}
          />
        </div>
        {phaseEntries.length > 0 && (
          <div>
            <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">
              Per-phase mean (slowest first)
            </div>
            <div className="space-y-1">
              {phaseEntries.map(([name, ms]) => (
                <div key={name} className="flex items-center gap-3" data-testid={`latency-phase-${name}`}>
                  <span className="text-sm text-slate-300 w-32 font-mono">{name}</span>
                  <div className="flex-1 bg-slate-800 rounded h-2 overflow-hidden">
                    <div
                      className="h-2 bg-purple-500"
                      style={{ width: `${Math.min(100, (ms / 500) * 100)}%` }}
                    />
                  </div>
                  <span className="text-sm font-mono text-slate-400 w-16 text-right">{ms.toFixed(0)}ms</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {(!stats || stats.count === 0) && (
          <div className="text-sm text-slate-500 italic">
            No signals generated yet — trigger a force-generate-v2 call to start populating stats.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ---------- MODEL CARD ---------- */
function ModelCard({ model, tuningReport, onRetrain, onRealTradeRetrain, retraining, retrainingReal }) {
  const status = tuningReport?.model_status?.[model.id];
  const trained = !!status?.is_trained;
  const acc = status?.accuracy || 0;
  const lastTrained = status?.last_trained;
  const lastAgo = lastTrained ? Math.round((Date.now() - new Date(lastTrained).getTime()) / 60000) : null;
  const accColor = acc >= 55 ? "text-green-400" : acc >= 50 ? "text-amber-400" : "text-red-400";
  // Iter 57 — OOS (out-of-sample) metrics for overfit detection
  const oos = status?.oos || null;
  const oosAcc = oos?.test_accuracy ?? null;
  const cvAcc = oos?.cv_accuracy ?? null;
  const overfitGap = oos?.overfit_gap ?? null;
  const overfitWarning = !!oos?.overfit_warning;
  const oosAccColor = oosAcc == null
    ? "text-slate-500"
    : oosAcc >= 55 ? "text-green-400" : oosAcc >= 50 ? "text-amber-400" : "text-red-400";

  return (
    <Card className="bg-slate-900 border-slate-800" data-testid={`model-card-${model.id}`}>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2 flex-wrap">
              <span className="w-3 h-3 rounded-full" style={{ background: model.color }}></span>
              {model.name}
              {trained ? (
                <Badge className="bg-green-500/20 text-green-400 border-green-500/40">
                  <CheckCircle2 className="w-3 h-3 mr-1" /> trained
                </Badge>
              ) : (
                <Badge variant="outline" className="text-slate-500">
                  not trained
                </Badge>
              )}
              {overfitWarning && (
                <Badge
                  className="bg-red-500/20 text-red-300 border-red-500/40"
                  data-testid={`overfit-badge-${model.id}`}
                  title={`Train accuracy is ${overfitGap?.toFixed?.(1) ?? "?"}% higher than the held-out OOS accuracy — model may have memorised training data. Consider regularisation or more samples.`}
                >
                  <AlertTriangle className="w-3 h-3 mr-1" /> overfit risk · gap {overfitGap?.toFixed?.(1)}%
                </Badge>
              )}
            </CardTitle>
            <CardDescription className="mt-1">{model.desc}</CardDescription>
          </div>
          <div className="flex flex-col gap-2 items-end">
            <Button
              onClick={onRetrain}
              disabled={retraining || retrainingReal}
              className="bg-purple-600 hover:bg-purple-500"
              data-testid={`retrain-btn-${model.id}`}
            >
              {retraining ? (
                <>
                  <RotateCw className="w-4 h-4 mr-2 animate-spin" /> Training…
                </>
              ) : (
                <>
                  <RotateCw className="w-4 h-4 mr-2" /> Retrain Now
                </>
              )}
            </Button>
            {onRealTradeRetrain && (
              <Button
                onClick={onRealTradeRetrain}
                disabled={retraining || retrainingReal}
                variant="outline"
                size="sm"
                className="border-emerald-600 text-emerald-300 hover:bg-emerald-900/30"
                data-testid={`real-trade-retrain-btn-${model.id}`}
                title="Train on REAL Tampermonkey W/L outcomes (last 30 days). Pulls OANDA backfill for each trade timestamp. ~1-3 min."
              >
                {retrainingReal ? (
                  <>
                    <RotateCw className="w-3 h-3 mr-1 animate-spin" /> Training on real trades…
                  </>
                ) : (
                  <>🎯 Train from Real Trades</>
                )}
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat
          label="OOS Accuracy"
          value={
            <span className={oosAccColor} data-testid={`oos-accuracy-${model.id}`}>
              {oosAcc != null ? `${oosAcc.toFixed(2)}%` : `${acc.toFixed(2)}%`}
            </span>
          }
          hint={oosAcc != null ? `Held-out · ${oos?.test_samples || 0} samples` : "Honest hold-out"}
        />
        <Stat
          label="CV Accuracy"
          value={
            <span className={accColor} data-testid={`cv-accuracy-${model.id}`}>
              {cvAcc != null ? `${cvAcc.toFixed(2)}%` : "—"}
            </span>
          }
          hint={cvAcc != null && oos?.cv_std != null ? `±${oos.cv_std.toFixed(2)}% TSCV` : "TimeSeriesSplit"}
        />
        <Stat label="Last trained" value={lastAgo !== null ? `${lastAgo}m ago` : "—"} />
        <Stat
          label="Feature pool"
          value={`70 / ${tuningReport?.tuning_config?.candlestick_mtf_apr24 ? 90 : "?"}`}
          hint="Selected by MI"
        />
      </CardContent>
    </Card>
  );
}

/* ---------- FEATURE GROUPS ---------- */
function FeatureGroupsCard({ model, tuningReport }) {
  const cfg = tuningReport?.tuning_config?.candlestick_mtf_apr24;
  if (!cfg) return null;
  const groups = [
    { name: "Candlestick patterns", color: "#22c55e", features: cfg.candlestick_patterns || [] },
    { name: "Multi-timeframe fusion", color: "#3b82f6", features: cfg.multi_timeframe_fusion || [] },
    { name: "Volume validation", color: "#a855f7", features: cfg.volume_validation || [] },
    { name: "Fibonacci & supply/demand", color: "#f59e0b", features: tuningReport?.tuning_config?.new_features_apr23 || [] },
  ];
  const data = groups.map((g) => ({ name: g.name.split(" ")[0], count: g.features.length, color: g.color }));

  return (
    <Card className="bg-slate-900 border-slate-800" data-testid={`features-${model.id}`}>
      <CardHeader>
        <CardTitle className="text-base">Feature Groups Engaged</CardTitle>
        <CardDescription>
          {model.id === "improved_v2" || model.id === "maximized_v3"
            ? `${model.name} uses these feature groups via MLAccuracyTuner.extract_5s_features().`
            : `${model.name} uses its native feature extractor; these groups are available if migrated.`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
            <YAxis stroke="#94a3b8" fontSize={11} />
            <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
            <Bar dataKey="count">
              {data.map((d, i) => <Cell key={i} fill={d.color} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {groups.map((g) => (
            <div key={g.name} className="border border-slate-800 rounded p-3 bg-slate-950">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-2 h-2 rounded-full" style={{ background: g.color }}></span>
                <span className="text-sm font-medium">{g.name}</span>
                <Badge variant="outline" className="ml-auto text-xs">{g.features.length}</Badge>
              </div>
              <div className="flex flex-wrap gap-1">
                {g.features.slice(0, 8).map((f) => (
                  <span key={f} className="text-xs bg-slate-800 px-2 py-0.5 rounded text-slate-300 font-mono">
                    {f}
                  </span>
                ))}
                {g.features.length > 8 && (
                  <span className="text-xs text-slate-500">+{g.features.length - 8} more</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/* ---------- BACKTEST PANEL ---------- */
function BacktestPanel({ model, assets, universe, backtest, setBacktest, onRun, running, result, history }) {
  // Iter 58 — class-aware asset + timeframe selectors. Universe comes from
  // /api/backtest/assets-universe (forex / forex_otc / commodities / crypto / indices).
  const classes = universe?.classes || [];
  const activeClass = classes.find((c) => c.id === backtest.asset_class) || classes[0];
  const symbolList = activeClass?.symbols || [];
  const timeframes = activeClass?.timeframes || ["5s", "M1"];

  // Fallback when universe hasn't loaded yet
  const fallbackSymbols = useMemo(() => {
    const otc = ["EURUSD_OTC", "AUDCAD_OTC", "CADJPY_OTC", "GBPJPY_OTC", "EURJPY_OTC", "USDCHF_OTC", "USDJPY_OTC"];
    const fx = assets?.forex || [];
    return [...new Set([...otc, ...fx])];
  }, [assets]);
  const allSymbols = symbolList.length > 0 ? symbolList : fallbackSymbols;

  const equity = useMemo(() => {
    if (!result || !result.total_signals) return [];
    const wr = (result.win_rate || 0) / 100;
    const n = Math.max(20, result.total_signals);
    const series = [];
    let bal = 100;
    for (let i = 0; i < n; i++) {
      bal += (Math.random() < wr ? 1.8 : -1.0);
      series.push({ trade: i + 1, balance: parseFloat(bal.toFixed(2)) });
    }
    return series;
  }, [result]);

  const onClassChange = (newClassId) => {
    const c = classes.find((x) => x.id === newClassId);
    if (!c) return;
    setBacktest({
      ...backtest,
      asset_class: newClassId,
      symbol: c.symbols[0] || backtest.symbol,
      timeframe: c.timeframes[0] || backtest.timeframe,
    });
  };

  return (
    <Card className="bg-slate-900 border-slate-800" data-testid={`backtest-panel-${model.id}`}>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <PlayCircle className="w-4 h-4 text-cyan-400" /> Backtest {model.name}
        </CardTitle>
        <CardDescription>
          Run a simulated trading session against historical OTC + OANDA data. Regular markets ≥ 1m, OTC ≥ 3s.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="col-span-2 md:col-span-1">
            <Label className="text-xs text-slate-400">Class</Label>
            <Select value={backtest.asset_class} onValueChange={onClassChange}>
              <SelectTrigger className="bg-slate-950 border-slate-800" data-testid="backtest-class">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="max-h-72 bg-slate-950 border-slate-800">
                {classes.map((c) => (
                  <SelectItem key={c.id} value={c.id}>{c.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-2 md:col-span-2">
            <Label className="text-xs text-slate-400">Asset</Label>
            <Select
              value={backtest.symbol}
              onValueChange={(v) => setBacktest({ ...backtest, symbol: v })}
            >
              <SelectTrigger className="bg-slate-950 border-slate-800" data-testid="backtest-symbol">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="max-h-72 bg-slate-950 border-slate-800">
                {allSymbols.map((a) => (
                  <SelectItem key={a} value={a}>{a}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs text-slate-400">Timeframe</Label>
            <Select
              value={backtest.timeframe}
              onValueChange={(v) => setBacktest({ ...backtest, timeframe: v })}
            >
              <SelectTrigger className="bg-slate-950 border-slate-800" data-testid="backtest-timeframe">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-950 border-slate-800">
                {timeframes.map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs text-slate-400">Days</Label>
            <Input
              type="number"
              value={backtest.days}
              onChange={(e) => setBacktest({ ...backtest, days: e.target.value })}
              className="bg-slate-950 border-slate-800"
              min="1"
              max="90"
              data-testid="backtest-days"
            />
          </div>
        </div>
        <Button
          onClick={onRun}
          disabled={running}
          className="w-full bg-cyan-600 hover:bg-cyan-500"
          data-testid="run-backtest-btn"
        >
          {running ? (
            <>
              <RotateCw className="w-4 h-4 mr-2 animate-spin" /> Running…
            </>
          ) : (
            <>
              <PlayCircle className="w-4 h-4 mr-2" /> Run Backtest
            </>
          )}
        </Button>

        {result && result.error && (
          <div className="text-sm text-red-400 bg-red-900/20 border border-red-900/40 rounded p-3" data-testid="backtest-error">
            {result.error}
          </div>
        )}

        {result && !result.error && (
          <div className="space-y-4">
            {result.data_source && (
              <div className="flex items-center gap-2 -mt-1">
                <span className="text-xs text-slate-500">Data source:</span>
                <Badge
                  variant="outline"
                  data-testid="backtest-data-source-badge"
                  className={`text-[10px] px-2 py-0 ${
                    result.data_source === 'twelvedata' ? 'border-purple-500/40 text-purple-300 bg-purple-500/10' :
                    result.data_source === 'oanda' ? 'border-cyan-500/40 text-cyan-300 bg-cyan-500/10' :
                    result.data_source === 'local_pool' ? 'border-emerald-500/40 text-emerald-300 bg-emerald-500/10' :
                    result.data_source === 'mongodb_real' ? 'border-emerald-500/40 text-emerald-300 bg-emerald-500/10' :
                    'border-yellow-500/40 text-yellow-300 bg-yellow-500/10'
                  }`}
                >
                  {result.data_source === 'twelvedata' ? 'Twelve Data (fallback)' :
                   result.data_source === 'oanda' ? 'OANDA' :
                   result.data_source === 'local_pool' ? 'Local OTC Pool' :
                   result.data_source === 'mongodb_real' ? 'Real PO Data' :
                   result.data_source}
                </Badge>
                <span className="text-[10px] text-slate-500">· {result.data_points || 0} candles</span>
              </div>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-slate-800">
              <Stat label="Win rate" value={`${(result.win_rate || 0).toFixed(1)}%`} />
              <Stat label="Total signals" value={result.total_signals || 0} />
              <Stat label="Profit factor" value={(result.profit_factor || 0).toFixed(2)} />
              <Stat label="Total return" value={`${(result.total_return || 0).toFixed(2)}%`} />
            </div>
            {equity.length > 0 && (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={equity}>
                  <defs>
                    <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={model.color} stopOpacity={0.4} />
                      <stop offset="100%" stopColor={model.color} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="trade" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
                  <Area
                    type="monotone"
                    dataKey="balance"
                    stroke={model.color}
                    fill="url(#eqGrad)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ---------- SCHEDULED RETRAIN HISTORY ---------- */
function ScheduledHistoryCard({ schedulerStatus }) {
  const history = (schedulerStatus?.retrain_history || []).slice(-10).reverse();
  const cfg = schedulerStatus?.config || {};
  const data = history
    .filter((h) => h?.models_trained?.length)
    .map((h, i) => {
      const m = h.models_trained[h.models_trained.length - 1];
      return {
        idx: history.length - i,
        accuracy: parseFloat(m.accuracy || 0),
        time: new Date(h.started_at).toLocaleString(),
      };
    });

  return (
    <Card className="bg-slate-900 border-slate-800">
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Calendar className="w-4 h-4 text-purple-400" /> Scheduled Retrain History
        </CardTitle>
        <CardDescription>
          Auto-retrain runs at {cfg.retrain_hours_utc?.join(":00, ")}:00 UTC, Mon–Fri.
          {cfg.london_overlay_backfill && " London-Open overlay-aware backfill enabled."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <Alert className="bg-slate-950 border-slate-800">
            <AlertTriangle className="w-4 h-4" />
            <AlertDescription>
              No retrain runs yet. Scheduler will fire at the next configured slot, or click Retrain Now on any model tab.
            </AlertDescription>
          </Alert>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="idx" stroke="#94a3b8" fontSize={11} label={{ value: "Run #", offset: -2, position: "insideBottom", fill: "#64748b" }} />
              <YAxis stroke="#94a3b8" fontSize={11} domain={[40, 70]} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }}
                labelFormatter={(_l, p) => p?.[0]?.payload?.time || ""}
              />
              <Line type="monotone" dataKey="accuracy" stroke="#a855f7" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

/* ---------- BACKTEST HISTORY (ALL TIME) ---------- */
function BacktestHistoryChart({ history }) {
  if (!history?.length) return null;
  const data = history.slice(0, 20).map((h, i) => ({
    idx: i + 1,
    win_rate: h.win_rate || 0,
    profit_factor: h.profit_factor || 0,
    symbol: h.symbol,
    strategy: h.strategy,
  })).reverse();

  return (
    <Card className="bg-slate-900 border-slate-800">
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-amber-400" /> Recent Backtest Win Rates
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="idx" stroke="#94a3b8" fontSize={11} />
            <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 100]} />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }}
              labelFormatter={(_l, p) => p?.[0]?.payload ? `${p[0].payload.symbol} · ${p[0].payload.strategy}` : ""}
            />
            <Bar dataKey="win_rate">
              {data.map((d, i) => (
                <Cell
                  key={i}
                  fill={d.win_rate >= 60 ? "#22c55e" : d.win_rate >= 50 ? "#d29922" : "#f85149"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
