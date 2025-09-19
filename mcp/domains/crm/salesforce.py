"""
Salesforce CRM provider
"""

import json
from typing import Dict, Any, List
from ..base import BaseProvider, BaseTool, ProviderType


class SalesforceProvider(BaseProvider):
    """Salesforce CRM system provider"""
    
    def __init__(self):
        super().__init__(
            name="salesforce",
            provider_type=ProviderType.CRM,
            config={
                'api_version': 'v58.0'
            }
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return Salesforce-specific tools"""
        return [
            {
                'name': 'lookup_customer',
                'tool_class': SalesforceLookupCustomerTool,
                'description': 'Look up customer information in Salesforce',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'search_term': {
                            'type': 'string',
                            'description': 'Search term (email, phone, name, or account ID)'
                        },
                        'search_type': {
                            'type': 'string',
                            'enum': ['email', 'phone', 'name', 'account_id'],
                            'description': 'Type of search to perform',
                            'default': 'email'
                        },
                        'include_opportunities': {
                            'type': 'boolean',
                            'description': 'Include related opportunities',
                            'default': False
                        }
                    },
                    'required': ['search_term']
                },
                'required_scopes': ['crm', 'salesforce']
            },
            {
                'name': 'create_lead',
                'tool_class': SalesforceCreateLeadTool,
                'description': 'Create a new lead in Salesforce',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'first_name': {
                            'type': 'string',
                            'description': 'Lead first name'
                        },
                        'last_name': {
                            'type': 'string',
                            'description': 'Lead last name'
                        },
                        'email': {
                            'type': 'string',
                            'description': 'Lead email address'
                        },
                        'phone': {
                            'type': 'string',
                            'description': 'Lead phone number'
                        },
                        'company': {
                            'type': 'string',
                            'description': 'Lead company name'
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Lead job title'
                        },
                        'lead_source': {
                            'type': 'string',
                            'description': 'Source of the lead'
                        }
                    },
                    'required': ['last_name', 'company']
                },
                'required_scopes': ['crm', 'salesforce', 'write']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        """Salesforce requires OAuth token and instance URL"""
        return ['access_token', 'instance_url']
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate Salesforce credentials"""
        access_token = credentials.get('access_token')
        instance_url = credentials.get('instance_url')
        
        if not access_token or not instance_url:
            return False
        
        try:
            import requests
            response = requests.get(
                f"{instance_url}/services/data/{self.config['api_version']}/sobjects/",
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False


class SalesforceLookupCustomerTool(BaseTool):
    """Look up customer information in Salesforce"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        access_token = credentials.get('access_token')
        instance_url = credentials.get('instance_url')
        
        if not access_token or not instance_url:
            return {'error': 'Salesforce credentials not configured'}
        
        search_term = arguments['search_term']
        search_type = arguments.get('search_type', 'email')
        include_opportunities = arguments.get('include_opportunities', False)
        
        try:
            import requests
            
            # Build SOQL query based on search type
            if search_type == 'email':
                query = f"SELECT Id, Name, Email, Phone, BillingAddress FROM Account WHERE PersonEmail = '{search_term}' OR (Id IN (SELECT AccountId FROM Contact WHERE Email = '{search_term}'))"
            elif search_type == 'phone':
                query = f"SELECT Id, Name, Email, Phone, BillingAddress FROM Account WHERE Phone = '{search_term}' OR PersonMobilePhone = '{search_term}'"
            elif search_type == 'name':
                query = f"SELECT Id, Name, Email, Phone, BillingAddress FROM Account WHERE Name LIKE '%{search_term}%'"
            elif search_type == 'account_id':
                query = f"SELECT Id, Name, Email, Phone, BillingAddress FROM Account WHERE Id = '{search_term}'"
            else:
                return {'error': f'Invalid search type: {search_type}'}
            
            # Execute query
            response = requests.get(
                f"{instance_url}/services/data/{self.provider.config['api_version']}/query/",
                headers={'Authorization': f'Bearer {access_token}'},
                params={'q': query},
                timeout=10
            )
            
            if response.status_code != 200:
                return {'error': f'Salesforce query failed: {response.text}'}
            
            query_result = response.json()
            accounts = query_result.get('records', [])
            
            # If including opportunities, fetch them for each account
            result_accounts = []
            for account in accounts:
                account_data = {
                    'id': account['Id'],
                    'name': account['Name'],
                    'email': account.get('Email'),
                    'phone': account.get('Phone'),
                    'billing_address': account.get('BillingAddress'),
                    'opportunities': []
                }
                
                if include_opportunities:
                    opp_query = f"SELECT Id, Name, StageName, Amount, CloseDate FROM Opportunity WHERE AccountId = '{account['Id']}'"
                    opp_response = requests.get(
                        f"{instance_url}/services/data/{self.provider.config['api_version']}/query/",
                        headers={'Authorization': f'Bearer {access_token}'},
                        params={'q': opp_query},
                        timeout=10
                    )
                    
                    if opp_response.status_code == 200:
                        opp_result = opp_response.json()
                        account_data['opportunities'] = opp_result.get('records', [])
                
                result_accounts.append(account_data)
            
            return {
                'provider': 'salesforce',
                'search_term': search_term,
                'search_type': search_type,
                'found_accounts': len(result_accounts),
                'accounts': result_accounts
            }
            
        except Exception as e:
            return {'error': f'Salesforce API error: {str(e)}'}


class SalesforceCreateLeadTool(BaseTool):
    """Create a new lead in Salesforce"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        access_token = credentials.get('access_token')
        instance_url = credentials.get('instance_url')
        
        if not access_token or not instance_url:
            return {'error': 'Salesforce credentials not configured'}
        
        try:
            import requests
            
            # Prepare lead data
            lead_data = {
                'LastName': arguments['last_name'],
                'Company': arguments['company']
            }
            
            # Add optional fields
            if 'first_name' in arguments:
                lead_data['FirstName'] = arguments['first_name']
            if 'email' in arguments:
                lead_data['Email'] = arguments['email']
            if 'phone' in arguments:
                lead_data['Phone'] = arguments['phone']
            if 'title' in arguments:
                lead_data['Title'] = arguments['title']
            if 'lead_source' in arguments:
                lead_data['LeadSource'] = arguments['lead_source']
            
            # Create lead
            response = requests.post(
                f"{instance_url}/services/data/{self.provider.config['api_version']}/sobjects/Lead/",
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                },
                json=lead_data,
                timeout=10
            )
            
            if response.status_code == 201:
                result = response.json()
                return {
                    'provider': 'salesforce',
                    'status': 'created',
                    'lead_id': result['id'],
                    'lead_data': lead_data
                }
            else:
                return {
                    'provider': 'salesforce',
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            return {'error': f'Salesforce lead creation error: {str(e)}'}
