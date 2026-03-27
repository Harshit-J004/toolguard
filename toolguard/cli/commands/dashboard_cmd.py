"""
toolguard.cli.commands.dashboard_cmd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The `toolguard dashboard` CLI command.
"""

import click
import uvicorn
import webbrowser
import threading
import time

@click.command(name="dashboard")
@click.option("--port", default=8555, help="Port to run the dashboard on (default 8555)")
@click.option("--host", default="127.0.0.1", help="Host interface to bind to")
@click.option("--no-browser", is_flag=True, help="Don't open the browser automatically")
def dashboard(port: int, host: str, no_browser: bool):
    """Launch the Live Web Dashboard to monitor MCP traces."""
    url = f"http://{host}:{port}"
    
    # ── Verify Dependencies ──
    try:
        import fastapi
        import uvicorn
        import sse_starlette
    except ImportError:
        click.secho("Missing dashboard dependencies. Please run:", fg="red", bold=True)
        click.secho("  pip install py-toolguard[dashboard]", fg="yellow")
        click.secho("or manually install: pip install fastapi uvicorn sse-starlette\n", fg="yellow")
        raise click.Abort()

    if not no_browser:
        def open_browser():
            time.sleep(1.5)  # Wait for uvicorn to bind
            webbrowser.open(url)
        
        threading.Thread(target=open_browser, daemon=True).start()

    click.secho(f"\n🚀 Starting Live Web Dashboard at {url}", fg="cyan", bold=True)
    click.secho("   Press Ctrl+C to stop the server\n", fg="cyan")
    
    # Run uvicorn programmatically
    uvicorn.run(
        "toolguard.dashboard.server:app",
        host=host,
        port=port,
        log_level="error",  # Keep the terminal clean
    )
