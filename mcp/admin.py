from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Tenant, AuthToken, MCPSession, MCPTool, MCPToolCall, ClientCredential,
    MSBookingsCredential, CalendlyCredential, GoogleCalendarCredential, StripeCredential
)
from .admin_config import mcp_admin_site


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant_id', 'is_active', 'created_at', 'active_tokens_count', 'active_sessions_count')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'tenant_id', 'description')
    readonly_fields = ('tenant_id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'tenant_id', 'description', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def active_tokens_count(self, obj):
        count = obj.authtoken_set.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:mcp_authtoken_changelist') + f'?tenant__id={obj.id}&is_active__exact=1'
            return format_html('<a href="{}">{} tokens</a>', url, count)
        return '0 tokens'
    active_tokens_count.short_description = 'Active Tokens'
    
    def active_sessions_count(self, obj):
        count = obj.mcpsession_set.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:mcp_mcpsession_changelist') + f'?tenant__id={obj.id}&is_active__exact=1'
            return format_html('<a href="{}">{} sessions</a>', url, count)
        return '0 sessions'
    active_sessions_count.short_description = 'Active Sessions'


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ('token_preview', 'tenant', 'scopes_display', 'is_active', 'expires_at', 'last_used', 'created_at')
    list_filter = ('is_active', 'expires_at', 'created_at', 'tenant')
    search_fields = ('tenant__name', 'tenant__tenant_id')
    readonly_fields = ('token', 'created_at', 'last_used')
    
    fieldsets = (
        ('Token Information', {
            'fields': ('tenant', 'is_active'),
            'description': 'Token will be auto-generated when saved'
        }),
        ('Permissions', {
            'fields': ('scopes',),
            'description': 'Enter scopes as JSON array, e.g., ["booking", "ms_bookings", "write"]'
        }),
        ('Expiration', {
            'fields': ('expires_at',),
            'description': 'Leave blank for no expiration, or set future date'
        }),
        ('Generated Token', {
            'fields': ('token',),
            'classes': ('collapse',),
            'description': 'Auto-generated secure token (read-only)'
        }),
        ('Usage Tracking', {
            'fields': ('created_at', 'last_used'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Generate token if not present"""
        if not obj.token:
            import secrets
            obj.token = secrets.token_urlsafe(32)
        
        # Set default expiration if not provided
        if not obj.expires_at:
            from django.utils import timezone
            from datetime import timedelta
            obj.expires_at = timezone.now() + timedelta(days=30)
        
        super().save_model(request, obj, form, change)
        
        # Show the generated token to the admin user
        if not change:  # Only on creation
            from django.contrib import messages
            messages.success(
                request, 
                f'Token created successfully! Token: {obj.token} (Save this securely - it won\'t be shown again)'
            )
    
    def token_preview(self, obj):
        return f"{obj.token[:8]}..." if obj.token else "No token"
    token_preview.short_description = 'Token'
    
    def scopes_display(self, obj):
        if obj.scopes:
            scopes_html = []
            for scope in obj.scopes:
                scopes_html.append(f'<span style="background-color: #e1f5fe; padding: 2px 6px; border-radius: 3px; margin: 1px;">{scope}</span>')
            return mark_safe(' '.join(scopes_html))
        return 'No scopes'
    scopes_display.short_description = 'Scopes'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


@admin.register(MCPSession)
class MCPSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'tenant', 'is_active', 'created_at', 'last_activity', 'tool_calls_count')
    list_filter = ('is_active', 'created_at', 'last_activity', 'tenant')
    search_fields = ('session_id', 'tenant__name', 'tenant__tenant_id')
    readonly_fields = ('session_id', 'created_at', 'last_activity')
    
    fieldsets = (
        ('Session Information', {
            'fields': ('session_id', 'tenant', 'auth_token', 'is_active')
        }),
        ('Client Information', {
            'fields': ('client_info',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_activity'),
            'classes': ('collapse',)
        }),
    )
    
    def tool_calls_count(self, obj):
        count = obj.mcptoolcall_set.count()
        if count > 0:
            url = reverse('admin:mcp_mcptoolcall_changelist') + f'?session__id={obj.id}'
            return format_html('<a href="{}">{} calls</a>', url, count)
        return '0 calls'
    tool_calls_count.short_description = 'Tool Calls'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant', 'auth_token')


@admin.register(MCPTool)
class MCPToolAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'required_scopes_display', 'requires_credentials', 'is_active', 'created_at')
    list_filter = ('is_active', 'requires_credentials', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Tool Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Requirements', {
            'fields': ('required_scopes', 'requires_credentials')
        }),
        ('Schema', {
            'fields': ('input_schema',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def required_scopes_display(self, obj):
        if obj.required_scopes:
            scopes_html = []
            for scope in obj.required_scopes:
                scopes_html.append(f'<span style="background-color: #fff3e0; padding: 2px 6px; border-radius: 3px; margin: 1px;">{scope}</span>')
            return mark_safe(' '.join(scopes_html))
        return 'No scopes required'
    required_scopes_display.short_description = 'Required Scopes'


@admin.register(MCPToolCall)
class MCPToolCallAdmin(admin.ModelAdmin):
    list_display = ('tool_name', 'session', 'tenant_name', 'created_at', 'execution_time', 'success_status')
    list_filter = ('tool_name', 'created_at', 'session__tenant')
    search_fields = ('tool_name', 'session__session_id', 'session__tenant__name')
    readonly_fields = ('created_at', 'execution_time')
    
    fieldsets = (
        ('Call Information', {
            'fields': ('session', 'tool_name', 'created_at', 'execution_time')
        }),
        ('Arguments', {
            'fields': ('arguments',),
            'classes': ('collapse',)
        }),
        ('Result', {
            'fields': ('result',),
            'classes': ('collapse',)
        }),
        ('Error', {
            'fields': ('error',),
            'classes': ('collapse',)
        }),
    )
    
    def tenant_name(self, obj):
        return obj.session.tenant.name if obj.session and obj.session.tenant else 'Unknown'
    tenant_name.short_description = 'Tenant'
    
    def success_status(self, obj):
        if obj.error:
            return format_html('<span style="color: red;">❌ Error</span>')
        elif obj.result:
            return format_html('<span style="color: green;">✅ Success</span>')
        else:
            return format_html('<span style="color: orange;">⏳ Pending</span>')
    success_status.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('session', 'session__tenant')


@admin.register(ClientCredential)
class ClientCredentialAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'tool_name', 'credential_key', 'is_active', 'created_at', 'updated_at')
    list_filter = ('tool_name', 'is_active', 'created_at', 'tenant')
    search_fields = ('tenant__name', 'tenant__tenant_id', 'tool_name', 'credential_key')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Credential Information', {
            'fields': ('tenant', 'tool_name', 'credential_key', 'is_active')
        }),
        ('Value', {
            'fields': ('credential_value',),
            'description': 'Credential values are encrypted in the database'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Make credential_value field a password field for security
        if 'credential_value' in form.base_fields:
            form.base_fields['credential_value'].widget.attrs['type'] = 'password'
        return form
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


# Add credential model admin interfaces
# These will be grouped under "Tool Credentials" in the admin

@admin.register(MSBookingsCredential)
class MSBookingsCredentialAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'business_id', 'service_id', 'azure_tenant_id', 'client_id_preview', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('tenant__name', 'tenant__tenant_id', 'azure_tenant_id', 'client_id', 'business_id', 'service_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Azure Configuration', {
            'fields': ('azure_tenant_id', 'client_id', 'client_secret'),
            'description': 'Microsoft Azure application credentials for MS Bookings access'
        }),
        ('Bookings Configuration', {
            'fields': ('business_id', 'service_id', 'staff_ids'),
            'description': 'Default business ID, service ID, and staff member GUIDs for this tenant'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Make client_secret field a password field for security
        if 'client_secret' in form.base_fields:
            form.base_fields['client_secret'].widget.attrs['type'] = 'password'
        return form
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


@admin.register(StripeCredential)
class StripeCredentialAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'secret_key_preview', 'publishable_key', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('tenant__name', 'tenant__tenant_id', 'publishable_key')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Stripe Configuration', {
            'fields': ('secret_key', 'publishable_key', 'webhook_secret'),
            'description': 'Stripe API keys and webhook configuration'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Password fields for sensitive data
        sensitive_fields = ['secret_key', 'webhook_secret']
        for field in sensitive_fields:
            if field in form.base_fields:
                form.base_fields[field].widget.attrs['type'] = 'password'
        return form


# Register additional credential admin classes for future tools

@admin.register(CalendlyCredential)
class CalendlyCredentialAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('tenant__name', 'tenant__tenant_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Calendly Configuration', {
            'fields': ('api_token',),
            'description': 'Calendly API token for accessing calendar data'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'api_token' in form.base_fields:
            form.base_fields['api_token'].widget.attrs['type'] = 'password'
        return form


@admin.register(GoogleCalendarCredential)
class GoogleCalendarCredentialAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'client_id', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('tenant__name', 'tenant__tenant_id', 'client_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Google OAuth Configuration', {
            'fields': ('client_id', 'client_secret', 'access_token', 'refresh_token'),
            'description': 'Google OAuth credentials for Calendar API access'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Password fields for sensitive data
        sensitive_fields = ['client_secret', 'access_token', 'refresh_token']
        for field in sensitive_fields:
            if field in form.base_fields:
                form.base_fields[field].widget.attrs['type'] = 'password'
        return form


# Customize admin site header and title
admin.site.site_header = "MCP Server Administration"
admin.site.site_title = "MCP Server Admin"
admin.site.index_title = "Welcome to MCP Server Administration"