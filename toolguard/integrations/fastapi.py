"""
toolguard.integrations.fastapi
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integration utilities for FastAPI-based AI agent endpoints.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from toolguard.core.validator import GuardedTool, create_tool


def as_fastapi_tool(func: Callable[..., Any]) -> GuardedTool:
    """Wrap a FastAPI route handler or backend function for ToolGuard fuzzing.
    
    If your API endpoint acts as a tool for a remote Vercel AI SDK or frontend client,
    wrapping it allows you to simulate malicious unstructured payloads locally.
    
    Args:
        func: The backend python function powering the API route.
        
    Returns:
        A GuardedTool instance.
    """
    return create_tool(schema="auto")(func)
