import React, { useState, useEffect } from "react";
import { BrowserRouter } from "react-router-dom";
import axios from "axios";
import { Toaster } from "sonner";
import "./App.css";

import SignalNotificationManager from "./components/SignalNotificationManager";

// Core Components
import DashboardRestructured from "./components/DashboardRestructured";
import TelegramBotPage from "./components/TelegramBotPage";
import StrategyBuilder from "./components/StrategyBuilder";
import AIMLModelsPage from "./components/AIMLModelsPage";
import MLLabPage from "./components/MLLabPage";
import LatencyDashboard from "./components/LatencyDashboard";
import UserApprovalsPage from "./components/UserApprovalsPage";
import PerformancePage from "./components/PerformancePage";
import SettingsPage from "./components/SettingsPage";
import PocketOptionPage from "./components/PocketOptionPage";
import MobileAutoTraderPage from "./components/MobileAutoTraderPage";
import RiskGuardPage from "./components/RiskGuardPage";
import BotLogo from "./components/BotLogo";
import MicrostructureDashboard from "./components/MicrostructureDashboard";
import EliteScreener from "./components/EliteScreener";
import IntegrationsPage from "./components/IntegrationsPage";
import SignalRoutingPage from "./components/SignalRoutingPage";
import TmaAdminPage from "./components/TmaAdminPage";
import { AuthProvider, LoginPage, useAuth } from "./components/AuthComponents";
import {
  LayoutDashboard, Send, LineChart, Smartphone, Shield, Waves,
  SearchCode, Plug, Route, UserCheck, Target, Brain, FlaskConical,
  Zap, Users, BarChart3, Settings as SettingsIcon,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = BACKEND_URL ? `${BACKEND_URL}/api` : '';

// Protected App Content - only shown when authenticated
function ProtectedApp() {
  const { user, logout, isAuthenticated, loading, token, isAdmin } = useAuth();
  
  // All hooks must be declared at the top before any conditional returns
  const [botStatus, setBotStatus] = useState(null);
  const [activeView, setActiveView] = useState("dashboard");
  const [isLoading, setIsLoading] = useState(true);
  const [liveSignals, setLiveSignals] = useState([]);
  const [pendingUserCount, setPendingUserCount] = useState(0);
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
    if (!BACKEND_URL || !isAuthenticated) return; // Skip if no backend URL or not authenticated
    
    fetchBotStatus();
    fetchLiveSignals();
    
    // Set up periodic status updates
    const statusInterval = setInterval(fetchBotStatus, 5000);
    const signalsInterval = setInterval(fetchLiveSignals, 3000); // Check for new signals every 3 seconds
    
    // Listen for custom navigation events
    const handleNavigate = (event) => {
      if (event.detail) {
        setActiveView(event.detail);
      }
    };
    window.addEventListener('navigate', handleNavigate);
    
    return () => {
      clearInterval(statusInterval);
      clearInterval(signalsInterval);
      window.removeEventListener('navigate', handleNavigate);
    };
  }, [isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

  // Iter 97 — Poll pending user count for admins so the sidebar badge stays fresh
  useEffect(() => {
    if (!isAuthenticated || !isAdmin || !token) {
      setPendingUserCount(0);
      return undefined;
    }
    const fetchPending = async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/auth/users/pending`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (r.ok) {
          const d = await r.json();
          setPendingUserCount(d.count || 0);
        }
      } catch (_e) { /* silent */ }
    };
    fetchPending();
    const iv = setInterval(fetchPending, 30000);
    return () => clearInterval(iv);
  }, [isAuthenticated, isAdmin, token]);
  
  // Show loading while checking auth
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-400">Loading...</p>
        </div>
      </div>
    );
  }
  
  // Show login page if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="mx-auto mb-4 flex justify-center">
              <BotLogo size={88} glow dataTestId="app-login-logo" />
            </div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-300 via-sky-400 to-fuchsia-400 bg-clip-text text-transparent">AI's Elite PO Traders Bot</h1>
            <p className="text-slate-500 mt-2">AI-Powered Trading System</p>
          </div>
          <LoginPage />
        </div>
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
    { id: "dashboard",      label: "Dashboard",         Icon: LayoutDashboard },
    { id: "telegram-bot",   label: "Telegram Bot",      Icon: Send },
    { id: "pocket-option",  label: "Pocket Option",     Icon: LineChart },
    { id: "mobile-trader",  label: "Mobile Auto-Trade", Icon: Smartphone },
    { id: "riskguard",      label: "RiskGuard",         Icon: Shield },
    { id: "microstructure", label: "Microstructure",    Icon: Waves },
    { id: "elite-screener", label: "Elite Screener",    Icon: SearchCode },
    { id: "integrations",   label: "Integrations",      Icon: Plug },
    { id: "signal-routing", label: "Signal Routing",    Icon: Route },
    { id: "tma-admin",      label: "TMA KYC Admin",     Icon: UserCheck },
    { id: "strategies",     label: "Strategies",        Icon: Target },
    { id: "ai-models",      label: "AI Models",         Icon: Brain },
    { id: "ml-lab",         label: "ML Lab",            Icon: FlaskConical },
    { id: "latency",        label: "Latency",           Icon: Zap },
    { id: "user-approvals", label: "User Approvals",    Icon: Users, adminOnly: true },
    { id: "performance",    label: "Performance",       Icon: BarChart3 },
    { id: "settings",       label: "Settings",          Icon: SettingsIcon },
  ];

  const renderActiveView = () => {
    switch (activeView) {
      case "dashboard":
        return (
          <DashboardRestructured 
            botStatus={botStatus} 
            liveSignals={liveSignals} 
            setLiveSignals={setLiveSignals}
            notificationSettings={globalNotificationSettings}
            setNotificationSettings={setGlobalNotificationSettings}
          />
        );
      case "telegram-bot":
        return <TelegramBotPage />;
      case "pocket-option":
        return <PocketOptionPage />;
      case "mobile-trader":
        return <MobileAutoTraderPage />;
      case "riskguard":
        return <RiskGuardPage />;
      case "microstructure":
        return <MicrostructureDashboard />;
      case "elite-screener":
        return <EliteScreener />;
      case "integrations":
        return <IntegrationsPage />;
      case "signal-routing":
        return <SignalRoutingPage />;
      case "tma-admin":
        return <TmaAdminPage />;
      case "strategies":
        return <StrategyBuilder />;
      case "ai-models":
        return <AIMLModelsPage />;
      case "ml-lab":
        return <MLLabPage />;
      case "latency":
        return <LatencyDashboard />;
      case "user-approvals":
        return <UserApprovalsPage />;
      case "performance":
        return <PerformancePage />;
      case "settings":
        return <SettingsPage />;
      default:
        return (
          <DashboardRestructured 
            botStatus={botStatus} 
            liveSignals={liveSignals} 
            setLiveSignals={setLiveSignals}
            notificationSettings={globalNotificationSettings}
            setNotificationSettings={setGlobalNotificationSettings}
          />
        );
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] trading-grid flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="mx-auto flex justify-center">
            <BotLogo size={96} glow dataTestId="app-loading-logo" />
          </div>
          <div className="animate-spin w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full mx-auto"></div>
          <p className="text-slate-300 text-lg font-medium">Loading AI's Elite PO Traders Bot...</p>
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
                <BotLogo size={44} glow dataTestId="app-header-logo" />
                <div>
                  <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-300 via-sky-400 to-fuchsia-400 bg-clip-text text-transparent">AI's Elite PO Traders Bot</h1>
                  <p className="text-slate-500 text-sm">AI-Powered Trading System • Real Market Data</p>
                </div>
              </div>
              
              {/* Status Indicator and User Menu */}
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
                
                {/* User Menu */}
                <div className="flex items-center space-x-2 bg-[#1a1a24] px-4 py-2 rounded-lg border border-[#2a2a35]">
                  <span className="text-purple-400">👤</span>
                  <span className="text-slate-300 font-medium">{user?.username}</span>
                  <span className="text-xs text-slate-500 bg-purple-500/20 px-2 py-0.5 rounded">{user?.role}</span>
                </div>
                <button
                  onClick={logout}
                  className="flex items-center space-x-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 px-4 py-2 rounded-lg border border-red-500/30 transition-colors"
                >
                  <span>🚪</span>
                  <span className="font-medium">Logout</span>
                </button>
              </div>
            </div>
          </div>
        </header>

        <div className="flex">
          {/* Sidebar Navigation */}
          <nav className="w-64 bg-[#13131a]/50 backdrop-blur-xl border-r border-[#2a2a35] min-h-screen">
            <div className="p-6">
              <div className="space-y-2">
                {navigation
                  .filter((item) => !item.adminOnly || isAdmin)
                  .map((item) => {
                    const IconCmp = item.Icon;
                    const isActive = activeView === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => setActiveView(item.id)}
                        className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 group ${
                          isActive
                            ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-lg shadow-cyan-500/10'
                            : 'text-slate-400 hover:text-white hover:bg-[#1a1a24] hover:border hover:border-[#2a2a35]'
                        }`}
                        data-testid={`nav-${item.id}`}
                      >
                        {IconCmp && (
                          <IconCmp
                            className={`w-4 h-4 shrink-0 group-hover:scale-110 transition-transform duration-200 ${
                              isActive ? 'text-cyan-300' : 'text-slate-400 group-hover:text-cyan-300'
                            }`}
                          />
                        )}
                        <span className="font-medium flex-1 text-left">{item.label}</span>
                        {item.id === 'user-approvals' && pendingUserCount > 0 && (
                          <span
                            className="ml-auto flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-rose-500 text-white text-[10px] font-bold shadow-lg shadow-rose-500/50"
                            data-testid="pending-users-badge"
                          >
                            {pendingUserCount > 99 ? '99+' : pendingUserCount}
                          </span>
                        )}
                      </button>
                    );
                  })}
              </div>
            </div>
          </nav>

          {/* Main Content */}
          <main className="flex-1 p-6 bg-gradient-to-br from-[#0a0a0f] via-[#0f0f16] to-[#0a0a0f]">
            {renderActiveView()}
          </main>
        </div>

        {/* Live Signal Notifications */}
        <SignalNotificationManager
          signals={liveSignals}
          onSignalExecute={handleSignalExecute}
          onSignalDismiss={handleSignalDismiss}
          notificationSettings={globalNotificationSettings}
        />
      </div>
    </BrowserRouter>
  );
}

// Main App with Auth Provider
function App() {
  // Check if backend URL is configured
  if (!BACKEND_URL) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        backgroundColor: '#0a0a0f',
        color: '#fff',
        fontFamily: 'Arial, sans-serif',
        padding: '20px',
        textAlign: 'center'
      }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '1rem', color: '#ff4444' }}>⚠️ Configuration Error</h1>
        <p style={{ fontSize: '1.2rem', marginBottom: '1rem' }}>Backend URL is not configured</p>
      </div>
    );
  }

  return (
    <AuthProvider>
      <ProtectedApp />
      <Toaster 
        position="top-right" 
        theme="dark" 
        richColors 
        closeButton
      />
    </AuthProvider>
  );
}

export default App;