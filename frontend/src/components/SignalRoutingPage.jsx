import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import { Plus, Trash2, Send, RefreshCw, ArrowRight, Filter, Zap, Route } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const DESTINATIONS = [
  { id: 'pocket_option', label: 'Pocket Option', color: 'bg-purple-600' },
  { id: 'mt5', label: 'MetaTrader 5', color: 'bg-green-600' },
  { id: 'telegram', label: 'Telegram', color: 'bg-sky-600' },
];

const SESSIONS = ['asian', 'london', 'new_york', 'overlap', 'off_hours'];

const SignalRoutingPage = () => {
  const [rules, setRules] = useState([]);
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(false);

  // Create form
  const [newRule, setNewRule] = useState({
    name: '',
    destinations: ['pocket_option'],
    priority: 50,
    filters: { min_confidence: 65, assets: [], directions: [], strategies: [], sessions: [] },
  });
  const [assetInput, setAssetInput] = useState('');

  // Test signal
  const [testSignal, setTestSignal] = useState({ direction: 'CALL', symbol: 'EURUSD_OTC', confidence: 75, strategy: 'iq720_ensemble' });
  const [testResult, setTestResult] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [rulesRes, statsRes, logsRes] = await Promise.all([
        axios.get(`${API}/api/signal-routing/rules`),
        axios.get(`${API}/api/signal-routing/stats`),
        axios.get(`${API}/api/signal-routing/log?limit=20`),
      ]);
      if (rulesRes.data.success) setRules(rulesRes.data.rules);
      if (statsRes.data.success) setStats(statsRes.data.stats);
      if (logsRes.data.success) setLogs(logsRes.data.logs);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const createRule = async () => {
    if (!newRule.name) { toast.error('Rule name required'); return; }
    if (newRule.destinations.length === 0) { toast.error('Select at least one destination'); return; }
    setLoading(true);
    try {
      await axios.post(`${API}/api/signal-routing/rules`, newRule);
      toast.success('Rule created');
      setShowCreate(false);
      setNewRule({ name: '', destinations: ['pocket_option'], priority: 50, filters: { min_confidence: 65, assets: [], directions: [], strategies: [], sessions: [] } });
      fetchAll();
    } catch (e) { toast.error('Failed to create rule'); }
    setLoading(false);
  };

  const toggleRule = async (ruleId, enabled) => {
    try {
      await axios.put(`${API}/api/signal-routing/rules/${ruleId}`, { enabled: !enabled });
      fetchAll();
    } catch (e) { toast.error('Update failed'); }
  };

  const deleteRule = async (ruleId) => {
    try {
      await axios.delete(`${API}/api/signal-routing/rules/${ruleId}`);
      toast.success('Rule deleted');
      fetchAll();
    } catch (e) { toast.error('Delete failed'); }
  };

  const testRoute = async () => {
    setTestResult(null);
    try {
      const res = await axios.post(`${API}/api/signal-routing/test`, testSignal);
      setTestResult(res.data);
      fetchAll();
    } catch (e) { toast.error('Test failed'); }
  };

  const toggleDest = (dest) => {
    setNewRule(prev => ({
      ...prev,
      destinations: prev.destinations.includes(dest)
        ? prev.destinations.filter(d => d !== dest)
        : [...prev.destinations, dest]
    }));
  };

  const toggleDirection = (dir) => {
    setNewRule(prev => ({
      ...prev,
      filters: {
        ...prev.filters,
        directions: prev.filters.directions.includes(dir)
          ? prev.filters.directions.filter(d => d !== dir)
          : [...prev.filters.directions, dir]
      }
    }));
  };

  const toggleSession = (s) => {
    setNewRule(prev => ({
      ...prev,
      filters: {
        ...prev.filters,
        sessions: prev.filters.sessions.includes(s)
          ? prev.filters.sessions.filter(x => x !== s)
          : [...prev.filters.sessions, s]
      }
    }));
  };

  const addAsset = () => {
    if (!assetInput.trim()) return;
    setNewRule(prev => ({
      ...prev,
      filters: { ...prev.filters, assets: [...prev.filters.assets, assetInput.trim().toUpperCase()] }
    }));
    setAssetInput('');
  };

  const removeAsset = (a) => {
    setNewRule(prev => ({
      ...prev,
      filters: { ...prev.filters, assets: prev.filters.assets.filter(x => x !== a) }
    }));
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-4 md:p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-white mb-1 flex items-center justify-center gap-3">
            <Route className="w-7 h-7 text-purple-400" />
            Signal Routing
          </h1>
          <p className="text-slate-400">Configure where signals get routed based on custom rules</p>
        </div>

        {/* Stats Row */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-3 text-center">
                <div className="text-2xl font-bold text-purple-400">{stats.total_rules}</div>
                <div className="text-xs text-slate-400">Total Rules</div>
              </CardContent>
            </Card>
            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-3 text-center">
                <div className="text-2xl font-bold text-emerald-400">{stats.enabled_rules}</div>
                <div className="text-xs text-slate-400">Active</div>
              </CardContent>
            </Card>
            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-3 text-center">
                <div className="text-2xl font-bold text-cyan-400">{stats.total_routed}</div>
                <div className="text-xs text-slate-400">Signals Routed</div>
              </CardContent>
            </Card>
            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-3 text-center">
                <div className="text-2xl font-bold text-green-400">{stats.by_destination?.mt5 || 0}</div>
                <div className="text-xs text-slate-400">To MT5</div>
              </CardContent>
            </Card>
            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-3 text-center">
                <div className="text-2xl font-bold text-sky-400">{stats.by_destination?.telegram || 0}</div>
                <div className="text-xs text-slate-400">To Telegram</div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Rules List + Create */}
        <Card className="bg-slate-800/50 border-slate-700" data-testid="routing-rules-card">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-white flex items-center gap-2"><Filter className="w-5 h-5 text-indigo-400" /> Routing Rules</CardTitle>
                <CardDescription>Signals are matched top-to-bottom by priority</CardDescription>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" className="border-slate-600" onClick={fetchAll}><RefreshCw className="w-3 h-3 mr-1" /> Refresh</Button>
                <Button data-testid="create-rule-btn" size="sm" onClick={() => setShowCreate(!showCreate)} className="bg-indigo-600 hover:bg-indigo-700"><Plus className="w-3 h-3 mr-1" /> New Rule</Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Create Form */}
            {showCreate && (
              <div data-testid="create-rule-form" className="bg-slate-900 rounded-lg p-4 border border-indigo-500/30 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-slate-400 text-xs">Rule Name</Label>
                    <Input data-testid="rule-name-input" value={newRule.name} onChange={e => setNewRule(p => ({ ...p, name: e.target.value }))} placeholder="e.g. High-Conf to MT5" className="bg-slate-800 border-slate-700 text-white" />
                  </div>
                  <div>
                    <Label className="text-slate-400 text-xs">Priority (lower = higher)</Label>
                    <Input type="number" value={newRule.priority} onChange={e => setNewRule(p => ({ ...p, priority: parseInt(e.target.value) || 50 }))} className="bg-slate-800 border-slate-700 text-white" />
                  </div>
                </div>

                {/* Destinations */}
                <div>
                  <Label className="text-slate-400 text-xs mb-1 block">Destinations</Label>
                  <div className="flex gap-2">
                    {DESTINATIONS.map(d => (
                      <Button key={d.id} size="sm" variant={newRule.destinations.includes(d.id) ? 'default' : 'outline'}
                        className={newRule.destinations.includes(d.id) ? d.color : 'border-slate-600'}
                        onClick={() => toggleDest(d.id)}>
                        {d.label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Filters */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-slate-400 text-xs">Min Confidence</Label>
                    <Input type="number" value={newRule.filters.min_confidence} onChange={e => setNewRule(p => ({ ...p, filters: { ...p.filters, min_confidence: parseInt(e.target.value) || 0 } }))} className="bg-slate-800 border-slate-700 text-white" />
                  </div>
                  <div>
                    <Label className="text-slate-400 text-xs">Assets (add one at a time)</Label>
                    <div className="flex gap-1">
                      <Input value={assetInput} onChange={e => setAssetInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && addAsset()} placeholder="EURUSD" className="bg-slate-800 border-slate-700 text-white" />
                      <Button size="sm" onClick={addAsset} className="bg-slate-700">+</Button>
                    </div>
                    {newRule.filters.assets.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {newRule.filters.assets.map(a => (
                          <Badge key={a} className="bg-slate-700 cursor-pointer" onClick={() => removeAsset(a)}>{a} x</Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Direction + Session Filters */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-slate-400 text-xs mb-1 block">Direction Filter</Label>
                    <div className="flex gap-2">
                      {['CALL', 'PUT'].map(d => (
                        <Button key={d} size="sm" variant={newRule.filters.directions.includes(d) ? 'default' : 'outline'}
                          className={newRule.filters.directions.includes(d) ? (d === 'CALL' ? 'bg-emerald-600' : 'bg-red-600') : 'border-slate-600'}
                          onClick={() => toggleDirection(d)}>
                          {d}
                        </Button>
                      ))}
                    </div>
                    <p className="text-[10px] text-slate-500 mt-1">Empty = all directions</p>
                  </div>
                  <div>
                    <Label className="text-slate-400 text-xs mb-1 block">Session Filter</Label>
                    <div className="flex flex-wrap gap-1">
                      {SESSIONS.map(s => (
                        <Badge key={s} className={`cursor-pointer text-xs ${newRule.filters.sessions.includes(s) ? 'bg-indigo-600' : 'bg-slate-700'}`} onClick={() => toggleSession(s)}>{s}</Badge>
                      ))}
                    </div>
                    <p className="text-[10px] text-slate-500 mt-1">Empty = all sessions</p>
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button data-testid="save-rule-btn" onClick={createRule} disabled={loading} className="bg-indigo-600 hover:bg-indigo-700">{loading ? 'Saving...' : 'Save Rule'}</Button>
                  <Button variant="outline" className="border-slate-600" onClick={() => setShowCreate(false)}>Cancel</Button>
                </div>
              </div>
            )}

            {/* Rules List */}
            {rules.length === 0 && !showCreate && (
              <div className="text-center py-8 text-slate-500">No routing rules configured. Click "New Rule" to create one.</div>
            )}
            {rules.map(rule => (
              <div key={rule.rule_id} data-testid={`rule-${rule.rule_id}`} className={`flex items-center gap-4 p-3 rounded-lg border ${rule.enabled ? 'bg-slate-900/80 border-slate-700' : 'bg-slate-900/30 border-slate-800 opacity-60'}`}>
                <div className="flex-shrink-0 w-8 text-center">
                  <span className="text-xs text-slate-500 font-mono">#{rule.priority}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-white truncate">{rule.name}</div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {rule.filters?.assets?.length > 0 && rule.filters.assets.map(a => <Badge key={a} variant="outline" className="text-[10px] border-slate-600">{a}</Badge>)}
                    {rule.filters?.min_confidence && <Badge variant="outline" className="text-[10px] border-amber-600/50 text-amber-400">Min {rule.filters.min_confidence}%</Badge>}
                    {rule.filters?.directions?.length > 0 && rule.filters.directions.map(d => <Badge key={d} className={`text-[10px] ${d === 'CALL' ? 'bg-emerald-700' : 'bg-red-700'}`}>{d}</Badge>)}
                    {rule.filters?.sessions?.length > 0 && <Badge variant="outline" className="text-[10px] border-indigo-600/50 text-indigo-400">{rule.filters.sessions.join(',')}</Badge>}
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-600 flex-shrink-0" />
                <div className="flex gap-1 flex-shrink-0">
                  {rule.destinations?.map(d => {
                    const dest = DESTINATIONS.find(x => x.id === d);
                    return <Badge key={d} className={`text-[10px] ${dest?.color || 'bg-slate-600'}`}>{dest?.label || d}</Badge>;
                  })}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Switch checked={rule.enabled} onCheckedChange={() => toggleRule(rule.rule_id, rule.enabled)} />
                  <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-red-400 hover:text-red-300" onClick={() => deleteRule(rule.rule_id)}><Trash2 className="w-3 h-3" /></Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Test Signal Router */}
        <Card className="bg-slate-800/50 border-slate-700" data-testid="test-router-card">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2"><Zap className="w-5 h-5 text-cyan-400" /> Test Signal Router</CardTitle>
            <CardDescription>Send a test signal through the routing engine</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-4 gap-3">
              <div>
                <Label className="text-slate-400 text-xs">Symbol</Label>
                <Input data-testid="test-route-symbol" value={testSignal.symbol} onChange={e => setTestSignal(p => ({ ...p, symbol: e.target.value }))} className="bg-slate-900 border-slate-700 text-white" />
              </div>
              <div>
                <Label className="text-slate-400 text-xs">Direction</Label>
                <select value={testSignal.direction} onChange={e => setTestSignal(p => ({ ...p, direction: e.target.value }))} className="w-full h-9 bg-slate-900 border border-slate-700 text-white rounded-md px-3 text-sm">
                  <option value="CALL">CALL</option>
                  <option value="PUT">PUT</option>
                </select>
              </div>
              <div>
                <Label className="text-slate-400 text-xs">Confidence</Label>
                <Input data-testid="test-route-confidence" type="number" value={testSignal.confidence} onChange={e => setTestSignal(p => ({ ...p, confidence: parseInt(e.target.value) || 0 }))} className="bg-slate-900 border-slate-700 text-white" />
              </div>
              <div className="flex items-end">
                <Button data-testid="test-route-btn" onClick={testRoute} className="bg-cyan-600 hover:bg-cyan-700 w-full"><Send className="w-4 h-4 mr-2" /> Test Route</Button>
              </div>
            </div>
            {testResult && (
              <div data-testid="test-route-result" className="bg-slate-900 rounded-lg p-4 border border-cyan-500/30">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-white font-medium text-sm">Matched {testResult.matched_rules?.length || 0} rule(s)</span>
                  <ArrowRight className="w-4 h-4 text-slate-500" />
                  <div className="flex gap-1">
                    {testResult.destinations?.map(d => {
                      const dest = DESTINATIONS.find(x => x.id === d);
                      return <Badge key={d} className={dest?.color || 'bg-slate-600'}>{dest?.label || d}</Badge>;
                    })}
                  </div>
                </div>
                {testResult.matched_rules?.length === 0 && <p className="text-xs text-slate-500">No rules matched — using default routing (Pocket Option + Telegram)</p>}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Routing Log */}
        {logs.length > 0 && (
          <Card className="bg-slate-800/50 border-slate-700" data-testid="routing-log-card">
            <CardHeader>
              <CardTitle className="text-white text-sm">Recent Routing Log</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {logs.map((log, i) => (
                  <div key={i} className="flex items-center justify-between text-xs bg-slate-900 rounded px-3 py-2 border border-slate-700/50">
                    <span className="text-slate-300 w-24 truncate">{log.signal_symbol}</span>
                    <Badge className={log.signal_direction === 'CALL' ? 'bg-emerald-600' : 'bg-red-600'}>{log.signal_direction}</Badge>
                    <span className="text-slate-400">{log.signal_confidence}%</span>
                    <div className="flex gap-1">
                      {log.destinations?.map(d => <Badge key={d} variant="outline" className="text-[9px] border-slate-600">{d}</Badge>)}
                    </div>
                    <span className="text-slate-600 text-[10px]">{new Date(log.routed_at).toLocaleTimeString()}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default SignalRoutingPage;
