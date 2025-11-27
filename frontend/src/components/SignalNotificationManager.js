import React, { useState, useEffect } from 'react';
import ImprovedSignalPopup from './ImprovedSignalPopup';

const SignalNotificationManager = ({ signals = [], onSignalExecute, onSignalDismiss, notificationSettings = {} }) => {
  const [activePopups, setActivePopups] = useState([]);
  const [processedSignalIds, setProcessedSignalIds] = useState(new Set());

  useEffect(() => {
    // Process new signals for popup notifications
    if (!signals || !Array.isArray(signals)) return;
    if (!notificationSettings.popupEnabled) return;

    // Find new high-priority signals that haven't been processed
    const newSignals = signals.filter(signal => {
      const isHighPriority = signal.probability >= 85 || signal.forced_generation;
      const isNewSignal = !processedSignalIds.has(signal.id);
      const isRecentSignal = signal.timestamp && 
        (Date.now() - new Date(signal.timestamp).getTime()) < 300000; // 5 minutes
      
      return isHighPriority && isNewSignal && isRecentSignal;
    });

    if (newSignals.length > 0) {
      // Create ONE new popup containing ALL new signals
      const popupId = `popup_${Date.now()}`;
      const newPopup = {
        id: popupId,
        signals: newSignals.map(signal => ({
          ...signal,
          notificationId: `${signal.id}_${Date.now()}`
        })),
        createdAt: Date.now()
      };

      // Add new popup (this will create a separate popup even if one is already showing)
      setActivePopups(prev => [...prev, newPopup]);

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

  const handleClosePopup = (popupId) => {
    setActivePopups(prev => prev.filter(popup => popup.id !== popupId));
  };

  const handleExecuteSignal = (signal) => {
    // Call execute callback if provided
    if (onSignalExecute) {
      onSignalExecute(signal);
    }
  };

  // Auto-cleanup old popups (after 10 minutes)
  useEffect(() => {
    const cleanup = setInterval(() => {
      const now = Date.now();
      setActivePopups(prev => 
        prev.filter(popup => (now - popup.createdAt) < 600000) // 10 minutes
      );
    }, 60000); // Check every minute

    return () => clearInterval(cleanup);
  }, []);

  return (
    <div className="fixed top-0 right-0 z-50 pointer-events-none">
      <div className="pointer-events-auto space-y-4">
        {activePopups.map((popup, index) => (
          <div
            key={popup.id}
            style={{
              transform: `translateY(${index * 20}px)`,
              zIndex: 1000 - index
            }}
          >
            <ImprovedSignalPopup
              signals={popup.signals}
              onClose={() => handleClosePopup(popup.id)}
              onExecute={handleExecuteSignal}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default SignalNotificationManager;