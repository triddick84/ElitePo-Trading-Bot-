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

          newTimers[signal.id] = {
            timeLeft: timeLeft,
            isExpired: timeLeft <= -10,  // Close at -10 seconds
            isOptimal: isOptimal,
            progress: Math.max(0, Math.min(100, ((20 - timeLeft) / 20) * 100))
          };
        } catch (error) {
          console.error('Timer error:', error);
        }
      });

      setSignalTimers(newTimers);

      // Auto-close if all signals expired past -10 seconds
      const allExpired = signals.every(s => newTimers[s.id]?.isExpired);
      if (allExpired) {
        console.log('🔔 All signals expired past -10s, auto-closing popup');
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
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <Card className="w-full max-w-md bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-2 border-emerald-500/50 shadow-2xl shadow-emerald-500/20">
        {/* Compact Header */}
        <div className="bg-gradient-to-r from-emerald-600 to-blue-600 p-3 flex items-center justify-between border-b border-emerald-500/30">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-white" />
            <h2 className="text-lg font-bold text-white">Signal Ready</h2>
          </div>
          <Button
            onClick={onClose}
            variant="ghost"
            className="text-white hover:bg-white/20 rounded-full p-1 h-8 w-8"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Compact Signals */}
        <div className="p-4 space-y-3">
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
                <div className="p-3 bg-slate-800/60">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xl font-bold text-white">{assetName}</span>
                      <Badge variant="outline" className="text-xs text-slate-300 border-slate-600">
                        {signal.timeframe}{marketType}
                      </Badge>
                    </div>
                  </div>

                  {/* BUY/SELL - Large & Prominent with Visual Effects */}
                  <div className={`
                    mb-3 p-4 rounded-lg text-center relative overflow-hidden
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
                    <div className="relative z-10 flex flex-col items-center gap-2">
                      {signal.direction === 'BUY' || signal.direction === 'CALL' ? 
                        <TrendingUp className="w-12 h-12 text-white drop-shadow-lg" /> : 
                        <TrendingDown className="w-12 h-12 text-white drop-shadow-lg" />
                      }
                      <div className="text-4xl font-black text-white drop-shadow-2xl tracking-wider">
                        {signal.direction}
                      </div>
                      {timer.isOptimal && (
                        <div className="text-xs font-bold text-white animate-bounce">
                          🎯 OPTIMAL ENTRY NOW!
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Countdown Timer - Prominent with Entry Point Effects */}
                  <div className={`
                    text-center mb-3 p-4 rounded-lg relative
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
                      <div className={`text-5xl font-black tracking-wider ${
                        timer.isOptimal ? 'text-green-400 animate-bounce' :
                        timer.timeLeft < 0 ? 'text-red-400' :
                        timer.timeLeft <= 5 ? 'text-yellow-400 animate-pulse' :
                        'text-white'
                      }`}>
                        {formatTime(timer.timeLeft)}
                      </div>
                      <div className={`text-sm font-bold mt-2 ${
                        timer.isOptimal ? 'text-green-300 animate-pulse' :
                        timer.timeLeft < 0 ? 'text-red-400' :
                        'text-slate-400'
                      }`}>
                        {timer.isOptimal ? '🎯 ENTER TRADE NOW!' :
                         timer.timeLeft < 0 ? '⏱️ Trade Window Closed' :
                         timer.timeLeft <= 5 ? '⚡ Get Ready!' :
                         '⏰ Time to Entry'}
                      </div>
                    </div>

                    {/* Entry Point Visual Indicator */}
                    {timer.isOptimal && (
                      <div className="mt-2 flex justify-center gap-1">
                        <span className="inline-block w-2 h-2 bg-green-400 rounded-full animate-ping"></span>
                        <span className="inline-block w-2 h-2 bg-green-400 rounded-full animate-ping" style={{animationDelay: '0.2s'}}></span>
                        <span className="inline-block w-2 h-2 bg-green-400 rounded-full animate-ping" style={{animationDelay: '0.4s'}}></span>
                      </div>
                    )}
                  </div>

                  {/* Compact Stats Row */}
                  <div className="grid grid-cols-3 gap-2 text-center text-xs mb-2">
                    <div>
                      <div className="text-slate-400">Probability</div>
                      <div className="text-white font-bold">{signal.probability?.toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="text-slate-400">Confidence</div>
                      <div className="text-white font-bold">{signal.confidence_level}</div>
                    </div>
                    <div>
                      <div className="text-slate-400">Stake</div>
                      <div className="text-white font-bold">${signal.suggested_stake?.toFixed(1)}</div>
                    </div>
                  </div>

                  {/* Signal Strength Heatmap */}
                  <div className="mt-3 p-2 bg-slate-900/50 rounded-lg border border-slate-700">
                    <div className="text-xs text-slate-400 mb-1 text-center">Signal Strength</div>
                    <div className="flex items-center gap-2">
                      {/* Heatmap Bar */}
                      <div className="flex-1 h-6 bg-slate-700 rounded-full overflow-hidden">
                        <div 
                          className={`h-full ${getHeatmapColor(strength)} transition-all duration-500 flex items-center justify-center`}
                          style={{ width: `${strength}%` }}
                        >
                          <span className="text-xs font-bold text-white drop-shadow-lg">
                            {strength.toFixed(0)}%
                          </span>
                        </div>
                      </div>
                      {/* Strength Label */}
                      <div className="text-xs font-bold whitespace-nowrap">
                        {getStrengthLabel(strength)}
                      </div>
                    </div>
                    
                    {/* Mini Legend */}
                    <div className="flex justify-between mt-2 text-xs text-slate-500">
                      <span>Weak</span>
                      <span>Moderate</span>
                      <span className="text-emerald-400">Strong</span>
                    </div>
                  </div>

                  {/* Strategy Badge */}
                  <div className="mt-2 text-xs text-slate-400 text-center">
                    Strategy: <span className="text-emerald-400">{signal.strategy_used?.replace('TradingStrategy.', '')}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer Note */}
        <div className="px-4 pb-3 text-xs text-slate-400 text-center">
          Popup auto-closes at -10s • {signals.length} signal{signals.length > 1 ? 's' : ''}
        </div>
      </Card>
    </div>
  );
};

export default CompactSignalPopup;
