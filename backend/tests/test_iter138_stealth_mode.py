"""Iter 138 — Stealth Mode smoke tests.

Verifies the compiled TM bundle actually contains the stealth-mode wiring
and that /api/tampermonkey/script serves it with the correct version + UI
markers. This is a regression guard so future rebuilds can't silently drop
the feature.
"""

import re
import subprocess
from pathlib import Path

import pytest


BUNDLE_PATHS = [
    Path("/app/tampermonkey-src/dist/pocket-option-auto-trader.user.js"),
    Path("/app/frontend/public/pocket-option-auto-trader.user.js"),
    Path("/app/frontend/public/pocket-option-auto-trader-modular.user.js"),
]

EXPECTED_VERSION = "8.151.0"


def _read_bundle(p: Path) -> str:
    if not p.exists():
        pytest.skip(f"bundle missing: {p}")
    return p.read_text(encoding="utf-8")


@pytest.mark.parametrize("bundle", BUNDLE_PATHS, ids=lambda p: p.name + ":" + p.parent.name)
def test_bundle_version_is_bumped(bundle: Path):
    text = _read_bundle(bundle)
    m = re.search(r"//\s*@version\s+([\d.]+)", text)
    assert m, f"no @version header in {bundle}"
    assert m.group(1) == EXPECTED_VERSION, (
        f"{bundle} still on {m.group(1)}, expected {EXPECTED_VERSION}"
    )


@pytest.mark.parametrize("bundle", BUNDLE_PATHS, ids=lambda p: p.name + ":" + p.parent.name)
def test_bundle_contains_stealth_storage_key(bundle: Path):
    text = _read_bundle(bundle)
    assert "epb_stealth_mode" in text, (
        f"stealth-mode storage key missing from {bundle} — module not bundled"
    )


@pytest.mark.parametrize("bundle", BUNDLE_PATHS, ids=lambda p: p.name + ":" + p.parent.name)
def test_bundle_contains_stealth_panel_hook(bundle: Path):
    """The panel toggle button uses data-testid=btn-stealth-toggle."""
    text = _read_bundle(bundle)
    assert "btn-stealth-toggle" in text, (
        f"stealth toggle button missing from {bundle} — UI wiring lost"
    )


@pytest.mark.parametrize("bundle", BUNDLE_PATHS, ids=lambda p: p.name + ":" + p.parent.name)
def test_bundle_connect_allowlist_expanded(bundle: Path):
    text = _read_bundle(bundle)
    # v8.148 expanded the allow-list — regression guard
    for host in ("auto-invert-engine.preview.emergentagent.com", "emergentagent.com"):
        assert f"@connect      {host}" in text or f"@connect {host}" in text, (
            f"@connect entry for {host} missing from {bundle}"
        )
    assert "@connect      *" in text or "@connect *" in text, (
        "wildcard @connect missing — TM will prompt on every backend call"
    )


def test_served_endpoint_matches_bundle():
    """/api/tampermonkey/script must serve the same version we just built."""
    api_url = None
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            api_url = line.split("=", 1)[1].strip()
            break
    if not api_url:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    r = subprocess.run(
        ["curl", "-sS", f"{api_url}/api/tampermonkey/script"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 0, f"curl failed: {r.stderr}"
    body = r.stdout
    m = re.search(r"//\s*@version\s+([\d.]+)", body)
    assert m, "served bundle has no @version"
    assert m.group(1) == EXPECTED_VERSION, (
        f"served bundle is {m.group(1)}, expected {EXPECTED_VERSION}"
    )
    assert "epb_stealth_mode" in body, "served bundle missing stealth module"
    assert "btn-stealth-toggle" in body, "served bundle missing stealth toggle UI"
