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
            "CrewAI integration requires crewai. "
            "Install with: pip install toolguard[crewai]"
        )

    # Extract the run function
    if hasattr(crewai_tool, "_run"):
        func = crewai_tool._run
    elif callable(crewai_tool):
        func = crewai_tool
    else:
        raise TypeError(f"Cannot extract callable from CrewAI tool: {type(crewai_tool).__name__}")

    @create_tool(schema="auto")
    def wrapper(**kwargs: Any) -> Any:
        return func(**kwargs)

    tool_name = getattr(crewai_tool, "name", getattr(func, "__name__", "crewai_tool"))
    wrapper.__name__ = tool_name  # type: ignore
    wrapper.__doc__ = getattr(crewai_tool, "description", "")
    return wrapper
