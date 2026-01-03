import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Alert, AlertDescription, AlertTitle } from './ui/alert';
import { 
  Wifi, 
  WifiOff, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  Copy,
  ExternalLink,
  Bell,
  Settings,
  Play,
  Pause
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const SSIDConnectionManager = () => {
  // Connection state
  const [connectionStatus, setConnectionStatus] = useState({
    connected: false,
    is_demo: true,
    balance: 0,
    account_id: null
  });
  
  // SSID input
  const [ssidInput, setSsidInput] = useState('');
  const [isDemo, setIsDemo] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateResult, setUpdateResult] = useState(null);
  
  // Health monitor
  const [healthStatus, setHealthStatus] = useState(null);
  const [alerts, setAlerts] = useState([]);
  
  // Auto trading
  const [autoTradingEnabled, setAutoTradingEnabled] = useState(false);
  
  // Loading states
  const [isLoading, setIsLoading] = useState(true);

  // Fetch connection status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/pocket-option/status`);
      const data = await response.json();
      if (data.success) {
        setConnectionStatus({
          connected: data.connected,
          is_demo: data.is_demo,
          balance: data.balance || 0,
          account_id: data.account_id
        });
      }
    } catch (error) {
      console.error('Failed to fetch status:', error);
    }
  }, []);

  // Fetch health monitor status
  const fetchHealthStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/ssid/health/status`);
      const data = await response.json();
      if (data.success) {
        setHealthStatus(data.status);
        setAlerts(data.status?.recent_alerts || []);
      }
    } catch (error) {
      console.error('Failed to fetch health status:', error);
    }
  }, []);

  // Initial load and polling
  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      await Promise.all([fetchStatus(), fetchHealthStatus()]);
      setIsLoading(false);
    };
    
    loadData();
    
    // Poll every 30 seconds
    const interval = setInterval(() => {
      fetchStatus();
      fetchHealthStatus();
    }, 30000);
    
    return () => clearInterval(interval);
  }, [fetchStatus, fetchHealthStatus]);

  // Update SSID
  const handleUpdateSSID = async () => {
    if (!ssidInput.trim()) {
      setUpdateResult({ success: false, error: 'Please enter an SSID' });
      return;
    }
    
    setIsUpdating(true);
    setUpdateResult(null);
    
    try {
      const response = await fetch(`${API_URL}/api/pocket-option/update-ssid?ssid=${encodeURIComponent(ssidInput)}&is_demo=${isDemo}`, {
        method: 'POST'
      });
      const data = await response.json();
      
      setUpdateResult(data);
      
      if (data.success) {
        setSsidInput('');
        // Refresh status
        setTimeout(() => {
          fetchStatus();
          fetchHealthStatus();
        }, 2000);
      }
    } catch (error) {
      setUpdateResult({ success: false, error: error.message });
    } finally {
      setIsUpdating(false);
    }
  };

  // Test connection
  const handleTestConnection = async () => {
    setIsUpdating(true);
    try {
      const response = await fetch(`${API_URL}/api/pocket-option/test-connection`, {
        method: 'POST'
      });
      const data = await response.json();
      setUpdateResult(data);
      await fetchStatus();
    } catch (error) {
      setUpdateResult({ success: false, error: error.message });
    } finally {
      setIsUpdating(false);
    }
  };

  // Toggle auto trading
  const toggleAutoTrading = async () => {
    try {
      const endpoint = autoTradingEnabled ? 'stop' : 'start';
      const response = await fetch(`${API_URL}/api/trading/auto/${endpoint}`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        setAutoTradingEnabled(!autoTradingEnabled);
      }
    } catch (error) {
      console.error('Failed to toggle auto trading:', error);
    }
  };

  // Copy instructions to clipboard
  const copyInstructions = () => {
    const instructions = `How to get SSID:
1. Open https://pocketoption.com
2. Login to your account
3. Press F12 (Developer Tools)
4. Go to Network tab → WS filter
5. Refresh page (F5)
6. Find WebSocket connection
7. Click Messages tab
8. Find: 42["auth",{"session":"...
9. Copy entire message`;
    
    navigator.clipboard.writeText(instructions);
  };

  // Open Pocket Option
  const openPocketOption = () => {
    window.open('https://pocketoption.com', '_blank');
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4">
      {/* Connection Status Card */}
      <Card className={connectionStatus.connected ? 'border-green-500' : 'border-red-500'}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              {connectionStatus.connected ? (
                <Wifi className="w-5 h-5 text-green-500" />
              ) : (
                <WifiOff className="w-5 h-5 text-red-500" />
              )}
              Connection Status
            </CardTitle>
            <Badge variant={connectionStatus.connected ? 'success' : 'destructive'}>
              {connectionStatus.connected ? 'Connected' : 'Disconnected'}
            </Badge>
          </div>
          <CardDescription>
            Pocket Option API Connection
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="text-sm text-gray-500">Account Type</div>
              <div className="text-lg font-semibold">
                {connectionStatus.is_demo ? '🎮 Demo' : '💰 Real'}
              </div>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="text-sm text-gray-500">Balance</div>
              <div className="text-lg font-semibold text-green-600">
                ${connectionStatus.balance?.toFixed(2) || '0.00'}
              </div>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="text-sm text-gray-500">Account ID</div>
              <div className="text-lg font-semibold">
                {connectionStatus.account_id || 'N/A'}
              </div>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="text-sm text-gray-500">Auto Trading</div>
              <Button 
                variant={autoTradingEnabled ? 'destructive' : 'default'}
                size="sm"
                onClick={toggleAutoTrading}
                disabled={!connectionStatus.connected}
                className="mt-1"
              >
                {autoTradingEnabled ? <Pause className="w-4 h-4 mr-1" /> : <Play className="w-4 h-4 mr-1" />}
                {autoTradingEnabled ? 'Stop' : 'Start'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* SSID Update Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Update SSID
          </CardTitle>
          <CardDescription>
            Enter your SSID from Pocket Option browser session
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Instructions Alert */}
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>How to get SSID</AlertTitle>
            <AlertDescription className="mt-2">
              <ol className="list-decimal list-inside space-y-1 text-sm">
                <li>Open Pocket Option and login</li>
                <li>Press F12 (Developer Tools)</li>
                <li>Go to Network → WS (WebSocket)</li>
                <li>Refresh page (F5)</li>
                <li>Find message: <code className="bg-gray-100 px-1 rounded">42["auth",...</code></li>
                <li>Copy entire message and paste below</li>
              </ol>
              <div className="flex gap-2 mt-3">
                <Button variant="outline" size="sm" onClick={openPocketOption}>
                  <ExternalLink className="w-4 h-4 mr-1" />
                  Open Pocket Option
                </Button>
                <Button variant="outline" size="sm" onClick={copyInstructions}>
                  <Copy className="w-4 h-4 mr-1" />
                  Copy Instructions
                </Button>
              </div>
            </AlertDescription>
          </Alert>

          {/* SSID Input */}
          <div className="space-y-3">
            <Input
              placeholder='Paste SSID here: 42["auth",{"session":"..."}]'
              value={ssidInput}
              onChange={(e) => setSsidInput(e.target.value)}
              className="font-mono text-sm"
            />
            
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  checked={isDemo}
                  onChange={() => setIsDemo(true)}
                  className="w-4 h-4"
                />
                <span>🎮 Demo Account</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  checked={!isDemo}
                  onChange={() => setIsDemo(false)}
                  className="w-4 h-4"
                />
                <span>💰 Real Account</span>
              </label>
            </div>

            <div className="flex gap-2">
              <Button 
                onClick={handleUpdateSSID} 
                disabled={isUpdating || !ssidInput.trim()}
                className="flex-1"
              >
                {isUpdating ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <CheckCircle className="w-4 h-4 mr-2" />
                )}
                Update SSID
              </Button>
              <Button 
                variant="outline"
                onClick={handleTestConnection}
                disabled={isUpdating}
              >
                Test Connection
              </Button>
            </div>
          </div>

          {/* Update Result */}
          {updateResult && (
            <Alert variant={updateResult.success ? 'default' : 'destructive'}>
              {updateResult.success ? (
                <CheckCircle className="h-4 w-4" />
              ) : (
                <AlertTriangle className="h-4 w-4" />
              )}
              <AlertTitle>
                {updateResult.success ? 'Success' : 'Error'}
              </AlertTitle>
              <AlertDescription>
                {updateResult.message || updateResult.error}
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Health Monitor Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="w-5 h-5" />
            Health Monitor
          </CardTitle>
          <CardDescription>
            SSID expiry tracking and connection alerts
          </CardDescription>
        </CardHeader>
        <CardContent>
          {healthStatus ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div className="text-sm text-gray-500 flex items-center gap-1">
                    <Clock className="w-4 h-4" />
                    Last Check
                  </div>
                  <div className="text-sm font-medium">
                    {healthStatus.last_check 
                      ? new Date(healthStatus.last_check).toLocaleTimeString()
                      : 'Never'}
                  </div>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div className="text-sm text-gray-500">SSID Set</div>
                  <div className="text-sm font-medium">
                    {healthStatus.ssid_set_time 
                      ? new Date(healthStatus.ssid_set_time).toLocaleTimeString()
                      : 'Not set'}
                  </div>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div className="text-sm text-gray-500">Est. Expiry</div>
                  <div className="text-sm font-medium text-orange-600">
                    {healthStatus.estimated_expiry 
                      ? new Date(healthStatus.estimated_expiry).toLocaleTimeString()
                      : 'Unknown'}
                  </div>
                </div>
              </div>

              {/* Alerts */}
              {alerts.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-sm">Recent Alerts</h4>
                  <div className="max-h-40 overflow-y-auto space-y-2">
                    {alerts.slice(-5).reverse().map((alert, index) => (
                      <div 
                        key={index}
                        className={`p-2 rounded text-sm ${
                          alert.level === 'critical' ? 'bg-red-100 text-red-800' :
                          alert.level === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-blue-100 text-blue-800'
                        }`}
                      >
                        <div className="font-medium">{alert.alert_type}</div>
                        <div>{alert.message}</div>
                        <div className="text-xs opacity-70">
                          {new Date(alert.timestamp).toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-4 text-gray-500">
              Health monitor not initialized
            </div>
          )}
        </CardContent>
      </Card>

      {/* Desktop Client Card - HYBRID SOLUTION */}
      <Card className="border-green-500/30 bg-green-500/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="text-xl">🖥️</span>
            Desktop Trading Client
            <Badge className="bg-green-500/20 text-green-600">RECOMMENDED</Badge>
          </CardTitle>
          <CardDescription>
            Run the trading bot on your PC for reliable connection (bypasses IP blocking)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DesktopClientSection />
        </CardContent>
      </Card>

      {/* Auto Login Card - CLOUD BASED */}
      <Card className="border-purple-500/30">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="text-xl">🤖</span>
            Auto Login (Cloud)
            <Badge variant="outline" className="text-yellow-600">IP Blocked</Badge>
          </CardTitle>
          <CardDescription>
            Cloud-based auto login (currently blocked by Pocket Option)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AutoLoginSection 
            onSuccess={(ssid) => {
              setSsidInput(ssid);
              fetchStatus();
              fetchHealthStatus();
            }}
          />
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={fetchStatus}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh Status
            </Button>
            <Button 
              variant="outline" 
              onClick={() => window.open(`${API_URL}/api/docs`, '_blank')}
            >
              <ExternalLink className="w-4 h-4 mr-2" />
              API Docs
            </Button>
            <Button 
              variant="outline"
              onClick={() => window.open('/local-bot-download', '_blank')}
            >
              Download Local Bot
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

// Desktop Client Sub-Component
const DesktopClientSection = () => {
  const [desktopStatus, setDesktopStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchDesktopStatus();
    const interval = setInterval(fetchDesktopStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchDesktopStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/desktop-client/status`);
      const data = await response.json();
      if (data.success) {
        setDesktopStatus(data.status);
      }
    } catch (error) {
      console.error('Failed to fetch desktop status:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const downloadClient = () => {
    window.open(`${API_URL}/api/desktop-client/download`, '_blank');
  };

  return (
    <div className="space-y-4">
      {/* Status */}
      <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${
            desktopStatus?.is_online ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
          }`} />
          <span className="font-medium">
            {desktopStatus?.is_online ? 'Desktop Client Online' : 'Desktop Client Offline'}
          </span>
        </div>
        {desktopStatus?.is_online && (
          <div className="text-sm text-gray-500">
            Balance: ${desktopStatus?.balance?.toFixed(2) || '0.00'} ({desktopStatus?.account_type})
          </div>
        )}
      </div>

      {/* Benefits */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
          <div className="font-medium text-green-700 dark:text-green-300">✅ No IP Blocking</div>
          <div className="text-gray-600 dark:text-gray-400 text-xs mt-1">
            Your home IP isn't blocked by Pocket Option
          </div>
        </div>
        <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
          <div className="font-medium text-green-700 dark:text-green-300">✅ Auto CAPTCHA</div>
          <div className="text-gray-600 dark:text-gray-400 text-xs mt-1">
            2Captcha integration solves CAPTCHAs automatically
          </div>
        </div>
        <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
          <div className="font-medium text-green-700 dark:text-green-300">✅ Direct Trading</div>
          <div className="text-gray-600 dark:text-gray-400 text-xs mt-1">
            Executes trades directly with lower latency
          </div>
        </div>
        <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
          <div className="font-medium text-green-700 dark:text-green-300">✅ Web UI Signals</div>
          <div className="text-gray-600 dark:text-gray-400 text-xs mt-1">
            Uses strategies from this web interface
          </div>
        </div>
      </div>

      {/* Setup Instructions */}
      <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
        <h4 className="font-medium text-blue-700 dark:text-blue-300 mb-2">Quick Setup (5 minutes)</h4>
        <ol className="text-sm text-gray-600 dark:text-gray-400 space-y-1 list-decimal list-inside">
          <li>Download the desktop client below</li>
          <li>Extract to a folder on your PC</li>
          <li>Edit <code className="bg-gray-200 dark:bg-gray-700 px-1 rounded">config.py</code> with your server URL</li>
          <li>Run: <code className="bg-gray-200 dark:bg-gray-700 px-1 rounded">pip install -r requirements.txt</code></li>
          <li>Run: <code className="bg-gray-200 dark:bg-gray-700 px-1 rounded">python main.py</code></li>
        </ol>
      </div>

      {/* Download Button */}
      <Button
        onClick={downloadClient}
        className="w-full bg-green-600 hover:bg-green-700 text-white"
      >
        <span className="mr-2">📥</span>
        Download Desktop Client
      </Button>

      {/* Recent Trades */}
      {desktopStatus?.recent_trades > 0 && (
        <div className="text-sm text-gray-500 text-center">
          {desktopStatus.recent_trades} trades executed via desktop client
        </div>
      )}
    </div>
  );
};

// Auto Login Sub-Component
const AutoLoginSection = ({ onSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [captchaApiKey, setCaptchaApiKey] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [loginResult, setLoginResult] = useState(null);
  const [loginStats, setLoginStats] = useState(null);

  // Fetch login stats on mount
  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/auto-login/stats`);
      const data = await response.json();
      if (data.success) {
        setLoginStats(data.stats);
      }
    } catch (error) {
      console.error('Failed to fetch login stats:', error);
    }
  };

  const handleAutoLogin = async () => {
    if (!email || !password) {
      setLoginResult({ success: false, error: 'Please enter email and password' });
      return;
    }

    setIsLoggingIn(true);
    setLoginResult(null);

    try {
      const params = new URLSearchParams({
        email,
        password,
        use_stealth_first: 'true'
      });
      
      if (captchaApiKey) {
        params.append('captcha_api_key', captchaApiKey);
      }

      const response = await fetch(`${API_URL}/api/auto-login/attempt?${params}`, {
        method: 'POST'
      });
      const data = await response.json();

      setLoginResult(data);
      
      if (data.success && data.result?.ssid) {
        onSuccess(data.result.ssid);
      }

      // Refresh stats
      fetchStats();
    } catch (error) {
      setLoginResult({ success: false, error: error.message });
    } finally {
      setIsLoggingIn(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Method Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
          <div className="font-medium text-purple-700 dark:text-purple-300">🥷 Stealth Browser (Free)</div>
          <div className="text-gray-600 dark:text-gray-400 text-xs mt-1">
            Uses undetected Chrome to bypass detection. May be blocked by CAPTCHA.
          </div>
        </div>
        <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <div className="font-medium text-blue-700 dark:text-blue-300">🧩 CAPTCHA Solver (~$0.003/login)</div>
          <div className="text-gray-600 dark:text-gray-400 text-xs mt-1">
            Falls back to 2Captcha if stealth fails. Requires API key.
          </div>
        </div>
      </div>

      {/* Login Stats */}
      {loginStats && (
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge variant="outline">
            Attempts: {loginStats.total_attempts}
          </Badge>
          <Badge variant="outline" className="text-green-600">
            Success: {loginStats.successful}
          </Badge>
          {loginStats.total_captcha_cost > 0 && (
            <Badge variant="outline" className="text-blue-600">
              Cost: ${loginStats.total_captcha_cost.toFixed(4)}
            </Badge>
          )}
        </div>
      )}

      {/* Credentials Input */}
      <div className="space-y-3">
        <Input
          type="email"
          placeholder="Pocket Option Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        
        {/* Advanced Options */}
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-sm text-purple-600 hover:underline"
        >
          {showAdvanced ? '▼ Hide' : '▶ Show'} Advanced Options
        </button>
        
        {showAdvanced && (
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg space-y-2">
            <div className="text-sm text-gray-500">
              2Captcha API Key (Optional - for CAPTCHA fallback)
            </div>
            <Input
              type="password"
              placeholder="2Captcha API Key"
              value={captchaApiKey}
              onChange={(e) => setCaptchaApiKey(e.target.value)}
            />
            <div className="text-xs text-gray-400">
              Get key from: <a href="https://2captcha.com" target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">2captcha.com</a>
              {' '}(~$2.99 per 1000 solves)
            </div>
          </div>
        )}

        <Button
          onClick={handleAutoLogin}
          disabled={isLoggingIn || !email || !password}
          className="w-full bg-purple-600 hover:bg-purple-700"
        >
          {isLoggingIn ? (
            <>
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              Attempting Auto Login...
            </>
          ) : (
            <>
              <span className="mr-2">🤖</span>
              Auto Login
            </>
          )}
        </Button>
      </div>

      {/* Login Result */}
      {loginResult && (
        <Alert variant={loginResult.success ? 'default' : 'destructive'}>
          {loginResult.success ? (
            <CheckCircle className="h-4 w-4" />
          ) : (
            <AlertTriangle className="h-4 w-4" />
          )}
          <AlertTitle>
            {loginResult.success ? '✅ Login Successful!' : '❌ Login Failed'}
          </AlertTitle>
          <AlertDescription>
            <div>{loginResult.message || loginResult.error}</div>
            {loginResult.result && (
              <div className="mt-2 text-xs space-y-1">
                <div>Method: {loginResult.result.method_used}</div>
                <div>Status: {loginResult.result.status}</div>
                {loginResult.result.captcha_cost > 0 && (
                  <div>CAPTCHA Cost: ${loginResult.result.captcha_cost.toFixed(4)}</div>
                )}
              </div>
            )}
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
};

export default SSIDConnectionManager;
