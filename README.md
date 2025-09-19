# Django MCP Server

A comprehensive Model Context Protocol (MCP) server implementation using Django, designed to be used by agents on other platforms with enterprise-grade authentication and multi-tenancy.

## Features

- **Full MCP Protocol Support**: Implements MCP 2024-11-05 specification
- **Multi-Tenant Architecture**: Complete tenant isolation with per-tenant credentials
- **Authentication & Authorization**: Token-based authentication with scope-based access control
- **WebSocket & HTTP Support**: Real-time WebSocket connections and HTTP RPC endpoints
- **Built-in Tools**: 7 sample tools with scope-based access control
- **Credential Management**: Encrypted per-tenant credential storage for tools
- **Session Management**: Track and manage client sessions with tenant context
- **Analytics & Monitoring**: Built-in analytics for tool usage and session tracking
- **Admin API**: Complete REST API for tenant and credential management
- **Modern UI**: Beautiful web interface for server monitoring

## Quick Start

### 1. Installation

```bash
# Clone or create the project directory
cd "MCP Server"

# Install Python dependencies
pip install -r requirements.txt

# Run Django migrations
python3 manage.py makemigrations
python3 manage.py migrate

# Create superuser (optional)
python3 manage.py createsuperuser
```

### 2. No External Dependencies Required

The server uses in-memory channels, so no Redis or other external services are required for basic functionality.

### 3. Run the Server

```bash
# Start the Django development server
python3 manage.py runserver 0.0.0.0:8000
```

The server will be available at:
- **Web Interface**: http://localhost:8000
- **WebSocket**: ws://localhost:8000/ws/mcp/
- **API Endpoints**: http://localhost:8000/api/mcp/

## Authentication & Multi-Tenancy

### Tenant Management

1. **Create a Tenant**:
```bash
curl -X POST http://localhost:8000/api/admin/tenants/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Company",
    "description": "Company tenant for MCP access"
  }'
```

2. **Create Authentication Token**:
```bash
curl -X POST http://localhost:8000/api/admin/tokens/ \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-id",
    "scopes": ["basic", "files", "web", "api"],
    "expires_in_days": 30
  }'
```

3. **Store Credentials for Tools**:
```bash
curl -X POST http://localhost:8000/api/admin/credentials/ \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-id",
    "tool_name": "secure_api",
    "credential_key": "api_key",
    "credential_value": "your-api-key"
  }'
```

## MCP Client Connection

### WebSocket Connection (Authenticated)

Connect to the MCP server via WebSocket with authentication:

```javascript
const token = 'your-auth-token';
const tenantId = 'your-tenant-id';
const ws = new WebSocket(`ws://localhost:8000/ws/mcp/?token=${token}&tenant_id=${tenantId}`);

// Initialize MCP session
const initMessage = {
    jsonrpc: "2.0",
    id: "1",
    method: "initialize",
    params: {
        protocolVersion: "2024-11-05",
        clientInfo: {
            name: "My MCP Client",
            version: "1.0.0"
        }
    }
};

ws.send(JSON.stringify(initMessage));
```

### HTTP RPC (Authenticated)

Make MCP calls via HTTP with authentication:

```bash
curl -X POST http://localhost:8000/api/mcp/rpc/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-auth-token" \
  -H "X-Tenant-ID: your-tenant-id" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tools/list"
  }'
```

## Available Tools & Scopes

The server comes with 7 built-in tools with scope-based access control:

### Scope System
- **No scope required**: Basic tools available to all authenticated users
- **basic**: Standard functionality (time, calculator)
- **files**: File system operations (tenant-isolated)
- **web**: HTTP request capabilities
- **admin**: Administrative access (system information)
- **api**: Secure API access with tenant credentials

### 1. Echo Tool (No scope required)
```json
{
  "name": "echo",
  "description": "Echo back a message",
  "arguments": {
    "message": "Hello, MCP!"
  }
}
```

### 2. Current Time Tool (Scope: basic)
```json
{
  "name": "current_time",
  "description": "Get the current server time",
  "arguments": {
    "format": "iso"  // "iso", "timestamp", or "human"
  }
}
```

### 3. System Info Tool (Scope: admin)
```json
{
  "name": "system_info",
  "description": "Get basic system information",
  "arguments": {}
}
```

### 4. File Operations Tool (Scope: files)
```json
{
  "name": "file_operations",
  "description": "Perform tenant-isolated file operations",
  "arguments": {
    "operation": "read",  // "read", "write", "list", "exists"
    "path": "test.txt",   // Automatically scoped to tenant directory
    "content": "File content"  // for write operation
  }
}
```

### 5. Web Request Tool (Scope: web)
```json
{
  "name": "web_request",
  "description": "Make HTTP requests with optional tenant credentials",
  "arguments": {
    "url": "https://api.github.com/users/octocat",
    "method": "GET",
    "headers": {},
    "data": {}
  }
}
```

### 6. Calculator Tool (Scope: basic)
```json
{
  "name": "calculator",
  "description": "Perform basic mathematical calculations",
  "arguments": {
    "expression": "2 + 2 * 3"
  }
}
```

### 7. Secure API Tool (Scope: api, Requires credentials)
```json
{
  "name": "secure_api",
  "description": "Call secure API endpoints using tenant credentials",
  "arguments": {
    "endpoint": "user_profile"
  }
}
```

## API Endpoints

### MCP Protocol Endpoints
```bash
GET /api/mcp/info/           # Server information and capabilities
GET /api/mcp/sessions/       # Active MCP sessions
GET /api/mcp/tools/          # Available tools (scope-filtered)
GET /api/mcp/analytics/      # Server analytics and usage statistics
POST /api/mcp/rpc/           # MCP RPC calls via HTTP (authenticated)
```

### Tenant Management Endpoints
```bash
GET /api/admin/tenants/      # List all tenants
POST /api/admin/tenants/     # Create new tenant
```

### Token Management Endpoints
```bash
GET /api/admin/tokens/       # List all authentication tokens
POST /api/admin/tokens/      # Create new authentication token
DELETE /api/admin/tokens/<id>/ # Deactivate token
```

### Credential Management Endpoints
```bash
GET /api/admin/credentials/  # List credentials for tenant
POST /api/admin/credentials/ # Store credential for tenant/tool
DELETE /api/admin/credentials/<id>/ # Deactivate credential
```

### Admin Endpoints
```bash
GET /api/admin/scopes/       # List available scopes and descriptions
GET /api/admin/dashboard/<tenant_id>/ # Tenant dashboard with analytics
```

## Example MCP Workflow

1. **Initialize Connection**:
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "clientInfo": {
      "name": "My Agent",
      "version": "1.0.0"
    }
  }
}
```

2. **List Available Tools**:
```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "tools/list"
}
```

3. **Call a Tool**:
```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "tools/call",
  "params": {
    "name": "echo",
    "arguments": {
      "message": "Hello from my agent!"
    }
  }
}
```

## Adding Custom Tools

To add custom tools, edit `mcp/tools.py`:

```python
async def my_custom_tool(arguments: Dict[str, Any], session_id: str) -> str:
    """Your custom tool implementation"""
    # Your logic here
    return "Tool result"

# Register the tool
protocol_handler.register_tool(
    name="my_tool",
    description="Description of what the tool does",
    input_schema={
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param1"]
    },
    handler=my_custom_tool
)
```

## Configuration

### Environment Variables

Create a `.env` file for production settings:

```env
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com
MCP_ENCRYPTION_KEY=your-encryption-key-here
```

### Production Deployment

For production deployment:

1. Set `DEBUG=False` in settings
2. Configure proper `SECRET_KEY`
3. Set up proper database (PostgreSQL recommended)
4. Set `MCP_ENCRYPTION_KEY` for credential encryption
5. Use a proper ASGI server like Uvicorn or Daphne

```bash
# Install production server
pip install uvicorn[standard]

# Run with Uvicorn
uvicorn mcp_server.asgi:application --host 0.0.0.0 --port 8000
```

## Architecture

```
├── mcp_server/          # Django project settings
│   ├── settings.py      # Django configuration
│   ├── urls.py          # Main URL routing
│   └── asgi.py          # ASGI configuration
├── mcp/                 # MCP application
│   ├── models.py        # Database models
│   ├── protocol.py      # MCP protocol implementation
│   ├── consumers.py     # WebSocket consumers
│   ├── views.py         # REST API views
│   ├── tools.py         # Tool implementations
│   ├── urls.py          # App URL routing
│   └── templates/       # HTML templates
└── requirements.txt     # Python dependencies
```

## Security Notes

- File operations are restricted to `/tmp/mcp_files/` directory
- Calculator tool only allows basic math operations
- Web requests have a 10-second timeout
- All tool calls are logged for audit purposes

## Troubleshooting

### WebSocket Connection Issues
- Check firewall settings
- Verify ALLOWED_HOSTS in settings.py
- Ensure authentication token and tenant_id are provided

### Tool Execution Errors
- Check server logs for detailed error messages
- Verify tool arguments match the schema
- Ensure proper permissions for file operations

## License

This project is provided as-is for educational and development purposes.
