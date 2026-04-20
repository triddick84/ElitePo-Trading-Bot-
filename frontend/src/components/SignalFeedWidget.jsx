import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Radio, ArrowUp, ArrowDown, Route, Trophy, Brain, Wifi, WifiOff } from 'lucide-react';

const WS_BASE = process.env.REACT_APP_BACKEND_URL?.replace('https://', 'wss://').replace('http://', 'ws://');

const EVENT_ICONS = {
  signal: Radio,
  decision: Brain,
  outcome: Trophy,
  routing: Route,
};

const EVENT_COLORS = {
  signal: 'border-cyan-500/30 bg-cyan-900/10',
  decision: 'border-purple-500/30 bg-purple-900/10',
  outcome: 'border-amber-500/30 bg-amber-900/10',
  routing: 'border-indigo-500/30 bg-indigo-900/10',
};

const SignalFeedWidget = () => {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const connect = useCallback(() => {
    if (!WS_BASE) return;

    try {
      const ws = new WebSocket(`${WS_BASE}/api/signals/feed`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        if (reconnectRef.current) {
          clearTimeout(reconnectRef.current);
          reconnectRef.current = null;
        }
      };

      ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data);
          if (data.type === 'history' && data.events) {
            setEvents(data.events.slice(-20));
          } else if (data.type !== 'pong') {
            setEvents(prev => [...prev.slice(-29), data]);
          }
        } catch (e) { /* ignore */ }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        reconnectRef.current = setTimeout(connect, 5000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      reconnectRef.current = setTimeout(connect, 5000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };
  }, [connect]);

  // Ping to keep alive
  useEffect(() => {
    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, 25000);
    return () => clearInterval(interval);
  }, []);

  const renderEvent = (event, idx) => {
    const Icon = EVENT_ICONS[event.type] || Radio;
    const colorClass = EVENT_COLORS[event.type] || 'border-slate-700 bg-slate-900/50';
    const time = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : '';

    return (
      <div key={idx} className={`flex items-start gap-2 px-3 py-2 rounded border ${colorClass}`}>
        <Icon className="w-3 h-3 mt-0.5 text-slate-400 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          {event.type === 'signal' && (
            <div className="flex items-center gap-2 text-xs">
              {event.direction === 'CALL' ? <ArrowUp className="w-3 h-3 text-emerald-400" /> : <ArrowDown className="w-3 h-3 text-red-400" />}
              <span className={`font-bold ${event.direction === 'CALL' ? 'text-emerald-400' : 'text-red-400'}`}>{event.direction}</span>
              <span className="text-slate-300">{event.symbol}</span>
              <Badge className="text-[9px] bg-slate-700">{event.confidence}%</Badge>
              <span className="text-slate-500 truncate">{event.strategy}</span>
            </div>
          )}
          {event.type === 'decision' && (
            <div className="flex items-center gap-2 text-xs">
              <span className={`font-bold ${event.action === 'CALL' ? 'text-emerald-400' : event.action === 'PUT' ? 'text-red-400' : 'text-slate-400'}`}>{event.action}</span>
              <Badge className="text-[9px] bg-purple-700">{event.confidence}%</Badge>
              <span className="text-slate-400">{event.regime}</span>
              <span className="text-slate-500">{event.strategy_mode}</span>
              {event.model_votes && (
                <span className="text-[9px] text-slate-600">[{Object.entries(event.model_votes).map(([k,v]) => `${k[0].toUpperCase()}:${v?.[0] || '?'}`).join(' ')}]</span>
              )}
            </div>
          )}
          {event.type === 'outcome' && (
            <div className="flex items-center gap-2 text-xs">
              <Badge className={event.outcome === 'win' ? 'bg-emerald-600 text-[9px]' : 'bg-red-600 text-[9px]'}>{event.outcome?.toUpperCase()}</Badge>
              <span className="text-slate-300">{event.symbol}</span>
              <span className="text-slate-400">{event.direction}</span>
              {event.strategy && <span className="text-slate-500">{event.strategy}</span>}
            </div>
          )}
          {event.type === 'routing' && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400">Routed to</span>
              {event.destinations?.map(d => (
                <Badge key={d} variant="outline" className="text-[9px] border-slate-600">{d}</Badge>
              ))}
              <span className="text-slate-500">{event.matched_rules} rules</span>
            </div>
          )}
        </div>
        <span className="text-[9px] text-slate-600 flex-shrink-0">{time}</span>
      </div>
    );
  };

  return (
    <Card data-testid="signal-feed-widget" className="bg-slate-900/80 border border-cyan-500/20 backdrop-blur-md overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-cyan-600/20 to-teal-600/20 border-b border-cyan-500/20">
        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-bold text-white tracking-wide">LIVE SIGNAL FEED</span>
        </div>
        <div className="flex items-center gap-2">
          {connected ? (
            <Badge className="bg-emerald-600 text-[10px]"><Wifi className="w-2 h-2 mr-1 inline" /> Live</Badge>
          ) : (
            <Badge className="bg-slate-600 text-[10px]"><WifiOff className="w-2 h-2 mr-1 inline" /> Connecting</Badge>
          )}
          <Badge variant="outline" className="text-[10px] text-cyan-300 border-cyan-500/40">{events.length} events</Badge>
        </div>
      </div>

      <div className="p-3 space-y-1.5 max-h-64 overflow-y-auto">
        {events.length === 0 ? (
          <div className="text-center py-6 text-slate-500 text-xs">
            Waiting for signals... Events will appear here in real-time.
          </div>
        ) : (
          events.slice().reverse().map((ev, i) => renderEvent(ev, i))
        )}
      </div>
    </Card>
  );
};

export default SignalFeedWidget;
