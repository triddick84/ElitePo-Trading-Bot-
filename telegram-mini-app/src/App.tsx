import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, Package, TmaUser } from './api';
import { bootstrap, openExternal } from './telegram';

type Step = 'po_signup' | 'kyc' | 'package' | 'access';
const STEP_LABEL: Record<Step, string> = {
  po_signup: '1 · Signup',
  kyc: '2 · KYC',
  package: '3 · Package',
  access: '4 · Access',
};

const TOKEN_KEY = 'tma_token_v1';

export default function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<TmaUser | null>(null);
  const [nextStep, setNextStep] = useState<Step>('po_signup');
  const [affiliateUrl, setAffiliateUrl] = useState<string>('');
  const [packages, setPackages] = useState<Package[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const bootstrapped = useRef(false);

  // --- session bootstrap
  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    (async () => {
      try {
        setLoading(true); setError(null);
        const boot = bootstrap();

        // Always call /auth to ensure the server upserts the latest Telegram
        // user snapshot (username changes, referral capture). We keep the
        // localStorage token only as a UX niceness — the /auth call is cheap.
        const resp = await api.auth(boot.initData, boot.referral);
        localStorage.setItem(TOKEN_KEY, resp.token);
        setToken(resp.token);
        setUser(resp.user);
        setAffiliateUrl(resp.affiliate_url);
        await refreshState(resp.token);
        const pkg = await api.packages(resp.token);
        setPackages(pkg.packages);
      } catch (e: any) {
        setError(e.message || 'Failed to initialise');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const refreshState = useCallback(async (tk: string) => {
    const s = await api.onboardingState(tk);
    setNextStep(s.next_step as Step);
    setAffiliateUrl(s.affiliate_url);
    const me = await api.me(tk);
    setUser(me.user);
    return { state: s, user: me.user };
  }, []);

  const stepsUi = useMemo(() => (['po_signup', 'kyc', 'package', 'access'] as Step[]), []);
  const onb = user?.onboarding;

  const stepStatus = (s: Step): 'done' | 'active' | 'idle' => {
    if (!onb) return 'idle';
    if ((onb as any)[s]?.completed) return 'done';
    if (nextStep === s) return 'active';
    return 'idle';
  };

  if (loading) {
    return (
      <div className="tma-shell center" style={{ minHeight: '80vh' }}>
        <div className="loader" data-testid="tma-loader" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="tma-shell">
        <Brand />
        <div className="card" data-testid="tma-error">
          <h2>Couldn't sign you in</h2>
          <p>{error}</p>
          <p>Open this app from inside Telegram — it needs the initData signature to sign you in.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="tma-shell" data-testid="tma-shell">
      <Brand />

      <div className="hero" data-testid="tma-hero">
        <h1>Unlock <em>Elite PO Traders</em> Access</h1>
        <p>Four quick steps. You'll be trading with the bot in under 10 minutes.</p>
      </div>

      <div className="stepper" role="list">
        {stepsUi.map((s) => (
          <div
            key={s}
            role="listitem"
            data-testid={`step-pill-${s}`}
            className={`step-pill ${stepStatus(s)}`}
          >
            {STEP_LABEL[s]}
          </div>
        ))}
      </div>

      {user?.access_granted ? (
        <AccessGrantedCard user={user} />
      ) : (
        <>
          {nextStep === 'po_signup' && (
            <PoSignupCard
              affiliateUrl={affiliateUrl}
              token={token!}
              onDone={() => refreshState(token!)}
            />
          )}
          {nextStep === 'kyc' && (
            <KycCard token={token!} user={user!} onDone={() => refreshState(token!)} />
          )}
          {nextStep === 'package' && (
            <PackageCard
              token={token!}
              packages={packages}
              selected={user?.onboarding.package.package_id || null}
              onDone={() => refreshState(token!)}
            />
          )}
          {nextStep === 'access' && (
            <AccessPendingCard user={user!} />
          )}
        </>
      )}

      <ReferralCard user={user} />

      <div className="footer">v0.1.0 · Elite PO Traders · Phase A</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Brand() {
  return (
    <div className="tma-brand">
      <div className="tma-brand-mark">EP</div>
      <div>
        <div className="tma-brand-title">Elite Access</div>
        <div className="tma-brand-name">PO Traders Bot</div>
      </div>
    </div>
  );
}

function PoSignupCard({ affiliateUrl, token, onDone }: {
  affiliateUrl: string; token: string; onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visited, setVisited] = useState(false);

  const handleOpen = () => {
    openExternal(affiliateUrl);
    setVisited(true);
  };

  const handleConfirm = async () => {
    try {
      setBusy(true); setError(null);
      await api.onboardingUpdate(token, 'po_signup');
      onDone();
    } catch (e: any) {
      setError(e.message);
    } finally { setBusy(false); }
  };

  return (
    <div className="card" data-testid="step-po-signup-card">
      <h2>Step 1 — Sign up on Pocket Option</h2>
      <p>Create a Pocket Option account using our partner link so we can grant bot access. It takes ~2 minutes.</p>
      <div className="row">
        <button className="btn btn-primary grow" onClick={handleOpen} data-testid="po-signup-open">
          Open signup link
        </button>
      </div>
      <button
        className="btn btn-ghost"
        onClick={handleConfirm}
        disabled={!visited || busy}
        data-testid="po-signup-confirm"
      >
        {busy ? 'Confirming…' : 'I created my account'}
      </button>
      {!visited && <p style={{ fontSize: 12 }}>Tap "Open signup link" first, then come back and confirm.</p>}
      {error && <div className="status err" data-testid="po-error">{error}</div>}
    </div>
  );
}

function KycCard({ token, user, onDone }: { token: string; user: TmaUser; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const status = user.kyc_status;

  const onFileChange = (f: File | null) => {
    setFile(f);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
  };

  const submit = async () => {
    if (!file) return;
    try {
      setBusy(true); setError(null);
      await api.uploadKyc(token, file);
      onDone();
    } catch (e: any) {
      setError(e.message);
    } finally { setBusy(false); }
  };

  return (
    <div className="card" data-testid="step-kyc-card">
      <h2>Step 2 — KYC Verification</h2>
      <p>Upload a screenshot of your Pocket Option account showing your UID + email. Our team reviews within 24 hours.</p>

      {status === 'pending' && (
        <div className="status warn" data-testid="kyc-status-pending">
          ⏳ Submission received — awaiting review.
        </div>
      )}
      {status === 'rejected' && (
        <div className="status err" data-testid="kyc-status-rejected">
          Your last submission was rejected. Please upload a clearer screenshot.
        </div>
      )}
      {status === 'approved' && (
        <div className="status ok" data-testid="kyc-status-approved">✅ KYC approved.</div>
      )}

      {(status === 'not_submitted' || status === 'rejected') && (
        <>
          <label className="file-drop" data-testid="kyc-file-drop">
            <input
              type="file"
              accept="image/*"
              onChange={(e) => onFileChange(e.target.files?.[0] || null)}
              data-testid="kyc-file-input"
            />
            {file ? file.name : 'Tap to attach screenshot (PNG/JPG, ≤ 8 MB)'}
          </label>
          {previewUrl && <img src={previewUrl} className="file-preview" alt="preview" />}
          <button
            className="btn btn-primary"
            onClick={submit}
            disabled={!file || busy}
            data-testid="kyc-submit"
          >
            {busy ? 'Uploading…' : 'Submit for review'}
          </button>
        </>
      )}

      {error && <div className="status err">{error}</div>}
    </div>
  );
}

function PackageCard({
  token, packages, selected, onDone,
}: {
  token: string; packages: Package[]; selected: string | null; onDone: () => void;
}) {
  const [picked, setPicked] = useState<string | null>(selected);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirm = async () => {
    if (!picked) return;
    try {
      setBusy(true); setError(null);
      await api.onboardingUpdate(token, 'package', picked);
      onDone();
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="card" data-testid="step-package-card">
      <h2>Step 3 — Pick your package</h2>
      <p>Payments unlock in Phase B (Stripe + crypto). For now, pick your preferred plan so we can prepare access.</p>
      <div className="pkg-grid">
        {packages.map((p) => (
          <div
            key={p.id}
            className={`pkg ${p.highlight ? 'highlight' : ''} ${picked === p.id ? 'selected' : ''}`}
            onClick={() => setPicked(p.id)}
            data-testid={`package-${p.id}`}
          >
            <div className="pkg-head">
              <div>
                <div className="pkg-name">{p.name}</div>
                <div className="pkg-cadence">{p.cadence}</div>
              </div>
              <div className="pkg-price">${p.price_usd}</div>
            </div>
            <div className="pkg-desc">{p.description}</div>
            <div className="pkg-feats">
              {p.features.map((f) => <span key={f} className="pkg-feat">{f}</span>)}
            </div>
          </div>
        ))}
      </div>
      <button
        className="btn btn-primary"
        onClick={confirm}
        disabled={!picked || busy}
        data-testid="package-confirm"
      >
        {busy ? 'Saving…' : 'Confirm package'}
      </button>
      {error && <div className="status err">{error}</div>}
    </div>
  );
}

function AccessPendingCard({ user }: { user: TmaUser }) {
  return (
    <div className="card" data-testid="step-access-pending">
      <h2>Step 4 — Access</h2>
      <p>Once your KYC is approved and your package is confirmed, we'll flip the switch and your bot access will unlock automatically.</p>
      <div className="status warn">
        KYC: <strong>{user.kyc_status}</strong> · Package:{' '}
        <strong>{user.onboarding.package.package_id || 'not picked'}</strong>
      </div>
    </div>
  );
}

function AccessGrantedCard({ user }: { user: TmaUser }) {
  return (
    <div className="card" data-testid="step-access-granted">
      <h2>🎉 You're in, {user.first_name || user.username}!</h2>
      <p>Bot access is active. Head back to Telegram and message @ElitePocket_bot to receive your Tampermonkey activation.</p>
      <div className="status ok">Access granted</div>
    </div>
  );
}

function ReferralCard({ user }: { user: TmaUser | null }) {
  if (!user) return null;
  const shareUrl = `https://t.me/ElitePocket_bot?start=${user.referral_code}`;
  const copy = async () => {
    try { await navigator.clipboard.writeText(shareUrl); } catch { /* ignore */ }
  };
  return (
    <div className="card" data-testid="referral-card">
      <h2>Refer & earn</h2>
      <p>Share your link — every friend you onboard gives you priority signals & a % of their plan.</p>
      <div className="row">
        <input
          value={shareUrl}
          readOnly
          className="btn btn-ghost grow"
          style={{ textAlign: 'left', fontSize: 12, cursor: 'text' }}
          data-testid="referral-link"
        />
        <button className="btn btn-primary" onClick={copy} data-testid="referral-copy">Copy</button>
      </div>
    </div>
  );
}
