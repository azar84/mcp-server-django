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
                        },
                        'from': {
                            'type': 'string',
                            'description': 'Sender phone number (optional, uses tenant default if not provided)'
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
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        from channels.db import database_sync_to_async
        
        try:
            # Get tenant Twilio configuration
            tenant = context.get('tenant')
            
            @database_sync_to_async
            def get_twilio_config(tenant):
                try:
                    twilio_cred = tenant.twilio_credential
                    return {
                        'account_sid': twilio_cred.account_sid,
                        'auth_token': twilio_cred.get_auth_token(),  # Decrypted
                        'phone_number': twilio_cred.phone_number
                    }
                except Exception as e:
                    raise Exception(f'Twilio credentials not configured: {str(e)}')
            
            try:
                config = await get_twilio_config(tenant)
            except Exception as e:
                return f'ERROR: {str(e)}'
            
            # Extract and validate arguments
            to_number = arguments.get('to')
            message_text = arguments.get('message')
            from_number = arguments.get('from') or config['phone_number']
            
            if not to_number or not message_text:
                return 'ERROR: Both "to" and "message" are required'
            
            # Format phone numbers
            to_formatted = self._format_phone_number(to_number)
            from_formatted = self._format_phone_number(from_number)
            
            if not to_formatted:
                return f'ERROR: Invalid recipient phone number: {to_number}'
            if not from_formatted:
                return f'ERROR: Invalid sender phone number: {from_number}'
            
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
                    error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                    return f'ERROR: SMS sending failed (HTTP {response.status_code}): {error_data}'
                    
            except Exception as e:
                return f'ERROR: Twilio API error: {str(e)}'
                
        except Exception as e:
            return f'ERROR: {str(e)}'


class TwilioGetMessageStatusTool(BaseTool):
    """Get SMS message delivery status from Twilio"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        from channels.db import database_sync_to_async
        
        try:
            # Get tenant Twilio configuration
            tenant = context.get('tenant')
            
            @database_sync_to_async
            def get_twilio_config(tenant):
                try:
                    twilio_cred = tenant.twilio_credential
                    return {
                        'account_sid': twilio_cred.account_sid,
                        'auth_token': twilio_cred.get_auth_token()
                    }
                except Exception as e:
                    raise Exception(f'Twilio credentials not configured: {str(e)}')
            
            try:
                config = await get_twilio_config(tenant)
            except Exception as e:
                return f'ERROR: {str(e)}'
            
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
