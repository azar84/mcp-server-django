# MCP Server Changelog

## Version 1.3.0 - Authentication & Resource Access Stabilization (2025-09-26)

### 🔧 **Major Fixes**
- **Authentication Flow Stabilization**: Fixed tenant validation to prevent authentication failures after async-to-sync conversions
- **Resource Access Optimization**: Converted resource resolution methods from async to synchronous to eliminate threading deadlocks on Heroku
- **Content Fetching Resolution**: Resolved "a coroutine was expected" errors when agents fetch document content  
- **Scope-based Access Controls**: Streamlined permission scopes for resource tools from `['basic', 'read']` to `['basic']` for better agent accessibility

### 🐛 **Bugfixes**
- **Threading Issues**: Eliminated "You cannot submit onto CurrentThreadExecutor from its own thread" errors that appeared specifically in Heroku deployment environment
- **Tenant Relation Corruption**: Fixed `auth_token.tenant` becoming None after async-to-sync conversions leading to authentication failures
- **Resource Resolution**: Converted `onedrive_resource.resolve_resource()` from async to synchronous to prevent mounting `asyncio.run()` calls that caused synchronization issues
- **Agent Documentation Access**: Resolved intermittent failures when agents attempted to retrieve document content where was previously working

### ✅ **Authentication Improvements**
- Added explicit tenant validation in MCP transport to ensure `auth_token.tenant` is valid before resource access
- Enhanced error handling for malformed authentication tokens with meaningful error messages
- Prevented "Authentication required for resource access" failures through early detection of missing tenant relationships

### 🚀 **Performance & Stability**
- Simplified database calls by removing unnecessary `@database_sync_to_async` decorators that contributed to threading conflicts
- Eliminated async/await patterns for synchronous resource operations affecting `list_resources()` and `resolve_resource()`
- Optimized imports and reduce circular dependency risks in resource resolution workflows

### 🔄 **Breaking Changes**
- **Resource Methods Now Synchronous**: `onedrive_resource.list_resources()` and `onedrive_resource.resolve_resource()` converted to synchronous calls
- **Removed Async Wrappers**: Eliminated `asyncio.run()` calls throughout resource access layers for better threading compatibility

### 📋 **Updated Features**
- All authentication and multi-tenancy features remain unchanged
- WebSocket connections work identically
- Tool execution and credential management preserved
- Admin API functionality maintained
- Improved agent resource accessibility with streamlined authentication flow

---

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
