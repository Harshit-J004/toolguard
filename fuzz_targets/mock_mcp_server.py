"""
Mock MCP Server — A minimal but REAL MCP server for testing the proxy.

This script reads JSON-RPC 2.0 messages from stdin and responds via stdout.
It implements the core MCP lifecycle:
  - initialize
  - tools/list
  - tools/call (read_file, delete_file, search_web)
"""
import json
import sys


TOOLS = [
    {
        "name": "read_file",
        "description": "Read contents of a file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file from the filesystem",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to delete"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_web",
        "description": "Search the internet",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "execute_code",
        "description": "Execute arbitrary code",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Code to execute"}
            },
            "required": ["code"],
        },
    },
]


def handle_message(msg: dict) -> dict | None:
    method = msg.get("method", "")
    request_id = msg.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "mock-mcp-server", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Simulate actual tool execution
        if tool_name == "read_file":
            result_text = f"[MOCK] Contents of {arguments.get('path', '?')}: Hello World!"
        elif tool_name == "delete_file":
            result_text = f"[MOCK] Deleted {arguments.get('path', '?')} successfully."
        elif tool_name == "search_web":
            result_text = f"[MOCK] Search results for '{arguments.get('query', '?')}': 3 results found."
        elif tool_name == "execute_code":
            result_text = f"[MOCK] Code executed: {arguments.get('code', '?')}"
        else:
            result_text = f"[MOCK] Unknown tool: {tool_name}"

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": result_text}],
                "isError": False,
            },
        }

    # Unknown method — return error
    if request_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    return None


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        response = handle_message(msg)
        if response:
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
