import React, { useState, useEffect } from 'react';
import SignalPopupNotification from './SignalPopupNotification';

const SignalNotificationManager = ({ signals = [], onSignalExecute, onSignalDismiss, notificationSettings = {} }) => {
  const [activeNotifications, setActiveNotifications] = useState([]);
  const [processedSignalIds, setProcessedSignalIds] = useState(new Set());

  useEffect(() => {
    // Process new signals for popup notifications
    if (!signals || !Array.isArray(signals)) return;

    const newSignals = signals.filter(signal => {
      // Only show popup for high-priority signals
      const isHighPriority = signal.probability >= 85 || signal.forced_generation;
      const isNewSignal = !processedSignalIds.has(signal.id);
      const isRecentSignal = signal.timestamp && 
        (Date.now() - new Date(signal.timestamp).getTime()) < 300000; // 5 minutes

      return isHighPriority && isNewSignal && isRecentSignal && notificationSettings.popupEnabled;
    });

    if (newSignals.length > 0) {
      // Add new signals to active notifications
      setActiveNotifications(prev => {
        const updated = [...prev];
        newSignals.forEach(signal => {
          // Avoid duplicates
          if (!updated.find(n => n.id === signal.id)) {
            updated.push({
              ...signal,
              notificationId: `${signal.id}_${Date.now()}`,
              showTime: Date.now()
            });
          }
        });
        // Limit to 3 active notifications
        return updated.slice(-3);
      });

      // Mark signals as processed
      setProcessedSignalIds(prev => {
        const updated = new Set(prev);
        newSignals.forEach(signal => updated.add(signal.id));
        return updated;
      });

      // Play sound notification if enabled
      if (notificationSettings.soundEnabled) {
        playNotificationSound();
      }
    }
  }, [signals, processedSignalIds, notificationSettings.popupEnabled, notificationSettings.soundEnabled]);

  const playNotificationSound = () => {
    try {
      // Create enhanced notification sound for signal alerts
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      // Create a more sophisticated notification sound
      const createTone = (frequency, startTime, duration) => {
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.setValueAtTime(frequency, startTime);
        gainNode.gain.setValueAtTime(0, startTime);
        gainNode.gain.linearRampToValueAtTime(0.3, startTime + 0.01);
        gainNode.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
        
        oscillator.start(startTime);
        oscillator.stop(startTime + duration);
      };

      // Play a sequence of tones for signal alert
      const now = audioContext.currentTime;
      createTone(800, now, 0.15);        // High tone
      createTone(600, now + 0.2, 0.15);  // Lower tone  
      createTone(800, now + 0.4, 0.15);  // High tone again
      
    } catch (error) {
      console.warn('Could not play notification sound:', error);
    }
  };

  const handleCloseNotification = (notificationId) => {
    setActiveNotifications(prev => 
      prev.filter(notification => notification.notificationId !== notificationId)
    );
    
    // Call dismiss callback if provided
    const notification = activeNotifications.find(n => n.notificationId === notificationId);
    if (notification && onSignalDismiss) {
      onSignalDismiss(notification.id);
    }
  };

  const handleExecuteSignal = (signal) => {
    // Close the notification
    handleCloseNotification(signal.notificationId);
    
    // Call execute callback if provided
    if (onSignalExecute) {
      onSignalExecute(signal);
    }
  };

  // Auto-cleanup old notifications (after 5 minutes)
  useEffect(() => {
    const cleanup = setInterval(() => {
      const now = Date.now();
      setActiveNotifications(prev => 
        prev.filter(notification => 
          (now - notification.showTime) < 300000 // 5 minutes
        )
      );
    }, 30000); // Check every 30 seconds

    return () => clearInterval(cleanup);
  }, []);

  return (
    <div className="fixed top-0 right-0 z-50 pointer-events-none">
      <div className="pointer-events-auto space-y-4 p-4">
        {activeNotifications.map((signal, index) => (
          <div
            key={signal.notificationId}
            style={{
              transform: `translateY(${index * 10}px)`,
              zIndex: 1000 - index
            }}
          >
            <SignalPopupNotification
              signal={signal}
              onClose={() => handleCloseNotification(signal.notificationId)}
              onExecute={handleExecuteSignal}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default SignalNotificationManager;