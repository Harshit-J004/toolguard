"""
toolguard.core.schema
~~~~~~~~~~~~~~~~~~~~~

Tool schema management — auto-generation from type hints,
import from OpenAPI specs, and JSON Schema export.

A ToolSchema is the source of truth for what a tool accepts and returns.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_type_hints

from pydantic import BaseModel, Field, create_model

# ──────────────────────────────────────────────────────────
#  Schema Model
# ──────────────────────────────────────────────────────────

class ToolSchema(BaseModel):
    """Metadata describing a tool's contract.

    Attributes:
        name:           Tool function name.
        description:    Docstring or user-supplied description.
        version:        Semantic version string.
        input_schema:   JSON Schema dict for the tool's inputs.
        output_schema:  JSON Schema dict for the tool's outputs.
        tags:           Free-form tags for categorization.
    """

    name: str
    description: str = ""
    version: str = "1.0.0"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    # ── Serialisation helpers ────────────────────────────
    def to_json(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> ToolSchema:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**data)


# ──────────────────────────────────────────────────────────
#  Auto-generate schema from function signature
# ──────────────────────────────────────────────────────────

# Type mapping for common Python types → JSON-friendly Pydantic fields
_SUPPORTED_PRIMITIVES = (str, int, float, bool, list, dict, type(None))


def auto_generate_input_model(func: Callable) -> type[BaseModel]:
    """Inspect a function's signature and build a Pydantic model for its inputs.

    Handles:
        - Required and optional parameters
        - Type annotations (falls back to `Any` if missing)
        - Default values
    """
    sig = inspect.signature(func)
    hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}

    fields: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        annotation = hints.get(param_name, Any)
        default = param.default if param.default is not inspect.Parameter.empty else ...

        fields[param_name] = (annotation, default)

    model_name = f"{func.__name__}_Input"
    return create_model(model_name, **fields)  # type: ignore[call-overload]


def auto_generate_schema(
    func: Callable,
    *,
    input_model: type[BaseModel] | None = None,
    output_model: type[BaseModel] | None = None,
) -> ToolSchema:
    """Build a complete ToolSchema from a function.

    Args:
        func:          The tool function to introspect.
        input_model:   Optional Pydantic model for inputs (bypasses auto-generation).
        output_model:  Optional Pydantic model describing the return value.
    """
    if input_model is None:
        input_model = auto_generate_input_model(func)

    return ToolSchema(
        name=func.__name__,
        description=inspect.getdoc(func) or "",
        input_schema=input_model.model_json_schema(),
        output_schema=output_model.model_json_schema() if output_model else {},
    )


# ──────────────────────────────────────────────────────────
#  Import from OpenAPI spec
# ──────────────────────────────────────────────────────────

def from_openapi(spec_path: str | Path) -> list[ToolSchema]:
    """Parse an OpenAPI YAML/JSON spec and return a ToolSchema per endpoint.

    This is a lightweight parser — it extracts operationId, summary,
    and request/response schemas.  Full OpenAPI compliance is a non-goal
    for v0.1; we cover the 80% case.
    """
    import yaml  # deferred so PyYAML is only required when used

    path = Path(spec_path)
    raw = path.read_text(encoding="utf-8")
    spec = yaml.safe_load(raw) if path.suffix in (".yml", ".yaml") else json.loads(raw)

    schemas: list[ToolSchema] = []
    paths: dict = spec.get("paths", {})

    for endpoint, methods in paths.items():
        for method, details in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue

            op_id = details.get("operationId", f"{method}_{endpoint}".replace("/", "_"))
            summary = details.get("summary", "")

            # Extract request body schema
            input_schema: dict[str, Any] = {}
            req_body = details.get("requestBody", {})
            if req_body:
                content = req_body.get("content", {})
                json_content = content.get("application/json", {})
                input_schema = json_content.get("schema", {})

            # Extract response schema (200 / default)
            output_schema: dict[str, Any] = {}
            responses = details.get("responses", {})
            success = responses.get("200", responses.get("201", responses.get("default", {})))
            if success:
                resp_content = success.get("content", {})
                resp_json = resp_content.get("application/json", {})
                output_schema = resp_json.get("schema", {})

            schemas.append(
                ToolSchema(
                    name=op_id,
                    description=summary,
                    input_schema=input_schema,
                    output_schema=output_schema,
                    tags=details.get("tags", []),
                )
            )

    return schemas
