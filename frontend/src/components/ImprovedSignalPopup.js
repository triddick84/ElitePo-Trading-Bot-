import React, { useState, useEffect } from 'react';
import { X, ChevronDown, ChevronUp, Clock, TrendingUp, TrendingDown, Target, Zap, Calendar } from 'lucide-react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Progress } from './ui/progress';

const ImprovedSignalPopup = ({ signals, onClose, onDismiss }) => {
  console.log('🎨 ImprovedSignalPopup rendering with signals:', signals?.length);
  
  const [signalTimers, setSignalTimers] = useState({});
  const [expandedSignals, setExpandedSignals] = useState({});

  useEffect(() => {
    // Safety check inside useEffect
    if (!signals || !Array.isArray(signals) || signals.length === 0) {
      return;
    }
    
    const interval = setInterval(() => {
      const now = Date.now();
      const newTimers = {};

      signals.forEach(signal => {
        try {
          let timeLeft = 0;

          // PRIORITY: Use countdown_duration and precision_entry_time for accurate countdown
          if (signal?.countdown_duration !== undefined && signal?.precision_entry_time) {
            const entryTime = new Date(signal.precision_entry_time);
            
            if (signal.countdown_duration === 0) {
              // Auto-generate: immediate entry
              timeLeft = (entryTime.getTime() - now) / 1000;
            } else {
              // Force generate: calculate from now to entry
              timeLeft = (entryTime.getTime() - now) / 1000;
            }
          } else if (signal?.precision_entry_time) {
            const entryTime = new Date(signal.precision_entry_time);
            const diffMs = entryTime.getTime() - now;
            timeLeft = diffMs / 1000;
          } else {
            // Fallback
            const signalTime = signal?.timestamp ? new Date(signal.timestamp) : new Date();
            const entryDelays = {
              '5s': 10000, '15s': 15000, '30s': 20000,
              '1m': 30000, '3m': 45000, '5m': 60000
            };
            const delay = entryDelays[signal?.timeframe] || 15000;
            const entryTime = new Date(signalTime.getTime() + delay);
            timeLeft = (entryTime.getTime() - now) / 1000;
          }

          newTimers[signal.id] = {
            timeLeft: Math.max(0, timeLeft),
            isExpired: timeLeft <= 0,
            isOptimal: timeLeft > 0 && timeLeft <= 3,
            progress: Math.max(0, Math.min(100, ((10 - timeLeft) / 10) * 100))
          };
        } catch (error) {
          console.error('Timer error:', error);
        }
      });

      setSignalTimers(newTimers);
    }, 100);

    return () => clearInterval(interval);
  }, [signals]);

  const toggleExpanded = (signalId) => {
    setExpandedSignals(prev => ({
      ...prev,
      [signalId]: !prev[signalId]
    }));
  };

  const formatTime = (seconds) => {
    if (seconds <= 0) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getAccuracyColor = (accuracy) => {
    if (accuracy >= 90) return 'text-emerald-400';
    if (accuracy >= 80) return 'text-green-400';
    if (accuracy >= 70) return 'text-yellow-400';
    return 'text-orange-400';
  };

  const getConfidenceColor = (level) => {
    if (level === 'HIGH') return 'bg-green-500/20 text-green-400 border-green-500';
    if (level === 'MEDIUM') return 'bg-yellow-500/20 text-yellow-400 border-yellow-500';
    return 'bg-orange-500/20 text-orange-400 border-orange-500';
  };

  console.log('✅ ImprovedSignalPopup: Rendering with', signals.length, 'signals');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <Card className="w-full max-w-3xl max-h-[90vh] overflow-y-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-2 border-emerald-500/50 shadow-2xl shadow-emerald-500/20">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-gradient-to-r from-emerald-600 to-blue-600 p-4 flex items-center justify-between border-b border-emerald-500/30">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Trading Signals Generated</h2>
              <p className="text-sm text-emerald-100">{signals.length} signal{signals.length > 1 ? 's' : ''} ready</p>
            </div>
          </div>
          <Button
            onClick={onClose}
            variant="ghost"
            className="text-white hover:bg-white/20 rounded-full p-2"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Signals */}
        <div className="p-4 space-y-3">
          {signals.map((signal) => {
            const timer = signalTimers[signal.id] || { timeLeft: 0, isExpired: false, isOptimal: false, progress: 0 };
            const assetName = signal.symbol?.replace('_regular', '')?.replace('_OTC', '') || 'Unknown';
            const marketType = signal.market_type === 'otc' ? ' (OTC)' : '';
            const isExpanded = expandedSignals[signal.id];
            
            return (
              <Card 
                key={signal.id}
                className={`
                  transition-all duration-300 overflow-hidden
                  ${timer.isExpired ? 'bg-slate-800/30 border-slate-700' : 
                    timer.isOptimal ? 'bg-gradient-to-r from-green-900/40 to-emerald-900/40 border-green-500 shadow-lg shadow-green-500/30 animate-pulse' :
                    'bg-slate-800/60 border-slate-600 hover:border-emerald-500/50'}
                `}
              >
                {/* Main Signal Info */}
                <div className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    {/* Asset & Direction */}
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-2xl">{signal.market_type === 'otc' ? '🌙' : '📊'}</span>
                        <div>
                          <h3 className="text-lg font-bold text-white">{assetName}{marketType}</h3>
                          <div className="flex items-center gap-2 text-xs text-slate-400">
                            <Calendar className="w-3 h-3" />
                            <span>{signal.timeframe || '1m'}</span>
                            <span>•</span>
                            <span>Expires: {signal.expiration_minutes}m</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Direction Badge */}
                    <div className={`
                      px-6 py-3 rounded-xl font-bold text-lg flex items-center gap-2 shadow-lg
                      ${signal.direction === 'BUY' || signal.direction === 'CALL' 
                        ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white shadow-green-500/50' 
                        : 'bg-gradient-to-r from-red-500 to-rose-500 text-white shadow-red-500/50'}
                    `}>
                      {signal.direction === 'BUY' || signal.direction === 'CALL' ? (
                        <>
                          <TrendingUp className="w-5 h-5" />
                          <span>CALL</span>
                        </>
                      ) : (
                        <>
                          <TrendingDown className="w-5 h-5" />
                          <span>PUT</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Countdown Timer & Progress */}
                  <div className="mb-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-emerald-400" />
                        <span className="text-sm text-slate-300">Entry Countdown</span>
                      </div>
                      <div className={`
                        text-2xl font-mono font-bold
                        ${timer.isOptimal ? 'text-green-400 animate-pulse' :
                          timer.isExpired ? 'text-slate-500' : 'text-white'}
                      `}>
                        {formatTime(timer.timeLeft)}
                      </div>
                    </div>
                    <Progress 
                      value={timer.progress} 
                      className="h-2 bg-slate-700"
                      indicatorClassName={timer.isOptimal ? 'bg-green-500' : 'bg-emerald-500'}
                    />
                    {timer.isOptimal && (
                      <div className="mt-1 text-center">
                        <span className="text-xs font-bold text-green-400 animate-pulse">
                          ⚡ ENTER NOW! Optimal Entry Window
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Accuracy & Confidence */}
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="bg-slate-900/50 p-3 rounded-lg border border-slate-700">
                      <div className="flex items-center gap-2 mb-1">
                        <Target className="w-4 h-4 text-emerald-400" />
                        <span className="text-xs text-slate-400">Accuracy</span>
                      </div>
                      <div className={`text-2xl font-bold ${getAccuracyColor(signal.probability || 0)}`}>
                        {typeof signal.probability === 'number' ? signal.probability.toFixed(1) : '0.0'}%
                      </div>
                    </div>
                    
                    <div className="bg-slate-900/50 p-3 rounded-lg border border-slate-700">
                      <div className="flex items-center gap-2 mb-1">
                        <Zap className="w-4 h-4 text-blue-400" />
                        <span className="text-xs text-slate-400">Confidence</span>
                      </div>
                      <Badge variant="outline" className={getConfidenceColor(signal.confidence_level || 'MEDIUM')}>
                        {signal.confidence_level || 'MEDIUM'}
                      </Badge>
                    </div>
                  </div>

                  {/* Strategy Display */}
                  {signal.technical_analysis?.primary_strategy && (
                    <div className="bg-blue-900/20 border border-blue-500/30 p-2 rounded-lg mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400">Strategy:</span>
                        <span className="text-sm font-semibold text-blue-300">
                          {signal.technical_analysis.primary_strategy}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Technical Analysis Toggle */}
                  {signal.technical_analysis && (
                    <Button
                      onClick={() => toggleExpanded(signal.id)}
                      variant="outline"
                      className="w-full border-slate-600 hover:bg-slate-700/50 text-slate-300"
                    >
                      <span className="flex items-center justify-between w-full">
                        <span className="flex items-center gap-2">
                          📊 Technical Analysis
                        </span>
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </span>
                    </Button>
                  )}

                  {/* Expanded Technical Analysis */}
                  {isExpanded && signal.technical_analysis && (
                    <div className="mt-3 p-3 bg-slate-900/70 rounded-lg border border-slate-700 space-y-2">
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        {signal.technical_analysis.buy_score !== undefined && (
                          <div className="flex justify-between p-2 bg-slate-800/50 rounded">
                            <span className="text-slate-400">Buy Score:</span>
                            <span className="font-semibold text-green-400">
                              {Number(signal.technical_analysis.buy_score).toFixed(1)}
                            </span>
                          </div>
                        )}
                        {signal.technical_analysis.sell_score !== undefined && (
                          <div className="flex justify-between p-2 bg-slate-800/50 rounded">
                            <span className="text-slate-400">Sell Score:</span>
                            <span className="font-semibold text-red-400">
                              {Number(signal.technical_analysis.sell_score).toFixed(1)}
                            </span>
                          </div>
                        )}
                        {signal.technical_analysis.strategies_analyzed !== undefined && (
                          <div className="flex justify-between p-2 bg-slate-800/50 rounded">
                            <span className="text-slate-400">Strategies:</span>
                            <span className="font-semibold text-blue-400">
                              {signal.technical_analysis.strategies_analyzed}
                            </span>
                          </div>
                        )}
                        {signal.technical_analysis.market_type && (
                          <div className="flex justify-between p-2 bg-slate-800/50 rounded">
                            <span className="text-slate-400">Market:</span>
                            <span className="font-semibold text-purple-400">
                              {signal.technical_analysis.market_type.toUpperCase()}
                            </span>
                          </div>
                        )}
                      </div>

                      {signal.market_analysis_summary && (
                        <div className="mt-2 p-2 bg-slate-800/30 rounded text-xs text-slate-300">
                          {signal.market_analysis_summary}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="flex gap-2 mt-3">
                    <Button
                      onClick={() => onDismiss(signal.id)}
                      variant="outline"
                      className="flex-1 border-slate-600 hover:bg-slate-700 text-slate-300"
                    >
                      Dismiss
                    </Button>
                    <Button
                      disabled={timer.isExpired}
                      className={`
                        flex-1 font-bold
                        ${timer.isOptimal 
                          ? 'bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 animate-pulse'
                          : 'bg-gradient-to-r from-emerald-600 to-blue-600 hover:from-emerald-700 hover:to-blue-700'}
                        ${timer.isExpired ? 'opacity-50 cursor-not-allowed' : ''}
                      `}
                    >
                      {timer.isExpired ? 'Expired' : timer.isOptimal ? '⚡ ENTER NOW!' : 'Execute Trade'}
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-slate-800/95 backdrop-blur-sm p-4 border-t border-slate-700">
          <div className="flex items-center justify-between text-sm text-slate-400">
            <span>💡 Enter during the green "Optimal Entry Window"</span>
            <Button onClick={onClose} variant="outline" className="border-slate-600">
              Close All
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default ImprovedSignalPopup;
