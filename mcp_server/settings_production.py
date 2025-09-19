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

# Database configuration for Heroku PostgreSQL
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

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
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
    },
}

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# CORS settings (if needed for browser access)
CORS_ALLOW_ALL_ORIGINS = True  # For development - restrict in production
