"""
Sentiment Service (Iter 62, May 27 2026)
========================================

Pulls free forex/macro news headlines, scores per-currency sentiment with the
Emergent LLM (Claude Sonnet 4.6), and caches the result in MongoDB.

Used as a soft confidence modifier in `routes/signals.py force_generate_v2`:
  - if signal direction aligns with the pair's net sentiment, +up_to_3% confidence
  - if it conflicts, -up_to_3% confidence (and a warning is added to reasoning)

Refresh policy:
  - Background loop every SENTIMENT_REFRESH_MINUTES (default 15)
  - Manual trigger via /api/sentiment/refresh
  - Cached score is "fresh" for `SENTIMENT_FRESH_MINUTES` (default 30)

Currencies covered: USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD, XAU, BTC
"""
from __future__ import annotations
import os
import json
import logging
import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

import feedparser
from pymongo import MongoClient, DESCENDING

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "gpt_signal_bot")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]
sentiment_scores_col = _db["sentiment_scores"]
sentiment_runs_col = _db["sentiment_runs"]
sentiment_scores_col.create_index([("ts", DESCENDING)])
sentiment_runs_col.create_index([("ts", DESCENDING)])

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "XAU", "BTC"]

# Free RSS sources — no auth needed
RSS_SOURCES = [
    "https://www.forexlive.com/feed/news",
    "https://www.fxstreet.com/rss/news",
    "https://www.investing.com/rss/news_25.rss",      # forex news
    "https://www.investing.com/rss/news_301.rss",     # commodities
    "https://www.investing.com/rss/news_285.rss",     # cryptocurrency
]

MAX_HEADLINES_PER_FEED = 8
MAX_TOTAL_HEADLINES = 25

SENTIMENT_REFRESH_MINUTES = int(os.environ.get("SENTIMENT_REFRESH_MINUTES", "15"))
SENTIMENT_FRESH_MINUTES = int(os.environ.get("SENTIMENT_FRESH_MINUTES", "30"))


# --------------------------------------------------------------------------- #
# RSS fetcher
# --------------------------------------------------------------------------- #
def _fetch_headlines() -> List[Dict[str, str]]:
    """Pull recent headlines from the configured RSS sources."""
    out: List[Dict[str, str]] = []
    for url in RSS_SOURCES:
        try:
            parsed = feedparser.parse(url)
            for entry in (parsed.entries or [])[:MAX_HEADLINES_PER_FEED]:
                title = (entry.get("title") or "").strip()
                summary = (entry.get("summary") or "").strip()
                # Strip HTML tags from summary
                summary = re.sub(r"<[^>]+>", "", summary)[:200]
                if title:
                    out.append({
                        "title": title,
                        "summary": summary,
                        "source": url.split("/")[2],
                    })
        except Exception as e:
            logger.warning(f"[sentiment] RSS fetch failed {url}: {e}")
    # De-dupe by title
    seen = set()
    deduped = []
    for h in out:
        if h["title"] not in seen:
            seen.add(h["title"])
            deduped.append(h)
        if len(deduped) >= MAX_TOTAL_HEADLINES:
            break
    return deduped


# --------------------------------------------------------------------------- #
# LLM scorer
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """You are a forex/macro sentiment analyst. Given a list of recent market headlines, output a JSON object scoring each major currency from -1.0 (strongly bearish) to +1.0 (strongly bullish), plus a confidence (0..1) and a one-line reason.

Strict rules:
1. Output JSON only — no preamble, no markdown fences, no commentary.
2. Schema:
   {
     "scores": {
       "USD": {"score": -1.0..+1.0, "confidence": 0..1, "reason": "..."},
       "EUR": {...}, "GBP": {...}, "JPY": {...}, "AUD": {...}, "CAD": {...},
       "CHF": {...}, "NZD": {...}, "XAU": {...}, "BTC": {...}
     },
     "summary": "one-sentence overall market tone"
   }
3. Score every currency in the schema (use 0.0 with low confidence if no headline touches it).
4. XAU = gold; treat as risk-off proxy. BTC = crypto risk appetite.
5. If a headline is ambiguous, score conservatively (closer to 0).
"""


async def _score_with_llm(headlines: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """Send headlines to Emergent LLM (Claude Sonnet 4.6) and parse a JSON response."""
    if not EMERGENT_LLM_KEY:
        logger.warning("[sentiment] EMERGENT_LLM_KEY missing — skipping LLM scoring")
        return None
    if not headlines:
        return None

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        logger.error(f"[sentiment] emergentintegrations import failed: {e}")
        return None

    headlines_text = "\n".join(
        f"{i+1}. [{h['source']}] {h['title']}" + (f" — {h['summary']}" if h.get('summary') else "")
        for i, h in enumerate(headlines)
    )

    session_id = f"sentiment-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-sonnet-4-6")

    user_msg = UserMessage(text=f"Headlines:\n{headlines_text}\n\nRespond with the JSON object only.")

    try:
        resp = await chat.send_message(user_msg)
    except Exception as e:
        msg = str(e).lower()
        if "budget" in msg or "exceeded" in msg:
            logger.error(
                "[sentiment] LLM budget exceeded — top up the Emergent Universal Key "
                "via Profile → Universal Key → Add Balance"
            )
        else:
            logger.error(f"[sentiment] LLM call failed: {e}")
        return None

    text = str(resp).strip()
    # Strip code fences if any
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Extract first {...} blob
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        logger.warning(f"[sentiment] LLM returned non-JSON: {text[:200]}")
        return None
    try:
        return json.loads(m.group(0))
    except Exception as e:
        logger.warning(f"[sentiment] JSON parse failed: {e} / raw={text[:300]}")
        return None


# --------------------------------------------------------------------------- #
# Public refresh + read
# --------------------------------------------------------------------------- #
async def refresh_sentiment(force: bool = False) -> Dict[str, Any]:
    """Refresh the cached sentiment snapshot. Returns the new doc (or last cached)."""
    latest = sentiment_scores_col.find_one(sort=[("ts", DESCENDING)])
    if (not force) and latest:
        latest_ts = latest["ts"]
        if isinstance(latest_ts, datetime) and latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=timezone.utc)
        age_min = (datetime.now(timezone.utc) - latest_ts).total_seconds() / 60
        if age_min < SENTIMENT_FRESH_MINUTES:
            return _clean(latest)

    headlines = await asyncio.to_thread(_fetch_headlines)
    run_doc = {
        "ts": datetime.now(timezone.utc),
        "headline_count": len(headlines),
        "headlines": headlines[:10],  # store a sample for audit
    }

    if not headlines:
        run_doc["status"] = "no_headlines"
        sentiment_runs_col.insert_one(run_doc)
        return _clean(latest) if latest else {"error": "no_headlines"}

    scored = await _score_with_llm(headlines)
    if not scored or "scores" not in scored:
        run_doc["status"] = "llm_failed"
        sentiment_runs_col.insert_one(run_doc)
        return _clean(latest) if latest else {"error": "llm_failed"}

    # Normalize: clamp scores to [-1, 1], confidence to [0, 1]
    norm: Dict[str, Dict[str, Any]] = {}
    for cur in CURRENCIES:
        entry = (scored.get("scores") or {}).get(cur) or {}
        try:
            s = float(entry.get("score", 0))
        except (TypeError, ValueError):
            s = 0.0
        try:
            c = float(entry.get("confidence", 0))
        except (TypeError, ValueError):
            c = 0.0
        norm[cur] = {
            "score": max(-1.0, min(1.0, s)),
            "confidence": max(0.0, min(1.0, c)),
            "reason": str(entry.get("reason", ""))[:240],
        }

    doc = {
        "ts": datetime.now(timezone.utc),
        "scores": norm,
        "summary": str(scored.get("summary", ""))[:300],
        "headline_count": len(headlines),
    }
    sentiment_scores_col.insert_one(dict(doc))  # copy so caller doesn't see _id
    run_doc["status"] = "ok"
    sentiment_runs_col.insert_one(run_doc)
    logger.info(f"[sentiment] refreshed: {len(headlines)} headlines, summary={doc['summary'][:80]}")
    return _clean(doc)


def get_latest_sentiment() -> Optional[Dict[str, Any]]:
    doc = sentiment_scores_col.find_one(sort=[("ts", DESCENDING)])
    return _clean(doc) if doc else None


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Strip Mongo _id + ISO-format ts for JSON serialization."""
    if not doc:
        return {}
    out = {k: v for k, v in doc.items() if k != "_id"}
    if isinstance(out.get("ts"), datetime):
        ts = out["ts"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        out["ts"] = ts.isoformat()
    return out


# --------------------------------------------------------------------------- #
# Confidence-modifier helper used by signals.py
# --------------------------------------------------------------------------- #
# Map pair → (base_currency, quote_currency). For OTC variants we strip _OTC.
_PAIR_RE = re.compile(r"^([A-Z]{3})_?([A-Z]{3})$")


def get_pair_sentiment_bias(asset: str) -> Optional[Dict[str, Any]]:
    """
    Return a soft directional bias for a given asset, derived from the latest
    cached sentiment snapshot. Returns None when no fresh data is available.

    Output:
      {
        "asset": "EURUSD_OTC",
        "base": "EUR", "quote": "USD",
        "net_score": -1..+1,   # base − quote
        "confidence": 0..1,    # min(base, quote) confidence
        "suggested_direction": "CALL"|"PUT"|"NEUTRAL",
        "ts": iso-string,
      }
    """
    latest = sentiment_scores_col.find_one(sort=[("ts", DESCENDING)])
    if not latest:
        return None
    latest_ts = latest["ts"]
    if isinstance(latest_ts, datetime) and latest_ts.tzinfo is None:
        latest_ts = latest_ts.replace(tzinfo=timezone.utc)
    age_min = (datetime.now(timezone.utc) - latest_ts).total_seconds() / 60
    if age_min > SENTIMENT_FRESH_MINUTES * 2:
        # Too stale to use as a confidence modifier
        return None

    a = (asset or "").upper().replace("OTC", "").replace("_", "").strip()
    if len(a) != 6:
        # Single-asset (XAU, BTC) — treat as base vs USD
        if a in CURRENCIES and a != "USD":
            base, quote = a, "USD"
        else:
            return None
    else:
        base, quote = a[:3], a[3:]

    scores = latest.get("scores") or {}
    b = scores.get(base) or {}
    q = scores.get(quote) or {}
    if not b and not q:
        return None

    b_s = float(b.get("score", 0))
    q_s = float(q.get("score", 0))
    b_c = float(b.get("confidence", 0))
    q_c = float(q.get("confidence", 0))

    net = b_s - q_s        # positive → base stronger → CALL
    conf = min(b_c, q_c)   # require both sides to be confident

    if abs(net) < 0.15 or conf < 0.3:
        direction = "NEUTRAL"
    elif net > 0:
        direction = "CALL"
    else:
        direction = "PUT"

    return {
        "asset": asset,
        "base": base,
        "quote": quote,
        "net_score": round(net, 3),
        "confidence": round(conf, 3),
        "suggested_direction": direction,
        "ts": (latest_ts.isoformat() if isinstance(latest_ts, datetime) else None),
    }


# --------------------------------------------------------------------------- #
# Background loop (started by server.py on startup)
# --------------------------------------------------------------------------- #
_loop_task: Optional[asyncio.Task] = None


async def _refresh_loop():
    logger.info(f"[sentiment] background loop started — refresh every {SENTIMENT_REFRESH_MINUTES} min")
    # Do an immediate refresh so the dashboard isn't empty on first load
    try:
        await refresh_sentiment(force=False)
    except Exception as e:
        logger.error(f"[sentiment] initial refresh failed: {e}")
    while True:
        try:
            await asyncio.sleep(SENTIMENT_REFRESH_MINUTES * 60)
            await refresh_sentiment(force=True)
        except asyncio.CancelledError:
            logger.info("[sentiment] background loop cancelled")
            break
        except Exception as e:
            logger.error(f"[sentiment] refresh loop error: {e}")


def start_background_loop():
    global _loop_task
    if _loop_task and not _loop_task.done():
        return
    _loop_task = asyncio.create_task(_refresh_loop())


def stop_background_loop():
    global _loop_task
    if _loop_task and not _loop_task.done():
        _loop_task.cancel()
        _loop_task = None
