# MCP Server Django

A production-ready **Model Context Protocol (MCP) Server** built with Django, designed for seamless integration with OpenAI Realtime API and multi-tenant environments.

## 🚀 Features

### Core Capabilities
- **Multi-tenant Architecture** - Isolated data and configurations per tenant
- **Token-based Authentication** - Secure Bearer token authentication with scopes
- **OpenAI Realtime Compatible** - Streamable HTTP transport for OpenAI Agents SDK
- **Domain-based Tool Organization** - Tools organized by business function (bookings, CRM, payments, email)
- **Encrypted Credential Storage** - Secure per-tenant credential management
- **WebSocket & HTTP Support** - Full MCP protocol implementation

### Available Tools
- **General Tools** (require `basic` scope)
  - `general_get_server_status` - Server health and connection testing (no scope required)
  - `general_current_time` - Get current server time with multiple formats
  - `general_calculator` - Perform basic mathematical calculations
  - `general_get_timezone_by_location` - Get both Windows and IANA timezones for any city/location
- **Booking Tools** (require `booking` + provider scopes)
  - `bookings_get_staff_availability` - Microsoft Bookings staff availability (requires `ms_bookings` scope)

### Supported Integrations
- **Microsoft Bookings** - Staff availability, appointment scheduling
- **Open-Meteo Geocoding** - City-to-timezone resolution
- **Unicode CLDR** - Local timezone mapping data (offline)
- **Extensible Architecture** - Easy to add new providers (Calendly, Google Calendar, etc.)

### Special Features
- **Saskatchewan Timezone Fix** - Correctly maps Saskatchewan cities to Mountain Standard Time
- **Local CLDR Mapping** - No external API dependency for timezone conversion
- **Dual Timezone Format** - Returns both Windows and IANA timezone formats
- **City Name Parsing** - Handles "City, State" and "City, Country" formats

## 🏗️ Architecture

```
MCP Server (Django + Channels)
├── Multi-tenant Authentication
├── Domain-based Tools
│   ├── bookings/ (MS Bookings, Calendly, Google Calendar)
│   ├── crm/ (Salesforce, HubSpot, Pipedrive)
│   ├── payments/ (Stripe, PayPal)
│   ├── email/ (SendGrid, Mailgun)
│   └── general/ (Server utilities)
├── Encrypted Credentials Storage
├── MCP Streamable HTTP Transport
└── Admin Panel Management
```

## 🚀 Quick Start

### 1. Local Development

```bash
# Clone the repository
git clone https://github.com/azar84/mcp-server-django.git
cd mcp-server-django

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### 2. Heroku Deployment

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/azar84/mcp-server-django)

Or manually:

```bash
# Create Heroku app
heroku create your-mcp-server

# Set environment variables
heroku config:set DJANGO_SETTINGS_MODULE="mcp_server.settings_production"
heroku config:set MCP_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

# Add PostgreSQL
heroku addons:create heroku-postgresql:essential-0

# Deploy
git push heroku main

# Run migrations
heroku run python manage.py migrate
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | Yes |
| `MCP_ENCRYPTION_KEY` | Fernet key for credential encryption | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes (Heroku) |
| `DJANGO_SETTINGS_MODULE` | Settings module | Yes (Production) |

### Settings Files

- `settings.py` - Development settings
- `settings_production.py` - Production settings for Heroku

## 🔐 Authentication

### 1. Create Tenant
```bash
curl -X POST https://your-server.herokuapp.com/api/admin/tenants/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Your Company", "description": "Main tenant"}'
```

### 2. Generate Token
```bash
curl -X POST https://your-server.herokuapp.com/api/admin/tokens/ \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-id",
    "scopes": ["basic", "booking", "ms_bookings"],
    "expires_in_days": 365
  }'
```

**Available Scopes:**
- `basic` - General tools (server status, time, calculator, timezone lookup)
- `booking` - Booking domain access
- `ms_bookings` - Microsoft Bookings provider
- `write` - Write operations (booking appointments, etc.)

### 3. JWT Tokens for OpenAI (Optional)

For better OpenAI integration, you can create JWT tokens that embed tenant information:

```python
import jwt
from mcp.models import AuthToken

# Get your existing token
auth_token = AuthToken.objects.get(token='your-raw-token')

# Create JWT token with tenant info
payload = {
    'tenant_id': auth_token.tenant.tenant_id,
    'token_secret': auth_token.token
}
jwt_token = jwt.encode(payload, 'secret', algorithm='HS256')
print(f"JWT Token: {jwt_token}")
```

Use the JWT token instead of the raw token for OpenAI integration.

### 4. Use with OpenAI Realtime

```python
from openai import OpenAI

client = OpenAI(api_key="your-openai-api-key")

response = client.responses.create(
    model="gpt-4o-realtime-preview",
    tools=[{
        "type": "mcp",
        "server_label": "bookings",
        "server_url": "https://your-server.herokuapp.com/api/mcp/",
        "headers": {
            "Authorization": "Bearer your-mcp-token"
            # Note: No X-Tenant-ID needed! The /api/mcp/ endpoint extracts tenant from token
        }
    }],
    input="Check server status, get current time, and find timezone for New York"
)
```

## 📚 API Endpoints

### MCP Protocol

#### Primary Endpoint (Recommended)
- `POST /api/mcp/` - **OpenAI-compatible MCP endpoint**
  - Authentication: `Authorization: Bearer <token>` only
  - Supports: `initialize`, `tools/list`, `tools/call`
  - Extracts tenant info from token automatically
  - **Use this for OpenAI Realtime integration**

#### Legacy Endpoints (Testing/Debug)
- `GET /api/mcp/tools/` - Available tools list (requires Bearer + X-Tenant-ID)
- `GET /api/mcp/capabilities/` - Server capabilities (requires Bearer + X-Tenant-ID)
- `POST /api/mcp/legacy/` - Legacy MCP transport (requires Bearer + X-Tenant-ID)

### Administration
- `POST /api/admin/tenants/` - Tenant management
- `POST /api/admin/tokens/` - Token generation
- `POST /api/admin/credentials/` - Credential management

### WebSocket
- `ws://localhost:8000/ws/mcp/` - MCP WebSocket endpoint

## 🛠️ Adding New Tools

### 1. Create Provider

```python
# mcp/domains/your_domain/your_provider.py
from ..base import BaseProvider, BaseTool, ProviderType

class YourProvider(BaseProvider):
    def __init__(self):
        super().__init__(
            name="your_provider",
            provider_type=ProviderType.YOUR_DOMAIN,
            config={}
        )
    
    def get_tools(self):
        return [{
            'name': 'your_tool',
            'tool_class': YourTool,
            'description': 'Your tool description',
            'input_schema': {...},
            'required_scopes': ['your_scope']
        }]
```

### 2. Register in Domain Registry

```python
# mcp/domain_registry.py
def _initialize_domains(self):
    # Add your domain
    your_domain = DomainManager("your_domain")
    your_domain.register_provider(YourProvider())
    self.domains["your_domain"] = your_domain
```

## 🏥 Health Monitoring

Check server status:
```bash
curl -X POST https://your-server.herokuapp.com/api/mcp/ \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"general_get_server_status","arguments":{}}}'
```

## 📊 Admin Panel

Access the Django admin panel at `/admin/` to manage:
- **Tenants** - Multi-tenant organizations
- **Auth Tokens** - API authentication tokens
- **Tool Credentials** - Encrypted third-party service credentials
- **Sessions** - Active MCP sessions
- **Analytics** - Usage monitoring

## 🔒 Security Features

- **HTTPS Enforcement** - All production traffic encrypted
- **CSRF Protection** - Cross-site request forgery prevention
- **Token Scoping** - Granular permission control
- **Credential Encryption** - Fernet encryption for sensitive data
- **Origin Validation** - Trusted origins for admin panel

## 🧪 Testing

```bash
# Run tests
python manage.py test

# Test MCP endpoint
python example_client.py

# Test with authentication
python authenticated_client_example.py
```

### Testing Individual Tools

```bash
# Test server status
curl -X POST https://your-server.herokuapp.com/api/mcp/ \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"general_get_server_status","arguments":{}}}'

# Test timezone lookup
curl -X POST https://your-server.herokuapp.com/api/mcp/ \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"2","method":"tools/call","params":{"name":"general_get_timezone_by_location","arguments":{"query":"Saskatoon"}}}'

# Test calculator
curl -X POST https://your-server.herokuapp.com/api/mcp/ \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"3","method":"tools/call","params":{"name":"general_calculator","arguments":{"expression":"2+2*3"}}}'
```

## 📈 Scaling

### Horizontal Scaling
- Use Redis for channel layers: `pip install channels-redis`
- Configure Redis in `CHANNEL_LAYERS` settings
- Deploy multiple Heroku dynos

### Database Optimization
- Use PostgreSQL connection pooling
- Implement database read replicas for heavy read workloads
- Add database indexes for frequently queried fields

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -am 'Add your feature'`
4. Push to branch: `git push origin feature/your-feature`
5. Submit a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [Full deployment guide](DEPLOY.md)
- **Issues**: [GitHub Issues](https://github.com/azar84/mcp-server-django/issues)
- **Discussions**: [GitHub Discussions](https://github.com/azar84/mcp-server-django/discussions)

## 🎯 Roadmap

- [ ] Additional booking providers (Calendly, Acuity)
- [ ] CRM integrations (Salesforce, HubSpot)
- [ ] Payment processing (Stripe, PayPal)
- [ ] Email marketing (SendGrid, Mailgun)
- [ ] Advanced analytics and monitoring
- [ ] Rate limiting and quotas
- [ ] Webhook support for real-time updates

---

**Built with ❤️ for the OpenAI ecosystem**

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/azar84/mcp-server-django)