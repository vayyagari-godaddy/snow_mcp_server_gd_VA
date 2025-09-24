#!/usr/bin/env python3
"""
JWT Authentication Module for ServiceNow MCP Server

Provides JWT token generation, validation, and management functionality
for secure authentication with ServiceNow instances.
"""

import os
#import jwt  # type: ignore
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import jwt

logger = logging.getLogger(__name__)


def _generate_secret_key() -> str:
    """Generate a secure random secret key for JWT signing"""
    import secrets
    return secrets.token_urlsafe(32)


class JWTAuthManager:
    """JWT Authentication Manager for ServiceNow connections"""
    
    def __init__(self):
        """Initialize JWT Auth Manager with configuration from environment"""
        # JWT Configuration from environment variables
        self.secret_key = os.getenv('JWT_CLIENT_SECRET')
        self.algorithm = os.getenv('JWT_ALGORITHM', 'HS256')
        self.token_expiry_hours = int(os.getenv('JWT_EXPIRY_HOURS', '24'))
        self.refresh_token_expiry_days = int(os.getenv('JWT_REFRESH_EXPIRY_DAYS', '30'))
        
        # ServiceNow specific claims
        self.issuer = os.getenv('JWT_ISSUER', 'servicenow-mcp-server')
        self.audience = os.getenv('JWT_AUDIENCE', 'servicenow-api')
        
        # Auto-generate secret key if not provided
        if not self.secret_key:
            self.secret_key = _generate_secret_key()
            logger.warning("JWT_SECRET_KEY not found in environment. Generated a temporary key. "
                          "For production, set JWT_SECRET_KEY environment variable.")

    def generate_token(self, user_info: Dict[str, Any], token_type: str = 'access') -> str:
        """
        Generate JWT token for ServiceNow authentication
        
        Args:
            user_info: Dictionary containing user information (username, instance_url, etc.)
            token_type: Type of token ('access' or 'refresh')
            
        Returns:
            JWT token string
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Set expiration based on token type
            if token_type == 'refresh':
                expiry = now + timedelta(days=self.refresh_token_expiry_days)
            else:
                expiry = now + timedelta(hours=self.token_expiry_hours)
            
            # Build JWT payload
            payload = {
                'iss': self.issuer,  # Issuer
                'aud': self.audience,  # Audience
                'sub': user_info.get('username'),  # Subject (username)
                'iat': now.timestamp(),  # Issued at
                'exp': expiry.timestamp(),  # Expiration time
                'type': token_type,  # Token type
                'snow_instance': user_info.get('instance_url'),  # ServiceNow instance
                'client_id': user_info.get('client_id'),  # OAuth client ID
            }
            
            # Generate and return JWT token
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            logger.info(f"Generated {token_type} JWT token for user: {user_info.get('username')}")
            return token
            
        except Exception as e:
            logger.error(f"Error generating JWT token: {str(e)}")
            raise Exception(f"Failed to generate JWT token: {str(e)}")
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token and return payload
        
        Args:
            token: JWT token string
            
        Returns:
            Dictionary containing token payload if valid
            
        Raises:
            Exception if token is invalid or expired
        """
        try:
            # Decode and validate token
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer
            )
            
            # Check if token is expired
            exp_timestamp = payload.get('exp')
            if exp_timestamp and datetime.now(timezone.utc).timestamp() > exp_timestamp:
                raise jwt.ExpiredSignatureError("Token has expired")
            
            logger.debug(f"JWT token validated successfully for user: {payload.get('sub')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            raise Exception("JWT token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            raise Exception(f"Invalid JWT token: {str(e)}")
        except Exception as e:
            logger.error(f"Error validating JWT token: {str(e)}")
            raise Exception(f"Failed to validate JWT token: {str(e)}")
    
    def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """
        Generate new access token using refresh token
        
        Args:
            refresh_token: Valid refresh JWT token
            
        Returns:
            Dictionary containing new access and refresh tokens
        """
        try:
            # Validate refresh token
            payload = self.validate_token(refresh_token)
            
            # Check if it's actually a refresh token
            if payload.get('type') != 'refresh':
                raise Exception("Invalid token type. Refresh token required.")
            
            # Extract user info from refresh token
            user_info = {
                'username': payload.get('sub'),
                'instance_url': payload.get('snow_instance'),
                'client_id': payload.get('client_id')
            }
            
            # Generate new tokens
            new_access_token = self.generate_token(user_info, 'access')
            new_refresh_token = self.generate_token(user_info, 'refresh')
            
            logger.info(f"Tokens refreshed for user: {user_info['username']}")
            
            return {
                'access_token': new_access_token,
                'refresh_token': new_refresh_token,
                'token_type': 'Bearer',
                'expires_in': self.token_expiry_hours * 3600  # In seconds
            }
            
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise Exception(f"Failed to refresh token: {str(e)}")
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """
        Get information about a JWT token without full validation
        
        Args:
            token: JWT token string
            
        Returns:
            Dictionary containing token information
        """
        try:
            # Decode without verification to get payload info
            payload = jwt.decode(token, options={"verify_signature": False})
            
            exp_timestamp = payload.get('exp')
            exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc) if exp_timestamp else None
            
            iat_timestamp = payload.get('iat')
            iat_datetime = datetime.fromtimestamp(iat_timestamp, tz=timezone.utc) if iat_timestamp else None
            
            return {
                'username': payload.get('sub'),
                'token_type': payload.get('type'),
                'instance_url': payload.get('snow_instance'),
                'issued_at': iat_datetime.isoformat() if iat_datetime else None,
                'expires_at': exp_datetime.isoformat() if exp_datetime else None,
                'is_expired': exp_datetime < datetime.now(timezone.utc) if exp_datetime else True,
                'issuer': payload.get('iss'),
                'audience': payload.get('aud')
            }
            
        except Exception as e:
            logger.error(f"Error getting token info: {str(e)}")
            raise Exception(f"Failed to get token info: {str(e)}")

# Global JWT auth manager instance
jwt_auth = JWTAuthManager()

def create_initial_tokens(username: str, password: str, instance_url: str, client_id: str) -> Dict[str, str]:
    """
    Create initial JWT tokens using username/password authentication
    This would typically be called once to establish JWT-based auth
    
    Args:
        username: ServiceNow username
        password: ServiceNow password (used for initial auth only)
        instance_url: ServiceNow instance URL
        client_id: OAuth client ID
        
    Returns:
        Dictionary containing access and refresh tokens
    """
    try:
        # In a real implementation, you might want to validate credentials against ServiceNow first
        # For now, we'll generate tokens based on provided credentials
        
        user_info = {
            'username': username,
            'instance_url': instance_url,
            'client_id': client_id
        }
        
        access_token = jwt_auth.generate_token(user_info, 'access')
        refresh_token = jwt_auth.generate_token(user_info, 'refresh')
        
        logger.info(f"Created initial JWT tokens for user: {username}")
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': jwt_auth.token_expiry_hours * 3600
        }
        
    except Exception as e:
        logger.error(f"Error creating initial tokens: {str(e)}")
        raise Exception(f"Failed to create initial tokens: {str(e)}")
