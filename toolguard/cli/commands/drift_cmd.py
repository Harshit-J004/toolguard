"""
toolguard.cli.commands.drift_cmd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`toolguard drift` — Schema drift detection for LLM outputs.

Subcommands:
    toolguard drift snapshot    Create a baseline fingerprint from a JSON file
    toolguard drift check       Compare live output against stored fingerprint
    toolguard drift list        Show all stored fingerprints
    toolguard drift clear       Remove stored fingerprints
"""

from __future__ import annotations

import json
import os
import sys

import click
from rich.console import Console

from toolguard.core.drift import (
    create_fingerprint, 
    detect_drift, 
    infer_schema,
    create_fingerprint_from_model
)
from toolguard.core.drift_store import FingerprintStore

# Fix Windows console encoding for emoji/unicode output
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

console = Console(force_terminal=True)


@click.group("drift")
def drift_cmd() -> None:
    """🔬 Schema drift detection for LLM outputs.

    Detects when an LLM provider silently changes its structured
    output format by comparing live outputs against frozen baselines.
    """
    pass


# ──────────────────────────────────────────────────────────
#  toolguard drift snapshot
# ──────────────────────────────────────────────────────────

@drift_cmd.command("snapshot")
@click.option(
    "--output-file", "-o",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to a JSON file containing the LLM output to fingerprint.",
)
@click.option(
    "--tool", "-t",
    type=str,
    required=True,
    help="Name of the tool this output belongs to.",
)
@click.option(
    "--model", "-m",
    type=str,
    required=True,
    help="Model identifier (e.g., 'gpt-5.4', 'gemini-3.1-flash').",
)
@click.option(
    "--prompt", "-p",
    type=str,
    default="(not specified)",
    help="The prompt that generated this output.",
)
def snapshot_cmd(output_file: str, tool: str, model: str, prompt: str) -> None:
    """📸 Create a baseline schema fingerprint from a JSON file.

    Reads a JSON file containing an LLM's structured output and
    freezes its inferred schema as a baseline for future drift checks.

    Example:
        toolguard drift snapshot -o weather_output.json -t get_weather -m gpt-5.4
    """
    # Load the JSON output
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            output = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]✗ Invalid JSON in {output_file}: {e}[/]")
        raise click.Abort()

    # Create fingerprint
    fp = create_fingerprint(
        tool_name=tool,
        prompt=prompt,
        model=model,
        output=output,
    )

    # Store it
    with FingerprintStore() as store:
        store.save_fingerprint(fp)

    # Pretty print
    console.print()
    console.print(f"[bold green]📸 Fingerprint Created[/]")
    console.print(f"   Tool:     [cyan]{fp.tool_name}[/]")
    console.print(f"   Model:    [cyan]{fp.model}[/]")
    console.print(f"   Checksum: [dim]{fp.checksum}[/]")
    console.print(f"   Fields:   [white]{_count_fields(fp.json_schema)}[/]")
    console.print(f"   Stored:   [dim].toolguard/drift.db[/]")
    console.print()

    # Show inferred schema
    schema_str = json.dumps(fp.json_schema, indent=2)
    console.print("[bold]Inferred Schema:[/]")
    console.print(f"[dim]{schema_str}[/]")
    console.print()


# ──────────────────────────────────────────────────────────
#  toolguard drift snapshot-pydantic
# ──────────────────────────────────────────────────────────

@drift_cmd.command("snapshot-pydantic")
@click.option(
    "--target", "-T",
    type=str,
    required=True,
    help="Python import path to Pydantic model (e.g., 'my_agent.models:WeatherResponse').",
)
@click.option(
    "--tool", "-t",
    type=str,
    required=True,
    help="Name of the tool this schema belongs to.",
)
@click.option(
    "--model", "-m",
    type=str,
    required=True,
    help="Model identifier this schema applies to.",
)
def snapshot_pydantic_cmd(target: str, tool: str, model: str) -> None:
    """📸 Freeze a JSON schema baseline directly from a Pydantic model.

    This bridges the gap between static type definitions and dynamic AI outputs.
    Instead of calling an LLM to generate a baseline, ToolGuard extracts the schema
    natively from your Python class so you can enforce strict contracts in CI/CD.
    """
    import importlib
    import sys

    # Add current dir to path so local modules import correctly
    sys.path.insert(0, os.getcwd())

    try:
        module_path, class_name = target.split(":")
    except ValueError:
        console.print(f"[bold red]✗ Invalid target format: '{target}'[/]")
        console.print("[dim]Must be 'module.path:ClassName'[/]")
        raise click.Abort()

    try:
        module = importlib.import_module(module_path)
        pydantic_model = getattr(module, class_name)
    except Exception as e:
        console.print(f"[bold red]✗ Failed to load Pydantic model: {e}[/]")
        raise click.Abort()

    console.print(f"Loading native Pydantic definitions from [blue]{target}[/]...\n")

    try:
        fp = create_fingerprint_from_model(
            tool_name=tool,
            model=model,
            pydantic_model=pydantic_model,
        )
    except Exception as e:
        console.print(f"[bold red]✗ Schema extraction failed: {e}[/]")
        raise click.Abort()

    with FingerprintStore() as store:
        store.save_fingerprint(fp)

    console.print(f"[bold green]✅ Pydantic-native Fingerprint stored securely![/]")
    console.print(f"   Tool:     [cyan]{fp.tool_name}[/]")
    console.print(f"   Model:    [cyan]{fp.model}[/]")
    console.print(f"   Checksum: [dim]{fp.checksum}[/]")
    console.print(f"   Fields:   [white]{_count_fields(fp.json_schema)}[/]")
    console.print(f"   Stored:   [dim].toolguard/drift.db[/]")
    console.print()

    # Show inferred schema
    schema_str = json.dumps(fp.json_schema, indent=2)
    console.print("[bold]Extracted Schema:[/]")
    console.print(f"[dim]{schema_str}[/]")
    console.print()


# ──────────────────────────────────────────────────────────
#  toolguard drift check
# ──────────────────────────────────────────────────────────

@drift_cmd.command("check")
@click.option(
    "--output-file", "-o",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to a JSON file containing the new LLM output to compare.",
)
@click.option(
    "--tool", "-t",
    type=str,
    required=True,
    help="Name of the tool to check drift for.",
)
@click.option(
    "--model", "-m",
    type=str,
    required=True,
    help="Model identifier to compare against.",
)
@click.option(
    "--fail-on-drift", is_flag=True, default=False,
    help="Exit with code 1 if drift is detected (for CI/CD pipelines).",
)
def check_cmd(output_file: str, tool: str, model: str, fail_on_drift: bool) -> None:
    """🔍 Check for schema drift against a stored fingerprint.

    Compares a new LLM output against the baseline fingerprint and
    reports every structural deviation: added/removed fields, type
    changes, format changes.

    Example:
        toolguard drift check -o new_weather_output.json -t get_weather -m gpt-5.4
        toolguard drift check -o output.json -t my_tool -m gpt-5.4 --fail-on-drift
    """
    # Load new output
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            live_output = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]✗ Invalid JSON in {output_file}: {e}[/]")
        raise click.Abort()

    # Load stored fingerprint
    with FingerprintStore() as store:
        fp = store.get_fingerprint(tool, model)

    if fp is None:
        console.print(f"[red]✗ No stored fingerprint found for tool='{tool}', model='{model}'[/]")
        console.print(f"[dim]  Run 'toolguard drift snapshot' first to create a baseline.[/]")
        raise click.Abort()

    # Detect drift
    report = detect_drift(fp, live_output)

    # Print report
    _print_drift_report(report)

    # CI/CD gate
    if fail_on_drift and report.has_drift:
        raise SystemExit(1)


# ──────────────────────────────────────────────────────────
#  toolguard drift list
# ──────────────────────────────────────────────────────────

@drift_cmd.command("list")
def list_cmd() -> None:
    """📋 List all stored schema fingerprints."""
    from rich.table import Table
    from rich import box

    with FingerprintStore() as store:
        fingerprints = store.get_all_fingerprints()

    if not fingerprints:
        console.print("[yellow]No fingerprints stored yet.[/]")
        console.print("[dim]Run 'toolguard drift snapshot' to create one.[/]")
        return

    table = Table(
        title="🔬 Stored Schema Fingerprints",
        box=box.ROUNDED,
        border_style="bright_blue",
    )
    table.add_column("Tool", style="bold cyan")
    table.add_column("Model", style="white")
    table.add_column("Checksum", style="dim")
    table.add_column("Fields", justify="right")
    table.add_column("Created", style="dim")

    for fp in fingerprints:
        table.add_row(
            fp.tool_name,
            fp.model,
            fp.checksum,
            str(_count_fields(fp.json_schema)),
            fp.timestamp,
        )

    console.print()
    console.print(table)
    console.print()


# ──────────────────────────────────────────────────────────
#  toolguard drift clear
# ──────────────────────────────────────────────────────────

@drift_cmd.command("clear")
@click.option("--tool", "-t", type=str, required=True, help="Tool name to clear.")
@click.option("--model", "-m", type=str, required=True, help="Model to clear.")
@click.confirmation_option(prompt="Are you sure you want to delete this fingerprint?")
def clear_cmd(tool: str, model: str) -> None:
    """🗑️  Delete a stored fingerprint."""
    with FingerprintStore() as store:
        deleted = store.delete_fingerprint(tool, model)

    if deleted:
        console.print(f"[green]✓ Deleted {deleted} fingerprint(s) for {tool}/{model}[/]")
    else:
        console.print(f"[yellow]No fingerprints found for {tool}/{model}[/]")


# ──────────────────────────────────────────────────────────
#  Rich Drift Report Printer
# ──────────────────────────────────────────────────────────

def _print_drift_report(report) -> None:
    """Render a DriftReport to the terminal with Rich formatting."""
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    console.print()

    if not report.has_drift:
        console.print(Panel(
            f"[bold green]✅ No Schema Drift Detected[/]\n\n"
            f"  Tool:     [cyan]{report.tool_name}[/]\n"
            f"  Model:    [cyan]{report.model}[/]\n"
            f"  Checksum: [dim]{report.fingerprint_checksum}[/]",
            border_style="green",
            box=box.HEAVY,
            title="[bold]Drift Check[/]",
        ))
        console.print()
        return

    # Drift detected — show warning
    severity_color = {
        "critical": "red",
        "major": "yellow",
        "minor": "blue",
    }.get(report.severity, "white")

    console.print(Panel(
        f"[bold {severity_color}]⚠️  SCHEMA DRIFT DETECTED[/]\n\n"
        f"  Tool:       [cyan]{report.tool_name}[/]\n"
        f"  Model:      [cyan]{report.model}[/]\n"
        f"  Severity:   [bold {severity_color}]{report.severity.upper()}[/]\n"
        f"  Baseline:   [dim]{report.fingerprint_checksum}[/]\n"
        f"  Live:       [dim]{report.live_checksum}[/]",
        border_style=severity_color,
        box=box.HEAVY,
        title="[bold]Drift Check[/]",
    ))

    # Drift details table
    table = Table(
        box=box.ROUNDED,
        border_style="dim",
        title="[bold]Field-Level Analysis[/]",
    )
    table.add_column("Field", style="bold cyan")
    table.add_column("Drift Type", style="white")
    table.add_column("Expected", style="green")
    table.add_column("Actual", style="red")
    table.add_column("Severity", style="bold")

    for d in report.drifts:
        sev_color = "red" if d.severity == "critical" else "yellow" if d.severity == "major" else "blue"
        sev_icon = "🔴" if d.severity == "critical" else "🟡" if d.severity == "major" else "🔵"
        table.add_row(
            d.field,
            d.drift_type,
            d.expected,
            d.actual,
            f"[{sev_color}]{sev_icon} {d.severity}[/]",
        )

    console.print(table)
    console.print()


# ── Helpers ──────────────────────────────────────────────

def _count_fields(schema: dict) -> int:
    """Count the total number of fields in a JSON Schema (recursive)."""
    count = 0
    props = schema.get("properties", {})
    count += len(props)
    for v in props.values():
        if v.get("type") == "object":
            count += _count_fields(v)
        elif v.get("type") == "array" and "items" in v:
            items = v["items"]
            if items.get("type") == "object":
                count += _count_fields(items)
    return count
