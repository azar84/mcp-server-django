"""
Production settings for Heroku deployment
"""

import os
import dj_database_url
from .settings import *

# Security settings
DEBUG = False
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Heroku provides the PORT environment variable
ALLOWED_HOSTS = ['*']  # Heroku handles routing

# CSRF and CORS settings for Heroku
CSRF_TRUSTED_ORIGINS = [
    'https://mcp-server-production-5c5d51311224.herokuapp.com',
    'https://*.herokuapp.com',
]

# Database configuration for Heroku PostgreSQL with connection pooling
import dj_database_url

# Get database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3')

if DATABASE_URL.startswith('postgres://'):
    # Use Django's built-in connection management for PostgreSQL
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=0,  # Disable persistent connections to prevent exhaustion
            conn_health_checks=True,
            # Heroku-optimized database settings
            options={
                'MAX_CONNS': 1,  # Maximum connections per dyno
                'MIN_CONNS': 0,  # No minimum connections
                'INITIAL_CONNS': 0,  # No initial connections
                'MAX_IDLE': 0,   # No idle connections
                'MAX_USAGE': 100,  # Max queries per connection before recycling
                'BLOCK': True,   # Block when pool is exhausted
                'RESET_QUERIES': True,  # Reset queries on connection reuse
                'AUTOCOMMIT': True,  # Enable autocommit for better performance
            }
        )
    }
    
    # Additional database optimization settings
    DATABASE_CONNECTION_POOL_SIZE = 1  # Limit connection pool size
    DATABASE_CONNECTION_MAX_AGE = 0    # Don't reuse connections
else:
    # Fallback to default configuration for SQLite
    DATABASES = {
        'default': dj_database_url.config(
            default='sqlite:///db.sqlite3',
            conn_max_age=600,
            conn_health_checks=True
        )
    }

# Static files configuration
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# Whitenoise for static file serving
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
# Database connection monitoring
MIDDLEWARE.insert(2, 'mcp.db_monitoring.DatabaseConnectionMonitoringMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Channels configuration for Heroku
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# For production with Redis (if you add Redis addon)
# CHANNEL_LAYERS = {
#     'default': {
#         'BACKEND': 'channels_redis.core.RedisChannelLayer',
#         'CONFIG': {
#             "hosts": [os.environ.get('REDIS_URL', 'redis://localhost:6379')],
#         },
#     },
# }

# MCP Server configuration
MCP_ENCRYPTION_KEY = os.environ.get('MCP_ENCRYPTION_KEY')
if not MCP_ENCRYPTION_KEY:
    # Generate a key for first deployment
    from cryptography.fernet import Fernet
    MCP_ENCRYPTION_KEY = Fernet.generate_key().decode()
    print(f"Generated MCP_ENCRYPTION_KEY: {MCP_ENCRYPTION_KEY}")
    print("Set this as a Heroku config var: heroku config:set MCP_ENCRYPTION_KEY='{MCP_ENCRYPTION_KEY}'")

# Logging configuration with database connection monitoring
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',  # Only log database warnings and errors
            'propagate': False,
        },
        'psycopg2': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'mcp': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# CORS settings (if needed for browser access)
CORS_ALLOW_ALL_ORIGINS = True  # For development - restrict in production
