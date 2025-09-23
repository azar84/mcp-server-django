# Credential Retrieval Methodology for MCP Tools

## Problem
When building async MCP tools that need database access for credentials, Django's async/sync threading restrictions can cause `CurrentThreadExecutor` errors.

## Root Cause
Django doesn't allow synchronous database operations (`Model.objects.get()`) from within async contexts without proper handling.

## Solution: Two-Step Credential Retrieval Pattern

### ✅ CORRECT Pattern (Used by MS Bookings Availability Tool)

```python
class YourTool(BaseTool):
    async def execute(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute tool with credentials retrieved at top level"""
        try:
            # Step 1: Get tenant from context
            tenant = context.get('tenant')
            if not tenant:
                return json.dumps({
                    'error': True,
                    'message': 'No tenant found in context',
                    'error_type': 'missing_context'
                })
            
            # Step 2: Retrieve credentials synchronously at top level
            from ...models import YourCredentialModel
            
            try:
                # Direct synchronous database access - let DJANGO_ALLOW_ASYNC_UNSAFE handle it
                cred = YourCredentialModel.objects.get(tenant=tenant, is_active=True)
            except YourCredentialModel.DoesNotExist:
                return json.dumps({
                    'error': True,
                    'message': f'Credentials not configured for tenant: {tenant.name}',
                    'error_type': 'missing_credentials'
                })
            
            # Step 3: Add credentials to context for use in _execute_with_credentials
            context['your_credential'] = cred
            
            # Step 4: Get provider-specific credentials from context
            credentials = context.get('credentials', {})
            provider_credentials = {}
            
            for key in self.provider.get_required_credentials():
                cred_key = f"{self.provider.name}_{key}"
                if cred_key in credentials:
                    provider_credentials[key] = credentials[cred_key]
            
            # Step 5: Execute with credentials
            return await self._execute_with_credentials(arguments, provider_credentials, context)
            
        except Exception as e:
            return json.dumps({
                'error': True,
                'message': f'Error executing tool: {str(e)}',
                'error_type': 'execution_error'
            })

    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        """Execute tool logic with credentials already in context"""
        try:
            # Get credentials from context (already retrieved in execute method)
            cred = context.get('your_credential')
            if not cred:
                return 'ERROR: Credentials not found in context'
            
            # Use cred.field_name directly - NO MORE DATABASE ACCESS
            field_value = cred.field_name
            
            # Your tool logic here...
            
        except Exception as e:
            return f'ERROR: {str(e)}'
```

### ❌ INCORRECT Pattern (Causes Threading Errors)

```python
class YourTool(BaseTool):
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        """DON'T DO THIS - Causes threading errors"""
        
        # ❌ WRONG: Database access inside async method
        @database_sync_to_async
        def get_credential():
            return YourCredentialModel.objects.get(tenant=tenant, is_active=True)
        
        cred = await get_credential()  # This causes CurrentThreadExecutor error
        
        # ❌ WRONG: Another database access
        tenant = context.get('tenant')
        cred = tenant.your_credential  # This also causes threading issues
```

## Key Principles

### 1. Single Database Access
- **Do credential retrieval ONCE** in the `execute()` method
- **Never do database access** in `_execute_with_credentials()`

### 2. Context Management
- **Add credentials to context** after retrieving them
- **Use credentials from context** in `_execute_with_credentials()`

### 3. Error Handling
- **Handle credential not found** with proper error messages
- **Use consistent error format** with `json.dumps()`

### 4. Django Settings
- **Add `DJANGO_ALLOW_ASYNC_UNSAFE = True`** to settings for synchronous database access

## Implementation Checklist

When implementing a new tool:

- [ ] Add `execute()` method that retrieves credentials synchronously
- [ ] Add credentials to context: `context['your_credential'] = cred`
- [ ] Use credentials from context in `_execute_with_credentials()`
- [ ] Handle `DoesNotExist` exceptions properly
- [ ] Use consistent error message format
- [ ] Test both success and failure scenarios

## Examples for Other Tools

### Twilio Send Message Tool
```python
# In execute() method:
from ...models import TwilioCredential
cred = TwilioCredential.objects.get(tenant=tenant, is_active=True)
context['twilio_credential'] = cred

# In _execute_with_credentials() method:
twilio_cred = context.get('twilio_credential')
account_sid = twilio_cred.account_sid
auth_token = twilio_cred.auth_token
```

### Stripe Payment Tool
```python
# In execute() method:
from ...models import StripeCredential
cred = StripeCredential.objects.get(tenant=tenant, is_active=True)
context['stripe_credential'] = cred

# In _execute_with_credentials() method:
stripe_cred = context.get('stripe_credential')
secret_key = stripe_cred.secret_key
```

## Testing

Always test:
1. **Tool with valid credentials** - should work
2. **Tool with missing credentials** - should return proper error
3. **Tool with invalid tenant** - should return proper error
4. **Multiple concurrent requests** - should not cause threading issues

## Migration Guide

To fix existing tools with threading issues:

1. **Move database access** from `_execute_with_credentials()` to `execute()`
2. **Add credentials to context** in `execute()` method
3. **Use credentials from context** in `_execute_with_credentials()`
4. **Remove `@database_sync_to_async`** decorators
5. **Test thoroughly** to ensure no regression

This pattern ensures consistent, reliable credential retrieval across all MCP tools without threading issues.
