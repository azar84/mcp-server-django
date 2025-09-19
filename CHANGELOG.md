# MCP Server Changelog

## Version 2.0.0 - In-Memory Channels Update

### 🔄 **Breaking Changes**
- **Removed Redis dependency**: Server now uses Django Channels' `InMemoryChannelLayer`
- **Simplified deployment**: No external dependencies required for basic functionality

### ✅ **What Changed**
- Updated `CHANNEL_LAYERS` configuration to use in-memory backend
- Removed `channels-redis` and `redis` from requirements.txt
- Updated documentation to remove Redis setup instructions
- Added `psutil` dependency for system information tool

### 🚀 **Benefits**
- **Zero external dependencies** for basic functionality
- **Easier development setup** - just run `python manage.py runserver`
- **Simplified Docker deployment** - no Redis container needed
- **Lower resource usage** for small to medium deployments

### ⚠️ **Important Notes**
- **In-memory channels are not persistent** - WebSocket connections will be lost on server restart
- **Single-server limitation** - Cannot scale horizontally with in-memory channels
- **For production with multiple workers**: Consider using Redis or database channel layer

### 🔧 **Migration from Redis**
If you were using Redis before:

1. **Update settings.py**:
   ```python
   CHANNEL_LAYERS = {
       'default': {
           'BACKEND': 'channels.layers.InMemoryChannelLayer',
       },
   }
   ```

2. **Update requirements.txt**: Remove `channels-redis` and `redis`

3. **Remove Redis from deployment**: No need to run Redis server

### 🏭 **Production Considerations**
For production deployments with high availability requirements:

```python
# Option 1: Database channel layer (persistent)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.DatabaseChannelLayer',
    },
}

# Option 2: Redis channel layer (scalable)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

### 📋 **Updated Features**
- All authentication and multi-tenancy features remain unchanged
- WebSocket connections work identically
- Tool execution and credential management unaffected
- Admin API functionality preserved

---

## Version 1.0.0 - Initial Multi-Tenant Release

### 🎉 **Initial Features**
- Multi-tenant architecture with complete tenant isolation
- Token-based authentication with scope-based access control
- Encrypted per-tenant credential storage
- 7 built-in tools with scope requirements
- WebSocket and HTTP MCP protocol support
- Admin API for tenant and credential management
- Analytics and monitoring dashboard
