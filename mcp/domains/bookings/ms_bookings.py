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
                'name': 'book_online_meeting',
                'tool_class': MSBookOnlineMeetingTool,
                'description': 'After confirming with the client, use this tool to book the meeting online. Gather the following information and ensure you\'ve found staff availability and never book a meeting outside it. When you call the tool try to collect missing information and once you get it send it to this tool.',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'startLocal': {
                            'type': 'string',
                            'description': 'YYYY-MM-DDTHH:mm[:ss] (local wall time)',
                            'examples': ['2025-09-15T14:30:00', '2025-09-15T14:30', '2025-09-15']
                        },
                        'timeZone': {
                            'type': 'string',
                            'description': 'Windows time zone, e.g. \'Canada Central Standard Time\'',
                            'examples': ['Eastern Standard Time', 'Pacific Standard Time', 'Canada Central Standard Time']
                        },
                        'customerName': {
                            'type': 'string',
                            'description': 'Customer full name'
                        },
                        'customerEmail': {
                            'type': 'string',
                            'description': 'Customer email address'
                        },
                        'customerPhone': {
                            'type': 'string',
                            'description': 'Customer phone number (optional, will be formatted to E.164)'
                        },
                        'notes': {
                            'type': 'string',
                            'description': 'Additional notes for the appointment (optional)'
                        },
                        'serviceId': {
                            'type': 'string',
                            'description': 'Service ID (optional, uses tenant default if not provided)'
                        },
                        'durationMinutes': {
                            'type': 'number',
                            'description': 'Meeting duration in minutes (optional, uses service default)'
                        }
                    },
                    'required': ['startLocal', 'timeZone', 'customerName', 'customerEmail']
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
        from asgiref.sync import sync_to_async
        
        if not tenant:
            raise Exception('No tenant provided')
        
        try:
            # Get MS Bookings credentials for this tenant (async database access)
            ms_cred = await sync_to_async(MSBookingsCredential.objects.get)(tenant=tenant, is_active=True)
        except MSBookingsCredential.DoesNotExist:
            raise Exception(f'MS Bookings credentials not configured for tenant: {tenant.name} ({tenant.tenant_id})')
        
        if not ms_cred.azure_tenant_id or not ms_cred.client_id or not ms_cred.client_secret:
            raise Exception(f'MS Bookings credentials incomplete for tenant: {tenant.name}. Missing: azure_tenant_id, client_id, or client_secret')
        
        # Get the decrypted client secret using the model method
        client_secret = ms_cred.get_client_secret()
        
        import httpx
        
        token_url = f"https://login.microsoftonline.com/{ms_cred.azure_tenant_id}/oauth2/v2.0/token"
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': ms_cred.client_id,
            'client_secret': client_secret,
            'scope': 'https://graph.microsoft.com/.default'
        }
        
        try:
            async with httpx.AsyncClient() as client:
                token_response = await client.post(token_url, data=token_data, timeout=10)
                if token_response.status_code != 200:
                    error_details = token_response.text
                    raise Exception(f'Azure token request failed (HTTP {token_response.status_code}): {error_details}')
                
                token_result = token_response.json()
                access_token = token_result.get('access_token')
                
                if not access_token:
                    raise Exception(f'No access token in response: {token_result}')
                
                return access_token
        except httpx.TimeoutException:
            raise Exception('Timeout connecting to Microsoft Azure token endpoint')
        except httpx.RequestError as e:
            raise Exception(f'Network error connecting to Azure: {str(e)}')


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
            if not tenant:
                raise Exception('No tenant found in context')
            
            access_token = await self.provider.get_access_token(tenant)
            
            # Get MS Bookings credentials for business ID and staff IDs
            from ...models import MSBookingsCredential
            from asgiref.sync import sync_to_async
            ms_cred = await sync_to_async(MSBookingsCredential.objects.get)(tenant=tenant, is_active=True)
            
        except Exception as e:
            error_msg = str(e) if str(e) else f'Unknown authentication error: {type(e).__name__}'
            return {
                'error': True,
                'message': f'Failed to authenticate with MS Bookings: {error_msg}',
                'status': None,
                'details': {
                    'tenant_id': tenant.tenant_id if tenant else 'None',
                    'error_type': type(e).__name__
                }
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
            import httpx
            
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
            async with httpx.AsyncClient() as client:
                response = await client.post(
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


class MSBookOnlineMeetingTool(BaseTool):
    """Book an online meeting in Microsoft Bookings with comprehensive date/time handling"""
    
    def _pad(self, n):
        """Pad number to 2 digits"""
        return str(n).zfill(2)
    
    def _to_local_string(self, dt):
        """Convert datetime to local ISO string"""
        return f"{dt.year}-{self._pad(dt.month)}-{self._pad(dt.day)}T{self._pad(dt.hour)}:{self._pad(dt.minute)}:{self._pad(dt.second)}"
    
    def _normalize_start_local(self, input_str):
        """Normalize startLocal input to YYYY-MM-DDTHH:mm:ss format"""
        import re
        from datetime import datetime
        
        if not isinstance(input_str, str) or not input_str.strip():
            raise ValueError('Missing "startLocal"')
        
        s = input_str.strip().replace(" ", "T")
        
        # Full format: YYYY-MM-DDTHH:mm:ss
        if re.match(r'^\d{4}-\d{2}-\d{2}T\d{1,2}:\d{2}:\d{2}$', s):
            date_part, time_part = s.split("T")
            h, m, sec = time_part.split(":")
            return f"{date_part}T{self._pad(int(h))}:{self._pad(int(m))}:{self._pad(int(sec))}"
        
        # Short format: YYYY-MM-DDTHH:mm
        if re.match(r'^\d{4}-\d{2}-\d{2}T\d{1,2}:\d{2}$', s):
            date_part, time_part = s.split("T")
            h, m = time_part.split(":")
            return f"{date_part}T{self._pad(int(h))}:{self._pad(int(m))}:00"
        
        # Date only: YYYY-MM-DD
        if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
            return f"{s}T00:00:00"
        
        # Try parsing as datetime
        try:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
            return self._to_local_string(dt)
        except:
            pass
        
        raise ValueError(f'Invalid startLocal format: {input_str}')
    
    def _add_minutes_local(self, local_iso, minutes):
        """Add minutes to local ISO datetime string"""
        from datetime import datetime, timedelta
        
        # Parse the local ISO string
        y, mo, d = int(local_iso[:4]), int(local_iso[5:7]), int(local_iso[8:10])
        h, m, s = int(local_iso[11:13]), int(local_iso[14:16]), int(local_iso[17:19])
        
        dt = datetime(y, mo, d, h, m, s)
        dt += timedelta(minutes=minutes)
        return self._to_local_string(dt)
    
    def _to_e164_caus(self, phone):
        """Convert phone number to E.164 format for CA/US"""
        if not phone:
            return None
        
        import re
        digits = re.sub(r'\D+', '', str(phone))
        if not digits:
            return None
        
        if len(digits) == 11 and digits.startswith('1'):
            return f"+{digits}"
        if len(digits) == 10:
            return f"+1{digits}"
        return None
    
    def _iso_duration_to_minutes(self, duration):
        """Convert ISO 8601 duration to minutes"""
        import re
        if not isinstance(duration, str):
            return None
        
        match = re.match(r'^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$', duration, re.I)
        if not match:
            return None
        
        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3) or 0)
        seconds = int(match.group(4) or 0)
        
        return days * 1440 + hours * 60 + minutes + (seconds + 59) // 60  # Ceil seconds to minutes
    
    def _to_graph_datetime(self, iso_local, use_utc=False):
        """Convert local ISO to Microsoft Graph datetime format"""
        if not use_utc:
            return iso_local
        
        date_part, time_part = iso_local.split("T")
        hh, mm, ss = time_part.split(":")
        return f"{date_part}T{self._pad(int(hh))}:{self._pad(int(mm))}:{self._pad(int(ss))}.0000000+00:00"
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        from channels.db import database_sync_to_async
        
        try:
            # Get access token using tenant's credentials
            tenant = context.get('tenant')
            access_token = await self.provider.get_access_token(tenant)
        except Exception as e:
            return f'ERROR: Failed to authenticate with MS Bookings: {str(e)}'
        
        try:
            # Extract and validate arguments
            start_local_raw = arguments.get('startLocal') or arguments.get('startISO') or arguments.get('start') or arguments.get('dateTime')
            customer_time_zone = arguments.get('timeZone')
            customer_name = arguments.get('customerName')
            customer_email = arguments.get('customerEmail')
            customer_phone = arguments.get('customerPhone')
            notes = arguments.get('notes')
            
            if not customer_time_zone or not isinstance(customer_time_zone, str):
                return 'ERROR: missing "timeZone"'
            if not customer_name or not customer_email:
                return 'ERROR: missing "customerName" or "customerEmail"'
            
            # Normalize start time
            start_local = self._normalize_start_local(str(start_local_raw))
            
            # Get tenant MS Bookings configuration using sync_to_async
            @database_sync_to_async
            def get_ms_bookings_config(tenant):
                try:
                    ms_cred = tenant.ms_bookings_credential
                    return {
                        'business_id': ms_cred.business_id,
                        'service_id': ms_cred.service_id,
                        'staff_ids': ms_cred.staff_ids or []
                    }
                except Exception as e:
                    raise Exception(f'MS Bookings credentials not configured: {str(e)}')
            
            try:
                config = await get_ms_bookings_config(tenant)
                business_id = config['business_id']
                service_id = arguments.get('serviceId') or config['service_id']
                staff_ids = config['staff_ids']
            except Exception as e:
                return f'ERROR: {str(e)}'
            
            if not business_id:
                return 'ERROR: MS Bookings business ID not configured in tenant credentials'
            if not service_id:
                return 'ERROR: MS Bookings service ID not configured in tenant credentials'
            
            # Get service details
            import httpx
            async with httpx.AsyncClient() as client:
                service_response = await client.get(
                    f"https://graph.microsoft.com/beta/solutions/bookingBusinesses/{business_id}/services/{service_id}",
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=10
                )
                
                if service_response.status_code != 200:
                    return f'ERROR: Failed to get service details: {service_response.text}'
                
                service_data = service_response.json()
                default_dur_mins = self._iso_duration_to_minutes(service_data.get('defaultDuration')) or 30
                
                # Calculate duration
                duration_minutes = arguments.get('durationMinutes')
                if duration_minutes is not None and isinstance(duration_minutes, (int, float)):
                    duration_minutes = int(duration_minutes)
                else:
                    duration_minutes = default_dur_mins
                
                # Calculate end time
                end_local = self._add_minutes_local(start_local, duration_minutes)
                
                # Format phone number
                e164_phone = self._to_e164_caus(customer_phone)
                sms_enabled = bool(e164_phone)
                
                # Build appointment payload
                use_utc = arguments.get('useUTC', False)
                start_time_zone_field = "UTC" if use_utc else (arguments.get('startEndTimeZone') or customer_time_zone)
                
                payload = {
                    "@odata.type": "#microsoft.graph.bookingAppointment",
                    "customerTimeZone": customer_time_zone,
                    "customerName": customer_name,
                    "customerEmailAddress": customer_email,
                    "customerPhone": e164_phone or customer_phone,
                    "customerNotes": notes,
                    "smsNotificationsEnabled": sms_enabled,
                    "end": {
                        "@odata.type": "#microsoft.graph.dateTimeTimeZone",
                        "dateTime": self._to_graph_datetime(end_local, use_utc=use_utc),
                        "timeZone": start_time_zone_field,
                    },
                    "isCustomerAllowedToManageBooking": True,
                    "isLocationOnline": True,
                    "optOutOfCustomerEmail": False,
                    "anonymousJoinWebUrl": None,
                    "postBuffer": arguments.get('postBuffer', 'PT10M'),
                    "preBuffer": arguments.get('preBuffer', 'PT5M'),
                    "price": arguments.get('price', 0.0),
                    "priceType@odata.type": "#microsoft.graph.bookingPriceType",
                    "priceType": arguments.get('priceType', 'free'),
                    "reminders@odata.type": "#Collection(microsoft.graph.bookingReminder)",
                    "reminders": arguments.get('reminders', []),
                    "serviceId": service_id,
                    "serviceName": arguments.get('serviceName', 'Free Consultation with HiQSense'),
                    "serviceNotes": arguments.get('serviceNotes'),
                    "staffMemberIds": arguments.get('staffMemberIds', staff_ids),
                    "start": {
                        "@odata.type": "#microsoft.graph.dateTimeTimeZone",
                        "dateTime": self._to_graph_datetime(start_local, use_utc=use_utc),
                        "timeZone": start_time_zone_field,
                    },
                    "maximumAttendeesCount": arguments.get('maximumAttendeesCount', 1),
                    "filledAttendeesCount": arguments.get('filledAttendeesCount', 1),
                    "customers@odata.type": "#Collection(microsoft.graph.bookingCustomerInformation)",
                    "customers": [
                        {
                            "@odata.type": "#microsoft.graph.bookingCustomerInformation",
                            **({"customerId": arguments['customerId']} if arguments.get('customerId') else {}),
                            "name": customer_name,
                            "emailAddress": customer_email,
                            "phone": e164_phone or customer_phone,
                            "timeZone": customer_time_zone
                        }
                    ],
                }
                
                # Create the appointment
                response = await client.post(
                    f"https://graph.microsoft.com/beta/solutions/bookingBusinesses/{business_id}/appointments",
                    headers={
                        'Authorization': f'Bearer {access_token}',
                        'Content-Type': 'application/json'
                    },
                    json=payload,
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    resp_data = response.json()
                    return json.dumps({
                        "ok": True,
                        "appointmentId": resp_data.get('id'),
                        "joinUrl": resp_data.get('onlineMeetingUrl') or resp_data.get('anonymousJoinWebUrl'),
                        "window": {
                            "startLocal": start_local,
                            "endLocal": end_local,
                            "startEndTimeZone": start_time_zone_field,
                            "customerTimeZone": customer_time_zone
                        },
                        "usedDurationMinutes": duration_minutes,
                        "payloadSent": payload,
                        "response": resp_data
                    })
                else:
                    error_details = response.text
                    request_id = response.headers.get('request-id') or response.headers.get('client-request-id')
                    return f'ERROR: Booking failed (HTTP {response.status_code}){f" [request-id: {request_id}]" if request_id else ""} :: {error_details}'
                
        except Exception as e:
            return f'ERROR: {str(e)}'
