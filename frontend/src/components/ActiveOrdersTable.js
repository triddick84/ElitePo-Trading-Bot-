import React, { useState, useEffect } from 'react';
import { Badge } from './ui/badge';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const ActiveOrdersTable = () => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadOrders();
    const interval = setInterval(loadOrders, 2000); // Refresh every 2s for real-time updates
    return () => clearInterval(interval);
  }, []);

  const loadOrders = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/automated-trading/active-orders`);
      if (response.data.success) {
        setOrders(response.data.active_orders || []);
      }
    } catch (error) {
      console.error('Error loading active orders:', error);
    } finally {
      setLoading(false);
    }
  };

  const getDirectionBadge = (direction) => {
    const colors = {
      'call': 'bg-emerald-500/20 text-emerald-400 border-emerald-500',
      'put': 'bg-red-500/20 text-red-400 border-red-500'
    };
    return colors[direction?.toLowerCase()] || colors['call'];
  };

  const getTimeRemaining = (timestamp, duration) => {
    try {
      const startTime = new Date(timestamp);
      const endTime = new Date(startTime.getTime() + duration * 1000);
      const now = new Date();
      const remaining = Math.max(0, Math.floor((endTime - now) / 1000));
      
      const minutes = Math.floor(remaining / 60);
      const seconds = remaining % 60;
      
      return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    } catch (e) {
      return 'N/A';
    }
  };

  if (loading) {
    return <div className="text-center text-slate-400 py-8">Loading active orders...</div>;
  }

  if (orders.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400 text-lg">No active orders</p>
        <p className="text-slate-500 text-sm mt-2">
          Enable automated trading and generate signals to start
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left text-slate-400 text-sm font-semibold p-3">Order ID</th>
            <th className="text-left text-slate-400 text-sm font-semibold p-3">Asset</th>
            <th className="text-left text-slate-400 text-sm font-semibold p-3">Direction</th>
            <th className="text-right text-slate-400 text-sm font-semibold p-3">Amount</th>
            <th className="text-right text-slate-400 text-sm font-semibold p-3">Confidence</th>
            <th className="text-center text-slate-400 text-sm font-semibold p-3">Time Left</th>
            <th className="text-left text-slate-400 text-sm font-semibold p-3">Strategy</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order, index) => (
            <tr key={index} className="border-b border-slate-800 hover:bg-slate-800/50">
              <td className="p-3">
                <span className="text-slate-300 text-sm font-mono">
                  {order.order_id?.slice(-8) || 'N/A'}
                </span>
              </td>
              <td className="p-3">
                <span className="text-white font-semibold">{order.asset}</span>
              </td>
              <td className="p-3">
                <Badge className={getDirectionBadge(order.direction)}>
                  {order.direction === 'call' ? '📈 CALL' : '📉 PUT'}
                </Badge>
              </td>
              <td className="p-3 text-right">
                <span className="text-white font-semibold">${order.amount?.toFixed(2)}</span>
              </td>
              <td className="p-3 text-right">
                <span className="text-blue-400 font-semibold">{order.confidence?.toFixed(0)}%</span>
              </td>
              <td className="p-3 text-center">
                <span className="text-amber-400 font-mono font-semibold">
                  {getTimeRemaining(order.timestamp, order.duration)}
                </span>
              </td>
              <td className="p-3">
                <span className="text-slate-400 text-sm">{order.strategy}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ActiveOrdersTable;