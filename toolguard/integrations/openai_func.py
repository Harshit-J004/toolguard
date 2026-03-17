"""
toolguard.integrations.openai_func
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

OpenAI Function Calling adapter — import/export OpenAI function schemas,
and wrap OpenAI-style tool definitions with ToolGuard validation.

Usage:
    schema = to_openai_function(my_tool)
    guarded = from_openai_function(openai_schema, my_func)
"""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, create_model

from toolguard.core.validator import GuardedTool, create_tool
from toolguard.core.schema import ToolSchema


# ──────────────────────────────────────────────────────────
#  Export: ToolGuard → OpenAI Function Schema
# ──────────────────────────────────────────────────────────

def to_openai_function(tool: GuardedTool | Callable) -> dict[str, Any]:
    """Convert a ToolGuard tool to an OpenAI function calling schema.

    Returns a dict compatible with OpenAI's `tools` parameter:
        {"type": "function", "function": {...}}
    """
    schema: ToolSchema | None = getattr(tool, "schema", None)
    if schema is None:
        raise TypeError("Tool must be a GuardedTool (decorated with @create_tool)")

    # Build OpenAI-compatible parameters schema
    input_schema = dict(schema.input_schema)
    # Remove Pydantic-specific keys that OpenAI doesn't expect
    input_schema.pop("title", None)

    return {
        "type": "function",
        "function": {
            "name": schema.name,
            "description": schema.description or f"Tool: {schema.name}",
            "parameters": input_schema,
        },
    }


def to_openai_functions(tools: list[GuardedTool | Callable]) -> list[dict[str, Any]]:
    """Convert multiple tools to OpenAI function schemas."""
    return [to_openai_function(t) for t in tools]


# ──────────────────────────────────────────────────────────
#  Import: OpenAI Function Schema → ToolGuard
# ──────────────────────────────────────────────────────────

_JSON_TYPE_TO_PYTHON = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def from_openai_function(
    openai_schema: dict[str, Any],
    func: Callable,
) -> GuardedTool:
    """Wrap a function with ToolGuard validation using an OpenAI function schema.

    Args:
        openai_schema: OpenAI function schema dict.
        func:          The actual function to wrap.

    Returns:
        A GuardedTool with validation based on the OpenAI schema.
    """
    func_def = openai_schema.get("function", openai_schema)
    params = func_def.get("parameters", {})
    properties = params.get("properties", {})
    required = set(params.get("required", []))

    # Build Pydantic model from OpenAI schema
    fields: dict[str, Any] = {}
    for prop_name, prop_def in properties.items():
        py_type = _JSON_TYPE_TO_PYTHON.get(prop_def.get("type", "string"), Any)
        default = ... if prop_name in required else None
        fields[prop_name] = (py_type, default)

    InputModel = create_model(f"{func_def.get('name', 'tool')}_Input", **fields)

    return GuardedTool(
        func,
        input_model=InputModel,
        schema=ToolSchema(
            name=func_def.get("name", func.__name__),
            description=func_def.get("description", ""),
            input_schema=params,
        ),
    )
