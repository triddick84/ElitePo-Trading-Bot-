/**
 * Thin wrapper over window.Telegram.WebApp. Falls back to a browser
 * mock when opened outside Telegram (useful for local dev / QA).
 */

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    user?: { id: number; username?: string; first_name?: string };
    start_param?: string;
  };
  ready: () => void;
  expand: () => void;
  MainButton: any;
  BackButton: any;
  colorScheme: 'light' | 'dark';
  themeParams: Record<string, string>;
  HapticFeedback?: { impactOccurred: (style: string) => void; notificationOccurred: (t: string) => void };
  openLink?: (url: string) => void;
  showAlert?: (msg: string, cb?: () => void) => void;
}

export function getTelegram(): TelegramWebApp | null {
  const w = window as any;
  return w?.Telegram?.WebApp || null;
}

/** Returns { initData, referral } — either from Telegram or a dev fallback. */
export function bootstrap(): { initData: string; referral: string | null; source: 'telegram' | 'dev' } {
  const tg = getTelegram();
  if (tg && tg.initData) {
    try { tg.ready(); tg.expand(); } catch {}
    const referral = tg.initDataUnsafe?.start_param || null;
    return { initData: tg.initData, referral, source: 'telegram' };
  }
  // Dev fallback (used only when opened directly in a browser, not TG).
  const params = new URLSearchParams(window.location.search);
  const devUid = params.get('dev_uid') || '999000001';
  const devUsername = params.get('dev_username') || 'browser_user';
  return {
    initData: `dev:${devUid}:${devUsername}`,
    referral: params.get('ref'),
    source: 'dev',
  };
}

export function openExternal(url: string) {
  const tg = getTelegram();
  if (tg?.openLink) { tg.openLink(url); return; }
  window.open(url, '_blank', 'noopener,noreferrer');
}
