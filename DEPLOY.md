# Heroku Deployment Guide

Deploy your MCP Server to Heroku for production use with OpenAI Realtime integration.

## Prerequisites

- Heroku CLI installed
- Git repository initialized
- Heroku account

## Quick Deployment

### 1. Install Heroku CLI

```bash
# macOS
brew tap heroku/brew && brew install heroku

# Or download from: https://devcenter.heroku.com/articles/heroku-cli
```

### 2. Login to Heroku

```bash
heroku login
```

### 3. Create Heroku App

```bash
# In your project directory
cd "/Users/azarmacbook/Cursor Projects/MCP Server"

# Create Heroku app
heroku create your-mcp-server-name

# Or let Heroku generate a name
heroku create
```

### 4. Set Environment Variables

```bash
# Generate encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set the encryption key (use the generated key from above)
heroku config:set MCP_ENCRYPTION_KEY="your-generated-key-here"

# Set Django settings
heroku config:set DJANGO_SETTINGS_MODULE="mcp_server.settings_production"

# Optional: Set custom secret key
heroku config:set SECRET_KEY="your-custom-secret-key"
```

### 5. Add PostgreSQL Database

```bash
heroku addons:create heroku-postgresql:mini
```

### 6. Deploy

```bash
# Initialize git if not already done
git init
git add .
git commit -m "Initial MCP server deployment"

# Add Heroku remote
heroku git:remote -a your-app-name

# Deploy
git push heroku main
```

### 7. Run Migrations

```bash
heroku run python manage.py migrate
heroku run python manage.py createsuperuser
```

## Configuration

### Environment Variables

Set these on Heroku:

```bash
heroku config:set SECRET_KEY="your-secret-key"
heroku config:set MCP_ENCRYPTION_KEY="your-encryption-key"
heroku config:set DJANGO_SETTINGS_MODULE="mcp_server.settings_production"
```

### Database

Heroku automatically provides `DATABASE_URL` for PostgreSQL.

## Your MCP Server URLs

After deployment, your MCP server will be available at:

- **Main MCP Endpoint**: `https://your-app-name.herokuapp.com/api/mcp/`
- **Admin Panel**: `https://your-app-name.herokuapp.com/admin/`
- **Documentation**: `https://your-app-name.herokuapp.com/`

## OpenAI Integration

Use your Heroku URL in OpenAI Realtime:

```python
from openai import OpenAI

client = OpenAI(api_key="your-openai-api-key")

response = client.responses.create(
    model="gpt-4o-realtime-preview",
    tools=[{
        "type": "mcp",
        "server_label": "bookings",
        "server_url": "https://your-app-name.herokuapp.com/api/mcp/",
        "headers": {
            "Authorization": "Bearer your-token",
            "X-Tenant-ID": "your-tenant-id"
        }
    }],
    input="Check server status"
)
```

## Post-Deployment Setup

### 1. Create Tenant and Token

```bash
# Create tenant
curl -X POST https://your-app-name.herokuapp.com/api/admin/tenants/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Production Tenant", "description": "Main production tenant"}'

# Create token (use tenant_id from above response)
curl -X POST https://your-app-name.herokuapp.com/api/admin/tokens/ \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-id",
    "scopes": ["booking", "ms_bookings", "basic"],
    "expires_in_days": 365
  }'
```

### 2. Add MS Bookings Credentials

Access admin panel at `https://your-app-name.herokuapp.com/admin/` and add your MS Bookings credentials.

## Troubleshooting

### Check Logs

```bash
heroku logs --tail
```

### Restart App

```bash
heroku restart
```

### Run Commands

```bash
heroku run python manage.py shell
heroku run python manage.py migrate
```

### Scale App

```bash
heroku ps:scale web=1
```

## Security Notes

- Change default admin credentials after deployment
- Use strong SECRET_KEY and MCP_ENCRYPTION_KEY
- Regularly rotate authentication tokens
- Monitor access logs

## Updates

To update your deployed app:

```bash
git add .
git commit -m "Update MCP server"
git push heroku main
```

Your MCP server will be production-ready on Heroku with HTTPS, PostgreSQL, and full OpenAI Realtime compatibility!
