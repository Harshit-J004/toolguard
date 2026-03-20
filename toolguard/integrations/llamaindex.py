"""
toolguard.integrations.llamaindex
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration for LlamaIndex tools.
Wraps LlamaIndex `BaseTool` or `FunctionTool` instances into `GuardedTool` 
for native reliability fuzzing.
"""

from __future__ import annotations

from typing import Any

from toolguard.core.validator import GuardedTool, create_tool


def guard_llamaindex_tool(tool: Any) -> GuardedTool:
    """Wrap a LlamaIndex Tool into a GuardedTool.
    
    Args:
        tool: A LlamaIndex BaseTool (e.g., FunctionTool).
        
    Returns:
        A GuardedTool instance ready for fuzzing.
    """
    try:
        from llama_index.core.tools.types import BaseTool
        
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Expected a LlamaIndex BaseTool, got {type(tool)}")
            
    except ImportError:
        # Fallback to duck-typing if llama-index is not installed globally
        # but the object has the required attributes
        if not hasattr(tool, "fn") or not hasattr(tool, "metadata"):
            raise TypeError("Object does not appear to be a LlamaIndex tool (missing .fn or .metadata).")

    # Extract the underlying Python function (sync or async)
    func = getattr(tool, "fn", None)
    if not func:
        func = getattr(tool, "async_fn", None)
        
    if not func:
        raise ValueError("LlamaIndex tool missing both .fn and .async_fn to wrap.")

    name = tool.metadata.name if getattr(tool, "metadata", None) else tool.__class__.__name__
    desc = tool.metadata.description if getattr(tool, "metadata", None) else ""

    # Wrap the extracted function in a GuardedTool
    guarded = create_tool(schema="auto")(func)
    
    # Optional: overwrite the name/description to strictly match the LlamaIndex metadata
    guarded.name = name
    guarded.description = desc
    
    return guarded
