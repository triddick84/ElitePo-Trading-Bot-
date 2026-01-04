import React, { useState, useEffect } from 'react';
import { X, TrendingUp, TrendingDown, Target, Zap } from 'lucide-react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';

const CompactSignalPopup = ({ signals, onClose, onDismiss }) => {
  const [signalTimers, setSignalTimers] = useState({});
  const [hasPlayedEntrySound, setHasPlayedEntrySound] = useState({});

  // Play entry sound when optimal entry point is reached
  const playEntrySound = (signalId) => {
    if (hasPlayedEntrySound[signalId]) return;
    
    try {
      const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIGGSz6+ibVBEKT6Lg8rpnIgU2kdbyw3AqBSd+zPDajzsIEly06uinUxELTqXh8rppIwU0kNbwyHEpBSd+zPDajzsIE1606uqmUxAKTqTi8rppJAU0j9bwyHEpBSh+zPDajzsIE1+06uqmUxELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJgU0kdXwyHEpBSh+zO/bjzsIFF+06uqmUhELTaXh8rloJg==');
      audio.volume = 0.5;
      audio.play().catch(e => console.log('Entry sound play failed:', e));
      setHasPlayedEntrySound(prev => ({ ...prev, [signalId]: true }));
    } catch (e) {
      console.log('Entry sound error:', e);
    }
  };

  useEffect(() => {
    if (!signals || !Array.isArray(signals) || signals.length === 0) {
      return;
    }
    
    const interval = setInterval(() => {
      const now = Date.now();
      const newTimers = {};

      signals.forEach(signal => {
        try {
          let timeLeft = 0;

          if (signal?.precision_entry_time) {
            const entryTime = new Date(signal.precision_entry_time);
            timeLeft = (entryTime.getTime() - now) / 1000;
          } else if (signal?.seconds_to_entry !== undefined) {
            timeLeft = signal.seconds_to_entry - ((now - new Date(signal.timestamp).getTime()) / 1000);
          } else {
            // Fallback: 20 seconds
            const signalTime = signal?.timestamp ? new Date(signal.timestamp) : new Date();
            timeLeft = 20 - ((now - signalTime.getTime()) / 1000);
          }

          const isOptimal = timeLeft > 0 && timeLeft <= 3;
          
          // Play entry sound when reaching optimal entry window
          if (isOptimal && !hasPlayedEntrySound[signal.id]) {
            playEntrySound(signal.id);
          }

          // Calculate time since signal was created for max display time
          const signalCreatedTime = signal?.timestamp ? new Date(signal.timestamp).getTime() : now;
          const displayDuration = (now - signalCreatedTime) / 1000;
          
          // Close popup when:
          // 1. Entry time passed by 3 seconds (timeLeft <= -3), OR
          // 2. Popup has been displayed for more than 5 minutes (300 seconds) regardless of countdown
          const isExpiredByTime = timeLeft <= -3;  // Close 3 seconds after entry time
          const isExpiredByDuration = displayDuration > 300; // Max 5 minutes display
          
          newTimers[signal.id] = {
            timeLeft: timeLeft,
            isExpired: isExpiredByTime || isExpiredByDuration,
            isOptimal: isOptimal,
            progress: Math.max(0, Math.min(100, ((20 - timeLeft) / 20) * 100)),
            displayDuration: displayDuration
          };
        } catch (error) {
          console.error('Timer error:', error);
        }
      });

      setSignalTimers(newTimers);

      // Auto-close if all signals expired (entry time passed by 3s OR displayed for 5+ minutes)
      const allExpired = signals.every(s => newTimers[s.id]?.isExpired);
      if (allExpired) {
        const reason = signals.some(s => newTimers[s.id]?.displayDuration > 300) 
          ? 'max display duration reached (5 min)' 
          : 'entry time passed by 3s';
        console.log(`🔔 All signals expired (${reason}), auto-closing popup`);
        onClose();
      }
    }, 100);

    return () => clearInterval(interval);
  }, [signals, onClose]);

  const formatTime = (seconds) => {
    const isNegative = seconds < 0;
    const absSeconds = Math.abs(seconds);
    const mins = Math.floor(absSeconds / 60);
    const secs = Math.floor(absSeconds % 60);
    const sign = isNegative ? '-' : '';
    return `${sign}${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getSignalStrength = (probability, confidence) => {
    // Calculate overall strength from probability and confidence
    const probScore = probability || 75;
    const confMap = { 'HIGH': 95, 'MEDIUM': 80, 'LOW': 65 };
    const confScore = confMap[confidence] || 75;
    return (probScore + confScore) / 2;
  };

  const getHeatmapColor = (strength) => {
    if (strength >= 90) return 'bg-gradient-to-r from-green-500 to-emerald-600';
    if (strength >= 80) return 'bg-gradient-to-r from-green-400 to-green-500';
    if (strength >= 75) return 'bg-gradient-to-r from-yellow-400 to-green-400';
    if (strength >= 70) return 'bg-gradient-to-r from-orange-400 to-yellow-400';
    return 'bg-gradient-to-r from-red-400 to-orange-400';
  };

  const getStrengthLabel = (strength) => {
    if (strength >= 90) return '🔥 VERY STRONG';
    if (strength >= 80) return '💪 STRONG';
    if (strength >= 75) return '👍 GOOD';
    if (strength >= 70) return '⚠️ MODERATE';
    return '⚡ WEAK';
  };

  if (!signals || !Array.isArray(signals) || signals.length === 0) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-2 sm:p-4 bg-black/70 backdrop-blur-sm">
      <Card className="w-full max-w-sm bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-2 border-emerald-500/50 shadow-2xl shadow-emerald-500/20">
        {/* Compact Header */}
        <div className="bg-gradient-to-r from-emerald-600 to-blue-600 p-2 flex items-center justify-between border-b border-emerald-500/30">
          <div className="flex items-center gap-1.5">
            <Zap className="w-4 h-4 text-white" />
            <h2 className="text-base font-bold text-white">Signal Ready</h2>
          </div>
          <Button
            onClick={onClose}
            variant="ghost"
            className="text-white hover:bg-white/20 rounded-full p-1 h-7 w-7"
          >
            <X className="w-3.5 h-3.5" />
          </Button>
        </div>

        {/* Compact Signals */}
        <div className="p-3 space-y-2">
          {signals.map((signal) => {
            const timer = signalTimers[signal.id] || { timeLeft: 0, isExpired: false, isOptimal: false, progress: 0 };
            const assetName = signal.symbol?.replace('_regular', '')?.replace('_OTC', '') || 'Unknown';
            const marketType = signal.market_type === 'otc' ? ' (OTC)' : '';
            const strength = getSignalStrength(signal.probability, signal.confidence_level);
            
            return (
              <div 
                key={signal.id}
                className={`
                  border rounded-lg overflow-hidden transition-all
                  ${timer.isOptimal ? 'border-green-500 shadow-lg shadow-green-500/30 animate-pulse' :
                    timer.timeLeft < 0 ? 'border-slate-600 opacity-60' :
                    'border-emerald-500/50'}
                `}
              >
                {/* Signal Info - Compact */}
                <div className="p-2.5 bg-slate-800/60">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-1.5">
                      <span className="text-lg font-bold text-white">{assetName}</span>
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-slate-300 border-slate-600">
                        {signal.timeframe}{marketType}
                      </Badge>
                    </div>
                  </div>

                  {/* BUY/SELL - Compact & Prominent with Visual Effects */}
                  <div className={`
                    mb-2 p-3 rounded-lg text-center relative overflow-hidden
                    ${signal.direction === 'BUY' || signal.direction === 'CALL' 
                      ? 'bg-gradient-to-br from-green-600 to-emerald-600 shadow-lg shadow-green-500/50' 
                      : 'bg-gradient-to-br from-red-600 to-rose-600 shadow-lg shadow-red-500/50'}
                    ${timer.isOptimal ? 'animate-pulse' : ''}
                  `}>
                    {/* Animated Background Effect */}
                    <div className={`absolute inset-0 opacity-30 ${
                      timer.isOptimal ? 'animate-ping' : ''
                    }`}>
                      <div className={`w-full h-full ${
                        signal.direction === 'BUY' || signal.direction === 'CALL' 
                          ? 'bg-green-400' 
                          : 'bg-red-400'
                      }`}></div>
                    </div>
                    
                    {/* Direction Display */}
                    <div className="relative z-10 flex flex-col items-center gap-1">
                      {signal.direction === 'BUY' || signal.direction === 'CALL' ? 
                        <TrendingUp className="w-8 h-8 text-white drop-shadow-lg" /> : 
                        <TrendingDown className="w-8 h-8 text-white drop-shadow-lg" />
                      }
                      <div className="text-3xl font-black text-white drop-shadow-2xl tracking-wider">
                        {signal.direction}
                      </div>
                      {timer.isOptimal && (
                        <div className="text-[10px] font-bold text-white animate-bounce">
                          🎯 ENTER NOW!
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Countdown Timer - Compact with Entry Point Effects */}
                  <div className={`
                    text-center mb-2 p-2.5 rounded-lg relative
                    ${timer.isOptimal ? 'bg-gradient-to-r from-green-500/20 to-emerald-500/20 border-2 border-green-400 shadow-lg shadow-green-500/50' :
                      timer.timeLeft < 0 ? 'bg-red-500/10 border border-red-500/30' :
                      timer.timeLeft <= 5 ? 'bg-yellow-500/10 border border-yellow-500/30' :
                      'bg-slate-700/50 border border-slate-600'}
                  `}>
                    {/* Pulsing Ring Effect at Entry Point */}
                    {timer.isOptimal && (
                      <>
                        <div className="absolute inset-0 rounded-lg border-4 border-green-400 animate-ping opacity-75"></div>
                        <div className="absolute inset-0 rounded-lg bg-green-400/20 animate-pulse"></div>
                      </>
                    )}
                    
                    <div className="relative z-10">
                      <div className={`text-3xl font-black tracking-wider ${
                        timer.isOptimal ? 'text-green-400 animate-bounce' :
                        timer.timeLeft < 0 ? 'text-red-400' :
                        timer.timeLeft <= 5 ? 'text-yellow-400 animate-pulse' :
                        'text-white'
                      }`}>
                        {formatTime(timer.timeLeft)}
                      </div>
                      <div className={`text-xs font-bold mt-1 ${
                        timer.isOptimal ? 'text-green-300 animate-pulse' :
                        timer.timeLeft < 0 ? 'text-red-400' :
                        'text-slate-400'
                      }`}>
                        {timer.isOptimal ? '🎯 ENTER NOW!' :
                         timer.timeLeft < 0 ? '⏱️ Closed' :
                         timer.timeLeft <= 5 ? '⚡ Ready!' :
                         '⏰ Entry'}
                      </div>
                    </div>

                    {/* Entry Point Visual Indicator */}
                    {timer.isOptimal && (
                      <div className="mt-1.5 flex justify-center gap-1">
                        <span className="inline-block w-1.5 h-1.5 bg-green-400 rounded-full animate-ping"></span>
                        <span className="inline-block w-1.5 h-1.5 bg-green-400 rounded-full animate-ping" style={{animationDelay: '0.2s'}}></span>
                        <span className="inline-block w-1.5 h-1.5 bg-green-400 rounded-full animate-ping" style={{animationDelay: '0.4s'}}></span>
                      </div>
                    )}
                  </div>

                  {/* Compact Stats Row */}
                  <div className="grid grid-cols-3 gap-1.5 text-center text-[10px] mb-2">
                    <div className="bg-slate-900/50 rounded p-1">
                      <div className="text-slate-400">Prob.</div>
                      <div className="text-white font-bold text-xs">{signal.probability?.toFixed(0)}%</div>
                    </div>
                    <div className="bg-slate-900/50 rounded p-1">
                      <div className="text-slate-400">Conf.</div>
                      <div className="text-white font-bold text-xs">{signal.confidence_level}</div>
                    </div>
                    <div className="bg-slate-900/50 rounded p-1">
                      <div className="text-slate-400">Stake</div>
                      <div className="text-white font-bold text-xs">${signal.suggested_stake?.toFixed(1)}</div>
                    </div>
                  </div>

                  {/* Signal Strength Heatmap - Compact */}
                  <div className="p-1.5 bg-slate-900/50 rounded border border-slate-700">
                    <div className="flex items-center gap-1.5">
                      {/* Heatmap Bar */}
                      <div className="flex-1 h-4 bg-slate-700 rounded-full overflow-hidden">
                        <div 
                          className={`h-full ${getHeatmapColor(strength)} transition-all duration-500 flex items-center justify-center`}
                          style={{ width: `${strength}%` }}
                        >
                          <span className="text-[10px] font-bold text-white drop-shadow-lg">
                            {strength.toFixed(0)}%
                          </span>
                        </div>
                      </div>
                      {/* Strength Label */}
                      <div className="text-[10px] font-bold whitespace-nowrap">
                        {getStrengthLabel(strength)}
                      </div>
                    </div>
                  </div>

                  {/* Strategy Badge */}
                  <div className="mt-1.5 text-[10px] text-slate-400 text-center">
                    <span className="text-emerald-400">{signal.strategy_used?.replace('TradingStrategy.', '')}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer Note */}
        <div className="px-3 pb-2 text-[10px] text-slate-400 text-center">
          Auto-closes at -10s • {signals.length} signal{signals.length > 1 ? 's' : ''}
        </div>
      </Card>
    </div>
  );
};

export default CompactSignalPopup;
