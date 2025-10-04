import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const SignalsPanel = () => {
  const [signals, setSignals] = useState([]);
  const [signalHistory, setSignalHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('active');

  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchSignals = async () => {
    try {
      const [activeResponse, historyResponse] = await Promise.all([
        axios.get(`${API}/signals/active`),
        axios.get(`${API}/signals/history`)
      ]);

      setSignals(activeResponse.data);
      setSignalHistory(historyResponse.data.signals || []);
    } catch (error) {
      console.error('Error fetching signals:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getSignalColor = (direction) => {
    return direction === 'BUY' || direction === 'CALL' 
      ? 'bg-green-500/20 text-green-400 border-green-500/30'
      : 'bg-red-500/20 text-red-400 border-red-500/30';
  };

  const getConfidenceColor = (level) => {
    switch (level) {
      case 'HIGH': return 'text-green-400';
      case 'MEDIUM': return 'text-yellow-400';
      case 'LOW': return 'text-red-400';
      default: return 'text-slate-400';
    }
  };

  const getOutcomeIcon = (outcome) => {
    switch (outcome) {
      case 'WIN': return '✅';
      case 'LOSS': return '❌';
      default: return '⏳';
    }
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const SignalCard = ({ signal, showHistory = false }) => (
    <Card className="p-6 glass-dark border-slate-700/50 signal-item">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <Badge className={getSignalColor(signal.direction)}>
            {signal.direction}
          </Badge>
          <div>
            <h4 className="text-white font-semibold text-lg">{signal.symbol}</h4>
            <p className="text-slate-400 text-sm">{signal.asset_type}</p>
          </div>
        </div>
        {showHistory && (
          <div className="flex items-center space-x-2">
            <span className="text-2xl">{getOutcomeIcon(signal.actual_outcome)}</span>
            {signal.profit_loss && (
              <span className={`font-bold ${signal.profit_loss >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                ${signal.profit_loss.toFixed(2)}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div>
          <p className="text-slate-400 text-sm">Entry Price</p>
          <p className="text-white font-medium">${signal.entry_price}</p>
        </div>
        <div>
          <p className="text-slate-400 text-sm">Probability</p>
          <p className="text-white font-medium">{signal.probability}%</p>
        </div>
        <div>
          <p className="text-slate-400 text-sm">Expiration</p>
          <p className="text-white font-medium">{signal.expiration_minutes}m</p>
        </div>
        <div>
          <p className="text-slate-400 text-sm">Confidence</p>
          <p className={`font-medium ${getConfidenceColor(signal.confidence_level)}`}>
            {signal.confidence_level}
          </p>
        </div>
      </div>

      {signal.justification && (
        <div className="mb-4">
          <p className="text-slate-400 text-sm mb-2">Analysis</p>
          <p className="text-slate-300 text-sm bg-slate-800/30 p-3 rounded-lg">
            {signal.justification}
          </p>
        </div>
      )}

      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-400">
          Strategy: {signal.strategy_used?.replace('_', ' ').toUpperCase()}
        </span>
        <span className="text-slate-400">
          {formatTimestamp(signal.timestamp)}
        </span>
      </div>
    </Card>
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        {[...Array(3)].map((_, i) => (
          <Card key={i} className="p-6 glass-dark border-slate-700/50">
            <div className="skeleton h-32 w-full rounded"></div>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="signals-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-white mb-2">Trading Signals</h2>
          <p className="text-slate-400">Real-time AI-generated trading signals and analysis</p>
        </div>
        <Button 
          onClick={fetchSignals}
          className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
          data-testid="refresh-signals"
        >
          🔄 Refresh
        </Button>
      </div>

      {/* Tab Navigation */}
      <div className="flex space-x-1 bg-slate-800/30 p-1 rounded-xl w-fit">
        <button
          onClick={() => setActiveTab('active')}
          className={`px-6 py-2 rounded-lg font-medium transition-all duration-200 ${
            activeTab === 'active'
              ? 'bg-emerald-500/20 text-emerald-400'
              : 'text-slate-400 hover:text-white'
          }`}
          data-testid="active-signals-tab"
        >
          Active Signals ({signals.length})
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-6 py-2 rounded-lg font-medium transition-all duration-200 ${
            activeTab === 'history'
              ? 'bg-emerald-500/20 text-emerald-400'
              : 'text-slate-400 hover:text-white'
          }`}
          data-testid="signal-history-tab"
        >
          Signal History ({signalHistory.length})
        </button>
      </div>

      {/* Signals Content */}
      <div className="space-y-4" data-testid="signals-content">
        {activeTab === 'active' ? (
          signals.length === 0 ? (
            <Card className="p-12 glass-dark border-slate-700/50 text-center">
              <div className="text-6xl mb-4">📡</div>
              <h3 className="text-xl font-semibold text-white mb-2">No Active Signals</h3>
              <p className="text-slate-400">
                The AI is analyzing markets. New signals will appear when high-probability opportunities are detected.
              </p>
            </Card>
          ) : (
            signals.map((signal) => (
              <SignalCard key={signal.id} signal={signal} />
            ))
          )
        ) : (
          signalHistory.length === 0 ? (
            <Card className="p-12 glass-dark border-slate-700/50 text-center">
              <div className="text-6xl mb-4">📜</div>
              <h3 className="text-xl font-semibold text-white mb-2">No Signal History</h3>
              <p className="text-slate-400">
                Signal history will appear here once the bot starts generating signals.
              </p>
            </Card>
          ) : (
            signalHistory.map((signal, index) => (
              <SignalCard key={signal.id || index} signal={signal} showHistory={true} />
            ))
          )
        )}
      </div>
    </div>
  );
};

export default SignalsPanel;