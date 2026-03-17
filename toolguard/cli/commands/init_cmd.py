"""
toolguard.cli.commands.init_cmd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`toolguard init` — scaffold a new ToolGuard project.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

console = Console()

_CHAIN_CONFIG_TEMPLATE = """\
# ToolGuard Chain Configuration
# Run with: toolguard test --chain {name}_chain.yaml

chain:
  name: "{name}"
  description: "Tool chain for {name}"

tools:
  - name: "step_1"
    module: "tools"
    function: "step_one"

  - name: "step_2"
    module: "tools"
    function: "step_two"

  - name: "step_3"
    module: "tools"
    function: "step_three"

test_config:
  test_cases:
    - happy_path
    - null_handling
    - malformed_data
    - missing_fields
  iterations: 10
  reliability_threshold: 0.95

base_input:
  # Define your base test input here
  field_1: "value_1"
  field_2: 42
"""

_TOOLS_TEMPLATE = """\
\"\"\"
Example tools for {name} chain.
Wrap each tool with @create_tool for automatic validation.
\"\"\"

from toolguard import create_tool


@create_tool(schema="auto")
def step_one(field_1: str, field_2: int = 0) -> dict:
    \"\"\"First step in the chain.\"\"\"
    return {{
        "processed": field_1.upper(),
        "value": field_2 * 2,
    }}


@create_tool(schema="auto")
def step_two(processed: str, value: int = 0) -> dict:
    \"\"\"Second step — processes output from step_one.\"\"\"
    return {{
        "result": f"{{processed}}_done",
        "score": value + 10,
    }}


@create_tool(schema="auto")
def step_three(result: str, score: int = 0) -> dict:
    \"\"\"Final step — generates the output.\"\"\"
    return {{
        "status": "complete",
        "output": result,
        "final_score": score,
    }}
"""

_TEST_RUNNER_TEMPLATE = """\
\"\"\"
Run chain tests for {name}.
Execute with: python run_tests.py
\"\"\"

from tools import step_one, step_two, step_three
from toolguard import test_chain, score_chain
from toolguard.reporters.console import print_chain_report


def main():
    print("Running {name} chain tests...\\n")

    report = test_chain(
        [step_one, step_two, step_three],
        base_input={{"field_1": "hello", "field_2": 42}},
        test_cases=["happy_path", "null_handling", "malformed_data"],
        assert_reliability=0.0,  # Don't crash on first run
        chain_name="{name}",
        save=True,  # Save results to history
    )

    print_chain_report(report)

    # Show the reliability score
    score = score_chain(report)
    print(score.summary())

    # Tell the user what to do next
    print("\\nTip: Run 'toolguard history' to see your reliability trend over time.")
    print("Tip: Increase assert_reliability to 0.80+ once you fix the failures above.")


if __name__ == "__main__":
    main()
"""


@click.command("init")
@click.option("--name", "-n", default="my_project", help="Project name")
@click.option("--path", "-p", default=".", type=click.Path(), help="Directory to scaffold in")
def init_cmd(name: str, path: str) -> None:
    """🚀 Scaffold a new ToolGuard project with example tools and chain config."""

    target = Path(path) / name
    target.mkdir(parents=True, exist_ok=True)

    console.print(f"\n🛡️  Initializing ToolGuard project: [bold cyan]{name}[/]")
    console.print(f"   Directory: [dim]{target.resolve()}[/]\n")

    # Write chain config
    config_path = target / f"{name}_chain.yaml"
    config_path.write_text(_CHAIN_CONFIG_TEMPLATE.format(name=name), encoding="utf-8")
    console.print(f"  ✓ Created [cyan]{config_path.name}[/]")

    # Write tools
    tools_path = target / "tools.py"
    tools_path.write_text(_TOOLS_TEMPLATE.format(name=name), encoding="utf-8")
    console.print(f"  ✓ Created [cyan]{tools_path.name}[/]")

    # Write test runner
    runner_path = target / "run_tests.py"
    runner_path.write_text(_TEST_RUNNER_TEMPLATE.format(name=name), encoding="utf-8")
    console.print(f"  ✓ Created [cyan]{runner_path.name}[/]")

    console.print(f"\n[bold green]✅ Project '{name}' initialized![/]")
    console.print(f"\n[dim]Next steps:[/]")
    console.print(f"  1. cd {target}")
    console.print(f"  2. Edit [cyan]tools.py[/] with your real tools")
    console.print(f"  3. Run [cyan]python run_tests.py[/] to test your chain")
    console.print(f"  4. Run [cyan]toolguard test --chain {name}_chain.yaml[/]")
    console.print()
