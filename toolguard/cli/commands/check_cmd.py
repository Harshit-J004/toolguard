"""
toolguard.cli.commands.check_cmd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`toolguard check` — check tool compatibility in a chain.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import click
from rich.console import Console

from toolguard.core.compatibility import check_compatibility
from toolguard.reporters.console import print_compatibility_report

console = Console()


@click.command("check")
@click.option(
    "--tools", "-t",
    type=click.Path(exists=True),
    required=True,
    help="Path to Python file containing tool definitions",
)
@click.option(
    "--functions", "-f",
    type=str,
    default=None,
    help="Comma-separated function names to check (default: all @create_tool functions)",
)
def check_cmd(tools: str, functions: str | None) -> None:
    """🔗 Check tool compatibility in a chain.

    Detects schema conflicts, type mismatches, and missing fields
    between consecutive tools in your chain.
    """

    tools_path = Path(tools)

    # Add directory to sys.path
    tools_dir = str(tools_path.parent.resolve())
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)

    # Import the module
    module_name = tools_path.stem
    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        console.print(f"[red]✗ Failed to import {module_name}: {e}[/]")
        raise click.Abort()

    # Find tool functions
    if functions:
        func_names = [f.strip() for f in functions.split(",")]
        tool_list = []
        for name in func_names:
            func = getattr(mod, name, None)
            if func is None:
                console.print(f"[red]✗ Function '{name}' not found in {module_name}[/]")
                raise click.Abort()
            tool_list.append(func)
    else:
        # Auto-discover all @create_tool decorated functions
        tool_list = [
            getattr(mod, name)
            for name in dir(mod)
            if hasattr(getattr(mod, name), "_toolguard_wrapped")
        ]

    if len(tool_list) < 2:
        console.print("[yellow]⚠️  Need at least 2 tools to check compatibility.[/]")
        raise click.Abort()

    console.print(f"\n🔗 [bold]Checking compatibility:[/] {len(tool_list)} tools")
    console.print(f"   Source: [dim]{tools_path}[/]\n")

    # Run compatibility check
    report = check_compatibility(tool_list)
    print_compatibility_report(report)

    # Exit with error code if incompatible
    if not report.is_compatible:
        raise SystemExit(1)
