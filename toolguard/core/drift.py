"""
toolguard.core.drift
~~~~~~~~~~~~~~~~~~~~

Schema Drift Detection Engine.

Detects when an LLM provider silently changes its structured output format
by comparing live outputs against frozen "schema fingerprints".

Core algorithm:
    1. infer_schema(output)       → Recursively infer a JSON Schema from a raw dict
    2. create_fingerprint(...)    → Freeze a schema snapshot with metadata
    3. detect_drift(fp, live)     → Diff two schemas and report every structural deviation
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import socket
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ──────────────────────────────────────────────────────────
#  Schema Inference Engine
# ──────────────────────────────────────────────────────────

_MAX_DEPTH = 10


def infer_schema(value: Any, *, _depth: int = 0) -> dict[str, Any]:
    """Recursively infer a JSON Schema from a Python value.

    Handles: str, int, float, bool, None, list, dict (nested).
    Caps recursion at depth 10 to prevent infinite loops.

    Args:
        value: Any Python value returned by an LLM.

    Returns:
        A JSON Schema dict describing the value's structure.
    """
    if _depth > _MAX_DEPTH:
        return {"type": "any", "note": "max depth exceeded"}

    if value is None:
        return {"type": "null", "_value": None}
    if isinstance(value, bool):  # Must be before int (bool is subclass of int)
        return {"type": "boolean", "_value": value}
    if isinstance(value, int):
        return {"type": "integer", "_value": value}
    if isinstance(value, float):
        return {"type": "number", "_value": value}
    if isinstance(value, str):
        # Detect common format patterns
        schema: dict[str, Any] = {"type": "string", "_value": value}
        if _looks_like_iso_date(value):
            schema["format"] = "date"
        elif _looks_like_iso_datetime(value):
            schema["format"] = "date-time"
        elif _looks_like_email(value):
            schema["format"] = "email"
        elif _looks_like_url(value):
            schema["format"] = "uri"
        elif _looks_like_uuid(value):
            schema["format"] = "uuid"
        elif _looks_like_ipv4(value):
            schema["format"] = "ipv4"
        elif _looks_like_ipv6(value):
            schema["format"] = "ipv6"
        return schema

    if isinstance(value, list):
        schema = {"type": "array"}
        if len(value) > 0:
            # Supreme Security Fix: Deep Hash scan to prevent Nested-Object Polymorphic Bypasses
            unique_schemas = []
            seen_hashes = set()
            raw_items = []
            
            for v in value:
                item_schema = infer_schema(v, _depth=_depth + 1)
                raw_items.append(item_schema) # Keep raw position context for Tuples
                
                # Compute a deterministic hash of the entire nested schema structure
                canonical = json.dumps(item_schema, sort_keys=True)
                if canonical not in seen_hashes:
                    seen_hashes.add(canonical)
                    unique_schemas.append(item_schema)
            
            schema["_positional_items"] = raw_items
            if len(unique_schemas) == 1:
                schema["items"] = unique_schemas[0]
            else:
                # Array contains fundamentally different structural schemas.
                # Emit a native "anyOf" construct for polymorphic math evaluation.
                schema["items"] = {"anyOf": unique_schemas}
        else:
            schema["items"] = {}
        return schema

    if isinstance(value, dict):
        properties: dict[str, Any] = {}
        for k, v in value.items():
            properties[k] = infer_schema(v, _depth=_depth + 1)
        return {
            "type": "object",
            "properties": properties,
            "required": list(value.keys()),
        }

    # Fallback for unknown types
    return {"type": type(value).__name__}


# ── Format Detection Helpers ─────────────────────────────

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://")


def _looks_like_iso_date(s: str) -> bool:
    return bool(_ISO_DATE_RE.match(s))

def _looks_like_iso_datetime(s: str) -> bool:
    return bool(_ISO_DATETIME_RE.match(s))

def _looks_like_email(s: str) -> bool:
    return bool(_EMAIL_RE.match(s))

def _looks_like_url(s: str) -> bool:
    return bool(_URL_RE.match(s))

def _looks_like_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False

def _looks_like_ipv4(val: str) -> bool:
    try:
        socket.inet_pton(socket.AF_INET, val)
        return True
    except socket.error:
        return False

def _looks_like_ipv6(val: str) -> bool:
    try:
        socket.inet_pton(socket.AF_INET6, val)
        return True
    except socket.error:
        return False


# ──────────────────────────────────────────────────────────
#  Schema Fingerprint
# ──────────────────────────────────────────────────────────

@dataclass
class SchemaFingerprint:
    """A frozen snapshot of an LLM's output structure.

    Attributes:
        tool_name:      Name of the tool being probed.
        prompt:         The exact prompt used to generate the output.
        model:          The model identifier (e.g., "gemini-2.0-flash").
        timestamp:      ISO timestamp when the fingerprint was created.
        json_schema:    The inferred JSON Schema dict.
        sample_output:  The raw output dict for human reference.
        checksum:       SHA-256 hash of the schema for quick equality checks.
    """
    tool_name: str
    prompt: str
    model: str
    timestamp: str
    json_schema: dict[str, Any]
    sample_output: Any
    checksum: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "prompt": self.prompt,
            "model": self.model,
            "timestamp": self.timestamp,
            "json_schema": self.json_schema,
            "sample_output": self.sample_output,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SchemaFingerprint:
        return cls(**data)


def _compute_checksum(schema: dict[str, Any]) -> str:
    """Deterministic SHA-256 of a JSON Schema dict."""
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def create_fingerprint(
    tool_name: str,
    prompt: str,
    model: str,
    output: Any,
) -> SchemaFingerprint:
    """Create a frozen schema fingerprint from a live LLM output.

    Args:
        tool_name: Name of the tool being tested.
        prompt:    The exact prompt that generated the output.
        model:     Model identifier string.
        output:    The raw dict output from the LLM.

    Returns:
        A SchemaFingerprint ready to be stored.
    """
    schema = infer_schema(output)
    return SchemaFingerprint(
        tool_name=tool_name,
        prompt=prompt,
        model=model,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        json_schema=schema,
        sample_output=output,
        checksum=_compute_checksum(schema),
    )


def _resolve_refs(schema: Any, root: dict[str, Any], depth: int = 0) -> Any:
    """Recursively resolve $ref pointers in a JSON Schema (capped identically to infer_schema)."""
    if depth > _MAX_DEPTH:
        return {"type": "any", "note": "max depth exceeded"}

    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_path = schema["$ref"]
            keys = ref_path.lstrip("#/").split("/")
            resolved = root
            try:
                for k in keys:
                    resolved = resolved[k]
                # Recursively resolve any further references within
                return _resolve_refs(resolved, root, depth + 1)
            except KeyError:
                return schema
        return {k: _resolve_refs(v, root, depth + 1) for k, v in schema.items()}
    elif isinstance(schema, list):
        return [_resolve_refs(item, root, depth + 1) for item in schema]
    return schema


def _strip_pydantic_artifacts(schema: Any) -> Any:
    """Recursively strip Pydantic metadata. We now preserve 'anyOf' constructs perfectly."""
    if isinstance(schema, dict):
        # Blacklist of structural metadata artifacts that pollute the checksum cache
        forbidden_keys = {"title", "description", "default"}
        return {
            k: _strip_pydantic_artifacts(v) 
            for k, v in schema.items() 
            if k not in forbidden_keys
        }
    elif isinstance(schema, list):
        return [_strip_pydantic_artifacts(item) for item in schema]
    return schema


def create_fingerprint_from_model(
    tool_name: str,
    model: str,
    pydantic_model: Any,  # Type[pydantic.BaseModel]
    prompt: str = "(statically generated from Pydantic)",
) -> SchemaFingerprint:
    """Create a frozen schema fingerprint directly from a Pydantic model.
    
    This bridges the gap between static Python types and empirical LLM drift,
    allowing developers to enforce that live API responses mathematically match
    their strongly-typed codebase.
    """
    # Grab the JSON schema natively generated by Pydantic (v2 fallback to v1)
    if hasattr(pydantic_model, "model_json_schema"):
        raw_schema = pydantic_model.model_json_schema()
    elif hasattr(pydantic_model, "schema"):
        raw_schema = pydantic_model.schema()
    else:
        raise TypeError(f"Expected a Pydantic BaseModel, got {type(pydantic_model)}")
    
    # Flatten $ref pointers so the baseline is a pure structural map
    # that exactly matches what `infer_schema` will produce dynamically.
    schema = _resolve_refs(raw_schema, raw_schema)

    # Clean up recursive Pydantic metadata artifacts that pollute the O(1) checksum footprint.
    schema = _strip_pydantic_artifacts(schema)

    return SchemaFingerprint(
        tool_name=tool_name,
        prompt=prompt,
        model=model,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        json_schema=schema,
        sample_output={"_note": f"Generated statically from {getattr(pydantic_model, '__name__', 'Pydantic Model')}"},
        checksum=_compute_checksum(schema),
    )


# ──────────────────────────────────────────────────────────
#  Drift Detection Engine
# ──────────────────────────────────────────────────────────

@dataclass
class FieldDrift:
    """A single structural deviation detected in one field."""
    field: str
    drift_type: str   # "added", "removed", "type_changed", "format_changed",
                      # "required_changed", "items_changed"
    expected: str
    actual: str
    severity: str     # "minor", "major", "critical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "drift_type": self.drift_type,
            "expected": self.expected,
            "actual": self.actual,
            "severity": self.severity,
        }


@dataclass
class DriftReport:
    """Complete drift analysis between a fingerprint and a live output.

    Attributes:
        tool_name:    Tool being checked.
        model:        Model identifier.
        has_drift:    True if any structural drift was detected.
        drifts:       List of individual field-level drifts.
        severity:     Overall severity: "none", "minor", "major", "critical".
        fingerprint_checksum: Checksum of the baseline fingerprint.
        live_checksum:        Checksum of the live output's inferred schema.
    """
    tool_name: str
    model: str
    has_drift: bool
    drifts: list[FieldDrift] = field(default_factory=list)
    severity: str = "none"
    fingerprint_checksum: str = ""
    live_checksum: str = ""

    @property
    def added_fields(self) -> list[str]:
        return [d.field for d in self.drifts if d.drift_type == "added"]

    @property
    def removed_fields(self) -> list[str]:
        return [d.field for d in self.drifts if d.drift_type == "removed"]

    @property
    def type_changes(self) -> list[FieldDrift]:
        return [d for d in self.drifts if d.drift_type == "type_changed"]

    def summary(self) -> str:
        if not self.has_drift:
            return f"✅ No drift detected for '{self.tool_name}' ({self.model})"
        lines = [
            f"⚠️  DRIFT DETECTED for '{self.tool_name}' ({self.model})",
            f"   Severity: {self.severity.upper()}",
            f"   Baseline checksum: {self.fingerprint_checksum}",
            f"   Live checksum:     {self.live_checksum}",
            "",
        ]
        for d in self.drifts:
            icon = "🔴" if d.severity == "critical" else "🟡" if d.severity == "major" else "🔵"
            lines.append(f"   {icon} [{d.drift_type}] {d.field}: {d.expected} → {d.actual}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "model": self.model,
            "has_drift": self.has_drift,
            "severity": self.severity,
            "fingerprint_checksum": self.fingerprint_checksum,
            "live_checksum": self.live_checksum,
            "drifts": [d.to_dict() for d in self.drifts],
        }


def detect_drift(
    fingerprint: SchemaFingerprint,
    live_output: Any,
) -> DriftReport:
    """Compare a live LLM output against a stored fingerprint.

    This is the core diffing algorithm. It recursively walks both
    schemas and reports every structural deviation.

    Args:
        fingerprint: The frozen baseline schema.
        live_output: The fresh output dict from the LLM.

    Returns:
        A DriftReport with all detected drifts.
    """
    live_schema = infer_schema(live_output)
    live_checksum = _compute_checksum(live_schema)

    # Quick path: if checksums match, schemas are identical
    if fingerprint.checksum == live_checksum:
        return DriftReport(
            tool_name=fingerprint.tool_name,
            model=fingerprint.model,
            has_drift=False,
            fingerprint_checksum=fingerprint.checksum,
            live_checksum=live_checksum,
        )

    # Deep diff
    drifts: list[FieldDrift] = []
    _diff_schemas(fingerprint.json_schema, live_schema, drifts, prefix="", root_schema=fingerprint.json_schema)

    # Compute overall severity
    severity = _compute_severity(drifts)

    return DriftReport(
        tool_name=fingerprint.tool_name,
        model=fingerprint.model,
        has_drift=len(drifts) > 0,
        drifts=drifts,
        severity=severity,
        fingerprint_checksum=fingerprint.checksum,
        live_checksum=live_checksum,
    )


def _merge_branch(root: dict, branch: dict) -> dict:
    """Merges root properties dynamically into a topological branch to prevent Added Field bleeding. Protects nested routers."""
    # Guard: Boolean schemas (true = accept all, false = reject all)
    if not isinstance(branch, dict):
        if branch is True:
            return {}  # Accept anything — no constraints
        else:
            return {"not": {}}  # Reject everything — impossible schema
    
    clean_root = dict(root)  
    for k in ["anyOf", "oneOf", "allOf", "not"]:
        clean_root.pop(k, None)
        
    merged = dict(clean_root) 
    merged.update(branch)
    
    mp = dict(root.get("properties", {}))
    mp.update(branch.get("properties", {}))
    if mp: merged["properties"] = mp
    
    mr = list(root.get("required", []))
    mr.extend(branch.get("required", []))
    if mr: merged["required"] = list(set(mr))
    
    return merged

def _resolve_and_flatten_allofs(schema: dict, root: dict, seen: set = None) -> dict:
    if seen is None: seen = set()
    if id(schema) in seen: return schema
    seen.add(id(schema))
    
    if not isinstance(schema, dict):
        return schema
        
    # Process refs
    if "$ref" in schema:
        ref_path = schema["$ref"]
        if isinstance(ref_path, str):
            if ref_path.startswith("#/$defs/"):
                def_name = ref_path.replace("#/$defs/", "")
                resolved = root.get("$defs", {}).get(def_name, schema)
            elif ref_path.startswith("#/definitions/"):
                def_name = ref_path.replace("#/definitions/", "")
                resolved = root.get("definitions", {}).get(def_name, schema)
            else:
                resolved = schema
            
            new_schema = dict(schema)
            new_schema.pop("$ref", None)
            
            # Recurse on the resolved target
            resolved = _resolve_and_flatten_allofs(resolved, root, seen)
            
            if new_schema:
                schema = {"allOf": [resolved, new_schema]} # Becomes allOf, handled immediately below
            else:
                return resolved

    # Process allOf
    if "allOf" in schema:
        merged = dict(schema)
        mp = dict(schema.get("properties", {}))
        mr = list(schema.get("required", []))
        m_pattern_props = dict(schema.get("patternProperties", {}))
        
        # Collect logical gate collisions for nested intersection
        logic_gates = {"anyOf": [], "oneOf": [], "not": []}
        if "anyOf" in merged: logic_gates["anyOf"].append(merged.pop("anyOf"))
        if "oneOf" in merged: logic_gates["oneOf"].append(merged.pop("oneOf"))
        if "not" in merged: logic_gates["not"].append(merged.pop("not"))
        
        for exp_sub in schema["allOf"]:
            sub = _resolve_and_flatten_allofs(exp_sub, root, set(seen))
            
            # Merge standard object keys
            mp.update(sub.get("properties", {}))
            mr.extend(sub.get("required", []))
            m_pattern_props.update(sub.get("patternProperties", {}))
            
            # Accumulate logic gates for final intersection
            for gate in logic_gates:
                if gate in sub:
                    logic_gates[gate].append(sub[gate])
            
            # Carry forward all other constraints
            for carry_key, carry_val in sub.items():
                if carry_key not in ("properties", "required", "patternProperties", "allOf", "$ref", "anyOf", "oneOf", "not"):
                    if carry_key not in merged:
                        merged[carry_key] = carry_val
                        
        merged["properties"] = mp
        merged["required"] = list(set(mr))
        if m_pattern_props:
            merged["patternProperties"] = m_pattern_props
            
        # Re-apply intersected logic gates. 
        # If multiple branches have anyOf, the final object must satisfy ALL of them.
        nested_allOf = []
        for gate, constraints in logic_gates.items():
            if not constraints: continue
            if len(constraints) == 1:
                merged[gate] = constraints[0]
            else:
                # Collision! We must satisfy the intersection of these logic gates.
                for c in constraints:
                    nested_allOf.append({gate: c})
        
        merged.pop("allOf", None)
        if nested_allOf:
            merged["allOf"] = nested_allOf # Handled recursively in _diff_schemas
            
        return merged
        
    return schema


def _diff_schemas(
    expected: dict[str, Any],
    actual: dict[str, Any],
    drifts: list[FieldDrift],
    prefix: str,
    root_schema: dict[str, Any] | None = None,
) -> None:
    """Recursively diff two JSON Schema dicts."""
    # --- Boolean Schema Guard ---
    # JSON Schema allows True (accept anything) and False (reject everything) as schemas.
    if not isinstance(expected, dict):
        if expected is False:
            drifts.append(FieldDrift(field=prefix or "(root)", drift_type="boolean_schema", expected="(nothing allowed)", actual=str(actual.get("type", "any")), severity="major"))
        return  # True = accept anything, so no drift possible
    if not isinstance(actual, dict):
        return  # Can't diff non-dict actual schemas

    if root_schema is None:
        root_schema = expected

    # --- Pre-computation: Deep Topographical Flattening ---
    # Pydantic generates multi-inheritance models using heavily nested $ref and allOf arrays.
    # To mathematically validate the payload against the intersection of inherited constraints,
    # we completely resolve pointers and merge properties prior to evaluation.
    expected = _resolve_and_flatten_allofs(expected, root_schema)

    # --- Native AnyOf Sub-Branch Resolution ---
    if "anyOf" in expected:
        best_drifts = None
        for exp_sub in expected["anyOf"]:
            branch_drifts = []
            _diff_schemas(_merge_branch(expected, exp_sub), actual, branch_drifts, prefix, root_schema=root_schema)
            if not branch_drifts:
                best_drifts = [] # Perfect match
                break
            if best_drifts is None or len(branch_drifts) < len(best_drifts):
                best_drifts = branch_drifts
        if best_drifts:
            drifts.extend(best_drifts)
        return

    # If the Baseline discriminates structures, the LLM must match EXACTLY ONE.
    if "oneOf" in expected:
        pass_count = 0
        best_drifts = None
        for exp_sub in expected["oneOf"]:
            branch_drifts = []
            _diff_schemas(_merge_branch(expected, exp_sub), actual, branch_drifts, prefix, root_schema=root_schema)
            if not branch_drifts:
                pass_count += 1
            elif best_drifts is None or len(branch_drifts) < len(best_drifts):
                best_drifts = branch_drifts
        if pass_count != 1:
            if best_drifts:
                drifts.extend(best_drifts)
            else:
                drifts.append(FieldDrift(field=prefix or "(root)", drift_type="oneOf_violation", expected="Exactly 1 Discriminator", actual=f"{pass_count} discriminators matches", severity="major"))
        return

    # If the Baseline explicitly forbids a structure, the LLM must mathematically fail it.
    if "not" in expected:
        inv_drifts = []
        _diff_schemas(expected["not"], actual, inv_drifts, prefix, root_schema=root_schema)
        if not inv_drifts:
            drifts.append(FieldDrift(field=prefix or "(root)", drift_type="not_violation", expected="Inverse Schema Block", actual="Successfully bypassed NOT filter", severity="major"))
            return

    # --- Type Constraint ---
    exp_type_raw = expected.get("type", "any")
    exp_types = exp_type_raw if isinstance(exp_type_raw, list) else [exp_type_raw]

    act_type_raw = actual.get("type", "any")
    act_types = act_type_raw if isinstance(act_type_raw, list) else [act_type_raw]

    # Type-level drift
    # Check if any emitted empirical type violates the allowed baseline types
    violating_types = []
    for at in act_types:
        if at not in exp_types and "any" not in exp_types:
            # False Positive Guard 1: Allow ints when floats (number) are expected natively
            if at == "integer" and "number" in exp_types:
                continue
            # False Positive Guard 2: 'null' natively matches 'null' strings in AnyOf
            if at == "null" and "null" in exp_types:
                continue
            # False Positive Guard 3: Allow exact floats (10.0) when integer is expected
            # JSON serializers often emit 10.0 for what is logically an integer.
            if at == "number" and "integer" in exp_types:
                act_val = actual.get("_value")
                if isinstance(act_val, float) and act_val.is_integer():
                    continue
            violating_types.append(at)

    if violating_types:
        field_path = prefix or "(root)"
        act_str = act_type_raw if isinstance(act_type_raw, str) else "|".join(act_type_raw)
        
        severity = "major"
        if all(t in ("null", "unknown") for t in violating_types):
            severity = "minor"
            
        drifts.append(FieldDrift(
            field=field_path,
            drift_type="type_changed",
            expected="|".join(exp_types),
            actual=act_str,
            severity=severity,
        ))
        return  # Can't diff structural children if parent types diverged

    # Range Constraint Bound Enforcer (Prevents DoS string overflows and math out-of-bounds)
    act_val = actual.get("_value")
    if act_val is not None:
        if isinstance(act_val, (int, float)):
            if "minimum" in expected and act_val < expected["minimum"]:
                drifts.append(FieldDrift(field=prefix or "(root)", drift_type="bound_violation", expected=f">= {expected['minimum']}", actual=str(act_val), severity="major"))
            if "maximum" in expected and act_val > expected["maximum"]:
                drifts.append(FieldDrift(field=prefix or "(root)", drift_type="bound_violation", expected=f"<= {expected['maximum']}", actual=str(act_val), severity="major"))
            if "exclusiveMinimum" in expected and act_val <= expected["exclusiveMinimum"]:
                drifts.append(FieldDrift(field=prefix or "(root)", drift_type="bound_violation", expected=f"> {expected['exclusiveMinimum']}", actual=str(act_val), severity="major"))
            if "exclusiveMaximum" in expected and act_val >= expected["exclusiveMaximum"]:
                drifts.append(FieldDrift(field=prefix or "(root)", drift_type="bound_violation", expected=f"< {expected['exclusiveMaximum']}", actual=str(act_val), severity="major"))
            if "multipleOf" in expected:
                try:
                    if not math.isclose(act_val % expected["multipleOf"], 0, abs_tol=1e-9) and act_val % expected["multipleOf"] != 0:
                        drifts.append(FieldDrift(field=prefix or "(root)", drift_type="bound_violation", expected=f"% {expected['multipleOf']} == 0", actual=str(act_val), severity="major"))
                except BaseException: pass
        if isinstance(act_val, str):
            if "minLength" in expected and len(act_val) < expected["minLength"]:
                drifts.append(FieldDrift(field=prefix or "(root)", drift_type="bound_violation", expected=f"len >= {expected['minLength']}", actual=f"len {len(act_val)}", severity="major"))
            if "maxLength" in expected and len(act_val) > expected["maxLength"]:
                drifts.append(FieldDrift(field=prefix or "(root)", drift_type="bound_violation", expected=f"len <= {expected['maxLength']}", actual=f"len {len(act_val)}", severity="major"))
            if "pattern" in expected:
                try:
                    if not re.search(expected["pattern"], act_val):
                        drifts.append(FieldDrift(field=prefix or "(root)", drift_type="pattern_violation", expected=f"regex({expected['pattern']})", actual=act_val, severity="major"))
                except re.error:
                    pass  # Gracefully ignore invalid pydantic regex formulation

    # Format-level drift (e.g., date -> date-time)
    exp_fmt = expected.get("format", "")
    act_fmt = actual.get("format", "")
    if exp_fmt != act_fmt:
        # Supreme Security Fix: Hard-block string format evasions on supported network regexes
        supported_formats = {"date", "date-time", "email", "uri", "uuid", "ipv4", "ipv6"}
        severity = "minor"
        if exp_fmt in supported_formats and act_fmt == "":
            severity = "major"  # Escalated to stop payload bypasses and server 500 crashes
            
        field_path = prefix or "(root)"
        drifts.append(FieldDrift(
            field=field_path,
            drift_type="format_changed",
            expected=exp_fmt or "(none)",
            actual=act_fmt or "(none)",
            severity=severity,
        ))

    # Enum Constraint Bounds (Literal Verification)
    exp_enum = expected.get("enum")
    exp_const = expected.get("const")
    
    if exp_enum is not None:
        act_val = actual.get("_value")
        if "_value" in actual and act_val not in exp_enum:
            field_path = prefix or "(root)"
            drifts.append(FieldDrift(
                field=field_path,
                drift_type="enum_violation",
                expected=str(exp_enum),
                actual=str(act_val),
                severity="major", # Hard block for Enum evasion
            ))
            
    if exp_const is not None:
        act_val = actual.get("_value")
        if "_value" in actual and act_val != exp_const:
            drifts.append(FieldDrift(
                field=prefix or "(root)",
                drift_type="const_violation",
                expected=str(exp_const),
                actual=str(act_val),
                severity="major" # Hard block for Const literal evasion
            ))

    # Object-level: compare properties
    if "object" in exp_types or exp_type_raw == "object":
        exp_props = expected.get("properties", {})
        act_props = actual.get("properties", {})
        exp_keys = set(exp_props.keys())
        act_keys = set(act_props.keys())
        exp_required = set(expected.get("required", []))
        
        # Object Structural Overload Guard
        if "minProperties" in expected and len(act_keys) < expected["minProperties"]:
            drifts.append(FieldDrift(field=prefix or "(root)", drift_type="bound_violation", expected=f">= {expected['minProperties']} props", actual=f"{len(act_keys)} props", severity="major"))
        if "maxProperties" in expected and len(act_keys) > expected["maxProperties"]:
            drifts.append(FieldDrift(field=prefix or "(root)", drift_type="bound_violation", expected=f"<= {expected['maxProperties']} props", actual=f"{len(act_keys)} props", severity="major"))

        # Missing fields (in baseline, missing in live)
        for key in exp_keys - act_keys:
            path = f"{prefix}.{key}" if prefix else key
            exp_required_key = key in exp_required
            
            # Massive False-Positive Guard:
            # If the missing field is technically completely optional according
            # to the schema payload, it structurally passes validation.
            if not exp_required_key:
                continue

            drifts.append(FieldDrift(
                field=path,
                drift_type="removed",
                expected=exp_props[key].get("type", "unknown"),
                actual="(missing)",
                severity="major",
            ))

        # Conditional Dependent Requirements (If A exists, B must exist)
        exp_deps = expected.get("dependentRequired", {})
        for cond_key, req_list in exp_deps.items():
            if cond_key in act_keys:
                for req in req_list:
                    if req not in act_keys:
                        path = f"{prefix}.{req}" if prefix else req
                        drifts.append(FieldDrift(field=path, drift_type="missing_dependent", expected=f"required by conditional <{cond_key}>", actual="(not present)", severity="major"))

        # Added fields (new in live, not in baseline)
        add_prop = expected.get("additionalProperties")
        uneval_prop = expected.get("unevaluatedProperties")
        pattern_props = expected.get("patternProperties", {})
        for key in act_keys - exp_keys:
            path = f"{prefix}.{key}" if prefix else key
            
            # Security Exception 1: Allow dynamic mapped Dict[K,V]
            if add_prop is True:
                continue
            elif add_prop is False:
                drifts.append(FieldDrift(
                    field=path,
                    drift_type="additional_blocked",
                    expected="(no additional properties)",
                    actual=str(act_props[key].get("type", "any")),
                    severity="major",
                ))
                continue
            elif isinstance(add_prop, dict):
                _diff_schemas(add_prop, act_props[key], drifts, prefix=path, root_schema=root_schema)
                continue
            
            # Security Exception 2: Allow patternProperties regex-matched keys
            matched_pattern = False
            for pat, pat_schema in pattern_props.items():
                try:
                    if re.search(pat, key):
                        _diff_schemas(pat_schema, act_props[key], drifts, prefix=path, root_schema=root_schema)
                        matched_pattern = True
                        break
                except re.error:
                    pass
            if matched_pattern:
                continue
            
            # Strict Mode: unevaluatedProperties acts like additionalProperties
            # for properties not covered by any sub-schema (allOf/oneOf/anyOf)
            if uneval_prop is False:
                drifts.append(FieldDrift(
                    field=path,
                    drift_type="unevaluated",
                    expected="(not permitted)",
                    actual=str(act_props[key].get("type", "any")),
                    severity="major",
                ))
                continue
            elif isinstance(uneval_prop, dict):
                _diff_schemas(uneval_prop, act_props[key], drifts, prefix=path, root_schema=root_schema)
                continue
                
            drifts.append(FieldDrift(
                field=path,
                drift_type="added",
                expected="(not present)",
                actual=str(act_props[key].get("type", "any")),
                severity="major",
            ))

        # Dictionary Key Regex Name Enforcement
        prop_names = expected.get("propertyNames")
        if prop_names:
            for key in act_keys:
                key_schema = {"type": "string", "_value": key}
                # Dynamically validate the Key itself against the Regex constraints
                _diff_schemas(prop_names, key_schema, drifts, prefix=f"{prefix}.<key:{key}>" if prefix else f"<key:{key}>", root_schema=root_schema)

        # Common fields: recurse
        for key in exp_keys & act_keys:
            path = f"{prefix}.{key}" if prefix else key
            _diff_schemas(exp_props[key], act_props[key], drifts, prefix=path, root_schema=root_schema)

    # Array-level: compare items schema
    elif "array" in exp_types or exp_type_raw == "array":
        # Array Structural Overload Guard
        act_positional = actual.get("_positional_items", [])
        items_prefix = f"{prefix}[]" if prefix else "[]"
        if "minItems" in expected and len(act_positional) < expected["minItems"]:
            drifts.append(FieldDrift(field=prefix or "(root)", drift_type="bound_violation", expected=f">= {expected['minItems']} items", actual=f"{len(act_positional)} items", severity="major"))
        if "maxItems" in expected and len(act_positional) > expected["maxItems"]:
            drifts.append(FieldDrift(field=prefix or "(root)", drift_type="bound_violation", expected=f"<= {expected['maxItems']} items", actual=f"{len(act_positional)} items", severity="major"))

        # Unique Items Enforcement (Set[T] -> uniqueItems: true)
        if expected.get("uniqueItems") is True and act_positional:
            seen_hashes = set()
            for idx, item in enumerate(act_positional):
                item_hash = json.dumps(item, sort_keys=True)
                if item_hash in seen_hashes:
                    drifts.append(FieldDrift(field=f"{items_prefix}[{idx}]", drift_type="unique_violation", expected="unique items", actual="duplicate found", severity="major"))
                    break
                seen_hashes.add(item_hash)

        # Deep Array Mathematical Substring Loop (contains)
        exp_contains = expected.get("contains")
        if exp_contains is not None:
            matches = 0
            for r_item in act_positional:
                c_drifts = []
                _diff_schemas(exp_contains, r_item, c_drifts, prefix, root_schema=root_schema)
                if not c_drifts:
                    matches += 1
            min_c = expected.get("minContains", 1)  # Default sequence is 1
            max_c = expected.get("maxContains")
            if matches < min_c:
                drifts.append(FieldDrift(field=items_prefix, drift_type="contains_violation", expected=f">= {min_c} sub-matches required", actual=f"{matches} sub-matches found", severity="major"))
            if max_c is not None and matches > max_c:
                drifts.append(FieldDrift(field=items_prefix, drift_type="contains_violation", expected=f"<= {max_c} sub-matches required", actual=f"{matches} sub-matches found", severity="major"))

        # 1. Handle Positional Items (prefixItems) natively without restrictive length guards
        exp_prefix = expected.get("prefixItems", [])
        if not isinstance(exp_prefix, list): exp_prefix = []
        for idx in range(min(len(exp_prefix), len(act_positional))):
            _diff_schemas(exp_prefix[idx], act_positional[idx], drifts, prefix=f"{items_prefix}[{idx}]", root_schema=root_schema)

        # 2. Check un-evaluated tail items (past prefixItems)
        tail_index = len(exp_prefix)
        tail_items = act_positional[tail_index:]

        # 3. Apply `items` or `unevaluatedItems` constraint to the tail elements
        # Handle strict prohibitions (e.g. Items: False blocks anything beyond prefixItems)
        if expected.get("unevaluatedItems") is False or expected.get("items") is False:
            if tail_items:
                drifts.append(FieldDrift(
                    field=f"{items_prefix}[{tail_index}:]",
                    drift_type="unevaluated_items",
                    expected="(no additional items permitted)",
                    actual=f"{len(tail_items)} unpermitted items found",
                    severity="major"
                ))
            return # Block subsequent evaluations
            
        # 4. Standard Items mapping
        exp_items = expected.get("items", {})
        if exp_items and isinstance(exp_items, dict):
            # Iterate through the tail and validate EACH specific item against the bounding schema
            # This is mathematically superior to union-comparison as it tracks exact violating coordinates
            for idx, t_item in enumerate(tail_items, start=tail_index):
                _diff_schemas(exp_items, t_item, drifts, prefix=f"{items_prefix}[{idx}]", root_schema=root_schema)


def _compute_severity(drifts: list[FieldDrift]) -> str:
    """Compute overall severity from individual field drifts."""
    if not drifts:
        return "none"

    severities = {d.severity for d in drifts}
    if "critical" in severities:
        return "critical"
    if "major" in severities:
        return "major"
    return "minor"
