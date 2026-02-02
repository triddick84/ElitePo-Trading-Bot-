import React, { useState, useEffect } from 'react';

const MoneyManagement = () => {
  const [initialStake, setInitialStake] = useState(1.61);
  const [multiplier, setMultiplier] = useState(1.11);
  const [maxTrades, setMaxTrades] = useState(10);
  const [totalBankroll, setTotalBankroll] = useState(100);
  const [payoutPercent, setPayoutPercent] = useState(82);
  
  const [tradeSequence, setTradeSequence] = useState([]);
  const [alternativeSequence, setAlternativeSequence] = useState([]);
  const [recommendations, setRecommendations] = useState({});

  // Calculate trade sequences
  useEffect(() => {
    calculateSequences();
  }, [initialStake, multiplier, maxTrades]);

  // Calculate recommended stake
  useEffect(() => {
    calculateRecommendations();
  }, [totalBankroll, maxTrades, multiplier]);

  const calculateSequences = () => {
    // Sequence 1: Current multiplier
    const seq1 = [];
    let cumulativeLoss1 = 0;
    
    for (let i = 0; i < maxTrades; i++) {
      let stake;
      if (i === 0) {
        stake = initialStake;
      } else {
        stake = cumulativeLoss1 * multiplier + initialStake;
      }
      
      cumulativeLoss1 += stake;
      const payout = stake * (payoutPercent / 100);
      const profit = payout - cumulativeLoss1;
      
      seq1.push({
        trade: i + 1,
        stake: stake,
        cumulativeLoss: cumulativeLoss1,
        payout: payout,
        profit: profit,
        breakEven: profit >= 0
      });
    }
    
    // Sequence 2: Alternative 1.25 multiplier
    const seq2 = [];
    let cumulativeLoss2 = 0;
    
    for (let i = 0; i < maxTrades; i++) {
      let stake;
      if (i === 0) {
        stake = initialStake;
      } else {
        stake = cumulativeLoss2 * 1.25 + initialStake;
      }
      
      cumulativeLoss2 += stake;
      const payout = stake * (payoutPercent / 100);
      const profit = payout - cumulativeLoss2;
      
      seq2.push({
        trade: i + 1,
        stake: stake,
        cumulativeLoss: cumulativeLoss2,
        payout: payout,
        profit: profit,
        breakEven: profit >= 0
      });
    }
    
    setTradeSequence(seq1);
    setAlternativeSequence(seq2);
  };

  const calculateRecommendations = () => {
    // Calculate recommended initial stake based on bankroll
    // Formula: T1 = (Total * Multiplier) / (Multiplier^Tn - 1)
    const recommendedStake1 = (totalBankroll * multiplier) / (Math.pow(multiplier + 1, maxTrades) - 1);
    const recommendedStake2 = (totalBankroll * 1.25) / (Math.pow(2.25, maxTrades) - 1);
    
    setRecommendations({
      stake1: recommendedStake1,
      stake2: recommendedStake2,
      maxLoss: totalBankroll,
      safetyMargin: (totalBankroll * 0.8) // 80% of bankroll
    });
  };

  const getRowColor = (trade) => {
    if (trade.breakEven) return 'bg-green-600/20 border-green-400/50';
    if (trade.trade <= 3) return 'bg-blue-600/20 border-blue-400/50';
    if (trade.trade <= 6) return 'bg-yellow-600/20 border-yellow-400/50';
    return 'bg-red-600/20 border-red-400/50';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-3">
            💰 Money Management Calculator
          </h1>
          <p className="text-purple-200 text-lg">
            Martingale & Progressive Betting System with Loss Recovery
          </p>
          <div className="mt-4 inline-block bg-purple-600/20 border border-purple-400/30 rounded-lg px-6 py-3">
            <p className="text-purple-300 text-sm">
              ⚠️ <strong>Risk Warning:</strong> Martingale systems carry high risk. Use with proper bankroll management!
            </p>
          </div>
        </div>

        {/* Input Controls */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {/* Left Column - Basic Settings */}
          <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl border border-purple-500/30 p-6">
            <h2 className="text-2xl font-bold text-white mb-4 flex items-center">
              <span className="mr-2">⚙️</span> Trading Settings
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-purple-300 font-semibold mb-2">
                  Initial Stake ($)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={initialStake}
                  onChange={(e) => setInitialStake(parseFloat(e.target.value) || 0)}
                  className="w-full bg-gray-700 text-white border border-purple-400/50 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div>
                <label className="block text-purple-300 font-semibold mb-2">
                  Multiplier (Recovery Rate)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={multiplier}
                  onChange={(e) => setMultiplier(parseFloat(e.target.value) || 1)}
                  className="w-full bg-gray-700 text-white border border-purple-400/50 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <p className="text-xs text-purple-400 mt-1">
                  Common values: 1.11 (conservative), 1.25 (moderate), 1.5 (aggressive)
                </p>
              </div>

              <div>
                <label className="block text-purple-300 font-semibold mb-2">
                  Payout Percentage (%)
                </label>
                <input
                  type="number"
                  step="1"
                  value={payoutPercent}
                  onChange={(e) => setPayoutPercent(parseFloat(e.target.value) || 0)}
                  className="w-full bg-gray-700 text-white border border-purple-400/50 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <p className="text-xs text-purple-400 mt-1">
                  Pocket Option typical: 82-95%
                </p>
              </div>

              <div>
                <label className="block text-purple-300 font-semibold mb-2">
                  Max Trades in Sequence
                </label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={maxTrades}
                  onChange={(e) => setMaxTrades(parseInt(e.target.value) || 10)}
                  className="w-full bg-gray-700 text-white border border-purple-400/50 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>
          </div>

          {/* Right Column - Bankroll Management */}
          <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl border border-purple-500/30 p-6">
            <h2 className="text-2xl font-bold text-white mb-4 flex items-center">
              <span className="mr-2">💵</span> Bankroll Management
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-purple-300 font-semibold mb-2">
                  Total Bankroll ($)
                </label>
                <input
                  type="number"
                  step="1"
                  value={totalBankroll}
                  onChange={(e) => setTotalBankroll(parseFloat(e.target.value) || 0)}
                  className="w-full bg-gray-700 text-white border border-purple-400/50 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Recommendations */}
              <div className="bg-green-600/20 border border-green-400/50 rounded-lg p-4 mt-4">
                <h3 className="text-green-300 font-bold mb-2">📊 Recommendations</h3>
                
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-green-200">Recommended Initial (×{multiplier}):</span>
                    <span className="text-green-300 font-bold">
                      ${recommendations.stake1?.toFixed(2) || '0.00'}
                    </span>
                  </div>
                  
                  <div className="flex justify-between">
                    <span className="text-green-200">Recommended Initial (×1.25):</span>
                    <span className="text-green-300 font-bold">
                      ${recommendations.stake2?.toFixed(2) || '0.00'}
                    </span>
                  </div>
                  
                  <div className="flex justify-between border-t border-green-400/30 pt-2">
                    <span className="text-green-200">Safe Zone (80%):</span>
                    <span className="text-green-300 font-bold">
                      ${recommendations.safetyMargin?.toFixed(2) || '0.00'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Quick Stats */}
              <div className="bg-blue-600/20 border border-blue-400/50 rounded-lg p-4">
                <h3 className="text-blue-300 font-bold mb-2">⚡ Quick Stats</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-blue-200">Total Sequences:</span>
                    <span className="text-blue-300 font-bold">{maxTrades}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-blue-200">Max Risk:</span>
                    <span className="text-blue-300 font-bold">
                      ${tradeSequence[maxTrades - 1]?.cumulativeLoss.toFixed(2) || '0.00'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-blue-200">Bankroll Usage:</span>
                    <span className="text-blue-300 font-bold">
                      {((tradeSequence[maxTrades - 1]?.cumulativeLoss / totalBankroll) * 100 || 0).toFixed(1)}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Trade Sequences */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {/* Sequence 1 */}
          <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl border border-purple-500/30 overflow-hidden">
            <div className="bg-gradient-to-r from-purple-600/30 to-blue-600/30 p-4">
              <h2 className="text-xl font-bold text-white">
                📈 Sequence 1: ×{multiplier} Multiplier
              </h2>
              <p className="text-purple-200 text-sm">Current settings</p>
            </div>
            
            <div className="p-4 max-h-[600px] overflow-y-auto">
              <div className="space-y-2">
                {tradeSequence.map((trade) => (
                  <div
                    key={trade.trade}
                    className={`border rounded-lg p-3 ${getRowColor(trade)}`}
                  >
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-white font-bold">Trade {trade.trade}</span>
                      {trade.breakEven && (
                        <span className="bg-green-500 text-white text-xs px-2 py-1 rounded">
                          ✓ PROFIT
                        </span>
                      )}
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <p className="text-gray-400">Stake:</p>
                        <p className="text-white font-semibold">${trade.stake.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-gray-400">Total Loss:</p>
                        <p className="text-red-300 font-semibold">${trade.cumulativeLoss.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-gray-400">Payout:</p>
                        <p className="text-yellow-300 font-semibold">${trade.payout.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-gray-400">Profit:</p>
                        <p className={`font-semibold ${trade.profit >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                          {trade.profit >= 0 ? '+' : ''}${trade.profit.toFixed(2)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Sequence 2 - Alternative */}
          <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl border border-purple-500/30 overflow-hidden">
            <div className="bg-gradient-to-r from-orange-600/30 to-red-600/30 p-4">
              <h2 className="text-xl font-bold text-white">
                📉 Sequence 2: ×1.25 Multiplier
              </h2>
              <p className="text-orange-200 text-sm">Alternative strategy</p>
            </div>
            
            <div className="p-4 max-h-[600px] overflow-y-auto">
              <div className="space-y-2">
                {alternativeSequence.map((trade) => (
                  <div
                    key={trade.trade}
                    className={`border rounded-lg p-3 ${getRowColor(trade)}`}
                  >
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-white font-bold">Trade {trade.trade}</span>
                      {trade.breakEven && (
                        <span className="bg-green-500 text-white text-xs px-2 py-1 rounded">
                          ✓ PROFIT
                        </span>
                      )}
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <p className="text-gray-400">Stake:</p>
                        <p className="text-white font-semibold">${trade.stake.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-gray-400">Total Loss:</p>
                        <p className="text-red-300 font-semibold">${trade.cumulativeLoss.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-gray-400">Payout:</p>
                        <p className="text-yellow-300 font-semibold">${trade.payout.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-gray-400">Profit:</p>
                        <p className={`font-semibold ${trade.profit >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                          {trade.profit >= 0 ? '+' : ''}${trade.profit.toFixed(2)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Info Section */}
        <div className="bg-red-600/20 border border-red-400/50 rounded-xl p-6 mb-6">
          <h3 className="text-xl font-bold text-red-300 mb-3">⚠️ Important Risk Warnings</h3>
          <ul className="space-y-2 text-red-200">
            <li>• <strong>Martingale Risk:</strong> Losses compound exponentially. One long losing streak can wipe out your bankroll.</li>
            <li>• <strong>Capital Requirements:</strong> Ensure you have 2-3x the max cumulative loss in your bankroll.</li>
            <li>• <strong>Win Rate Requirement:</strong> This system requires a win rate above 50% to be profitable long-term.</li>
            <li>• <strong>Psychological Pressure:</strong> Stakes increase rapidly during losing streaks. Stay disciplined!</li>
            <li>• <strong>Platform Limits:</strong> Check Pocket Option max stake limits before using this strategy.</li>
          </ul>
        </div>

        {/* Tips Section */}
        <div className="bg-blue-600/20 border border-blue-400/50 rounded-xl p-6">
          <h3 className="text-xl font-bold text-blue-300 mb-3">💡 Pro Tips</h3>
          <div className="grid md:grid-cols-2 gap-4 text-blue-200">
            <div>
              <p className="font-semibold mb-2">✓ Best Practices:</p>
              <ul className="space-y-1 text-sm">
                <li>• Start with conservative multipliers (1.11-1.25)</li>
                <li>• Never exceed 50% of bankroll in any sequence</li>
                <li>• Use high-accuracy strategies (80%+ win rate)</li>
                <li>• Set daily loss limits and stick to them</li>
                <li>• Take profits after 2-3 wins</li>
              </ul>
            </div>
            <div>
              <p className="font-semibold mb-2">✓ When to Use:</p>
              <ul className="space-y-1 text-sm">
                <li>• During stable market conditions</li>
                <li>• With proven high-accuracy strategies</li>
                <li>• When you have sufficient bankroll</li>
                <li>• After testing on demo account</li>
                <li>• When emotionally prepared for losses</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Back Button */}
        <div className="mt-6 text-center">
          <button
            onClick={() => window.location.href = '/'}
            className="bg-gray-700 hover:bg-gray-600 text-white font-semibold py-3 px-8 rounded-lg transition-colors"
          >
            ← Back to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
};

export default MoneyManagement;
