"""
Iter 78 (Feb 28, 2026) — regression for deployment-blocking dependencies.

Root cause of production deploy failure (uvicorn: command not found):
  backend/requirements.txt line 15 referenced a LOCAL FILE WHEEL:
      BinaryOptionsToolsV2 @ file:///tmp/BinaryOptionsTools-v2/.../wheel
  which doesn't exist on the Kubernetes deploy build server. pip install
  bombed at that line, never reached `uvicorn==0.25.0` further down,
  and the entrypoint then failed with "uvicorn: command not found"
  → nginx had no upstream → every /api/* call returned the "red X
  connection error" the user was seeing on production.

Fix: removed all packages that are either:
  * Local-path/git-URL requirements (uninstallable on a fresh image)
  * OS-level C-lib dependencies (TA-Lib needs libta-lib0)
  * Heavy browser-automation packages (selenium, playwright, drivers)
  * GPU-targeted frameworks (tensorflow, keras, tensorboard) that
    exceed the 1Gi memory ceiling of the deploy pod

All these imports were already wrapped in try/except ImportError blocks
in the code so removal is graceful.

This file locks in those removals so a regression can't silently
re-introduce them and break production again.
"""
from pathlib import Path

import requests

API = "http://localhost:8001/api"
REQ_FILE = Path("/app/backend/requirements.txt")


FORBIDDEN_LINE_PATTERNS = (
    "@ file://",                # any local-file wheel reference
    "@ git+",                   # any git-url install
    "BinaryOptionsToolsV2",     # the specific original culprit
    "pocketoptionapi-async",    # git-url variant
    "tensorflow==",
    "tensorboard==",
    "keras==",
    "TA-Lib==",
    "selenium==",
    "playwright==",
    "playwright-stealth",
    "undetected-chromedriver",
    "webdriver-manager",
)


def _read_requirements() -> list[str]:
    return [
        line.strip()
        for line in REQ_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_requirements_has_no_deploy_blockers():
    """No requirement line may reference a local file path, a git URL,
    or any of the known heavyweight ML / browser-automation packages."""
    lines = _read_requirements()
    offenders = []
    for line in lines:
        for needle in FORBIDDEN_LINE_PATTERNS:
            if needle in line:
                offenders.append((needle, line))
    assert not offenders, (
        "requirements.txt contains deploy-blocking entries:\n  "
        + "\n  ".join(f"[{n}] {l}" for n, l in offenders)
    )


def test_requirements_still_includes_critical_runtime_deps():
    """Confirm the trimmed requirements.txt still pins the libs that
    server.py imports at module load. If any of these go missing the
    backend will crash on import in production too."""
    text = REQ_FILE.read_text(encoding="utf-8")
    must_have = (
        "uvicorn==",       # entrypoint command
        "fastapi==",       # web framework
        "motor==",         # async mongo driver used by routes
        "pymongo==",       # sync mongo driver used by backtest engine
        "scikit-learn==",  # ML trainer base
        "pandas==",
        "numpy==",
        "python-dotenv==",
        "passlib==",       # auth service password hashing
        "PyJWT==",         # auth service token signing
        "imbalanced-learn==",  # SMOTE (iter75)
    )
    missing = [k for k in must_have if k not in text]
    assert not missing, f"requirements.txt missing critical runtime deps: {missing}"


def test_backend_still_serves_health_after_trim():
    """Sanity smoke: with the trimmed requirements, the live backend on
    preview must still respond to /api/health. If a removed package was
    actually required at import time the server would crash on startup
    and this would fail."""
    r = requests.get(f"{API}/health", timeout=30)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert data.get("status") == "healthy"
    # `app_initialized` flips to True after the background init task
    # completes (a few seconds after uvicorn boots). The smoke we care
    # about here is just "did the import succeed and is uvicorn serving
    # responses" — which the 200 + healthy status already confirms.


def test_login_still_works_after_trim():
    """End-to-end: trimmed requirements must not break auth_service."""
    r = requests.post(
        f"{API}/auth/login",
        json={"username": "seedtest", "password": "SeedPass123!"},
        timeout=60,
    )
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert data.get("success") is True
    assert data.get("token"), "expected JWT in login response"
