import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Switch } from './ui/switch';
import { Button } from './ui/button';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const AccountModeToggle = ({ compact = false, onModeChange }) => {
  const [accountMode, setAccountMode] = useState('demo');
  const [isLoading, setIsLoading] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);

  useEffect(() => {
    fetchAccountMode();
  }, []);

  const fetchAccountMode = async () => {
    try {
      const response = await axios.get(`${API}/config`);
      const mode = response.data.trading_mode || 'demo';
      setAccountMode(mode);
    } catch (error) {
      console.error('Error fetching account mode:', error);
    }
  };

  const handleModeChange = (newMode) => {
    // If switching to real account, show confirmation
    if (newMode === 'live') {
      setShowConfirmation(true);
    } else {
      updateAccountMode(newMode);
    }
  };

  const confirmRealAccountSwitch = async () => {
    setShowConfirmation(false);
    await updateAccountMode('live');
  };

  const updateAccountMode = async (newMode) => {
    setIsLoading(true);
    try {
      await axios.put(`${API}/config`, {
        trading_mode: newMode
      });
      setAccountMode(newMode);
      
      if (newMode === 'live') {
        toast.success('🚨 Switched to REAL ACCOUNT - Trading with real money!', {
          duration: 5000,
          style: {
            background: '#dc2626',
            color: 'white',
            border: '2px solid #b91c1c'
          }
        });
      } else {
        toast.success('✅ Switched to DEMO ACCOUNT - Practice mode activated', {
          duration: 3000,
          style: {
            background: '#16a34a',
            color: 'white'
          }
        });
      }
      
      // Notify parent component
      if (onModeChange) {
        onModeChange(newMode);
      }
    } catch (error) {
      console.error('Error updating account mode:', error);
      toast.error('❌ Failed to switch account mode');
    } finally {
      setIsLoading(false);
    }
  };

  if (compact) {
    return (
      <>
        <Card className={`p-4 glass-dark border transition-all duration-300 ${
          accountMode === 'demo' 
            ? 'bg-blue-900/30 border-blue-500/50' 
            : 'bg-red-900/30 border-red-500/50'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className={`w-3 h-3 rounded-full animate-pulse ${
                accountMode === 'demo' ? 'bg-blue-400' : 'bg-red-500'
              }`}></div>
              <div>
                <h4 className="text-sm font-semibold text-white flex items-center space-x-2">
                  <span>{accountMode === 'demo' ? '🎮' : '💰'}</span>
                  <span>{accountMode === 'demo' ? 'Demo Account' : 'Real Account'}</span>
                </h4>
                <p className="text-xs text-slate-400">
                  {accountMode === 'demo' ? 'Practice trading' : 'Live trading'}
                </p>
              </div>
            </div>
            <Button
              onClick={() => handleModeChange(accountMode === 'demo' ? 'live' : 'demo')}
              disabled={isLoading}
              className={`text-xs px-3 py-1 font-semibold transition-all ${
                accountMode === 'demo'
                  ? 'bg-red-600 hover:bg-red-500 text-white'
                  : 'bg-blue-600 hover:bg-blue-500 text-white'
              }`}
            >
              {isLoading ? '...' : accountMode === 'demo' ? 'Switch to Real' : 'Switch to Demo'}
            </Button>
          </div>
        </Card>

        {/* Confirmation Modal */}
        {showConfirmation && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 animate-fade-in">
            <Card className="p-6 glass-dark border-red-500/50 max-w-md mx-4 shadow-2xl">
              <div className="text-center mb-6">
                <div className="text-6xl mb-4">⚠️</div>
                <h3 className="text-2xl font-bold text-white mb-2">Switch to Real Account?</h3>
                <p className="text-slate-300 text-sm mb-4">
                  You are about to switch to <span className="font-bold text-red-400">REAL ACCOUNT</span> mode.
                </p>
                <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-4 mb-4">
                  <p className="text-red-300 text-sm font-medium">
                    ⚠️ WARNING: Trades will use real money!
                  </p>
                  <ul className="text-red-200 text-xs mt-2 space-y-1 text-left">
                    <li>• Real funds will be at risk</li>
                    <li>• Losses will affect your actual balance</li>
                    <li>• Ensure you understand the risks</li>
                  </ul>
                </div>
              </div>
              <div className="flex space-x-3">
                <Button
                  onClick={() => setShowConfirmation(false)}
                  className="flex-1 bg-slate-600 hover:bg-slate-500 text-white"
                >
                  Cancel
                </Button>
                <Button
                  onClick={confirmRealAccountSwitch}
                  className="flex-1 bg-red-600 hover:bg-red-500 text-white font-bold"
                >
                  Confirm Real Account
                </Button>
              </div>
            </Card>
          </div>
        )}
      </>
    );
  }

  // Full version with detailed information
  return (
    <>
      <Card className={`p-6 glass-dark border-2 transition-all duration-300 ${
        accountMode === 'demo' 
          ? 'border-blue-500/50 bg-blue-900/20' 
          : 'border-red-500/50 bg-red-900/20'
      }`}>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-semibold text-white mb-2 flex items-center space-x-2">
              <span className="text-2xl">{accountMode === 'demo' ? '🎮' : '💰'}</span>
              <span>Account Mode</span>
            </h3>
            <p className="text-slate-400 text-sm">Switch between demo and real trading accounts</p>
          </div>
          <div className={`px-4 py-2 rounded-full font-bold text-sm ${
            accountMode === 'demo'
              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
              : 'bg-red-500/20 text-red-400 border border-red-500/50 animate-pulse'
          }`}>
            {accountMode === 'demo' ? 'DEMO MODE' : 'REAL MODE'}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          {/* Demo Account Card */}
          <div
            onClick={() => handleModeChange('demo')}
            className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
              accountMode === 'demo'
                ? 'bg-blue-500/20 border-blue-500 shadow-lg shadow-blue-500/20'
                : 'bg-slate-800/50 border-slate-600 hover:border-blue-400'
            }`}
          >
            <div className="text-center">
              <div className="text-4xl mb-2">🎮</div>
              <h4 className="text-white font-bold mb-2">Demo Account</h4>
              <p className="text-slate-400 text-xs mb-3">
                Practice trading with virtual money
              </p>
              <div className="space-y-1 text-xs">
                <div className="flex items-center justify-center space-x-1 text-green-400">
                  <span>✓</span>
                  <span>Risk-free practice</span>
                </div>
                <div className="flex items-center justify-center space-x-1 text-green-400">
                  <span>✓</span>
                  <span>Test strategies</span>
                </div>
                <div className="flex items-center justify-center space-x-1 text-green-400">
                  <span>✓</span>
                  <span>Learn platform</span>
                </div>
              </div>
            </div>
          </div>

          {/* Real Account Card */}
          <div
            onClick={() => handleModeChange('live')}
            className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
              accountMode === 'live'
                ? 'bg-red-500/20 border-red-500 shadow-lg shadow-red-500/20'
                : 'bg-slate-800/50 border-slate-600 hover:border-red-400'
            }`}
          >
            <div className="text-center">
              <div className="text-4xl mb-2">💰</div>
              <h4 className="text-white font-bold mb-2">Real Account</h4>
              <p className="text-slate-400 text-xs mb-3">
                Trade with real money on Pocket Option
              </p>
              <div className="space-y-1 text-xs">
                <div className="flex items-center justify-center space-x-1 text-orange-400">
                  <span>⚠️</span>
                  <span>Real money at risk</span>
                </div>
                <div className="flex items-center justify-center space-x-1 text-orange-400">
                  <span>⚠️</span>
                  <span>Actual profits/losses</span>
                </div>
                <div className="flex items-center justify-center space-x-1 text-orange-400">
                  <span>⚠️</span>
                  <span>Requires funding</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Current Status */}
        <div className={`p-4 rounded-lg border ${
          accountMode === 'demo'
            ? 'bg-blue-900/30 border-blue-500/30'
            : 'bg-red-900/30 border-red-500/50'
        }`}>
          <div className="flex items-center space-x-3">
            <div className={`w-4 h-4 rounded-full ${
              accountMode === 'demo' ? 'bg-blue-400 animate-pulse' : 'bg-red-500 animate-pulse'
            }`}></div>
            <div>
              <p className="text-white font-semibold">
                Currently in {accountMode === 'demo' ? 'DEMO' : 'REAL'} mode
              </p>
              <p className="text-slate-400 text-xs">
                {accountMode === 'demo' 
                  ? 'All trades are simulated. No real money involved.'
                  : '⚠️ All trades use real funds. Please trade responsibly.'}
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* Confirmation Modal for Real Account */}
      {showConfirmation && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 animate-fade-in">
          <Card className="p-6 glass-dark border-red-500/50 max-w-md mx-4 shadow-2xl">
            <div className="text-center mb-6">
              <div className="text-6xl mb-4">⚠️</div>
              <h3 className="text-2xl font-bold text-white mb-2">Switch to Real Account?</h3>
              <p className="text-slate-300 text-sm mb-4">
                You are about to switch to <span className="font-bold text-red-400">REAL ACCOUNT</span> mode.
              </p>
              <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-4 mb-4">
                <p className="text-red-300 text-sm font-medium mb-3">
                  ⚠️ WARNING: Trades will use real money!
                </p>
                <ul className="text-red-200 text-xs space-y-1 text-left">
                  <li>• Real funds will be at risk</li>
                  <li>• Losses will affect your actual balance</li>
                  <li>• Ensure you understand the risks</li>
                  <li>• Only use money you can afford to lose</li>
                </ul>
              </div>
            </div>
            <div className="flex space-x-3">
              <Button
                onClick={() => setShowConfirmation(false)}
                className="flex-1 bg-slate-600 hover:bg-slate-500 text-white"
              >
                Cancel
              </Button>
              <Button
                onClick={confirmRealAccountSwitch}
                className="flex-1 bg-red-600 hover:bg-red-500 text-white font-bold"
              >
                Confirm Real Account
              </Button>
            </div>
          </Card>
        </div>
      )}
    </>
  );
};

export default AccountModeToggle;
