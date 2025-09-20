from django.db import models
from django.contrib.auth.models import User
import json
import uuid



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

    class Meta:
        verbose_name = "Authentication Token"
        verbose_name_plural = "Authentication Tokens"

    def __str__(self):
        return f"Token for {self.tenant.name}"


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


class ClientCredential(models.Model):
    """Model to store per-client credentials for tools"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    tool_name = models.CharField(max_length=100)
    credential_key = models.CharField(max_length=255)  # e.g., 'api_key', 'username', 'token'
    credential_value = models.TextField()  # Encrypted credential value
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['tenant', 'tool_name', 'credential_key']

    def __str__(self):
        return f"{self.tenant.name} - {self.tool_name} - {self.credential_key}"


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
    """Microsoft Bookings specific credentials"""
    tenant = models.OneToOneField(
        Tenant, 
        on_delete=models.CASCADE,
        related_name='ms_bookings_credential'
    )
    azure_tenant_id = models.CharField(
        max_length=255,
        help_text="Azure Active Directory tenant ID"
    )
    client_id = models.CharField(
        max_length=255,
        help_text="Azure application client ID"
    )
    client_secret = models.TextField(
        help_text="Azure application client secret (encrypted)"
    )
    business_id = models.CharField(
        max_length=255,
        help_text="Microsoft Bookings business ID or email address",
        default=""
    )
    staff_ids = models.JSONField(
        default=list,
        help_text="List of default staff member GUIDs for this tenant"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        """Override save to encrypt client_secret if it's being set"""
        if self.client_secret and not self._is_encrypted(self.client_secret):
            from .auth import mcp_authenticator
            # Encrypt the client secret before saving
            self.client_secret = mcp_authenticator.cipher_suite.encrypt(
                self.client_secret.encode()
            ).decode()
        super().save(*args, **kwargs)
    
    def _is_encrypted(self, value):
        """Check if a value is already encrypted (starts with gAAAAAB)"""
        return value.startswith('gAAAAAB')
    
    def get_client_secret(self):
        """Get the decrypted client secret"""
        from .auth import mcp_authenticator
        try:
            return mcp_authenticator.cipher_suite.decrypt(
                self.client_secret.encode()
            ).decode()
        except Exception:
            return self.client_secret  # Return as-is if decryption fails
    
    class Meta:
        verbose_name = "MS Bookings Credential"
        verbose_name_plural = "MS Bookings Credentials"
        db_table = 'mcp_ms_bookings_credentials'
    
    def __str__(self):
        return f"MS Bookings - {self.tenant.name}"
    
    @property
    def client_id_preview(self):
        """Show only first 8 characters of client ID"""
        return f"{self.client_id[:8]}..." if self.client_id else "Not set"


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