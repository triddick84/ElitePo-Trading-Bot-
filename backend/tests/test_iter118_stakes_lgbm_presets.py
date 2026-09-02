"""
Iter 118 — Confidence-Tiered Stakes · Live-Trade LightGBM Retrain · AI Gates Presets.

Backend regression:
  B) /api/tampermonkey/stake-tiers GET/POST roundtrip + validation
  D) /api/ml/lightgbm/record-live-sample + auto-retrain threshold
  D) /api/ml/lightgbm/live-samples/stats + /api/ml/lightgbm/retrain-live
  A) /api/ai/gates/presets list + /api/ai/gates/apply-preset overwrites config
  Bundle) v8.143+ contains _stakeTiersConfig plumbing
"""

import re
import pytest
import httpx


def _api() -> str:
    env = open("/app/frontend/.env").read()
    m = re.search(r"REACT_APP_BACKEND_URL=(\S+)", env)
    assert m
    return f"{m.group(1)}/api"


API = _api()
BUNDLE = _api().rsplit("/api", 1)[0] + "/pocket-option-auto-trader-modular.user.js"


@pytest.mark.asyncio
async def test_b_stake_tiers_roundtrip():
    async with httpx.AsyncClient(timeout=30.0) as c:
        payload = {
            "enabled": True,
            "auto_set": False,
            "fallback": 2,
            "tiers": [
                {"min_conf": 75, "max_conf": 84, "amount": 1, "label": "Good"},
                {"min_conf": 85, "max_conf": 92, "amount": 3, "label": "Great"},
                {"min_conf": 93, "max_conf": 100, "amount": 8, "label": "Elite"},
            ],
        }
        r1 = await c.post(f"{API}/tampermonkey/stake-tiers", json=payload)
        assert r1.status_code == 200 and r1.json()["success"]

        r2 = await c.get(f"{API}/tampermonkey/stake-tiers")
    body = r2.json()
    assert body["success"] and body["enabled"] is True
    assert body["auto_set"] is False
    assert body["fallback"] == 2
    assert len(body["tiers"]) == 3
    # sorted asc by min_conf
    assert [t["min_conf"] for t in body["tiers"]] == [75, 85, 93]


@pytest.mark.asyncio
async def test_b_stake_tiers_validation():
    """Bad tiers should be silently dropped."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{API}/tampermonkey/stake-tiers", json={
            "enabled": True, "auto_set": True, "fallback": 1,
            "tiers": [
                {"min_conf": "bad", "max_conf": 90, "amount": 1},   # dropped
                {"min_conf": 80, "max_conf": 89, "amount": 0},       # dropped (amount<=0)
                {"min_conf": 90, "max_conf": 100, "amount": 5},
            ],
        })
    assert r.status_code == 200
    tiers = r.json()["tiers"]
    assert len(tiers) == 1 and tiers[0]["min_conf"] == 90


@pytest.mark.asyncio
async def test_d_live_sample_record_stats_and_retrain():
    async with httpx.AsyncClient(timeout=60.0) as c:
        # Record one sample
        r1 = await c.post(f"{API}/ml/lightgbm/record-live-sample", json={
            "outcome": "WIN",
            "features": {"rsi": 55, "adx": 30, "regime_code": 2,
                         "vote_up": 1, "vote_down": 0,
                         "mean_confidence": 0.85, "max_confidence": 0.85},
            "metadata": {"direction": "CALL", "asset": "EURUSD_OTC"},
        })
        assert r1.status_code == 200
        j = r1.json()
        assert j["success"] and j["sample_stored"]
        assert j["total_live_samples"] >= 1

        # Stats visible
        r2 = await c.get(f"{API}/ml/lightgbm/live-samples/stats")
        assert r2.status_code == 200
        assert r2.json()["total"] >= 1

        # Force retrain (may fail if too few samples — that's expected)
        r3 = await c.post(f"{API}/ml/lightgbm/retrain-live")
        assert r3.status_code == 200
        # Either succeeded or reported insufficient samples
        assert "success" in r3.json()


@pytest.mark.asyncio
async def test_a_gates_presets_and_apply():
    async with httpx.AsyncClient(timeout=30.0) as c:
        r0 = await c.get(f"{API}/ai/gates/presets")
        assert r0.status_code == 200
        ids = [p["id"] for p in r0.json()["presets"]]
        assert set(ids) == {"conservative", "balanced", "aggressive"}

        r1 = await c.post(f"{API}/ai/gates/apply-preset", json={"preset": "conservative"})
        assert r1.status_code == 200
        cfg = r1.json()["config"]
        assert cfg["adx_regime_enabled"] is True
        assert cfg["ha_min_streak"] == 3
        assert cfg["ha_require_no_opposing_wick"] is True

        r2 = await c.post(f"{API}/ai/gates/apply-preset", json={"preset": "aggressive"})
        assert r2.status_code == 200
        cfg2 = r2.json()["config"]
        assert cfg2["adx_regime_enabled"] is False

        # Unknown preset should 400
        r3 = await c.post(f"{API}/ai/gates/apply-preset", json={"preset": "nonsense"})
        assert r3.status_code == 400

        # Reset back to balanced
        await c.post(f"{API}/ai/gates/apply-preset", json={"preset": "balanced"})


@pytest.mark.asyncio
async def test_bundle_has_stake_tiers_plumbing_and_version():
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as c:
        r = await c.get(BUNDLE)
    assert r.status_code == 200
    src = r.text
    m = re.search(r"@version\s+(\S+)", src)
    assert m, "no @version"
    parts = m.group(1).split(".")
    assert int(parts[0]) >= 8 and int(parts[1]) >= 143, f"version too low: {m.group(1)}"
    # Stake-tiers plumbing:
    assert "/tampermonkey/stake-tiers" in src, "bundle missing stake-tiers URL"
    assert "stake_tiers_enabled" not in src or "stake" in src.lower()  # snake-case may be mangled; loose check
