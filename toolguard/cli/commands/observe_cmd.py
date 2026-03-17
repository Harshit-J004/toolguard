"""
toolguard.cli.commands.observe_cmd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`toolguard observe` — show tool execution statistics.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import click
from rich.console import Console

from toolguard.reporters.console import print_tool_stats

console = Console()


@click.command("observe")
@click.option(
    "--tools", "-t",
    type=click.Path(exists=True),
    default=None,
    help="Path to Python file containing tool definitions",
)
@click.option(
    "--demo",
    is_flag=True,
    default=False,
    help="Run a demo showing example tool statistics",
)
def observe_cmd(tools: str | None, demo: bool) -> None:
    """📊 Show tool execution statistics.

    Displays success rates, latency, and failure counts for
    all instrumented tools.
    """

    if demo:
        _run_demo()
        return

    if tools is None:
        console.print("[yellow]⚠️  Specify --tools path or use --demo for example output.[/]")
        console.print("[dim]  Usage: toolguard observe --tools my_tools.py[/]")
        return

    tools_path = Path(tools)
    tools_dir = str(tools_path.parent.resolve())
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)

    module_name = tools_path.stem
    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        console.print(f"[red]✗ Failed to import {module_name}: {e}[/]")
        raise click.Abort()

    # Find all GuardedTool instances
    tool_list = [
        getattr(mod, name)
        for name in dir(mod)
        if hasattr(getattr(mod, name), "_toolguard_wrapped")
    ]

    if not tool_list:
        console.print("[yellow]⚠️  No @create_tool decorated functions found.[/]")
        return

    console.print(f"\n📊 [bold]Tool Statistics[/] — {tools_path.name}\n")
    print_tool_stats(tool_list)


def _run_demo() -> None:
    """Run a demo with simulated tool stats."""
    from toolguard.core.validator import create_tool

    @create_tool(schema="auto")
    def get_weather(location: str = "NYC", units: str = "metric") -> dict:
        return {"temp": 22.5, "units": units}

    @create_tool(schema="auto")
    def process_forecast(temp: float = 0.0, units: str = "metric") -> dict:
        return {"forecast": f"It's {temp}°", "severity": "low"}

    @create_tool(schema="auto")
    def send_alert(forecast: str = "", severity: str = "low") -> dict:
        return {"sent": True}

    # Simulate some calls
    import random
    demo_tools = [get_weather, process_forecast, send_alert]

    for _ in range(100):
        for tool in demo_tools:
            try:
                if random.random() < 0.92:  # 92% success rate simulation
                    tool.stats.record_success(random.uniform(50, 500))
                else:
                    tool.stats.record_failure(random.uniform(500, 2000))
            except Exception:
                pass

    console.print("\n📊 [bold]Demo Tool Statistics[/] (simulated data)\n")
    print_tool_stats(demo_tools)
