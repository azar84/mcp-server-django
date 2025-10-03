from django.db import models
from django.contrib.auth.models import User
import json
import uuid



class AdminToken(models.Model):
    """Model for admin authentication tokens (for tenant creation, etc.)"""
    token = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, help_text="Description of this admin token")
    scopes = models.JSONField(default=list, help_text="List of admin scopes")
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    created_by = models.CharField(max_length=255, blank=True, help_text="Who created this token")

    class Meta:
        verbose_name = "Admin Token"
        verbose_name_plural = "Admin Tokens"

    def __str__(self):
        return f"Admin Token: {self.name} ({self.token[:8]}...)"


class Tenant(models.Model):
    """Model for tenant management"""
    tenant_id = models.CharField(max_length=255, unique=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"

    def __str__(self):
        return f"{self.name} ({self.tenant_id})"


class AuthToken(models.Model):
    """Model for authentication tokens"""
    token = models.CharField(max_length=255, unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    scopes = models.JSONField(default=list)  # List of allowed scopes/tools
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # MS Bookings configuration is now in MSBookingsCredential model

    class Meta:
        verbose_name = "Authentication Token"
        verbose_name_plural = "Authentication Tokens"

    def __str__(self):
        return f"Token for {self.tenant.name}"
    
    def has_valid_azure_credentials(self):
        """Check if Azure credentials are configured in environment"""
        from django.conf import settings
        return all([
            settings.MS_BOOKINGS_AZURE_TENANT_ID,
            settings.MS_BOOKINGS_CLIENT_ID,
            settings.MS_BOOKINGS_CLIENT_SECRET
        ])
    
    @property
    def ms_bookings_client_id_preview(self):
        """Show only first 8 characters of client ID from environment"""
        from django.conf import settings
        client_id = settings.MS_BOOKINGS_CLIENT_ID
        return f"{client_id[:8]}..." if client_id else "Not set in environment"


class MCPSession(models.Model):
    """Model to track MCP client sessions"""
    session_id = models.CharField(max_length=255, unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True)
    auth_token = models.ForeignKey(AuthToken, on_delete=models.CASCADE, null=True, blank=True)
    client_info = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "MCP Session"
        verbose_name_plural = "MCP Sessions"

    def __str__(self):
        tenant_name = self.tenant.name if self.tenant else "Unknown"
        return f"Session {self.session_id} - {tenant_name}"


class MCPTool(models.Model):
    """Model to define available MCP tools"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    input_schema = models.JSONField()
    required_scopes = models.JSONField(default=list)  # Scopes required to use this tool
    requires_credentials = models.BooleanField(default=False)  # Whether tool needs client credentials
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "MCP Tool"
        verbose_name_plural = "MCP Tools"

    def __str__(self):
        return self.name




class MCPToolCall(models.Model):
    """Model to log MCP tool calls"""
    session = models.ForeignKey(MCPSession, on_delete=models.CASCADE)
    tool_name = models.CharField(max_length=100)
    arguments = models.JSONField()
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    execution_time = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Tool Call Log"
        verbose_name_plural = "Tool Call Logs"

    def __str__(self):
        return f"{self.tool_name} - {self.session.tenant.name}"


# Separate credential models for each tool/provider

class MSBookingsCredential(models.Model):
    """Microsoft Bookings specific credentials - now token-based"""
    auth_token = models.OneToOneField(
        AuthToken, 
        on_delete=models.CASCADE,
        related_name='ms_bookings_credential'
    )
    
    # Azure tenant ID is now per-token
    azure_tenant_id = models.CharField(
        max_length=255,
        help_text="Azure AD tenant ID for this token",
        default=""
    )
    
    business_id = models.CharField(
        max_length=255,
        help_text="Microsoft Bookings business ID or email address",
        default=""
    )
    staff_ids = models.JSONField(
        default=list,
        help_text="List of default staff member GUIDs for this token"
    )
    service_id = models.CharField(
        max_length=255,
        help_text="Default Microsoft Bookings service ID",
        default=""
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_azure_credentials(self):
        """Get Azure credentials - tenant_id from token, client_id/secret from environment"""
        from django.conf import settings
        return {
            'azure_tenant_id': self.azure_tenant_id,
            'client_id': settings.MS_BOOKINGS_CLIENT_ID,
            'client_secret': settings.MS_BOOKINGS_CLIENT_SECRET
        }
    
    def has_valid_azure_credentials(self):
        """Check if Azure credentials are configured - tenant_id from token, others from environment"""
        from django.conf import settings
        return all([
            self.azure_tenant_id,
            settings.MS_BOOKINGS_CLIENT_ID,
            settings.MS_BOOKINGS_CLIENT_SECRET
        ])
    
    def has_valid_configuration(self):
        """Check if MS Bookings configuration is complete"""
        return bool(self.business_id)
    
    class Meta:
        verbose_name = "MS Bookings Credential"
        verbose_name_plural = "MS Bookings Credentials"
        db_table = 'mcp_ms_bookings_credentials'
    
    def __str__(self):
        return f"MS Bookings - {self.auth_token.token[:8]}..."
    
    @property
    def client_id_preview(self):
        """Show only first 8 characters of client ID from environment"""
        from django.conf import settings
        client_id = settings.MS_BOOKINGS_CLIENT_ID
        return f"{client_id[:8]}..." if client_id else "Not set in environment"


class CalendlyCredential(models.Model):
    """Calendly specific credentials"""
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='calendly_credential'
    )
    api_token = models.TextField(
        help_text="Calendly API token (encrypted)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Calendly Credential"
        verbose_name_plural = "Calendly Credentials"
        db_table = 'mcp_calendly_credentials'
    
    def __str__(self):
        return f"Calendly - {self.tenant.name}"


class GoogleCalendarCredential(models.Model):
    """Google Calendar specific credentials"""
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='google_calendar_credential'
    )
    access_token = models.TextField(
        help_text="Google OAuth access token (encrypted)"
    )
    refresh_token = models.TextField(
        blank=True,
        help_text="Google OAuth refresh token (encrypted)"
    )
    client_id = models.CharField(
        max_length=255,
        help_text="Google OAuth client ID"
    )
    client_secret = models.TextField(
        help_text="Google OAuth client secret (encrypted)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Google Calendar Credential"
        verbose_name_plural = "Google Calendar Credentials"
        db_table = 'mcp_google_calendar_credentials'
    
    def __str__(self):
        return f"Google Calendar - {self.tenant.name}"


class StripeCredential(models.Model):
    """Stripe payment credentials"""
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='stripe_credential'
    )
    secret_key = models.TextField(
        help_text="Stripe secret key (encrypted)"
    )
    publishable_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stripe publishable key"
    )
    webhook_secret = models.TextField(
        blank=True,
        help_text="Stripe webhook endpoint secret (encrypted)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Stripe Credential"
        verbose_name_plural = "Stripe Credentials"
        db_table = 'mcp_stripe_credentials'
    
    def __str__(self):
        return f"Stripe - {self.tenant.name}"
    
    @property
    def secret_key_preview(self):
        """Show only the key prefix"""
        if self.secret_key.startswith('sk_'):
            return f"{self.secret_key[:8]}..."
        return "sk_..."


class TwilioCredential(models.Model):
    """Twilio Voice & SMS credentials"""
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='twilio_credential'
    )
    account_sid = models.CharField(
        max_length=255,
        help_text="Twilio Account SID"
    )
    auth_token = models.TextField(
        help_text="Twilio Auth Token (encrypted)"
    )
    phone_number = models.CharField(
        max_length=20,
        help_text="Twilio phone number (E.164 format, e.g., +15551234567)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        """Override save to encrypt auth_token if it's being set"""
        if self.auth_token and not self._is_encrypted(self.auth_token):
            from .auth import mcp_authenticator
            # Encrypt the auth token before saving
            self.auth_token = mcp_authenticator.cipher_suite.encrypt(
                self.auth_token.encode()
            ).decode()
        super().save(*args, **kwargs)
    
    def _is_encrypted(self, value):
        """Check if a value is already encrypted (starts with gAAAAAB)"""
        return value.startswith('gAAAAAB')
    
    def get_auth_token(self):
        """Get the decrypted auth token"""
        from .auth import mcp_authenticator
        try:
            return mcp_authenticator.cipher_suite.decrypt(
                self.auth_token.encode()
            ).decode()
        except Exception:
            return self.auth_token  # Return as-is if decryption fails
    
    class Meta:
        verbose_name = "Twilio Credential"
        verbose_name_plural = "Twilio Credentials"
        db_table = 'mcp_twilio_credentials'
    
    def __str__(self):
        return f"Twilio - {self.tenant.name}"
    
    @property
    def account_sid_preview(self):
        """Show only first 8 characters of account SID"""
        return f"{self.account_sid[:8]}..." if self.account_sid else "Not set"


class TenantResource(models.Model):
    """Tenant-specific resources (files, documents, etc.)"""
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='resources'
    )
    name = models.CharField(
        max_length=255,
        help_text="Resource name/title"
    )
    resource_type = models.CharField(
        max_length=50,
        choices=[
            ('onedrive', 'OneDrive File'),
            ('sharepoint', 'SharePoint Document'),
            ('googledrive', 'Google Drive File'),
            ('url', 'Web URL'),
            ('text', 'Text Content')
        ],
        default='onedrive'
    )
    resource_uri = models.URLField(
        max_length=1000,
        help_text="OneDrive share link, URL, or resource identifier"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of the resource content"
    )
    tags = models.JSONField(
        default=list,
        help_text="Tags for categorizing resources (e.g., ['faq', 'documentation', 'policies'])"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tenant Resource"
        verbose_name_plural = "Tenant Resources"
        db_table = 'mcp_tenant_resources'
        unique_together = ['tenant', 'name']  # Unique resource names per tenant
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
    
    @property
    def uri_preview(self):
        """Show shortened URI for admin display"""
        if len(self.resource_uri) > 50:
            return f"{self.resource_uri[:47]}..."
        return self.resource_uri