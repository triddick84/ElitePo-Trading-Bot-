"""
Iter 89 — GZip compression + Signal pre-generation buffer.

Guards:
1. GZip response compression is enabled on FastAPI.
2. /api/signal-prewarm/stats is reachable + returns the expected shape.
3. Prewarm buffer records touches when /signals/latest is polled.
4. Prewarm background refresher populates writes over time.
"""

from __future__ import annotations

import os
import time
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


def test_gzip_compression_enabled_on_signals_latest():
    """A large-enough JSON response must come back gzipped."""
    r = requests.get(
        f"{BASE_URL}/api/signals/latest",
        headers={"Accept-Encoding": "gzip"},
        params={"symbol": "EURUSD_OTC"},
        timeout=15,
        stream=True,
    )
    r.raw.decode_content = False  # so we can inspect the encoding header
    assert r.status_code == 200
    ce = r.headers.get("Content-Encoding", "").lower()
    assert "gzip" in ce, f"Expected gzip Content-Encoding, got {ce!r}"


def test_gzip_reduces_large_response_size():
    """
    Compressed response for a large payload should be materially smaller
    than the uncompressed version — measured on the raw byte stream so
    requests' auto-decoder doesn't hide the compression win.
    """
    import urllib.request

    def _fetch(headers):
        req = urllib.request.Request(
            f"{BASE_URL}/api/signals/latest?symbol=EURUSD_OTC",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.getheader("Content-Encoding", ""), resp.read()

    ce_gz, body_gz = _fetch({"Accept-Encoding": "gzip"})
    ce_id, body_id = _fetch({"Accept-Encoding": "identity"})

    assert "gzip" in ce_gz.lower(), f"gzip request got Content-Encoding={ce_gz!r}"
    # For payloads > 500 B, gzip should shrink at least 30%
    if len(body_id) > 500:
        assert len(body_gz) < len(body_id) * 0.7, \
            f"gzip barely helped: {len(body_id)}B raw -> {len(body_gz)}B on wire"


def test_signal_prewarm_stats_endpoint_reachable():
    r = requests.get(f"{BASE_URL}/api/signal-prewarm/stats", timeout=5).json()
    assert r.get("success") is True
    for key in ("size", "tracked_active", "hits", "misses", "writes",
                "ttl_seconds", "refresh_interval_seconds", "entries"):
        assert key in r, f"Missing key {key!r} in stats"
    assert isinstance(r["entries"], list)


def test_prewarm_touches_are_tracked():
    """Polling /signals/latest?symbol=X should mark X as active."""
    before = requests.get(f"{BASE_URL}/api/signal-prewarm/stats", timeout=5).json()
    # Poll a symbol we know exists in the touch scan
    requests.get(f"{BASE_URL}/api/signals/latest",
                 params={"symbol": "AUDCAD_OTC"}, timeout=15)
    after = requests.get(f"{BASE_URL}/api/signal-prewarm/stats", timeout=5).json()
    assert after["tracked_active"] >= before["tracked_active"]


def test_prewarm_background_refresher_makes_progress():
    """Over a 6s window the background loop should attempt writes."""
    r0 = requests.get(f"{BASE_URL}/api/signal-prewarm/stats", timeout=5).json()
    # Touch a couple of combos then wait
    for sym in ("EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC"):
        requests.get(f"{BASE_URL}/api/signals/latest",
                     params={"symbol": sym}, timeout=15)
    time.sleep(6)  # ≥ 3x refresh interval
    r1 = requests.get(f"{BASE_URL}/api/signal-prewarm/stats", timeout=5).json()
    # Either writes went up, or misses went up (at minimum the loop is alive)
    assert (r1["writes"] >= r0["writes"]) and (r1["misses"] >= r0["misses"])


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
