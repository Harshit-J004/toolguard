"""
toolguard.integrations.openai_agents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integration for OpenAI Agents SDK tools.
Wraps `agents.function_tool` decorators into `GuardedTool` natively for fuzzing.
"""

from __future__ import annotations

from typing import Any

from toolguard.core.validator import GuardedTool, create_tool


def guard_openai_agents_tool(tool: Any) -> GuardedTool:
    """Wrap an OpenAI Agents SDK tool into a GuardedTool.
    
    Args:
        tool: A tool created via `@function_tool` from the `agents` package.
        
    Returns:
        A GuardedTool instance ready for fuzzing.
    """
    # Duck-typing check to support environments where the agents SDK isn't installed natively
    if not (hasattr(tool, "fn") or hasattr(tool, "_func")):
        raise TypeError("Object does not appear to be an OpenAI Agents SDK tool (missing .fn or ._func).")

    # Extract the underlying Python function
    func = getattr(tool, "fn", getattr(tool, "_func", None))
    if not func:
        raise ValueError("OpenAI Agents SDK tool does not have an underlying callable to wrap.")

    name = getattr(tool, "name", getattr(func, "__name__", "openai_agents_tool"))
    desc = getattr(tool, "description", getattr(func, "__doc__", ""))

    # Wrap the extracted function in a GuardedTool
    guarded = create_tool(schema="auto")(func)
    
    guarded.name = name
    guarded.description = desc or ""
    
    return guarded
