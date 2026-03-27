import sys
from mcp.server.fastmcp import FastMCP

# Initialize the authentic official server
mcp = FastMCP("OfficialTestServer")

@mcp.tool()
def get_weather(location: str) -> str:
    """Get the weather for a location."""
    return f"The weather in {location} is highly sunny!"

@mcp.tool()
def execute_sql(query: str, target: str = "prod") -> str:
    """Execute arbitrary SQL on a target database."""
    return f"Successfully executed: {query} against {target}"

if __name__ == "__main__":
    # Standard stdin/stdout transport is the default for FastMCP.run()
    mcp.run(transport='stdio')
