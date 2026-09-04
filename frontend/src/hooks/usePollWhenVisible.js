/**
 * Iter 121 — usePollWhenVisible
 *
 * Poll an async callback at `intervalMs` — but ONLY while the browser tab is
 * visible. Pauses on tab-hide and immediately refreshes + resumes on tab-show.
 *
 * This is the single biggest lever for reducing background API load — users
 * often leave 3-5 tabs open with dashboards that would otherwise keep hitting
 * the backend indefinitely.
 *
 * Usage:
 *   usePollWhenVisible(fetchStatus, 4000, [dep1, dep2]);
 */
import { useEffect, useRef } from 'react';

export default function usePollWhenVisible(callback, intervalMs, deps = []) {
  const cbRef = useRef(callback);
  useEffect(() => {
    cbRef.current = callback;
  }, [callback]);

  useEffect(() => {
    let timerId = null;

    const tick = () => {
      try {
        cbRef.current && cbRef.current();
      } catch (e) {
        console.error('poll callback failed', e);
      }
    };

    const start = () => {
      if (timerId != null) return;
      timerId = setInterval(tick, intervalMs);
    };
    const stop = () => {
      if (timerId != null) {
        clearInterval(timerId);
        timerId = null;
      }
    };

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        tick(); // refresh immediately
        start();
      } else {
        stop();
      }
    };

    if (document.visibilityState === 'visible') start();
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, ...deps]);
}
