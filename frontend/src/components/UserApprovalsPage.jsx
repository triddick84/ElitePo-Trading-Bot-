/**
 * Iter 97 — Admin: User Approvals page.
 * Lists users by status and lets admins approve / reject / suspend / re-approve.
 * Backend: /api/auth/users, /api/auth/users/pending, /api/auth/users/{id}/{approve|reject|suspend}
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import {
  Users, CheckCircle2, XCircle, ShieldOff, RefreshCw, Search,
  Clock, ShieldAlert, ShieldCheck, Ban, Shield,
} from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from './AuthComponents';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = `${BACKEND_URL}/api`;

const STATUS_META = {
  pending:   { label: 'Pending',   Icon: Clock,        color: 'text-amber-300 bg-amber-500/15 border-amber-500/40' },
  active:    { label: 'Active',    Icon: ShieldCheck,  color: 'text-emerald-300 bg-emerald-500/15 border-emerald-500/40' },
  rejected:  { label: 'Rejected',  Icon: Ban,          color: 'text-rose-300 bg-rose-500/15 border-rose-500/40' },
  suspended: { label: 'Suspended', Icon: ShieldAlert,  color: 'text-orange-300 bg-orange-500/15 border-orange-500/40' },
};

const StatusBadge = ({ status }) => {
  const meta = STATUS_META[status] || STATUS_META.pending;
  const { Icon } = meta;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${meta.color}`}
      data-testid={`status-badge-${status}`}
    >
      <Icon className="h-3 w-3" />
      {meta.label}
    </span>
  );
};

const RoleBadge = ({ role }) => {
  const isAdmin = role === 'admin';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
        isAdmin
          ? 'text-cyan-300 bg-cyan-500/15 border border-cyan-500/40'
          : 'text-slate-400 bg-slate-800/50 border border-slate-700/50'
      }`}
    >
      {isAdmin && <Shield className="h-2.5 w-2.5" />}
      {role || '—'}
    </span>
  );
};

export default function UserApprovalsPage() {
  const { user: currentUser, token } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [filter, setFilter] = useState('pending');
  const [search, setSearch] = useState('');

  const authHeaders = useMemo(
    () => (token ? { Authorization: `Bearer ${token}` } : {}),
    [token],
  );

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const url = filter === 'all'
        ? `${API}/auth/users`
        : `${API}/auth/users?status=${filter}`;
      const r = await axios.get(url, { headers: authHeaders, timeout: 8000 });
      setUsers(r.data?.users || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, [filter, authHeaders]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const doAction = async (userId, action, verb) => {
    setBusyId(userId);
    try {
      await axios.post(`${API}/auth/users/${userId}/${action}`, {}, { headers: authHeaders, timeout: 8000 });
      toast.success(`User ${verb}`);
      await fetchUsers();
    } catch (e) {
      toast.error(e.response?.data?.detail || `Failed to ${verb}`);
    } finally {
      setBusyId(null);
    }
  };

  const filteredUsers = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return users;
    return users.filter(u =>
      (u.username || '').toLowerCase().includes(q) ||
      (u.email || '').toLowerCase().includes(q)
    );
  }, [users, search]);

  const counts = useMemo(() => {
    const c = { pending: 0, active: 0, rejected: 0, suspended: 0 };
    users.forEach(u => { const s = u.status || 'pending'; if (c[s] !== undefined) c[s]++; });
    return c;
  }, [users]);

  if (currentUser && currentUser.role !== 'admin') {
    return (
      <div className="p-6" data-testid="user-approvals-non-admin">
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-6 text-center">
            <ShieldOff className="mx-auto h-10 w-10 text-rose-400 mb-3" />
            <p className="text-slate-200 font-semibold">Admin access required</p>
            <p className="text-slate-400 text-sm mt-1">This page is only visible to administrators.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-4" data-testid="user-approvals-page">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Users className="h-6 w-6 text-cyan-400" />
            User Approvals
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Review new registrations and manage user access.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchUsers}
          disabled={loading}
          className="border-slate-700"
          data-testid="user-approvals-refresh"
        >
          <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Filter pills */}
      <div className="flex items-center gap-2 flex-wrap">
        {[
          { key: 'pending',   label: 'Pending',   count: counts.pending },
          { key: 'active',    label: 'Active',    count: counts.active },
          { key: 'rejected',  label: 'Rejected',  count: counts.rejected },
          { key: 'suspended', label: 'Suspended', count: counts.suspended },
          { key: 'all',       label: 'All',       count: null },
        ].map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
              filter === key
                ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300'
                : 'bg-slate-800/50 border-slate-700/50 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
            data-testid={`filter-${key}`}
          >
            {label}
            {count !== null && count > 0 && (
              <span className="ml-1.5 rounded-full bg-slate-900/60 px-1.5 py-0.5 text-[10px]">{count}</span>
            )}
          </button>
        ))}
        <div className="flex-1" />
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by username or email…"
            className="pl-8 h-8 w-56 bg-slate-900 border-slate-700 text-sm"
            data-testid="user-search"
          />
        </div>
      </div>

      {/* User list */}
      <Card className="glass-dark border-slate-700/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base text-white">
            {filter === 'all' ? 'All Users' : `${STATUS_META[filter]?.label || filter} Users`}
            <span className="ml-2 text-sm font-normal text-slate-400">({filteredUsers.length})</span>
          </CardTitle>
          <CardDescription>
            {filter === 'pending' && 'New registrations awaiting your approval.'}
            {filter === 'active' && 'Users who can log in normally.'}
            {filter === 'rejected' && 'Registrations you declined. They cannot log in.'}
            {filter === 'suspended' && 'Previously-active users whose access has been revoked.'}
            {filter === 'all' && 'Every user in the system.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {loading && (
            <div className="p-8 text-center text-slate-400 text-sm">Loading…</div>
          )}
          {!loading && filteredUsers.length === 0 && (
            <div className="p-8 text-center text-slate-500 text-sm" data-testid="no-users-message">
              {search ? 'No users match your search.' : `No ${filter === 'all' ? '' : filter} users.`}
            </div>
          )}
          {!loading && filteredUsers.length > 0 && (
            <div className="divide-y divide-slate-800/60">
              {filteredUsers.map((u) => {
                const status = u.status || 'pending';
                const isSelf = currentUser?.id === u.id;
                return (
                  <div
                    key={u.id}
                    className="p-4 flex items-center gap-3 flex-wrap hover:bg-slate-900/30 transition-colors"
                    data-testid={`user-row-${u.username}`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-100">{u.username}</span>
                        <RoleBadge role={u.role} />
                        <StatusBadge status={status} />
                        {isSelf && (
                          <span className="text-[10px] font-semibold text-cyan-400 uppercase tracking-wider">You</span>
                        )}
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5 truncate">
                        {u.email}
                        {u.created_at && (
                          <span className="text-slate-600 ml-2">
                            · joined {new Date(u.created_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                      {u.approved_at && (
                        <div className="text-[10px] text-emerald-400/80 mt-0.5">
                          Approved {new Date(u.approved_at).toLocaleString()}
                        </div>
                      )}
                      {u.rejected_at && (
                        <div className="text-[10px] text-rose-400/80 mt-0.5">
                          Rejected {new Date(u.rejected_at).toLocaleString()}
                        </div>
                      )}
                      {u.suspended_at && (
                        <div className="text-[10px] text-orange-400/80 mt-0.5">
                          Suspended {new Date(u.suspended_at).toLocaleString()}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {status !== 'active' && (
                        <Button
                          size="sm"
                          onClick={() => doAction(u.id, 'approve', 'approved')}
                          disabled={busyId === u.id}
                          className="bg-emerald-600 hover:bg-emerald-500 text-white h-8"
                          data-testid={`approve-${u.username}`}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                          {status === 'pending' ? 'Approve' : 'Reactivate'}
                        </Button>
                      )}
                      {status !== 'rejected' && status !== 'suspended' && !isSelf && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => doAction(u.id, 'suspend', 'suspended')}
                          disabled={busyId === u.id}
                          className="border-orange-500/40 text-orange-300 hover:bg-orange-500/10 h-8"
                          data-testid={`suspend-${u.username}`}
                        >
                          <ShieldAlert className="h-3.5 w-3.5 mr-1" />
                          Suspend
                        </Button>
                      )}
                      {status === 'pending' && !isSelf && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => doAction(u.id, 'reject', 'rejected')}
                          disabled={busyId === u.id}
                          className="border-rose-500/40 text-rose-300 hover:bg-rose-500/10 h-8"
                          data-testid={`reject-${u.username}`}
                        >
                          <XCircle className="h-3.5 w-3.5 mr-1" />
                          Reject
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
