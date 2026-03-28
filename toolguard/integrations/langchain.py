"""
toolguard.integrations.langchain
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

LangChain adapter — wraps LangChain BaseTool with ToolGuard validation.

Usage:
    from langchain_core.tools import tool

    @tool
    def search(query: str) -> str:
        ...

    guarded = guard_langchain_tool(search)
"""

from __future__ import annotations

from typing import Any

from toolguard.core.validator import GuardedTool, create_tool


def guard_langchain_tool(lc_tool: Any) -> GuardedTool:
    """Wrap a LangChain tool with ToolGuard validation.

    Args:
        lc_tool: A LangChain BaseTool instance.

    Returns:
        A GuardedTool wrapping the LangChain tool's invoke method.

    Raises:
        ImportError: If langchain-core is not installed.
    """
    try:
        from langchain_core.tools import BaseTool
    except ImportError:
        raise ImportError(
            "ToolGuard requires the LangChain integration. "
            "Install with: pip install \"py-toolguard[langchain]\""
        )

    if not isinstance(lc_tool, BaseTool):
        raise TypeError(f"Expected a LangChain BaseTool, got {type(lc_tool).__name__}")

    # Extract the underlying Python function.
    # We strictly prioritize asynchronous coroutines over sync functions to prevent
    # thread-blocking inside highly concurrent AI swarms like CrewAI.
    func = None
    if hasattr(lc_tool, "coroutine") and callable(lc_tool.coroutine):
        func = lc_tool.coroutine
    elif hasattr(lc_tool, "func") and callable(lc_tool.func):
        func = lc_tool.func
    elif hasattr(lc_tool, "_arun"):
        func = lc_tool._arun
    elif hasattr(lc_tool, "_run"):
        # Check if _run is actually implemented (not just the abstract stub)
        try:
            import inspect as _inspect
            source = _inspect.getsource(lc_tool._run)
            if "NotImplementedError" not in source:
                func = lc_tool._run
        except (TypeError, OSError):
            func = lc_tool._run  # Can't inspect, assume it's real
            
    if func is None:
        func = getattr(lc_tool, "ainvoke", getattr(lc_tool, "invoke", None))
            
    if func is None:
        raise ValueError(f"Could not extract an underlying function or coroutine from {lc_tool.name}")

    # Wrap the extracted function directly
    guarded = create_tool(schema="auto")(func)
    
    # Overwrite with accurate LangChain metadata
    guarded.name = lc_tool.name
    guarded.description = lc_tool.description
    
    return guarded


def langchain_tools_to_chain(tools: list[Any]) -> list[GuardedTool]:
    """Convert a list of LangChain tools to GuardedTool instances.

    Args:
        tools: List of LangChain BaseTool instances.

    Returns:
        List of GuardedTool instances ready for test_chain().
    """
    return [guard_langchain_tool(t) for t in tools]
