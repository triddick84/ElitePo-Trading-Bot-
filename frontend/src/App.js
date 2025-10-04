import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";
import "./App.css";

// Components
import Dashboard from "./components/Dashboard";
import SignalsPanel from "./components/SignalsPanel";
import MarketData from "./components/MarketData";
import PerformanceMetrics from "./components/PerformanceMetrics";
import BotControls from "./components/BotControls";
import BacktestPanel from "./components/BacktestPanel";
import ApiConfiguration from "./components/ApiConfiguration";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [botStatus, setBotStatus] = useState(null);
  const [activeView, setActiveView] = useState("dashboard");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchBotStatus();
    // Set up periodic status updates
    const interval = setInterval(fetchBotStatus, 5000);
    return () => clearInterval(interval);
  }, []);

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

  const navigation = [
    { id: "dashboard", label: "Dashboard", icon: "📊" },
    { id: "signals", label: "Trading Signals", icon: "📈" },
    { id: "market", label: "Market Data", icon: "💹" },
    { id: "performance", label: "Performance", icon: "🎯" },
    { id: "controls", label: "Bot Controls", icon: "⚙️" },
    { id: "backtest", label: "Backtesting", icon: "🧪" },
    { id: "api", label: "API Config", icon: "🔑" }
  ];

  const renderActiveView = () => {
    switch (activeView) {
      case "dashboard":
        return <Dashboard botStatus={botStatus} />;
      case "signals":
        return <SignalsPanel />;
      case "market":
        return <MarketData />;
      case "performance":
        return <PerformanceMetrics />;
      case "controls":
        return <BotControls onStatusUpdate={fetchBotStatus} />;
      case "backtest":
        return <BacktestPanel />;
      default:
        return <Dashboard botStatus={botStatus} />;
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="animate-spin w-16 h-16 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto"></div>
          <p className="text-slate-300 text-lg font-medium">Loading GPT Signal Bot...</p>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        {/* Header */}
        <header className="bg-slate-800/50 backdrop-blur-xl border-b border-slate-700/50 sticky top-0 z-50">
          <div className="container mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center">
                  <span className="text-white font-bold text-lg">🤖</span>
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-white">GPT Signal Bot</h1>
                  <p className="text-slate-400 text-sm">AI-Powered Trading System</p>
                </div>
              </div>
              
              {/* Status Indicator */}
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <div className={`w-3 h-3 rounded-full ${
                    botStatus?.is_running ? 'bg-green-500 animate-pulse' : 'bg-red-500'
                  }`}></div>
                  <span className="text-slate-300 font-medium">
                    {botStatus?.is_running ? 'Active' : 'Stopped'}
                  </span>
                </div>
                <div className="text-slate-400 text-sm">
                  Mode: {botStatus?.current_mode || 'Unknown'}
                </div>
              </div>
            </div>
          </div>
        </header>

        <div className="flex">
          {/* Sidebar Navigation */}
          <nav className="w-64 bg-slate-800/30 backdrop-blur-xl border-r border-slate-700/50 min-h-screen">
            <div className="p-6">
              <div className="space-y-2">
                {navigation.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setActiveView(item.id)}
                    className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                      activeView === item.id
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'text-slate-400 hover:text-white hover:bg-slate-700/30'
                    }`}
                    data-testid={`nav-${item.id}`}
                  >
                    <span className="text-lg">{item.icon}</span>
                    <span className="font-medium">{item.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </nav>

          {/* Main Content */}
          <main className="flex-1 p-6">
            <Routes>
              <Route path="/*" element={renderActiveView()} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;