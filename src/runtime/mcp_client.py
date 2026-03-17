import json
import os
import urllib.request
from urllib.error import URLError

class MCPClient:
    """
    Stub for Model Context Protocol (MCP) Client.
    Currently used to read a local JSON file format and dynamically convert to Nexa Tool Schema.
    """
    def __init__(self, mcp_config_path: str = None):
        self.mcp_config_path = mcp_config_path
        self._tools = {}
        if mcp_config_path and os.path.exists(mcp_config_path):
            self.load_tools(mcp_config_path)

    def load_tools(self, filepath: str):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'tools' in data:
                    for tool in data['tools']:
                        # Convert to Nexa Tool Schema
                        name = tool.get('name')
                        if name:
                            self._tools[name] = {
                                "name": name,
                                "description": tool.get('description', ''),
                                "parameters": tool.get('parameters', {"type": "object", "properties": {}, "required": []})
                            }
        except Exception as e:
            print(f"[MCP] Error loading tools from {filepath}: {str(e)}")

    def get_tools_schema(self):
        return [schema for _, schema in self._tools.items()]

def fetch_mcp_tools(uri: str) -> list[dict]:
    """Fetches MCP tools from a URI (HTTP/HTTPS) or a local file path."""
    import json
    data = {}
    
    try:
        if uri.startswith("http://") or uri.startswith("https://"):
            req = urllib.request.Request(uri, headers={'User-Agent': 'Nexa/0.9'})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8')
                data = json.loads(content)
        else:
            with open(uri, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
        tools = []
        if 'tools' in data:
            for tool in data['tools']:
                name = tool.get('name')
                if name:
                    tools.append({
                        "name": name,
                        "description": tool.get('description', ''),
                        "parameters": tool.get('parameters', {"type": "object", "properties": {}, "required": []})
                    })
        return tools
    except Exception as e:
        print(f"⚠️ [MCP] Failed to fetch tools from {uri}: {e}")
        return []

