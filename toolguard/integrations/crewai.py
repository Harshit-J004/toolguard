"""
toolguard.integrations.crewai
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CrewAI adapter — wraps CrewAI tools with ToolGuard validation.

Usage:
    from crewai_tools import SomeCrewTool

    guarded = guard_crewai_tool(SomeCrewTool())
"""

from __future__ import annotations

from typing import Any

from toolguard.core.validator import GuardedTool, create_tool


def guard_crewai_tool(crewai_tool: Any) -> GuardedTool:
    """Wrap a CrewAI tool with ToolGuard validation.

    Args:
        crewai_tool: A CrewAI tool instance (BaseTool or @tool decorated).

    Returns:
        A GuardedTool wrapping the CrewAI tool's _run method.

    Raises:
        ImportError: If crewai is not installed.
    """
    try:
        from crewai.tools import BaseTool as CrewBaseTool
    except ImportError:
        raise ImportError(
            "ToolGuard requires the CrewAI integration. "
            "Install with: pip install \"py-toolguard[crewai]\""
        )

    # Extract the underlying Python function
    func = None
    if hasattr(crewai_tool, "func") and callable(crewai_tool.func):
        func = crewai_tool.func
    elif hasattr(crewai_tool, "_run"):
        func = crewai_tool._run
    elif callable(crewai_tool):
        func = crewai_tool
    else:
        raise TypeError(f"Cannot extract callable from CrewAI tool: {type(crewai_tool).__name__}")

    # Wrap the extracted function directly
    guarded = create_tool(schema="auto")(func)
    
    # Overwrite with accurate CrewAI metadata
    guarded.name = getattr(crewai_tool, "name", getattr(func, "__name__", "crewai_tool"))
    guarded.description = getattr(crewai_tool, "description", "")
    
    return guarded
