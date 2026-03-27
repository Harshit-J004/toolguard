import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("SemanticTestServer")

@mcp.tool()
def read_file(path: str) -> str:
    """Read a file from the filesystem."""
    return f"Contents of {path}: [mock data]"

@mcp.tool()
def execute_sql(query: str) -> str:
    """Execute a SQL query against the database."""
    return f"SQL Result: executed '{query}' successfully"

@mcp.tool()
def send_email(recipient: str, subject: str, body: str) -> str:
    """Send an email to a recipient."""
    return f"Email sent to {recipient}: {subject}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
