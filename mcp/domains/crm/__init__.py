"""
CRM domain providers
Supports multiple CRM systems: Salesforce, HubSpot, Pipedrive, etc.
"""

from .salesforce import SalesforceProvider
from .hubspot import HubSpotProvider
from .pipedrive import PipedriveProvider

__all__ = ['SalesforceProvider', 'HubSpotProvider', 'PipedriveProvider']
