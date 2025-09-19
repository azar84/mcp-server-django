"""
Knowledge base resource handler
Handles resources like kb://faq/*.md
"""

import os
import glob
from typing import Dict, Any, List, Optional


class KnowledgeBaseResource:
    """Handles knowledge base resources"""
    
    def __init__(self, base_path: str = None):
        self.base_path = base_path or os.path.join(os.path.dirname(__file__), '..', '..', 'kb')
        self.ensure_kb_directory()
    
    def ensure_kb_directory(self):
        """Ensure knowledge base directory exists"""
        os.makedirs(self.base_path, exist_ok=True)
        
        # Create sample FAQ directory and files
        faq_dir = os.path.join(self.base_path, 'faq')
        os.makedirs(faq_dir, exist_ok=True)
        
        # Create sample FAQ files if they don't exist
        sample_files = {
            'general.md': '''# General FAQ

## What is this MCP server?
This is a Django-based Model Context Protocol server that provides domain-organized tools for various business functions.

## How do I authenticate?
Use Bearer token authentication with your tenant ID in the X-Tenant-ID header.
''',
            'booking.md': '''# Booking FAQ

## What booking systems are supported?
- Calendly
- Google Calendar  
- Microsoft Bookings

## How do I set up booking credentials?
Store your provider credentials using the admin API endpoints.
''',
            'payments.md': '''# Payments FAQ

## What payment providers are supported?
- Stripe
- PayPal

## How do I create an invoice?
Use the payments.create_invoice tool with your provider credentials.
'''
        }
        
        for filename, content in sample_files.items():
            file_path = os.path.join(faq_dir, filename)
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    f.write(content)
    
    def resolve_resource(self, resource_uri: str) -> Optional[Dict[str, Any]]:
        """
        Resolve a knowledge base resource URI
        Examples: 
        - kb://faq/*.md
        - kb://faq/general.md
        """
        if not resource_uri.startswith('kb://'):
            return None
        
        # Remove kb:// prefix
        path = resource_uri[5:]
        
        # Handle wildcards
        if '*' in path:
            return self._resolve_wildcard_resource(path)
        else:
            return self._resolve_single_resource(path)
    
    def _resolve_wildcard_resource(self, path: str) -> Dict[str, Any]:
        """Resolve wildcard resource patterns"""
        full_pattern = os.path.join(self.base_path, path)
        matching_files = glob.glob(full_pattern)
        
        resources = []
        for file_path in matching_files:
            if os.path.isfile(file_path):
                relative_path = os.path.relpath(file_path, self.base_path)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                resources.append({
                    'uri': f'kb://{relative_path}',
                    'name': os.path.basename(file_path),
                    'type': 'text/markdown' if file_path.endswith('.md') else 'text/plain',
                    'content': content,
                    'size': len(content)
                })
        
        return {
            'type': 'resource_collection',
            'pattern': f'kb://{path}',
            'count': len(resources),
            'resources': resources
        }
    
    def _resolve_single_resource(self, path: str) -> Optional[Dict[str, Any]]:
        """Resolve a single resource"""
        full_path = os.path.join(self.base_path, path)
        
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            return None
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            'type': 'resource',
            'uri': f'kb://{path}',
            'name': os.path.basename(full_path),
            'mime_type': 'text/markdown' if full_path.endswith('.md') else 'text/plain',
            'content': content,
            'size': len(content),
            'last_modified': os.path.getmtime(full_path)
        }
    
    def list_resources(self, path: str = '') -> List[Dict[str, Any]]:
        """List available resources in a path"""
        full_path = os.path.join(self.base_path, path)
        
        if not os.path.exists(full_path):
            return []
        
        resources = []
        
        if os.path.isdir(full_path):
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                relative_path = os.path.join(path, item) if path else item
                
                if os.path.isdir(item_path):
                    resources.append({
                        'type': 'directory',
                        'uri': f'kb://{relative_path}/',
                        'name': item,
                        'children_count': len(os.listdir(item_path))
                    })
                else:
                    resources.append({
                        'type': 'file',
                        'uri': f'kb://{relative_path}',
                        'name': item,
                        'size': os.path.getsize(item_path),
                        'last_modified': os.path.getmtime(item_path)
                    })
        
        return resources


# Global knowledge base instance
kb_resource = KnowledgeBaseResource()
