import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { TrendingUp, TrendingDown, Minus, RefreshCw } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const classifyRate = (rate) => {
  if (rate === null || rate === undefined) return { label: 'NO DATA', color: 'slate', Icon: Minus };
  if (rate >= 65) return { label: 'STRONG', color: 'emerald', Icon: TrendingUp };
  if (rate >= 56) return { label: 'PROFITABLE', color: 'teal', Icon: TrendingUp };
  if (rate >= 50) return { label: 'BREAKING EVEN', color: 'amber', Icon: Minus };
  return { label: 'UNPROFITABLE', color: 'red', Icon: TrendingDown };
};

const WinRateWidget = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/signals/win-rate-stats`);
      if (res.data.success) setData(res.data);
    } catch (_e) { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 30000);
    return () => clearInterval(id);
  }, [fetchData]);

  if (!data) return null;

  const buckets = [
    { label: 'Last 50', data: data.last_50 },
    { label: 'Last 100', data: data.last_100 },
    { label: 'Last 500', data: data.last_500 },
  ];

  return (
    <Card data-testid="win-rate-widget" className="bg-slate-900/80 border border-teal-500/20 backdrop-blur-md overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-teal-600/20 to-emerald-600/20 border-b border-teal-500/20">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-teal-400" />
          <span className="text-sm font-bold text-white tracking-wide">ACTUAL WIN RATE</span>
        </div>
        <Button
          data-testid="win-rate-refresh-btn"
          size="sm"
          variant="ghost"
          onClick={fetchData}
          disabled={loading}
          className="h-6 w-6 p-0 text-teal-400 hover:text-white"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      <div className="p-4 space-y-2 text-xs">
        {data.total_with_outcome === 0 && (
          <div className="text-slate-400 text-center py-2" data-testid="win-rate-empty">
            No trades with outcome yet. Place trades with WIN/LOSS recorded to populate stats.
          </div>
        )}

        {buckets.map((b) => {
          const m = classifyRate(b.data.win_rate);
          const Icon = m.Icon;
          return (
            <div
              key={b.label}
              data-testid={`win-rate-row-${b.label.toLowerCase().replace(/\s/g, '-')}`}
              className="flex items-center justify-between bg-slate-800/50 rounded-lg p-2.5 border border-slate-700/30"
            >
              <div className="flex items-center gap-2">
                <Icon className={`w-3.5 h-3.5 text-${m.color}-400`} />
                <span className="text-slate-300 font-medium">{b.label}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-slate-400">
                  {b.data.trades} trades
                </span>
                <span className={`font-mono font-bold text-${m.color}-400`}>
                  {b.data.win_rate !== null ? `${b.data.win_rate}%` : '—'}
                </span>
                <Badge className={`text-[10px] text-${m.color}-300 bg-${m.color}-900/40 border border-${m.color}-500/40`}>
                  {m.label}
                </Badge>
              </div>
            </div>
          );
        })}

        <div className="pt-2 text-[10px] text-slate-500 leading-relaxed">
          Break-even at 80% payout: 56% win rate. Anything above is profitable. 
          {data.note && <div className="italic mt-1">{data.note}</div>}
        </div>
      </div>
    </Card>
  );
};

export default WinRateWidget;
