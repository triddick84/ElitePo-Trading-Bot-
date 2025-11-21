import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";
import { Toaster } from "sonner";
import "./App.css";

import SignalNotificationManager from "./components/SignalNotificationManager";

// Components
import Dashboard from "./components/Dashboard";
import SignalsPanel from "./components/SignalsPanel";
import MarketData from "./components/MarketData";
import PerformanceMetrics from "./components/PerformanceMetrics";
import BotControls from "./components/BotControls";
import BacktestPanel from "./components/BacktestPanel";
import ApiConfiguration from "./components/ApiConfiguration";
import IntegrationPage from "./components/IntegrationPage";
import StrategySelector from "./components/StrategySelector";
import MoneyManagement from "./components/MoneyManagement";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = BACKEND_URL ? `${BACKEND_URL}/api` : '';

function App() {
  // All hooks must be declared at the top before any conditional returns
  const [botStatus, setBotStatus] = useState(null);
  const [activeView, setActiveView] = useState("dashboard");
  const [isLoading, setIsLoading] = useState(true);
  const [liveSignals, setLiveSignals] = useState([]);
  const [globalNotificationSettings, setGlobalNotificationSettings] = useState({
    popupEnabled: true,
    soundEnabled: true,
    autoRefresh: true,
    signalInversion: false
  });

  // Fetch functions (must be declared before useEffect)
  const fetchBotStatus = async () => {
    try {
      const response = await axios.get(`${API}/bot/status`);
      setBotStatus(response.data);
    } catch (error) {
      console.error("Error fetching bot status:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchLiveSignals = async () => {
    try {
      const response = await axios.get(`${API}/signals/active`);
      const newSignals = response.data || [];
      
      // Filter for truly new signals (not already in our state)
      const existingIds = liveSignals.map(s => s.id);
      const freshSignals = newSignals.filter(signal => 
        !existingIds.includes(signal.id) && 
        signal.quality_check_passed && 
        signal.probability >= 95
      );
      
      if (freshSignals.length > 0) {
        setLiveSignals(prev => [...freshSignals, ...prev.slice(0, 9)]); // Keep last 10
      }
    } catch (error) {
      console.error("Error fetching live signals:", error);
    }
  };

  // useEffect must be after state declarations but before conditional returns
  useEffect(() => {
    if (!BACKEND_URL) return; // Skip if no backend URL
    
    fetchBotStatus();
    fetchLiveSignals();
    
    // Set up periodic status updates
    const statusInterval = setInterval(fetchBotStatus, 5000);
    const signalsInterval = setInterval(fetchLiveSignals, 3000); // Check for new signals every 3 seconds
    
    return () => {
      clearInterval(statusInterval);
      clearInterval(signalsInterval);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  
  // Check if backend URL is configured (now AFTER all hooks)
  if (!BACKEND_URL) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        backgroundColor: '#1a1a1a',
        color: '#fff',
        fontFamily: 'Arial, sans-serif',
        padding: '20px',
        textAlign: 'center'
      }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '1rem', color: '#ff4444' }}>⚠️ Configuration Error</h1>
        <p style={{ fontSize: '1.2rem', marginBottom: '1rem' }}>Backend URL is not configured</p>
        <p style={{ fontSize: '1rem', color: '#888' }}>Please ensure REACT_APP_BACKEND_URL is set in the .env file</p>
        <div style={{ 
          marginTop: '2rem', 
          padding: '1rem', 
          backgroundColor: '#2a2a2a', 
          borderRadius: '8px',
          maxWidth: '600px'
        }}>
          <p style={{ fontSize: '0.9rem', color: '#aaa', marginBottom: '0.5rem' }}>
            Current .env location: /app/frontend/.env
          </p>
          <p style={{ fontSize: '0.9rem', color: '#aaa' }}>
            Required variable: REACT_APP_BACKEND_URL=&lt;your-backend-url&gt;
          </p>
        </div>
        <button 
          onClick={() => window.location.reload()} 
          style={{
            marginTop: '2rem',
            padding: '12px 24px',
            fontSize: '1rem',
            backgroundColor: '#4CAF50',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer'
          }}
        >
          Reload Page
        </button>
      </div>
    );
  }

  const handleSignalExecute = (signal) => {
    console.log("Executing trade signal:", signal);
    // Here you would integrate with Pocket Option API or manual execution
  };

  const handleSignalDismiss = (signalId) => {
    setLiveSignals(prev => prev.filter(s => s.id !== signalId));
  };

  const navigation = [
    { id: "dashboard", label: "Dashboard", icon: "📊" },
    { id: "signals", label: "Signals", icon: "📡" },
    { id: "strategies", label: "Strategy Selector", icon: "🎯" },
    { id: "market", label: "Market Data", icon: "📈" },
    { id: "performance", label: "Performance", icon: "📉" },
    { id: "controls", label: "Bot Controls", icon: "⚙️" },
    { id: "backtest", label: "Backtesting", icon: "🧪" },
    { id: "integrations", label: "Integrations", icon: "🔗" },
    { id: "api", label: "API Config", icon: "🔑" }
  ];

  const renderActiveView = () => {
    switch (activeView) {
      case "dashboard":
        return (
          <Dashboard 
            botStatus={botStatus} 
            liveSignals={liveSignals} 
            setLiveSignals={setLiveSignals}
            notificationSettings={globalNotificationSettings}
            setNotificationSettings={setGlobalNotificationSettings}
          />
        );
      case "signals":
        return <SignalsPanel />;
      case "strategies":
        return <StrategySelector />;
      case "market":
        return <MarketData />;
      case "performance":
        return <PerformanceMetrics />;
      case "controls":
        return <BotControls onStatusUpdate={fetchBotStatus} />;
      case "backtest":
        return <BacktestPanel />;
      case "integrations":
        return <IntegrationPage />;
      case "api":
        return <ApiConfiguration />;
      default:
        return <Dashboard botStatus={botStatus} />;
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] trading-grid flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="animate-spin w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full mx-auto glow-purple"></div>
          <p className="text-slate-300 text-lg font-medium">Loading GPT Signal Bot...</p>
          <p className="text-slate-500 text-sm">Initializing trading systems...</p>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#0a0a0f] trading-grid">
        {/* Header */}
        <header className="bg-[#13131a]/80 backdrop-blur-xl border-b border-[#2a2a35] sticky top-0 z-50">
          <div className="container mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="w-10 h-10 bg-gradient-to-br from-purple-600 to-purple-800 rounded-xl flex items-center justify-center shadow-lg glow-purple">
                  <span className="text-white font-bold text-lg">🤖</span>
                </div>
                <div>
                  <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-purple-600 bg-clip-text text-transparent">GPT Signal Bot</h1>
                  <p className="text-slate-500 text-sm">AI-Powered Trading System • Real Market Data</p>
                </div>
              </div>
              
              {/* Status Indicator */}
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2 bg-[#1a1a24] px-4 py-2 rounded-lg border border-[#2a2a35]">
                  <div className={`w-3 h-3 rounded-full ${
                    botStatus?.is_running ? 'bg-green-500 animate-pulse shadow-lg shadow-green-500/50' : 'bg-red-500 shadow-lg shadow-red-500/50'
                  }`}></div>
                  <span className="text-slate-300 font-medium">
                    {botStatus?.is_running ? 'Active' : 'Stopped'}
                  </span>
                </div>
                <div className="text-slate-400 text-sm bg-[#1a1a24] px-4 py-2 rounded-lg border border-[#2a2a35]">
                  Mode: <span className="text-purple-400 font-semibold">{botStatus?.current_mode || 'live'}</span>
                </div>
                <div className="flex items-center space-x-1 text-green-400 text-sm bg-[#1a1a24] px-4 py-2 rounded-lg border border-[#2a2a35]">
                  <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse shadow-lg shadow-green-500/50"></span>
                  <span>Live Data</span>
                </div>
              </div>
            </div>
          </div>
        </header>

        <div className="flex">
          {/* Sidebar Navigation */}
          <nav className="w-64 bg-[#13131a]/50 backdrop-blur-xl border-r border-[#2a2a35] min-h-screen">
            <div className="p-6">
              <div className="space-y-2">
                {navigation.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setActiveView(item.id)}
                    className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 group ${
                      activeView === item.id
                        ? 'bg-purple-600/20 text-purple-400 border border-purple-500/30 shadow-lg glow-purple'
                        : 'text-slate-400 hover:text-white hover:bg-[#1a1a24] hover:border hover:border-[#2a2a35]'
                    }`}
                    data-testid={`nav-${item.id}`}
                  >
                    <span className="text-lg group-hover:scale-110 transition-transform duration-200">{item.icon}</span>
                    <span className="font-medium">{item.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </nav>

          {/* Main Content */}
          <main className="flex-1 p-6 bg-gradient-to-br from-[#0a0a0f] via-[#0f0f16] to-[#0a0a0f]">
            <Routes>
              <Route path="/*" element={renderActiveView()} />
            </Routes>
          </main>
        </div>

        {/* Live Signal Notifications */}
        <SignalNotificationManager
          signals={liveSignals}
          onSignalExecute={handleSignalExecute}
          onSignalDismiss={handleSignalDismiss}
          notificationSettings={globalNotificationSettings}
        />

        {/* Toast Notifications */}
        <Toaster 
          position="top-right" 
          theme="dark" 
          richColors 
          closeButton
        />
      </div>
    </BrowserRouter>
  );
}

export default App;