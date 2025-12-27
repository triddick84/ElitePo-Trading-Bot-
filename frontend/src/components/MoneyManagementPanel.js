import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Slider } from './ui/slider';
import { Progress } from './ui/progress';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const MoneyManagementPanel = () => {
  const [status, setStatus] = useState(null);
  const [stakeCalc, setStakeCalc] = useState(null);
  const [confidence, setConfidence] = useState(80);
  const [balance, setBalance] = useState(1000);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${BACKEND_URL}/api/money-management/status`);
      if (response.data.success) {
        setStatus(response.data);
        setBalance(response.data.balance);
      }
    } catch (error) {
      console.error('Error loading money management status:', error);
      toast.error('Failed to load money management status');
    } finally {
      setLoading(false);
    }
  };

  const calculateStake = async () => {
    try {
      const response = await axios.post(
        `${BACKEND_URL}/api/money-management/calculate-stake?confidence=${confidence}&balance=${balance}`
      );
      
      if (response.data.success) {
        setStakeCalc(response.data);
        toast.success('✅ Stake calculated!');
      }
    } catch (error) {
      console.error('Error calculating stake:', error);
      toast.error('Error calculating stake');
    }
  };

  const getRiskLevelColor = (level) => {
    const colors = {
      'low': 'text-emerald-400 bg-emerald-500/20 border-emerald-500',
      'moderate': 'text-blue-400 bg-blue-500/20 border-blue-500',
      'high': 'text-yellow-400 bg-yellow-500/20 border-yellow-500',
      'very_high': 'text-red-400 bg-red-500/20 border-red-500'
    };
    return colors[level] || colors['moderate'];
  };

  if (loading) {
    return (
      <Card className="w-full bg-slate-900 border-slate-700">
        <CardContent className="p-6">
          <div className="text-center text-slate-400">Loading Money Management System...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Account Status */}
      <Card className="bg-slate-900 border-slate-700">
        <CardHeader>
          <CardTitle className="text-2xl text-emerald-400">💰 Money Management System</CardTitle>
          <CardDescription className="text-slate-400">
            Smart stake calculation with Kelly Formula and risk management
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {status && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Current Balance */}
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Current Balance</p>
                <p className="text-2xl font-bold text-emerald-400">
                  ${status.balance?.toFixed(2) || '0.00'}
                </p>
              </div>

              {/* Initial Balance */}
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Initial Balance</p>
                <p className="text-2xl font-bold text-white">
                  ${status.initial_balance?.toFixed(2) || '0.00'}
                </p>
              </div>

              {/* Risk Level */}
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Risk Level</p>
                <Badge className={getRiskLevelColor(status.risk_level)}>
                  {status.risk_level?.toUpperCase() || 'MODERATE'}
                </Badge>
              </div>

              {/* Win Rate */}
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Win Rate</p>
                <p className="text-2xl font-bold text-blue-400">
                  {status.win_rate ? `${status.win_rate.toFixed(1)}%` : 'N/A'}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Stake Calculator */}
      <Card className="bg-slate-900 border-slate-700">
        <CardHeader>
          <CardTitle className="text-xl text-white">🎯 Stake Calculator</CardTitle>
          <CardDescription className="text-slate-400">
            Calculate optimal stake size based on confidence and balance
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Confidence Slider */}
          <div>
            <div className="flex justify-between mb-2">
              <label className="text-sm font-medium text-slate-300">Signal Confidence</label>
              <Badge className="bg-slate-700 text-white">{confidence}%</Badge>
            </div>
            <Slider
              value={[confidence]}
              onValueChange={(value) => setConfidence(value[0])}
              min={50}
              max={100}
              step={5}
              className="w-full"
            />
          </div>

          {/* Balance Input */}
          <div>
            <label className="text-sm font-medium text-slate-300 mb-2 block">Account Balance</label>
            <Input
              type="number"
              value={balance}
              onChange={(e) => setBalance(parseFloat(e.target.value))}
              placeholder="Enter balance"
              className="bg-slate-800 border-slate-700 text-white"
            />
          </div>

          {/* Calculate Button */}
          <Button
            onClick={calculateStake}
            className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            📊 Calculate Optimal Stake
          </Button>

          {/* Results */}
          {stakeCalc && (
            <div className="bg-slate-800 rounded-lg p-6 space-y-4">
              <div className="border-b border-slate-700 pb-4">
                <h3 className="text-lg font-semibold text-white mb-4">Calculation Results</h3>
                
                {stakeCalc.can_trade ? (
                  <div className="space-y-4">
                    {/* Recommended Stake */}
                    <div className="bg-emerald-500/10 border border-emerald-500 rounded-lg p-4">
                      <p className="text-sm text-slate-400 mb-1">Recommended Stake</p>
                      <p className="text-3xl font-bold text-emerald-400">
                        ${stakeCalc.stake?.toFixed(2) || '0.00'}
                      </p>
                      <p className="text-sm text-slate-400 mt-2">
                        {stakeCalc.stake_percentage?.toFixed(2)}% of balance
                      </p>
                    </div>

                    {/* Kelly Formula Details */}
                    <div className="space-y-2">
                      <div className="flex justify-between items-center text-sm">
                        <span className="text-slate-400">Kelly Formula %</span>
                        <span className="text-white">{stakeCalc.kelly_stake_pct?.toFixed(2)}%</span>
                      </div>
                      <div className="flex justify-between items-center text-sm">
                        <span className="text-slate-400">Risk Level</span>
                        <Badge className={getRiskLevelColor(stakeCalc.risk_level)}>
                          {stakeCalc.risk_level?.toUpperCase()}
                        </Badge>
                      </div>
                      {stakeCalc.drawdown_multiplier && (
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-slate-400">Drawdown Multiplier</span>
                          <span className="text-white">{stakeCalc.drawdown_multiplier.toFixed(2)}x</span>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="bg-red-500/10 border border-red-500 rounded-lg p-4">
                    <p className="text-red-400 font-semibold">⚠️ Cannot Trade</p>
                    <p className="text-sm text-slate-400 mt-2">
                      Risk management rules prevent trading at this time
                    </p>
                  </div>
                )}
              </div>

              {/* Kelly Formula Explanation */}
              <div>
                <h4 className="text-sm font-semibold text-slate-300 mb-2">📚 Kelly Formula</h4>
                <p className="text-xs text-slate-400">
                  The Kelly Formula calculates optimal stake size to maximize long-term growth while
                  managing risk. It considers win probability, payout ratio, and current drawdown.
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Trading Statistics */}
      {status && (
        <Card className="bg-slate-900 border-slate-700">
          <CardHeader>
            <CardTitle className="text-xl text-white">📊 Trading Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Total Trades</p>
                <p className="text-2xl font-bold text-white">{status.total_trades || 0}</p>
              </div>
              
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Win Rate</p>
                <p className="text-2xl font-bold text-emerald-400">
                  {status.win_rate ? `${status.win_rate.toFixed(1)}%` : 'N/A'}
                </p>
                {status.win_rate && <Progress value={status.win_rate} className="mt-2 h-2" />}
              </div>
              
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Profit Factor</p>
                <p className="text-2xl font-bold text-blue-400">
                  {status.profit_factor ? status.profit_factor.toFixed(2) : 'N/A'}
                </p>
              </div>
              
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Max Drawdown</p>
                <p className="text-2xl font-bold text-red-400">
                  {status.max_drawdown ? `${status.max_drawdown.toFixed(1)}%` : 'N/A'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Risk Management Rules */}
      <Card className="bg-slate-900 border-slate-700">
        <CardHeader>
          <CardTitle className="text-xl text-white">⚠️ Active Risk Management Rules</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm text-slate-300">
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span><strong>Fixed Percentage:</strong> Maximum 5% of balance per trade</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span><strong>Time Filter:</strong> Maximum 3 trades per 5 minutes</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span><strong>Correlation Check:</strong> Avoid correlated assets simultaneously</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span><strong>Trade Limit:</strong> Maximum 100 trades per day</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span><strong>Drawdown Protection:</strong> Reduce stake during drawdowns</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span><strong>Performance Review:</strong> Auto-pause after 5 consecutive losses</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default MoneyManagementPanel;
