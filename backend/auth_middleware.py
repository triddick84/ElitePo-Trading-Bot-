"""
Authentication Middleware for FastAPI
Provides JWT token validation and role-based access control
"""

import logging
from typing import Optional, List
from functools import wraps
from fastapi import Request, HTTPException
from auth_service import get_auth_service, UserRole

logger = logging.getLogger(__name__)


def get_token_from_request(request: Request) -> Optional[str]:
    """Extract JWT token from request headers"""
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None


async def get_current_user(request: Request, db=None) -> Optional[dict]:
    """Get current user from JWT token"""
    token = get_token_from_request(request)
    if not token:
        return None
    
    auth_service = get_auth_service(db)
    payload = auth_service.verify_token(token)
    
    if not payload:
        return None
    
    return {
        'user_id': payload.get('user_id'),
        'username': payload.get('username'),
        'role': payload.get('role')
    }


def require_auth(roles: List[str] = None):
    """Decorator to require authentication and optionally specific roles"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = await get_current_user(request)
            
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required"
                )
            
            if roles and user.get('role') not in roles:
                raise HTTPException(
                    status_code=403,
                    detail="Insufficient permissions"
                )
            
            # Add user to request state
            request.state.user = user
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def admin_only(func):
    """Decorator to require admin role"""
    return require_auth(roles=[UserRole.ADMIN.value])(func)
