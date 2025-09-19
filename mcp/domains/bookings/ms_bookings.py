"""
Microsoft Bookings provider
"""

import json
from typing import Dict, Any, List
from ..base import BaseProvider, BaseTool, ProviderType


class MSBookingsProvider(BaseProvider):
    """Microsoft Bookings system provider"""
    
    def __init__(self):
        super().__init__(
            name="ms_bookings",
            provider_type=ProviderType.BOOKING,
            config={
                'api_base': 'https://graph.microsoft.com/v1.0',
                'scopes': ['https://graph.microsoft.com/Bookings.ReadWrite.All']
            }
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return Microsoft Bookings-specific tools"""
        return [
            {
                'name': 'get_staff_availability',
                'tool_class': MSGetStaffAvailabilityTool,
                'description': 'Get staff availability from Microsoft Bookings for a 7-day window',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'startLocal': {
                            'type': 'string',
                            'description': 'Start date/time in local format (YYYY-MM-DDTHH:mm:ss or YYYY-MM-DD)',
                            'examples': ['2025-09-15T09:00:00', '2025-09-15T9:00', '2025-09-15']
                        },
                        'timeZone': {
                            'type': 'string',
                            'description': 'Windows time zone name',
                            'examples': ['Eastern Standard Time', 'Pacific Standard Time', 'Central Standard Time']
                        },
                        'business_id': {
                            'type': 'string',
                            'description': 'Microsoft Bookings business ID or email (optional, uses tenant default if not provided)'
                        },
                        'staff_ids': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'List of staff member GUIDs (optional, uses tenant default if not provided)'
                        }
                    },
                    'required': ['startLocal', 'timeZone']
                },
                'required_scopes': ['booking', 'ms_bookings']
            },
            {
                'name': 'book_slot',
                'tool_class': MSBookSlotTool,
                'description': 'Create a booking in Microsoft Bookings',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'business_id': {
                            'type': 'string',
                            'description': 'Microsoft Bookings business ID'
                        },
                        'service_id': {
                            'type': 'string',
                            'description': 'Service ID'
                        },
                        'staff_member_ids': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'List of staff member IDs'
                        },
                        'start_time': {
                            'type': 'string',
                            'description': 'Appointment start time (ISO 8601 format)'
                        },
                        'customer_name': {
                            'type': 'string',
                            'description': 'Customer full name'
                        },
                        'customer_email': {
                            'type': 'string',
                            'description': 'Customer email address'
                        },
                        'customer_phone': {
                            'type': 'string',
                            'description': 'Customer phone number'
                        },
                        'notes': {
                            'type': 'string',
                            'description': 'Additional notes for the appointment'
                        }
                    },
                    'required': ['business_id', 'service_id', 'start_time', 'customer_name', 'customer_email']
                },
                'required_scopes': ['booking', 'ms_bookings', 'write']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        """Microsoft Bookings requires Azure tenant ID, client ID, and client secret"""
        return ['azure_tenant_id', 'client_id', 'client_secret']
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate Microsoft Graph credentials by obtaining access token"""
        azure_tenant_id = credentials.get('azure_tenant_id')
        client_id = credentials.get('client_id')
        client_secret = credentials.get('client_secret')
        
        if not all([azure_tenant_id, client_id, client_secret]):
            return False
        
        try:
            import requests
            
            # Get access token using client credentials flow
            token_url = f"https://login.microsoftonline.com/{azure_tenant_id}/oauth2/v2.0/token"
            token_data = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret,
                'scope': 'https://graph.microsoft.com/.default'
            }
            
            token_response = requests.post(token_url, data=token_data, timeout=10)
            if token_response.status_code != 200:
                return False
            
            token_result = token_response.json()
            access_token = token_result.get('access_token')
            
            if not access_token:
                return False
            
            # Test the token by calling Microsoft Graph
            response = requests.get(
                f"{self.config['api_base']}/bookingBusinesses",
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    async def get_access_token(self, tenant) -> str:
        """Get access token using tenant's MS Bookings credentials"""
        from ...models import MSBookingsCredential
        from ...auth import mcp_authenticator
        
        try:
            # Get MS Bookings credentials for this tenant
            ms_cred = MSBookingsCredential.objects.get(tenant=tenant, is_active=True)
        except MSBookingsCredential.DoesNotExist:
            raise Exception('MS Bookings credentials not configured for this tenant')
        
        # Decrypt the client secret
        client_secret = mcp_authenticator.cipher_suite.decrypt(
            ms_cred.client_secret.encode()
        ).decode()
        
        import requests
        
        token_url = f"https://login.microsoftonline.com/{ms_cred.azure_tenant_id}/oauth2/v2.0/token"
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': ms_cred.client_id,
            'client_secret': client_secret,
            'scope': 'https://graph.microsoft.com/.default'
        }
        
        token_response = requests.post(token_url, data=token_data, timeout=10)
        if token_response.status_code != 200:
            raise Exception(f'Failed to get access token: {token_response.text}')
        
        token_result = token_response.json()
        access_token = token_result.get('access_token')
        
        if not access_token:
            raise Exception('No access token returned')
        
        return access_token


class MSGetStaffAvailabilityTool(BaseTool):
    """Get staff availability from Microsoft Bookings for a 7-day window"""
    
    def normalize_start_local(self, input_str: str) -> str:
        """Normalize startLocal input to YYYY-MM-DDTHH:mm:ss format"""
        import re
        from datetime import datetime
        
        if not input_str or not input_str.strip():
            raise ValueError('Missing "startLocal"')
        
        s = input_str.strip()
        
        # Replace space with T
        if ' ' in s:
            s = s.replace(' ', 'T')
        
        # Regex patterns
        re_full = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{1,2}:\d{2}:\d{2}$')
        re_short = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{1,2}:\d{2}$')
        re_date = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        re_has_tz = re.compile(r'(Z|[+-]\d{2}:\d{2})$')
        
        # Full format: ensure 2-digit hour
        if re_full.match(s):
            date_part, time_part = s.split('T')
            h, m, sec = time_part.split(':')
            return f"{date_part}T{int(h):02d}:{int(m):02d}:{int(sec):02d}"
        
        # Short format: add seconds
        if re_short.match(s):
            date_part, time_part = s.split('T')
            h, m = time_part.split(':')
            return f"{date_part}T{int(h):02d}:{int(m):02d}:00"
        
        # Date only: add time
        if re_date.match(s):
            return f"{s}T00:00:00"
        
        # Has timezone: parse and convert to local time
        if re_has_tz.search(s):
            try:
                d = datetime.fromisoformat(s.replace('Z', '+00:00'))
                return d.strftime('%Y-%m-%dT%H:%M:%S')
            except ValueError:
                raise ValueError(f"Invalid ISO with offset: {s}")
        
        # Last attempt: try parsing as datetime
        try:
            d = datetime.fromisoformat(s)
            return d.strftime('%Y-%m-%dT%H:%M:%S')
        except ValueError:
            pass
        
        raise ValueError(f"Invalid startLocal format: {input_str}")
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        try:
            # Get access token and tenant credentials
            tenant = context.get('tenant')
            access_token = await self.provider.get_access_token(tenant)
            
            # Get MS Bookings credentials for business ID and staff IDs
            from ...models import MSBookingsCredential
            ms_cred = MSBookingsCredential.objects.get(tenant=tenant, is_active=True)
            
        except Exception as e:
            return {
                'error': True,
                'message': f'Failed to authenticate with MS Bookings: {str(e)}',
                'status': None,
                'details': None
            }
        
        # Parse arguments
        start_local_input = arguments.get('startLocal')
        time_zone = arguments.get('timeZone')
        business_id = arguments.get('business_id', ms_cred.business_id)
        staff_ids = arguments.get('staff_ids', ms_cred.staff_ids)
        
        if not time_zone:
            return {
                'error': True,
                'message': 'Missing "timeZone" (Windows time zone, e.g., "Eastern Standard Time")',
                'status': None,
                'details': None
            }
        
        try:
            # Normalize start time and compute end time (7 days later)
            start_local = self.normalize_start_local(str(start_local_input))
            
            # Parse start time and add 7 days for end time
            from datetime import datetime, timedelta
            start_dt = datetime.fromisoformat(start_local)
            end_dt = start_dt + timedelta(days=7)
            end_local = end_dt.strftime('%Y-%m-%dT%H:%M:%S')
            
        except ValueError as e:
            return {
                'error': True,
                'message': str(e),
                'status': None,
                'details': None
            }
        
        try:
            import requests
            
            # Prepare payload for MS Bookings getStaffAvailability API
            payload = {
                'staffIds': staff_ids,
                'startDateTime': {
                    'dateTime': start_local,
                    'timeZone': time_zone
                },
                'endDateTime': {
                    'dateTime': end_local,
                    'timeZone': time_zone
                }
            }
            
            # Call MS Bookings getStaffAvailability API
            response = requests.post(
                f"{self.provider.config['api_base']}/solutions/bookingBusinesses/{business_id}/getStaffAvailability",
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                },
                json=payload,
                timeout=30
            )
            
            # Return response in the same format as your JavaScript tool
            if response.status_code == 200:
                api_response = response.json()
                return json.dumps({
                    'ok': True,
                    'businessId': business_id,
                    'staffIds': staff_ids,
                    'window': {
                        'startLocal': start_local,
                        'endLocal': end_local,
                        'timeZone': time_zone
                    },
                    'response': api_response
                })
            else:
                return json.dumps({
                    'error': True,
                    'message': f'MS Bookings API error: HTTP {response.status_code}',
                    'status': response.status_code,
                    'details': response.text
                })
                
        except Exception as e:
            return json.dumps({
                'error': True,
                'message': str(e),
                'status': None,
                'details': None
            })


class MSBookSlotTool(BaseTool):
    """Create a booking in Microsoft Bookings"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        try:
            # Get access token using tenant's credentials
            tenant = context.get('tenant')
            access_token = await self.provider.get_access_token(tenant)
        except Exception as e:
            return {'error': f'Failed to authenticate with MS Bookings: {str(e)}'}
        
        business_id = arguments['business_id']
        service_id = arguments['service_id']
        staff_member_ids = arguments.get('staff_member_ids', [])
        start_time = arguments['start_time']
        customer_name = arguments['customer_name']
        customer_email = arguments['customer_email']
        customer_phone = arguments.get('customer_phone', '')
        notes = arguments.get('notes', '')
        
        try:
            import requests
            from datetime import datetime, timedelta
            
            # Get service duration
            service_response = requests.get(
                f"{self.provider.config['api_base']}/bookingBusinesses/{business_id}/services/{service_id}",
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10
            )
            
            if service_response.status_code != 200:
                return {'error': f'Failed to get service details: {service_response.text}'}
            
            service_data = service_response.json()
            
            # Calculate end time based on service duration
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            duration_iso = service_data.get('defaultDuration', 'PT30M')
            
            # Parse duration
            import re
            duration_match = re.match(r'PT(\d+)M', duration_iso)
            duration_minutes = int(duration_match.group(1)) if duration_match else 30
            end_dt = start_dt + timedelta(minutes=duration_minutes)
            
            # Create appointment data
            appointment_data = {
                'serviceId': service_id,
                'staffMemberIds': staff_member_ids if staff_member_ids else service_data.get('staffMemberIds', []),
                'startTime': {
                    'dateTime': start_time,
                    'timeZone': 'UTC'
                },
                'endTime': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': 'UTC'
                },
                'customerName': customer_name,
                'customerEmailAddress': customer_email,
                'customerPhone': customer_phone,
                'customerNotes': notes
            }
            
            response = requests.post(
                f"{self.provider.config['api_base']}/bookingBusinesses/{business_id}/appointments",
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                },
                json=appointment_data,
                timeout=10
            )
            
            if response.status_code == 201:
                appointment_result = response.json()
                return {
                    'provider': 'ms_bookings',
                    'status': 'booked',
                    'appointment_id': appointment_result['id'],
                    'start_time': start_time,
                    'end_time': end_dt.isoformat(),
                    'service_id': service_id,
                    'customer': {
                        'name': customer_name,
                        'email': customer_email,
                        'phone': customer_phone
                    },
                    'notes': notes
                }
            else:
                return {
                    'provider': 'ms_bookings',
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            return {'error': f'Microsoft Bookings error: {str(e)}'}
