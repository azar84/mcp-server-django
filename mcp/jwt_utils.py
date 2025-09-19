"""
JWT utilities for OpenAI-compatible token generation
Embeds tenant information in JWT tokens since OpenAI doesn't forward X-Tenant-ID
"""

import jwt
import secrets
from datetime import datetime, timedelta
from django.conf import settings


def generate_jwt_token(tenant_id, scopes, expires_in_days=365):
    """
    Generate a JWT token that includes tenant information
    This allows us to work around OpenAI's limitation of not forwarding custom headers
    """
    # Generate a random secret for this token (stored in token field)
    token_secret = secrets.token_urlsafe(32)
    
    # Create JWT payload
    payload = {
        'tenant_id': tenant_id,
        'scopes': scopes,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=expires_in_days),
        'iss': 'mcp-server-django',
        'token_secret': token_secret  # Include the secret in the JWT
    }
    
    # Use Django's SECRET_KEY for JWT signing
    secret_key = getattr(settings, 'SECRET_KEY', 'fallback-secret-key')
    
    # Generate JWT
    jwt_token = jwt.encode(payload, secret_key, algorithm='HS256')
    
    return jwt_token, token_secret


def decode_jwt_token(jwt_token):
    """
    Decode and validate JWT token
    Returns the payload if valid, None if invalid
    """
    try:
        secret_key = getattr(settings, 'SECRET_KEY', 'fallback-secret-key')
        payload = jwt.decode(jwt_token, secret_key, algorithms=['HS256'])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, jwt.DecodeError):
        return None


def create_openai_compatible_token(tenant, scopes, expires_in_days=365):
    """
    Create an OpenAI-compatible token for a tenant
    Returns both the JWT token and the token secret to store in the database
    """
    jwt_token, token_secret = generate_jwt_token(
        tenant_id=tenant.tenant_id,
        scopes=scopes,
        expires_in_days=expires_in_days
    )
    
    return {
        'jwt_token': jwt_token,
        'token_secret': token_secret,  # Store this in AuthToken.token field
        'tenant_id': tenant.tenant_id,
        'scopes': scopes,
        'expires_in_days': expires_in_days
    }
