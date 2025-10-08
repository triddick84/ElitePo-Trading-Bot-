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
        
        // Determine entry time with proper future timing for ultra-short timeframes
        let needsCorrection = false;
        
        if (signal?.precision_entry_time) {
          entryTime = new Date(signal.precision_entry_time);
          
          // Check if precision_entry_time is already in the past (common with force signals)
          const now = Date.now();
          const timeDiff = entryTime.getTime() - now;
          
          // If time is in the past or too close (less than 5 seconds), we need to correct it
          if (timeDiff < 5000) {
            needsCorrection = true;
            console.log('Correcting past precision_entry_time for ultra-short timeframe:', {
              originalTime: entryTime.toISOString(),
              timeframe: signal.timeframe,
              diffMs: timeDiff
            });
          }
        } else {
          needsCorrection = true;
        }
        
        if (needsCorrection) {
          // Create proper future entry time based on signal creation + appropriate delay
          const signalTime = signal?.timestamp ? new Date(signal.timestamp) : new Date();
          const currentTime = Date.now();
          
          // Use current time if signal time is also in the past
          const baseTime = Math.max(signalTime.getTime(), currentTime);
          
          // Enhanced entry delays for ultra-short timeframes to ensure positive countdown
          const entryDelays = {
            '5s': 25000,   // 25 seconds for 5s timeframe - more time to prepare
            '15s': 30000,  // 30 seconds for 15s timeframe
            '30s': 35000,  // 35 seconds for 30s timeframe
            '1m': 45000,   // 45 seconds for 1m timeframe
            '3m': 60000,   // 60 seconds for 3m timeframe
            '5m': 90000    // 90 seconds for 5m timeframe
          };
          
          const delay = entryDelays[signal?.timeframe] || 30000;
          entryTime = new Date(baseTime + delay);
          
          console.log('Created corrected entry time:', {
            timeframe: signal.timeframe,
            baseTime: new Date(baseTime).toISOString(),
            delay: delay / 1000 + 's',
            newEntryTime: entryTime.toISOString()
          });
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
          // Ultra-short: precise but not too tight entry window
          optimalStart = 8;   // 8 seconds before entry time
          optimalEnd = -2;    // 2 seconds after entry time
          expireAfter = -15;  // Expire 15 seconds after entry
        } else if (isShort) {
          // Short: moderate entry window
          optimalStart = 10;  // 10 seconds before
          optimalEnd = -5;    // 5 seconds after
          expireAfter = -30;  // Expire 30 seconds after
        } else {
          // Standard: generous entry window
          optimalStart = 15;  // 15 seconds before
          optimalEnd = -10;   // 10 seconds after
          expireAfter = -60;  // Expire 60 seconds after
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
    
    // Enhanced status messages for ultra-short timeframes
    const timeframeData = {
      '5s': { warning: 8, label: 'Ultra-Fast 5s' },
      '15s': { warning: 10, label: 'Quick 15s' },
      '30s': { warning: 12, label: 'Fast 30s' },
      '1m': { warning: 15, label: '1-minute' },
      '3m': { warning: 20, label: '3-minute' },
      '5m': { warning: 30, label: '5-minute' }
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
      return `⏳ Preparing ${timeframeInfo.label} entry`;
    }
    
    return '⏳ Preparing entry...';
  }, [isExpired, isOptimalTime, timeLeft, signal?.timeframe]);

  // Get direction display with emoji and color
  const getDirectionDisplay = () => {
    const isBuy = signal.direction === 'BUY' || signal.direction === 'CALL';
    return isBuy ? '🟢⬆️ UP' : '🔴⬇️ DOWN';
  };

  // Get asset display with appropriate emoji
  const getAssetDisplay = () => {
    const marketEmoji = signal.market_type === 'otc' ? '📈' : '📊';
    const assetName = signal.symbol?.replace('_regular', '')?.replace('_OTC', '') || 'Unknown';
    const marketType = signal.market_type === 'otc' ? ' OTC' : '';
    return `${marketEmoji} Asset: ${assetName}${marketType}`;
  };

  // Get duration display
  const getDurationDisplay = () => {
    const timeframe = signal.timeframe || '1m';
    const expiration = signal.expiration_minutes || 5;
    
    // Convert timeframe to readable format
    let durationText;
    if (timeframe.includes('s')) {
      durationText = `${timeframe.replace('s', '')} Second${timeframe === '1s' ? '' : 's'}`;
    } else if (timeframe.includes('m')) {
      durationText = `${timeframe.replace('m', '')} Minute${timeframe === '1m' ? '' : 's'}`;
    } else {
      durationText = `${expiration} Minute${expiration === 1 ? '' : 's'}`;
    }
    
    return `⏳ Duration: ${durationText}`;
  };

  return (
    <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-top-2 duration-500">
      <div className={`
        w-80 max-w-[90vw] bg-gradient-to-br from-slate-800/95 to-slate-900/95 
        backdrop-blur-xl border-2 rounded-xl shadow-2xl
        ${signal.market_type === 'otc' ? 'border-purple-500/50' : 'border-emerald-500/50'}
        ${isOptimalTime ? 'animate-pulse shadow-green-400/50' : ''}
      `}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700/50">
          <h2 className="text-lg font-bold text-white">🚀 Trading Alert:</h2>
          <button 
            onClick={handleClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Main Content */}
        <div className="p-4 space-y-3">
          {/* Asset */}
          <div className="text-white font-medium">
            {getAssetDisplay()}
          </div>

          {/* Direction */}
          <div className="text-lg font-bold">
            {getDirectionDisplay()}
          </div>

          {/* Duration */}
          <div className="text-white font-medium">
            {getDurationDisplay()}
          </div>

          {/* Accuracy */}
          <div className="text-white font-medium">
            🏆 Accuracy: {signal.probability}%
          </div>

          {/* Trading Tips Section */}
          <div className="mt-4 p-3 bg-slate-700/30 rounded-lg border border-slate-600/50">
            <div className="text-white font-bold mb-2">🚦 Trading Tips:</div>
            <div className="text-sm text-slate-300 space-y-1">
              <div>👁‍🗨 Wait for the Start! signal,</div>
              <div>Have countdown timer to countdown to the precise entry time for maximum accuracy</div>
            </div>
          </div>

          {/* Countdown Timer */}
          <div className={`
            p-3 rounded-lg border text-center
            ${timerColor}
          `}>
            <div className="flex items-center justify-center space-x-2 mb-1">
              <Clock className="w-4 h-4" />
              <span className="text-sm font-medium">{statusMessage}</span>
            </div>
            <div className="text-3xl font-bold font-mono">
              {formatTime(timeLeft)}
            </div>
            {isOptimalTime && (
              <div className="text-sm mt-1 text-green-300 animate-pulse">
                🎯 START! OPTIMAL ENTRY NOW!
              </div>
            )}
          </div>

          {/* Entry Price and Stake Info */}
          <div className="flex justify-between text-sm text-slate-400">
            <span>Entry: ${signal.entry_price}</span>
            <span>Stake: ${signal.suggested_stake}</span>
          </div>

          {/* Action Buttons */}
          {!isExpired && (
            <div className="flex space-x-2 mt-4">
              <button
                onClick={handleExecute}
                disabled={!isOptimalTime}
                className={`
                  flex-1 py-3 px-4 rounded-lg font-semibold transition-all text-sm
                  ${isOptimalTime 
                    ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white hover:from-green-600 hover:to-emerald-600 animate-pulse' 
                    : 'bg-slate-700 text-slate-400 cursor-not-allowed'}
                `}
              >
                {isOptimalTime ? '🚀 EXECUTE NOW' : '⏳ Wait for Start!'}
              </button>
              
              <button
                onClick={handleClose}
                className="px-4 py-3 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors text-sm"
              >
                Dismiss
              </button>
            </div>
          )}

          {isExpired && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-center">
              <div className="text-red-400 font-semibold">⏰ Signal Expired</div>
              <div className="text-xs text-red-300 mt-1">This signal is no longer valid for trading.</div>
            </div>
          )}
        </div>

        {/* Footer */}
        {signal.forced_generation && (
          <div className="px-4 pb-3">
            <div className="text-xs text-slate-500 text-center">
              🚀 Force Generated • Maximum Analysis Applied
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SignalPopupNotification;