"""
Calendly booking provider
"""

import json
import requests
from typing import Dict, Any, List
from ..base import BaseProvider, BaseTool, ProviderType


class CalendlyProvider(BaseProvider):
    """Calendly booking system provider"""
    
    def __init__(self):
        super().__init__(
            name="calendly",
            provider_type=ProviderType.BOOKING,
            config={
                'api_base': 'https://api.calendly.com',
                'api_version': 'v1'
            }
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return Calendly-specific tools"""
        return [
            {
                'name': 'get_staff_availability',
                'tool_class': GetStaffAvailabilityTool,
                'description': 'Get staff availability from Calendly',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'user_uuid': {
                            'type': 'string',
                            'description': 'Calendly user UUID'
                        },
                        'start_time': {
                            'type': 'string',
                            'description': 'Start time (ISO 8601 format)'
                        },
                        'end_time': {
                            'type': 'string',
                            'description': 'End time (ISO 8601 format)'
                        }
                    },
                    'required': ['user_uuid', 'start_time', 'end_time']
                },
                'required_scopes': ['booking', 'calendly']
            },
            {
                'name': 'book_slot',
                'tool_class': BookSlotTool,
                'description': 'Book a time slot in Calendly',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'event_type_uuid': {
                            'type': 'string',
                            'description': 'Calendly event type UUID'
                        },
                        'start_time': {
                            'type': 'string',
                            'description': 'Booking start time (ISO 8601 format)'
                        },
                        'invitee_email': {
                            'type': 'string',
                            'description': 'Invitee email address'
                        },
                        'invitee_name': {
                            'type': 'string',
                            'description': 'Invitee full name'
                        }
                    },
                    'required': ['event_type_uuid', 'start_time', 'invitee_email', 'invitee_name']
                },
                'required_scopes': ['booking', 'calendly', 'write']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        """Calendly requires API token"""
        return ['api_token']
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate Calendly API credentials"""
        api_token = credentials.get('api_token')
        if not api_token:
            return False
        
        try:
            response = requests.get(
                f"{self.config['api_base']}/users/me",
                headers={'Authorization': f'Bearer {api_token}'},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False


class GetStaffAvailabilityTool(BaseTool):
    """Get staff availability from Calendly"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        api_token = credentials.get('api_token')
        if not api_token:
            return {'error': 'Calendly API token not configured'}
        
        user_uuid = arguments['user_uuid']
        start_time = arguments['start_time']
        end_time = arguments['end_time']
        
        try:
            # Get user's event types
            response = requests.get(
                f"{self.provider.config['api_base']}/event_types",
                headers={'Authorization': f'Bearer {api_token}'},
                params={
                    'user': f"https://api.calendly.com/users/{user_uuid}",
                    'active': 'true'
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return {'error': f'Failed to get event types: {response.text}'}
            
            event_types = response.json().get('collection', [])
            
            # Get availability for each event type
            availability_data = []
            for event_type in event_types:
                event_uuid = event_type['uuid']
                
                # Get available times
                avail_response = requests.get(
                    f"{self.provider.config['api_base']}/event_type_available_times",
                    headers={'Authorization': f'Bearer {api_token}'},
                    params={
                        'event_type': event_type['uri'],
                        'start_time': start_time,
                        'end_time': end_time
                    },
                    timeout=10
                )
                
                if avail_response.status_code == 200:
                    available_times = avail_response.json().get('collection', [])
                    availability_data.append({
                        'event_type': event_type['name'],
                        'event_type_uuid': event_uuid,
                        'duration': event_type['duration'],
                        'available_times': available_times
                    })
            
            return {
                'provider': 'calendly',
                'user_uuid': user_uuid,
                'period': {'start': start_time, 'end': end_time},
                'availability': availability_data
            }
            
        except Exception as e:
            return {'error': f'Calendly API error: {str(e)}'}


class BookSlotTool(BaseTool):
    """Book a time slot in Calendly"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        api_token = credentials.get('api_token')
        if not api_token:
            return {'error': 'Calendly API token not configured'}
        
        event_type_uuid = arguments['event_type_uuid']
        start_time = arguments['start_time']
        invitee_email = arguments['invitee_email']
        invitee_name = arguments['invitee_name']
        
        try:
            # Create scheduling link
            booking_data = {
                'event_type': f"https://api.calendly.com/event_types/{event_type_uuid}",
                'start_time': start_time,
                'responses': {
                    'email': invitee_email,
                    'name': invitee_name
                }
            }
            
            response = requests.post(
                f"{self.provider.config['api_base']}/scheduled_events",
                headers={
                    'Authorization': f'Bearer {api_token}',
                    'Content-Type': 'application/json'
                },
                json=booking_data,
                timeout=10
            )
            
            if response.status_code == 201:
                booking_result = response.json()
                return {
                    'provider': 'calendly',
                    'status': 'booked',
                    'booking_id': booking_result['resource']['uuid'],
                    'event_uri': booking_result['resource']['uri'],
                    'start_time': start_time,
                    'invitee': {
                        'email': invitee_email,
                        'name': invitee_name
                    }
                }
            else:
                return {
                    'provider': 'calendly',
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            return {'error': f'Calendly booking error: {str(e)}'}
