"""
toolguard.cli.commands.run_cmd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`toolguard run` — zero-config auto-discovery of tools in a Python file.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

import click
from rich.console import Console

from toolguard.core.chain import test_chain
from toolguard.core.validator import GuardedTool
from toolguard.reporters.console import print_chain_report
from toolguard.reporters.html import generate_html_report

console = Console()


def _discover_tools(file_path: Path) -> list:
    """Dynamically load a Python file and discover tools."""
    tools = []
    
    # Add directory to sys.path so relative imports in the script work
    dir_path = str(file_path.parent.resolve())
    if dir_path not in sys.path:
        sys.path.insert(0, dir_path)
        
    module_name = file_path.stem
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if not spec or not spec.loader:
        console.print(f"[red]✗ Could not load {file_path.name}[/]")
        raise click.Abort()
        
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        console.print(f"[red]✗ Failed to execute {file_path.name}: {e}[/]")
        raise click.Abort()

    # Scan module
    for name, obj in inspect.getmembers(mod):
        # 1. Native GuardedTool (created via @create_tool)
        if isinstance(obj, GuardedTool):
            tools.append(obj)
            continue
            
        # 2. LangChain BaseTool (duck typing to avoid hard dependency)
        if hasattr(obj, "func") and hasattr(obj, "name") and obj.__class__.__name__ in ("Tool", "StructuredTool"):
            try:
                from toolguard.integrations.langchain import guard_langchain_tool
                guarded = guard_langchain_tool(obj)
                tools.append(guarded)
                continue
            except ImportError:
                pass
                
        # 3. CrewAI Tool
        if hasattr(obj, "func") and hasattr(obj, "name") and obj.__class__.__name__ == "Tool" and "crewai" in str(type(obj)):
            try:
                from toolguard.integrations.crewai import guard_crewai_tool
                guarded = guard_crewai_tool(obj)
                tools.append(guarded)
                continue
            except ImportError:
                pass
                
        # 4. LlamaIndex Tool
        if hasattr(obj, "metadata") and (hasattr(obj, "fn") or hasattr(obj, "async_fn")) and obj.__class__.__name__ in ("FunctionTool", "AsyncFunctionTool", "BaseTool"):
            try:
                from toolguard.integrations.llamaindex import guard_llamaindex_tool
                guarded = guard_llamaindex_tool(obj)
                tools.append(guarded)
                continue
            except ImportError:
                pass
                
        # 5. Microsoft AutoGen FunctionTool
        if hasattr(obj, "_func") and hasattr(obj, "name") and obj.__class__.__name__ == "FunctionTool" and "autogen" in str(type(obj)):
            try:
                from toolguard.integrations.autogen import guard_autogen_tool
                guarded = guard_autogen_tool(obj)
                tools.append(guarded)
                continue
            except ImportError:
                pass
                
        # 6. OpenAI Swarm Agent
        if hasattr(obj, "functions") and obj.__class__.__name__ == "Agent" and "swarm" in str(type(obj)):
            try:
                from toolguard.integrations.swarm import guard_swarm_agent
                guarded_list = guard_swarm_agent(obj)
                tools.extend(guarded_list)
                continue
            except ImportError:
                pass
                
    return tools


@click.command("run")
@click.argument("script", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--reliability", "-r",
    type=float,
    default=0.95,
    help="Reliability threshold (0.0 - 1.0)",
)
@click.option(
    "--iterations", "-i",
    type=int,
    default=5,
    help="Happy-path test iterations count",
)
@click.option(
    "--html", "-o",
    type=click.Path(),
    default=None,
    help="Generate HTML report at this path",
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    default=False,
    help="Suppress console output",
)
@click.option(
    "--github-pr",
    is_flag=True,
    default=False,
    help="Post results dynamically as a GitHub PR comment",
)
@click.option(
    "--junit-xml",
    type=click.Path(),
    default=None,
    help="Export results in Jenkins/GitLab JUnit format",
)
def run_cmd(
    script: str,
    reliability: float,
    iterations: int,
    html: str | None,
    quiet: bool,
    github_pr: bool,
    junit_xml: str | None,
) -> None:
    """🚀 Zero-config auto-test a Python script.
    
    Dynamically loads the python script, auto-discovers any tools 
    (ToolGuard, LangChain, or CrewAI), and runs the full fuzzing suite.
    """
    path = Path(script)
    
    if not quiet:
        console.print(f"\n🚀 [bold]Auto-Discovering tools in:[/] [cyan]{path.name}[/]")
    
    tools = _discover_tools(path)
    
    if not tools:
        console.print(f"[yellow]⚠️ No tools found in {path.name}.[/]")
        console.print("Decorate your functions with [bold]@create_tool[/] to test them.")
        raise SystemExit(0)
        
    if not quiet:
        console.print(f"   Found [bold green]{len(tools)}[/] tools: {', '.join(getattr(t, 'name', t.__name__) for t in tools)}\n")
        
    try:
        report = test_chain(
            chain=tools,
            iterations=iterations,
            assert_reliability=0.0, # Checked manually below
            chain_name=f"Auto [{path.name}]",
            save=True,
        )
    except Exception as e:
        console.print(f"[red]✗ Test suite failed with error: {e}[/]")
        raise click.Abort()
        
    # Display results
    if not quiet:
        print_chain_report(report)
        
    # HTML report
    if html:
        output_path = generate_html_report(report, html)
        if not quiet:
            console.print(f"📄 HTML report saved to: [cyan]{output_path}[/]\n")
            
    # JUnit XML
    if junit_xml:
        from toolguard.reporters.junit import generate_junit_xml
        out_xml = generate_junit_xml(report, junit_xml)
        if not quiet:
            console.print(f"✅ JUnit XML saved to: [cyan]{out_xml}[/]\n")

    # GitHub PR Commenting
    if github_pr:
        from toolguard.reporters.github import post_pr_comment
        post_pr_comment(report, reliability)
        if not quiet:
            console.print("🚀 Posted reliability report to GitHub PR.\n")
        
    if report.reliability < reliability:
        if quiet:
            console.print(f"[red]❌ FAIL: {report.reliability:.1%} reliability[/]")
        raise SystemExit(1)
    else:
        if quiet:
            console.print(f"[green]✅ PASS: {report.reliability:.1%} reliability[/]")
