"""
Pipedrive CRM provider
"""

import json
from typing import Dict, Any, List
from ..base import BaseProvider, BaseTool, ProviderType


class PipedriveProvider(BaseProvider):
    """Pipedrive CRM system provider"""
    
    def __init__(self):
        super().__init__(
            name="pipedrive",
            provider_type=ProviderType.CRM,
            config={
                'api_base': 'https://api.pipedrive.com/v1'
            }
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return Pipedrive-specific tools"""
        return [
            {
                'name': 'lookup_customer',
                'tool_class': PipedriveLookupCustomerTool,
                'description': 'Look up customer information in Pipedrive',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'search_term': {
                            'type': 'string',
                            'description': 'Search term (email, phone, name, or person ID)'
                        },
                        'search_type': {
                            'type': 'string',
                            'enum': ['email', 'phone', 'name', 'person_id'],
                            'description': 'Type of search to perform',
                            'default': 'email'
                        },
                        'include_deals': {
                            'type': 'boolean',
                            'description': 'Include related deals',
                            'default': False
                        }
                    },
                    'required': ['search_term']
                },
                'required_scopes': ['crm', 'pipedrive']
            },
            {
                'name': 'create_person',
                'tool_class': PipedriveCreatePersonTool,
                'description': 'Create a new person in Pipedrive',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'name': {
                            'type': 'string',
                            'description': 'Person name'
                        },
                        'email': {
                            'type': 'string',
                            'description': 'Person email address'
                        },
                        'phone': {
                            'type': 'string',
                            'description': 'Person phone number'
                        },
                        'organization_name': {
                            'type': 'string',
                            'description': 'Organization name'
                        },
                        'job_title': {
                            'type': 'string',
                            'description': 'Person job title'
                        }
                    },
                    'required': ['name']
                },
                'required_scopes': ['crm', 'pipedrive', 'write']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        """Pipedrive requires API token and company domain"""
        return ['api_token', 'company_domain']
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate Pipedrive credentials"""
        api_token = credentials.get('api_token')
        company_domain = credentials.get('company_domain')
        
        if not api_token or not company_domain:
            return False
        
        try:
            import requests
            api_base = f"https://{company_domain}.pipedrive.com/api/v1"
            response = requests.get(
                f"{api_base}/users/me",
                params={'api_token': api_token},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False


class PipedriveLookupCustomerTool(BaseTool):
    """Look up customer information in Pipedrive"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        api_token = credentials.get('api_token')
        company_domain = credentials.get('company_domain')
        
        if not api_token or not company_domain:
            return {'error': 'Pipedrive credentials not configured'}
        
        search_term = arguments['search_term']
        search_type = arguments.get('search_type', 'email')
        include_deals = arguments.get('include_deals', False)
        
        try:
            import requests
            
            api_base = f"https://{company_domain}.pipedrive.com/api/v1"
            
            # Search for persons based on search type
            if search_type == 'person_id':
                # Direct person lookup
                response = requests.get(
                    f"{api_base}/persons/{search_term}",
                    params={'api_token': api_token},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    persons = [result['data']] if result['data'] else []
                else:
                    return {'error': f'Person not found: {response.text}'}
            else:
                # Search persons
                search_params = {
                    'api_token': api_token,
                    'term': search_term,
                    'field': 'email' if search_type == 'email' else 'phone' if search_type == 'phone' else 'name',
                    'exact_match': True if search_type in ['email', 'phone'] else False
                }
                
                response = requests.get(
                    f"{api_base}/persons/search",
                    params=search_params,
                    timeout=10
                )
                
                if response.status_code != 200:
                    return {'error': f'Pipedrive search failed: {response.text}'}
                
                search_result = response.json()
                persons = search_result.get('data', {}).get('items', [])
            
            # Process persons and optionally include deals
            result_persons = []
            for person in persons:
                person_data = {
                    'id': person['id'],
                    'name': person.get('name'),
                    'email': person.get('email', [{}])[0].get('value') if person.get('email') else None,
                    'phone': person.get('phone', [{}])[0].get('value') if person.get('phone') else None,
                    'organization': person.get('org_name'),
                    'job_title': person.get('job_title'),
                    'deals': []
                }
                
                if include_deals:
                    # Get deals for this person
                    deals_response = requests.get(
                        f"{api_base}/persons/{person['id']}/deals",
                        params={'api_token': api_token},
                        timeout=10
                    )
                    
                    if deals_response.status_code == 200:
                        deals_result = deals_response.json()
                        deals = deals_result.get('data', [])
                        
                        for deal in deals:
                            person_data['deals'].append({
                                'id': deal['id'],
                                'title': deal.get('title'),
                                'value': deal.get('value'),
                                'currency': deal.get('currency'),
                                'stage_name': deal.get('stage_name'),
                                'status': deal.get('status'),
                                'expected_close_date': deal.get('expected_close_date')
                            })
                
                result_persons.append(person_data)
            
            return {
                'provider': 'pipedrive',
                'search_term': search_term,
                'search_type': search_type,
                'found_persons': len(result_persons),
                'persons': result_persons
            }
            
        except Exception as e:
            return {'error': f'Pipedrive API error: {str(e)}'}


class PipedriveCreatePersonTool(BaseTool):
    """Create a new person in Pipedrive"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        api_token = credentials.get('api_token')
        company_domain = credentials.get('company_domain')
        
        if not api_token or not company_domain:
            return {'error': 'Pipedrive credentials not configured'}
        
        try:
            import requests
            
            api_base = f"https://{company_domain}.pipedrive.com/api/v1"
            
            # Prepare person data
            person_data = {
                'name': arguments['name']
            }
            
            # Add optional fields
            if 'email' in arguments:
                person_data['email'] = [arguments['email']]
            if 'phone' in arguments:
                person_data['phone'] = [arguments['phone']]
            if 'job_title' in arguments:
                person_data['job_title'] = arguments['job_title']
            
            # Handle organization
            if 'organization_name' in arguments:
                # First, try to find existing organization
                org_search_response = requests.get(
                    f"{api_base}/organizations/search",
                    params={
                        'api_token': api_token,
                        'term': arguments['organization_name'],
                        'exact_match': True
                    },
                    timeout=10
                )
                
                if org_search_response.status_code == 200:
                    org_search_result = org_search_response.json()
                    orgs = org_search_result.get('data', {}).get('items', [])
                    
                    if orgs:
                        # Use existing organization
                        person_data['org_id'] = orgs[0]['id']
                    else:
                        # Create new organization
                        org_create_response = requests.post(
                            f"{api_base}/organizations",
                            params={'api_token': api_token},
                            json={'name': arguments['organization_name']},
                            timeout=10
                        )
                        
                        if org_create_response.status_code == 201:
                            org_result = org_create_response.json()
                            person_data['org_id'] = org_result['data']['id']
            
            # Create person
            response = requests.post(
                f"{api_base}/persons",
                params={'api_token': api_token},
                json=person_data,
                timeout=10
            )
            
            if response.status_code == 201:
                result = response.json()
                return {
                    'provider': 'pipedrive',
                    'status': 'created',
                    'person_id': result['data']['id'],
                    'person_data': person_data
                }
            else:
                return {
                    'provider': 'pipedrive',
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            return {'error': f'Pipedrive person creation error: {str(e)}'}
