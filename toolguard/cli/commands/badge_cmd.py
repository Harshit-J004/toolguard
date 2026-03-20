"""
toolguard.cli.commands.badge_cmd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
`toolguard badge` — generate a dynamic markdown shield for repository READMEs.
"""

from __future__ import annotations

import click
from rich.console import Console

from toolguard.storage.db import ResultStore

console = Console()

@click.command("badge")
@click.option(
    "--save",
    is_flag=True,
    help="Save the markdown string to the clipboard (macOS/Linux via clip/pbcopy)",
)
def badge_cmd(save: bool) -> None:
    """🛡️ Generate a dynamic Markdown Reliability Badge for your README."""
    
    try:
        store = ResultStore()
        chains = store.get_all_chains()
        store.close()
    except Exception as e:
        console.print(f"[red]✗ Failed to access history database:[/] {e}")
        raise click.Abort()
        
    runs = sum(c["run_count"] for c in chains)
    
    if runs == 0:
        console.print("[yellow]⚠️ No test history found. Run `toolguard test` first.[/]")
        raise SystemExit(0)
        
    total_rel = sum(c["avg_reliability"] * c["run_count"] for c in chains)
    rel = total_rel / runs
    rel_percent = rel * 100
    
    if rel_percent >= 95:
        color = "brightgreen"
    elif rel_percent >= 80:
        color = "yellow"
    else:
        color = "red"
        
    badge_url = f"https://img.shields.io/badge/ToolGuard-{rel_percent:.0f}%25-{color}?logo=shield&style=flat-square"
    markdown = f"![ToolGuard Reliability]({badge_url})"
    
    console.print("\n[bold]🛡️ Generated Reliability Badge:[/]\n")
    console.print(f"Paste this directly into your [cyan]README.md[/] or GitHub PR:\n")
    console.print(f"   [green]{markdown}[/]\n")
    
    console.print(f"(Based on an average score of [bold]{rel_percent:.1f}%[/] across [bold]{runs}[/] runs)")
    
    if save:
        try:
            import pyperclip
            pyperclip.copy(markdown)
            console.print("\n[dim]✨ Copied to clipboard![/]")
        except ImportError:
            console.print("\n[dim]To use the --save flag, install pyperclip: pip install pyperclip[/]")
