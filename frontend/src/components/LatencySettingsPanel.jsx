/**
 * Iter 94 — Latency Dashboard interactive settings panel.
 *
 * Exposes runtime-tunable knobs across the whole latency stack:
 *   - Signal prewarm buffer: TTL / refresh interval / active window / max combos
 *   - Adaptive offset: sample window / min samples / clamp bounds / cache TTL / default
 *   - Guardrail: throttle fraction (0-1), manual trip / release
 *
 * Every input is bounded server-side too (the backend clamps to safe ranges);
 * these client-side ranges match the server's bounds so users don't waste time
 * on invalid values.
 */
import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Slider } from "./ui/slider";
import { Input } from "./ui/input";
import { Settings2, Save, RefreshCw, Zap, Gauge, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const API = BACKEND_URL ? `${BACKEND_URL}/api` : "";

const Row = ({ label, hint, children, testId }) => (
  <div className="flex items-center justify-between gap-4 py-2" data-testid={testId}>
    <div className="min-w-0 flex-1">
      <div className="text-sm text-slate-200">{label}</div>
      {hint && <div className="text-xs text-slate-500 mt-0.5">{hint}</div>}
    </div>
    <div className="flex items-center gap-2 shrink-0">{children}</div>
  </div>
);

const NumberField = ({ value, onChange, min, max, step = 1, suffix, testId, width = "w-24" }) => (
  <div className="flex items-center gap-1.5">
    <Input
      type="number"
      value={value}
      onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
      min={min}
      max={max}
      step={step}
      className={`${width} h-8 bg-slate-900 border-slate-700 text-right font-mono text-sm`}
      data-testid={testId}
    />
    {suffix && <span className="text-xs text-slate-500 w-8">{suffix}</span>}
  </div>
);

export default function LatencySettingsPanel() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({ prewarm: false, adaptive: false, throttle: false });
  const [pw, setPw] = useState(null);
  const [ao, setAo] = useState(null);
  const [gr, setGr] = useState(null);
  // Draft values (user edits before Save)
  const [pwDraft, setPwDraft] = useState({});
  const [aoDraft, setAoDraft] = useState({});
  const [throttleDraft, setThrottleDraft] = useState(0);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/latency/runtime-settings`, { timeout: 5000 });
      const d = r.data || {};
      setPw(d.signal_prewarm);
      setAo(d.adaptive_offset);
      setGr(d.guardrail);
      setPwDraft(d.signal_prewarm || {});
      setAoDraft(d.adaptive_offset || {});
      setThrottleDraft(d.guardrail?.throttle_fraction ?? 0);
    } catch (e) {
      toast.error("Failed to load latency settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchSettings(); }, [fetchSettings]);

  const savePrewarm = async () => {
    setSaving((s) => ({ ...s, prewarm: true }));
    try {
      const r = await axios.post(`${API}/latency/runtime-settings/prewarm`, pwDraft, { timeout: 5000 });
      setPw(r.data?.signal_prewarm || pwDraft);
      setPwDraft(r.data?.signal_prewarm || pwDraft);
      toast.success("Prewarm settings saved");
    } catch (e) {
      toast.error("Failed to save prewarm settings");
    } finally {
      setSaving((s) => ({ ...s, prewarm: false }));
    }
  };

  const saveAdaptive = async () => {
    setSaving((s) => ({ ...s, adaptive: true }));
    try {
      const r = await axios.post(`${API}/latency/runtime-settings/adaptive-offset`, aoDraft, { timeout: 5000 });
      setAo(r.data?.adaptive_offset || aoDraft);
      setAoDraft(r.data?.adaptive_offset || aoDraft);
      toast.success("Adaptive-offset settings saved · cache cleared");
    } catch (e) {
      toast.error("Failed to save adaptive-offset settings");
    } finally {
      setSaving((s) => ({ ...s, adaptive: false }));
    }
  };

  const saveThrottle = async () => {
    setSaving((s) => ({ ...s, throttle: true }));
    try {
      await axios.post(
        `${API}/signals/latency-guardrail/throttle-fraction`,
        { fraction: Number(throttleDraft) },
        { timeout: 5000 },
      );
      await fetchSettings();
      toast.success(`Guardrail throttle set to ${(throttleDraft * 100).toFixed(0)}%`);
    } catch (e) {
      toast.error("Failed to update throttle");
    } finally {
      setSaving((s) => ({ ...s, throttle: false }));
    }
  };

  const forceTrip = async () => {
    try {
      await axios.post(`${API}/signals/latency-guardrail/force-trip`, {}, { timeout: 5000 });
      await fetchSettings();
      toast.success("Guardrail TRIPPED — signals gated");
    } catch (e) {
      toast.error("Failed to trip guardrail");
    }
  };

  const forceRelease = async () => {
    try {
      await axios.post(`${API}/signals/latency-guardrail/force-release`, {}, { timeout: 5000 });
      await fetchSettings();
      toast.success("Guardrail RELEASED — signals flowing");
    } catch (e) {
      toast.error("Failed to release guardrail");
    }
  };

  const pwDirty =
    pw && (
      Number(pwDraft.ttl_seconds) !== pw.ttl_seconds ||
      Number(pwDraft.refresh_interval_seconds) !== pw.refresh_interval_seconds ||
      Number(pwDraft.active_window_seconds) !== pw.active_window_seconds ||
      Number(pwDraft.max_tracked_combos) !== pw.max_tracked_combos
    );

  const aoDirty =
    ao && (
      Number(aoDraft.sample_window) !== ao.sample_window ||
      Number(aoDraft.min_samples_required) !== ao.min_samples_required ||
      Number(aoDraft.min_offset_sec) !== ao.min_offset_sec ||
      Number(aoDraft.max_offset_sec) !== ao.max_offset_sec ||
      Number(aoDraft.cache_ttl_sec) !== ao.cache_ttl_sec ||
      Number(aoDraft.default_offset_sec) !== ao.default_offset_sec
    );

  const throttleDirty = gr && Number(throttleDraft) !== gr.throttle_fraction;

  return (
    <div className="space-y-4" data-testid="latency-settings-panel">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <Settings2 className="w-5 h-5 text-cyan-400" />
          Runtime Settings
        </h3>
        <Button
          onClick={fetchSettings}
          variant="outline"
          size="sm"
          disabled={loading}
          className="border-slate-700"
          data-testid="latency-settings-refresh"
        >
          <RefreshCw className={`w-4 h-4 mr-1 ${loading ? "animate-spin" : ""}`} />
          Reload
        </Button>
      </div>

      {/* Signal prewarm settings */}
      <Card className="glass-dark border-slate-700/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base text-white flex items-center gap-2">
            <Zap className="w-4 h-4 text-cyan-400" />
            Signal Prewarm Buffer
          </CardTitle>
          <CardDescription>
            Background loop that pre-computes signals for actively-polled (asset, TF) combos.
            Serves `/signals/latest` from memory to skip the 300-1500ms enhanced_oanda hop.
          </CardDescription>
        </CardHeader>
        <CardContent className="divide-y divide-slate-800/60">
          <Row
            label="TTL"
            hint="How long a buffered signal is considered fresh"
            testId="prewarm-ttl-row"
          >
            <NumberField
              value={pwDraft.ttl_seconds ?? 3}
              onChange={(v) => setPwDraft({ ...pwDraft, ttl_seconds: v })}
              min={0.5} max={30} step={0.5} suffix="s"
              testId="prewarm-ttl-input"
            />
          </Row>
          <Row
            label="Refresh interval"
            hint="How often the background loop regenerates active combos"
            testId="prewarm-refresh-row"
          >
            <NumberField
              value={pwDraft.refresh_interval_seconds ?? 2}
              onChange={(v) => setPwDraft({ ...pwDraft, refresh_interval_seconds: v })}
              min={0.5} max={15} step={0.5} suffix="s"
              testId="prewarm-refresh-input"
            />
          </Row>
          <Row
            label="Active-combo window"
            hint="A combo is refreshed if hit in the last N seconds"
            testId="prewarm-window-row"
          >
            <NumberField
              value={pwDraft.active_window_seconds ?? 30}
              onChange={(v) => setPwDraft({ ...pwDraft, active_window_seconds: v })}
              min={5} max={600} step={5} suffix="s"
              testId="prewarm-window-input"
            />
          </Row>
          <Row
            label="Max tracked combos"
            hint="Hard cap on how many (asset, TF) pairs we keep alive"
            testId="prewarm-max-row"
          >
            <NumberField
              value={pwDraft.max_tracked_combos ?? 50}
              onChange={(v) => setPwDraft({ ...pwDraft, max_tracked_combos: v })}
              min={1} max={500} step={1}
              testId="prewarm-max-input"
            />
          </Row>
          <div className="flex items-center justify-end gap-2 pt-3">
            {pwDirty && (
              <Badge className="bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs">
                Unsaved changes
              </Badge>
            )}
            <Button
              onClick={savePrewarm}
              disabled={!pwDirty || saving.prewarm}
              size="sm"
              className="bg-cyan-600 hover:bg-cyan-500 text-white"
              data-testid="prewarm-save-btn"
            >
              <Save className="w-4 h-4 mr-1" />
              {saving.prewarm ? "Saving…" : "Save"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Adaptive offset settings */}
      <Card className="glass-dark border-slate-700/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base text-white flex items-center gap-2">
            <Gauge className="w-4 h-4 text-cyan-400" />
            Adaptive Latency Offset
          </CardTitle>
          <CardDescription>
            Per-asset TM click-delay computed from median network RTT + DOM lag reports.
            Falls back to the global default when samples are thin.
          </CardDescription>
        </CardHeader>
        <CardContent className="divide-y divide-slate-800/60">
          <Row label="Sample window" hint="How many recent samples enter the median" testId="adaptive-window-row">
            <NumberField
              value={aoDraft.sample_window ?? 50}
              onChange={(v) => setAoDraft({ ...aoDraft, sample_window: v })}
              min={5} max={500} step={5}
              testId="adaptive-window-input"
            />
          </Row>
          <Row label="Min samples required" hint="Fewer than this → global default is used" testId="adaptive-min-samples-row">
            <NumberField
              value={aoDraft.min_samples_required ?? 8}
              onChange={(v) => setAoDraft({ ...aoDraft, min_samples_required: v })}
              min={1} max={200} step={1}
              testId="adaptive-min-samples-input"
            />
          </Row>
          <Row label="Min offset clamp" hint="Lower bound (negative allowed → fire early)" testId="adaptive-min-offset-row">
            <NumberField
              value={aoDraft.min_offset_sec ?? -5}
              onChange={(v) => setAoDraft({ ...aoDraft, min_offset_sec: v })}
              min={-30} max={0} step={0.5} suffix="s"
              testId="adaptive-min-offset-input"
            />
          </Row>
          <Row label="Max offset clamp" hint="Upper bound (guardrails against absurd DOM lag samples)" testId="adaptive-max-offset-row">
            <NumberField
              value={aoDraft.max_offset_sec ?? 15}
              onChange={(v) => setAoDraft({ ...aoDraft, max_offset_sec: v })}
              min={0} max={60} step={0.5} suffix="s"
              testId="adaptive-max-offset-input"
            />
          </Row>
          <Row label="Cache TTL" hint="How long a per-asset recommendation is cached in memory" testId="adaptive-cache-row">
            <NumberField
              value={aoDraft.cache_ttl_sec ?? 30}
              onChange={(v) => setAoDraft({ ...aoDraft, cache_ttl_sec: v })}
              min={1} max={600} step={1} suffix="s"
              testId="adaptive-cache-input"
            />
          </Row>
          <Row label="Global default offset" hint="Used when an asset has < min samples" testId="adaptive-default-row">
            <NumberField
              value={aoDraft.default_offset_sec ?? 3.5}
              onChange={(v) => setAoDraft({ ...aoDraft, default_offset_sec: v })}
              min={-15} max={30} step={0.5} suffix="s"
              testId="adaptive-default-input"
            />
          </Row>
          <div className="flex items-center justify-end gap-2 pt-3">
            {aoDirty && (
              <Badge className="bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs">
                Unsaved changes · cache will clear
              </Badge>
            )}
            <Button
              onClick={saveAdaptive}
              disabled={!aoDirty || saving.adaptive}
              size="sm"
              className="bg-cyan-600 hover:bg-cyan-500 text-white"
              data-testid="adaptive-save-btn"
            >
              <Save className="w-4 h-4 mr-1" />
              {saving.adaptive ? "Saving…" : "Save"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Guardrail controls */}
      <Card className="glass-dark border-slate-700/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base text-white flex items-center gap-2">
            <ShieldAlert className={`w-4 h-4 ${gr?.tripped ? "text-rose-400" : "text-emerald-400"}`} />
            Latency Guardrail
            {gr && (
              <Badge className={gr.tripped
                ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"}
              >
                {gr.tripped ? "TRIPPED" : "RELEASED"}
              </Badge>
            )}
          </CardTitle>
          <CardDescription>
            Kills or throttles signal generation when p95 latency spikes above baseline.
            {gr && ` · ${gr.trip_count} trips / ${gr.release_count} releases lifetime.`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="text-sm text-slate-200">Throttle fraction</div>
                <div className="text-xs text-slate-500 mt-0.5">
                  0 = let everything through · 1 = abstain ALL signals when tripped
                </div>
              </div>
              <span className="font-mono text-cyan-400 text-sm" data-testid="throttle-value">
                {(throttleDraft * 100).toFixed(0)}%
              </span>
            </div>
            <Slider
              value={[throttleDraft * 100]}
              onValueChange={(v) => setThrottleDraft((v[0] ?? 0) / 100)}
              min={0} max={100} step={5}
              data-testid="throttle-slider"
            />
          </div>
          <div className="flex items-center justify-between gap-2">
            <div className="flex gap-2">
              <Button
                onClick={forceTrip}
                variant="outline"
                size="sm"
                className="border-rose-500/50 text-rose-300 hover:bg-rose-500/10"
                data-testid="guardrail-force-trip"
              >
                Force Trip
              </Button>
              <Button
                onClick={forceRelease}
                variant="outline"
                size="sm"
                className="border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/10"
                data-testid="guardrail-force-release"
              >
                Force Release
              </Button>
            </div>
            <div className="flex items-center gap-2">
              {throttleDirty && (
                <Badge className="bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs">
                  Unsaved
                </Badge>
              )}
              <Button
                onClick={saveThrottle}
                disabled={!throttleDirty || saving.throttle}
                size="sm"
                className="bg-cyan-600 hover:bg-cyan-500 text-white"
                data-testid="throttle-save-btn"
              >
                <Save className="w-4 h-4 mr-1" />
                {saving.throttle ? "Saving…" : "Save Throttle"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
