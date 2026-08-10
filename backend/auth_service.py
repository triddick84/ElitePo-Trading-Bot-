"""
JWT Authentication Service with Admin Roles
Provides user registration, login, and role-based access control
"""

import os
import logging
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
import jwt

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', secrets.token_hex(32))
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Default admin credentials from env
DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD', 'admin123')


class UserRole(str, Enum):
    ADMIN = 'admin'
    USER = 'user'
    VIEWER = 'viewer'


class UserStatus(str, Enum):
    """
    Iter 97 — Account approval status.
    New users default to PENDING and can't log in until an admin approves them.
    """
    PENDING = 'pending'
    ACTIVE = 'active'
    REJECTED = 'rejected'
    SUSPENDED = 'suspended'


# Frontend-facing status codes returned in login error payloads.
STATUS_ERROR_CODES = {
    UserStatus.PENDING.value: ('ACCOUNT_PENDING', 'Your account is pending admin approval.'),
    UserStatus.REJECTED.value: ('ACCOUNT_REJECTED', 'Your registration was rejected.'),
    UserStatus.SUSPENDED.value: ('ACCOUNT_SUSPENDED', 'Your account is suspended. Contact an administrator.'),
}


@dataclass
class User:
    id: str
    username: str
    email: str
    password_hash: str
    role: UserRole
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    telegram_chat_id: Optional[str] = None
    settings: Optional[Dict] = None


class AuthService:
    """
    JWT-based Authentication Service
    Handles user registration, login, and token management
    """
    
    def __init__(self, db=None):
        self.db = db
        self.jwt_secret = JWT_SECRET
        self.jwt_algorithm = JWT_ALGORITHM
        self.token_expiration = JWT_EXPIRATION_HOURS
    
    def _hash_password(self, password: str) -> str:
        """Hash password using HMAC-SHA256 with salt"""
        salt = secrets.token_hex(16)
        password_hash = hmac.new(salt.encode(), password.encode(), hashlib.sha256).hexdigest()
        return f"hmac:{salt}:{password_hash}"
    
    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash (supports both old SHA256 and new HMAC-SHA256)"""
        try:
            if stored_hash.startswith('hmac:'):
                # New format: hmac:salt:hash
                _, salt, hash_value = stored_hash.split(':')
                password_hash = hmac.new(salt.encode(), password.encode(), hashlib.sha256).hexdigest()
                return hmac.compare_digest(password_hash, hash_value)
            else:
                # Legacy format: salt:hash (plain SHA-256)
                salt, hash_value = stored_hash.split(':')
                password_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
                return hmac.compare_digest(password_hash, hash_value)
        except Exception:
            return False
    
    def _generate_token(self, user_id: str, username: str, role: str) -> str:
        """Generate JWT token"""
        payload = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'exp': datetime.now(timezone.utc) + timedelta(hours=self.token_expiration),
            'iat': datetime.now(timezone.utc)
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    async def register(self, username: str, email: str, password: str, 
                       role: UserRole = UserRole.USER) -> Dict:
        """Register a new user"""
        try:
            if self.db is None:
                return {'success': False, 'error': 'Database not available'}
            
            # Check if user already exists
            existing = await self.db.users.find_one({
                '$or': [
                    {'username': username},
                    {'email': email}
                ]
            })
            
            if existing:
                return {'success': False, 'error': 'Username or email already exists'}
            
            # Validate password
            if len(password) < 6:
                return {'success': False, 'error': 'Password must be at least 6 characters'}
            
            # Create user
            import uuid
            user_id = str(uuid.uuid4())
            # Iter 97 — Admins are auto-approved; regular users start as PENDING.
            initial_status = (
                UserStatus.ACTIVE.value if role == UserRole.ADMIN else UserStatus.PENDING.value
            )
            user_doc = {
                'id': user_id,
                'username': username,
                'email': email,
                'password_hash': self._hash_password(password),
                'role': role.value,
                'status': initial_status,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'is_active': True,
                'telegram_chat_id': None,
                'settings': {
                    'auto_trading_enabled': False,
                    'signal_notifications': True,
                    'risk_level': 'medium'
                }
            }
            
            await self.db.users.insert_one(user_doc)
            
            logger.info(f"User registered: {username} ({role.value}) status={initial_status}")

            # Iter 97 — Regular users must be approved before they can log in.
            # We DO NOT issue a token here for pending users; they'll receive
            # one only when their subsequent login succeeds after approval.
            if initial_status == UserStatus.PENDING.value:
                return {
                    'success': True,
                    'pending': True,
                    'code': 'ACCOUNT_PENDING',
                    'message': (
                        'Registration received. Your account is pending admin '
                        'approval — you will be able to sign in once approved.'
                    ),
                    'user': {
                        'id': user_id,
                        'username': username,
                        'email': email,
                        'role': role.value,
                        'status': initial_status,
                    },
                }

            # Admin/seed path — auto-active, issue token immediately.
            token = self._generate_token(user_id, username, role.value)
            return {
                'success': True,
                'user': {
                    'id': user_id,
                    'username': username,
                    'email': email,
                    'role': role.value,
                    'status': initial_status,
                },
                'token': token
            }
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def login(self, username: str, password: str) -> Dict:
        """Login user and return token"""
        try:
            if self.db is None:
                return {'success': False, 'error': 'Database not available'}
            
            # Find user by username or email
            user = await self.db.users.find_one({
                '$or': [
                    {'username': username},
                    {'email': username}
                ]
            })
            
            if not user:
                return {'success': False, 'error': 'Invalid credentials'}
            
            if not user.get('is_active', True):
                return {'success': False, 'error': 'Account is disabled'}
            
            # Verify password
            if not self._verify_password(password, user['password_hash']):
                return {'success': False, 'error': 'Invalid credentials'}

            # Iter 97 — Status gate. After password verification, refuse to
            # issue a token unless the account is ACTIVE. We default missing
            # status to PENDING (fail-safe) so a lost migration never
            # accidentally grants access.
            status_val = user.get('status', UserStatus.PENDING.value)
            if status_val != UserStatus.ACTIVE.value:
                code, message = STATUS_ERROR_CODES.get(
                    status_val,
                    ('ACCOUNT_INACTIVE', 'Your account is not active.'),
                )
                logger.info(f"Login blocked for {username} — status={status_val}")
                return {
                    'success': False,
                    'code': code,
                    'error': message,
                    'status': status_val,
                }
            
            # Update last login
            await self.db.users.update_one(
                {'id': user['id']},
                {'$set': {'last_login': datetime.now(timezone.utc).isoformat()}}
            )
            
            # Generate token
            token = self._generate_token(user['id'], user['username'], user['role'])
            
            logger.info(f"User logged in: {username}")
            
            return {
                'success': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'role': user['role'],
                    'status': user.get('status', UserStatus.ACTIVE.value),
                    'telegram_chat_id': user.get('telegram_chat_id'),
                    'settings': user.get('settings', {})
                },
                'token': token
            }
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        if self.db is None:
            return None
        
        user = await self.db.users.find_one({'id': user_id}, {'_id': 0, 'password_hash': 0})
        return user
    
    async def update_user(self, user_id: str, updates: Dict) -> Dict:
        """Update user profile"""
        try:
            if self.db is None:
                return {'success': False, 'error': 'Database not available'}
            
            # Remove protected fields
            protected = ['id', 'password_hash', 'created_at']
            for field in protected:
                updates.pop(field, None)
            
            await self.db.users.update_one(
                {'id': user_id},
                {'$set': updates}
            )
            
            return {'success': True, 'message': 'User updated'}
            
        except Exception as e:
            logger.error(f"Update error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def change_password(self, user_id: str, old_password: str, new_password: str) -> Dict:
        """Change user password"""
        try:
            if self.db is None:
                return {'success': False, 'error': 'Database not available'}
            
            user = await self.db.users.find_one({'id': user_id})
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            if not self._verify_password(old_password, user['password_hash']):
                return {'success': False, 'error': 'Current password is incorrect'}
            
            if len(new_password) < 6:
                return {'success': False, 'error': 'Password must be at least 6 characters'}
            
            await self.db.users.update_one(
                {'id': user_id},
                {'$set': {'password_hash': self._hash_password(new_password)}}
            )
            
            return {'success': True, 'message': 'Password changed'}
            
        except Exception as e:
            logger.error(f"Password change error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def list_users(self, admin_only: bool = False) -> List[Dict]:
        """List all users (admin function)"""
        if self.db is None:
            return []
        
        query = {'role': 'admin'} if admin_only else {}
        users = await self.db.users.find(query, {'_id': 0, 'password_hash': 0}).to_list(1000)
        return users
    
    async def set_user_role(self, admin_user_id: str, target_user_id: str, new_role: UserRole) -> Dict:
        """Set user role (admin function)"""
        try:
            if self.db is None:
                return {'success': False, 'error': 'Database not available'}
            
            # Verify admin
            admin = await self.db.users.find_one({'id': admin_user_id})
            if not admin or admin.get('role') != 'admin':
                return {'success': False, 'error': 'Unauthorized'}
            
            await self.db.users.update_one(
                {'id': target_user_id},
                {'$set': {'role': new_role.value}}
            )
            
            return {'success': True, 'message': f'Role updated to {new_role.value}'}
            
        except Exception as e:
            logger.error(f"Set role error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def link_telegram(self, user_id: str, telegram_chat_id: str) -> Dict:
        """Link Telegram chat ID to user account"""
        try:
            if self.db is None:
                return {'success': False, 'error': 'Database not available'}
            
            await self.db.users.update_one(
                {'id': user_id},
                {'$set': {'telegram_chat_id': telegram_chat_id}}
            )
            
            return {'success': True, 'message': 'Telegram linked'}
            
        except Exception as e:
            logger.error(f"Link telegram error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def create_default_admin(self):
        """Create default admin user if none exists"""
        try:
            if self.db is None:
                return
            
            admin = await self.db.users.find_one({'role': 'admin'})
            if not admin:
                result = await self.register(
                    username='admin',
                    email='admin@elitepocket.com',
                    password=DEFAULT_ADMIN_PASSWORD,
                    role=UserRole.ADMIN
                )
                if result['success']:
                    logger.info("Default admin created")
                    
        except Exception as e:
            logger.error(f"Create default admin error: {e}")

    # ------------------------------------------------------------------
    # Iter 97 — Admin approval workflow helpers
    # ------------------------------------------------------------------
    async def grandfather_existing_users(self) -> Dict:
        """
        One-time idempotent migration: any user without a `status` field
        is upgraded to ACTIVE so we don't lock out anyone who existed
        before the admin-approval feature was rolled out.

        Safe to call on every startup — `$exists: False` only matches
        legacy documents and never overwrites explicit statuses.
        """
        if self.db is None:
            return {'grandfathered': 0}
        result = await self.db.users.update_many(
            {'status': {'$exists': False}},
            {'$set': {'status': UserStatus.ACTIVE.value}},
        )
        if result.modified_count:
            logger.info(f"[grandfather] set status=active on {result.modified_count} legacy users")
        return {'grandfathered': result.modified_count}

    async def list_users(self, status_filter: Optional[str] = None, limit: int = 500) -> List[Dict]:
        """List users (optionally filtered by status). Never returns password hashes."""
        if self.db is None:
            return []
        query = {'status': status_filter} if status_filter else {}
        cursor = self.db.users.find(
            query,
            {'_id': 0, 'password_hash': 0},
        ).sort('created_at', -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def set_user_status(self, user_id: str, new_status: str, actor_id: str) -> Dict:
        """
        Change a user's status. Records `<action>_by` + `<action>_at` audit
        fields. Refuses no-op transitions and self-suspension/rejection.
        """
        if self.db is None:
            return {'success': False, 'error': 'Database not available'}
        if new_status not in {s.value for s in UserStatus}:
            return {'success': False, 'error': f'Invalid status: {new_status}'}

        # Fetch target user first — needed for self-lockout + admin-count check
        target = await self.db.users.find_one({'id': user_id})
        if not target:
            return {'success': False, 'error': 'User not found'}

        # Guard: an admin cannot lock themselves out
        if actor_id == user_id and new_status in (UserStatus.REJECTED.value, UserStatus.SUSPENDED.value):
            return {'success': False, 'error': 'You cannot reject or suspend your own account'}

        # Guard: prevent locking out the last active admin
        if (target.get('role') == UserRole.ADMIN.value
                and new_status != UserStatus.ACTIVE.value):
            active_admins = await self.db.users.count_documents({
                'role': UserRole.ADMIN.value,
                'status': UserStatus.ACTIVE.value,
                'id': {'$ne': user_id},
            })
            if active_admins == 0:
                return {'success': False, 'error': 'Cannot deactivate the last active admin'}

        now = datetime.now(timezone.utc).isoformat()
        audit_fields = {
            UserStatus.ACTIVE.value: {'approved_by': actor_id, 'approved_at': now},
            UserStatus.REJECTED.value: {'rejected_by': actor_id, 'rejected_at': now},
            UserStatus.SUSPENDED.value: {'suspended_by': actor_id, 'suspended_at': now},
            UserStatus.PENDING.value: {},  # re-queuing to pending records nothing extra
        }[new_status]

        set_doc = {'status': new_status, **audit_fields}
        result = await self.db.users.update_one({'id': user_id}, {'$set': set_doc})
        if result.matched_count == 0:
            return {'success': False, 'error': 'User not found'}

        updated = await self.db.users.find_one(
            {'id': user_id},
            {'_id': 0, 'password_hash': 0},
        )
        logger.info(f"[status] user={user_id} → {new_status} (by={actor_id})")
        return {'success': True, 'user': updated}

    async def seed_admins_from_env(self):
        """
        Iter 65 — Seed admin accounts from the SEED_ADMINS env var on startup.

        Format:
            SEED_ADMINS="email1:password1[:username1],email2:password2[:username2]"
        Username is optional; if omitted, we derive it from the email local-part.

        Idempotent: `register()` skips users whose email/username already exists,
        so it's safe to call this on every server boot.

        Example:
            SEED_ADMINS="ops@elitepo.com:SuperSecret!9,trader@elitepo.com:Hunter2!"
        """
        import os
        raw = (os.environ.get('SEED_ADMINS') or '').strip()
        if not raw:
            return {'seeded': 0, 'skipped': 0, 'errors': []}
        if self.db is None:
            logger.warning("[seed_admins] DB unavailable, skipping")
            return {'seeded': 0, 'skipped': 0, 'errors': ['db_unavailable']}

        seeded = 0
        skipped = 0
        errors = []
        for entry in (e.strip() for e in raw.split(',') if e.strip()):
            parts = entry.split(':')
            if len(parts) < 2:
                errors.append(f"bad_format:{entry[:40]}")
                continue
            email = parts[0].strip()
            password = parts[1].strip()
            username = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else email.split('@')[0]
            try:
                # First check by email — if the seeded admin exists, ensure role=admin AND status=active
                existing = await self.db.users.find_one({'email': email})
                if existing:
                    update_fields = {}
                    if existing.get('role') != UserRole.ADMIN.value:
                        update_fields['role'] = UserRole.ADMIN.value
                    # Iter 97 — seed admins are ALWAYS force-active. Prevents
                    # the admin-approval feature from ever locking out the
                    # operator running the app.
                    if existing.get('status') != UserStatus.ACTIVE.value:
                        update_fields['status'] = UserStatus.ACTIVE.value
                    if update_fields:
                        await self.db.users.update_one(
                            {'id': existing['id']},
                            {'$set': update_fields}
                        )
                        logger.info(f"[seed_admins] updated existing seed {email}: {update_fields}")
                    skipped += 1
                    continue
                result = await self.register(
                    username=username,
                    email=email,
                    password=password,
                    role=UserRole.ADMIN,
                )
                if result.get('success'):
                    seeded += 1
                    logger.info(f"[seed_admins] created admin {email} (username={username})")
                else:
                    errors.append(f"{email}:{result.get('error')}")
            except Exception as e:
                errors.append(f"{email}:{e}")

        logger.info(f"[seed_admins] done — seeded={seeded} skipped={skipped} errors={len(errors)}")
        return {'seeded': seeded, 'skipped': skipped, 'errors': errors}


# Singleton instance
_auth_service = None

def get_auth_service(db=None) -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService(db)
    elif db is not None:
        _auth_service.db = db
    return _auth_service
