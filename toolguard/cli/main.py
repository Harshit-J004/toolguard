"""
toolguard.cli.main
~~~~~~~~~~~~~~~~~~

Click CLI entrypoint — the `toolguard` command.

Commands:
    toolguard run       Zero-config auto-test a Python script
    toolguard test      Test a tool chain from YAML config
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

from toolguard.cli.commands.check_cmd import check_cmd
from toolguard.cli.commands.history_cmd import history_cmd
from toolguard.cli.commands.init_cmd import init_cmd
from toolguard.cli.commands.observe_cmd import observe_cmd
from toolguard.cli.commands.run_cmd import run_cmd
from toolguard.cli.commands.test_cmd import test_cmd
from toolguard.cli.commands.badge_cmd import badge_cmd
from toolguard.cli.commands.replay_cmd import replay_cmd
from toolguard.cli.commands.proxy_cmd import proxy_cmd
from toolguard.cli.commands.dashboard_cmd import dashboard
from toolguard.cli.commands.drift_cmd import drift_cmd
from toolguard.cli.commands.serve_cmd import serve_cmd

cli.add_command(init_cmd, "init")
cli.add_command(run_cmd, "run")
cli.add_command(test_cmd, "test")
cli.add_command(check_cmd, "check")
cli.add_command(observe_cmd, "observe")
cli.add_command(history_cmd, "history")
cli.add_command(badge_cmd, "badge")
cli.add_command(replay_cmd, "replay")
cli.add_command(proxy_cmd, "proxy")
cli.add_command(dashboard, "dashboard")
cli.add_command(drift_cmd, "drift")
cli.add_command(serve_cmd, "serve")


# ── Standalone version command ───────────────────────────

@cli.command("info")
def info_cmd() -> None:
    """Show ToolGuard banner and version info."""
    print_banner()
    click.echo(f"  Version: {__version__}")
    click.echo("  Docs:    https://toolguard.dev")
    click.echo("  GitHub:  https://github.com/Harshit-J004/toolguard")
    click.echo()


if __name__ == "__main__":
    cli()
