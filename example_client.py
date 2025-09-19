#!/usr/bin/env python3
"""
Example MCP client for testing the Django MCP server
"""

import asyncio
import json
import websockets
import requests
from typing import Dict, Any


class MCPClient:
    """Simple MCP client for testing"""
    
    def __init__(self, server_url: str = "ws://localhost:8000/ws/mcp/"):
        self.server_url = server_url
        self.websocket = None
        self.message_id = 0
    
    async def connect(self):
        """Connect to MCP server via WebSocket"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            print(f"Connected to MCP server at {self.server_url}")
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from MCP server"""
        if self.websocket:
            await self.websocket.close()
            print("Disconnected from MCP server")
    
    def _next_id(self) -> str:
        """Get next message ID"""
        self.message_id += 1
        return str(self.message_id)
    
    async def send_message(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send MCP message and get response"""
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
                "name": "Python MCP Test Client",
                "version": "1.0.0"
            }
        }
        
        response = await self.send_message("initialize", params)
        print("Initialize response:", json.dumps(response, indent=2))
        return response
    
    async def list_tools(self):
        """List available tools"""
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


async def test_websocket_client():
    """Test the MCP server via WebSocket"""
    print("=== Testing MCP Server via WebSocket ===")
    
    client = MCPClient()
    
    if not await client.connect():
        return
    
    try:
        # Initialize session
        await client.initialize()
        print("\n" + "="*50 + "\n")
        
        # List tools
        await client.list_tools()
        print("\n" + "="*50 + "\n")
        
        # Test echo tool
        await client.call_tool("echo", {"message": "Hello from test client!"})
        print("\n" + "="*30 + "\n")
        
        # Test current time tool
        await client.call_tool("current_time", {"format": "human"})
        print("\n" + "="*30 + "\n")
        
        # Test calculator tool
        await client.call_tool("calculator", {"expression": "15 + 27 * 3"})
        print("\n" + "="*30 + "\n")
        
        # Test system info tool
        await client.call_tool("system_info", {})
        print("\n" + "="*30 + "\n")
        
        # Test file operations
        await client.call_tool("file_operations", {
            "operation": "write",
            "path": "test_file.txt",
            "content": "Hello from MCP client!"
        })
        print("\n" + "="*30 + "\n")
        
        await client.call_tool("file_operations", {
            "operation": "read",
            "path": "test_file.txt"
        })
        print("\n" + "="*30 + "\n")
        
    finally:
        await client.disconnect()


def test_http_client():
    """Test the MCP server via HTTP"""
    print("=== Testing MCP Server via HTTP ===")
    
    base_url = "http://localhost:8000"
    
    # Test server info
    print("Getting server info...")
    response = requests.get(f"{base_url}/api/mcp/info/")
    print("Server info:", json.dumps(response.json(), indent=2))
    print("\n" + "="*50 + "\n")
    
    # Test RPC endpoint
    print("Testing RPC endpoint...")
    rpc_data = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/list"
    }
    
    response = requests.post(f"{base_url}/api/mcp/rpc/", json=rpc_data)
    print("RPC response:", json.dumps(response.json(), indent=2))
    print("\n" + "="*30 + "\n")
    
    # Test tool call via RPC
    rpc_data = {
        "jsonrpc": "2.0",
        "id": "2",
        "method": "tools/call",
        "params": {
            "name": "echo",
            "arguments": {
                "message": "Hello via HTTP RPC!"
            }
        }
    }
    
    response = requests.post(f"{base_url}/api/mcp/rpc/", json=rpc_data)
    print("Tool call response:", json.dumps(response.json(), indent=2))
    print("\n" + "="*30 + "\n")
    
    # Test analytics
    print("Getting analytics...")
    response = requests.get(f"{base_url}/api/mcp/analytics/")
    print("Analytics:", json.dumps(response.json(), indent=2))


async def main():
    """Main test function"""
    print("MCP Server Test Client")
    print("Make sure the Django server is running on localhost:8000")
    print("Press Ctrl+C to exit\n")
    
    try:
        # Test HTTP endpoints first
        test_http_client()
        print("\n" + "="*60 + "\n")
        
        # Test WebSocket connection
        await test_websocket_client()
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
