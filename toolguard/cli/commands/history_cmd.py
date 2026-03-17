"""
toolguard.cli.commands.history_cmd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`toolguard history` — View chain reliability history and trends.

Usage:
    toolguard history                      # Show all chains
    toolguard history --chain my_chain     # Show specific chain
    toolguard history --days 7             # Last 7 days
    toolguard history --clear my_chain     # Clear history for a chain
"""

from __future__ import annotations

import click
from rich import box
from rich.console import Console
from rich.table import Table

console = Console()


@click.command("history")
@click.option("--chain", type=str, default=None, help="Chain name to show history for.")
@click.option("--days", type=int, default=30, help="How many days back to look.")
@click.option("--clear", type=str, default=None, help="Clear history for a specific chain.")
@click.option("--db", type=str, default=None, help="Path to database file.")
def history_cmd(chain: str | None, days: int, clear: str | None, db: str | None) -> None:
    """View chain reliability history and trends."""
    from toolguard.storage.db import ResultStore

    store = ResultStore(db_path=db)

    try:
        if clear:
            deleted = store.clear_chain(clear)
            console.print(f"[green]Cleared {deleted} records for '{clear}'[/]")
            return

        if chain:
            _show_chain_detail(store, chain, days)
        else:
            _show_all_chains(store)
    finally:
        store.close()


def _show_all_chains(store) -> None:
    """Show overview of all chains that have been tested."""
    chains = store.get_all_chains()

    if not chains:
        console.print()
        console.print("[dim]No test history found. Run [bold]toolguard test[/] to generate data.[/]")
        console.print()
        return

    table = Table(
        title="📊 Chain Test History",
        box=box.ROUNDED,
        border_style="bright_blue",
    )
    table.add_column("Chain", style="bold cyan")
    table.add_column("Runs", justify="right")
    table.add_column("Latest", justify="right")
    table.add_column("Average", justify="right")
    table.add_column("Last Run", style="dim")

    for c in chains:
        reliability = c["latest_reliability"]
        color = "green" if reliability >= 0.95 else "yellow" if reliability >= 0.80 else "red"
        avg_color = "green" if c["avg_reliability"] >= 0.95 else "yellow" if c["avg_reliability"] >= 0.80 else "red"

        table.add_row(
            c["chain_name"],
            str(c["run_count"]),
            f"[{color}]{reliability:.1%}[/]",
            f"[{avg_color}]{c['avg_reliability']:.1%}[/]",
            c["last_run"][:19] if c["last_run"] else "—",
        )

    console.print()
    console.print(table)
    console.print()


def _show_chain_detail(store, chain_name: str, days: int) -> None:
    """Show detailed history and trend for a specific chain."""
    trend = store.get_reliability_trend(chain_name, days=days)

    if not trend.entries:
        console.print(f"\n[dim]No history found for '[bold]{chain_name}[/]' in the last {days} days.[/]\n")
        return

    console.print()
    console.print(f"[bold cyan]📈 Reliability Trend: {chain_name}[/]")
    console.print()

    # Trend summary
    console.print(f"  Runs:  [bold]{len(trend.entries)}[/]")
    console.print(f"  Avg:   [bold]{trend.average_reliability:.1%}[/]")

    direction = trend.trend_direction
    dir_color = "green" if "improving" in direction else "red" if "declining" in direction else "yellow"
    console.print(f"  Trend: [{dir_color}]{direction}[/]")
    console.print()

    # History table
    table = Table(box=box.SIMPLE_HEAVY, border_style="dim")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Date", style="dim")
    table.add_column("Tests", justify="right")
    table.add_column("Pass", justify="right", style="green")
    table.add_column("Fail", justify="right", style="red")
    table.add_column("Reliability", justify="right")
    table.add_column("Status")

    for i, entry in enumerate(trend.entries, 1):
        color = "green" if entry.reliability >= 0.95 else "yellow" if entry.reliability >= 0.80 else "red"
        table.add_row(
            str(i),
            entry.run_at[:19],
            str(entry.total_tests),
            str(entry.passed),
            str(entry.failed),
            f"[{color}]{entry.reliability_pct}[/]",
            entry.status_icon,
        )

    console.print(table)

    # Sparkline visualization
    if len(trend.entries) >= 3:
        console.print()
        _draw_sparkline(trend)

    console.print()


def _draw_sparkline(trend) -> None:
    """Draw a simple ASCII sparkline of reliability over time."""
    blocks = " ▁▂▃▄▅▆▇█"
    values = [e.reliability for e in trend.entries]

    min_val = min(values)
    max_val = max(values)
    spread = max_val - min_val if max_val > min_val else 1.0

    sparkline = ""
    for v in values:
        idx = int((v - min_val) / spread * (len(blocks) - 1))
        sparkline += blocks[idx]

    console.print(f"  [dim]Trend:[/] [bold cyan]{sparkline}[/]  [dim]({min_val:.0%} → {max_val:.0%})[/]")
