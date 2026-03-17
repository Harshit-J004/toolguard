"""
toolguard.cli.commands.test_cmd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`toolguard test` — run chain reliability tests from YAML config.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console

from toolguard.core.chain import test_chain
from toolguard.reporters.console import print_chain_report
from toolguard.reporters.html import generate_html_report

console = Console()


def _load_tools_from_config(config: dict[str, Any], config_dir: Path) -> list:
    """Dynamically load tool functions from the chain config."""
    tools = []

    # Add config directory to sys.path for imports
    config_dir_str = str(config_dir.resolve())
    if config_dir_str not in sys.path:
        sys.path.insert(0, config_dir_str)

    for tool_def in config.get("tools", []):
        module_name = tool_def["module"]
        func_name = tool_def["function"]

        try:
            mod = importlib.import_module(module_name)
            func = getattr(mod, func_name)
            tools.append(func)
        except (ImportError, AttributeError) as e:
            console.print(f"  [red]✗ Failed to load {module_name}.{func_name}: {e}[/]")
            raise click.Abort()

    return tools


@click.command("test")
@click.option(
    "--chain", "-c",
    type=click.Path(exists=True),
    required=True,
    help="Path to chain YAML config file",
)
@click.option(
    "--reliability", "-r",
    type=float,
    default=None,
    help="Override reliability threshold (0.0 - 1.0)",
)
@click.option(
    "--iterations", "-i",
    type=int,
    default=None,
    help="Override test iterations count",
)
@click.option(
    "--html", "-o",
    type=click.Path(),
    default=None,
    help="Generate HTML report at this path",
)
@click.option(
    "--json-output", "-j",
    type=click.Path(),
    default=None,
    help="Save JSON report at this path",
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    default=False,
    help="Suppress console output (only show pass/fail)",
)
@click.option(
    "--no-save",
    is_flag=True,
    default=False,
    help="Don't save results to history database",
)
def test_cmd(
    chain: str,
    reliability: float | None,
    iterations: int | None,
    html: str | None,
    json_output: str | None,
    quiet: bool,
    no_save: bool,
) -> None:
    """🧪 Test a tool chain for reliability.

    Runs your tool chain against generated edge-case inputs and
    reports cascading failures with actionable suggestions.
    """

    config_path = Path(chain)
    config_dir = config_path.parent

    # Load config
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    chain_name = config.get("chain", {}).get("name", config_path.stem)
    test_config = config.get("test_config", {})
    base_input = config.get("base_input", {})

    # Override from CLI flags
    threshold = reliability or test_config.get("reliability_threshold", 0.95)
    iters = iterations or test_config.get("iterations", 10)
    test_cases = test_config.get("test_cases", ["happy_path", "null_handling", "malformed_data"])

    if not quiet:
        console.print(f"\n🧪 [bold]Testing chain:[/] [cyan]{chain_name}[/]")
        console.print(f"   Config: [dim]{config_path}[/]")
        console.print(f"   Tests:  [dim]{', '.join(test_cases)}[/]")
        console.print(f"   Threshold: [dim]{threshold:.0%}[/]\n")

    # Load tools
    tools = _load_tools_from_config(config, config_dir)

    if not quiet:
        console.print(f"   Loaded [bold]{len(tools)}[/] tools: {', '.join(t.__name__ for t in tools)}\n")

    # Run tests
    try:
        report = test_chain(
            tools,
            test_cases=test_cases,
            base_input=base_input,
            iterations=iters,
            assert_reliability=0.0,  # Don't assert here, we handle it below
            chain_name=chain_name,
        )
    except Exception as e:
        console.print(f"[red]✗ Chain test failed with error: {e}[/]")
        raise click.Abort()

    # Display results
    if not quiet:
        print_chain_report(report)

    # HTML report
    if html:
        output_path = generate_html_report(report, html)
        console.print(f"📄 HTML report saved to: [cyan]{output_path}[/]\n")

    # JSON report
    if json_output:
        Path(json_output).write_text(report.to_json(), encoding="utf-8")
        console.print(f"\U0001f4c4 JSON report saved to: [cyan]{json_output}[/]\n")

    # Auto-save to history database
    if not no_save:
        try:
            from toolguard.storage.db import ResultStore
            store = ResultStore()
            store.save_report(report)
            store.close()
            if not quiet:
                console.print("[dim]\U0001f4be Results saved to history. "
                              "Run [bold]toolguard history[/] to view trends.[/]\n")
        except Exception:
            pass  # Storage failure should never break the test command

    # Exit with error code if below threshold
    if report.reliability < threshold:
        if quiet:
            console.print(
                f"[red]\u274c FAIL: {report.reliability:.1%} reliability "
                f"(below {threshold:.0%} threshold)[/]"
            )
        raise SystemExit(1)
    else:
        if quiet:
            console.print(
                f"[green]\u2705 PASS: {report.reliability:.1%} reliability[/]"
            )
