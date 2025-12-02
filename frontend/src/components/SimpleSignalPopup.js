import React, { useState, useEffect } from 'react';
import { X, Clock, TrendingUp, TrendingDown } from 'lucide-react';

const SimpleSignalPopup = ({ signal, onClose }) => {
  const [countdown, setCountdown] = useState(10);

  useEffect(() => {
    if (!signal) return;

    const calculateCountdown = () => {
      if (signal.precision_entry_time) {
        const entryTime = new Date(signal.precision_entry_time).getTime();
        const now = Date.now();
        const diff = Math.max(0, Math.floor((entryTime - now) / 1000));
        setCountdown(diff);
      } else {
        setCountdown(Math.max(0, countdown - 1));
      }
    };

    const interval = setInterval(calculateCountdown, 1000);
    return () => clearInterval(interval);
  }, [signal, countdown]);

  if (!signal) return null;

  const isCall = signal.direction === 'CALL' || signal.direction === 'BUY';
  const probability = signal.probability || 0;
  const confidence = signal.confidence_level || 'MEDIUM';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-md bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-2 border-emerald-500 rounded-xl shadow-2xl">
        {/* Header */}
        <div className={`p-4 rounded-t-xl ${
          isCall 
            ? 'bg-gradient-to-r from-green-600 to-emerald-600' 
            : 'bg-gradient-to-r from-red-600 to-rose-600'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {isCall ? (
                <TrendingUp className="w-8 h-8 text-white" />
              ) : (
                <TrendingDown className="w-8 h-8 text-white" />
              )}
              <div>
                <h2 className="text-2xl font-bold text-white">
                  {isCall ? 'CALL' : 'PUT'}
                </h2>
                <p className="text-sm text-white/90">{signal.symbol}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:bg-white/20 rounded-full p-2 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Countdown */}
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <Clock className="w-5 h-5 text-emerald-400" />
              <span className="text-sm text-slate-400">Entry Countdown</span>
            </div>
            <div className={`text-6xl font-mono font-bold ${
              countdown <= 3 ? 'text-green-400 animate-pulse' : 'text-white'
            }`}>
              {countdown}s
            </div>
            {countdown <= 3 && countdown > 0 && (
              <div className="mt-2 text-green-400 font-bold animate-pulse">
                ⚡ ENTER NOW!
              </div>
            )}
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-800/50 p-4 rounded-lg text-center">
              <div className="text-sm text-slate-400 mb-1">Accuracy</div>
              <div className={`text-2xl font-bold ${
                probability >= 85 ? 'text-green-400' :
                probability >= 75 ? 'text-yellow-400' : 'text-orange-400'
              }`}>
                {probability.toFixed(1)}%
              </div>
            </div>
            <div className="bg-slate-800/50 p-4 rounded-lg text-center">
              <div className="text-sm text-slate-400 mb-1">Confidence</div>
              <div className={`text-lg font-bold ${
                confidence === 'HIGH' ? 'text-green-400' :
                confidence === 'MEDIUM' ? 'text-yellow-400' : 'text-orange-400'
              }`}>
                {confidence}
              </div>
            </div>
          </div>

          {/* Info */}
          <div className="bg-slate-800/30 p-3 rounded-lg space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Timeframe:</span>
              <span className="text-white font-medium">{signal.timeframe || '1m'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Expiry:</span>
              <span className="text-white font-medium">{signal.expiration_minutes || 1}m</span>
            </div>
            {signal.technical_analysis?.primary_strategy && (
              <div className="flex justify-between">
                <span className="text-slate-400">Strategy:</span>
                <span className="text-blue-300 font-medium text-xs">
                  {signal.technical_analysis.primary_strategy}
                </span>
              </div>
            )}
          </div>

          {/* Action Button */}
          <button
            onClick={onClose}
            className={`w-full py-4 rounded-lg font-bold text-white text-lg transition ${
              countdown <= 3 && countdown > 0
                ? 'bg-gradient-to-r from-green-500 to-emerald-500 animate-pulse shadow-lg shadow-green-500/50'
                : 'bg-gradient-to-r from-emerald-600 to-blue-600 hover:from-emerald-700 hover:to-blue-700'
            }`}
          >
            {countdown === 0 ? 'Close' : 'Execute Trade'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SimpleSignalPopup;
