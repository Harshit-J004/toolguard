"""
toolguard.core.compatibility
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tool compatibility checker — analyzes pairs of tools in a chain
to detect schema conflicts, type mismatches, and missing fields
before you even run the chain.

Usage:
    report = check_compatibility([get_weather, process_forecast, send_alert])
    print(report.summary())
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

# ──────────────────────────────────────────────────────────
#  Compatibility Issue Levels
# ──────────────────────────────────────────────────────────

@dataclass
class CompatibilityIssue:
    """A single compatibility issue between two tools."""

    level: str  # "error", "warning", "info"
    source_tool: str
    target_tool: str
    field: str
    message: str
    suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "source_tool": self.source_tool,
            "target_tool": self.target_tool,
            "field": self.field,
            "message": self.message,
            "suggestion": self.suggestion,
        }


# ──────────────────────────────────────────────────────────
#  Compatibility Report
# ──────────────────────────────────────────────────────────

@dataclass
class CompatibilityReport:
    """Report from checking tool chain compatibility."""

    chain_name: str
    tools_checked: list[str]
    issues: list[CompatibilityIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[CompatibilityIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[CompatibilityIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def is_compatible(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [
            f"Compatibility Report: {self.chain_name}",
            f"{'═' * 50}",
            f"  Tools: {' → '.join(self.tools_checked)}",
            f"  Errors: {len(self.errors)}  |  Warnings: {len(self.warnings)}",
            "",
        ]

        for issue in self.issues:
            icon = "❌" if issue.level == "error" else "⚠️" if issue.level == "warning" else "ℹ️"
            lines.append(f"  {icon} [{issue.source_tool} → {issue.target_tool}] {issue.message}")
            lines.append(f"     💡 {issue.suggestion}")
            lines.append("")

        status = "✅ COMPATIBLE" if self.is_compatible else "❌ INCOMPATIBLE"
        lines.append(f"Result: {status}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────
#  Type Mapping for Compatibility Checks
# ──────────────────────────────────────────────────────────

# JSON Schema type → Python type name
_JSON_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
    "null": "None",
}


def _get_schema_properties(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract properties from a JSON Schema dict."""
    props = schema.get("properties", {})
    return props


def _get_required_fields(schema: dict[str, Any]) -> set[str]:
    """Extract required fields from a JSON Schema dict."""
    return set(schema.get("required", []))


# ──────────────────────────────────────────────────────────
#  Compatibility Checker
# ──────────────────────────────────────────────────────────

def check_compatibility(
    tools: Sequence[Callable],
    *,
    chain_name: str = "",
) -> CompatibilityReport:
    """Check if tools in a chain have compatible schemas.

    Analyzes consecutive tool pairs:
      - Output schema of tool[i] vs input schema of tool[i+1]
      - Detects: missing required fields, type mismatches, naming conflicts

    Args:
        tools:      Sequence of tools (must have ._toolguard_schema or .schema).
        chain_name: Human-readable name for reporting.

    Returns:
        CompatibilityReport with all detected issues.
    """
    tool_names = [getattr(t, "__name__", f"tool_{i}") for i, t in enumerate(tools)]
    chain_name = chain_name or " → ".join(tool_names)

    issues: list[CompatibilityIssue] = []

    for i in range(len(tools) - 1):
        source = tools[i]
        target = tools[i + 1]
        source_name = tool_names[i]
        target_name = tool_names[i + 1]

        # Get schemas
        source_schema = _get_tool_output_schema(source)
        target_schema = _get_tool_input_schema(target)

        if not source_schema or not target_schema:
            issues.append(CompatibilityIssue(
                level="warning",
                source_tool=source_name,
                target_tool=target_name,
                field="*",
                message="Cannot check compatibility — missing schema on one or both tools.",
                suggestion=f"Add @create_tool(schema='auto') to both {source_name} and {target_name}.",
            ))
            continue

        # Check each required field of the target
        source_props = _get_schema_properties(source_schema)
        target_props = _get_schema_properties(target_schema)
        target_required = _get_required_fields(target_schema)

        # 1. Missing fields: Target requires a field that Source doesn't output
        for field_name in target_required:
            if field_name not in source_props:
                issues.append(CompatibilityIssue(
                    level="error",
                    source_tool=source_name,
                    target_tool=target_name,
                    field=field_name,
                    message=f"'{field_name}' is required by {target_name} but not in {source_name}'s output.",
                    suggestion=f"Add '{field_name}' to {source_name}'s return dict, or make it optional in {target_name}.",
                ))

        # 2. Type mismatches: Same field name, different types
        common_fields = set(source_props) & set(target_props)
        for field_name in common_fields:
            source_type = source_props[field_name].get("type", "")
            target_type = target_props[field_name].get("type", "")

            if source_type and target_type and source_type != target_type:
                s_type = _JSON_TYPE_MAP.get(source_type, source_type)
                t_type = _JSON_TYPE_MAP.get(target_type, target_type)
                issues.append(CompatibilityIssue(
                    level="error",
                    source_tool=source_name,
                    target_tool=target_name,
                    field=field_name,
                    message=f"Type mismatch on '{field_name}': {source_name} outputs {s_type}, {target_name} expects {t_type}.",
                    suggestion=f"Add a converter between {source_name} and {target_name}: convert {s_type} → {t_type}.",
                ))

        # 3. Extra fields: Source outputs fields that Target doesn't expect
        extra_fields = set(source_props) - set(target_props)
        if extra_fields and target_props:
            issues.append(CompatibilityIssue(
                level="info",
                source_tool=source_name,
                target_tool=target_name,
                field=", ".join(sorted(extra_fields)),
                message=f"{source_name} outputs extra fields not used by {target_name}: {sorted(extra_fields)}",
                suggestion="This is usually fine. Extra fields are ignored unless strict mode is enabled.",
            ))

    return CompatibilityReport(
        chain_name=chain_name,
        tools_checked=tool_names,
        issues=issues,
    )


# ── Schema extraction helpers ────────────────────────────

def _get_tool_output_schema(tool: Any) -> dict[str, Any]:
    """Extract output schema from a tool (GuardedTool or plain function)."""
    # GuardedTool
    if hasattr(tool, "schema") and hasattr(tool.schema, "output_schema"):
        return tool.schema.output_schema
    # Raw _toolguard_schema
    if hasattr(tool, "_toolguard_schema"):
        return tool._toolguard_schema.output_schema
    return {}


def _get_tool_input_schema(tool: Any) -> dict[str, Any]:
    """Extract input schema from a tool (GuardedTool or plain function)."""
    if hasattr(tool, "schema") and hasattr(tool.schema, "input_schema"):
        return tool.schema.input_schema
    if hasattr(tool, "_toolguard_schema"):
        return tool._toolguard_schema.input_schema
    return {}
