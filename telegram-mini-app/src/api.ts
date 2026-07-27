// Central API client. The TMA is served from the same origin as the FastAPI
// backend (via the CRA static serve), so relative /api URLs Just Work.

const BASE = '/api/tma';

function authHeaders(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function jsonFetch<T = any>(
  path: string,
  init: RequestInit = {},
  token: string | null = null,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(token),
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try { detail = JSON.parse(text).detail || detail; } catch {}
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json() as Promise<T>;
}

export interface Onboarding {
  po_signup: { completed: boolean; at: string | null };
  kyc: { completed: boolean; at: string | null };
  package: { completed: boolean; at: string | null; package_id: string | null };
  access: { completed: boolean; at: string | null };
}

export interface TmaUser {
  id: string;
  telegram_user_id: number;
  username: string;
  first_name?: string;
  role: 'admin' | 'user';
  referral_code: string;
  referred_by: string | null;
  onboarding: Onboarding;
  access_granted: boolean;
  kyc_status: 'not_submitted' | 'pending' | 'approved' | 'rejected';
}

export interface Package {
  id: string;
  name: string;
  cadence: string;
  price_usd: number;
  description: string;
  features: string[];
  highlight?: boolean;
}

export const api = {
  auth(initData: string, referral: string | null) {
    return jsonFetch<{ token: string; user: TmaUser; affiliate_url: string }>(
      '/auth',
      { method: 'POST', body: JSON.stringify({ init_data: initData, referral_code: referral }) },
    );
  },
  me(token: string) {
    return jsonFetch<{ user: TmaUser }>('/me', {}, token);
  },
  onboardingState(token: string) {
    return jsonFetch<{
      steps: string[];
      onboarding: Onboarding;
      next_step: string;
      affiliate_url: string;
      kyc_status: string;
      access_granted: boolean;
    }>('/onboarding/state', {}, token);
  },
  onboardingUpdate(token: string, step: string, value?: string) {
    return jsonFetch<{ user: TmaUser }>(
      '/onboarding/update',
      { method: 'POST', body: JSON.stringify({ step, value }) },
      token,
    );
  },
  packages(token: string) {
    return jsonFetch<{ packages: Package[] }>('/packages', {}, token);
  },
  async uploadKyc(token: string, file: File) {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/kyc/upload`, {
      method: 'POST',
      headers: { ...authHeaders(token) },
      body: form,
    });
    if (!res.ok) {
      const text = await res.text();
      let detail = text;
      try { detail = JSON.parse(text).detail || detail; } catch {}
      throw new Error(`${res.status} ${detail}`);
    }
    return res.json() as Promise<{ kyc_id: string; status: string }>;
  },
  kycStatus(token: string) {
    return jsonFetch<{ status: string; submission: any }>('/kyc/status', {}, token);
  },
};
