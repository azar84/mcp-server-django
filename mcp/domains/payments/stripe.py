"""
Stripe payments provider
"""

import json
from typing import Dict, Any, List
from ..base import BaseProvider, BaseTool, ProviderType


class StripeProvider(BaseProvider):
    """Stripe payment system provider"""
    
    def __init__(self):
        super().__init__(
            name="stripe",
            provider_type=ProviderType.PAYMENT,
            config={
                'api_base': 'https://api.stripe.com/v1'
            }
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return Stripe-specific tools"""
        return [
            {
                'name': 'create_invoice',
                'tool_class': StripeCreateInvoiceTool,
                'description': 'Create an invoice in Stripe',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'customer_email': {
                            'type': 'string',
                            'description': 'Customer email address'
                        },
                        'customer_name': {
                            'type': 'string',
                            'description': 'Customer name'
                        },
                        'line_items': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'description': {'type': 'string'},
                                    'amount': {'type': 'number'},
                                    'quantity': {'type': 'integer', 'default': 1}
                                },
                                'required': ['description', 'amount']
                            },
                            'description': 'Invoice line items'
                        },
                        'currency': {
                            'type': 'string',
                            'description': 'Currency code (e.g., USD, EUR)',
                            'default': 'USD'
                        },
                        'due_date': {
                            'type': 'string',
                            'description': 'Invoice due date (YYYY-MM-DD)'
                        },
                        'description': {
                            'type': 'string',
                            'description': 'Invoice description'
                        }
                    },
                    'required': ['customer_email', 'line_items']
                },
                'required_scopes': ['payments', 'stripe', 'write']
            },
            {
                'name': 'get_payment_status',
                'tool_class': StripeGetPaymentStatusTool,
                'description': 'Get payment status from Stripe',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'payment_intent_id': {
                            'type': 'string',
                            'description': 'Stripe Payment Intent ID'
                        },
                        'invoice_id': {
                            'type': 'string',
                            'description': 'Stripe Invoice ID'
                        }
                    }
                },
                'required_scopes': ['payments', 'stripe']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        """Stripe requires secret key"""
        return ['secret_key']
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate Stripe credentials"""
        secret_key = credentials.get('secret_key')
        if not secret_key:
            return False
        
        try:
            import requests
            import base64
            
            auth_header = base64.b64encode(f"{secret_key}:".encode()).decode()
            response = requests.get(
                f"{self.config['api_base']}/account",
                headers={'Authorization': f'Basic {auth_header}'},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False


class StripeCreateInvoiceTool(BaseTool):
    """Create an invoice in Stripe"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        secret_key = credentials.get('secret_key')
        if not secret_key:
            return {'error': 'Stripe secret key not configured'}
        
        customer_email = arguments['customer_email']
        customer_name = arguments.get('customer_name', '')
        line_items = arguments['line_items']
        currency = arguments.get('currency', 'USD').lower()
        due_date = arguments.get('due_date')
        description = arguments.get('description', '')
        
        try:
            import requests
            import base64
            from datetime import datetime, timedelta
            
            auth_header = base64.b64encode(f"{secret_key}:".encode()).decode()
            headers = {
                'Authorization': f'Basic {auth_header}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Step 1: Create or get customer
            customer_search_response = requests.get(
                f"{self.provider.config['api_base']}/customers/search",
                headers=headers,
                params={'query': f'email:"{customer_email}"'},
                timeout=10
            )
            
            if customer_search_response.status_code == 200:
                search_result = customer_search_response.json()
                customers = search_result.get('data', [])
                
                if customers:
                    customer_id = customers[0]['id']
                else:
                    # Create new customer
                    customer_data = {
                        'email': customer_email,
                        'name': customer_name
                    }
                    
                    customer_response = requests.post(
                        f"{self.provider.config['api_base']}/customers",
                        headers=headers,
                        data=customer_data,
                        timeout=10
                    )
                    
                    if customer_response.status_code == 200:
                        customer_result = customer_response.json()
                        customer_id = customer_result['id']
                    else:
                        return {'error': f'Failed to create customer: {customer_response.text}'}
            else:
                return {'error': f'Failed to search customers: {customer_search_response.text}'}
            
            # Step 2: Create invoice
            invoice_data = {
                'customer': customer_id,
                'currency': currency,
                'description': description
            }
            
            # Add due date if provided
            if due_date:
                try:
                    due_date_obj = datetime.strptime(due_date, '%Y-%m-%d')
                    invoice_data['due_date'] = int(due_date_obj.timestamp())
                except ValueError:
                    return {'error': 'Invalid due date format. Use YYYY-MM-DD'}
            
            invoice_response = requests.post(
                f"{self.provider.config['api_base']}/invoices",
                headers=headers,
                data=invoice_data,
                timeout=10
            )
            
            if invoice_response.status_code != 200:
                return {'error': f'Failed to create invoice: {invoice_response.text}'}
            
            invoice_result = invoice_response.json()
            invoice_id = invoice_result['id']
            
            # Step 3: Add line items
            for item in line_items:
                # Convert amount to cents
                amount_cents = int(float(item['amount']) * 100)
                quantity = item.get('quantity', 1)
                
                line_item_data = {
                    'invoice': invoice_id,
                    'amount': amount_cents,
                    'currency': currency,
                    'description': item['description'],
                    'quantity': quantity
                }
                
                line_item_response = requests.post(
                    f"{self.provider.config['api_base']}/invoiceitems",
                    headers=headers,
                    data=line_item_data,
                    timeout=10
                )
                
                if line_item_response.status_code != 200:
                    return {'error': f'Failed to add line item: {line_item_response.text}'}
            
            # Step 4: Finalize invoice
            finalize_response = requests.post(
                f"{self.provider.config['api_base']}/invoices/{invoice_id}/finalize",
                headers=headers,
                timeout=10
            )
            
            if finalize_response.status_code == 200:
                final_invoice = finalize_response.json()
                return {
                    'provider': 'stripe',
                    'status': 'created',
                    'invoice_id': invoice_id,
                    'invoice_url': final_invoice.get('hosted_invoice_url'),
                    'invoice_pdf': final_invoice.get('invoice_pdf'),
                    'amount_due': final_invoice.get('amount_due', 0) / 100,
                    'currency': currency.upper(),
                    'customer_email': customer_email,
                    'due_date': due_date
                }
            else:
                return {'error': f'Failed to finalize invoice: {finalize_response.text}'}
                
        except Exception as e:
            return {'error': f'Stripe invoice creation error: {str(e)}'}


class StripeGetPaymentStatusTool(BaseTool):
    """Get payment status from Stripe"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        secret_key = credentials.get('secret_key')
        if not secret_key:
            return {'error': 'Stripe secret key not configured'}
        
        payment_intent_id = arguments.get('payment_intent_id')
        invoice_id = arguments.get('invoice_id')
        
        if not payment_intent_id and not invoice_id:
            return {'error': 'Either payment_intent_id or invoice_id is required'}
        
        try:
            import requests
            import base64
            
            auth_header = base64.b64encode(f"{secret_key}:".encode()).decode()
            headers = {'Authorization': f'Basic {auth_header}'}
            
            if payment_intent_id:
                # Get payment intent status
                response = requests.get(
                    f"{self.provider.config['api_base']}/payment_intents/{payment_intent_id}",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    payment_intent = response.json()
                    return {
                        'provider': 'stripe',
                        'type': 'payment_intent',
                        'id': payment_intent_id,
                        'status': payment_intent.get('status'),
                        'amount': payment_intent.get('amount', 0) / 100,
                        'currency': payment_intent.get('currency', '').upper(),
                        'client_secret': payment_intent.get('client_secret'),
                        'created': payment_intent.get('created')
                    }
                else:
                    return {'error': f'Failed to get payment intent: {response.text}'}
            
            elif invoice_id:
                # Get invoice status
                response = requests.get(
                    f"{self.provider.config['api_base']}/invoices/{invoice_id}",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    invoice = response.json()
                    return {
                        'provider': 'stripe',
                        'type': 'invoice',
                        'id': invoice_id,
                        'status': invoice.get('status'),
                        'amount_due': invoice.get('amount_due', 0) / 100,
                        'amount_paid': invoice.get('amount_paid', 0) / 100,
                        'currency': invoice.get('currency', '').upper(),
                        'customer_email': invoice.get('customer_email'),
                        'hosted_invoice_url': invoice.get('hosted_invoice_url'),
                        'due_date': invoice.get('due_date'),
                        'paid': invoice.get('paid', False)
                    }
                else:
                    return {'error': f'Failed to get invoice: {response.text}'}
                    
        except Exception as e:
            return {'error': f'Stripe status check error: {str(e)}'}
