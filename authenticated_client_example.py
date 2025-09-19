#!/usr/bin/env python3
"""
Example authenticated MCP client demonstrating tenant-based authentication
"""

import asyncio
import json
import websockets
import requests
from typing import Dict, Any


class AuthenticatedMCPClient:
    """MCP client with authentication support"""
    
    def __init__(self, server_url: str = "localhost:8000", token: str = None, tenant_id: str = None):
        self.base_url = f"http://{server_url}"
        self.ws_url = f"ws://{server_url}/ws/mcp/"
        self.token = token
        self.tenant_id = tenant_id
        self.websocket = None
        self.message_id = 0
    
    async def connect_websocket(self):
        """Connect to MCP server via WebSocket with authentication"""
        if not self.token or not self.tenant_id:
            print("Error: Token and tenant_id are required for WebSocket connection")
            return False
        
        # Add authentication parameters to WebSocket URL
        auth_url = f"{self.ws_url}?token={self.token}&tenant_id={self.tenant_id}"
        
        try:
            self.websocket = await websockets.connect(auth_url)
            print(f"Connected to MCP server as tenant {self.tenant_id}")
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    def _get_auth_headers(self):
        """Get authentication headers for HTTP requests"""
        return {
            'Authorization': f'Bearer {self.token}',
            'X-Tenant-ID': self.tenant_id,
            'Content-Type': 'application/json'
        }
    
    def _next_id(self) -> str:
        """Get next message ID"""
        self.message_id += 1
        return str(self.message_id)
    
    async def send_message(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send MCP message via WebSocket"""
        message = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method
        }
        
        if params:
            message["params"] = params
        
        await self.websocket.send(json.dumps(message))
        response = await self.websocket.recv()
        
        return json.loads(response)
    
    async def initialize(self):
        """Initialize MCP session"""
        params = {
            "protocolVersion": "2024-11-05",
            "clientInfo": {
                "name": "Authenticated Python MCP Client",
                "version": "1.0.0"
            }
        }
        
        response = await self.send_message("initialize", params)
        print("Initialize response:", json.dumps(response, indent=2))
        return response
    
    async def list_tools(self):
        """List available tools (filtered by scopes)"""
        response = await self.send_message("tools/list")
        print("Available tools:", json.dumps(response, indent=2))
        return response
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
        """Call a specific tool"""
        params = {
            "name": tool_name,
            "arguments": arguments
        }
        
        response = await self.send_message("tools/call", params)
        print(f"Tool '{tool_name}' response:", json.dumps(response, indent=2))
        return response
    
    def create_tenant(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new tenant (admin function)"""
        data = {
            'name': name,
            'description': description
        }
        
        response = requests.post(
            f"{self.base_url}/api/admin/tenants/",
            json=data
        )
        
        return response.json()
    
    def create_token(self, tenant_id: str, scopes: list, expires_in_days: int = 30) -> Dict[str, Any]:
        """Create authentication token for a tenant (admin function)"""
        data = {
            'tenant_id': tenant_id,
            'scopes': scopes,
            'expires_in_days': expires_in_days
        }
        
        response = requests.post(
            f"{self.base_url}/api/admin/tokens/",
            json=data
        )
        
        return response.json()
    
    def store_credential(self, tenant_id: str, tool_name: str, credential_key: str, credential_value: str):
        """Store credential for a tenant and tool (admin function)"""
        data = {
            'tenant_id': tenant_id,
            'tool_name': tool_name,
            'credential_key': credential_key,
            'credential_value': credential_value
        }
        
        response = requests.post(
            f"{self.base_url}/api/admin/credentials/",
            json=data
        )
        
        return response.json()
    
    def get_tenant_dashboard(self, tenant_id: str):
        """Get dashboard data for a tenant"""
        response = requests.get(
            f"{self.base_url}/api/admin/dashboard/{tenant_id}/"
        )
        
        return response.json()


async def demo_setup_and_test():
    """Demonstrate complete setup and testing flow"""
    print("=== MCP Server Authentication Demo ===\n")
    
    # Create client instance
    client = AuthenticatedMCPClient()
    
    # Step 1: Create a tenant
    print("1. Creating tenant...")
    tenant_response = client.create_tenant(
        name="Demo Company",
        description="Demo tenant for testing MCP authentication"
    )
    print("Tenant created:", json.dumps(tenant_response, indent=2))
    
    if 'tenant' not in tenant_response:
        print("Failed to create tenant")
        return
    
    tenant_id = tenant_response['tenant']['tenant_id']
    print(f"\nTenant ID: {tenant_id}\n")
    
    # Step 2: Create authentication token with various scopes
    print("2. Creating authentication token...")
    token_response = client.create_token(
        tenant_id=tenant_id,
        scopes=["basic", "files", "web", "api"],  # Grant multiple scopes
        expires_in_days=30
    )
    print("Token created:", json.dumps(token_response, indent=2))
    
    if 'token_info' not in token_response:
        print("Failed to create token")
        return
    
    token = token_response['token_info']['token']
    print(f"\nToken: {token[:20]}...\n")
    
    # Step 3: Store credentials for secure API tool
    print("3. Storing credentials for secure API tool...")
    cred_response = client.store_credential(
        tenant_id=tenant_id,
        tool_name="secure_api",
        credential_key="api_key",
        credential_value="demo-api-key-12345"
    )
    print("Credential stored:", json.dumps(cred_response, indent=2))
    
    # Step 4: Connect with authentication
    print("\n4. Connecting to MCP server with authentication...")
    client.token = token
    client.tenant_id = tenant_id
    
    if not await client.connect_websocket():
        print("Failed to connect to WebSocket")
        return
    
    try:
        # Step 5: Initialize session
        print("\n5. Initializing MCP session...")
        await client.initialize()
        
        # Step 6: List available tools (filtered by scopes)
        print("\n6. Listing available tools...")
        await client.list_tools()
        
        # Step 7: Test various tools
        print("\n7. Testing tools...")
        
        # Test echo tool (no scope required)
        print("\n--- Testing echo tool ---")
        await client.call_tool("echo", {
            "message": "Hello from authenticated client!"
        })
        
        # Test current_time tool (basic scope)
        print("\n--- Testing current_time tool ---")
        await client.call_tool("current_time", {
            "format": "human"
        })
        
        # Test file operations (files scope)
        print("\n--- Testing file_operations tool ---")
        await client.call_tool("file_operations", {
            "operation": "write",
            "path": "test_file.txt",
            "content": "Hello from authenticated tenant!"
        })
        
        await client.call_tool("file_operations", {
            "operation": "read",
            "path": "test_file.txt"
        })
        
        # Test web request (web scope)
        print("\n--- Testing web_request tool ---")
        await client.call_tool("web_request", {
            "url": "https://httpbin.org/get",
            "method": "GET"
        })
        
        # Test secure API (api scope + credentials)
        print("\n--- Testing secure_api tool ---")
        await client.call_tool("secure_api", {
            "endpoint": "user_profile"
        })
        
        # Step 8: Test scope restrictions
        print("\n8. Testing scope restrictions...")
        print("Attempting to call system_info (requires admin scope)...")
        admin_response = await client.call_tool("system_info", {})
        if 'error' in admin_response:
            print("✓ Correctly blocked due to insufficient permissions")
        
    finally:
        await client.websocket.close()
    
    # Step 9: Get tenant dashboard
    print("\n9. Getting tenant dashboard...")
    dashboard = client.get_tenant_dashboard(tenant_id)
    print("Dashboard:", json.dumps(dashboard, indent=2))
    
    print("\n=== Demo completed successfully! ===")


async def demo_multiple_tenants():
    """Demonstrate multi-tenant isolation"""
    print("\n=== Multi-Tenant Isolation Demo ===\n")
    
    client = AuthenticatedMCPClient()
    
    # Create two tenants
    tenant1 = client.create_tenant("Company A", "First tenant")['tenant']
    tenant2 = client.create_tenant("Company B", "Second tenant")['tenant']
    
    # Create tokens with different scopes
    token1_info = client.create_token(tenant1['tenant_id'], ["basic", "files"])['token_info']
    token2_info = client.create_token(tenant2['tenant_id'], ["basic", "web", "admin"])['token_info']
    
    print(f"Tenant 1: {tenant1['name']} - Scopes: basic, files")
    print(f"Tenant 2: {tenant2['name']} - Scopes: basic, web, admin")
    
    # Store different credentials for each tenant
    client.store_credential(tenant1['tenant_id'], "secure_api", "api_key", "tenant1-key")
    client.store_credential(tenant2['tenant_id'], "secure_api", "api_key", "tenant2-key")
    
    print("\nStored different API keys for each tenant")
    print("\n=== Multi-tenant demo setup complete ===")


if __name__ == "__main__":
    print("MCP Server Authentication Demo")
    print("Make sure the Django server is running on localhost:8000")
    print("The server uses in-memory channels (no Redis required)")
    print("Press Ctrl+C to exit\n")
    
    try:
        # Run the main demo
        asyncio.run(demo_setup_and_test())
        
        # Run multi-tenant demo
        asyncio.run(demo_multiple_tenants())
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
