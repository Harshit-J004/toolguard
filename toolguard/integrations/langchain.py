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

    # Extract the tool's function
    func = lc_tool._run if hasattr(lc_tool, "_run") else lc_tool.invoke

    # Create a wrapper that preserves the tool's metadata
    @create_tool(schema="auto")
    def wrapper(**kwargs: Any) -> Any:
        return func(**kwargs)

    wrapper.__name__ = lc_tool.name  # type: ignore
    wrapper.__doc__ = lc_tool.description
    return wrapper


def langchain_tools_to_chain(tools: list[Any]) -> list[GuardedTool]:
    """Convert a list of LangChain tools to GuardedTool instances.

    Args:
        tools: List of LangChain BaseTool instances.

    Returns:
        List of GuardedTool instances ready for test_chain().
    """
    return [guard_langchain_tool(t) for t in tools]
