"""
Google Calendar booking provider
"""

import json
from typing import Dict, Any, List
from ..base import BaseProvider, BaseTool, ProviderType


class GoogleCalendarProvider(BaseProvider):
    """Google Calendar booking system provider"""
    
    def __init__(self):
        super().__init__(
            name="google_calendar",
            provider_type=ProviderType.BOOKING,
            config={
                'api_base': 'https://www.googleapis.com/calendar/v3',
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return Google Calendar-specific tools"""
        return [
            {
                'name': 'get_staff_availability',
                'tool_class': GoogleGetStaffAvailabilityTool,
                'description': 'Get staff availability from Google Calendar',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'calendar_id': {
                            'type': 'string',
                            'description': 'Google Calendar ID (email or calendar ID)'
                        },
                        'start_time': {
                            'type': 'string',
                            'description': 'Start time (ISO 8601 format)'
                        },
                        'end_time': {
                            'type': 'string',
                            'description': 'End time (ISO 8601 format)'
                        },
                        'duration_minutes': {
                            'type': 'integer',
                            'description': 'Desired appointment duration in minutes',
                            'default': 30
                        }
                    },
                    'required': ['calendar_id', 'start_time', 'end_time']
                },
                'required_scopes': ['booking', 'google_calendar']
            },
            {
                'name': 'book_slot',
                'tool_class': GoogleBookSlotTool,
                'description': 'Create an event in Google Calendar',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'calendar_id': {
                            'type': 'string',
                            'description': 'Google Calendar ID'
                        },
                        'start_time': {
                            'type': 'string',
                            'description': 'Event start time (ISO 8601 format)'
                        },
                        'end_time': {
                            'type': 'string',
                            'description': 'Event end time (ISO 8601 format)'
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Event title'
                        },
                        'description': {
                            'type': 'string',
                            'description': 'Event description'
                        },
                        'attendee_emails': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'List of attendee email addresses'
                        }
                    },
                    'required': ['calendar_id', 'start_time', 'end_time', 'title']
                },
                'required_scopes': ['booking', 'google_calendar', 'write']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        """Google Calendar requires OAuth token or service account key"""
        return ['access_token']  # or 'service_account_json'
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate Google Calendar credentials"""
        access_token = credentials.get('access_token')
        if not access_token:
            return False
        
        try:
            import requests
            response = requests.get(
                f"{self.config['api_base']}/calendars/primary",
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False


class GoogleGetStaffAvailabilityTool(BaseTool):
    """Get staff availability from Google Calendar"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        access_token = credentials.get('access_token')
        if not access_token:
            return {'error': 'Google Calendar access token not configured'}
        
        calendar_id = arguments['calendar_id']
        start_time = arguments['start_time']
        end_time = arguments['end_time']
        duration_minutes = arguments.get('duration_minutes', 30)
        
        try:
            import requests
            from datetime import datetime, timedelta
            
            # Get busy times using freebusy query
            freebusy_data = {
                'timeMin': start_time,
                'timeMax': end_time,
                'items': [{'id': calendar_id}]
            }
            
            response = requests.post(
                f"{self.provider.config['api_base']}/freeBusy",
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                },
                json=freebusy_data,
                timeout=10
            )
            
            if response.status_code != 200:
                return {'error': f'Failed to get calendar data: {response.text}'}
            
            freebusy_result = response.json()
            busy_times = freebusy_result.get('calendars', {}).get(calendar_id, {}).get('busy', [])
            
            # Calculate available slots
            available_slots = self._calculate_available_slots(
                start_time, end_time, busy_times, duration_minutes
            )
            
            return {
                'provider': 'google_calendar',
                'calendar_id': calendar_id,
                'period': {'start': start_time, 'end': end_time},
                'duration_minutes': duration_minutes,
                'busy_times': busy_times,
                'available_slots': available_slots
            }
            
        except Exception as e:
            return {'error': f'Google Calendar API error: {str(e)}'}
    
    def _calculate_available_slots(self, start_time: str, end_time: str, 
                                 busy_times: List[Dict], duration_minutes: int) -> List[Dict]:
        """Calculate available time slots"""
        from datetime import datetime, timedelta
        
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        duration = timedelta(minutes=duration_minutes)
        
        # Convert busy times to datetime objects
        busy_periods = []
        for busy in busy_times:
            busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
            busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
            busy_periods.append((busy_start, busy_end))
        
        # Sort busy periods
        busy_periods.sort(key=lambda x: x[0])
        
        # Find available slots
        available_slots = []
        current_time = start_dt
        
        for busy_start, busy_end in busy_periods:
            # Check if there's a gap before this busy period
            if current_time + duration <= busy_start:
                # Add available slots in this gap
                while current_time + duration <= busy_start:
                    available_slots.append({
                        'start': current_time.isoformat(),
                        'end': (current_time + duration).isoformat()
                    })
                    current_time += timedelta(minutes=15)  # 15-minute increments
            
            # Move past this busy period
            current_time = max(current_time, busy_end)
        
        # Check for slots after the last busy period
        while current_time + duration <= end_dt:
            available_slots.append({
                'start': current_time.isoformat(),
                'end': (current_time + duration).isoformat()
            })
            current_time += timedelta(minutes=15)
        
        return available_slots


class GoogleBookSlotTool(BaseTool):
    """Create an event in Google Calendar"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        access_token = credentials.get('access_token')
        if not access_token:
            return {'error': 'Google Calendar access token not configured'}
        
        calendar_id = arguments['calendar_id']
        start_time = arguments['start_time']
        end_time = arguments['end_time']
        title = arguments['title']
        description = arguments.get('description', '')
        attendee_emails = arguments.get('attendee_emails', [])
        
        try:
            import requests
            
            # Create event data
            event_data = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'UTC'
                },
                'attendees': [{'email': email} for email in attendee_emails]
            }
            
            response = requests.post(
                f"{self.provider.config['api_base']}/calendars/{calendar_id}/events",
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                },
                json=event_data,
                timeout=10
            )
            
            if response.status_code == 200:
                event_result = response.json()
                return {
                    'provider': 'google_calendar',
                    'status': 'booked',
                    'event_id': event_result['id'],
                    'event_link': event_result.get('htmlLink'),
                    'start_time': start_time,
                    'end_time': end_time,
                    'title': title,
                    'attendees': attendee_emails
                }
            else:
                return {
                    'provider': 'google_calendar',
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            return {'error': f'Google Calendar booking error: {str(e)}'}
