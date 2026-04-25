"""
Iteration 52 backend regression tests.

Scope:
- Live OTC overlay tagging (source='po_live') in /api/signals/collect-otc-candles
- Idempotency / overlay-wins behavior on (symbol, timestamp) collisions
- /api/signals/otc-candle-stats top-level + per-symbol source_breakdown / overlay_ratio
- /api/signals/force-generate-v2 wires improved_ml_v2 + maximized_ml_v3 ensemble vote
- OTC vs non-OTC weighting: improved (4x OTC / 2.5x non-OTC), maximized (2x OTC / 3x non-OTC)
- /api/ml/tuning-report shows both models trained
- Regression: trades/report, trades/outcome, signals/win-rate-stats, ml/backfill-otc-from-oanda
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TIMEOUT = 60


# ----------------------- Fixtures -----------------------

@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def test_symbol():
    # Unique per test run so overlay/idempotency assertions are not polluted
    return f"TEST_ITER52_{uuid.uuid4().hex[:8].upper()}_OTC"


# ----------------------- Live OTC overlay tagging -----------------------

class TestOTCOverlayTagging:
    """POST /api/signals/collect-otc-candles tags inserts as source='po_live'."""

    def test_collect_otc_candles_tags_po_live(self, api, test_symbol):
        # Send 3 fresh candles
        ts_base = int(time.time())
        candles = [
            {"open": 1.10 + i * 0.0001, "high": 1.1015 + i * 0.0001,
             "low": 1.0995 + i * 0.0001, "close": 1.1010 + i * 0.0001,
             "volume": 100 + i, "timestamp": f"2026-04-25T10:00:{i:02d}Z__{ts_base}"}
            for i in range(3)
        ]
        r = api.post(
            f"{BASE_URL}/api/signals/collect-otc-candles",
            json={"symbol": test_symbol, "candles": candles, "timeframe": "5s"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True
        assert data.get("stored") == 3
        assert data.get("symbol") == test_symbol

    def test_otc_candle_stats_reflects_po_live(self, api, test_symbol):
        r = api.get(f"{BASE_URL}/api/signals/otc-candle-stats", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        data = r.json()

        # Top-level summary fields
        summary = data.get("summary") or {}
        assert "po_live_candles" in summary, f"missing po_live_candles: keys={list(summary.keys())}"
        assert "oanda_backfill_candles" in summary
        assert "overlay_ratio" in summary
        assert isinstance(summary["po_live_candles"], int)
        assert isinstance(summary["oanda_backfill_candles"], int)
        assert isinstance(summary["overlay_ratio"], (int, float))
        assert 0.0 <= summary["overlay_ratio"] <= 1.0

        # Per-symbol entry for our test symbol (key is `by_symbol` in this API)
        per_symbol = data.get("by_symbol") or data.get("per_symbol") or data.get("symbols") or []
        rows = [s for s in per_symbol if s.get("symbol") == test_symbol]
        assert rows, f"test_symbol not found in by_symbol; sample={[s.get('symbol') for s in per_symbol[:5]]}"
        sb = rows[0].get("source_breakdown")
        assert sb is not None, f"source_breakdown missing in row: {rows[0]}"
        assert sb["po_live"] == 3
        assert sb.get("oanda_backfill", 0) == 0
        assert "untagged" in sb
        assert "overlay_ratio" in sb
        assert sb["overlay_ratio"] == 1.0  # 100% po_live for fresh symbol


class TestOTCOverlayIdempotent:
    """Same (symbol, timestamp) is overwritten — po_live wins / stays po_live on re-send."""

    def test_repeat_collect_is_idempotent(self, api, test_symbol):
        # Re-send the same 3 candles (same timestamps) with mutated close price.
        ts_base_marker = "REPLAY"
        candles = [
            {"open": 1.20, "high": 1.21, "low": 1.19, "close": 1.205,
             "volume": 999, "timestamp": f"2026-04-25T11:00:{i:02d}Z__{ts_base_marker}"}
            for i in range(2)
        ]
        # First insert
        r1 = api.post(
            f"{BASE_URL}/api/signals/collect-otc-candles",
            json={"symbol": test_symbol, "candles": candles, "timeframe": "5s"},
            timeout=TIMEOUT,
        )
        assert r1.status_code == 200
        # Second insert with same timestamps but modified close
        for c in candles:
            c["close"] = 1.999
        r2 = api.post(
            f"{BASE_URL}/api/signals/collect-otc-candles",
            json={"symbol": test_symbol, "candles": candles, "timeframe": "5s"},
            timeout=TIMEOUT,
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["stored"] == 2

        # Stats: count must NOT double — upserted in place
        r3 = api.get(f"{BASE_URL}/api/signals/otc-candle-stats", timeout=TIMEOUT)
        assert r3.status_code == 200
        per_symbol = r3.json().get("by_symbol") or r3.json().get("per_symbol") or []
        row = next((s for s in per_symbol if s.get("symbol") == test_symbol), None)
        assert row is not None
        # Should be 3 (initial) + 2 (replay, deduped) = 5 NOT 7
        count = row.get("candle_count") or row.get("count")
        assert count == 5, f"upsert collision broken: count={count}"
        assert row["source_breakdown"]["po_live"] == 5


# ----------------------- ML voting in force-generate-v2 -----------------------

class TestForceGenerateV2MLVoting:
    """force-generate-v2 wires improved_ml_v2 and maximized_ml_v3 with OTC-aware weighting."""

    def test_force_generate_v2_otc_ml_components(self, api):
        r = api.get(
            f"{BASE_URL}/api/signals/force-generate-v2",
            params={"asset": "EURUSD_OTC"},
            timeout=TIMEOUT,
        )
        # Some implementations expose POST; try POST as fallback
        if r.status_code == 405:
            r = api.post(
                f"{BASE_URL}/api/signals/force-generate-v2",
                params={"asset": "EURUSD_OTC"},
                timeout=TIMEOUT,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        signal = body.get("signal") or body
        comps = signal.get("components") or body.get("components") or {}

        assert "improved_ml_v2" in comps, f"improved_ml_v2 missing; comps keys={list(comps.keys())}"
        assert "maximized_ml_v3" in comps, f"maximized_ml_v3 missing; comps keys={list(comps.keys())}"

        imp = comps["improved_ml_v2"]
        mx = comps["maximized_ml_v3"]
        for c, name in ((imp, "improved_ml_v2"), (mx, "maximized_ml_v3")):
            assert c["direction"] in ("CALL", "PUT"), f"{name}.direction={c.get('direction')}"
            assert isinstance(c["confidence"], (int, float))
            assert isinstance(c["weight"], (int, float))
            assert isinstance(c["model_accuracy"], (int, float))

        # OTC weights: improved 4.0*acc, maximized 2.0*acc
        imp_expected = 4.0 * (imp["model_accuracy"] / 100.0)
        mx_expected = 2.0 * (mx["model_accuracy"] / 100.0)
        assert abs(imp["weight"] - imp_expected) < 0.05, f"OTC improved weight {imp['weight']} vs expected {imp_expected:.2f}"
        assert abs(mx["weight"] - mx_expected) < 0.05, f"OTC maximized weight {mx['weight']} vs expected {mx_expected:.2f}"
        # On OTC, improved should outweigh maximized
        assert imp["weight"] > mx["weight"], f"OTC: improved should outweigh maximized; got {imp['weight']} vs {mx['weight']}"

    def test_force_generate_v2_non_otc_ml_components(self, api):
        r = api.get(
            f"{BASE_URL}/api/signals/force-generate-v2",
            params={"asset": "EUR_USD"},
            timeout=TIMEOUT,
        )
        if r.status_code == 405:
            r = api.post(
                f"{BASE_URL}/api/signals/force-generate-v2",
                params={"asset": "EUR_USD"},
                timeout=TIMEOUT,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        signal = body.get("signal") or body
        comps = signal.get("components") or body.get("components") or {}
        assert "improved_ml_v2" in comps
        assert "maximized_ml_v3" in comps
        imp = comps["improved_ml_v2"]
        mx = comps["maximized_ml_v3"]
        # Non-OTC: improved 2.5*acc, maximized 3.0*acc
        imp_expected = 2.5 * (imp["model_accuracy"] / 100.0)
        mx_expected = 3.0 * (mx["model_accuracy"] / 100.0)
        assert abs(imp["weight"] - imp_expected) < 0.05, f"non-OTC improved weight {imp['weight']} vs expected {imp_expected:.2f}"
        assert abs(mx["weight"] - mx_expected) < 0.05, f"non-OTC maximized weight {mx['weight']} vs expected {mx_expected:.2f}"
        # Non-OTC: maximized should slightly outweigh improved
        assert mx["weight"] >= imp["weight"], f"non-OTC: maximized should be >= improved; got {mx['weight']} vs {imp['weight']}"

    def test_force_generate_v2_envelope_no_regression(self, api):
        r = api.get(
            f"{BASE_URL}/api/signals/force-generate-v2",
            params={"asset": "EURUSD_OTC"},
            timeout=TIMEOUT,
        )
        if r.status_code == 405:
            r = api.post(
                f"{BASE_URL}/api/signals/force-generate-v2",
                params={"asset": "EURUSD_OTC"},
                timeout=TIMEOUT,
            )
        assert r.status_code == 200
        body = r.json()
        signal = body.get("signal") or body
        for k in ("direction", "confidence", "quality", "agreeing_strategies",
                  "beta", "components", "votes", "confluence_score"):
            assert k in signal, f"envelope missing '{k}'; keys={list(signal.keys())}"
        assert signal["direction"] in ("CALL", "PUT")
        assert isinstance(signal["beta"], bool)


# ----------------------- ML tuning report -----------------------

class TestMLTuningReport:
    def test_tuning_report_shows_both_models(self, api):
        r = api.get(f"{BASE_URL}/api/ml/tuning-report", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        ms = body.get("model_status") or body.get("models") or {}
        improved = ms.get("improved_v2") or ms.get("improved_ml_v2")
        maximized = ms.get("maximized_v3") or ms.get("maximized_ml_v3")
        assert improved is not None, f"improved_v2 not in tuning-report.model_status; keys={list(ms.keys())}"
        assert maximized is not None, f"maximized_v3 not in tuning-report.model_status; keys={list(ms.keys())}"
        # API uses is_trained, not trained
        assert improved.get("is_trained") is True or improved.get("trained") is True, f"improved is_trained={improved}"
        assert maximized.get("is_trained") is True or maximized.get("trained") is True, f"maximized is_trained={maximized}"
        assert float(improved.get("accuracy", 0)) > 0
        assert float(maximized.get("accuracy", 0)) > 0


# ----------------------- Regression -----------------------

class TestRegressionEndpoints:
    def test_trades_report(self, api):
        payload = {
            "asset": "TEST_ITER52_REG",
            "direction": "CALL",
            "confidence": 70,
            "strategy": "TEST_ITER52",
            "timestamp": "2026-04-25T12:00:00Z",
        }
        r = api.post(f"{BASE_URL}/api/trades/report", json=payload, timeout=TIMEOUT)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body.get("success") is True or body.get("trade_id") or body.get("id")

    def test_trades_outcome(self, api):
        payload = {
            "asset": "TEST_ITER52_REG",
            "direction": "CALL",
            "outcome": "WIN",
            "strategy": "TEST_ITER52",
            "timestamp": "2026-04-25T12:00:30Z",
        }
        r = api.post(f"{BASE_URL}/api/trades/outcome", json=payload, timeout=TIMEOUT)
        assert r.status_code in (200, 201), r.text

    def test_win_rate_stats(self, api):
        r = api.get(f"{BASE_URL}/api/signals/win-rate-stats", timeout=TIMEOUT)
        assert r.status_code == 200, r.text

    def test_backfill_otc_from_oanda_endpoint_exists(self, api):
        # Light-touch: tiny request to confirm the route is alive (200/202/4xx all OK
        # — we just want to confirm it didn't get accidentally removed).
        r = api.post(
            f"{BASE_URL}/api/ml/backfill-otc-from-oanda",
            json={"symbol": "EURUSD_OTC", "days": 1},
            timeout=TIMEOUT,
        )
        # Anything except 404/500 means the route is wired
        assert r.status_code != 404, "backfill-otc-from-oanda route disappeared"
        assert r.status_code != 405, f"method not allowed: {r.status_code}"
        # 200/202/400/422 all acceptable as 'route exists'
        assert r.status_code in (200, 201, 202, 400, 422), f"unexpected: {r.status_code} body={r.text[:200]}"
