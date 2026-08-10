import React, { useState, useEffect, createContext, useContext } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import { User, Lock, Mail, LogOut, Shield } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Auth Context
export const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(sessionStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      fetchCurrentUser();
    } else {
      setLoading(false);
    }
  }, [token]);

  const fetchCurrentUser = async () => {
    try {
      const response = await fetch(`${API_URL}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      if (data.success) {
        setUser(data.user);
      } else {
        logout();
      }
    } catch (error) {
      console.error('Auth error:', error);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (username, password) => {
    try {
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await response.json();
      
      if (data.success) {
        sessionStorage.setItem('token', data.token);
        setToken(data.token);
        setUser(data.user);
        toast.success(`Welcome back, ${data.user.username}!`);
        return { success: true };
      } else {
        // Iter 97 — status-gated failures come back as { detail: {code, message} }
        const detail = data.detail;
        if (detail && typeof detail === 'object' && detail.code) {
          const friendly = {
            ACCOUNT_PENDING: 'Your account is pending admin approval. You will be able to sign in once an admin approves you.',
            ACCOUNT_REJECTED: 'Your registration was rejected. Please contact an administrator.',
            ACCOUNT_SUSPENDED: 'Your account has been suspended. Please contact an administrator.',
          }[detail.code] || detail.message || 'Login failed';
          toast.error(friendly, { duration: 6000 });
          return { success: false, error: friendly, code: detail.code };
        }
        const errMsg = data.error || data.detail || 'Login failed';
        toast.error(typeof errMsg === 'string' ? errMsg : 'Login failed');
        return { success: false, error: errMsg };
      }
    } catch (error) {
      toast.error('Connection error');
      return { success: false, error: error.message };
    }
  };

  const register = async (username, email, password) => {
    try {
      const response = await fetch(`${API_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password })
      });
      const data = await response.json();
      
      // Iter 97 — Regular registrations now return HTTP 202 with `pending:true`
      // and NO token. Surface the approval-pending message and don't auto-login.
      if (data.success && data.pending) {
        toast.success(
          data.message || 'Registration received. Your account is pending admin approval.',
          { duration: 8000 },
        );
        return { success: true, pending: true };
      }
      if (data.success && data.token) {
        // Admin/seed path — auto-active
        sessionStorage.setItem('token', data.token);
        setToken(data.token);
        setUser(data.user);
        toast.success('Account created successfully!');
        return { success: true };
      }
      const errMsg = data.error || data.detail || 'Registration failed';
      toast.error(typeof errMsg === 'string' ? errMsg : 'Registration failed');
      return { success: false, error: errMsg };
    } catch (error) {
      toast.error('Connection error');
      return { success: false, error: error.message };
    }
  };

  const logout = () => {
    sessionStorage.removeItem('token');
    setToken(null);
    setUser(null);
    toast.info('Logged out');
  };

  const value = {
    user,
    token,
    loading,
    login,
    register,
    logout,
    isAuthenticated: !!user,
    isAdmin: user?.role === 'admin'
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// Login/Register Page Component
export const LoginPage = ({ onClose }) => {
  const { login, register } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  
  // Login form state
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  
  // Register form state
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    const result = await login(loginUsername, loginPassword);
    setIsLoading(false);
    if (result.success && onClose) {
      onClose();
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    if (regPassword !== regConfirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    if (regPassword.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }
    setIsLoading(true);
    const result = await register(regUsername, regEmail, regPassword);
    setIsLoading(false);
    // Iter 97 — Pending registrations keep the modal open (user isn't signed in
    // yet). Only auto-close on a real success (admin/seed with token).
    if (result.success && !result.pending && onClose) {
      onClose();
    }
  };

  return (
    <div className="flex items-center justify-center p-4">
      <Card className="w-full max-w-md bg-slate-900/90 border-slate-700">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-2">
            <Shield className="w-12 h-12 text-purple-500" />
          </div>
          <CardTitle className="text-2xl text-white">AI's Elite PO Traders Bot</CardTitle>
          <CardDescription>Sign in to access your trading dashboard</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="login-username">Username</Label>
              <div className="relative">
                <User className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
                <Input
                  id="login-username"
                  type="text"
                  placeholder="Enter username"
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  className="pl-10 bg-slate-800 border-slate-600"
                  required
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="login-password">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
                <Input
                  id="login-password"
                  type="password"
                  placeholder="Enter password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  className="pl-10 bg-slate-800 border-slate-600"
                  required
                />
              </div>
            </div>
            <Button 
              type="submit" 
              className="w-full bg-purple-600 hover:bg-purple-700"
              disabled={isLoading}
            >
              {isLoading ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

// User Menu Component
export const UserMenu = () => {
  const { user, logout, isAdmin } = useAuth();

  if (!user) return null;

  return (
    <div className="flex items-center gap-2">
      <div className="text-right hidden sm:block">
        <p className="text-sm font-medium text-white">{user.username}</p>
        <p className="text-xs text-slate-400">{user.email}</p>
      </div>
      {isAdmin && (
        <Badge variant="outline" className="border-purple-500 text-purple-400">
          Admin
        </Badge>
      )}
      <Button
        variant="ghost"
        size="sm"
        onClick={logout}
        className="text-slate-400 hover:text-white"
      >
        <LogOut className="w-4 h-4" />
      </Button>
    </div>
  );
};

export default LoginPage;
