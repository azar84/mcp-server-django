"""
HubSpot CRM provider
"""

import json
from typing import Dict, Any, List
from ..base import BaseProvider, BaseTool, ProviderType


class HubSpotProvider(BaseProvider):
    """HubSpot CRM system provider"""
    
    def __init__(self):
        super().__init__(
            name="hubspot",
            provider_type=ProviderType.CRM,
            config={
                'api_base': 'https://api.hubapi.com'
            }
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return HubSpot-specific tools"""
        return [
            {
                'name': 'lookup_customer',
                'tool_class': HubSpotLookupCustomerTool,
                'description': 'Look up customer information in HubSpot',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'search_term': {
                            'type': 'string',
                            'description': 'Search term (email, phone, company name, or contact ID)'
                        },
                        'search_type': {
                            'type': 'string',
                            'enum': ['email', 'phone', 'company', 'contact_id'],
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
                'required_scopes': ['crm', 'hubspot']
            },
            {
                'name': 'create_contact',
                'tool_class': HubSpotCreateContactTool,
                'description': 'Create a new contact in HubSpot',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'email': {
                            'type': 'string',
                            'description': 'Contact email address'
                        },
                        'first_name': {
                            'type': 'string',
                            'description': 'Contact first name'
                        },
                        'last_name': {
                            'type': 'string',
                            'description': 'Contact last name'
                        },
                        'phone': {
                            'type': 'string',
                            'description': 'Contact phone number'
                        },
                        'company': {
                            'type': 'string',
                            'description': 'Contact company name'
                        },
                        'job_title': {
                            'type': 'string',
                            'description': 'Contact job title'
                        },
                        'lifecycle_stage': {
                            'type': 'string',
                            'enum': ['subscriber', 'lead', 'marketingqualifiedlead', 'salesqualifiedlead', 'opportunity', 'customer'],
                            'description': 'Contact lifecycle stage'
                        }
                    },
                    'required': ['email']
                },
                'required_scopes': ['crm', 'hubspot', 'write']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        """HubSpot requires API key or OAuth token"""
        return ['api_key']  # or 'access_token'
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate HubSpot credentials"""
        api_key = credentials.get('api_key')
        access_token = credentials.get('access_token')
        
        if not api_key and not access_token:
            return False
        
        try:
            import requests
            headers = {}
            if access_token:
                headers['Authorization'] = f'Bearer {access_token}'
            elif api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            
            response = requests.get(
                f"{self.config['api_base']}/crm/v3/objects/contacts",
                headers=headers,
                params={'limit': 1},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False


class HubSpotLookupCustomerTool(BaseTool):
    """Look up customer information in HubSpot"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        api_key = credentials.get('api_key')
        access_token = credentials.get('access_token')
        
        if not api_key and not access_token:
            return {'error': 'HubSpot credentials not configured'}
        
        search_term = arguments['search_term']
        search_type = arguments.get('search_type', 'email')
        include_deals = arguments.get('include_deals', False)
        
        try:
            import requests
            
            headers = {}
            if access_token:
                headers['Authorization'] = f'Bearer {access_token}'
            elif api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            
            # Build search request based on search type
            if search_type == 'email':
                search_url = f"{self.provider.config['api_base']}/crm/v3/objects/contacts/search"
                search_data = {
                    'filterGroups': [{
                        'filters': [{
                            'propertyName': 'email',
                            'operator': 'EQ',
                            'value': search_term
                        }]
                    }],
                    'properties': ['email', 'firstname', 'lastname', 'phone', 'company', 'jobtitle', 'lifecyclestage']
                }
            elif search_type == 'phone':
                search_url = f"{self.provider.config['api_base']}/crm/v3/objects/contacts/search"
                search_data = {
                    'filterGroups': [{
                        'filters': [{
                            'propertyName': 'phone',
                            'operator': 'EQ',
                            'value': search_term
                        }]
                    }],
                    'properties': ['email', 'firstname', 'lastname', 'phone', 'company', 'jobtitle', 'lifecyclestage']
                }
            elif search_type == 'company':
                search_url = f"{self.provider.config['api_base']}/crm/v3/objects/contacts/search"
                search_data = {
                    'filterGroups': [{
                        'filters': [{
                            'propertyName': 'company',
                            'operator': 'CONTAINS_TOKEN',
                            'value': search_term
                        }]
                    }],
                    'properties': ['email', 'firstname', 'lastname', 'phone', 'company', 'jobtitle', 'lifecyclestage']
                }
            elif search_type == 'contact_id':
                # Direct contact lookup
                response = requests.get(
                    f"{self.provider.config['api_base']}/crm/v3/objects/contacts/{search_term}",
                    headers=headers,
                    params={'properties': 'email,firstname,lastname,phone,company,jobtitle,lifecyclestage'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    contact_data = response.json()
                    contacts = [contact_data]
                else:
                    return {'error': f'Contact not found: {response.text}'}
            else:
                return {'error': f'Invalid search type: {search_type}'}
            
            # Execute search (except for direct ID lookup)
            if search_type != 'contact_id':
                response = requests.post(
                    search_url,
                    headers={**headers, 'Content-Type': 'application/json'},
                    json=search_data,
                    timeout=10
                )
                
                if response.status_code != 200:
                    return {'error': f'HubSpot search failed: {response.text}'}
                
                search_result = response.json()
                contacts = search_result.get('results', [])
            
            # Process contacts and optionally include deals
            result_contacts = []
            for contact in contacts:
                contact_props = contact.get('properties', {})
                contact_data = {
                    'id': contact['id'],
                    'email': contact_props.get('email'),
                    'first_name': contact_props.get('firstname'),
                    'last_name': contact_props.get('lastname'),
                    'phone': contact_props.get('phone'),
                    'company': contact_props.get('company'),
                    'job_title': contact_props.get('jobtitle'),
                    'lifecycle_stage': contact_props.get('lifecyclestage'),
                    'deals': []
                }
                
                if include_deals:
                    # Get associated deals
                    deals_response = requests.get(
                        f"{self.provider.config['api_base']}/crm/v3/objects/contacts/{contact['id']}/associations/deals",
                        headers=headers,
                        timeout=10
                    )
                    
                    if deals_response.status_code == 200:
                        deals_result = deals_response.json()
                        deal_ids = [assoc['id'] for assoc in deals_result.get('results', [])]
                        
                        # Get deal details
                        for deal_id in deal_ids:
                            deal_response = requests.get(
                                f"{self.provider.config['api_base']}/crm/v3/objects/deals/{deal_id}",
                                headers=headers,
                                params={'properties': 'dealname,amount,dealstage,closedate'},
                                timeout=10
                            )
                            
                            if deal_response.status_code == 200:
                                deal_data = deal_response.json()
                                deal_props = deal_data.get('properties', {})
                                contact_data['deals'].append({
                                    'id': deal_id,
                                    'name': deal_props.get('dealname'),
                                    'amount': deal_props.get('amount'),
                                    'stage': deal_props.get('dealstage'),
                                    'close_date': deal_props.get('closedate')
                                })
                
                result_contacts.append(contact_data)
            
            return {
                'provider': 'hubspot',
                'search_term': search_term,
                'search_type': search_type,
                'found_contacts': len(result_contacts),
                'contacts': result_contacts
            }
            
        except Exception as e:
            return {'error': f'HubSpot API error: {str(e)}'}


class HubSpotCreateContactTool(BaseTool):
    """Create a new contact in HubSpot"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        api_key = credentials.get('api_key')
        access_token = credentials.get('access_token')
        
        if not api_key and not access_token:
            return {'error': 'HubSpot credentials not configured'}
        
        try:
            import requests
            
            headers = {'Content-Type': 'application/json'}
            if access_token:
                headers['Authorization'] = f'Bearer {access_token}'
            elif api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            
            # Prepare contact data
            contact_properties = {
                'email': arguments['email']
            }
            
            # Add optional fields
            if 'first_name' in arguments:
                contact_properties['firstname'] = arguments['first_name']
            if 'last_name' in arguments:
                contact_properties['lastname'] = arguments['last_name']
            if 'phone' in arguments:
                contact_properties['phone'] = arguments['phone']
            if 'company' in arguments:
                contact_properties['company'] = arguments['company']
            if 'job_title' in arguments:
                contact_properties['jobtitle'] = arguments['job_title']
            if 'lifecycle_stage' in arguments:
                contact_properties['lifecyclestage'] = arguments['lifecycle_stage']
            
            contact_data = {
                'properties': contact_properties
            }
            
            # Create contact
            response = requests.post(
                f"{self.provider.config['api_base']}/crm/v3/objects/contacts",
                headers=headers,
                json=contact_data,
                timeout=10
            )
            
            if response.status_code == 201:
                result = response.json()
                return {
                    'provider': 'hubspot',
                    'status': 'created',
                    'contact_id': result['id'],
                    'contact_properties': contact_properties
                }
            else:
                return {
                    'provider': 'hubspot',
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            return {'error': f'HubSpot contact creation error: {str(e)}'}
