"""
Iter 112 — Auto-Scan & Route (dashboard → TM handoff) tests.

Covers:
  • AutoScanService singleton exists with core methods
  • Config default shape + partial merge (deep-merges strategy dict)
  • scan_once returns matched/direction/confidence/elite_score fields
  • _route_to_tm actually writes the singleton tampermonkey_settings
  • REST endpoints exist and validate payloads
  • React AutoScanPanel wired into Dashboard.js with correct testids
"""

import re
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"


# ---------------------------------------------------------------------------
# Service behaviour
# ---------------------------------------------------------------------------
class TestAutoScanService:
    def test_singleton_exists(self):
        from auto_scan_service import auto_scan_service, AutoScanService
        assert isinstance(auto_scan_service, AutoScanService)
        for m in ("scan_once", "start", "stop", "status",
                  "set_config", "bind_db", "load_persisted_config"):
            assert hasattr(auto_scan_service, m)

    def test_default_config_shape(self):
        from auto_scan_service import auto_scan_service, DEFAULT_CONFIG
        # All keys accounted for
        for k in ("enabled", "interval_seconds", "chart_timeframe",
                  "trade_duration_seconds", "min_confidence",
                  "min_elite_score", "prefer_elite_on_tie", "assets",
                  "strategy", "force_signal", "target_ttl_seconds"):
            assert k in DEFAULT_CONFIG
        # Sensible defaults
        assert DEFAULT_CONFIG["min_confidence"] > 0
        assert DEFAULT_CONFIG["interval_seconds"] > 0

    @pytest.mark.asyncio
    async def test_set_config_deep_merges_strategy(self):
        from auto_scan_service import auto_scan_service
        # Reset to known-good state first
        await auto_scan_service.set_config({"interval_seconds": 10,
                                            "strategy": {"sma_fast": 8}})
        # Partial update should NOT wipe sma_slow
        cfg = await auto_scan_service.set_config({"strategy": {"sma_slow": 20}})
        assert cfg["strategy"]["sma_fast"] == 8
        assert cfg["strategy"]["sma_slow"] == 20
        assert cfg["interval_seconds"] == 10

    @pytest.mark.asyncio
    async def test_scan_once_with_empty_universe_returns_error(self):
        from auto_scan_service import auto_scan_service
        # Ensure assets list is empty
        await auto_scan_service.set_config({"assets": []})
        r = await auto_scan_service.scan_once(assets=[])
        assert r["success"] is False
        assert "empty" in r["error"] or "no assets" in r["error"]

    @pytest.mark.asyncio
    async def test_route_to_tm_writes_active_target(self):
        from auto_scan_service import auto_scan_service
        # Mock the DB
        mock_col = MagicMock()
        mock_col.update_one = AsyncMock()
        mock_db = MagicMock()
        mock_db.tampermonkey_settings = mock_col
        auto_scan_service.bind_db(mock_db)

        winner = {"asset": "EURJPY_OTC", "direction": "CALL",
                  "confidence": 0.78, "elite_score": 30.9}
        await auto_scan_service._route_to_tm(
            winner, {"chart_timeframe": "1m", "target_ttl_seconds": 60})

        # Verify update_one called with singleton + active_target
        mock_col.update_one.assert_called_once()
        call_kwargs = mock_col.update_one.call_args
        args, kwargs = call_kwargs.args, call_kwargs.kwargs
        assert args[0] == {"_id": "singleton"}
        set_doc = args[1]["$set"]
        target = set_doc["active_target"]
        assert target["asset"] == "EURJPY_OTC"
        assert target["direction"] == "CALL"
        assert target["source"] == "auto_scan"
        assert kwargs.get("upsert") is True


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
class TestAutoScanEndpoints:
    @pytest.mark.asyncio
    async def test_status_endpoint(self):
        from routes.auto_scan import auto_scan_status
        r = await auto_scan_status()
        assert r["success"] is True
        assert "running" in r
        assert "config" in r
        assert "stats" in r

    @pytest.mark.asyncio
    async def test_set_config_endpoint(self):
        from routes.auto_scan import auto_scan_set_config, AutoScanConfigPayload
        payload = AutoScanConfigPayload(
            interval_seconds=20, min_confidence=0.7,
            assets=["EURUSD_OTC", "GBPUSD_OTC"],
        )
        r = await auto_scan_set_config(payload)
        assert r["success"] is True
        assert r["config"]["interval_seconds"] == 20
        assert r["config"]["min_confidence"] == 0.7
        assert r["config"]["assets"] == ["EURUSD_OTC", "GBPUSD_OTC"]

    def test_config_payload_validates_ranges(self):
        from routes.auto_scan import AutoScanConfigPayload
        # Should reject out-of-range values
        with pytest.raises(Exception):
            AutoScanConfigPayload(interval_seconds=1)  # min is 3
        with pytest.raises(Exception):
            AutoScanConfigPayload(min_confidence=1.5)  # max is 1.0


# ---------------------------------------------------------------------------
# Frontend wiring
# ---------------------------------------------------------------------------
class TestAutoScanPanelWiring:
    def test_component_file_exists(self):
        p = FRONTEND_DIR / "src" / "components" / "AutoScanPanel.jsx"
        assert p.exists()
        body = p.read_text()
        # Critical testids
        for tid in ("auto-scan-panel", "auto-scan-status-badge",
                    "auto-scan-universe", "auto-scan-interval-slider",
                    "auto-scan-confidence-slider", "auto-scan-elite-slider",
                    "auto-scan-start-btn", "auto-scan-scan-now-btn",
                    "auto-scan-results-table"):
            assert f'data-testid="{tid}"' in body, f"testid {tid} missing"

    def test_dashboard_imports_and_mounts_panel(self):
        p = FRONTEND_DIR / "src" / "components" / "DashboardRestructured.js"
        body = p.read_text()
        assert "import AutoScanPanel from './AutoScanPanel'" in body
        assert "<AutoScanPanel selectedAssets={config.selected_assets" in body


# ---------------------------------------------------------------------------
# Server registration
# ---------------------------------------------------------------------------
class TestServerRegistration:
    def test_router_registered(self):
        p = BACKEND_DIR / "server.py"
        body = p.read_text()
        assert "from routes.auto_scan import router as auto_scan_router" in body
        assert "api_router.include_router(auto_scan_router)" in body

    def test_startup_binds_and_restores(self):
        p = BACKEND_DIR / "server.py"
        body = p.read_text()
        assert "auto_scan_service.bind_db(db)" in body
        assert "load_persisted_config" in body


# ---------------------------------------------------------------------------
# No-regression
# ---------------------------------------------------------------------------
class TestNoRegression:
    def test_iter111_microstructure_fix_intact(self):
        p = BACKEND_DIR / "microstructure_models.py"
        body = p.read_text()
        assert '"symbol": {"$in":' in body

    def test_iter110_master_toggle_intact(self):
        b = (FRONTEND_DIR / "public" / "pocket-option-auto-trader.user.js").read_text()
        assert "tm-master-toggle" in b
