/**
 * Iter 131 — RiskGuard: Capital-Guard-Pro-style trade sizing + session
 * discipline module.
 *
 * Panels:
 *   • Big "Minimum next trade $X.XX" card
 *   • Session progress (N/M), stop-loss, target, win-rate, account gain
 *   • Config form: capital, payout %, target, stop-loss, max trades
 *   • Record trade Win/Loss/Draw buttons
 *   • Session history table with account_gain + status pills
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Shield, TrendingUp, TrendingDown, Target, Ban, Activity, RefreshCw } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const USER_ID = 'default';

const STATUS_BADGE = {
  active:              { label: 'ACTIVE',            klass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' },
  target_reached:      { label: 'TARGET HIT',        klass: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40' },
  stop_loss_hit:       { label: 'STOP-LOSS HIT',     klass: 'bg-rose-500/20 text-rose-300 border-rose-500/40' },
  max_trades_reached:  { label: 'MAX TRADES',        klass: 'bg-amber-500/20 text-amber-300 border-amber-500/40' },
  closed:              { label: 'CLOSED',            klass: 'bg-slate-500/20 text-slate-300 border-slate-500/40' },
};

const StatTile = ({ label, value, sub, icon: Icon, tone = 'slate', testid }) => (
  <div
    data-testid={testid}
    className={`p-4 rounded-lg border bg-slate-900/40 border-slate-700/60 flex items-start gap-3`}
  >
    {Icon && (
      <div className={`p-2 rounded-md bg-${tone}-500/10 text-${tone}-300`}>
        <Icon className="w-4 h-4" />
      </div>
    )}
    <div className="flex-1 min-w-0">
      <div className="text-xs text-slate-400 uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold text-white truncate">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
    </div>
  </div>
);

const RiskGuardPage = () => {
  const [session, setSession] = useState(null);
  const [history, setHistory] = useState([]);
  const [summary, setSummary] = useState(null);
  const [calc, setCalc] = useState({ amount: null, allowed: false });

  // Config form defaults model the CapitalGuardPro reference numbers.
  const [form, setForm] = useState({
    capital: 1000, payout_pct: 0.85, target_profit: 500,
    stop_loss: 300, max_trades: 5,
  });

  const [busy, setBusy] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [s, h, sum] = await Promise.all([
        axios.get(`${API}/riskguard/session/current`, { params: { user_id: USER_ID } }),
        axios.get(`${API}/riskguard/sessions/history`, { params: { user_id: USER_ID, limit: 25 } }),
        axios.get(`${API}/riskguard/stats/summary`, { params: { user_id: USER_ID } }),
      ]);
      setSession(s.data?.session || null);
      setHistory(h.data?.sessions || []);
      setSummary(sum.data || null);
    } catch (e) {
      console.error('[RiskGuard] fetch failed', e);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 10000);
    return () => clearInterval(t);
  }, [fetchAll]);

  // Whenever the session or form changes, recalc the next-trade amount.
  const recalc = useCallback(async () => {
    const src = session || {};
    try {
      const payload = {
        capital: Number(src.capital ?? form.capital),
        payout_pct: Number(src.payout_pct ?? form.payout_pct),
        target_profit: Number(src.target_profit ?? form.target_profit),
        stop_loss: Number(src.stop_loss ?? form.stop_loss),
        max_trades: Number(src.max_trades ?? form.max_trades),
        trades_taken: Number(src.trades_taken ?? 0),
        current_pnl: Number(src.current_pnl ?? 0),
      };
      const r = await axios.post(`${API}/riskguard/calculate`, payload);
      setCalc(r.data);
    } catch (e) {
      setCalc({ amount: null, allowed: false });
    }
  }, [session, form]);

  useEffect(() => { recalc(); }, [recalc]);

  const startSession = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/riskguard/session/start`, {
        user_id: USER_ID, ...form,
      });
      if (r.data?.success) {
        toast.success('Session started — trade with discipline');
        await fetchAll();
      }
    } catch (e) {
      toast.error('Failed to start session');
    } finally { setBusy(false); }
  };

  const recordTrade = async (outcome) => {
    if (!session) return toast.error('Start a session first');
    if (!calc.allowed || !calc.amount) return toast.error(`Locked: ${calc.reason || 'session finished'}`);
    setBusy(true);
    try {
      const r = await axios.post(`${API}/riskguard/session/record-trade`, {
        user_id: USER_ID, outcome, amount: Number(calc.amount),
      });
      if (r.data?.success) {
        const s = r.data.session;
        toast.success(`${outcome.toUpperCase()} recorded · session P&L $${s.current_pnl.toFixed(2)}`);
        await fetchAll();
      } else {
        toast.error(r.data?.error || 'Record failed');
      }
    } catch (e) {
      toast.error('Failed to record trade');
    } finally { setBusy(false); }
  };

  const closeSession = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/riskguard/session/close`, { user_id: USER_ID });
      toast.success('Session closed');
      await fetchAll();
    } catch (e) {
      toast.error('Failed to close');
    } finally { setBusy(false); }
  };

  const s = session;
  const status = s?.status || 'no_session';
  const badge = STATUS_BADGE[status];
  const isActive = status === 'active';
  const isLocked = s && !isActive;

  return (
    <div className="space-y-6" data-testid="riskguard-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30">
            <Shield className="w-5 h-5 text-cyan-300" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-white">RiskGuard</h1>
            <p className="text-sm text-slate-400">Trade with a system. Protect your capital.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {badge && (
            <Badge
              data-testid="riskguard-status-badge"
              className={`border ${badge.klass}`}
            >
              {isActive && <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />}
              {badge.label}
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchAll}
            data-testid="riskguard-refresh-btn"
            className="text-slate-400 hover:text-white"
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Big Minimum Next Trade card */}
      <Card className="bg-gradient-to-br from-slate-900 via-slate-900 to-cyan-950/40 border-cyan-500/30">
        <CardContent className="p-6 md:p-8">
          <div className="text-xs uppercase tracking-widest text-cyan-300/80 mb-2">
            Minimum next trade
          </div>
          <div
            data-testid="riskguard-next-trade-amount"
            className={`text-5xl md:text-6xl font-bold ${
              calc.allowed ? 'text-white' : 'text-rose-300'
            }`}
          >
            {calc.allowed
              ? `$${Number(calc.amount || 0).toFixed(2)}`
              : (isLocked ? 'LOCKED' : '—')}
          </div>
          <div className="text-sm text-slate-400 mt-2">
            {calc.allowed
              ? 'Calculated from capital, payout, target and risk limits.'
              : (calc.reason === 'target_reached' ? '🎯 Target reached — stop trading for the day.'
                : calc.reason === 'stop_loss_hit' ? '🛑 Stop-loss hit — protect your capital, stop now.'
                : calc.reason === 'max_trades_reached' ? '⏹ Max trades reached — session complete.'
                : 'Start a session to activate risk gates.')}
          </div>
        </CardContent>
      </Card>

      {/* Live session stats — mirrors CapitalGuardPro's hero card */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatTile
          testid="riskguard-tile-session-progress"
          icon={Activity} tone="cyan"
          label="Session progress"
          value={s ? `${s.trades_taken} / ${s.max_trades}` : '—'}
        />
        <StatTile
          testid="riskguard-tile-stop-loss"
          icon={Ban} tone="rose"
          label="Stop Loss"
          value={s ? `-$${s.stop_loss.toFixed(0)}` : '—'}
        />
        <StatTile
          testid="riskguard-tile-target"
          icon={Target} tone="emerald"
          label="Target"
          value={s ? `$${s.target_profit.toFixed(0)}` : '—'}
        />
        <StatTile
          testid="riskguard-tile-win-rate"
          icon={TrendingUp} tone="emerald"
          label="Win rate"
          value={s ? `${s.win_rate.toFixed(0)}%` : '—'}
          sub={s ? `${s.wins}W / ${s.losses}L` : ''}
        />
        <StatTile
          testid="riskguard-tile-account-gain"
          icon={s && s.current_pnl >= 0 ? TrendingUp : TrendingDown}
          tone={s && s.current_pnl >= 0 ? 'emerald' : 'rose'}
          label="Account gain"
          value={s ? `${s.account_gain_pct >= 0 ? '+' : ''}${s.account_gain_pct.toFixed(1)}%` : '—'}
          sub={s ? `$${s.current_pnl >= 0 ? '+' : ''}${s.current_pnl.toFixed(2)}` : ''}
        />
      </div>

      {/* Action bar — record win/loss/draw + close */}
      <Card className="bg-slate-900/40 border-slate-700/60">
        <CardContent className="p-4 flex flex-wrap gap-2 items-center">
          <Button
            data-testid="riskguard-record-win-btn"
            disabled={!isActive || !calc.allowed || busy}
            onClick={() => recordTrade('win')}
            className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30"
          >
            <TrendingUp className="w-4 h-4 mr-1" /> Record Win
          </Button>
          <Button
            data-testid="riskguard-record-loss-btn"
            disabled={!isActive || !calc.allowed || busy}
            onClick={() => recordTrade('loss')}
            className="bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30"
          >
            <TrendingDown className="w-4 h-4 mr-1" /> Record Loss
          </Button>
          <Button
            data-testid="riskguard-record-draw-btn"
            disabled={!isActive || !calc.allowed || busy}
            onClick={() => recordTrade('draw')}
            variant="ghost"
            className="text-slate-300 border border-slate-600"
          >
            Draw
          </Button>
          <div className="flex-1" />
          {s && (
            <Button
              data-testid="riskguard-close-session-btn"
              variant="ghost"
              size="sm"
              onClick={closeSession}
              className="text-slate-400 hover:text-rose-300"
            >
              Close session
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Config form — always visible so user can retune before next session */}
      <Card className="bg-slate-900/40 border-slate-700/60">
        <CardHeader className="pb-2">
          <CardTitle className="text-base text-white flex items-center gap-2">
            Configure risk rules
            {s && (
              <span className="text-xs font-normal text-slate-400">
                (current session locked in — starting a new one supersedes it)
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { key: 'capital',       label: 'Capital ($)',   step: 10, min: 10 },
            { key: 'payout_pct',    label: 'Payout (0-1)',  step: 0.01, min: 0.1, max: 5 },
            { key: 'target_profit', label: 'Target ($)',    step: 5, min: 0 },
            { key: 'stop_loss',     label: 'Stop-loss ($)', step: 5, min: 0 },
            { key: 'max_trades',    label: 'Max trades',    step: 1, min: 1, max: 200 },
          ].map(field => (
            <div key={field.key}>
              <Label className="text-xs text-slate-400">{field.label}</Label>
              <Input
                data-testid={`riskguard-cfg-${field.key}`}
                type="number"
                value={form[field.key]}
                min={field.min}
                max={field.max}
                step={field.step}
                onChange={(e) => setForm(f => ({ ...f, [field.key]: parseFloat(e.target.value) || f[field.key] }))}
                className="h-9 bg-slate-800 border-slate-700 text-white"
              />
            </div>
          ))}
          <div className="col-span-2 md:col-span-5 flex justify-end">
            <Button
              data-testid="riskguard-start-session-btn"
              onClick={startSession}
              disabled={busy}
              className="bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30"
            >
              {s ? 'Start new session' : 'Start session'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Session history */}
      <Card className="bg-slate-900/40 border-slate-700/60">
        <CardHeader className="pb-2">
          <CardTitle className="text-base text-white flex items-center justify-between">
            <span>Session history</span>
            {summary && (
              <span className="text-xs font-normal text-slate-400">
                {summary.total_sessions} sessions · WR {summary.win_rate.toFixed(1)}% ·
                P&L ${summary.total_pnl.toFixed(2)}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {history.length === 0 ? (
            <div className="text-sm text-slate-500 py-6 text-center">
              No sessions yet — start your first one above.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="riskguard-history-table">
                <thead>
                  <tr className="text-xs uppercase tracking-wide text-slate-500 border-b border-slate-700">
                    <th className="text-left py-2">Started</th>
                    <th className="text-right">Trades</th>
                    <th className="text-right">W/L</th>
                    <th className="text-right">P&L</th>
                    <th className="text-right">Gain %</th>
                    <th className="text-right">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(row => {
                    const badge2 = STATUS_BADGE[row.status] || STATUS_BADGE.closed;
                    return (
                      <tr key={row.id} className="border-b border-slate-800/60 hover:bg-slate-800/30">
                        <td className="py-2 text-slate-300">
                          {row.started_at ? new Date(row.started_at).toLocaleString() : '—'}
                        </td>
                        <td className="text-right text-slate-200">{row.trades_taken}/{row.max_trades}</td>
                        <td className="text-right text-slate-200">{row.wins}/{row.losses}</td>
                        <td className={`text-right font-medium ${row.current_pnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                          ${row.current_pnl.toFixed(2)}
                        </td>
                        <td className={`text-right ${row.account_gain_pct >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                          {row.account_gain_pct >= 0 ? '+' : ''}{row.account_gain_pct.toFixed(1)}%
                        </td>
                        <td className="text-right">
                          <Badge className={`border ${badge2.klass} text-[10px]`}>{badge2.label}</Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default RiskGuardPage;
