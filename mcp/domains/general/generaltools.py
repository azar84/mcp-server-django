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
            },
            {
                'name': 'get_resource',
                'tool_class': GetResourceTool,
                'description': 'Use this tool to retrieve the full, authoritative text of a knowledge resource (policies, FAQs, manuals, PDFs, etc.). Provide the URI (e.g., kb://docs/refunds, sp://TENANT/drive/…/item/…). It returns the complete content of that file. Always call this after search_documents (or when you already know the exact URI) instead of guessing. Use the returned text as your source of truth and cite the URI in your answer.',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'uri': {
                            'type': 'string',
                            'description': 'Resource URI to fetch (e.g., "tenant://company-policies", "kb://faq/general.md")',
                            'examples': ['tenant://company-policies', 'tenant://user-manual', 'kb://faq/general.md']
                        }
                    },
                    'required': ['uri'],
                    'additionalProperties': False
                },
                'required_scopes': ['basic']
            },
            {
                'name': 'search_documents',
                'tool_class': SearchDocumentsTool,
                'description': 'Use this tool to look up knowledge documents by keyword or question when you don’t already know the URI. It searches the tenant’s SharePoint knowledge base and returns a ranked list of matching resources with their URIs, titles, and snippets. Call this first to discover which document is relevant, then use get_resource with one of the returned URIs to read the full content.',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'Search query to find relevant documents',
                            'examples': ['work from home policy', 'contact information', 'pricing']
                        },
                        'top_k': {
                            'type': 'integer',
                            'description': 'Maximum number of results to return',
                            'minimum': 1,
                            'maximum': 20,
                            'default': 5
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
            return json.dumps({
                'error': True,
                'message': 'Missing required parameter: expression',
                'error_type': 'missing_parameter',
                'suggestions': [
                    'Provide a mathematical expression to evaluate',
                    'Examples: "2 + 2", "10 * 5", "(3 + 4) * 2"',
                    'Use only numbers and basic operators: +, -, *, /, (, )'
                ],
                'status': None,
                'details': {
                    'missing_parameter': 'expression',
                    'supported_operations': ['addition (+)', 'subtraction (-)', 'multiplication (*)', 'division (/)', 'parentheses ()']
                }
            })
        
        try:
            # Security: only allow basic math operations
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in expression):
                return json.dumps({
                    'error': True,
                    'message': 'Expression contains invalid characters',
                    'error_type': 'invalid_expression',
                    'suggestions': [
                        'Use only numbers (0-9) and basic math operators',
                        'Allowed characters: +, -, *, /, (, ), and spaces',
                        'Examples: "2 + 2", "10 * 5", "(3 + 4) * 2"',
                        'Remove any letters, special symbols, or advanced functions'
                    ],
                    'status': None,
                    'details': {
                        'invalid_expression': expression,
                        'allowed_characters': ['0-9', '+', '-', '*', '/', '(', ')', ' '],
                        'invalid_characters_found': [c for c in expression if c not in allowed_chars]
                    }
                })
            
            result = eval(expression)
            return json.dumps({
                'success': True,
                'expression': expression,
                'result': result,
                'formatted': f"{expression} = {result}"
            })
        
        except ZeroDivisionError:
            return json.dumps({
                'error': True,
                'message': 'Division by zero is not allowed',
                'error_type': 'division_by_zero',
                'suggestions': [
                    'Check your expression for division by zero',
                    'Ensure denominators are not zero',
                    'Example: Use "5/2" instead of "5/0"'
                ],
                'status': None,
                'details': {
                    'expression': expression,
                    'error_type': 'ZeroDivisionError'
                }
            })
        except SyntaxError as e:
            return json.dumps({
                'error': True,
                'message': f'Invalid mathematical expression syntax: {str(e)}',
                'error_type': 'syntax_error',
                'suggestions': [
                    'Check for missing parentheses or operators',
                    'Ensure proper mathematical notation',
                    'Examples: "2 + 2", "10 * 5", "(3 + 4) * 2"',
                    'Avoid complex expressions or functions'
                ],
                'status': None,
                'details': {
                    'expression': expression,
                    'syntax_error': str(e),
                    'error_type': 'SyntaxError'
                }
            })
        except Exception as e:
            return json.dumps({
                'error': True,
                'message': f'Error evaluating expression: {str(e)}',
                'error_type': 'evaluation_error',
                'suggestions': [
                    'Check that the expression is a valid mathematical calculation',
                    'Ensure all parentheses are properly closed',
                    'Try a simpler expression first',
                    'Use only basic arithmetic operations'
                ],
                'status': None,
                'details': {
                    'expression': expression,
                    'error_message': str(e),
                    'error_type': type(e).__name__
                }
            })


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
    
    def _geocode_city(self, city):
        """Fetch IANA timezone and country code by city (synchronous)"""
        import requests
        
        try:
            response = requests.get(
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
        except Exception as e:
            return {'iana': None, 'countryCode': None}
    
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
            geocode_result = self._geocode_city(city)
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
                'message': f'Timezone lookup failed: {str(e)}',
                'error_type': 'lookup_failed',
                'suggestions': [
                    'Try a different city name or location',
                    'Use major city names (e.g., "New York", "London", "Tokyo")',
                    'Check spelling of the city name',
                    'Try using country names if city lookup fails',
                    'Ensure the location exists and is spelled correctly'
                ],
                'status': None,
                'details': {
                    'input_location': arguments.get('location'),
                    'error_message': str(e),
                    'error_type': type(e).__name__
                },
                'windows_timezone': None,
                'iana_timezone': None
            }
            return json.dumps(error_result)


class GetResourceTool(BaseTool):
    """Tool to fetch resource content by URI"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], credentials: Dict[str, str], context: Dict[str, Any]) -> str:
        """Execute the get_resource tool"""
        uri = arguments.get('uri')
        if not uri:
            return json.dumps({
                'error': 'Missing required parameter: uri',
                'example': 'Use uri like "tenant://company-policies" or "kb://faq/general.md"'
            })
        
        tenant = context.get('tenant')
        auth_token = context.get('auth_token')
        
        if not tenant:
            return json.dumps({
                'error': 'Authentication required',
                'message': 'This tool requires tenant authentication',
            })
        
        try:
            # Import here to avoid circular imports
            from ...resources.onedrive import onedrive_resource
            from ...resources.knowledge_base import kb_resource
            
            # Try OneDrive/tenant resources first using asyncio.run to avoid threading issues
            import asyncio
            if onedrive_resource.can_handle(uri):
                resource_data = asyncio.run(onedrive_resource.resolve_resource(uri, tenant, auth_token))
            else:
                # Fallback to knowledge base resources (global)
                resource_data = kb_resource.resolve_resource(uri)
            
            if resource_data is None:
                # List available resources to help the user (now synchronous method)
                available_resources = onedrive_resource.list_resources(tenant)
                available_uris = [r['uri'] for r in available_resources] if available_resources else []
                
                return json.dumps({
                    'error': f'Resource not found: {uri}',
                    'available_resources': available_uris,
                    'suggestion': 'Use search_documents tool to find the right URI first'
                })
            
            # Handle error responses from resource handlers
            if 'error' in resource_data:
                return json.dumps({
                    'error': resource_data['error'],
                    'uri': uri
                })
            
            # Return successful resource data
            content = resource_data.get('content', '')
            
            return json.dumps({
                'success': True,
                'uri': resource_data.get('uri', uri),
                'name': resource_data.get('name', 'Unknown'),
                'description': resource_data.get('description', ''),
                'content': content,
                'content_length': len(content),
                'mime_type': resource_data.get('mime_type', 'text/plain'),
                'tags': resource_data.get('tags', []),
                'source': resource_data.get('source', 'Unknown')
            })
            
        except Exception as e:
            return json.dumps({
                'error': True,
                'message': f'Failed to fetch resource: {str(e)}',
                'error_type': 'resource_fetch_failed',
                'suggestions': [
                    'Check if the URI is correct and exists',
                    'Verify the resource is accessible to your tenant',
                    'Try using search_documents to find available resources',
                    'Ensure the resource URI format is correct (e.g., "tenant://resource-name")',
                    'Contact your administrator if the resource should be available'
                ],
                'status': None,
                'details': {
                    'uri': uri,
                    'error_message': str(e),
                    'error_type': type(e).__name__,
                    'tenant_id': context.get('tenant').tenant_id if context.get('tenant') else 'Unknown'
                }
            })


class SearchDocumentsTool(BaseTool):
    """Tool to search for resources"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], credentials: Dict[str, str], context: Dict[str, Any]) -> str:
        """Execute the search_documents tool"""
        query = arguments.get('query')
        top_k = arguments.get('top_k', 5)
        
        if not query:
            return json.dumps({
                'error': 'Missing required parameter: query',
                'example': 'Use query like "work from home policy" or "contact information"'
            })
        
        tenant = context.get('tenant')
        if not tenant:
            return json.dumps({
                'error': 'Authentication required',
                'message': 'This tool requires tenant authentication',
            })
        
        try:
            # Import here to avoid circular imports
            from ...resources.onedrive import onedrive_resource
            from ...resources.knowledge_base import kb_resource
            
            # Get all tenant resources (now synchronous method)  
            tenant_resources = onedrive_resource.list_resources(tenant)
            
            # Get global knowledge base resources
            kb_resources = kb_resource.list_resources()
            
            # Combine all resources
            all_resources = tenant_resources + [
                {
                    'type': 'resource',
                    'uri': f'kb://{r["name"]}',
                    'name': r['name'],
                    'description': f'Knowledge base: {r["name"]}',
                    'tags': ['kb', 'global'],
                    'resource_type': 'knowledge_base'
                } for r in kb_resources if r['type'] == 'file'
            ]
            
            if not all_resources:
                return json.dumps({
                    'message': 'No documents available to search',
                    'suggestion': 'Add resources in the Django admin panel',
                    'results': []
                })
            
            # Enhanced text-based search (metadata + content)
            query_lower = query.lower()
            scored_resources = []
            
            for resource in all_resources:
                score = 0
                
                # Search in metadata (name, description, tags)
                metadata_text = f"{resource.get('name', '')} {resource.get('description', '')} {' '.join(resource.get('tags', []))}".lower()
                
                # Also search in actual document content for tenant resources
                content_text = ""
                if resource.get('uri', '').startswith('tenant://'):
                    try:
                        # Get the actual document content for search
                        from ...resources.onedrive import onedrive_resource
                        import asyncio
                        resource_data = asyncio.run(onedrive_resource.resolve_resource(resource['uri'], tenant, context.get('auth_token')))
                        if resource_data and resource_data.get('content'):
                            content_text = resource_data['content'].lower()[:5000]  # First 5000 chars for performance
                    except:
                        pass  # If content fetch fails, just search metadata
                
                # Combine metadata and content for search
                searchable_text = f"{metadata_text} {content_text}"
                
                # Score based on query terms
                query_terms = query_lower.split()
                for term in query_terms:
                    if term in searchable_text:
                        # Higher weight for metadata matches
                        if term in metadata_text:
                            score += 3
                        # Lower weight for content matches  
                        if term in content_text:
                            score += 1
                
                if score > 0:
                    scored_resources.append({
                        'resource': resource,
                        'score': score,
                        'relevance': 'high' if score >= 5 else 'medium' if score >= 2 else 'low'
                    })
            
            # Sort by score and limit results
            scored_resources.sort(key=lambda x: x['score'], reverse=True)
            top_results = scored_resources[:top_k]
            
            if not top_results:
                return json.dumps({
                    'message': f'No documents found matching "{query}"',
                    'available_resources': [r['name'] for r in all_resources[:5]],
                    'suggestion': 'Try broader search terms or check available resources',
                    'results': []
                })
            
            # Format results for the agent
            results = []
            for result in top_results:
                resource = result['resource']
                results.append({
                    'uri': resource['uri'],
                    'name': resource.get('name', 'Unknown'),
                    'description': resource.get('description', ''),
                    'tags': resource.get('tags', []),
                    'resource_type': resource.get('resource_type', 'unknown'),
                    'relevance': result['relevance'],
                    'score': result['score']
                })
            
            return json.dumps({
                'success': True,
                'query': query,
                'total_results': len(results),
                'results': results,
                'instruction': 'Use get_resource tool with the URI to read the full content of any document'
            })
            
        except Exception as e:
            return json.dumps({
                'error': True,
                'message': f'Search failed: {str(e)}',
                'error_type': 'search_failed',
                'suggestions': [
                    'Try a simpler or more specific search query',
                    'Use different keywords to describe what you\'re looking for',
                    'Check if resources are available for your tenant',
                    'Try broader search terms if specific searches fail',
                    'Contact your administrator if you expect resources to be available'
                ],
                'status': None,
                'details': {
                    'query': query,
                    'error_message': str(e),
                    'error_type': type(e).__name__,
                    'tenant_id': context.get('tenant').tenant_id if context.get('tenant') else 'Unknown'
                }
            })
