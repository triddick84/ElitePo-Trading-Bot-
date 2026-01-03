import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { toast } from 'sonner';

const SignalNotification = ({ signal, onClose, onExecute }) => {
  const [timeLeft, setTimeLeft] = useState(30); // 30 second precision window
  const [isExpired, setIsExpired] = useState(false);
  const [audioEnabled, setAudioEnabled] = useState(true);

  useEffect(() => {
    // Play notification sound
    if (audioEnabled) {
      try {
        const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSWBy/LZiTYIGGa57+OZURE');
        audio.volume = 0.7;
        audio.play();
      } catch (error) {
        console.log('Audio playback not available');
      }
    }

    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          setIsExpired(true);
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    // Auto-close after expiry
    const autoClose = setTimeout(() => {
      onClose?.();
    }, 35000); // 35 seconds total (30s + 5s grace)

    return () => {
      clearInterval(timer);
      clearTimeout(autoClose);
    };
  }, [audioEnabled, onClose]);

  const getSignalColor = (direction) => {
    return direction === 'BUY' || direction === 'CALL' 
      ? 'bg-green-500/20 text-green-400 border-green-500/50'
      : 'bg-red-500/20 text-red-400 border-red-500/50';
  };

  const getTimeColor = () => {
    if (timeLeft > 20) return 'text-green-400';
    if (timeLeft > 10) return 'text-yellow-400';
    return 'text-red-400';
  };

  const formatTime = (seconds) => {
    return `${seconds.toString().padStart(2, '0')}s`;
  };

  return (
    <div className="fixed top-4 right-4 z-50 animate-slide-in" data-testid="signal-notification">
      <Card className={`p-6 glass-dark border-2 ${isExpired ? 'border-red-500/50' : 'border-emerald-500/50'} shadow-2xl max-w-md`}>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></div>
            <h4 className="text-white font-bold text-lg">🚨 TRADING SIGNAL</h4>
          </div>
          <Button
            size="sm"
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 h-6 w-6"
          >
            ✕
          </Button>
        </div>

        {/* Precision Timer */}
        <div className={`text-center p-4 rounded-xl mb-4 ${
          isExpired ? 'bg-red-500/10 border border-red-500/30' : 'bg-emerald-500/10 border border-emerald-500/30'
        }`}>
          <div className="flex items-center justify-center space-x-2 mb-2">
            <span className="text-slate-400 text-sm">Precision Entry Window</span>
            {!isExpired && <span className="w-2 h-2 bg-emerald-500 rounded-full animate-ping"></span>}
          </div>
          <div className={`text-4xl font-mono font-bold ${getTimeColor()}`}>
            {formatTime(timeLeft)}
          </div>
          {isExpired ? (
            <p className="text-red-400 text-sm mt-1">⚠️ Entry window expired</p>
          ) : (
            <p className="text-slate-300 text-sm mt-1">Optimal entry timing</p>
          )}
        </div>

        {/* Signal Details */}
        <div className="space-y-3 mb-4">
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Asset</span>
            <span className="text-white font-semibold">{signal.symbol}</span>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Direction</span>
            <Badge className={getSignalColor(signal.direction)}>
              {signal.direction === 'BUY' ? '📈 BUY/CALL' : '📉 SELL/PUT'}
            </Badge>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Entry Price</span>
            <span className="text-white font-mono">${signal.entry_price}</span>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Expiration</span>
            <span className="text-white">
              {signal.expiration_minutes < 1
                ? `${Math.round(signal.expiration_minutes * 60)}s`
                : `${signal.expiration_minutes}m`}
            </span>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Probability</span>
            <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/30">
              {signal.probability}%
            </Badge>
          </div>
        </div>

        {/* Analysis Preview */}
        <div className="p-3 bg-slate-800/30 rounded-lg mb-4">
          <p className="text-slate-400 text-xs mb-1">AI Analysis Preview</p>
          <p className="text-slate-300 text-sm line-clamp-2">
            {signal.justification?.substring(0, 100)}...
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex space-x-2">
          <Button
            onClick={() => onExecute?.(signal)}
            disabled={isExpired}
            className={`flex-1 font-semibold ${
              isExpired 
                ? 'bg-slate-600/50 text-slate-400 cursor-not-allowed' 
                : signal.direction === 'BUY'
                ? 'bg-green-500/20 text-green-400 border border-green-500/30 hover:bg-green-500/30'
                : 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30'
            }`}
          >
            {isExpired ? '⏰ Expired' : `🎯 Execute ${signal.direction}`}
          </Button>
          
          <Button
            onClick={onClose}
            className="px-4 bg-slate-600/50 text-slate-300 hover:bg-slate-600/70"
          >
            Skip
          </Button>
        </div>

        {/* Precision Indicators */}
        <div className="mt-4 pt-3 border-t border-slate-700/50">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center space-x-1">
              <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
              <span className="text-slate-400">High Confidence</span>
            </div>
            <div className="flex items-center space-x-1">
              <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
              <span className="text-slate-400">Real Market Data</span>
            </div>
            <div className="flex items-center space-x-1">
              <span className="w-2 h-2 bg-purple-500 rounded-full"></span>
              <span className="text-slate-400">AI Verified</span>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

// Notification Manager Component
const SignalNotificationManager = ({ signals = [], onSignalExecute, onSignalDismiss }) => {
  const [activeSignals, setActiveSignals] = useState([]);
  const [notificationSettings, setNotificationSettings] = useState({
    enabled: true,
    sound: true,
    desktop: true,
    precision_timer: true
  });

  useEffect(() => {
    // Request notification permission
    if ('Notification' in window && notificationSettings.desktop) {
      Notification.requestPermission();
    }
  }, [notificationSettings.desktop]);

  useEffect(() => {
    // Handle new signals
    signals.forEach(signal => {
      if (!activeSignals.find(active => active.id === signal.id)) {
        showSignalNotification(signal);
      }
    });
  }, [signals]);

  const showSignalNotification = (signal) => {
    if (!notificationSettings.enabled) return;

    // Add to active signals
    setActiveSignals(prev => [...prev, signal]);

    // Show desktop notification
    if (notificationSettings.desktop && 'Notification' in window && Notification.permission === 'granted') {
      const notification = new Notification(`Trading Signal: ${signal.symbol}`, {
        body: `${signal.direction} signal with ${signal.probability}% probability`,
        icon: '/favicon.ico',
        tag: signal.id,
        requireInteraction: true
      });

      notification.onclick = () => {
        window.focus();
        notification.close();
      };
    }

    // Show toast notification
    toast.success(`🚨 New ${signal.direction} signal for ${signal.symbol}`, {
      description: `${signal.probability}% probability • Entry: $${signal.entry_price}`,
      duration: 5000,
      action: {
        label: 'View',
        onClick: () => {
          // Focus on the popup notification
          document.querySelector('[data-testid="signal-notification"]')?.scrollIntoView();
        }
      }
    });
  };

  const handleSignalClose = (signalId) => {
    setActiveSignals(prev => prev.filter(signal => signal.id !== signalId));
    onSignalDismiss?.(signalId);
  };

  const handleSignalExecute = (signal) => {
    onSignalExecute?.(signal);
    handleSignalClose(signal.id);
    
    const expirationText = signal.expiration_minutes < 1
      ? `${Math.round(signal.expiration_minutes * 60)}s`
      : `${signal.expiration_minutes}m`;
    
    toast.success(`Trade executed: ${signal.direction} ${signal.symbol}`, {
      description: `Entry: $${signal.entry_price} • Expiration: ${expirationText}`,
      duration: 3000
    });
  };

  return (
    <div className="fixed top-0 right-0 z-50 p-4 space-y-4 pointer-events-none">
      <div className="pointer-events-auto">
        {activeSignals.slice(0, 3).map((signal, index) => (
          <div key={signal.id} style={{ marginTop: index * 10 }}>
            <SignalNotification
              signal={signal}
              onClose={() => handleSignalClose(signal.id)}
              onExecute={handleSignalExecute}
            />
          </div>
        ))}
      </div>
      
      {/* Settings Panel (Mini) */}
      {activeSignals.length > 0 && (
        <Card className="pointer-events-auto p-3 glass-dark border-slate-700/50 max-w-48">
          <div className="text-xs text-slate-400 mb-2">Notification Settings</div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-300">Sound</span>
              <input
                type="checkbox"
                checked={notificationSettings.sound}
                onChange={(e) => setNotificationSettings(prev => ({ ...prev, sound: e.target.checked }))}
                className="w-3 h-3"
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-300">Desktop</span>
              <input
                type="checkbox"
                checked={notificationSettings.desktop}
                onChange={(e) => setNotificationSettings(prev => ({ ...prev, desktop: e.target.checked }))}
                className="w-3 h-3"
              />
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};

export { SignalNotification, SignalNotificationManager };
export default SignalNotificationManager;