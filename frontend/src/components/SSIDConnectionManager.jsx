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

export default SSIDConnectionManager;
