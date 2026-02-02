/**
 * Signal Setup Guide Modal
 * Displays comprehensive setup instructions for trading signals
 * Ensures users configure Pocket Option with exact conditions that generated the signal
 */

import React, { useState, useEffect } from 'react';
import { X, CheckCircle, AlertCircle, Clock, Settings, TrendingUp, Target } from 'lucide-react';

const SignalSetupGuideModal = ({ signal, onClose, onConfirm }) => {
  const [checkedItems, setCheckedItems] = useState({});
  const [countdown, setCountdown] = useState(0);
  const [allConfirmed, setAllConfirmed] = useState(false);
  
  const setupGuide = signal?.setup_guide;
  
  useEffect(() => {
    if (!setupGuide) return;
    
    // Initialize countdown
    const secondsToCandle = setupGuide.timing_settings?.seconds_to_next_candle || 0;
    setCountdown(secondsToCandle);
    
    // Update countdown every second
    const timer = setInterval(() => {
      setCountdown(prev => Math.max(0, prev - 1));
    }, 1000);
    
    return () => clearInterval(timer);
  }, [setupGuide]);
  
  useEffect(() => {
    // Check if all critical items are checked
    const checklist = setupGuide?.pre_trade_checklist || [];
    const criticalItems = checklist.filter(item => item.critical);
    const allCriticalChecked = criticalItems.every(item => checkedItems[item.item]);
    setAllConfirmed(allCriticalChecked);
  }, [checkedItems, setupGuide]);
  
  if (!signal || !setupGuide) {
    return null;
  }
  
  const handleCheckItem = (itemKey) => {
    setCheckedItems(prev => ({
      ...prev,
      [itemKey]: !prev[itemKey]
    }));
  };
  
  const handleConfirmAndTrade = () => {
    if (allConfirmed) {
      onConfirm(signal);
      onClose();
    }
  };
  
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };
  
  const getCountdownColor = () => {
    if (countdown < 5) return 'text-red-600 animate-pulse';
    if (countdown < 15) return 'text-orange-500';
    if (countdown < 30) return 'text-yellow-500';
    return 'text-blue-500';
  };
  
  const getTimingRecommendation = () => {
    if (countdown < 5) return { icon: '⚡', text: 'EXECUTE NOW', color: 'bg-green-500', pulse: true };
    if (countdown < 15) return { icon: '⏰', text: 'PREPARE', color: 'bg-yellow-500', pulse: false };
    if (countdown < 30) return { icon: '⏳', text: 'GET READY', color: 'bg-orange-500', pulse: false };
    return { icon: '⌛', text: 'WAIT', color: 'bg-blue-500', pulse: false };
  };
  
  const timing = getTimingRecommendation();
  
  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-[9999] flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl shadow-2xl border border-gray-700 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-purple-600 p-6 rounded-t-2xl flex justify-between items-center z-10">
          <div>
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <Settings className="w-7 h-7" />
              Signal Setup Guide
            </h2>
            <p className="text-blue-100 text-sm mt-1">Configure Pocket Option to match signal conditions</p>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:bg-white/20 rounded-full p-2 transition"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        
        {/* Signal Info Banner */}
        <div className="bg-gradient-to-r from-purple-900/50 to-blue-900/50 p-4 border-b border-gray-700">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              <div className={`px-4 py-2 rounded-lg font-bold text-lg ${
                signal.direction === 'CALL' || signal.direction === 'BUY'
                  ? 'bg-green-500 text-white'
                  : 'bg-red-500 text-white'
              }`}>
                {signal.direction}
              </div>
              <div>
                <div className="text-white font-semibold text-lg">{signal.symbol}</div>
                <div className="text-gray-400 text-sm">{setupGuide.strategy} • {signal.confidence}% confidence</div>
              </div>
            </div>
            
            {/* Countdown Timer */}
            <div className={`flex flex-col items-center p-4 rounded-xl border-2 ${
              timing.pulse ? 'border-green-400 animate-pulse' : 'border-gray-600'
            } ${timing.color} bg-opacity-20`}>
              <div className="flex items-center gap-2 mb-1">
                <Clock className="w-5 h-5 text-white" />
                <span className="text-white font-semibold">Next Candle</span>
              </div>
              <div className={`text-3xl font-bold ${getCountdownColor()}`}>
                {formatTime(countdown)}
              </div>
              <div className={`text-sm font-bold mt-1 ${timing.pulse ? 'animate-pulse' : ''}`}>
                {timing.icon} {timing.text}
              </div>
            </div>
          </div>
        </div>
        
        <div className="p-6 space-y-6">
          {/* Critical Settings */}
          <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700">
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-red-500" />
              Critical Settings (Must Match Exactly)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(setupGuide.critical_settings || {}).map(([key, setting]) => (
                <div key={key} className="bg-gray-900/50 rounded-lg p-4 border border-gray-700">
                  <div className="flex items-start justify-between mb-2">
                    <div className="text-gray-400 text-sm font-medium uppercase">{key.replace(/_/g, ' ')}</div>
                    {setting.critical && <span className="text-red-500 text-xs font-bold">REQUIRED</span>}
                  </div>
                  <div className="text-white font-bold text-lg mb-1">{setting.required}</div>
                  <div className="text-gray-500 text-xs">{setting.location}</div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Pre-Trade Checklist */}
          <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700">
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              Pre-Trade Checklist
            </h3>
            <div className="space-y-2">
              {(setupGuide.pre_trade_checklist || []).map((item, idx) => (
                <label
                  key={idx}
                  className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition ${
                    checkedItems[item.item]
                      ? 'bg-green-900/30 border-green-600'
                      : 'bg-gray-900/50 border-gray-700'
                  } border`}
                >
                  <input
                    type="checkbox"
                    checked={checkedItems[item.item] || false}
                    onChange={() => handleCheckItem(item.item)}
                    className="w-5 h-5 rounded"
                  />
                  <div className="flex-1">
                    <div className="text-white font-medium">{item.item}</div>
                    <div className="text-gray-500 text-xs">{item.category}</div>
                  </div>
                  {item.critical && (
                    <span className="text-red-400 text-xs font-bold">CRITICAL</span>
                  )}
                </label>
              ))}
            </div>
          </div>
          
          {/* Step-by-Step Setup */}
          <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700">
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-500" />
              Step-by-Step Setup Instructions
            </h3>
            <div className="space-y-3">
              {(setupGuide.setup_steps || []).slice(0, 6).map((step, idx) => (
                <div key={idx} className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-sm">
                    {step.step}
                  </div>
                  <div className="flex-1">
                    <div className="text-white font-semibold mb-1">{step.action}</div>
                    <div className="text-gray-400 text-sm">{step.details}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Technical Indicators */}
          {setupGuide.indicators_used && setupGuide.indicators_used.length > 0 && (
            <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700">
              <h3 className="text-xl font-bold text-white mb-4">Technical Indicators Used</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {setupGuide.indicators_used.map((indicator, idx) => (
                  <div key={idx} className="bg-gray-900/50 rounded-lg p-3">
                    <div className="text-blue-400 font-semibold text-sm">{indicator.name}</div>
                    <div className="text-white text-lg font-bold">{indicator.value}</div>
                    <div className="text-gray-500 text-xs">{indicator.setting}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Expected Conditions */}
          {setupGuide.expected_conditions && setupGuide.expected_conditions.indicators && (
            <div className="bg-yellow-900/20 rounded-xl p-5 border border-yellow-600/50">
              <h3 className="text-xl font-bold text-yellow-400 mb-3 flex items-center gap-2">
                <AlertCircle className="w-5 h-5" />
                Verify These Conditions on Chart
              </h3>
              <div className="text-gray-300 text-sm mb-3">{setupGuide.expected_conditions.description}</div>
              <ul className="space-y-2">
                {setupGuide.expected_conditions.indicators.map((condition, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-gray-200">
                    <span className="text-yellow-400 mt-1">•</span>
                    <span>{condition}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          {/* Warnings */}
          {setupGuide.warnings && setupGuide.warnings.length > 0 && (
            <div className="bg-red-900/20 rounded-xl p-5 border border-red-600/50">
              <h3 className="text-xl font-bold text-red-400 mb-3 flex items-center gap-2">
                <AlertCircle className="w-5 h-5" />
                Important Warnings
              </h3>
              <ul className="space-y-2">
                {setupGuide.warnings.map((warning, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-gray-200">
                    <span className="text-red-400 mt-1">⚠️</span>
                    <span>{warning}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          {/* Risk Management */}
          {setupGuide.risk_management && (
            <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700">
              <h3 className="text-xl font-bold text-white mb-4">Risk Management</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-400">Recommended Stake</div>
                  <div className="text-white font-bold text-lg">${setupGuide.risk_management.recommended_stake}</div>
                </div>
                <div>
                  <div className="text-gray-400">Max Per Trade</div>
                  <div className="text-white font-semibold">{setupGuide.risk_management.max_stake_percentage}</div>
                </div>
                <div>
                  <div className="text-gray-400">Stop Loss Rule</div>
                  <div className="text-white font-semibold">{setupGuide.risk_management.stop_loss_rule}</div>
                </div>
                <div>
                  <div className="text-gray-400">Daily Limit</div>
                  <div className="text-white font-semibold">{setupGuide.risk_management.daily_limit}</div>
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Footer Actions */}
        <div className="sticky bottom-0 bg-gray-900 p-6 border-t border-gray-700 flex justify-between items-center rounded-b-2xl">
          <div className="text-gray-400 text-sm">
            {allConfirmed ? (
              <span className="text-green-400 flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                All critical items confirmed
              </span>
            ) : (
              <span className="text-yellow-400 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                Please confirm all critical items
              </span>
            )}
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-semibold transition"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirmAndTrade}
              disabled={!allConfirmed || countdown > 10}
              className={`px-8 py-3 rounded-lg font-bold transition flex items-center gap-2 ${
                allConfirmed && countdown <= 10
                  ? 'bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400 text-white'
                  : 'bg-gray-600 text-gray-400 cursor-not-allowed'
              }`}
            >
              {countdown <= 10 ? (
                <>
                  <CheckCircle className="w-5 h-5" />
                  Execute Trade
                </>
              ) : (
                <>
                  <Clock className="w-5 h-5" />
                  Wait {formatTime(countdown)}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignalSetupGuideModal;
