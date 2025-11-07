import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const IntegrationPage = () => {
  const [integrations, setIntegrations] = useState({
    telegram: {
      enabled: false,
      bot_token: '',
      chat_id: '',
      username: ''
    },
    autobot: {
      enabled: false,
      webhook_url: '',
      signal_key: '',
      buy_message_template: JSON.stringify({
        "action": "BUY",
        "symbol": "{{symbol}}",
        "price": "{{price}}",
        "confidence": "{{confidence}}",
        "timeframe": "{{timeframe}}",
        "timestamp": "{{timestamp}}"
      }, null, 2),
      sell_message_template: JSON.stringify({
        "action": "SELL",
        "symbol": "{{symbol}}",
        "price": "{{price}}",
        "confidence": "{{confidence}}",
        "timeframe": "{{timeframe}}",
        "timestamp": "{{timestamp}}"
      }, null, 2)
    },
    pocket_option: {
      enabled: false,
      email: '',
      password: '',
      ssid: '',
      demo_mode: true
    },
    mt4: {
      enabled: false,
      server: '',
      login: '',
      password: '',
      account_type: 'demo'
    },
    mt5: {
      enabled: false,
      server: '',
      login: '',
      password: '',
      account_type: 'demo'
    }
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingConnection, setTestingConnection] = useState({});
  const [saveMessage, setSaveMessage] = useState('');

  useEffect(() => {
    fetchIntegrations();
  }, []);

  const fetchIntegrations = async () => {
    try {
      const response = await axios.get(`${API}/api/integrations/settings`);
      if (response.data.success) {
        setIntegrations(response.data.data);
      }
    } catch (error) {
      console.error('Error fetching integrations:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMessage('');
    try {
      const response = await axios.post(`${API}/api/integrations/settings`, integrations);
      if (response.data.success) {
        setSaveMessage('✅ Settings saved successfully!');
        setTimeout(() => setSaveMessage(''), 3000);
      }
    } catch (error) {
      setSaveMessage('❌ Failed to save settings');
      console.error('Error saving integrations:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async (platform) => {
    setTestingConnection({ ...testingConnection, [platform]: true });
    try {
      const response = await axios.post(`${API}/api/integrations/test/${platform}`, 
        integrations[platform]
      );
      if (response.data.success) {
        alert(`✅ ${platform.toUpperCase()} connection successful!\n${response.data.message}`);
      } else {
        alert(`❌ ${platform.toUpperCase()} connection failed:\n${response.data.message}`);
      }
    } catch (error) {
      alert(`❌ Error testing ${platform}: ${error.response?.data?.detail || error.message}`);
    } finally {
      setTestingConnection({ ...testingConnection, [platform]: false });
    }
  };

  const updateIntegration = (platform, field, value) => {
    setIntegrations({
      ...integrations,
      [platform]: {
        ...integrations[platform],
        [field]: value
      }
    });
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
        <div className="text-white text-xl">Loading integrations...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2 flex items-center">
            <span className="mr-3">🔗</span>
            Platform Integrations
          </h1>
          <p className="text-slate-300">Connect your trading platforms and signal delivery services</p>
        </div>

        {/* Save Message */}
        {saveMessage && (
          <div className={`mb-6 p-4 rounded-lg ${saveMessage.includes('✅') ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}`}>
            {saveMessage}
          </div>
        )}

        {/* Telegram Integration */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 mb-6 border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <span className="text-3xl mr-3">📱</span>
              <div>
                <h2 className="text-2xl font-bold text-white">Telegram Bot</h2>
                <p className="text-slate-400 text-sm">Send signals to Telegram channels/groups</p>
              </div>
            </div>
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={integrations.telegram.enabled}
                onChange={(e) => updateIntegration('telegram', 'enabled', e.target.checked)}
                className="w-6 h-6 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-2 focus:ring-purple-500"
              />
              <span className="ml-2 text-white">Enabled</span>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Bot Token</label>
              <input
                type="text"
                value={integrations.telegram.bot_token}
                onChange={(e) => updateIntegration('telegram', 'bot_token', e.target.value)}
                placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Chat ID</label>
              <input
                type="text"
                value={integrations.telegram.chat_id}
                onChange={(e) => updateIntegration('telegram', 'chat_id', e.target.value)}
                placeholder="-1001234567890"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Bot Username (optional)</label>
              <input
                type="text"
                value={integrations.telegram.username}
                onChange={(e) => updateIntegration('telegram', 'username', e.target.value)}
                placeholder="@YourBot"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={() => handleTestConnection('telegram')}
                disabled={testingConnection.telegram}
                className="w-full px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50"
              >
                {testingConnection.telegram ? 'Testing...' : 'Test Connection'}
              </button>
            </div>
          </div>
        </div>

        {/* AutobotSignal.io Integration */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 mb-6 border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <span className="text-3xl mr-3">🤖</span>
              <div>
                <h2 className="text-2xl font-bold text-white">AutobotSignal.io</h2>
                <p className="text-slate-400 text-sm">Send signals with custom JSON payloads</p>
              </div>
            </div>
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={integrations.autobot.enabled}
                onChange={(e) => updateIntegration('autobot', 'enabled', e.target.checked)}
                className="w-6 h-6 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-2 focus:ring-purple-500"
              />
              <span className="ml-2 text-white">Enabled</span>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Webhook URL</label>
              <input
                type="text"
                value={integrations.autobot.webhook_url}
                onChange={(e) => updateIntegration('autobot', 'webhook_url', e.target.value)}
                placeholder="https://autobotsignal.io/webhook"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Signal Key</label>
              <input
                type="text"
                value={integrations.autobot.signal_key}
                onChange={(e) => updateIntegration('autobot', 'signal_key', e.target.value)}
                placeholder="Your signal key"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          {/* JSON Message Templates */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                BUY Signal JSON Template
              </label>
              <p className="text-xs text-slate-500 mb-2">Variables: symbol, price, confidence, timeframe, timestamp</p>
              <textarea
                value={integrations.autobot.buy_message_template}
                onChange={(e) => updateIntegration('autobot', 'buy_message_template', e.target.value)}
                rows="10"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 font-mono text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                SELL Signal JSON Template
              </label>
              <p className="text-xs text-slate-500 mb-2">Variables: symbol, price, confidence, timeframe, timestamp</p>
              <textarea
                value={integrations.autobot.sell_message_template}
                onChange={(e) => updateIntegration('autobot', 'sell_message_template', e.target.value)}
                rows="10"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 font-mono text-sm"
              />
            </div>
          </div>

          <div className="mt-4">
            <button
              onClick={() => handleTestConnection('autobot')}
              disabled={testingConnection.autobot}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50"
            >
              {testingConnection.autobot ? 'Testing...' : 'Test Connection'}
            </button>
          </div>
        </div>

        {/* Pocket Option Integration */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 mb-6 border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <span className="text-3xl mr-3">🎯</span>
              <div>
                <h2 className="text-2xl font-bold text-white">Pocket Option</h2>
                <p className="text-slate-400 text-sm">Auto-trading on Pocket Option platform</p>
              </div>
            </div>
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={integrations.pocket_option.enabled}
                onChange={(e) => updateIntegration('pocket_option', 'enabled', e.target.checked)}
                className="w-6 h-6 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-2 focus:ring-purple-500"
              />
              <span className="ml-2 text-white">Enabled</span>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Email</label>
              <input
                type="email"
                value={integrations.pocket_option.email}
                onChange={(e) => updateIntegration('pocket_option', 'email', e.target.value)}
                placeholder="your@email.com"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Password</label>
              <input
                type="password"
                value={integrations.pocket_option.password}
                onChange={(e) => updateIntegration('pocket_option', 'password', e.target.value)}
                placeholder="••••••••"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">SSID (optional)</label>
              <input
                type="text"
                value={integrations.pocket_option.ssid}
                onChange={(e) => updateIntegration('pocket_option', 'ssid', e.target.value)}
                placeholder="Session ID"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Account Mode</label>
              <select
                value={integrations.pocket_option.demo_mode ? 'demo' : 'real'}
                onChange={(e) => updateIntegration('pocket_option', 'demo_mode', e.target.value === 'demo')}
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-purple-500"
              >
                <option value="demo">Demo Account</option>
                <option value="real">Real Account</option>
              </select>
            </div>
          </div>

          <div className="mt-4">
            <button
              onClick={() => handleTestConnection('pocket_option')}
              disabled={testingConnection.pocket_option}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50"
            >
              {testingConnection.pocket_option ? 'Testing...' : 'Test Connection'}
            </button>
          </div>
        </div>

        {/* MT4 Integration */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 mb-6 border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <span className="text-3xl mr-3">📊</span>
              <div>
                <h2 className="text-2xl font-bold text-white">MetaTrader 4 (MT4)</h2>
                <p className="text-slate-400 text-sm">Connect to your MT4 account</p>
              </div>
            </div>
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={integrations.mt4.enabled}
                onChange={(e) => updateIntegration('mt4', 'enabled', e.target.checked)}
                className="w-6 h-6 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-2 focus:ring-purple-500"
              />
              <span className="ml-2 text-white">Enabled</span>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Server</label>
              <input
                type="text"
                value={integrations.mt4.server}
                onChange={(e) => updateIntegration('mt4', 'server', e.target.value)}
                placeholder="broker-server.com:443"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Login</label>
              <input
                type="text"
                value={integrations.mt4.login}
                onChange={(e) => updateIntegration('mt4', 'login', e.target.value)}
                placeholder="Account number"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Password</label>
              <input
                type="password"
                value={integrations.mt4.password}
                onChange={(e) => updateIntegration('mt4', 'password', e.target.value)}
                placeholder="••••••••"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Account Type</label>
              <select
                value={integrations.mt4.account_type}
                onChange={(e) => updateIntegration('mt4', 'account_type', e.target.value)}
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-purple-500"
              >
                <option value="demo">Demo</option>
                <option value="real">Real</option>
              </select>
            </div>
          </div>

          <div className="mt-4">
            <button
              onClick={() => handleTestConnection('mt4')}
              disabled={testingConnection.mt4}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50"
            >
              {testingConnection.mt4 ? 'Testing...' : 'Test Connection'}
            </button>
          </div>
        </div>

        {/* MT5 Integration */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 mb-6 border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <span className="text-3xl mr-3">📈</span>
              <div>
                <h2 className="text-2xl font-bold text-white">MetaTrader 5 (MT5)</h2>
                <p className="text-slate-400 text-sm">Connect to your MT5 account</p>
              </div>
            </div>
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={integrations.mt5.enabled}
                onChange={(e) => updateIntegration('mt5', 'enabled', e.target.checked)}
                className="w-6 h-6 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-2 focus:ring-purple-500"
              />
              <span className="ml-2 text-white">Enabled</span>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Server</label>
              <input
                type="text"
                value={integrations.mt5.server}
                onChange={(e) => updateIntegration('mt5', 'server', e.target.value)}
                placeholder="broker-server.com:443"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Login</label>
              <input
                type="text"
                value={integrations.mt5.login}
                onChange={(e) => updateIntegration('mt5', 'login', e.target.value)}
                placeholder="Account number"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Password</label>
              <input
                type="password"
                value={integrations.mt5.password}
                onChange={(e) => updateIntegration('mt5', 'password', e.target.value)}
                placeholder="••••••••"
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Account Type</label>
              <select
                value={integrations.mt5.account_type}
                onChange={(e) => updateIntegration('mt5', 'account_type', e.target.value)}
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-purple-500"
              >
                <option value="demo">Demo</option>
                <option value="real">Real</option>
              </select>
            </div>
          </div>

          <div className="mt-4">
            <button
              onClick={() => handleTestConnection('mt5')}
              disabled={testingConnection.mt5}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50"
            >
              {testingConnection.mt5 ? 'Testing...' : 'Test Connection'}
            </button>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-end mt-8">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-8 py-3 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-lg font-bold text-lg disabled:opacity-50 transition-all transform hover:scale-105"
          >
            {saving ? '💾 Saving...' : '💾 Save All Settings'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default IntegrationPage;
