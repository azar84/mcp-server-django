"""
SendGrid email provider (structure only)
"""

from typing import Dict, Any, List
from ..base import BaseProvider, ProviderType


class SendGridProvider(BaseProvider):
    """SendGrid email system provider"""
    
    def __init__(self):
        super().__init__(
            name="sendgrid",
            provider_type=ProviderType.EMAIL,
            config={
                'api_base': 'https://api.sendgrid.com/v3'
            }
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return SendGrid tool definitions (structure only)"""
        return [
            {
                'name': 'send_email',
                'description': 'Send email via SendGrid',
                'required_scopes': ['email', 'sendgrid', 'write']
            },
            {
                'name': 'get_email_stats',
                'description': 'Get email delivery statistics',
                'required_scopes': ['email', 'sendgrid']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        return ['api_key']
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        # Validation logic would go here
        return True
