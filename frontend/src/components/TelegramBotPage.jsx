import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Switch } from './ui/switch';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

const TelegramBotPage = () => {
  const [botStatus, setBotStatus] = useState({
    is_running: false,
    auto_trading_enabled: false,
    demo_mode: true,
    trade_amount: 1,
  });
  const [chatMessages, setChatMessages] = useState([]);
  const [signalHistory, setSignalHistory] = useState([]);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [stats, setStats] = useState({
    total_signals: 0,
    total_trades: 0,
    wins: 0,
    losses: 0,
    win_rate: 0,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [messageInput, setMessageInput] = useState('');
  const chatEndRef = useRef(null);

  useEffect(() => {
    fetchBotStatus();
    fetchHistory();
    fetchStats();
    
    // Poll for updates
    const interval = setInterval(() => {
      fetchBotStatus();
      fetchHistory();
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const fetchBotStatus = async () => {
    try {
      const response = await axios.get(`${API}/telegram-bot/status`);
      if (response.data?.status) {
        setBotStatus(response.data.status);
      }
    } catch (error) {
      console.error('Error fetching bot status:', error);
    }
  };

  const fetchHistory = async () => {
    try {
      const response = await axios.get(`${API}/telegram-bot/history?limit=20`);
      if (response.data?.signals) {
        setSignalHistory(response.data.signals);
      }
      if (response.data?.trades) {
        setTradeHistory(response.data.trades);
      }
    } catch (error) {
      console.error('Error fetching history:', error);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/telegram-bot/stats`);
      if (response.data?.stats) {
        setStats(response.data.stats);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const startBot = async () => {
    setIsLoading(true);
    try {
      const response = await axios.post(`${API}/telegram-bot/start`);
      if (response.data?.success) {
        toast.success('Telegram bot started!');
        addChatMessage('system', '🟢 Bot started successfully');
        fetchBotStatus();
      }
    } catch (error) {
      toast.error('Failed to start bot');
      addChatMessage('system', '❌ Failed to start bot');
    } finally {
      setIsLoading(false);
    }
  };

  const stopBot = async () => {
    setIsLoading(true);
    try {
      const response = await axios.post(`${API}/telegram-bot/stop`);
      if (response.data?.success) {
        toast.success('Telegram bot stopped');
        addChatMessage('system', '🔴 Bot stopped');
        fetchBotStatus();
      }
    } catch (error) {
      toast.error('Failed to stop bot');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleAutoTrading = async () => {
    try {
      const newState = !botStatus.auto_trading_enabled;
      const response = await axios.put(`${API}/telegram-bot/settings`, {
        auto_trading_enabled: newState
      });
      if (response.data?.success) {
        toast.success(newState ? 'Auto-trading enabled' : 'Auto-trading disabled');
        addChatMessage('system', newState ? '🤖 Auto-trading ENABLED' : '🤖 Auto-trading DISABLED');
        fetchBotStatus();
      }
    } catch (error) {
      toast.error('Failed to update settings');
    }
  };

  const toggleDemoMode = async () => {
    try {
      const newState = !botStatus.demo_mode;
      const response = await axios.put(`${API}/telegram-bot/settings`, {
        demo_mode: newState
      });
      if (response.data?.success) {
        toast.success(newState ? 'Switched to DEMO mode' : 'Switched to REAL mode');
        addChatMessage('system', newState ? '🟢 DEMO mode activated' : '🔴 REAL mode activated - Be careful!');
        fetchBotStatus();
      }
    } catch (error) {
      toast.error('Failed to update mode');
    }
  };

  const sendMessage = async () => {
    if (!messageInput.trim()) return;
    
    addChatMessage('user', messageInput);
    
    try {
      const response = await axios.post(`${API}/telegram-bot/send`, {
        message: messageInput
      });
      if (response.data?.success) {
        addChatMessage('bot', `✅ Message sent (ID: ${response.data.message_id})`);
      }
    } catch (error) {
      addChatMessage('bot', '❌ Failed to send message');
    }
    
    setMessageInput('');
  };

  const generateSignal = async () => {
    addChatMessage('system', '🔄 Generating signal...');
    try {
      const response = await axios.post(`${API}/signals/force-generate`);
      if (response.data?.success) {
        addChatMessage('bot', `✅ ${response.data.message}`);
        toast.success('Signal generated and sent to Telegram!');
        fetchHistory();
      } else {
        addChatMessage('bot', '⚠️ No signal generated');
      }
    } catch (error) {
      addChatMessage('bot', '❌ Signal generation failed');
      toast.error('Failed to generate signal');
    }
  };

  const addChatMessage = (type, message) => {
    setChatMessages(prev => [...prev, {
      type,
      message,
      time: new Date().toLocaleTimeString()
    }]);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">📱 Telegram Bot Control</h1>
          <p className="text-slate-400">Manage your trading bot and view activity</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge className={botStatus.is_running ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
            {botStatus.is_running ? '🟢 Running' : '🔴 Stopped'}
          </Badge>
          <Badge className={botStatus.demo_mode ? 'bg-blue-500/20 text-blue-400' : 'bg-orange-500/20 text-orange-400'}>
            {botStatus.demo_mode ? '🎮 DEMO' : '💰 REAL'}
          </Badge>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column - Controls & Status */}
        <div className="space-y-6">
          {/* Bot Controls */}
          <Card className="bg-slate-900/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white text-lg">🎛️ Bot Controls</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-2">
                <Button 
                  onClick={startBot} 
                  disabled={isLoading || botStatus.is_running}
                  className="bg-green-600 hover:bg-green-700"
                >
                  ▶️ Start
                </Button>
                <Button 
                  onClick={stopBot} 
                  disabled={isLoading || !botStatus.is_running}
                  className="bg-red-600 hover:bg-red-700"
                >
                  ⏹️ Stop
                </Button>
              </div>
              
              <div className="pt-4 border-t border-slate-700 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">Auto-Trading</span>
                  <Switch 
                    checked={botStatus.auto_trading_enabled}
                    onCheckedChange={toggleAutoTrading}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">Demo Mode</span>
                  <Switch 
                    checked={botStatus.demo_mode}
                    onCheckedChange={toggleDemoMode}
                  />
                </div>
              </div>

              <Button 
                onClick={generateSignal}
                className="w-full bg-purple-600 hover:bg-purple-700"
              >
                ⚡ Force Generate Signal
              </Button>
            </CardContent>
          </Card>

          {/* Stats */}
          <Card className="bg-slate-900/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white text-lg">📊 Trading Stats</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-3 bg-slate-800/50 rounded-lg">
                  <div className="text-2xl font-bold text-purple-400">{stats.total_signals}</div>
                  <div className="text-xs text-slate-400">Signals Sent</div>
                </div>
                <div className="text-center p-3 bg-slate-800/50 rounded-lg">
                  <div className="text-2xl font-bold text-blue-400">{stats.total_trades}</div>
                  <div className="text-xs text-slate-400">Trades Placed</div>
                </div>
                <div className="text-center p-3 bg-slate-800/50 rounded-lg">
                  <div className="text-2xl font-bold text-green-400">{stats.wins}</div>
                  <div className="text-xs text-slate-400">Wins</div>
                </div>
                <div className="text-center p-3 bg-slate-800/50 rounded-lg">
                  <div className="text-2xl font-bold text-red-400">{stats.losses}</div>
                  <div className="text-xs text-slate-400">Losses</div>
                </div>
              </div>
              <div className="mt-4 p-3 bg-slate-800/50 rounded-lg text-center">
                <div className="text-3xl font-bold text-yellow-400">{stats.win_rate.toFixed(1)}%</div>
                <div className="text-sm text-slate-400">Win Rate</div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Middle Column - Chat Window */}
        <Card className="bg-slate-900/50 border-slate-700 lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-white text-lg">💬 Bot Activity Log</CardTitle>
            <CardDescription>Real-time bot messages and commands</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col h-[500px]">
            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto space-y-2 mb-4 p-3 bg-slate-800/30 rounded-lg">
              {chatMessages.length === 0 ? (
                <div className="text-center text-slate-500 py-8">
                  <p>No messages yet</p>
                  <p className="text-xs mt-1">Start the bot to see activity</p>
                </div>
              ) : (
                chatMessages.map((msg, idx) => (
                  <div key={idx} className={`p-2 rounded-lg text-sm ${
                    msg.type === 'user' ? 'bg-purple-600/20 text-purple-300 ml-8' :
                    msg.type === 'bot' ? 'bg-blue-600/20 text-blue-300 mr-8' :
                    'bg-slate-700/50 text-slate-400 text-center text-xs'
                  }`}>
                    <div className="flex justify-between items-start">
                      <span>{msg.message}</span>
                      <span className="text-xs text-slate-500 ml-2">{msg.time}</span>
                    </div>
                  </div>
                ))
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Message Input */}
            <div className="flex gap-2">
              <Input 
                value={messageInput}
                onChange={(e) => setMessageInput(e.target.value)}
                placeholder="Send message to Telegram..."
                className="bg-slate-800 border-slate-600"
                onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              />
              <Button onClick={sendMessage} className="bg-purple-600 hover:bg-purple-700">
                📤
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Right Column - Signal & Trade History */}
        <div className="space-y-6">
          {/* Recent Signals */}
          <Card className="bg-slate-900/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white text-lg">⚡ Recent Signals</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-[200px] overflow-y-auto">
                {signalHistory.length === 0 ? (
                  <p className="text-slate-500 text-center py-4">No signals yet</p>
                ) : (
                  signalHistory.slice(0, 5).map((signal, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg text-sm">
                      <div className="flex items-center gap-2">
                        <span className={signal.direction === 'CALL' ? 'text-green-400' : 'text-red-400'}>
                          {signal.direction === 'CALL' ? '📈' : '📉'}
                        </span>
                        <span className="text-white">{signal.symbol?.replace('_otc', '')}</span>
                      </div>
                      <Badge className={signal.direction === 'CALL' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
                        {signal.direction}
                      </Badge>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          {/* Trade Status */}
          <Card className="bg-slate-900/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white text-lg">💰 Trade Status</CardTitle>
              <CardDescription>Auto-trading execution status</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="p-3 bg-slate-800/50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-slate-400">Connection</span>
                    <Badge className={botStatus.is_running ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
                      {botStatus.is_running ? 'Connected' : 'Disconnected'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-slate-400">Auto-Trade</span>
                    <Badge className={botStatus.auto_trading_enabled ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}>
                      {botStatus.auto_trading_enabled ? 'Enabled' : 'Disabled'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Trade Amount</span>
                    <span className="text-white font-medium">${botStatus.trade_amount}</span>
                  </div>
                </div>

                {!botStatus.auto_trading_enabled && (
                  <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                    <p className="text-yellow-400 text-sm">
                      ⚠️ <strong>Manual Trading Mode</strong>
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      Signals sent to Telegram for manual execution. Enable auto-trading to execute trades automatically.
                    </p>
                  </div>
                )}

                <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                  <p className="text-blue-400 text-sm">
                    ℹ️ <strong>Note:</strong> Cloud IPs are blocked by Pocket Option.
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    Signals are sent to Telegram for manual trading.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default TelegramBotPage;
