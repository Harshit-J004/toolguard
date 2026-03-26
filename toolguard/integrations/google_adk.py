"""
toolguard.integrations.google_adk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integration for Google Agent Development Kit (ADK) tools.
Wraps `google.adk.tools.FunctionTool` into `GuardedTool` natively for fuzzing.
"""

from __future__ import annotations

from typing import Any

from toolguard.core.validator import GuardedTool, create_tool


def guard_google_adk_tool(tool: Any) -> GuardedTool:
    """Wrap a Google ADK FunctionTool into a GuardedTool.
    
    Args:
        tool: An instance of `FunctionTool` from `google.adk.tools`.
        
    Returns:
        A GuardedTool instance ready for fuzzing.
    """
    # Duck-typing check for ADK compatibility
    if not (hasattr(tool, "func") or hasattr(tool, "_func")):
        raise TypeError("Object does not appear to be a Google ADK FunctionTool (missing .func or ._func).")

    # Extract the underlying Python function
    func = getattr(tool, "func", getattr(tool, "_func", None))
    if not func:
        raise ValueError("Google ADK FunctionTool does not have an underlying callable to wrap.")

    name = getattr(tool, "name", getattr(func, "__name__", "google_adk_tool"))
    desc = getattr(tool, "description", getattr(func, "__doc__", ""))

    # Wrap the extracted function in a GuardedTool
    guarded = create_tool(schema="auto")(func)
    
    guarded.name = name
    guarded.description = desc or ""
    
    return guarded
