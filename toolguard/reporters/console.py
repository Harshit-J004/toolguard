"""
toolguard.reporters.console
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Beautiful Rich terminal output for ToolGuard reports.

Uses the Rich library for color-coded results, tables,
progress bars, and detailed failure panels.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

if TYPE_CHECKING:
    from toolguard.core.report import ChainTestReport, FailureAnalysis
    from toolguard.core.compatibility import CompatibilityReport

console = Console()

_MAX_DISPLAY_LEN = 300  # Max chars for any single string in console output


def _truncate(text: str, max_len: int = _MAX_DISPLAY_LEN) -> str:
    """Safely truncate a string to prevent terminal flooding."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... ({len(text)} chars total)"


# ──────────────────────────────────────────────────────────
#  Chain Test Report
# ──────────────────────────────────────────────────────────

def print_chain_report(report: ChainTestReport) -> None:
    """Render a chain test report to the terminal with Rich formatting."""

    # Header
    status_color = "green" if report.passed_threshold else "red"
    status_icon = "✅" if report.passed_threshold else "❌"

    header = Text()
    header.append("🧪 ", style="bold")
    header.append("Chain Test Report: ", style="bold white")
    header.append(report.chain_name, style="bold cyan")

    console.print()
    console.print(Panel(header, border_style="bright_blue", box=box.DOUBLE))

    # Summary table
    summary = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 2))
    summary.add_column("Metric", style="dim")
    summary.add_column("Value", justify="right")

    summary.add_row("Total Tests", f"[bold]{report.total_tests}[/]")
    summary.add_row("Passed", f"[green]✓ {report.passed}[/]")
    summary.add_row("Failed", f"[red]✗ {report.failed}[/]")
    summary.add_row(
        "Reliability",
        f"[bold {status_color}]{report.reliability:.1%}[/]"
    )
    summary.add_row(
        "Threshold",
        f"[dim]{report.reliability_threshold:.0%}[/]"
    )

    console.print(summary)
    console.print()

    # Failure details
    if report.failure_analyses:
        console.print("[bold red]Top Failures:[/]")
        console.print()

        for i, tf in enumerate(report.top_failures[:5], 1):
            failure_panel = _build_failure_panel(i, tf)
            console.print(failure_panel)
            console.print()

    # Cascade visualization (show first 3 failed runs)
    failed_runs = [r for r in report.runs if not r.success][:3]
    if failed_runs:
        console.print("[bold yellow]Cascade Visualization:[/]")
        for run in failed_runs:
            path = " \u2192 ".join(run.cascade_path)
            console.print(f"   {_truncate(path)}")
        console.print()

    # Final verdict
    verdict = Panel(
        f"[bold {status_color}]{status_icon} {'PASSED' if report.passed_threshold else 'BELOW THRESHOLD'}[/]",
        border_style=status_color,
        box=box.HEAVY,
    )
    console.print(verdict)
    console.print()


def _build_failure_panel(index: int, failure: dict) -> Panel:
    """Build a rich panel for a single failure."""
    content = Text()
    content.append(f"[{failure['count']}x] ", style="bold red")
    content.append(f"{_truncate(failure['tool_name'], 100)}", style="bold yellow")
    content.append(f" \u2192 {_truncate(failure['error_type'], 100)}\n", style="red")
    content.append(f"\n\U0001f50d Root cause: ", style="bold")
    content.append(f"{_truncate(failure['root_cause'])}\n", style="white")
    content.append(f"\n\U0001f4a1 Suggestion: ", style="bold green")
    content.append(f"{_truncate(failure['suggestion'])}", style="green")

    return Panel(
        content,
        title=f"[bold]Failure #{index}[/]",
        border_style="red",
        box=box.ROUNDED,
        padding=(0, 1),
    )


# ──────────────────────────────────────────────────────────
#  Compatibility Report
# ──────────────────────────────────────────────────────────

def print_compatibility_report(report: CompatibilityReport) -> None:
    """Render a compatibility report to the terminal."""

    status = "✅ COMPATIBLE" if report.is_compatible else "❌ INCOMPATIBLE"
    color = "green" if report.is_compatible else "red"

    header = Text()
    header.append("🔗 ", style="bold")
    header.append("Compatibility Check: ", style="bold white")
    header.append(" → ".join(report.tools_checked), style="bold cyan")

    console.print()
    console.print(Panel(header, border_style="bright_blue", box=box.DOUBLE))

    if report.issues:
        table = Table(box=box.ROUNDED, border_style="dim")
        table.add_column("Level", style="bold", width=8)
        table.add_column("Connection", style="cyan")
        table.add_column("Issue", style="white")
        table.add_column("Suggestion", style="green")

        for issue in report.issues:
            level_icon = "❌" if issue.level == "error" else "⚠️" if issue.level == "warning" else "ℹ️"
            level_color = "red" if issue.level == "error" else "yellow" if issue.level == "warning" else "blue"

            table.add_row(
                f"[{level_color}]{level_icon} {issue.level.upper()}[/]",
                f"{issue.source_tool} → {issue.target_tool}",
                issue.message,
                issue.suggestion,
            )

        console.print(table)
    else:
        console.print("  [green]No issues found! All tools are compatible.[/]")

    console.print()
    console.print(Panel(
        f"[bold {color}]{status}[/]",
        border_style=color,
        box=box.HEAVY,
    ))
    console.print()


# ──────────────────────────────────────────────────────────
#  Tool Stats
# ──────────────────────────────────────────────────────────

def print_tool_stats(tools: list) -> None:
    """Print a table of tool statistics from GuardedTool instances."""

    table = Table(
        title="🔧 Tool Statistics",
        box=box.ROUNDED,
        border_style="bright_blue",
    )
    table.add_column("Tool", style="bold cyan")
    table.add_column("Calls", justify="right")
    table.add_column("Success", justify="right", style="green")
    table.add_column("Failures", justify="right", style="red")
    table.add_column("Success Rate", justify="right")
    table.add_column("Avg Latency", justify="right")

    for tool in tools:
        stats = getattr(tool, "stats", None)
        if stats is None:
            continue

        rate = stats.success_rate
        rate_color = "green" if rate >= 0.95 else "yellow" if rate >= 0.80 else "red"

        table.add_row(
            getattr(tool, "__name__", "unknown"),
            str(stats.total_calls),
            str(stats.success_count),
            str(stats.failure_count),
            f"[{rate_color}]{rate:.1%}[/]",
            f"{stats.avg_latency_ms:.1f}ms",
        )

    console.print()
    console.print(table)
    console.print()


# ──────────────────────────────────────────────────────────
#  Welcome Banner
# ──────────────────────────────────────────────────────────

def print_banner() -> None:
    """Print the ToolGuard ASCII banner."""
    banner = """
╔══════════════════════════════════════════════════╗
║                                                  ║
║   ████████╗ ██████╗  ██████╗ ██╗                 ║
║   ╚══██╔══╝██╔═══██╗██╔═══██╗██║                 ║
║      ██║   ██║   ██║██║   ██║██║                 ║
║      ██║   ██║   ██║██║   ██║██║                 ║
║      ██║   ╚██████╔╝╚██████╔╝███████╗            ║
║      ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝            ║
║                                                  ║
║     ██████╗ ██╗   ██╗ █████╗ ██████╗ ██████╗     ║
║    ██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔══██╗    ║
║    ██║  ███╗██║   ██║███████║██████╔╝██║  ██║    ║
║    ██║   ██║██║   ██║██╔══██║██╔══██╗██║  ██║    ║
║    ╚██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝    ║
║     ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝    ║
║                                                  ║
║  Reliability testing for AI agent tool chains    ║
║  v0.1.0                                         ║
║                                                  ║
╚══════════════════════════════════════════════════╝
"""
    console.print(banner, style="bold bright_blue")
