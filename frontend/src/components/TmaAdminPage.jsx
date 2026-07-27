import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;
const TMA_ADMIN_TOKEN_KEY = "tma_admin_token_v1";

/**
 * Admin-only page to review TMA KYC submissions.
 *
 * Auth model: the admin holds a TMA JWT (issued by /api/tma/auth). We store
 * it in localStorage and let the admin obtain one by clicking "Sign in as
 * TMA admin" — which posts a dev-mode initData when TMA_DEV_MODE is on
 * (Phase A default) OR by pasting a token obtained from opening the TMA
 * inside Telegram as the admin user.
 */
export default function TmaAdminPage() {
  const [token, setToken] = useState(() => localStorage.getItem(TMA_ADMIN_TOKEN_KEY));
  const [health, setHealth] = useState(null);
  const [me, setMe] = useState(null);
  const [items, setItems] = useState([]);
  const [users, setUsers] = useState([]);
  const [status, setStatus] = useState("pending");
  const [loading, setLoading] = useState(false);
  const [pasteToken, setPasteToken] = useState("");

  const fetchHealth = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/tma/health`);
      setHealth(r.data);
    } catch (e) { /* ignore */ }
  }, []);

  const authedHeaders = () => ({ Authorization: `Bearer ${token}` });

  const refresh = useCallback(async (overrideToken) => {
    const tk = overrideToken || token;
    if (!tk) return;
    setLoading(true);
    try {
      const [meRes, qRes, uRes] = await Promise.all([
        axios.get(`${API}/api/tma/me`, { headers: { Authorization: `Bearer ${tk}` } }),
        axios.get(`${API}/api/tma/admin/kyc/queue`, {
          headers: { Authorization: `Bearer ${tk}` },
          params: { status_filter: status },
        }),
        axios.get(`${API}/api/tma/admin/users`, { headers: { Authorization: `Bearer ${tk}` } }),
      ]);
      setMe(meRes.data.user);
      setItems(qRes.data.items || []);
      setUsers(uRes.data.items || []);
    } catch (e) {
      const detail = e?.response?.data?.detail || e.message;
      toast.error(`Load failed: ${detail}`);
      if (e?.response?.status === 401 || e?.response?.status === 403) {
        setToken(null);
        localStorage.removeItem(TMA_ADMIN_TOKEN_KEY);
      }
    } finally { setLoading(false); }
  }, [token, status]);

  useEffect(() => { fetchHealth(); }, [fetchHealth]);
  useEffect(() => { if (token) refresh(); }, [token, status, refresh]);

  const signInDev = async () => {
    if (!health?.dev_mode) {
      toast.error("Dev mode is off. Paste an admin token instead.");
      return;
    }
    const adminId = (health?.admin_ids || [])[0];
    if (!adminId) { toast.error("No admin id configured in TMA_ADMIN_TELEGRAM_IDS."); return; }
    try {
      const r = await axios.post(`${API}/api/tma/auth`, {
        init_data: `dev:${adminId}:admin_dev`,
      });
      localStorage.setItem(TMA_ADMIN_TOKEN_KEY, r.data.token);
      setToken(r.data.token);
      toast.success("Signed in as TMA admin");
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    }
  };

  const applyPastedToken = () => {
    if (!pasteToken.trim()) return;
    localStorage.setItem(TMA_ADMIN_TOKEN_KEY, pasteToken.trim());
    setToken(pasteToken.trim());
    setPasteToken("");
  };

  const signOut = () => {
    localStorage.removeItem(TMA_ADMIN_TOKEN_KEY);
    setToken(null);
    setMe(null);
    setItems([]);
    setUsers([]);
  };

  const review = async (kycId, action, reason = null) => {
    try {
      await axios.post(
        `${API}/api/tma/admin/kyc/${kycId}/review`,
        { action, reason },
        { headers: authedHeaders() },
      );
      toast.success(`KYC ${action}d`);
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    }
  };

  if (!token) {
    return (
      <div className="max-w-2xl mx-auto space-y-6" data-testid="tma-admin-signin">
        <h1 className="text-3xl font-bold text-white">TMA Admin — KYC Review</h1>
        <div className="bg-[#13131a] border border-[#2a2a35] rounded-xl p-6 space-y-4">
          <p className="text-slate-400">
            Sign in as the TMA admin to review KYC submissions and manage subscribers.
          </p>
          <div className="text-sm text-slate-500">
            Dev mode: <span className={health?.dev_mode ? "text-green-400" : "text-red-400"}>
              {health?.dev_mode ? "ON" : "OFF"}
            </span>
            {" · "}Admin IDs: {(health?.admin_ids || []).join(", ") || "not set"}
          </div>
          <button
            onClick={signInDev}
            disabled={!health?.dev_mode}
            className="w-full bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white px-4 py-3 rounded-lg font-medium"
            data-testid="tma-admin-signin-dev"
          >
            Sign in as TMA admin (dev bypass)
          </button>
          <div className="text-xs text-slate-500">— or —</div>
          <textarea
            className="w-full bg-[#0f0f16] border border-[#2a2a35] rounded-lg p-3 text-slate-200 text-xs"
            rows={3}
            placeholder="Paste an admin JWT token (from /tma/ inside Telegram)"
            value={pasteToken}
            onChange={(e) => setPasteToken(e.target.value)}
            data-testid="tma-admin-paste-token"
          />
          <button
            onClick={applyPastedToken}
            disabled={!pasteToken.trim()}
            className="w-full border border-[#2a2a35] hover:border-purple-500 text-slate-200 px-4 py-2 rounded-lg font-medium"
            data-testid="tma-admin-apply-token"
          >
            Use pasted token
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="tma-admin-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">TMA Admin</h1>
          <p className="text-slate-400 text-sm">
            Signed in as <span className="text-purple-400">{me?.username}</span> (tg: {me?.telegram_user_id})
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => refresh()}
            className="border border-[#2a2a35] hover:border-purple-500 text-slate-200 px-4 py-2 rounded-lg text-sm"
            data-testid="tma-admin-refresh"
          >
            {loading ? "…" : "Refresh"}
          </button>
          <button
            onClick={signOut}
            className="border border-red-500/40 hover:border-red-500 text-red-300 px-4 py-2 rounded-lg text-sm"
            data-testid="tma-admin-signout"
          >
            Sign out
          </button>
        </div>
      </div>

      <div className="bg-[#13131a] border border-[#2a2a35] rounded-xl p-6 space-y-4">
        <div className="flex gap-2 flex-wrap">
          {["pending", "approved", "rejected", "all"].map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`px-3 py-1 rounded-full text-sm border ${
                status === s
                  ? "border-purple-500 text-purple-300 bg-purple-500/10"
                  : "border-[#2a2a35] text-slate-400 hover:border-purple-400"
              }`}
              data-testid={`filter-${s}`}
            >
              {s}
            </button>
          ))}
        </div>

        {items.length === 0 ? (
          <p className="text-slate-500 text-sm" data-testid="tma-admin-empty">
            No submissions in this bucket.
          </p>
        ) : (
          <div className="space-y-3">
            {items.map((k) => (
              <div key={k.id} className="border border-[#2a2a35] rounded-lg p-4 space-y-3" data-testid={`kyc-item-${k.id}`}>
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm">
                    <div className="text-slate-300">Telegram ID: <span className="text-purple-400">{k.telegram_user_id}</span></div>
                    <div className="text-slate-500 text-xs">Submitted: {k.submitted_at} · Status: {k.status}</div>
                  </div>
                  <div className="flex gap-2">
                    <a
                      href={`${API}/api/tma/admin/kyc/${k.id}/image`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-purple-400 text-sm underline"
                      data-testid={`kyc-view-${k.id}`}
                    >
                      View screenshot
                    </a>
                    {k.status === "pending" && (
                      <>
                        <button
                          onClick={() => review(k.id, "approve")}
                          className="bg-green-600/20 hover:bg-green-600/30 border border-green-500/40 text-green-300 px-3 py-1 rounded-lg text-sm"
                          data-testid={`kyc-approve-${k.id}`}
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => {
                            const reason = window.prompt("Rejection reason?");
                            if (reason !== null) review(k.id, "reject", reason);
                          }}
                          className="bg-red-600/20 hover:bg-red-600/30 border border-red-500/40 text-red-300 px-3 py-1 rounded-lg text-sm"
                          data-testid={`kyc-reject-${k.id}`}
                        >
                          Reject
                        </button>
                      </>
                    )}
                  </div>
                </div>
                {k.review_reason && (
                  <div className="text-xs text-slate-500">Reason: {k.review_reason}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-[#13131a] border border-[#2a2a35] rounded-xl p-6 space-y-3">
        <h2 className="text-xl font-semibold text-white">TMA Users ({users.length})</h2>
        <div className="max-h-96 overflow-y-auto space-y-2">
          {users.map((u) => (
            <div
              key={u.id}
              className="flex items-center justify-between border border-[#2a2a35] rounded-lg px-3 py-2 text-sm"
              data-testid={`tma-user-${u.telegram_user_id}`}
            >
              <div>
                <div className="text-slate-200">@{u.username} <span className="text-slate-500">({u.telegram_user_id})</span></div>
                <div className="text-slate-500 text-xs">
                  KYC: {u.kyc_status} · Access: {u.access_granted ? "granted" : "no"} · Ref: {u.referral_code}
                </div>
              </div>
              <div className="text-xs text-slate-500">
                {u.role === "admin" ? "🛡️ admin" : "user"}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
