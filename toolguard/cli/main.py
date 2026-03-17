"""
toolguard.cli.main
~~~~~~~~~~~~~~~~~~

Click CLI entrypoint — the `toolguard` command.

Commands:
    toolguard init      Scaffold a new ToolGuard project
    toolguard test      Test a tool chain for reliability
    toolguard check     Check tool compatibility in a chain
    toolguard observe   Show tool execution statistics
    toolguard version   Print version info
"""

from __future__ import annotations

import click

from toolguard import __version__
from toolguard.reporters.console import print_banner


@click.group()
@click.version_option(__version__, prog_name="toolguard")
def cli() -> None:
    """🛡️  ToolGuard — Reliability testing for AI agent tool chains.

    Catch cascading failures before production.
    """
    pass


# ── Register subcommands ─────────────────────────────────

from toolguard.cli.commands.init_cmd import init_cmd
from toolguard.cli.commands.test_cmd import test_cmd
from toolguard.cli.commands.check_cmd import check_cmd
from toolguard.cli.commands.observe_cmd import observe_cmd
from toolguard.cli.commands.history_cmd import history_cmd

cli.add_command(init_cmd, "init")
cli.add_command(test_cmd, "test")
cli.add_command(check_cmd, "check")
cli.add_command(observe_cmd, "observe")
cli.add_command(history_cmd, "history")


# ── Standalone version command ───────────────────────────

@cli.command("info")
def info_cmd() -> None:
    """Show ToolGuard banner and version info."""
    print_banner()
    click.echo(f"  Version: {__version__}")
    click.echo(f"  Docs:    https://toolguard.dev")
    click.echo(f"  GitHub:  https://github.com/toolguard/toolguard")
    click.echo()


if __name__ == "__main__":
    cli()
