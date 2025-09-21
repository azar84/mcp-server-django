"""
General utility tools provider
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List
from ..base import BaseProvider, BaseTool, ProviderType


class GeneralToolsProvider(BaseProvider):
    """General utility tools provider"""
    
    def __init__(self):
        super().__init__(
            name="general",
            provider_type=ProviderType.GENERAL,
            config={}
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return general utility tools"""
        return [
            {
                'name': 'get_server_status',
                'tool_class': ServerStatusTool,
                'description': 'Check if the MCP server is working and get basic server information. Use this when user asks "is the server working", "test connection", or "server status".',
                'input_schema': {
                    'type': 'object',
                    'properties': {},
                    'additionalProperties': False
                },
                'required_scopes': []
            },
            {
                'name': 'current_time',
                'tool_class': CurrentTimeTool,
                'description': 'Get the current server time',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'format': {
                            'type': 'string',
                            'enum': ['iso', 'timestamp', 'human'],
                            'description': 'Time format to return'
                        }
                    }
                },
                'required_scopes': ['basic']
            },
            {
                'name': 'calculator',
                'tool_class': CalculatorTool,
                'description': 'Perform basic mathematical calculations',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'expression': {
                            'type': 'string',
                            'description': 'Mathematical expression to evaluate'
                        }
                    },
                    'required': ['expression']
                },
                'required_scopes': ['basic']
            },
            {
                'name': 'system_info',
                'tool_class': SystemInfoTool,
                'description': 'Get basic system information',
                'input_schema': {
                    'type': 'object',
                    'properties': {}
                },
                'required_scopes': ['admin']
            },
            {
                'name': 'file_operations',
                'tool_class': FileOperationsTool,
                'description': 'Perform tenant-isolated file operations',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'operation': {
                            'type': 'string',
                            'enum': ['read', 'write', 'list', 'exists'],
                            'description': 'File operation to perform'
                        },
                        'path': {
                            'type': 'string',
                            'description': 'File or directory path'
                        },
                        'content': {
                            'type': 'string',
                            'description': 'Content to write (for write operation)'
                        }
                    },
                    'required': ['operation', 'path']
                },
                'required_scopes': ['files']
            },
            {
                'name': 'web_request',
                'tool_class': WebRequestTool,
                'description': 'Make HTTP requests with optional tenant credentials',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'url': {
                            'type': 'string',
                            'description': 'URL to request'
                        },
                        'method': {
                            'type': 'string',
                            'enum': ['GET', 'POST', 'PUT', 'DELETE'],
                            'description': 'HTTP method'
                        },
                        'headers': {
                            'type': 'object',
                            'description': 'HTTP headers'
                        },
                        'data': {
                            'type': 'object',
                            'description': 'Request data (JSON)'
                        }
                    },
                    'required': ['url']
                },
                'required_scopes': ['web']
            },
            {
                'name': 'get_timezone_by_location',
                'tool_class': TimezoneLookupTool,
                'description': 'Get Windows and IANA time zones for a geographic location (city, country, etc.)',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'Location to lookup (city name, "City, Country", etc.)',
                            'examples': ['Saskatoon', 'New York', 'London, UK', 'Tokyo, Japan']
                        }
                    },
                    'required': ['query'],
                    'additionalProperties': False
                },
                'required_scopes': ['basic']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        """General tools don't require specific credentials"""
        return []
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """General tools don't need credential validation"""
        return True


# Tool implementations

class ServerStatusTool(BaseTool):
    """Server status and connection test tool"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        from datetime import datetime
        import platform
        
        tenant_name = context.get('tenant').name if context.get('tenant') else 'Unknown'
        
        status_info = {
            "server_status": "MCP Server is running successfully",
            "connection_test": "PASSED",
            "tenant": tenant_name,
            "timestamp": datetime.now().isoformat(),
            "server_info": {
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "mcp_protocol": "2024-11-05"
            },
            "message": "The MCP server is operational and ready to handle requests"
        }
        
        return json.dumps(status_info, indent=2)


class CurrentTimeTool(BaseTool):
    """Get current server time"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        format_type = arguments.get('format', 'iso')
        now = datetime.now()
        
        if format_type == 'iso':
            return now.isoformat()
        elif format_type == 'timestamp':
            return str(int(now.timestamp()))
        elif format_type == 'human':
            return now.strftime('%Y-%m-%d %H:%M:%S')
        else:
            return now.isoformat()


class CalculatorTool(BaseTool):
    """Basic calculator tool"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        expression = arguments.get('expression')
        
        if not expression:
            return "Error: Expression is required"
        
        try:
            # Security: only allow basic math operations
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in expression):
                return "Error: Expression contains invalid characters"
            
            result = eval(expression)
            return f"{expression} = {result}"
        
        except Exception as e:
            return f"Error evaluating expression: {str(e)}"


class SystemInfoTool(BaseTool):
    """Get system information"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        import platform
        import psutil
        
        tenant_name = context.get('tenant').name if context.get('tenant') else 'Unknown'
        
        info = {
            'tenant': tenant_name,
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'cpu_count': os.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'disk_usage': psutil.disk_usage('/').percent
        }
        
        return json.dumps(info, indent=2)


class FileOperationsTool(BaseTool):
    """File operations with tenant isolation"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        operation = arguments.get('operation')
        path = arguments.get('path')
        
        if not operation or not path:
            return "Error: Both 'operation' and 'path' are required"
        
        # Create tenant-specific directory for isolation
        tenant = context.get('tenant')
        if tenant:
            tenant_dir = f'/tmp/mcp_files/{tenant.tenant_id}'
        else:
            tenant_dir = '/tmp/mcp_files/default'
        
        os.makedirs(tenant_dir, exist_ok=True)
        
        # Ensure path is within tenant directory
        if not path.startswith(tenant_dir):
            path = os.path.join(tenant_dir, os.path.basename(path))
        
        try:
            if operation == 'read':
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        return f.read()
                else:
                    return f"File not found: {path}"
            
            elif operation == 'write':
                content = arguments.get('content', '')
                with open(path, 'w') as f:
                    f.write(content)
                return f"Successfully wrote to {path}"
            
            elif operation == 'list':
                if os.path.isdir(path):
                    files = os.listdir(path)
                    return json.dumps(files, indent=2)
                else:
                    return f"Directory not found: {path}"
            
            elif operation == 'exists':
                return str(os.path.exists(path))
            
            else:
                return f"Unknown operation: {operation}"
        
        except Exception as e:
            return f"Error: {str(e)}"


class WebRequestTool(BaseTool):
    """Make HTTP requests"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        import requests
        
        url = arguments.get('url')
        method = arguments.get('method', 'GET').upper()
        headers = arguments.get('headers', {})
        data = arguments.get('data')
        
        if not url:
            return "Error: URL is required"
        
        # Add tenant credentials if available
        tenant_credentials = context.get('credentials', {})
        if tenant_credentials:
            # Add API key to headers if available
            if 'api_key' in tenant_credentials:
                headers['Authorization'] = f"Bearer {tenant_credentials['api_key']}"
            # Add other credentials as needed
            for key, value in tenant_credentials.items():
                if key.startswith('header_'):
                    header_name = key.replace('header_', '').replace('_', '-')
                    headers[header_name] = value
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data if data else None,
                timeout=10
            )
            
            result = {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'content': response.text[:1000],  # Limit content size
                'tenant': context.get('tenant').name if context.get('tenant') else 'Unknown'
            }
            
            return json.dumps(result, indent=2)
        
        except Exception as e:
            return f"Error making request: {str(e)}"


class TimezoneLookupTool(BaseTool):
    """Get Windows and IANA time zones for a geographic location"""
    
    def _coalesce_city(self, input_str):
        """Extract city name from various input formats"""
        if not input_str or not isinstance(input_str, str):
            return None
        
        s = input_str.strip()
        if not s:
            return None
        
        # Try to parse as JSON first
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                return (obj.get('city') or obj.get('name') or 
                       obj.get('town') or obj.get('locality') or 
                       obj.get('place') or None)
        except:
            pass
        
        # Handle city names with state abbreviations (e.g., "Seattle, WA" -> "Seattle")
        if ',' in s:
            # Split by comma and take the first part (city name)
            city_part = s.split(',')[0].strip()
            return city_part
        
        # Return as string if not JSON and no comma
        return s
    
    async def _geocode_city(self, city):
        """Fetch IANA timezone and country code by city"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    'name': city,
                    'count': 1,
                    'language': 'en',
                    'format': 'json'
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return {'iana': None, 'countryCode': None}
            
            data = response.json()
            hit = data.get('results', [{}])[0] if data.get('results') else {}
            
            return {
                'iana': hit.get('timezone'),
                'countryCode': hit.get('country_code')
            }
    
    def _pick_windows_tz(self, iana, country_code):
        """Convert IANA timezone to Windows timezone using local mapping"""
        from .windows_zones_mapping import get_windows_timezone
        return get_windows_timezone(iana, country_code)
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        try:
            # Extract city from input
            query = arguments.get('query', '')
            city = self._coalesce_city(query)
            
            if not city:
                error_result = {
                    'error': True,
                    'message': 'CITY_NOT_PROVIDED',
                    'windows_timezone': None,
                    'iana_timezone': None
                }
                return json.dumps(error_result)
            
            # Geocode to get IANA timezone and country code
            geocode_result = await self._geocode_city(city)
            iana = geocode_result['iana']
            country_code = geocode_result['countryCode']
            
            if not iana:
                error_result = {
                    'error': True,
                    'message': 'CITY_NOT_FOUND',
                    'windows_timezone': None,
                    'iana_timezone': None,
                    'searched_city': city
                }
                return json.dumps(error_result)
            
            # Get Windows timezone using local mapping
            windows_tz = self._pick_windows_tz(iana, country_code)
            
            result = {
                'error': False,
                'message': 'SUCCESS',
                'searched_city': city,
                'iana_timezone': iana,
                'windows_timezone': windows_tz,
                'country_code': country_code
            }
            return json.dumps(result)
            
        except Exception as e:
            error_result = {
                'error': True,
                'message': f'LOOKUP_FAILED: {str(e)}',
                'windows_timezone': None,
                'iana_timezone': None
            }
            return json.dumps(error_result)
