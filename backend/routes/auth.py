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
    """Register a new user"""
    auth_service = get_auth_service(db)
    result = await auth_service.register(
        username=request.username,
        email=request.email,
        password=request.password,
        role=UserRole.USER
    )
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    return result



@router.post("/auth/login")
async def login_user(request: UserLoginRequest):
    """Login user and return JWT token"""
    auth_service = get_auth_service(db)
    result = await auth_service.login(
        username=request.username,
        password=request.password
    )
    if not result['success']:
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
async def list_users(request: Request):
    """List all users (admin only)"""
    from auth_middleware import get_current_user as get_user
    user = await get_user(request, db)
    if not user or user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    auth_service = get_auth_service(db)
    users = await auth_service.list_users()
    return {"success": True, "users": users}



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


