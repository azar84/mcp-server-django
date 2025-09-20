# MCP Server Domain Structure

This document outlines the domain-based organization structure for the MCP server tools and resources.

## Directory Structure

```
mcp/
├── domains/                    # Domain-based tool organization
│   ├── base.py                # Base classes for providers and tools
│   ├── bookings/              # Booking & Scheduling domain
│   │   ├── calendly.py        # Calendly provider
│   │   ├── google_calendar.py # Google Calendar provider
│   │   └── ms_bookings.py     # Microsoft Bookings provider
│   ├── crm/                   # Customer Relationship Management
│   │   ├── salesforce.py      # Salesforce provider
│   │   ├── hubspot.py         # HubSpot provider
│   │   └── pipedrive.py       # Pipedrive provider
│   ├── payments/              # Payment Processing
│   │   ├── stripe.py          # Stripe provider
│   │   └── paypal.py          # PayPal provider
│   └── email/                 # Email Services
│       ├── sendgrid.py        # SendGrid provider
│       └── mailgun.py         # Mailgun provider
├── resources/                 # Resource handlers
│   └── knowledge_base.py      # kb:// resource handler
└── domain_registry.py        # Central domain registry
```

## Tool Organization

### Bookings Domain
**Providers**: Calendly, Google Calendar, Microsoft Bookings

**Tools**:
- `bookings_get_staff_availability` - Get available time slots
- `bookings_book_slot` - Book appointment/meeting

**Scopes**: `booking`, `[provider_name]`, `write` (for booking)

### CRM Domain  
**Providers**: Salesforce, HubSpot, Pipedrive

**Tools**:
- `crm_lookup_customer` - Search for customer information
- `crm_create_lead` - Create new lead/contact

**Scopes**: `crm`, `[provider_name]`, `write` (for creation)

### Payments Domain
**Providers**: Stripe, PayPal

**Tools**:
- `payments_create_invoice` - Generate invoices
- `payments_get_payment_status` - Check payment status

**Scopes**: `payments`, `[provider_name]`, `write` (for creation)

### Email Domain
**Providers**: SendGrid, Mailgun

**Tools**:
- `email_send_email` - Send emails
- `email_get_delivery_stats` - Get email statistics

**Scopes**: `email`, `[provider_name]`, `write` (for sending)

## Resources System

### Knowledge Base Resources
**URI Pattern**: `kb://path/to/resource`

**Examples**:
- `kb://faq/*.md` - All FAQ markdown files
- `kb://faq/general.md` - Specific FAQ file

**Sample Structure**:
```
kb/
└── faq/
    ├── general.md      # General questions
    ├── booking.md      # Booking-related FAQ
    └── payments.md     # Payment-related FAQ
```

## Provider System

Each domain supports multiple providers with:

### Base Provider Features
- **Authentication**: Provider-specific credential validation
- **Configuration**: Provider-specific settings
- **Tool Registration**: Automatic tool discovery
- **Scope Management**: Required scopes per tool

### Credential Storage
Credentials are stored per-tenant with format:
- `{provider_name}_{credential_key}`
- Example: `stripe_secret_key`, `calendly_api_token`

## Usage Examples

### Tool Naming Convention
```
{domain}_{tool_name}
```

Examples:
- `bookings_get_staff_availability`
- `crm_lookup_customer` 
- `payments_create_invoice`

### Scope-based Access
```python
# Tenant with basic booking access
scopes = ["booking", "calendly"]

# Tenant with full CRM access  
scopes = ["crm", "salesforce", "hubspot", "write"]
```

### Resource Access
```python
# Get all FAQ files
kb_resource.resolve_resource("kb://faq/*.md")

# Get specific FAQ
kb_resource.resolve_resource("kb://faq/general.md")
```

## Extensibility

### Adding New Providers
1. Create provider class inheriting from `BaseProvider`
2. Implement required methods
3. Register with domain manager
4. Define tool classes (structure only)

### Adding New Domains
1. Create domain directory under `domains/`
2. Create provider classes
3. Register domain in `domain_registry.py`
4. Update scope definitions

### Adding New Resources
1. Create resource handler class
2. Implement URI resolution logic
3. Register with resource system

## Integration Points

### With Authentication System
- Tools filtered by tenant scopes
- Credentials resolved per tenant/provider
- Session tracking per domain

### With MCP Protocol
- Tools registered with protocol handler
- Scope validation on tool calls
- Credential injection into tool context

This structure provides a scalable foundation for adding new business domains and service providers while maintaining clean separation of concerns.
