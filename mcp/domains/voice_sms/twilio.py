"""
Twilio Voice & SMS provider
"""

import json
from typing import Dict, Any, List
from ..base import BaseProvider, BaseTool, ProviderType


class TwilioProvider(BaseProvider):
    """Twilio Voice & SMS system provider"""
    
    def __init__(self):
        super().__init__(
            name="twilio",
            provider_type=ProviderType.VOICE_SMS,
            config={
                'api_base': 'https://api.twilio.com/2010-04-01',
                'api_version': '2010-04-01'
            }
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return Twilio-specific tools"""
        return [
            {
                'name': 'send_sms',
                'tool_class': TwilioSendSMSTool,
                'description': 'Send SMS message using Twilio. Supports both US/Canada and international numbers.',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'to': {
                            'type': 'string',
                            'description': 'Recipient phone number (E.164 format recommended, e.g., +1234567890)',
                            'examples': ['+15551234567', '+442071234567', '555-123-4567']
                        },
                        'message': {
                            'type': 'string',
                            'description': 'SMS message content (max 1600 characters)',
                            'maxLength': 1600
                        }
                    },
                    'required': ['to', 'message']
                },
                'required_scopes': ['voice_sms', 'twilio', 'write']
            },
            {
                'name': 'get_message_status',
                'tool_class': TwilioGetMessageStatusTool,
                'description': 'Get the delivery status of a previously sent SMS message',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'message_sid': {
                            'type': 'string',
                            'description': 'Twilio message SID returned from send_sms'
                        }
                    },
                    'required': ['message_sid']
                },
                'required_scopes': ['voice_sms', 'twilio']
            },
            {
                'name': 'end_call',
                'tool_class': TwilioEndCallTool,
                'description': """End an active Twilio call. IMPORTANT: Only use this tool AFTER you have completely finished the conversation with the user and confirmed they are ready to end the call. You MUST: 
                1) Complete all conversation objectives, 2) Ask if the user has any other questions,
                 3) Confirm the user is ready to end the call, 4) Use proper ending statements like "Thank you, 
                 have a great day, goodbye!", and 5) Wait for user acknowledgment before calling this tool.
                  Use this tool when: conversation is fully complete, answering machine detected,
                   long waiting time, or user explicitly requests to end call.
                   Don't explain the results of this tool to the user.""",
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'call_sid': {
                            'type': 'string',
                            'description': 'Twilio Call SID of the active call to end'
                        },
                        'reason': {
                            'type': 'string',
                            'description': 'Reason for ending the call (optional)',
                            'examples': ['conversation_complete', 'answering_machine', 'long_wait_time', 'caller_requested_end']
                        }
                    },
                    'required': ['call_sid']
                },
                'required_scopes': ['voice_sms', 'twilio', 'write']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        """Twilio requires account SID, auth token, and phone number"""
        return ['account_sid', 'auth_token', 'phone_number']
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate Twilio credentials by testing API access"""
        account_sid = credentials.get('account_sid')
        auth_token = credentials.get('auth_token')
        
        if not all([account_sid, auth_token]):
            return False
        
        try:
            import requests
            import base64
            
            # Create basic auth header
            auth_string = f"{account_sid}:{auth_token}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()
            
            # Test the credentials by getting account info
            response = requests.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json",
                headers={'Authorization': f'Basic {auth_bytes}'},
                timeout=10
            )
            
            return response.status_code == 200
        except:
            return False


class TwilioSendSMSTool(BaseTool):
    """Send SMS messages using Twilio"""
    
    def _format_phone_number(self, phone):
        """Format phone number to E.164 format"""
        if not phone:
            return None
        
        import re
        # Remove all non-digit characters
        digits = re.sub(r'\D+', '', str(phone))
        
        if not digits:
            return None
        
        # Handle US/Canada numbers
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits.startswith('1'):
            return f"+{digits}"
        elif digits.startswith('+'):
            return phone  # Already formatted
        else:
            # For international numbers, assume they're correct
            return f"+{digits}"
    
    async def execute(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute SMS tool with credentials retrieved at top level (same as MS Bookings pattern)"""
        try:
            # Get Twilio credentials at the top level to avoid threading issues
            tenant = context.get('tenant')
            if not tenant:
                return json.dumps({
                    'error': True,
                    'message': 'No tenant found in context',
                    'error_type': 'missing_context',
                    'suggestions': [
                        'Ensure the request includes proper tenant authentication',
                        'Check if the authentication token is valid'
                    ],
                    'status': None,
                    'details': {
                        'missing_context': 'tenant'
                    }
                })
            
            # Retrieve Twilio credentials synchronously (bypass all async handling)
            from ...models import TwilioCredential
            
            try:
                # Direct synchronous database access - let DJANGO_ALLOW_ASYNC_UNSAFE handle it
                twilio_cred = TwilioCredential.objects.get(tenant=tenant, is_active=True)
            except TwilioCredential.DoesNotExist:
                return json.dumps({
                    'error': True,
                    'message': f'Twilio credentials not configured for tenant: {tenant.name} ({tenant.tenant_id})',
                    'error_type': 'missing_credentials',
                    'suggestions': [
                        'Configure Twilio credentials for this tenant',
                        'Ensure account_sid, auth_token, and phone_number are set',
                        'Activate the Twilio credential configuration'
                    ],
                    'status': None,
                    'details': {
                        'tenant_id': tenant.tenant_id,
                        'tenant_name': tenant.name,
                        'missing_credentials': 'Twilio'
                    }
                })
            
            # Add Twilio credentials to context for use in _execute_with_credentials
            context['twilio_credential'] = twilio_cred
            
            # Get provider-specific credentials from context
            credentials = context.get('credentials', {})
            provider_credentials = {}
            
            for key in self.provider.get_required_credentials():
                cred_key = f"{self.provider.name}_{key}"
                if cred_key in credentials:
                    provider_credentials[key] = credentials[cred_key]
            
            # Execute with credentials
            return await self._execute_with_credentials(arguments, provider_credentials, context)
            
        except Exception as e:
            return json.dumps({
                'error': True,
                'message': f'Error executing SMS tool: {str(e)}',
                'error_type': 'execution_error',
                'details': {
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            })

    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        try:
            # Get Twilio configuration from context (already retrieved in execute method)
            twilio_cred = context.get('twilio_credential')
            if not twilio_cred:
                return 'ERROR: Twilio credentials not found in context'
            
            # Extract configuration from credential
            config = {
                'account_sid': twilio_cred.account_sid,
                'auth_token': twilio_cred.get_auth_token(),  # Decrypted
                'phone_number': twilio_cred.phone_number
            }
            
            # Extract and validate arguments
            to_number = arguments.get('to')
            message_text = arguments.get('message')
            from_number = config['phone_number']  # Always use tenant's Twilio phone number
            
            if not to_number or not message_text:
                return json.dumps({
                    'error': True,
                    'message': 'Missing required parameters',
                    'error_type': 'missing_parameters',
                    'suggestions': [
                        'Provide both "to" (recipient phone number) and "message" parameters',
                        'Phone number should be in E.164 format (e.g., +1234567890)',
                        'Message should contain the text content to send'
                    ],
                    'status': None,
                    'details': {
                        'missing_parameters': [p for p in ['to', 'message'] if not arguments.get(p)],
                        'provided_parameters': {k: v for k, v in arguments.items() if k in ['to', 'message']}
                    }
                })
            
            # Format phone numbers
            to_formatted = self._format_phone_number(to_number)
            from_formatted = self._format_phone_number(from_number)
            
            if not to_formatted:
                return json.dumps({
                    'error': True,
                    'message': f'Invalid recipient phone number: {to_number}',
                    'error_type': 'invalid_phone_number',
                    'suggestions': [
                        'Use E.164 format: +1234567890 (country code + number)',
                        'For US/Canada: +1 followed by 10 digits',
                        'For international: + followed by country code and number',
                        'Remove spaces, dashes, and parentheses',
                        'Examples: "+15551234567", "+442071234567"'
                    ],
                    'status': None,
                    'details': {
                        'invalid_number': to_number,
                        'number_type': 'recipient',
                        'required_format': 'E.164'
                    }
                })
            if not from_formatted:
                return json.dumps({
                    'error': True,
                    'message': f'Invalid sender phone number in configuration: {from_number}',
                    'error_type': 'invalid_sender_number',
                    'suggestions': [
                        'Check Twilio phone number configuration in tenant credentials',
                        'Verify the phone number is in E.164 format',
                        'Ensure the phone number is verified in your Twilio account',
                        'Contact your administrator to fix the phone number configuration'
                    ],
                    'status': None,
                    'details': {
                        'invalid_number': from_number,
                        'number_type': 'sender',
                        'configuration_location': 'tenant Twilio credentials'
                    }
                })
            
            # Send SMS using Twilio API
            try:
                import requests
                import base64
                
                # Create basic auth
                auth_string = f"{config['account_sid']}:{config['auth_token']}"
                auth_bytes = base64.b64encode(auth_string.encode()).decode()
                
                # Send SMS
                response = requests.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{config['account_sid']}/Messages.json",
                    headers={'Authorization': f'Basic {auth_bytes}'},
                    data={
                        'From': from_formatted,
                        'To': to_formatted,
                        'Body': message_text
                    },
                    timeout=10
                )
                
                if response.status_code == 201:
                    result = response.json()
                    return json.dumps({
                        "ok": True,
                        "message_sid": result.get('sid'),
                        "status": result.get('status'),
                        "from": from_formatted,
                        "to": to_formatted,
                        "message": message_text,
                        "price": result.get('price'),
                        "uri": result.get('uri'),
                        "date_created": result.get('date_created')
                    })
                else:
                    try:
                        error_data = response.json()
                        api_error_msg = error_data.get('message', 'Unknown Twilio API error')
                    except:
                        api_error_msg = response.text or 'Unknown Twilio API error'
                    
                    return json.dumps({
                        'error': True,
                        'message': f'SMS sending failed: {api_error_msg}',
                        'error_type': 'twilio_api_error',
                        'suggestions': [
                            'Check if the recipient phone number is valid and reachable',
                            'Verify your Twilio account has sufficient balance',
                            'Ensure the phone number is verified in your Twilio account',
                            'Check Twilio account restrictions or rate limits',
                            'Verify the message content complies with SMS regulations'
                        ],
                        'status': response.status_code,
                        'details': {
                            'http_status': response.status_code,
                            'api_error': api_error_msg,
                            'from_number': from_formatted,
                            'to_number': to_formatted,
                            'message_length': len(message_text)
                        }
                    })
                    
            except Exception as e:
                return json.dumps({
                    'error': True,
                    'message': f'Twilio API request failed: {str(e)}',
                    'error_type': 'api_request_error',
                    'suggestions': [
                        'Check your internet connection',
                        'Verify Twilio API is accessible',
                        'Try again in a few minutes',
                        'Contact support if this error persists'
                    ],
                    'status': None,
                    'details': {
                        'error_message': str(e),
                        'error_type': type(e).__name__,
                        'from_number': from_formatted,
                        'to_number': to_formatted
                    }
                })
                
        except Exception as e:
            return json.dumps({
                'error': True,
                'message': f'Unexpected error in SMS sending: {str(e)}',
                'error_type': 'unexpected_error',
                'suggestions': [
                    'Try again in a few minutes',
                    'Check your internet connection',
                    'Verify Twilio credentials are correct',
                    'Contact support if this error persists'
                ],
                'status': None,
                'details': {
                    'error_message': str(e),
                    'error_type': type(e).__name__,
                    'tenant_id': tenant.tenant_id if tenant else 'Unknown'
                }
            })


class TwilioGetMessageStatusTool(BaseTool):
    """Get SMS message delivery status from Twilio"""
    
    async def execute(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute message status tool with credentials retrieved at top level (same as MS Bookings pattern)"""
        try:
            # Get Twilio credentials at the top level to avoid threading issues
            tenant = context.get('tenant')
            if not tenant:
                return json.dumps({
                    'error': True,
                    'message': 'No tenant found in context',
                    'error_type': 'missing_context',
                    'suggestions': [
                        'Ensure the request includes proper tenant authentication',
                        'Check if the authentication token is valid'
                    ],
                    'status': None,
                    'details': {
                        'missing_context': 'tenant'
                    }
                })
            
            # Retrieve Twilio credentials synchronously (bypass all async handling)
            from ...models import TwilioCredential
            
            try:
                # Direct synchronous database access - let DJANGO_ALLOW_ASYNC_UNSAFE handle it
                twilio_cred = TwilioCredential.objects.get(tenant=tenant, is_active=True)
            except TwilioCredential.DoesNotExist:
                return json.dumps({
                    'error': True,
                    'message': f'Twilio credentials not configured for tenant: {tenant.name} ({tenant.tenant_id})',
                    'error_type': 'missing_credentials',
                    'suggestions': [
                        'Configure Twilio credentials for this tenant',
                        'Ensure account_sid, auth_token, and phone_number are set',
                        'Activate the Twilio credential configuration'
                    ],
                    'status': None,
                    'details': {
                        'tenant_id': tenant.tenant_id,
                        'tenant_name': tenant.name,
                        'missing_credentials': 'Twilio'
                    }
                })
            
            # Add Twilio credentials to context for use in _execute_with_credentials
            context['twilio_credential'] = twilio_cred
            
            # Get provider-specific credentials from context
            credentials = context.get('credentials', {})
            provider_credentials = {}
            
            for key in self.provider.get_required_credentials():
                cred_key = f"{self.provider.name}_{key}"
                if cred_key in credentials:
                    provider_credentials[key] = credentials[cred_key]
            
            # Execute with credentials
            return await self._execute_with_credentials(arguments, provider_credentials, context)
            
        except Exception as e:
            return json.dumps({
                'error': True,
                'message': f'Error executing message status tool: {str(e)}',
                'error_type': 'execution_error',
                'details': {
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            })

    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        try:
            # Get Twilio configuration from context (already retrieved in execute method)
            twilio_cred = context.get('twilio_credential')
            if not twilio_cred:
                return 'ERROR: Twilio credentials not found in context'
            
            # Extract configuration from credential
            config = {
                'account_sid': twilio_cred.account_sid,
                'auth_token': twilio_cred.get_auth_token()
            }
            
            # Extract message SID
            message_sid = arguments.get('message_sid')
            if not message_sid:
                return 'ERROR: message_sid is required'
            
            # Get message status from Twilio
            try:
                import requests
                import base64
                
                # Create basic auth
                auth_string = f"{config['account_sid']}:{config['auth_token']}"
                auth_bytes = base64.b64encode(auth_string.encode()).decode()
                
                # Get message details
                response = requests.get(
                    f"https://api.twilio.com/2010-04-01/Accounts/{config['account_sid']}/Messages/{message_sid}.json",
                    headers={'Authorization': f'Basic {auth_bytes}'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return json.dumps({
                        "ok": True,
                        "message_sid": result.get('sid'),
                        "status": result.get('status'),
                        "error_code": result.get('error_code'),
                        "error_message": result.get('error_message'),
                        "from": result.get('from'),
                        "to": result.get('to'),
                        "body": result.get('body'),
                        "price": result.get('price'),
                        "date_created": result.get('date_created'),
                        "date_updated": result.get('date_updated'),
                        "date_sent": result.get('date_sent')
                    })
                else:
                    error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                    return f'ERROR: Failed to get message status (HTTP {response.status_code}): {error_data}'
                    
            except Exception as e:
                return f'ERROR: Twilio API error: {str(e)}'
                
        except Exception as e:
            return f'ERROR: {str(e)}'


class TwilioEndCallTool(BaseTool):
    """End an active Twilio call"""
    
    async def execute(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute end call tool with credentials retrieved at top level (same as MS Bookings pattern)"""
        try:
            # Get Twilio credentials at the top level to avoid threading issues
            tenant = context.get('tenant')
            if not tenant:
                return json.dumps({
                    'error': True,
                    'message': 'No tenant found in context',
                    'error_type': 'missing_context',
                    'suggestions': [
                        'Ensure the request includes proper tenant authentication',
                        'Check if the authentication token is valid'
                    ],
                    'status': None,
                    'details': {
                        'missing_context': 'tenant'
                    }
                })
            
            # Retrieve Twilio credentials synchronously (bypass all async handling)
            from ...models import TwilioCredential
            
            try:
                # Direct synchronous database access - let DJANGO_ALLOW_ASYNC_UNSAFE handle it
                twilio_cred = TwilioCredential.objects.get(tenant=tenant, is_active=True)
            except TwilioCredential.DoesNotExist:
                return json.dumps({
                    'error': True,
                    'message': f'Twilio credentials not configured for tenant: {tenant.name} ({tenant.tenant_id})',
                    'error_type': 'missing_credentials',
                    'suggestions': [
                        'Configure Twilio credentials for this tenant',
                        'Ensure account_sid, auth_token, and phone_number are set',
                        'Activate the Twilio credential configuration'
                    ],
                    'status': None,
                    'details': {
                        'tenant_id': tenant.tenant_id,
                        'tenant_name': tenant.name,
                        'missing_credentials': 'Twilio'
                    }
                })
            
            # Add Twilio credentials to context for use in _execute_with_credentials
            context['twilio_credential'] = twilio_cred
            
            # Get provider-specific credentials from context
            credentials = context.get('credentials', {})
            provider_credentials = {}
            
            for key in self.provider.get_required_credentials():
                cred_key = f"{self.provider.name}_{key}"
                if cred_key in credentials:
                    provider_credentials[key] = credentials[cred_key]
            
            # Execute with credentials
            return await self._execute_with_credentials(arguments, provider_credentials, context)
            
        except Exception as e:
            return json.dumps({
                'error': True,
                'message': f'Error executing end call tool: {str(e)}',
                'error_type': 'execution_error',
                'details': {
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            })

    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        try:
            # Get Twilio configuration from context (already retrieved in execute method)
            twilio_cred = context.get('twilio_credential')
            if not twilio_cred:
                return 'ERROR: Twilio credentials not found in context'
            
            # Extract configuration from credential
            config = {
                'account_sid': twilio_cred.account_sid,
                'auth_token': twilio_cred.get_auth_token()
            }
            
            # Extract call SID
            call_sid = arguments.get('call_sid')
            reason = arguments.get('reason', 'manual_end')
            
            if not call_sid:
                return 'ERROR: call_sid is required'
            
            # Add 5-second delay before ending the call to allow final words to be heard
            import asyncio
            import requests
            import base64
            
            # Wait 5 seconds before ending the call
            await asyncio.sleep(5)
            
            # Create basic auth header
            auth_string = f"{config['account_sid']}:{config['auth_token']}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()
            
            response = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{config['account_sid']}/Calls/{call_sid}.json",
                headers={'Authorization': f'Basic {auth_bytes}'},
                data={'Status': 'completed'},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return json.dumps({
                    "ok": True,
                    "call_sid": result.get('sid'),
                    "status": result.get('status'),
                    "reason": reason,
                    "message": "Call ended successfully after 5-second delay",
                    "duration": result.get('duration'),
                    "delay_applied": "5_seconds",
                    "response": result
                })
            else:
                error_details = response.text
                return f'ERROR: Failed to end call (HTTP {response.status_code}): {error_details}'
                
        except Exception as e:
            return f'ERROR: {str(e)}'
