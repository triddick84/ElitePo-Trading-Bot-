import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { X, Clock, TrendingUp, TrendingDown, Target, Zap } from 'lucide-react';

const SignalPopupNotification = ({ signal, onClose, onExecute }) => {
  const [timeLeft, setTimeLeft] = useState(0);
  const [isOptimalTime, setIsOptimalTime] = useState(false);
  const [isExpired, setIsExpired] = useState(false);

  useEffect(() => {
    let intervalId = null;
    
    // Stable calculation function that prevents jumping
    const calculateTimeLeft = () => {
      try {
        let entryTime;
        
        // Determine entry time - prefer precision_entry_time, fallback to calculated time
        if (signal?.precision_entry_time) {
          entryTime = new Date(signal.precision_entry_time);
        } else {
          // Create stable fallback time based on signal creation
          const signalTime = signal?.timestamp ? new Date(signal.timestamp) : new Date();
          
          // Consistent entry delay based on timeframe
          const entryDelays = {
            '5s': 15000,   // 15 seconds for 5s timeframe
            '15s': 20000,  // 20 seconds for 15s timeframe
            '30s': 30000,  // 30 seconds for 30s timeframe
            '1m': 45000,   // 45 seconds for 1m timeframe
            '3m': 60000,   // 60 seconds for 3m timeframe
            '5m': 90000    // 90 seconds for 5m timeframe
          };
          
          const delay = entryDelays[signal?.timeframe] || 30000;
          entryTime = new Date(signalTime.getTime() + delay);
        }
        
        // Validate timestamps to prevent errors
        if (isNaN(entryTime.getTime())) {
          console.error('Invalid entry time calculation');
          setIsExpired(true);
          return;
        }
        
        // Use performance.now() for more stable timing
        const now = Date.now();
        const entryTimeMs = entryTime.getTime();
        const diffMs = entryTimeMs - now;
        
        // Prevent timer jumping by using consistent rounding
        const diffSeconds = Math.floor(diffMs / 1000);
        
        // Only update if the value actually changed (prevents unnecessary re-renders)
        setTimeLeft(prevTime => {
          if (prevTime !== diffSeconds) {
            return diffSeconds;
          }
          return prevTime;
        });
        
        // Determine timeframe category for appropriate thresholds
        const isUltraShort = ['5s', '15s', '30s'].includes(signal?.timeframe);
        const isShort = ['1m', '3m'].includes(signal?.timeframe);
        
        let optimalStart, optimalEnd, expireAfter;
        
        if (isUltraShort) {
          // Ultra-short: tight entry window
          optimalStart = 5;   // 5 seconds before
          optimalEnd = -3;    // 3 seconds after
          expireAfter = -20;  // Expire 20 seconds after
        } else if (isShort) {
          // Short: moderate entry window
          optimalStart = 10;  // 10 seconds before
          optimalEnd = -5;    // 5 seconds after
          expireAfter = -45;  // Expire 45 seconds after
        } else {
          // Standard: generous entry window
          optimalStart = 15;  // 15 seconds before
          optimalEnd = -10;   // 10 seconds after
          expireAfter = -90;  // Expire 90 seconds after
        }
        
        // Update states only when necessary to prevent jumping
        const isOptimal = diffSeconds <= optimalStart && diffSeconds >= optimalEnd;
        const hasExpired = diffSeconds < expireAfter;
        
        setIsOptimalTime(prev => prev !== isOptimal ? isOptimal : prev);
        setIsExpired(prev => prev !== hasExpired ? hasExpired : prev);
        
      } catch (error) {
        console.error('Countdown calculation error:', error);
        setIsExpired(true);
      }
    };

    // Initial calculation
    calculateTimeLeft();
    
    // Set up interval with optimized frequency
    intervalId = setInterval(calculateTimeLeft, 1000); // Update every second for stability
    
    // Cleanup interval
    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [signal?.precision_entry_time, signal?.timestamp, signal?.timeframe]);

  useEffect(() => {
    if (isExpired) {
      const timer = setTimeout(() => {
        onClose();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [isExpired, onClose]);

  // Optimized callbacks to prevent unnecessary re-renders
  const handleClose = useCallback(() => {
    if (onClose) {
      onClose();
    }
  }, [onClose]);

  const handleExecute = useCallback(() => {
    if (onExecute) {
      onExecute(signal);
    }
  }, [onExecute, signal]);

  if (!signal) return null;

  const formatTime = (seconds) => {
    // Handle invalid input
    if (typeof seconds !== 'number' || isNaN(seconds)) {
      return '0s';
    }
    
    const isNegative = seconds < 0;
    const absSeconds = Math.abs(seconds);
    const mins = Math.floor(absSeconds / 60);
    const secs = Math.floor(absSeconds % 60);
    
    // Consistent formatting to prevent jumping
    let timeString;
    if (mins > 0) {
      timeString = `${mins}:${secs.toString().padStart(2, '0')}`;
    } else {
      timeString = `${secs}s`;
    }
    
    return isNegative ? `-${timeString}` : timeString;
  };

  // Memoized calculations to prevent unnecessary re-renders and improve performance
  const timerColor = useMemo(() => {
    if (isExpired) {
      return 'text-red-500 bg-red-500/20 border-red-500';
    }
    
    if (isOptimalTime) {
      return 'text-green-400 bg-green-500/20 border-green-400 animate-pulse';
    }
    
    // Determine warning thresholds based on timeframe
    const timeframeThresholds = {
      '5s': 8,    // 8 second warning for 5s timeframe
      '15s': 10,  // 10 second warning for 15s timeframe
      '30s': 15,  // 15 second warning for 30s timeframe
      '1m': 20,   // 20 second warning for 1m timeframe
      '3m': 30,   // 30 second warning for 3m timeframe
      '5m': 45    // 45 second warning for 5m timeframe
    };
    
    const warningThreshold = timeframeThresholds[signal?.timeframe] || 20;
    
    if (timeLeft <= warningThreshold && timeLeft > 0) {
      return 'text-yellow-400 bg-yellow-500/20 border-yellow-400';
    }
    
    if (timeLeft < 0 && !isOptimalTime) {
      return 'text-orange-400 bg-orange-500/20 border-orange-400';
    }
    
    return 'text-blue-400 bg-blue-500/20 border-blue-400';
  }, [isExpired, isOptimalTime, timeLeft, signal?.timeframe]);

  const signalIcon = useMemo(() => {
    const isBuySignal = signal?.direction === 'BUY' || signal?.direction === 'CALL';
    return isBuySignal ? (
      <TrendingUp className="w-8 h-8 text-green-400" />
    ) : (
      <TrendingDown className="w-8 h-8 text-red-400" />
    );
  }, [signal?.direction]);

  const statusMessage = useMemo(() => {
    if (isExpired) {
      return '⏰ Signal Expired';
    }
    
    if (isOptimalTime) {
      if (timeLeft > 0) {
        return '🎯 ENTRY WINDOW OPENS SOON!';
      } else if (timeLeft >= -2) {
        return '🚀 OPTIMAL ENTRY NOW!';
      } else {
        return '⚡ FINAL MOMENTS TO ENTER!';
      }
    }
    
    // Dynamic thresholds based on timeframe
    const timeframeData = {
      '5s': { warning: 8, label: '5-second' },
      '15s': { warning: 10, label: '15-second' },
      '30s': { warning: 15, label: '30-second' },
      '1m': { warning: 20, label: '1-minute' },
      '3m': { warning: 30, label: '3-minute' },
      '5m': { warning: 45, label: '5-minute' }
    };
    
    const timeframeInfo = timeframeData[signal?.timeframe] || { warning: 20, label: 'standard' };
    
    if (timeLeft <= timeframeInfo.warning && timeLeft > 0) {
      return `⚠️ ${timeframeInfo.label} entry in ${timeLeft}s`;
    }
    
    if (timeLeft < 0 && !isExpired) {
      const remainingWindow = Math.abs(timeLeft);
      return `⏳ Window closing (${remainingWindow}s past)`;
    }
    
    if (timeLeft > timeframeInfo.warning) {
      return `⏳ Preparing ${timeframeInfo.label} entry (${timeLeft}s)`;
    }
    
    return '⏳ Preparing entry...';
  }, [isExpired, isOptimalTime, timeLeft, signal?.timeframe]);

  return (
    <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-top-2 duration-500">
      <div className={`
        w-96 max-w-[90vw] bg-gradient-to-br from-slate-800/95 to-slate-900/95 
        backdrop-blur-xl border-2 rounded-xl shadow-2xl
        ${signal.market_type === 'otc' ? 'border-purple-500/50' : 'border-emerald-500/50'}
        ${isOptimalTime ? 'animate-pulse shadow-green-400/50' : ''}
      `}>
        {/* Header */}
        <div className={`
          flex items-center justify-between p-4 border-b
          ${signal.market_type === 'otc' ? 'border-purple-500/30 bg-purple-500/10' : 'border-emerald-500/30 bg-emerald-500/10'}
        `}>
          <div className="flex items-center space-x-3">
            {signal.forced_generation && <Zap className="w-5 h-5 text-yellow-400" />}
            <h3 className="font-bold text-white">
              🚀 {signal.market_type?.toUpperCase()} SIGNAL
            </h3>
            <div className={`
              px-2 py-1 rounded-full text-xs font-semibold
              ${signal.probability >= 90 ? 'bg-green-500/20 text-green-400' :
                signal.probability >= 80 ? 'bg-yellow-500/20 text-yellow-400' :
                'bg-red-500/20 text-red-400'}
            `}>
              {signal.probability}%
            </div>
          </div>
          <button 
            onClick={handleClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Signal Details */}
        <div className="p-4 space-y-4">
          {/* Asset and Direction */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {signalIcon}
              <div>
                <div className="text-xl font-bold text-white">
                  {signal.direction} {signal.symbol}
                </div>
                <div className="text-sm text-slate-400">
                  Entry: ${signal.entry_price} • {signal.expiration_minutes}min • {signal.timeframe}
                </div>
              </div>
            </div>
          </div>

          {/* Countdown Timer */}
          <div className={`
            flex items-center justify-between p-3 rounded-lg border
            ${timerColor}
          `}>
            <div className="flex items-center space-x-2">
              <Clock className="w-5 h-5" />
              <span className="font-medium">{statusMessage}</span>
            </div>
            <div className="text-2xl font-bold font-mono">
              {formatTime(timeLeft)}
            </div>
          </div>

          {/* Optimal Entry Indicator */}
          {isOptimalTime && (
            <div className="p-3 bg-gradient-to-r from-green-500/20 to-emerald-500/20 border border-green-400/50 rounded-lg animate-pulse">
              <div className="flex items-center space-x-2">
                <Target className="w-5 h-5 text-green-400" />
                <span className="text-green-400 font-semibold">EXECUTE NOW FOR MAXIMUM ACCURACY!</span>
              </div>
              <div className="text-xs text-green-300 mt-1">
                {timeLeft > 0 
                  ? `Perfect timing in ${timeLeft}s!` 
                  : Math.abs(timeLeft) <= 5 
                    ? '🎯 PERFECT TIMING NOW!' 
                    : `Window closing in ${Math.max(0, (signal?.timeframe === '5s' || signal?.timeframe === '15s' || signal?.timeframe === '30s' ? 2 : 5) + timeLeft)}s`
                }
              </div>
            </div>
          )}

          {/* Signal Quality Indicators */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-800/50 rounded-lg p-3">
              <div className="text-xs text-slate-400">Confidence</div>
              <div className="text-lg font-bold text-white">{signal.confidence_level}</div>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3">
              <div className="text-xs text-slate-400">Stake</div>
              <div className="text-lg font-bold text-white">${signal.suggested_stake}</div>
            </div>
          </div>

          {/* Action Buttons */}
          {!isExpired && (
            <div className="flex space-x-2">
              <button
                onClick={() => onExecute && onExecute(signal)}
                disabled={!isOptimalTime}
                className={`
                  flex-1 py-3 px-4 rounded-lg font-semibold transition-all
                  ${isOptimalTime 
                    ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white hover:from-green-600 hover:to-emerald-600 animate-pulse' 
                    : 'bg-slate-700 text-slate-400 cursor-not-allowed'}
                `}
              >
                {isOptimalTime ? '🎯 EXECUTE TRADE' : '⏳ Wait for Optimal Time'}
              </button>
              
              <button
                onClick={onClose}
                className="px-4 py-3 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors"
              >
                Dismiss
              </button>
            </div>
          )}

          {isExpired && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg">
              <div className="text-red-400 font-semibold">⏰ Signal Expired</div>
              <div className="text-xs text-red-300">This signal is no longer valid for trading.</div>
            </div>
          )}
        </div>

        {/* Footer with Strategy Info */}
        <div className="px-4 pb-3">
          <div className="text-xs text-slate-500 break-words">
            {signal.forced_generation && '🚀 Force Generated • '}
            Strategy: {signal.strategy_used} • 
            {signal.technical_analysis?.strategies_analyzed && ` ${signal.technical_analysis.strategies_analyzed} indicators`}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignalPopupNotification;