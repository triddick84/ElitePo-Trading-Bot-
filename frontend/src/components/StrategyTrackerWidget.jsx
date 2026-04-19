import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Trophy, RefreshCw, TrendingUp, Star } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const StrategyTrackerWidget = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/signals/strategy-tracker`);
      if (res.data.success) setData(res.data);
    } catch (e) { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (!data || !data.tracker || Object.keys(data.tracker).length === 0) return null;

  const tracker = data.tracker;
  const overall = data.overall || {};

  // Sort assets by total trades descending
  const sorted = Object.entries(tracker).sort((a, b) => b[1].total_trades - a[1].total_trades);

  return (
    <Card data-testid="strategy-tracker-widget" className="bg-slate-900/80 border border-amber-500/20 backdrop-blur-md overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-amber-600/20 to-orange-600/20 border-b border-amber-500/20">
        <div className="flex items-center gap-2">
          <Trophy className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-bold text-white tracking-wide">STRATEGY TRACKER</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs text-amber-300 border-amber-500/40">{data.total_assets_tracked} Assets</Badge>
          <Button size="sm" variant="ghost" onClick={fetchData} disabled={loading} className="h-6 w-6 p-0 text-amber-400 hover:text-white">
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <div className="p-4 space-y-2">
        {/* Overall */}
        <div className="flex items-center justify-between text-xs pb-2 border-b border-slate-800">
          <span className="text-slate-400">Overall: {overall.total_trades} trades</span>
          <span className={`font-bold ${overall.win_rate >= 60 ? 'text-emerald-400' : 'text-amber-400'}`}>{overall.win_rate}% WR</span>
          <span className="text-slate-500">Sharpe: {overall.sharpe_ratio}</span>
        </div>

        {/* Per-Asset */}
        {sorted.slice(0, 6).map(([symbol, info]) => (
          <div key={symbol} className="bg-slate-800/50 rounded-lg p-2.5 border border-slate-700/30">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-medium text-white">{symbol}</span>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-bold ${info.win_rate >= 60 ? 'text-emerald-400' : info.win_rate >= 50 ? 'text-amber-400' : 'text-red-400'}`}>
                  {info.win_rate}%
                </span>
                <span className="text-[10px] text-slate-500">{info.total_trades}t</span>
                <span className={`text-[10px] font-mono ${info.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  ${info.pnl >= 0 ? '+' : ''}{info.pnl}
                </span>
              </div>
            </div>

            {/* Strategy breakdown */}
            <div className="flex flex-wrap gap-1">
              {Object.entries(info.strategies || {}).map(([strat, stats]) => {
                const isBest = strat === info.best_strategy;
                return (
                  <Badge key={strat} className={`text-[9px] px-1.5 py-0 ${isBest ? 'bg-amber-600/80 text-white' : stats.win_rate >= 60 ? 'bg-emerald-900/50 text-emerald-300 border border-emerald-500/30' : 'bg-slate-700/50 text-slate-400'}`}>
                    {isBest && <Star className="w-2 h-2 mr-0.5 inline" />}
                    {strat.replace('_', ' ')} {stats.win_rate}%
                  </Badge>
                );
              })}
            </div>

            {info.best_strategy && (
              <div className="flex items-center gap-1 mt-1">
                <TrendingUp className="w-3 h-3 text-amber-400" />
                <span className="text-[10px] text-amber-300">Best: {info.best_strategy.replace('_', ' ')} ({info.best_win_rate}%)</span>
              </div>
            )}
          </div>
        ))}

        {sorted.length > 6 && (
          <div className="text-center text-[10px] text-slate-500">+{sorted.length - 6} more assets</div>
        )}
      </div>
    </Card>
  );
};

export default StrategyTrackerWidget;
