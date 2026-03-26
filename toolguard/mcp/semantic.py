"""
toolguard.mcp.semantic
~~~~~~~~~~~~~~~~~~~~~~
Semantic Policy Engine — context-aware authorization for MCP tool calls.

Goes beyond type-checking to answer: "Was the tool ALLOWED to do this?"

Three tiers of constraint evaluation:
  Tier 1: Rule-based (glob/regex on argument values) — deterministic, free
  Tier 2: Context-aware (session history dependencies) — deterministic, free
  Tier 3: LLM-guided (optional semantic judgment) — configurable, off by default

Usage:
    engine = SemanticEngine.from_policy_dict(policy_data)
    result = engine.evaluate("read_file", {"path": "/etc/passwd"}, session)
    if not result.allowed:
        print(result.reason)  # "Access to system files is prohibited"
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any


# ──────────────────────────────────────────────
#  Evaluation Result
# ──────────────────────────────────────────────

@dataclass
class SemanticResult:
    """Result of semantic constraint evaluation."""
    allowed: bool
    constraint_type: str = ""
    reason: str = ""
    field_name: str = ""
    field_value: Any = None


# ──────────────────────────────────────────────
#  Session Context (for Tier 2)
# ──────────────────────────────────────────────

@dataclass
class SessionContext:
    """Tracks tool call history within a single proxy session.
    
    Used by Tier 2 constraints to enforce logical dependencies
    (e.g., "must call get_user before delete_user").
    """
    tool_history: list[str] = field(default_factory=list)
    field_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    
    def record_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Record a tool call for session-aware constraint checks."""
        self.tool_history.append(tool_name)
        
        # Track per-field value counts for scope limits
        if tool_name not in self.field_counts:
            self.field_counts[tool_name] = {}
        for field_name, value in arguments.items():
            key = f"{field_name}:{value}"
            self.field_counts[tool_name][key] = (
                self.field_counts[tool_name].get(key, 0) + 1
            )
    
    def was_called(self, tool_name: str) -> bool:
        """Check if a tool has been called in this session."""
        return tool_name in self.tool_history
    
    def get_unique_value_count(self, tool_name: str, field_name: str) -> int:
        """Count unique values used for a field across calls to a tool."""
        if tool_name not in self.field_counts:
            return 0
        return sum(
            1 for k in self.field_counts[tool_name]
            if k.startswith(f"{field_name}:")
        )


# ──────────────────────────────────────────────
#  Tier 1: Rule-Based Constraints
# ──────────────────────────────────────────────

def _check_path_deny(arguments: dict[str, Any], constraint: dict) -> SemanticResult | None:
    """Deny access if any argument value matches a forbidden file path pattern."""
    deny_patterns = constraint.get("paths", [])
    reason = constraint.get("reason", "Path access denied by semantic policy")
    target_field = constraint.get("field", None)
    
    values_to_check = {}
    if target_field:
        if target_field in arguments:
            values_to_check[target_field] = arguments[target_field]
    else:
        # Scan all string arguments for path-like values
        values_to_check = {
            k: v for k, v in arguments.items() if isinstance(v, str)
        }
    
    for field_name, value in values_to_check.items():
        if not isinstance(value, str):
            continue
        # Normalize path separators for cross-platform matching
        normalized = value.replace("\\", "/")
        for pattern in deny_patterns:
            if fnmatch.fnmatch(normalized, pattern):
                return SemanticResult(
                    allowed=False,
                    constraint_type="path_deny",
                    reason=reason,
                    field_name=field_name,
                    field_value=value,
                )
    return None


def _check_path_allow(arguments: dict[str, Any], constraint: dict) -> SemanticResult | None:
    """Deny access if the path does NOT match any allowed pattern (whitelist)."""
    allow_patterns = constraint.get("paths", [])
    reason = constraint.get("reason", "Path not in allowed list")
    target_field = constraint.get("field", None)
    
    if not allow_patterns:
        return None
    
    values_to_check = {}
    if target_field:
        if target_field in arguments:
            values_to_check[target_field] = arguments[target_field]
    else:
        values_to_check = {
            k: v for k, v in arguments.items() if isinstance(v, str)
        }
    
    for field_name, value in values_to_check.items():
        if not isinstance(value, str):
            continue
        normalized = value.replace("\\", "/")
        if not any(fnmatch.fnmatch(normalized, p) for p in allow_patterns):
            return SemanticResult(
                allowed=False,
                constraint_type="path_allow",
                reason=reason,
                field_name=field_name,
                field_value=value,
            )
    return None


def _check_value_deny(arguments: dict[str, Any], constraint: dict) -> SemanticResult | None:
    """Deny if a specific field's value matches any of the denied patterns."""
    target_field = constraint.get("field")
    deny_patterns = constraint.get("patterns", [])
    reason = constraint.get("reason", "Value denied by semantic policy")
    
    if not target_field or target_field not in arguments:
        return None
    
    value = str(arguments[target_field])
    for pattern in deny_patterns:
        if fnmatch.fnmatch(value, pattern):
            return SemanticResult(
                allowed=False,
                constraint_type="value_deny",
                reason=reason,
                field_name=target_field,
                field_value=value,
            )
    return None


def _check_value_allow(arguments: dict[str, Any], constraint: dict) -> SemanticResult | None:
    """Deny if a specific field's value does NOT match any allowed pattern."""
    target_field = constraint.get("field")
    allow_patterns = constraint.get("patterns", [])
    reason = constraint.get("reason", "Value not in allowed list")
    
    if not target_field or target_field not in arguments:
        return None
    
    if not allow_patterns:
        return None
    
    value = str(arguments[target_field])
    if not any(fnmatch.fnmatch(value, p) for p in allow_patterns):
        return SemanticResult(
            allowed=False,
            constraint_type="value_allow",
            reason=reason,
            field_name=target_field,
            field_value=value,
        )
    return None


def _check_regex_deny(arguments: dict[str, Any], constraint: dict) -> SemanticResult | None:
    """Deny if a field's value matches any of the forbidden regex patterns."""
    target_field = constraint.get("field")
    deny_patterns = constraint.get("patterns", [])
    reason = constraint.get("reason", "Content denied by semantic policy")
    
    if not target_field or target_field not in arguments:
        return None
    
    value = str(arguments[target_field])
    for pattern in deny_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return SemanticResult(
                allowed=False,
                constraint_type="regex_deny",
                reason=reason,
                field_name=target_field,
                field_value=value,
            )
    return None


# ──────────────────────────────────────────────
#  Tier 2: Context-Aware Constraints
# ──────────────────────────────────────────────

def _check_context(
    tool_name: str,
    arguments: dict[str, Any],
    constraint: dict,
    session: SessionContext,
) -> SemanticResult | None:
    """Deny if a required prior tool has not been called in this session."""
    required_tool = constraint.get("require_prior_tool")
    reason = constraint.get(
        "reason",
        f"Tool '{tool_name}' requires '{required_tool}' to be called first",
    )
    
    if required_tool and not session.was_called(required_tool):
        return SemanticResult(
            allowed=False,
            constraint_type="context_check",
            reason=reason,
        )
    return None


def _check_scope(
    tool_name: str,
    arguments: dict[str, Any],
    constraint: dict,
    session: SessionContext,
) -> SemanticResult | None:
    """Deny if the number of unique values for a field exceeds the session limit."""
    target_field = constraint.get("field")
    max_per_session = constraint.get("max_per_session", 999)
    reason = constraint.get(
        "reason",
        f"Scope limit exceeded: max {max_per_session} unique values for '{target_field}' per session",
    )
    
    if not target_field:
        return None
    
    current_count = session.get_unique_value_count(tool_name, target_field)
    
    # Check if this call would push us over the limit
    current_value = arguments.get(target_field)
    existing_key = f"{target_field}:{current_value}"
    is_new_value = (
        tool_name not in session.field_counts
        or existing_key not in session.field_counts.get(tool_name, {})
    )
    
    if is_new_value and current_count >= max_per_session:
        return SemanticResult(
            allowed=False,
            constraint_type="max_scope",
            reason=reason,
            field_name=target_field,
            field_value=current_value,
        )
    return None


# ──────────────────────────────────────────────
#  Constraint Router
# ──────────────────────────────────────────────

_TIER1_HANDLERS = {
    "path_deny": _check_path_deny,
    "path_allow": _check_path_allow,
    "value_deny": _check_value_deny,
    "value_allow": _check_value_allow,
    "regex_deny": _check_regex_deny,
}

_TIER2_HANDLERS = {
    "context_check": _check_context,
    "max_scope": _check_scope,
}


# ──────────────────────────────────────────────
#  Semantic Engine (Orchestrator)
# ──────────────────────────────────────────────

class SemanticEngine:
    """Evaluates semantic constraints for MCP tool calls.
    
    Processes Tier 1 (rule-based) and Tier 2 (context-aware) constraints
    sequentially. Returns the first denial, or allows the call if all pass.
    """
    
    def __init__(self, tool_constraints: dict[str, list[dict]] | None = None):
        self._tool_constraints: dict[str, list[dict]] = tool_constraints or {}
    
    def has_constraints(self, tool_name: str) -> bool:
        """Check if a tool has any semantic constraints defined."""
        return tool_name in self._tool_constraints
    
    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session: SessionContext | None = None,
    ) -> SemanticResult:
        """Evaluate all semantic constraints for a tool call.
        
        Args:
            tool_name:  The MCP tool being called.
            arguments:  The arguments dict from the tools/call request.
            session:    Optional session context for Tier 2 constraints.
            
        Returns:
            SemanticResult — allowed=True if all constraints pass.
        """
        constraints = self._tool_constraints.get(tool_name, [])
        
        if not constraints:
            return SemanticResult(allowed=True)
        
        if session is None:
            session = SessionContext()
        
        for constraint in constraints:
            ctype = constraint.get("type", "")
            
            # Tier 1: Rule-based (deterministic)
            if ctype in _TIER1_HANDLERS:
                result = _TIER1_HANDLERS[ctype](arguments, constraint)
                if result is not None:
                    return result
            
            # Tier 2: Context-aware (session history)
            elif ctype in _TIER2_HANDLERS:
                result = _TIER2_HANDLERS[ctype](
                    tool_name, arguments, constraint, session
                )
                if result is not None:
                    return result
        
        return SemanticResult(allowed=True)
    
    @classmethod
    def from_policy_dict(cls, data: dict[str, Any]) -> SemanticEngine:
        """Build a SemanticEngine from a YAML-parsed policy dict.
        
        Expected format:
            tools:
              read_file:
                constraints:
                  - type: path_deny
                    paths: ["/etc/passwd", "*.env"]
                    reason: "System file access denied"
        """
        tool_constraints: dict[str, list[dict]] = {}
        
        for tool_name, tool_data in data.get("tools", {}).items():
            constraints = tool_data.get("constraints", [])
            if constraints:
                tool_constraints[tool_name] = constraints
        
        return cls(tool_constraints=tool_constraints)
