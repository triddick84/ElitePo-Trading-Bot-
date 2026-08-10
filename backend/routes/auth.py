"""Auto-extracted route module from server.py refactoring."""
from fastapi import APIRouter, HTTPException, Query, Request, Body, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import logging
import json
import uuid
import os
import asyncio
import pandas as pd

from routes import db, convert_numpy_types, logger

# Re-use the main api_router — routes are registered via include in server.py
# This module uses a local router that gets included by server.py
router = APIRouter()

from routes.models import UserRegisterRequest, UserLoginRequest, ChangePasswordRequest, UpdateUserRequest, UserRole
import traceback
import hashlib
from auth_service import get_auth_service


@router.post("/auth/register")
async def register_user(request: UserRegisterRequest):
    """
    Register a new user.

    Iter 97 — non-admin registrations default to `status=pending` and do
    NOT receive a JWT. The user must be approved by an admin before
    they can log in.
    """
    auth_service = get_auth_service(db)
    result = await auth_service.register(
        username=request.username,
        email=request.email,
        password=request.password,
        role=UserRole.USER
    )
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    # Pending users: return 202 (accepted, not-yet-active) with a clear
    # message the frontend can surface to the operator.
    if result.get('pending'):
        return JSONResponse(status_code=202, content=result)
    return result



@router.post("/auth/login")
async def login_user(request: UserLoginRequest):
    """
    Login user and return JWT token.

    Iter 97 — after password verification we also check `status`. Non-active
    accounts get a 403 with a stable code (ACCOUNT_PENDING / ACCOUNT_REJECTED
    / ACCOUNT_SUSPENDED) that the frontend uses to render a helpful message.
    """
    auth_service = get_auth_service(db)
    result = await auth_service.login(
        username=request.username,
        password=request.password
    )
    if not result['success']:
        # Status-gated failures return 403 + structured detail. Bad creds
        # remain 401 (keeps callers who look at raw status codes working).
        if result.get('code') in ('ACCOUNT_PENDING', 'ACCOUNT_REJECTED', 'ACCOUNT_SUSPENDED', 'ACCOUNT_INACTIVE'):
            raise HTTPException(
                status_code=403,
                detail={
                    'code': result['code'],
                    'message': result.get('error') or 'Account is not active',
                    'status': result.get('status'),
                },
            )
        raise HTTPException(status_code=401, detail=result['error'])
    return result



@router.get("/auth/me")
async def get_current_user(request: Request):
    """Get current user from JWT token"""
    from auth_middleware import get_current_user as get_user
    user = await get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    auth_service = get_auth_service(db)
    full_user = await auth_service.get_user(user['user_id'])
    if not full_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"success": True, "user": full_user}



@router.put("/auth/me")
async def update_current_user(request: Request, updates: UpdateUserRequest):
    """Update current user profile"""
    from auth_middleware import get_current_user as get_user
    user = await get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    auth_service = get_auth_service(db)
    result = await auth_service.update_user(user['user_id'], updates.dict(exclude_none=True))
    return result



@router.post("/auth/change-password")
async def change_password(request: Request, data: ChangePasswordRequest):
    """Change user password"""
    from auth_middleware import get_current_user as get_user
    user = await get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    auth_service = get_auth_service(db)
    result = await auth_service.change_password(
        user['user_id'],
        data.old_password,
        data.new_password
    )
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    return result



@router.get("/auth/users")
async def list_users(request: Request, status: Optional[str] = None):
    """List all users (admin only). Iter 97 — supports ?status=pending|active|rejected|suspended."""
    from auth_middleware import get_current_user as get_user
    user = await get_user(request, db)
    if not user or user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    auth_service = get_auth_service(db)
    users = await auth_service.list_users(status_filter=status)
    return {"success": True, "users": users, "count": len(users), "filter": status}


@router.get("/auth/users/pending")
async def list_pending_users(request: Request):
    """
    Iter 97 — Convenience shortcut: list every user awaiting approval.
    Same as GET /auth/users?status=pending but easier to badge in the UI.
    """
    from auth_middleware import get_current_user as get_user
    user = await get_user(request, db)
    if not user or user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    auth_service = get_auth_service(db)
    pending = await auth_service.list_users(status_filter='pending')
    return {"success": True, "users": pending, "count": len(pending)}


async def _admin_action_on_user(request: Request, user_id: str, new_status: str) -> Dict[str, Any]:
    """
    Iter 97 — Shared helper: verify admin caller, delegate to the audit-safe
    set_user_status in auth_service. Blocks admin self-lockout + last-admin-out.
    """
    from auth_middleware import get_current_user as get_user
    actor = await get_user(request, db)
    if not actor or actor.get('role') != 'admin':
        raise HTTPException(status_code=403, detail={"code": "ADMIN_REQUIRED", "message": "Admin access required"})
    auth_service = get_auth_service(db)
    result = await auth_service.set_user_status(user_id, new_status, actor['user_id'])
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error', 'action failed'))
    return result


@router.post("/auth/users/{user_id}/approve")
async def approve_user(request: Request, user_id: str):
    """Iter 97 — Admin-approves a pending user so they can log in."""
    return await _admin_action_on_user(request, user_id, 'active')


@router.post("/auth/users/{user_id}/reject")
async def reject_user(request: Request, user_id: str):
    """Iter 97 — Admin-rejects a pending registration (user cannot log in)."""
    return await _admin_action_on_user(request, user_id, 'rejected')


@router.post("/auth/users/{user_id}/suspend")
async def suspend_user(request: Request, user_id: str):
    """Iter 97 — Admin-suspends an active user (revokes login access)."""
    return await _admin_action_on_user(request, user_id, 'suspended')



@router.post("/auth/users/{user_id}/role")
async def set_user_role(request: Request, user_id: str, role: str):
    """Set user role (admin only)"""
    from auth_middleware import get_current_user as get_user
    user = await get_user(request, db)
    if not user or user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        new_role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    
    auth_service = get_auth_service(db)
    result = await auth_service.set_user_role(user['user_id'], user_id, new_role)
    return result


