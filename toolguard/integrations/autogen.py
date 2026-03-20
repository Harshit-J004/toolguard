"""
toolguard.integrations.autogen
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integration for Microsoft AutoGen core tools.
Wraps `autogen_core.tools.FunctionTool` into `GuardedTool` natively for fuzzing.
"""

from __future__ import annotations

from typing import Any

from toolguard.core.validator import GuardedTool, create_tool


def guard_autogen_tool(tool: Any) -> GuardedTool:
    """Wrap a Microsoft AutoGen FunctionTool into a GuardedTool.
    
    Args:
        tool: An autogen_core.tools.FunctionTool instance.
        
    Returns:
        A GuardedTool instance ready for fuzzing.
    """
    try:
        from autogen_core.tools import FunctionTool
        
        if not isinstance(tool, FunctionTool):
            raise TypeError(f"Expected an AutoGen FunctionTool, got {type(tool)}")
            
    except ImportError:
        # Fallback to duck-typing if autogen is not installed globally
        # but the object has the required attributes
        if not hasattr(tool, "_func") or not hasattr(tool, "name"):
            raise TypeError("Object does not appear to be an AutoGen FunctionTool (missing ._func or .name).")

    # Extract the underlying Python function
    func = getattr(tool, "_func", None)
    if not func:
        raise ValueError("AutoGen tool does not have an underlying ._func to wrap.")

    name = tool.name
    desc = tool.description

    # Wrap the extracted function in a GuardedTool
    guarded = create_tool(schema="auto")(func)
    
    guarded.name = name
    guarded.description = desc
    
    return guarded
