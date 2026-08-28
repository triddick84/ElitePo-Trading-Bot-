"""
Telegram Mini App (TMA) routes.

Implements:
  - initData HMAC-SHA256 validation per the official Telegram spec
    (https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)
  - JWT session issuance for the Mini App
  - MongoDB upserts into `tma_users`
  - 4-step onboarding state machine: PO Signup -> KYC -> Package -> Access
  - KYC screenshot upload (local filesystem storage)
  - Minimal admin review queue

All routes are prefixed with `/tma/` and mounted under the `/api` router in
server.py (final base path: `/api/tma/...`).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl

import jwt
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from routes import db

logger = logging.getLogger("server.tma")

router = APIRouter(prefix="/tma", tags=["tma"])

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TMA_JWT_SECRET = os.environ.get("TMA_JWT_SECRET", "")
TMA_JWT_ALGORITHM = "HS256"
TMA_JWT_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days
TMA_INIT_DATA_MAX_AGE = 24 * 60 * 60    # 24 hours — cursor for stale replay
TMA_DEV_MODE = os.environ.get("TMA_DEV_MODE", "false").lower() == "true"

# Comma-separated Telegram user ids allowed to hit /tma/admin/*
_ADMIN_IDS_RAW = os.environ.get("TMA_ADMIN_TELEGRAM_IDS", "")
TMA_ADMIN_TELEGRAM_IDS = {
    int(x.strip()) for x in _ADMIN_IDS_RAW.split(",") if x.strip().isdigit()
}

PO_AFFILIATE_URL = os.environ.get(
    "PO_AFFILIATE_URL",
    "https://pocketoption.com/en/register/",
)

UPLOAD_ROOT = Path("/app/backend/uploads/tma_kyc")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# Onboarding step ids
STEP_PO = "po_signup"
STEP_KYC = "kyc"
STEP_PACKAGE = "package"
STEP_ACCESS = "access"
ONBOARDING_STEPS = [STEP_PO, STEP_KYC, STEP_PACKAGE, STEP_ACCESS]

# Static package catalog (source of truth until Stripe wiring lands in Phase B)
PACKAGES: List[Dict[str, Any]] = [
    {
        "id": "basic_weekly",
        "name": "Basic",
        "cadence": "weekly",
        "price_usd": 29,
        "description": "Access to the core signal engine, 5s + 15s strategies, Telegram alerts.",
        "features": ["Core signals", "5s + 15s strategies", "Telegram alerts"],
    },
    {
        "id": "pro_weekly",
        "name": "Pro",
        "cadence": "weekly",
        "price_usd": 49,
        "description": "Everything in Basic plus 30s / 1m strategies and auto-invert engine.",
        "features": ["All 5s→1m strategies", "Auto-invert engine", "Priority alerts"],
        "highlight": True,
    },
    {
        "id": "pro_monthly",
        "name": "Pro (Monthly)",
        "cadence": "monthly",
        "price_usd": 129,
        "description": "Monthly Pro plan — save vs weekly billing.",
        "features": ["All 5s→1m strategies", "Auto-invert engine", "Priority alerts"],
    },
    {
        "id": "elite_monthly",
        "name": "Elite",
        "cadence": "monthly",
        "price_usd": 199,
        "description": "Everything in Pro + BETA strategies, longer expiries, and ML-tuned auto-trades.",
        "features": [
            "All strategies (BETA included)",
            "ML-tuned auto-trades",
            "1:1 onboarding call",
        ],
    },
    {
        "id": "elite_annual",
        "name": "Elite (Annual)",
        "cadence": "annual",
        "price_usd": 1899,
        "description": "Best value — 12 months of Elite at ~$158/mo.",
        "features": ["All Elite features", "12 months", "Save ~20%"],
    },
]

# ---------------------------------------------------------------------------
# initData validation
# ---------------------------------------------------------------------------

def _telegram_secret_key(bot_token: str) -> bytes:
    """
    Per Telegram's spec:
      secret_key = HMAC_SHA256(key='WebAppData', msg=bot_token)
    """
    return hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()


def validate_init_data(init_data: str, *, bot_token: str, max_age_seconds: int = TMA_INIT_DATA_MAX_AGE) -> Dict[str, Any]:
    """
    Validate a Telegram Mini App initData string.

    Returns the parsed dict (with `user` decoded) on success.
    Raises HTTPException(401) on any validation failure.
    """
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")
    if not bot_token:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN not configured")

    # parse_qsl preserves the URL-decoded values (which is what the spec expects).
    parsed_pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    parsed = dict(parsed_pairs)

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="initData missing hash")

    # Build the data_check_string: k=v joined by \n, sorted alphabetically by k.
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

    secret_key = _telegram_secret_key(bot_token)
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=401, detail="initData signature invalid")

    # Reject stale initData
    auth_date_raw = parsed.get("auth_date")
    if auth_date_raw:
        try:
            auth_ts = int(auth_date_raw)
            age = time.time() - auth_ts
            if age > max_age_seconds:
                raise HTTPException(status_code=401, detail="initData expired")
        except ValueError:
            raise HTTPException(status_code=401, detail="initData auth_date malformed")

    # Decode the nested user JSON
    user_raw = parsed.get("user")
    if user_raw:
        try:
            parsed["user"] = json.loads(user_raw)
        except json.JSONDecodeError:
            raise HTTPException(status_code=401, detail="initData user field malformed")

    return parsed


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _issue_jwt(*, telegram_user_id: int, is_admin: bool) -> str:
    if not TMA_JWT_SECRET:
        raise HTTPException(status_code=500, detail="TMA_JWT_SECRET not configured")
    now = int(time.time())
    payload = {
        "sub": str(telegram_user_id),
        "tid": telegram_user_id,
        "adm": bool(is_admin),
        "iat": now,
        "exp": now + TMA_JWT_TTL_SECONDS,
        "iss": "tma-elitepo",
    }
    return jwt.encode(payload, TMA_JWT_SECRET, algorithm=TMA_JWT_ALGORITHM)


def _decode_jwt(token: str) -> Dict[str, Any]:
    if not TMA_JWT_SECRET:
        raise HTTPException(status_code=500, detail="TMA_JWT_SECRET not configured")
    try:
        return jwt.decode(token, TMA_JWT_SECRET, algorithms=[TMA_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="TMA session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="TMA session invalid")


async def current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """FastAPI dependency: parse Bearer token, fetch user from mongo."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    claims = _decode_jwt(token)
    telegram_user_id = claims.get("tid")
    if not telegram_user_id:
        raise HTTPException(status_code=401, detail="Malformed session")
    user = await db.tma_users.find_one({"telegram_user_id": int(telegram_user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="TMA user not found")
    user["_id"] = str(user["_id"])
    user["is_admin"] = bool(claims.get("adm", False))
    return user


async def require_admin(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class TmaAuthRequest(BaseModel):
    init_data: str = Field(..., description="Raw initData string from Telegram.WebApp")
    referral_code: Optional[str] = Field(default=None, max_length=64)


class OnboardingUpdateRequest(BaseModel):
    step: str
    value: Optional[str] = None  # e.g. selected package id


class KycReviewRequest(BaseModel):
    action: str  # "approve" | "reject"
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth / bootstrap
# ---------------------------------------------------------------------------

@router.post("/auth")
async def tma_auth(payload: TmaAuthRequest) -> Dict[str, Any]:
    """
    Validate initData, upsert the tma_users record, return a JWT.
    """
    # Dev bypass: allow synthetic initData when TMA_DEV_MODE=true and the string
    # begins with 'dev:'. Format: dev:<telegram_user_id>:<username>
    if TMA_DEV_MODE and payload.init_data.startswith("dev:"):
        parts = payload.init_data.split(":", 2)
        telegram_user_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 999_000_001
        username = parts[2] if len(parts) > 2 else "dev_user"
        tg_user = {"id": telegram_user_id, "username": username, "first_name": "Dev"}
    else:
        parsed = validate_init_data(payload.init_data, bot_token=TELEGRAM_BOT_TOKEN)
        tg_user = parsed.get("user") or {}
        if not tg_user or not tg_user.get("id"):
            raise HTTPException(status_code=401, detail="initData missing user")
        telegram_user_id = int(tg_user["id"])
        username = tg_user.get("username") or f"tg_{telegram_user_id}"

    now = datetime.now(timezone.utc).isoformat()
    is_admin = telegram_user_id in TMA_ADMIN_TELEGRAM_IDS

    # Upsert user
    existing = await db.tma_users.find_one({"telegram_user_id": telegram_user_id})
    if existing:
        update: Dict[str, Any] = {
            "username": username,
            "first_name": tg_user.get("first_name"),
            "last_name": tg_user.get("last_name"),
            "language_code": tg_user.get("language_code"),
            "updated_at": now,
            "role": "admin" if is_admin else existing.get("role", "user"),
        }
        # Only accept referral on first application (never override)
        if payload.referral_code and not existing.get("referred_by"):
            update["referred_by"] = payload.referral_code
        await db.tma_users.update_one(
            {"telegram_user_id": telegram_user_id},
            {"$set": update},
        )
        user_id = existing["id"]
    else:
        user_id = str(uuid.uuid4())
        await db.tma_users.insert_one({
            "id": user_id,
            "telegram_user_id": telegram_user_id,
            "username": username,
            "first_name": tg_user.get("first_name"),
            "last_name": tg_user.get("last_name"),
            "language_code": tg_user.get("language_code"),
            "role": "admin" if is_admin else "user",
            "referral_code": secrets.token_urlsafe(6),
            "referred_by": payload.referral_code,
            "onboarding": {
                STEP_PO: {"completed": False, "at": None},
                STEP_KYC: {"completed": False, "at": None},
                STEP_PACKAGE: {"completed": False, "at": None, "package_id": None},
                STEP_ACCESS: {"completed": False, "at": None},
            },
            "access_granted": False,
            "kyc_status": "not_submitted",
            "created_at": now,
            "updated_at": now,
        })

    token = _issue_jwt(telegram_user_id=telegram_user_id, is_admin=is_admin)
    user_doc = await db.tma_users.find_one({"telegram_user_id": telegram_user_id})
    return {
        "success": True,
        "token": token,
        "user": _public_user(user_doc),
        "affiliate_url": PO_AFFILIATE_URL,
    }


def _public_user(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return {}
    return {
        "id": doc.get("id"),
        "telegram_user_id": doc.get("telegram_user_id"),
        "username": doc.get("username"),
        "first_name": doc.get("first_name"),
        "role": doc.get("role", "user"),
        "referral_code": doc.get("referral_code"),
        "referred_by": doc.get("referred_by"),
        "onboarding": doc.get("onboarding", {}),
        "access_granted": bool(doc.get("access_granted")),
        "kyc_status": doc.get("kyc_status", "not_submitted"),
    }


@router.get("/me")
async def tma_me(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return {"success": True, "user": _public_user(user)}


@router.get("/packages")
async def tma_packages() -> Dict[str, Any]:
    return {"success": True, "packages": PACKAGES}


@router.get("/onboarding/state")
async def tma_onboarding_state(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    onboarding = user.get("onboarding") or {}
    # Compute the next incomplete step
    next_step = STEP_ACCESS
    for step in ONBOARDING_STEPS:
        if not (onboarding.get(step) or {}).get("completed"):
            next_step = step
            break
    return {
        "success": True,
        "steps": ONBOARDING_STEPS,
        "onboarding": onboarding,
        "next_step": next_step,
        "affiliate_url": PO_AFFILIATE_URL,
        "kyc_status": user.get("kyc_status", "not_submitted"),
        "access_granted": bool(user.get("access_granted")),
    }


@router.post("/onboarding/update")
async def tma_onboarding_update(
    payload: OnboardingUpdateRequest,
    user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    """
    Mark an onboarding step as completed. Currently used for the PO signup
    self-attestation step (Step 1) and package selection (Step 3, pre-payment).

    Step 4 (access) is granted server-side only — once KYC is approved
    AND a package is on file — never directly via this endpoint.
    """
    if payload.step not in {STEP_PO, STEP_PACKAGE}:
        raise HTTPException(status_code=400, detail=f"Cannot self-complete step '{payload.step}'")

    now = datetime.now(timezone.utc).isoformat()
    set_doc: Dict[str, Any] = {
        f"onboarding.{payload.step}.completed": True,
        f"onboarding.{payload.step}.at": now,
        "updated_at": now,
    }
    if payload.step == STEP_PACKAGE:
        if not payload.value:
            raise HTTPException(status_code=400, detail="Package id required")
        if payload.value not in {p["id"] for p in PACKAGES}:
            raise HTTPException(status_code=400, detail="Unknown package id")
        set_doc[f"onboarding.{STEP_PACKAGE}.package_id"] = payload.value

    await db.tma_users.update_one(
        {"telegram_user_id": user["telegram_user_id"]},
        {"$set": set_doc},
    )
    fresh = await db.tma_users.find_one({"telegram_user_id": user["telegram_user_id"]})
    return {"success": True, "user": _public_user(fresh)}


# ---------------------------------------------------------------------------
# KYC
# ---------------------------------------------------------------------------

_ALLOWED_KYC_EXT = {"png", "jpg", "jpeg", "webp", "heic", "heif"}
_MAX_KYC_BYTES = 8 * 1024 * 1024  # 8 MB


@router.post("/kyc/upload")
async def tma_kyc_upload(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_KYC_EXT:
        raise HTTPException(status_code=400, detail=f"Only {sorted(_ALLOWED_KYC_EXT)} allowed")

    # Stream to disk with a size guard
    kyc_id = str(uuid.uuid4())
    dest_dir = UPLOAD_ROOT / str(user["telegram_user_id"])
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{kyc_id}.{ext}"

    total = 0
    with dest.open("wb") as fh:  # noqa: E501 (pre-existing: KYC storage — deferred migration to Emergent object storage; local pod-only)
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_KYC_BYTES:
                fh.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large (max 8 MB)")
            fh.write(chunk)

    now = datetime.now(timezone.utc).isoformat()
    await db.tma_kyc.insert_one({
        "id": kyc_id,
        "user_id": user["id"],
        "telegram_user_id": user["telegram_user_id"],
        "status": "pending",
        "screenshot_path": str(dest),
        "file_size": total,
        "content_type": file.content_type,
        "original_filename": file.filename,
        "submitted_at": now,
        "reviewed_at": None,
        "reviewed_by": None,
        "review_reason": None,
    })
    await db.tma_users.update_one(
        {"telegram_user_id": user["telegram_user_id"]},
        {"$set": {
            "kyc_status": "pending",
            "kyc_submission_id": kyc_id,
            "updated_at": now,
        }},
    )
    return {"success": True, "kyc_id": kyc_id, "status": "pending"}


@router.get("/kyc/status")
async def tma_kyc_status(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    latest = await db.tma_kyc.find_one(
        {"telegram_user_id": user["telegram_user_id"]},
        sort=[("submitted_at", -1)],
    )
    return {
        "success": True,
        "status": user.get("kyc_status", "not_submitted"),
        "submission": _public_kyc(latest) if latest else None,
    }


def _public_kyc(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id"),
        "status": doc.get("status"),
        "submitted_at": doc.get("submitted_at"),
        "reviewed_at": doc.get("reviewed_at"),
        "review_reason": doc.get("review_reason"),
        "telegram_user_id": doc.get("telegram_user_id"),
    }


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@router.get("/admin/kyc/queue")
async def tma_admin_kyc_queue(
    status_filter: str = "pending",
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    q: Dict[str, Any] = {} if status_filter == "all" else {"status": status_filter}
    docs = await db.tma_kyc.find(q).sort("submitted_at", -1).to_list(length=200)
    return {"success": True, "items": [_public_kyc(d) for d in docs]}


@router.get("/admin/kyc/{kyc_id}/image")
async def tma_admin_kyc_image(
    kyc_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    doc = await db.tma_kyc.find_one({"id": kyc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="KYC not found")
    path = Path(doc["screenshot_path"])
    if not path.exists():
        raise HTTPException(status_code=410, detail="Screenshot missing on disk")
    return FileResponse(path)


@router.post("/admin/kyc/{kyc_id}/review")
async def tma_admin_kyc_review(
    kyc_id: str,
    payload: KycReviewRequest,
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    if payload.action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="action must be approve|reject")

    doc = await db.tma_kyc.find_one({"id": kyc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="KYC not found")

    new_status = "approved" if payload.action == "approve" else "rejected"
    now = datetime.now(timezone.utc).isoformat()

    await db.tma_kyc.update_one(
        {"id": kyc_id},
        {"$set": {
            "status": new_status,
            "reviewed_at": now,
            "reviewed_by": admin["telegram_user_id"],
            "review_reason": payload.reason,
        }},
    )

    # Reflect status on the user + step
    user_update: Dict[str, Any] = {
        "kyc_status": new_status,
        "updated_at": now,
    }
    if new_status == "approved":
        user_update[f"onboarding.{STEP_KYC}.completed"] = True
        user_update[f"onboarding.{STEP_KYC}.at"] = now
    await db.tma_users.update_one(
        {"telegram_user_id": doc["telegram_user_id"]},
        {"$set": user_update},
    )

    # Auto-grant access when both KYC approved AND package chosen
    if new_status == "approved":
        user_doc = await db.tma_users.find_one({"telegram_user_id": doc["telegram_user_id"]})
        onboarding = (user_doc or {}).get("onboarding", {})
        if (onboarding.get(STEP_PACKAGE) or {}).get("completed"):
            await db.tma_users.update_one(
                {"telegram_user_id": doc["telegram_user_id"]},
                {"$set": {
                    "access_granted": True,
                    f"onboarding.{STEP_ACCESS}.completed": True,
                    f"onboarding.{STEP_ACCESS}.at": now,
                }},
            )

    fresh = await db.tma_kyc.find_one({"id": kyc_id})
    return {"success": True, "kyc": _public_kyc(fresh)}


@router.get("/admin/users")
async def tma_admin_users(admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    docs = await db.tma_users.find({}).sort("created_at", -1).to_list(length=500)
    return {"success": True, "items": [_public_user(d) for d in docs]}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health")
async def tma_health() -> Dict[str, Any]:
    return {
        "success": True,
        "dev_mode": TMA_DEV_MODE,
        "bot_configured": bool(TELEGRAM_BOT_TOKEN),
        "jwt_configured": bool(TMA_JWT_SECRET),
        "admin_ids": sorted(TMA_ADMIN_TELEGRAM_IDS),
        "affiliate_url": PO_AFFILIATE_URL,
    }
