"""
toolguard.cli.commands.proxy_cmd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CLI command: `toolguard proxy`

Launches the ToolGuard MCP Security Proxy — a transparent runtime
firewall that sits between any MCP client and any MCP server.

Usage:
    toolguard proxy --upstream "python my_mcp_server.py"
    toolguard proxy --upstream "npx some-mcp-server" --policy policy.yaml
    toolguard proxy --upstream "python server.py" --verbose --log .toolguard/traces
"""

from __future__ import annotations

import click
import shlex


@click.command("proxy")
@click.option(
    "--upstream",
    required=True,
    help="Shell command to spawn the upstream MCP server (e.g. 'python my_server.py').",
)
@click.option(
    "--policy",
    default=None,
    type=click.Path(exists=True),
    help="Path to a YAML policy file defining per-tool security rules.",
)
@click.option(
    "--log",
    "log_dir",
    default=None,
    help="Directory to save JSON execution traces (e.g. .toolguard/mcp_traces/).",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Print interceptor decisions to stderr for debugging.",
)
def proxy_cmd(upstream: str, policy: str | None, log_dir: str | None, verbose: bool) -> None:
    """🛡️  MCP Security Proxy — Runtime firewall for the Model Context Protocol.

    Intercepts all tools/call requests between an MCP client and server,
    applying schema validation, injection scanning, risk-tier gating,
    and rate limiting in real-time.

    \b
    Example:
        toolguard proxy --upstream "python my_mcp_server.py"
        toolguard proxy --upstream "npx @mcp/server" --policy policy.yaml --verbose
    """
    import sys

    from toolguard.mcp.policy import MCPPolicy
    from toolguard.mcp.proxy import MCPProxy

    # Load policy
    if policy:
        loaded_policy = MCPPolicy.from_yaml_file(policy)
        click.echo(f"  🛡️  Loaded policy: {policy}", err=True)
    else:
        loaded_policy = MCPPolicy.default()
        click.echo("  🛡️  Using default policy (scan all, tier-1)", err=True)

    # Parse upstream command
    upstream_cmd = shlex.split(upstream)

    # Create and start the proxy
    proxy = MCPProxy(
        upstream_cmd=upstream_cmd,
        policy=loaded_policy,
        verbose=verbose,
        log_dir=log_dir,
    )

    proxy.start()
