"""
Mailgun email provider (structure only)
"""

from typing import Dict, Any, List
from ..base import BaseProvider, ProviderType


class MailgunProvider(BaseProvider):
    """Mailgun email system provider"""
    
    def __init__(self):
        super().__init__(
            name="mailgun",
            provider_type=ProviderType.EMAIL,
            config={
                'api_base': 'https://api.mailgun.net/v3'
            }
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return Mailgun tool definitions (structure only)"""
        return [
            {
                'name': 'send_email',
                'description': 'Send email via Mailgun',
                'required_scopes': ['email', 'mailgun', 'write']
            },
            {
                'name': 'get_delivery_stats',
                'description': 'Get email delivery statistics',
                'required_scopes': ['email', 'mailgun']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        return ['api_key', 'domain']
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        # Validation logic would go here
        return True
