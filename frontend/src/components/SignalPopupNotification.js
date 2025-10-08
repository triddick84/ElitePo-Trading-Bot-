import React, { useState, useEffect } from 'react';
import { X, Clock, TrendingUp, TrendingDown, Target, Zap } from 'lucide-react';

const SignalPopupNotification = ({ signal, onClose, onExecute }) => {
  const [timeLeft, setTimeLeft] = useState(0);
  const [isOptimalTime, setIsOptimalTime] = useState(false);
  const [isExpired, setIsExpired] = useState(false);

  useEffect(() => {
    if (!signal?.precision_entry_time) {
      // If no precision entry time, create one based on signal timestamp and timeframe
      const signalTime = signal?.timestamp ? new Date(signal.timestamp) : new Date();
      
      // Calculate entry window based on timeframe
      let entryDelayMs = 30000; // Default 30 seconds
      
      if (signal?.timeframe) {
        switch (signal.timeframe) {
          case '5s':
            entryDelayMs = 10000; // 10 seconds for 5s timeframe
            break;
          case '15s':
            entryDelayMs = 15000; // 15 seconds for 15s timeframe
            break;
          case '30s':
            entryDelayMs = 25000; // 25 seconds for 30s timeframe
            break;
          case '1m':
            entryDelayMs = 45000; // 45 seconds for 1m timeframe
            break;
          default:
            entryDelayMs = 30000; // Default for other timeframes
        }
      }
      
      const fallbackEntryTime = new Date(signalTime.getTime() + entryDelayMs);
      
      const calculateFallbackTimeLeft = () => {
        const now = new Date();
        const diffMs = fallbackEntryTime.getTime() - now.getTime();
        const diffSeconds = Math.round(diffMs / 1000); // Use Math.round for better precision
        
        setTimeLeft(diffSeconds);
        
        const isUltraShort = ['5s', '15s', '30s'].includes(signal?.timeframe);
        
        if (isUltraShort) {
          setIsOptimalTime(diffSeconds <= 3 && diffSeconds >= -2);
          setIsExpired(diffSeconds < -30);
        } else {
          setIsOptimalTime(diffSeconds <= 5 && diffSeconds >= -5);
          setIsExpired(diffSeconds < -60);
        }
      };

      calculateFallbackTimeLeft();
      const interval = setInterval(calculateFallbackTimeLeft, 500); // Update every 500ms for balance
      return () => clearInterval(interval);
    }

    const calculateTimeLeft = () => {
      try {
        const now = new Date();
        const entryTime = new Date(signal.precision_entry_time);
        
        // Validate timestamps
        if (isNaN(entryTime.getTime()) || isNaN(now.getTime())) {
          console.error('Invalid timestamp in countdown calculation');
          setIsExpired(true);
          return;
        }
        
        const diffMs = entryTime.getTime() - now.getTime();
        const diffSeconds = Math.round(diffMs / 1000); // Use Math.round for better precision
        
        setTimeLeft(diffSeconds);
        
        // For ultra-short timeframes (5s, 15s, 30s), use tighter windows
        const isUltraShort = ['5s', '15s', '30s'].includes(signal.timeframe);
        
        if (isUltraShort) {
          // Ultra-short optimal window: 3 seconds before to 2 seconds after
          setIsOptimalTime(diffSeconds <= 3 && diffSeconds >= -2);
          // Expires quickly after 30 seconds
          setIsExpired(diffSeconds < -30);
        } else {
          // Standard timeframes: 5 seconds before to 5 seconds after (more forgiving)
          setIsOptimalTime(diffSeconds <= 5 && diffSeconds >= -5);
          // Expires after 90 seconds
          setIsExpired(diffSeconds < -90);
        }
        
        // Debug logging only when needed
        if (diffSeconds <= 10 && diffSeconds >= -10) {
          console.log('Countdown Debug:', {
            now: now.toISOString(),
            entryTime: entryTime.toISOString(),
            diffSeconds,
            isOptimal: diffSeconds <= (isUltraShort ? 3 : 5) && diffSeconds >= (isUltraShort ? -2 : -5),
            timeframe: signal.timeframe
          });
        }
      } catch (error) {
        console.error('Error in countdown calculation:', error);
        setIsExpired(true);
      }
    };

    calculateTimeLeft();
    const interval = setInterval(calculateTimeLeft, 500); // Update every 500ms for balance

    return () => clearInterval(interval);
  }, [signal?.precision_entry_time, signal?.timestamp, signal?.timeframe]);

  useEffect(() => {
    if (isExpired) {
      const timer = setTimeout(() => {
        onClose();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [isExpired, onClose]);

  if (!signal) return null;

  const formatTime = (seconds) => {
    const isNegative = seconds < 0;
    const absSeconds = Math.abs(seconds);
    const mins = Math.floor(absSeconds / 60);
    const secs = Math.floor(absSeconds % 60); // Use Math.floor for consistency
    
    let timeString;
    if (mins > 0) {
      timeString = `${mins}:${secs.toString().padStart(2, '0')}`;
    } else {
      timeString = `${secs}s`;
    }
    
    return isNegative ? `-${timeString}` : timeString;
  };

  const getTimerColor = () => {
    if (isExpired) return 'text-red-500 bg-red-500/20 border-red-500';
    if (isOptimalTime) return 'text-green-400 bg-green-500/20 border-green-400 animate-pulse';
    if (timeLeft <= 15) return 'text-yellow-400 bg-yellow-500/20 border-yellow-400';
    return 'text-blue-400 bg-blue-500/20 border-blue-400';
  };

  const getSignalIcon = () => {
    return signal.direction === 'BUY' ? (
      <TrendingUp className="w-8 h-8 text-green-400" />
    ) : (
      <TrendingDown className="w-8 h-8 text-red-400" />
    );
  };

  const getStatusMessage = () => {
    if (isExpired) return '⏰ Signal Expired';
    if (isOptimalTime) return '🎯 OPTIMAL ENTRY TIME!';
    if (timeLeft <= 15) return '⚠️ Entry Window Approaching';
    return '⏳ Preparing Entry...';
  };

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
            onClick={onClose}
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
              {getSignalIcon()}
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
            ${getTimerColor()}
          `}>
            <div className="flex items-center space-x-2">
              <Clock className="w-5 h-5" />
              <span className="font-medium">{getStatusMessage()}</span>
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
                Optimal entry window: {Math.abs(timeLeft) <= 5 ? 'Perfect timing!' : `${15 + timeLeft}s remaining`}
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