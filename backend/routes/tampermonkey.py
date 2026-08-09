"""
Tampermonkey userscript integration endpoints.

These are the endpoints called by the compiled `pocket-option-auto-trader.user.js`
bundle (v8.122.0+) that were not covered by the other modular routers:

- GET  /api/tampermonkey/script  → serves the compiled userscript for @updateURL
                                    / @downloadURL auto-updates.
- GET  /api/settings/chart       → returns the user's current chart type /
                                    timeframe so the TM panel can render the
                                    right chart-mode indicator.
- POST /api/diag/ws-frames       → sink for TM WS frame diagnostics (fire-and-
                                    forget, capped so we don't blow up Mongo).

Kept intentionally lightweight — no heavy dependencies, no ML imports.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Mongo bootstrap — matches the pattern in the other route modules so we can
# read/write persisted settings without touching server.py globals.
# ---------------------------------------------------------------------------
_client: AsyncIOMotorClient | None = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        from dotenv import load_dotenv
        from pathlib import Path
        load_dotenv(Path(__file__).parent.parent / ".env")
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        _db = _client[os.environ["DB_NAME"]]
    return _db


# ---------------------------------------------------------------------------
# GET /api/tampermonkey/script  →  compiled userscript
# ---------------------------------------------------------------------------
# The compiled bundle lives in /app/frontend/public/ (served both by CRA in dev
# and copied into the static build in prod). We serve it here so Tampermonkey
# can honour @updateURL/@downloadURL without exposing an unversioned public path.

USERSCRIPT_PATHS = [
    Path("/app/frontend/public/pocket-option-auto-trader.user.js"),
    Path("/app/frontend/public/pocket-option-auto-trader-modular.user.js"),
    Path("/app/tampermonkey-src/dist/pocket-option-auto-trader.user.js"),
]


# Iter 93 — Hardcoded API_URL in the compiled bundle. The user has been
# expected to manually GM_setValue("epb_api_url", "…") to override this. When
# they don't (or storage got cleared), every fetch goes to the stale
# elitepotradingbot.com domain and the TM panel shows "Backend disconnected".
# Fix: rewrite the compiled bundle at delivery time so API_URL always points
# to whichever host is actually SERVING the script. Self-healing.
_STALE_API_URL_LITERAL = 'API_URL:"https://www.elitepotradingbot.com/api"'


def _resolve_public_api_root(request: Request) -> str:
    """
    Figure out the API root URL to inject. Priority:
      1. `PUBLIC_API_URL` env override (for production deployments where the
         backend host and the user-facing host differ).
      2. The forwarded scheme+host on the incoming request (works both in
         preview + production behind the Emergent ingress).
      3. Falls back to `https://<host>/api`.
    """
    override = os.environ.get("PUBLIC_API_URL", "").strip().rstrip("/")
    if override:
        return override if override.endswith("/api") else f"{override}/api"

    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.hostname
        or ""
    ).strip()
    if not host:
        return "/api"  # relative fallback — GM_xmlhttpRequest can't use this, but at least fail-safe
    return f"{scheme}://{host}/api"


@router.get("/tampermonkey/script")
async def get_tampermonkey_script(request: Request):
    """
    Serve the compiled userscript with API_URL rewritten to match the
    host that's actually serving it — so the TM panel connects back to
    whatever backend the user grabbed the script from.
    """
    for p in USERSCRIPT_PATHS:
        if not p.exists():
            continue
        try:
            raw = p.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("[tampermonkey/script] failed to read %s: %s", p, e)
            continue

        api_root = _resolve_public_api_root(request)
        rewritten_literal = f'API_URL:"{api_root}"'
        if _STALE_API_URL_LITERAL in raw:
            raw = raw.replace(_STALE_API_URL_LITERAL, rewritten_literal)
            logger.info(
                "[tampermonkey/script] rewrote API_URL -> %s (host=%s)",
                api_root,
                request.headers.get("host"),
            )
        else:
            # Best-effort catch — rewrite ANY hardcoded API_URL literal in
            # the compiled bundle to the current serving host. Handles the
            # legacy elitepotradingbot.com literal AND any preview/prod
            # hostname that got baked in during a fresh webpack build.
            import re
            raw, _n = re.subn(
                r'API_URL\s*:\s*["\']https?://[^"\'\\]+["\']',
                rewritten_literal,
                raw,
                count=1,
            )
            if _n:
                logger.info(
                    "[tampermonkey/script] rewrote API_URL (generic match) -> %s (host=%s)",
                    api_root,
                    request.headers.get("host"),
                )

        # Iter 93 — Also rewrite `@updateURL`/`@downloadURL` in the metadata
        # block so Tampermonkey's auto-update actually points at the host
        # serving the script — otherwise TM periodically fetches the stale
        # elitepotradingbot.com URL, fails, and logs a warning.
        # Iter 95: broadened regex to match ANY host (including fresh
        # rebuilds that ship with a different placeholder).
        script_endpoint = f"{api_root}/tampermonkey/script"
        import re
        raw = re.sub(
            r"(//\s*@updateURL\s+)https?://[^\s\n]+/api/tampermonkey/script",
            f"\\1{script_endpoint}",
            raw,
        )
        raw = re.sub(
            r"(//\s*@downloadURL\s+)https?://[^\s\n]+/api/tampermonkey/script",
            f"\\1{script_endpoint}",
            raw,
        )
        # Also ensure the host serving the script is in the @connect allow-list
        # so GM_xmlhttpRequest doesn't get blocked in strict TM installs.
        try:
            from urllib.parse import urlparse
            api_host = urlparse(api_root).netloc.split(":")[0]
            if api_host and f"@connect      {api_host}" not in raw and f"@connect {api_host}" not in raw:
                # Insert right after the last existing @connect line
                raw = re.sub(
                    r"(//\s*@connect\s+[^\n]+\n)(?!//\s*@connect)",
                    lambda m: f"{m.group(1)}// @connect      {api_host}\n",
                    raw, count=1,
                )
        except Exception as _connect_err:
            logger.debug("[tampermonkey/script] @connect append skipped: %s", _connect_err)

        # Iter 93c — Append a runtime version-badge injector. Reads
        # GM_info.script.version (authoritative — reflects the *actually
        # installed* userscript version, not any stale BOT_VERSION constant
        # baked into the webpack bundle) and stamps a small badge into the
        # panel header once it renders. If the badge already exists it's
        # updated in place — safe against SPA re-renders.
        raw += _VERSION_BADGE_INJECTOR

        return Response(
            content=raw,
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Content-Disposition": (
                    'inline; filename="pocket-option-auto-trader.user.js"'
                ),
                "X-EPB-Api-Root": api_root,
            },
        )
    raise HTTPException(
        status_code=404,
        detail="Compiled userscript not found on disk — rebuild TM bundle.",
    )


# ---------------------------------------------------------------------------
# Iter 93c — Version badge injector
# ---------------------------------------------------------------------------
# Appended at the very end of the served script (outside the webpack IIFE).
# By that point the panel bootstrap has already run so we defer with a
# MutationObserver + polling fallback until the header element exists.
_VERSION_BADGE_INJECTOR = r"""
;(function () {
  // Reads the running version from GM_info (Tampermonkey / Violentmonkey /
  // Greasemonkey all populate this). Falls back to the @version literal at
  // the top of the file if for some reason GM_info isn't available.
  var version = "";
  try {
    if (typeof GM_info !== "undefined" && GM_info && GM_info.script && GM_info.script.version) {
      version = String(GM_info.script.version);
    }
  } catch (_e) {}
  if (!version) return;  // no reliable source — skip silently

  var BADGE_ID = "epb-version-badge";
  var STYLE_ID = "epb-version-badge-style";

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = [
      "." + BADGE_ID + "{",
      "  display:inline-flex;align-items:center;gap:4px;",
      "  margin-left:8px;padding:2px 8px;",
      "  font-size:10px;font-weight:600;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;",
      "  letter-spacing:.02em;",
      "  color:#67e8f9;background:rgba(6,182,212,0.14);",
      "  border:1px solid rgba(103,232,249,0.35);",
      "  border-radius:9999px;",
      "  text-shadow:0 0 6px rgba(103,232,249,0.55);",
      "  box-shadow:0 0 12px rgba(103,232,249,0.18) inset;",
      "  vertical-align:middle;line-height:1;",
      "  cursor:default;user-select:none;",
      "}",
      "." + BADGE_ID + "::before{",
      "  content:'●';color:#4ade80;font-size:8px;",
      "  text-shadow:0 0 4px #4ade80;",
      "}",
    ].join("");
    (document.head || document.documentElement).appendChild(s);
  }

  function upsertBadge() {
    ensureStyle();
    // Find a suitable host element inside the panel header — try a couple of
    // known selectors emitted by the compiled bundle.
    var host = document.querySelector(
      "[id$='header'] [class$='title'], [class$='header'] [class$='title'], " +
      "[data-testid='panel-content'] [class*='title'], " +
      "[data-testid='panel-content'] h1, [data-testid='panel-content'] h2"
    );
    if (!host) return false;
    var existing = host.querySelector("." + BADGE_ID) ||
                   document.getElementById(BADGE_ID);
    if (existing) {
      existing.textContent = "v" + version;
      existing.title = "Userscript version " + version + " · click to check for updates";
      return true;
    }
    var badge = document.createElement("span");
    badge.id = BADGE_ID;
    badge.className = BADGE_ID;
    badge.textContent = "v" + version;
    badge.title = "Userscript version " + version + " · click to check for updates";
    badge.addEventListener("click", function (ev) {
      ev.stopPropagation();
      // Give the user a fast path to the update URL
      try {
        window.open(
          (window.epb_api_url || "") + "/tampermonkey/script",
          "_blank",
        );
      } catch (_e) {}
    });
    host.appendChild(badge);
    return true;
  }

  // Try immediately, then via MutationObserver, then poll for up to 30s.
  if (upsertBadge()) return;

  var observer = new MutationObserver(function () {
    if (upsertBadge()) observer.disconnect();
  });
  try {
    observer.observe(document.body || document.documentElement, {
      childList: true, subtree: true,
    });
  } catch (_e) {}

  var attempts = 0;
  var iv = setInterval(function () {
    attempts++;
    if (upsertBadge() || attempts > 60) {
      clearInterval(iv);
      try { observer.disconnect(); } catch (_e) {}
    }
  }, 500);
})();
"""


# ---------------------------------------------------------------------------
# GET /api/settings/chart  →  user's current chart type + timeframe
# ---------------------------------------------------------------------------
# The TM panel polls this on init to sync its "chart-mode" indicator with what
# the user has set in the React dashboard. Falls back to sensible defaults if
# no config doc exists yet.

VALID_CHART_TYPES = {
    "japanese_candles",
    "heikin_ashi",
    "line",
    "bar",
    "area",
}


@router.get("/settings/chart")
async def get_chart_settings(user_id: str = "default_user"):
    """Return current chart type + timeframe for the panel indicator."""
    try:
        db = _get_db()
        cfg = await db.trading_configurations.find_one({"user_id": user_id})

        chart_type = "japanese_candles"
        chart_timeframe = "30s"
        if cfg:
            ct = cfg.get("chart_type")
            if isinstance(ct, str) and ct in VALID_CHART_TYPES:
                chart_type = ct
            tf = cfg.get("chart_timeframe")
            if isinstance(tf, str) and tf:
                chart_timeframe = tf

        return {
            "success": True,
            "chart_type": chart_type,
            "chart_timeframe": chart_timeframe,
        }
    except Exception as exc:
        logger.error("[settings/chart] read failed: %s", exc)
        # Return defaults so the TM panel keeps working even on DB error
        return {
            "success": True,
            "chart_type": "japanese_candles",
            "chart_timeframe": "30s",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# POST /api/diag/ws-frames  →  Websocket frame diagnostics sink
# ---------------------------------------------------------------------------
# The TM script batches PO websocket frames and posts them here in chunks of
# ~40 at a time. We persist a small rolling buffer for offline debugging and
# capp at 2 000 rows/day so it can't blow up Mongo.

_MAX_FRAMES_PER_REQUEST = 200
_ROLLING_LIMIT = 2_000


@router.post("/diag/ws-frames")
async def diag_ws_frames(payload: dict = Body(default={})):
    """Fire-and-forget sink for TM WS frame batches."""
    try:
        frames = payload.get("frames") or []
        if not isinstance(frames, list):
            frames = []
        # Cap incoming batch so a bad client can't nuke us
        frames = frames[:_MAX_FRAMES_PER_REQUEST]
        meta = payload.get("meta") or {}
        if not isinstance(meta, dict):
            meta = {}

        db = _get_db()
        doc = {
            "frames": frames,
            "meta": meta,
            "count": len(frames),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await db.tm_ws_frame_diagnostics.insert_one(doc)

        # Keep rolling buffer bounded
        try:
            total = await db.tm_ws_frame_diagnostics.count_documents({})
            if total > _ROLLING_LIMIT:
                extra = total - _ROLLING_LIMIT
                cursor = db.tm_ws_frame_diagnostics.find({}, {"_id": 1}).sort(
                    "ts", 1
                ).limit(extra)
                ids = [d["_id"] async for d in cursor]
                if ids:
                    await db.tm_ws_frame_diagnostics.delete_many(
                        {"_id": {"$in": ids}}
                    )
        except Exception:
            # Trimming errors must never poison the ack
            pass

        return {"success": True, "stored": len(frames)}
    except Exception as exc:
        logger.warning("[diag/ws-frames] store failed: %s", exc)
        return JSONResponse(
            status_code=200,
            content={"success": False, "error": str(exc)},
        )


@router.get("/diag/ws-frames")
async def diag_ws_frames_recent(limit: int = 20):
    """List recent WS frame batches — handy for offline debugging."""
    try:
        db = _get_db()
        limit = max(1, min(200, int(limit)))
        cursor = (
            db.tm_ws_frame_diagnostics.find({}, {"_id": 0, "frames": 0})
            .sort("ts", -1)
            .limit(limit)
        )
        rows = [d async for d in cursor]
        return {"success": True, "count": len(rows), "batches": rows}
    except Exception as exc:
        logger.warning("[diag/ws-frames] list failed: %s", exc)
        return {"success": False, "error": str(exc), "batches": []}
