import React, { useState, useEffect } from 'react';
import { Badge } from './ui/badge';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const TradeHistoryTable = () => {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    loadHistory();
  }, [limit]);

  const loadHistory = async () => {
    try {
      const response = await axios.get(
        `${BACKEND_URL}/api/automated-trading/trade-history?limit=${limit}`
      );
      if (response.data.success) {
        setTrades(response.data.trades || []);
      }
    } catch (error) {
      console.error('Error loading trade history:', error);
    } finally {
      setLoading(false);
    }
  };

  const getResultBadge = (result) => {
    const configs = {
      'win': { class: 'bg-emerald-500/20 text-emerald-400 border-emerald-500', text: '✅ WIN' },
      'loss': { class: 'bg-red-500/20 text-red-400 border-red-500', text: '❌ LOSS' },
      'draw': { class: 'bg-gray-500/20 text-gray-400 border-gray-500', text: '➖ DRAW' },
      'pending': { class: 'bg-blue-500/20 text-blue-400 border-blue-500', text: '⏳ PENDING' }
    };
    const config = configs[result?.toLowerCase()] || configs['pending'];
    return <Badge className={config.class}>{config.text}</Badge>;
  };

  const getDirectionBadge = (direction) => {
    const colors = {
      'call': 'bg-emerald-500/20 text-emerald-400 border-emerald-500',
      'put': 'bg-red-500/20 text-red-400 border-red-500'
    };
    return colors[direction?.toLowerCase()] || colors['call'];
  };

  const formatDate = (timestamp) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return 'N/A';
    }
  };

  if (loading) {
    return <div className="text-center text-slate-400 py-8">Loading trade history...</div>;
  }

  if (trades.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400 text-lg">No trade history</p>
        <p className="text-slate-500 text-sm mt-2">
          Completed trades will appear here
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="text-left text-slate-400 text-sm font-semibold p-3">Date</th>
              <th className="text-left text-slate-400 text-sm font-semibold p-3">Asset</th>
              <th className="text-left text-slate-400 text-sm font-semibold p-3">Direction</th>
              <th className="text-right text-slate-400 text-sm font-semibold p-3">Amount</th>
              <th className="text-right text-slate-400 text-sm font-semibold p-3">Confidence</th>
              <th className="text-center text-slate-400 text-sm font-semibold p-3">Result</th>
              <th className="text-right text-slate-400 text-sm font-semibold p-3">Profit/Loss</th>
              <th className="text-left text-slate-400 text-sm font-semibold p-3">Strategy</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade, index) => (
              <tr key={index} className="border-b border-slate-800 hover:bg-slate-800/50">
                <td className="p-3">
                  <span className="text-slate-300 text-sm">
                    {formatDate(trade.timestamp)}
                  </span>
                </td>
                <td className="p-3">
                  <span className="text-white font-semibold">{trade.asset}</span>
                </td>
                <td className="p-3">
                  <Badge className={getDirectionBadge(trade.direction)}>
                    {trade.direction === 'call' ? '📈 CALL' : '📉 PUT'}
                  </Badge>
                </td>
                <td className="p-3 text-right">
                  <span className="text-white">${trade.amount?.toFixed(2)}</span>
                </td>
                <td className="p-3 text-right">
                  <span className="text-blue-400">{trade.confidence?.toFixed(0)}%</span>
                </td>
                <td className="p-3 text-center">
                  {getResultBadge(trade.result)}
                </td>
                <td className="p-3 text-right">
                  <span className={`font-semibold ${
                    trade.profit > 0 ? 'text-emerald-400' : 
                    trade.profit < 0 ? 'text-red-400' : 'text-slate-400'
                  }`}>
                    {trade.profit > 0 ? '+' : ''}${trade.profit?.toFixed(2)}
                  </span>
                </td>
                <td className="p-3">
                  <span className="text-slate-400 text-sm">{trade.strategy}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Load More Button */}
      <div className="text-center">
        <button
          onClick={() => setLimit(limit + 50)}
          className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors"
        >
          Load More
        </button>
      </div>
    </div>
  );
};

export default TradeHistoryTable;