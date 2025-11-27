import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { X, Clock, TrendingUp, TrendingDown, ChevronDown, ChevronUp } from 'lucide-react';

const ConsolidatedSignalPopup = ({ signals = [], onClose, onExecute }) => {
  const [signalTimers, setSignalTimers] = useState({});
  const [allExpired, setAllExpired] = useState(false);
  const [expandedSignals, setExpandedSignals] = useState({});

  // Initialize and update timers for all signals
  useEffect(() => {
    if (!signals || signals.length === 0) return;

    const intervalId = setInterval(() => {
      const now = Date.now();
      const newTimers = {};
      let allAreExpired = true;

      signals.forEach(signal => {
        let timeLeft = 0;
        let isExpired = false;
        
        try {
          // PRIORITY 1: Use countdown_duration for force generate (shows popup 10s before entry)
          if (signal?.countdown_duration !== undefined && signal?.popup_display_time) {
            const popupTime = new Date(signal.popup_display_time);
            const entryTime = new Date(signal.precision_entry_time);
            const countdownMs = signal.countdown_duration * 1000;
            
            // Calculate time left in the countdown (from popup display to entry)
            const timeSincePopup = now - popupTime.getTime();
            timeLeft = (countdownMs - timeSincePopup) / 1000;
            
            // If countdown_duration is 0 (auto-generate), show immediate entry
            if (signal.countdown_duration === 0) {
              timeLeft = (entryTime.getTime() - now) / 1000;
            }
          }
          // PRIORITY 2: Use backend's seconds_to_entry if available (Pocket Option synchronized)
          else if (signal?.seconds_to_entry !== undefined && signal.seconds_to_entry > 0) {
            const backendCalculatedTime = signal._calculatedEntryTime || (Date.now() + (signal.seconds_to_entry * 1000));
            if (!signal._calculatedEntryTime) {
              signal._calculatedEntryTime = backendCalculatedTime;
            }
            const diffMs = signal._calculatedEntryTime - now;
            timeLeft = diffMs / 1000;
          } 
          // PRIORITY 3: Use precision_entry_time
          else if (signal?.precision_entry_time) {
            const entryTime = new Date(signal.precision_entry_time);
            const diffMs = entryTime.getTime() - now;
            timeLeft = diffMs / 1000;
          } 
          // FALLBACK: create entry time based on signal timestamp + timeframe delay
          else {
            const signalTime = signal?.timestamp ? new Date(signal.timestamp) : new Date();
            const entryDelays = {
              '5s': 25000, '15s': 30000, '30s': 35000,
              '1m': 45000, '3m': 60000, '5m': 90000
            };
            const delay = entryDelays[signal?.timeframe] || 30000;
            const entryTime = new Date(signalTime.getTime() + delay);
            const diffMs = entryTime.getTime() - now;
            timeLeft = diffMs / 1000;
          }

          // Signal expires when timer reaches 0 or goes negative
          isExpired = timeLeft <= 0;
          
          if (!isExpired) {
            allAreExpired = false;
          }
        } catch (error) {
          console.error('Timer calculation error for signal:', signal.id, error);
          isExpired = true;
        }

        newTimers[signal.id] = {
          timeLeft,
          isExpired,
          isOptimal: timeLeft <= 5 && timeLeft >= -5
        };
      });

      setSignalTimers(newTimers);
      setAllExpired(allAreExpired);
    }, 100); // Update every 100ms for precision

    return () => clearInterval(intervalId);
  }, [signals]);

  // Auto-close when all signals expire (reach 0)
  useEffect(() => {
    if (allExpired && signals.length > 0) {
      const timer = setTimeout(() => {
        console.log('⏰ All signal timers reached 0 - auto-closing popup');
        onClose();
      }, 1000); // Close after 1 second once all reach 0
      return () => clearTimeout(timer);
    }
  }, [allExpired, onClose, signals.length]);

  const handleClose = useCallback(() => {
    if (onClose) {
      onClose();
    }
  }, [onClose]);

  const handleExecute = useCallback((signal) => {
    if (onExecute) {
      onExecute(signal);
    }
  }, [onExecute]);

  const toggleExpanded = useCallback((signalId) => {
    setExpandedSignals(prev => ({
      ...prev,
      [signalId]: !prev[signalId]
    }));
  }, []);

  // Debug signal data on mount
  useEffect(() => {
    if (signals && signals.length > 0) {
      console.log('📊 ConsolidatedSignalPopup - Signals received:', signals.map(s => ({
        id: s.id,
        symbol: s.symbol,
        direction: s.direction,
        probability: s.probability,
        confidence_level: s.confidence_level,
        timeframe: s.timeframe,
        market_type: s.market_type
      })));
    }
  }, [signals]);

  if (!signals || signals.length === 0) return null;

  const formatTime = (seconds) => {
    if (typeof seconds !== 'number' || isNaN(seconds)) {
      return '0s';
    }
    
    const isNegative = seconds < 0;
    const absSeconds = Math.abs(seconds);
    
    // Show decimal for values under 10 seconds
    if (absSeconds < 10) {
      const formatted = absSeconds.toFixed(1);
      return isNegative ? `-${formatted}s` : `${formatted}s`;
    }
    
    const mins = Math.floor(absSeconds / 60);
    const secs = Math.floor(absSeconds % 60);
    
    if (mins > 0) {
      return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    return `${secs}s`;
  };

  const getTimerColor = (timer) => {
    if (!timer) return 'text-blue-400 bg-blue-500/20 border-blue-400';
    
    if (timer.isExpired) {
      return 'text-red-500 bg-red-500/20 border-red-500';
    }
    
    if (timer.isOptimal) {
      return 'text-green-400 bg-green-500/20 border-green-400 animate-pulse';
    }
    
    if (timer.timeLeft <= 10 && timer.timeLeft > 0) {
      return 'text-yellow-400 bg-yellow-500/20 border-yellow-400';
    }
    
    return 'text-blue-400 bg-blue-500/20 border-blue-400';
  };

  const getDirectionDisplay = (direction) => {
    const isBuy = direction === 'BUY' || direction === 'CALL';
    return isBuy ? '🟢 UP' : '🔴 DOWN';
  };

  return (
    <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-top-2 duration-500">
      <div className="w-96 max-w-[90vw] bg-gradient-to-br from-slate-800/95 to-slate-900/95 backdrop-blur-xl border-2 border-emerald-500/50 rounded-xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700/50">
          <h2 className="text-lg font-bold text-white">
            🚀 Trading Alerts ({signals.length})
          </h2>
          <button 
            onClick={handleClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Signals List */}
        <div className="p-4 space-y-3 max-h-[70vh] overflow-y-auto">
          {signals.map((signal, index) => {
            const timer = signalTimers[signal.id] || { timeLeft: 0, isExpired: false, isOptimal: false };
            const assetName = signal.symbol?.replace('_regular', '')?.replace('_OTC', '') || 'Unknown';
            const marketType = signal.market_type === 'otc' ? ' OTC' : '';
            
            return (
              <div 
                key={signal.id}
                className={`
                  p-3 rounded-lg border-2 transition-all
                  ${timer.isExpired ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-700/30 border-slate-600'}
                  ${timer.isOptimal ? 'border-green-500 shadow-lg shadow-green-500/30' : ''}
                `}
              >
                {/* Asset & Direction */}
                <div className="flex items-center justify-between mb-2">
                  <div className="text-white font-bold">
                    {signal.market_type === 'otc' ? '📈' : '📊'} {assetName}{marketType}
                  </div>
                  <div className="text-lg font-bold">
                    {getDirectionDisplay(signal.direction)}
                  </div>
                </div>

                {/* Timeframe & Accuracy */}
                <div className="flex items-center justify-between text-sm text-slate-300 mb-2">
                  <span>⏱ {signal.timeframe || '1m'}</span>
                  <span className="font-bold text-emerald-400">
                    🎯 {typeof signal.probability === 'number' ? signal.probability.toFixed(1) : '0.0'}% Accuracy
                  </span>
                </div>

                {/* Confidence Level */}
                {signal.confidence_level && (
                  <div className="text-xs text-slate-400 mb-2">
                    Confidence: <span className={`font-semibold ${
                      signal.confidence_level === 'HIGH' ? 'text-green-400' :
                      signal.confidence_level === 'MEDIUM' ? 'text-yellow-400' :
                      'text-orange-400'
                    }`}>{signal.confidence_level}</span>
                  </div>
                )}

                {/* Technical Analysis Toggle */}
                {signal.technical_analysis && (
                  <div className="mb-2">
                    <button
                      onClick={() => toggleExpanded(signal.id)}
                      className="w-full flex items-center justify-between p-2 bg-slate-800/50 rounded-lg border border-slate-600/50 hover:bg-slate-700/50 transition-colors"
                    >
                      <span className="text-xs font-semibold text-emerald-400">📊 Technical Analysis</span>
                      {expandedSignals[signal.id] ? (
                        <ChevronUp className="w-4 h-4 text-slate-400" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                      )}
                    </button>
                    
                    {expandedSignals[signal.id] && (
                      <div className="mt-1 p-2 bg-slate-800/50 rounded-lg border border-slate-600/50">
                    <div className="space-y-0.5 text-xs text-slate-300">
                      {/* Strategy Used */}
                      {signal.strategy_used && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Strategy:</span>
                          <span className="font-medium text-blue-300">
                            {signal.strategy_used.replace('_', ' ').toUpperCase()}
                          </span>
                        </div>
                      )}
                      
                      {/* Buy/Sell Scores */}
                      {signal.technical_analysis.buy_score !== undefined && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Buy Score:</span>
                          <span className="font-medium text-green-400">
                            {Number(signal.technical_analysis.buy_score).toFixed(1)}
                          </span>
                        </div>
                      )}
                      {signal.technical_analysis.sell_score !== undefined && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Sell Score:</span>
                          <span className="font-medium text-red-400">
                            {Number(signal.technical_analysis.sell_score).toFixed(1)}
                          </span>
                        </div>
                      )}

                      {/* Confidence Boosters */}
                      {signal.technical_analysis.confidence_boosters_applied > 0 && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Boosters:</span>
                          <span className="font-medium text-emerald-400">
                            +{Number(signal.technical_analysis.confidence_boosters_applied).toFixed(1)}%
                          </span>
                        </div>
                      )}

                      {/* EMA Indicators */}
                      {signal.technical_analysis.ema_3 && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">EMA 3:</span>
                          <span className="font-medium">{Number(signal.technical_analysis.ema_3).toFixed(4)}</span>
                        </div>
                      )}
                      {signal.technical_analysis.ema_8 && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">EMA 8:</span>
                          <span className="font-medium">{Number(signal.technical_analysis.ema_8).toFixed(4)}</span>
                        </div>
                      )}

                      {/* RSI */}
                      {signal.technical_analysis.rsi && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">RSI:</span>
                          <span className={`font-medium ${
                            signal.technical_analysis.rsi > 70 ? 'text-red-400' :
                            signal.technical_analysis.rsi < 30 ? 'text-green-400' :
                            'text-yellow-400'
                          }`}>
                            {Number(signal.technical_analysis.rsi).toFixed(1)}
                          </span>
                        </div>
                      )}

                      {/* MACD */}
                      {signal.technical_analysis.macd_signal && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">MACD:</span>
                          <span className={`font-medium ${
                            signal.technical_analysis.macd_signal === 'bullish' ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {signal.technical_analysis.macd_signal.toUpperCase()}
                          </span>
                        </div>
                      )}

                      {/* Volume Signal */}
                      {signal.technical_analysis.volume_signal && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Volume:</span>
                          <span className="font-medium text-purple-400">
                            {signal.technical_analysis.volume_signal.toUpperCase()}
                          </span>
                        </div>
                      )}

                      {/* OTC Boost */}
                      {signal.technical_analysis.otc_boost_applied > 0 && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">OTC Boost:</span>
                          <span className="font-medium text-cyan-400">
                            +{Number(signal.technical_analysis.otc_boost_applied).toFixed(1)}%
                          </span>
                        </div>
                      )}

                      {/* Candle Sync */}
                      {signal.technical_analysis.candle_sync && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Candle Sync:</span>
                          <span className="font-medium text-green-400">✅ ACTIVE</span>
                        </div>
                      )}

                      {/* Forced Generation */}
                      {signal.technical_analysis.forced_generation && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Mode:</span>
                          <span className="font-medium text-yellow-400">🚀 FORCE</span>
                        </div>
                      )}
                    </div>

                    {/* Analysis Summary */}
                    {signal.market_analysis_summary && (
                      <div className="mt-2 pt-2 border-t border-slate-600/50">
                        <div className="text-xs text-slate-400 mb-1 font-semibold">Summary:</div>
                        <div className="text-xs text-slate-300 leading-relaxed">
                          {signal.market_analysis_summary}
                        </div>
                      </div>
                    )}

                    {/* Justification */}
                    {signal.justification && (
                      <div className="mt-2 pt-2 border-t border-slate-600/50">
                        <div className="text-xs text-slate-400 mb-1 font-semibold">Justification:</div>
                        <div className="text-xs text-slate-300 leading-relaxed">
                          {signal.justification}
                        </div>
                      </div>
                    )}
                  </div>
                    )}
                  </div>
                )}

                {/* Countdown Timer */}
                <div className={`
                  p-2 rounded-lg border text-center
                  ${getTimerColor(timer)}
                `}>
                  <div className="flex items-center justify-center space-x-2">
                    <Clock className="w-3 h-3" />
                    <span className="text-lg font-bold font-mono">
                      {formatTime(timer.timeLeft)}
                    </span>
                  </div>
                  {timer.isOptimal && (
                    <div className="text-xs mt-1 text-green-300 animate-pulse">
                      🎯 START NOW!
                    </div>
                  )}
                  {timer.isExpired && (
                    <div className="text-xs mt-1 text-red-400">
                      ⏰ Entry Time Passed
                    </div>
                  )}
                  {!timer.isExpired && !timer.isOptimal && timer.timeLeft > 0 && (
                    <div className="text-xs mt-1 text-blue-300">
                      ⏳ Wait for optimal entry
                    </div>
                  )}
                </div>

                {/* Execute Button */}
                {!timer.isExpired && timer.isOptimal && (
                  <button
                    onClick={() => handleExecute(signal)}
                    className="w-full mt-2 py-2 px-3 rounded-lg font-semibold text-sm bg-gradient-to-r from-green-500 to-emerald-500 text-white hover:from-green-600 hover:to-emerald-600 animate-pulse transition-all"
                  >
                    🚀 EXECUTE NOW
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer Info */}
        <div className="px-4 pb-3 border-t border-slate-700/50 pt-3">
          <div className="text-xs text-slate-400 text-center">
            {allExpired ? '⏰ All signals expired' : '👁 Watch for START NOW! to enter'}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConsolidatedSignalPopup;
