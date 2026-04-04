"""
toolguard serve — Launch the HTTP Proxy Sidecar.

Enables any language (TypeScript, Go, Rust, Java) to use ToolGuard's
7-layer security pipeline via a simple HTTP POST.

Usage:
    # Local dev (no auth):
    toolguard serve --policy security.yaml

    # Production (with API key):
    toolguard serve --policy security.yaml --port 8080 --api-key "tg_live_xxx"

    # Enterprise (Redis + API key):
    toolguard serve --policy security.yaml --storage redis://redis:6379/0 --api-key "tg_live_xxx"

    # API key via environment variable:
    export TOOLGUARD_API_KEY="tg_live_xxx"
    toolguard serve --policy security.yaml
"""

from __future__ import annotations

import click


@click.command("serve")
@click.option("--policy", "-p", type=click.Path(), default=None,
              help="Path to the YAML policy file defining security tiers.")
@click.option("--port", type=int, default=8080,
              help="Port to listen on. Default: 8080")
@click.option("--host", type=str, default="0.0.0.0",
              help="Host to bind to. Default: 0.0.0.0")
@click.option("--storage", type=str, default=None,
              help="Storage backend URL. Example: redis://redis:6379/0")
@click.option("--api-key", type=str, default=None,
              help="Bearer token for API authentication. Also reads TOOLGUARD_API_KEY env var.")
@click.option("--reload", is_flag=True, default=False,
              help="Enable auto-reload for development.")
def serve_cmd(policy, port, host, storage, api_key, reload):
    """🌐 Launch the ToolGuard HTTP Proxy Sidecar.
    
    Exposes the full 7-layer security pipeline as an HTTP API.
    Any language (TypeScript, Go, Rust, Java) can use ToolGuard
    by sending a POST request to /v1/intercept.
    """
    try:
        import uvicorn
    except ImportError:
        click.echo("❌ uvicorn is required. Install with: pip install toolguard[server]", err=True)
        raise SystemExit(1)
    
    from toolguard.server.routes import create_app
    
    # Resolve storage URL from CLI flag or environment variable
    resolved_storage = storage or __import__("os").environ.get("TOOLGUARD_STORAGE_URL")
    
    app = create_app(
        policy_path=policy,
        storage_url=resolved_storage,
        api_key=api_key,
    )
    
    auth_mode = "🔒 Bearer Token" if (api_key or __import__("os").environ.get("TOOLGUARD_API_KEY")) else "🔓 Open (local dev)"
    
    click.echo()
    click.echo("=" * 60)
    click.echo("  🛡️  ToolGuard HTTP Proxy Sidecar")
    click.echo("=" * 60)
    click.echo(f"  Endpoint:  http://{host}:{port}/v1/intercept")
    click.echo(f"  Health:    http://{host}:{port}/v1/health")
    click.echo(f"  Docs:      http://{host}:{port}/docs")
    click.echo(f"  Auth:      {auth_mode}")
    click.echo(f"  Storage:   {resolved_storage or 'local (SQLite/JSON)'}")
    click.echo(f"  Policy:    {policy or 'default (permissive)'}")
    click.echo("=" * 60)
    click.echo()
    
    uvicorn.run(app, host=host, port=port, reload=reload, log_level="info")
