"""
JWT Authentication Service with Admin Roles
Provides user registration, login, and role-based access control
"""

import os
import logging
import hashlib
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


class UserRole(str, Enum):
    ADMIN = 'admin'
    USER = 'user'
    VIEWER = 'viewer'


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
        """Hash password using SHA-256 with salt"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"{salt}:{password_hash}"
    
    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash"""
        try:
            salt, hash_value = stored_hash.split(':')
            password_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
            return password_hash == hash_value
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
            if not self.db:
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
            user_doc = {
                'id': user_id,
                'username': username,
                'email': email,
                'password_hash': self._hash_password(password),
                'role': role.value,
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
            
            # Generate token
            token = self._generate_token(user_id, username, role.value)
            
            logger.info(f"User registered: {username} ({role.value})")
            
            return {
                'success': True,
                'user': {
                    'id': user_id,
                    'username': username,
                    'email': email,
                    'role': role.value
                },
                'token': token
            }
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def login(self, username: str, password: str) -> Dict:
        """Login user and return token"""
        try:
            if not self.db:
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
        if not self.db:
            return None
        
        user = await self.db.users.find_one({'id': user_id}, {'_id': 0, 'password_hash': 0})
        return user
    
    async def update_user(self, user_id: str, updates: Dict) -> Dict:
        """Update user profile"""
        try:
            if not self.db:
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
            if not self.db:
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
        if not self.db:
            return []
        
        query = {'role': 'admin'} if admin_only else {}
        users = await self.db.users.find(query, {'_id': 0, 'password_hash': 0}).to_list(1000)
        return users
    
    async def set_user_role(self, admin_user_id: str, target_user_id: str, new_role: UserRole) -> Dict:
        """Set user role (admin function)"""
        try:
            if not self.db:
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
            if not self.db:
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
                    password='admin123',
                    role=UserRole.ADMIN
                )
                if result['success']:
                    logger.info("Default admin created: admin / admin123")
                    
        except Exception as e:
            logger.error(f"Create default admin error: {e}")


# Singleton instance
_auth_service = None

def get_auth_service(db=None) -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService(db)
    elif db is not None:
        _auth_service.db = db
    return _auth_service
