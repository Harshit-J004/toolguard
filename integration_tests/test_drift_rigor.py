import json
from toolguard.core.drift import create_fingerprint, detect_drift, SchemaFingerprint

def run_test(name: str, baseline_json: dict, live_json: dict, expect_drift: bool, is_raw_schema: bool = False):
    print(f"\n--- Testing: {name} ---")
    if is_raw_schema:
        # Avoid inferring the schema if the test explicitly provides a Pydantic raw schema
        fp = SchemaFingerprint("test", "prompt", "model", "", baseline_json, {}, "")
    else:
        fp = create_fingerprint("test_tool", "prompt", "model", baseline_json)
        
    report = detect_drift(fp, live_json)
    
    status = "✅ PASS" if report.has_drift == expect_drift else "❌ FAIL"
    print(f"{status} | Expected Drift: {expect_drift} | Actual Drift: {report.has_drift}")
    
    if report.has_drift:
        for d in report.drifts:
            print(f"   🚨 [{d.severity.upper()}] {d.field}: {d.expected} -> {d.actual}")

def main():
    print("🧪 Running Rigorous Drift Logic Tests...")

    # 1. The Mixed-List Polymorphic Attack
    run_test(
        "Mixed-List Polymorphic Attack",
        baseline_json={"data": [1, 2, 3]},
        live_json={"data": [1, 2, "HACKED_STRING"]},
        expect_drift=True
    )
    
    # 2. Integer-to-Float Coercion False Positive
    run_test(
        "Int-to-Float Coercion False Positive",
        baseline_json={"price": 10.5},
        live_json={"price": 10},
        expect_drift=False
    )
    
    # 3. Empty Array False Positive
    run_test(
        "Empty Array False Positive",
        baseline_json={"tags": ["a", "b", "c"]},
        live_json={"tags": []},
        expect_drift=False
    )

    # 4. Nested-Object Map Polymorphism Attack
    run_test(
        "Nested-Object Polymorphism Bypass",
        baseline_json={"jobs": [{"cmd": "ping"}]},
        live_json={"jobs": [{"cmd": "ping"}, {"cmd": "rm -rf *", "hacked_flag": True}]},
        expect_drift=True
    )
    
    # 5. String Format Constraint Evasion
    run_test(
        "String Regex Format Evasion",
        baseline_json={"contact": "user@example.com"},
        live_json={"contact": "hack_the_planet"},
        expect_drift=True
    )

    # 6. AnyOf Union Execution
    run_test(
        "Pydantic AnyOf (Union) Success",
        baseline_json={"type": "object", "properties": {"data": {"anyOf": [{"type": "string"}, {"type": "integer"}]}}},
        live_json={"data": 100},
        expect_drift=False,
        is_raw_schema=True
    )
    
    # 7. Enum Literal Evasion
    run_test(
        "Enum (Literal) Constraint Evasion",
        baseline_json={"type": "object", "properties": {"state": {"type": "string", "enum": ["ACTIVE", "STANDBY"]}}},
        live_json={"state": "HACKED"},
        expect_drift=True,
        is_raw_schema=True
    )
    
    # 8. Bounds & Overflow Evasion
    # Baseline restricts length to 5. Live sends an overt overflow payload.
    run_test(
        "Domain Buffer Overflow Attack",
        baseline_json={"type": "object", "properties": {"password": {"type": "string", "maxLength": 5}}},
        live_json={"password": "hacked_buffer_overflow"},
        expect_drift=True,
        is_raw_schema=True
    )

    # 9. Dynamic Dictionary Verification (Dict[K, V])
    # Baseline allows added arbitrary integers. Live sends a new dynamic key safely.
    run_test(
        "Dynamic Mapped Object (additionalProperties) Success",
        baseline_json={"type": "object", "properties": {"static": {"type": "string"}}, "additionalProperties": {"type": "integer"}},
        live_json={"static": "hello", "dynamic_key_1": 100},
        expect_drift=False,
        is_raw_schema=True
    )
    
    # 10. Strict Tuple Positional Tracking
    # Baseline expects [integer, string]. Live inverts it to [string, integer].
    run_test(
        "Positional Tuple Index Evasion",
        baseline_json={"type": "array", "prefixItems": [{"type": "integer"}, {"type": "string"}]},
        live_json=[ "hacked", 1 ],
        expect_drift=True,
        is_raw_schema=True
    )
    
    # 11. Custom Regex 'pattern' Injection
    run_test(
        "Regex Pattern Injection",
        baseline_json={"type": "object", "properties": {"user_id": {"type": "string", "pattern": "^user_\\d{4}$"}}},
        live_json={"user_id": "user_1234_DROP_TABLE_USERS"},
        expect_drift=True,
        is_raw_schema=True
    )

    # 12. allOf Pydantic Inheritance Composition
    run_test(
        "Inherited Class 'allOf' Composition",
        baseline_json={"type": "object", "allOf": [{"type": "object", "properties": {"base_id": {"type": "integer"}}}], "properties": {"child_id": {"type": "integer"}}},
        live_json={"base_id": 1, "child_id": 2},
        expect_drift=False,
        is_raw_schema=True
    )

    # 13. oneOf Discriminated Union Exact Match
    run_test(
        "Discriminated Union 'oneOf' Evasion",
        baseline_json={"type": "object", "oneOf": [{"type": "object", "properties": {"a": {"type": "integer"}}}, {"type": "object", "properties": {"b": {"type": "string"}}}]},
        live_json={"a": 1, "b": "hacked"},  # Fails discriminator because it matches BOTH or NEITHER cleanly if discriminated. Actually matches neither perfectly if 'additionalProperties' is false, but here we test structural branch failures. Wait, if it matches both, pass_count=2 -> drift.
        expect_drift=True,
        is_raw_schema=True
    )

    # 14. Structural Array Overload 'maxItems'
    run_test(
        "Structural Capacity 'maxItems' Overload",
        baseline_json={"type": "array", "maxItems": 2, "items": {"type": "integer"}},
        live_json=[1, 2, 3],
        expect_drift=True,
        is_raw_schema=True
    )

    # 15. Inverse Constraint 'not' Evasion
    run_test(
        "Inverse Schema 'not' Exclusion",
        baseline_json={"not": {"type": "string"}},
        live_json="hacked",
        expect_drift=True,
        is_raw_schema=True
    )

    # 16. Structural Array Substring 'contains'
    run_test(
        "Array Substring Match 'contains'",
        baseline_json={"type": "array", "contains": {"type": "string"}, "minContains": 1},
        live_json=[1, 2, 3], # Array of ints, does not contain the required string
        expect_drift=True,
        is_raw_schema=True
    )

    # 17. Literal Single Bind 'const'
    run_test(
        "Literal Exact Match 'const'",
        baseline_json={"type": "string", "const": "ADMIN_ONLY"},
        live_json="hacked",
        expect_drift=True,
        is_raw_schema=True
    )

    # 18. Pattern Object Names 'propertyNames'
    run_test(
        "Key-Level Regex Injection 'propertyNames'",
        baseline_json={"type": "object", "propertyNames": {"pattern": "^user_\\d+$"}},
        live_json={"SQL_INJECT_DROP_TABLE": "data"},
        expect_drift=True,
        is_raw_schema=True
    )

    # 19. Dependent Conditionals 'dependentRequired'
    run_test(
        "Conditional Authentication 'dependentRequired'",
        baseline_json={"type": "object", "properties": {"password_hash": {"type": "string"}}, "dependentRequired": {"password_hash": ["salt"]}},
        live_json={"password_hash": "asdf123"}, # Forgot the salt!
        expect_drift=True,
        is_raw_schema=True
    )

    # 20. Network String Format Escape (UUID)
    run_test(
        "Network String UUID Format Evasion",
        baseline_json={"type": "string", "format": "uuid"},
        live_json="inject_sql_string_here",
        expect_drift=True,
        is_raw_schema=True
    )

    # 21. Topological Context Erasure (Nested Branches)
    run_test(
        "Topological Context Erasure (Nested Branches)",
        baseline_json={"type": "object", "anyOf": [ {"oneOf": [ {"properties": {"discriminator": {"type": "integer"}}} ]} ]},
        live_json={"discriminator": "hacked"},
        expect_drift=True,
        is_raw_schema=True
    )

    # 22. Float-to-Integer Coercion (10.0 → integer should pass)
    run_test(
        "Float-to-Int Silent Coercion (10.0)",
        baseline_json={"type": "object", "properties": {"count": {"type": "integer"}}},
        live_json={"count": 10.0},
        expect_drift=False,
        is_raw_schema=True
    )

    # 23. patternProperties Regex-Mapped Dictionary
    run_test(
        "patternProperties Regex Dictionary (No False Positive)",
        baseline_json={"type": "object", "patternProperties": {"^user_\\d+$": {"type": "integer"}}},
        live_json={"user_001": 42, "user_999": 7},
        expect_drift=False,
        is_raw_schema=True
    )

    # 24. unevaluatedProperties Strict Mode Block
    run_test(
        "unevaluatedProperties Strict Mode Block",
        baseline_json={"type": "object", "properties": {"id": {"type": "integer"}}, "unevaluatedProperties": False},
        live_json={"id": 1, "injected_field": "hacked"},
        expect_drift=True,
        is_raw_schema=True
    )

    # 25. additionalProperties: false explicit block
    run_test(
        "additionalProperties False Block",
        baseline_json={"type": "object", "properties": {"id": {"type": "integer"}}, "additionalProperties": False},
        live_json={"id": 1, "hacked": "injected"},
        expect_drift=True,
        is_raw_schema=True
    )

    # 26. allOf constraint propagation (sub-schema carries additionalProperties:false)
    run_test(
        "allOf Constraint Propagation",
        baseline_json={"type": "object", "allOf": [{"properties": {"base": {"type": "string"}}, "additionalProperties": False}], "properties": {"child": {"type": "integer"}}},
        live_json={"base": "ok", "child": 1, "injected": "hacked"},
        expect_drift=True,
        is_raw_schema=True
    )

    # 27. items: false blocks all array items
    run_test(
        "items False Array Block",
        baseline_json={"type": "array", "items": False},
        live_json=[1, 2, 3],
        expect_drift=True,
        is_raw_schema=True
    )

    # 28. Boolean schema True in anyOf (should NOT crash)
    run_test(
        "Boolean Schema True in anyOf (No Crash)",
        baseline_json={"anyOf": [True, {"type": "string"}]},
        live_json=42,
        expect_drift=False,  # True branch accepts anything
        is_raw_schema=True
    )

    # 29. Boolean schema False (should block everything)
    run_test(
        "Boolean Schema False Blocks All",
        baseline_json=False,
        live_json="anything",
        expect_drift=True,
        is_raw_schema=True
    )

    # 30. uniqueItems enforcement (Set[T] duplicate detection)
    run_test(
        "uniqueItems Duplicate Detection (Set)",
        baseline_json={"type": "array", "uniqueItems": True, "items": {"type": "integer"}},
        live_json=[1, 2, 3, 2],
        expect_drift=True,
        is_raw_schema=True
    )

    # 31. Nested $ref vulnerability patch
    run_test(
        "Nested $ref Resolution Vulnerability",
        baseline_json={
            "type": "object",
            "properties": {"user": {"$ref": "#/$defs/User"}},
            "$defs": {
                "User": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"]
                }
            }
        },
        live_json={
            "user": {"hacked": "bypassed"}
        },
        expect_drift=True, # Should correctly flag missing 'name' and added 'hacked' inside the resolved ref schema
        is_raw_schema=True
    )

    # 32. Variable-Length Tuple (Unconstrained Tail)
    run_test(
        "Variable-Length Tuple (No Tail Constraint) Success",
        baseline_json={
            "type": "array",
            "prefixItems": [{"type": "integer"}]
        },
        live_json=[1, "arbitrary", True, {}],  # Positional index 0 matches, tail allows anything
        expect_drift=False,
        is_raw_schema=True
    )

    # 33. Constrained-Tail Tuple (items keyword)
    run_test(
        "Variable-Length Tuple (Constrained Tail) Evasion",
        baseline_json={
            "type": "array",
            "prefixItems": [{"type": "string"}],
            "items": {"type": "integer"}
        },
        live_json=["ok", 1, 2, "hacked", 4], # Positional 0 string matches, items 1 and 2 integers match, item 3 string fails "items": integer.
        expect_drift=True,
        is_raw_schema=True
    )

    # 34. Deep Multi-Inheritance Dropping
    run_test(
        "Nested Multi-Inheritance (allOf loop dropping) Evasion",
        baseline_json={
            "allOf": [
                {"$ref": "#/$defs/ParentA"},
                {"$ref": "#/$defs/ParentB"}
            ],
            "$defs": {
                "ParentA": {
                    "allOf": [
                        {"type": "object", "properties": {"grand_a": {"type": "integer"}}, "required": ["grand_a"]}
                    ]
                },
                "ParentB": {
                    "type": "object", "properties": {"grand_b": {"type": "string"}}, "required": ["grand_b"]
                }
            }
        },
        live_json={"grand_a": 1}, # Missing grand_b from second branch, which used to be dropped!
        expect_drift=True,
        is_raw_schema=True
    )

if __name__ == "__main__":
    main()
