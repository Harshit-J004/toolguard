"""
test_semantic_engine.py
~~~~~~~~~~~~~~~~~~~~~~~
End-to-end proof script for the ToolGuard Semantic Policy Engine.

Tests all 7 constraint types across Tier 1 (rule-based) and Tier 2 (context-aware).
"""

import sys
import os

# Ensure the toolguard package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["TOOLGUARD_AUTO_APPROVE"] = "1"

from toolguard.mcp.semantic import SemanticEngine, SessionContext, SemanticResult
from toolguard.mcp.interceptor import MCPInterceptor
from toolguard.mcp.policy import MCPPolicy

passed = 0
failed = 0

def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name} — {detail}")


# ──────────────────────────────────────────────
#  Build a comprehensive semantic policy
# ──────────────────────────────────────────────

POLICY = {
    "tools": {
        "read_file": {
            "constraints": [
                {
                    "type": "path_deny",
                    "paths": ["/etc/passwd", "/etc/shadow", "*.env", "*/.ssh/*"],
                    "reason": "Access to system/secret files is prohibited",
                },
                {
                    "type": "path_allow",
                    "paths": ["/workspace/*", "/tmp/*"],
                    "reason": "Agent may only access workspace or temp files",
                },
            ]
        },
        "execute_sql": {
            "constraints": [
                {
                    "type": "regex_deny",
                    "field": "query",
                    "patterns": [r"DROP\s+TABLE", r"DELETE\s+FROM", r"TRUNCATE", r"ALTER\s+TABLE"],
                    "reason": "Destructive SQL operations are forbidden",
                },
                {
                    "type": "value_allow",
                    "field": "query",
                    "patterns": ["SELECT *"],
                    "reason": "Only SELECT queries are permitted",
                },
            ]
        },
        "send_email": {
            "constraints": [
                {
                    "type": "value_deny",
                    "field": "recipient",
                    "patterns": ["*@internal.company.com", "*admin*"],
                    "reason": "Agent cannot email internal company addresses",
                },
            ]
        },
        "delete_user": {
            "constraints": [
                {
                    "type": "context_check",
                    "require_prior_tool": "get_user_details",
                    "reason": "Must look up user details before deleting",
                },
                {
                    "type": "max_scope",
                    "field": "user_id",
                    "max_per_session": 3,
                    "reason": "Cannot delete more than 3 users per session",
                },
            ]
        },
    }
}


def run_tests():
    engine = SemanticEngine.from_policy_dict(POLICY)

    # ──────────────────────────────────────────
    print("\n🛡️  TIER 1: Rule-Based Constraints")
    print("─" * 50)

    # 1. Path Deny
    print("\n📁 Path Deny Rules:")
    r = engine.evaluate("read_file", {"path": "/etc/passwd"})
    check("Block /etc/passwd", not r.allowed, r.reason)

    r = engine.evaluate("read_file", {"path": "/etc/shadow"})
    check("Block /etc/shadow", not r.allowed, r.reason)

    r = engine.evaluate("read_file", {"path": "/home/user/.env"})
    check("Block *.env files", not r.allowed, r.reason)

    r = engine.evaluate("read_file", {"path": "/home/user/.ssh/id_rsa"})
    check("Block .ssh/* paths", not r.allowed, r.reason)

    # 2. Path Allow (whitelist)
    print("\n📂 Path Allow Rules:")
    r = engine.evaluate("read_file", {"path": "/workspace/data.csv"})
    check("Allow /workspace/data.csv", r.allowed, r.reason)

    r = engine.evaluate("read_file", {"path": "/tmp/scratch.txt"})
    check("Allow /tmp/scratch.txt", r.allowed, r.reason)

    r = engine.evaluate("read_file", {"path": "/var/log/syslog"})
    check("Block /var/log/syslog (not in whitelist)", not r.allowed, r.reason)

    # 3. Regex Deny (SQL)
    print("\n🔍 Regex Deny Rules:")
    r = engine.evaluate("execute_sql", {"query": "DROP TABLE users"})
    check("Block DROP TABLE", not r.allowed, r.reason)

    r = engine.evaluate("execute_sql", {"query": "DELETE FROM customers WHERE id=5"})
    check("Block DELETE FROM", not r.allowed, r.reason)

    r = engine.evaluate("execute_sql", {"query": "TRUNCATE orders"})
    check("Block TRUNCATE", not r.allowed, r.reason)

    r = engine.evaluate("execute_sql", {"query": "ALTER TABLE users ADD COLUMN age"})
    check("Block ALTER TABLE", not r.allowed, r.reason)

    # 4. Value Allow (SQL SELECT only)
    print("\n✅ Value Allow Rules:")
    r = engine.evaluate("execute_sql", {"query": "SELECT * FROM users"})
    check("Allow SELECT query", r.allowed, r.reason)

    r = engine.evaluate("execute_sql", {"query": "INSERT INTO users VALUES (1, 'a')"})
    check("Block INSERT (not SELECT)", not r.allowed, r.reason)

    # 5. Value Deny (Email)
    print("\n📧 Value Deny Rules:")
    r = engine.evaluate("send_email", {"recipient": "ceo@internal.company.com"})
    check("Block internal company email", not r.allowed, r.reason)

    r = engine.evaluate("send_email", {"recipient": "admin@gmail.com"})
    check("Block admin-pattern email", not r.allowed, r.reason)

    r = engine.evaluate("send_email", {"recipient": "user@external.com"})
    check("Allow external email", r.allowed, r.reason)

    # ──────────────────────────────────────────
    print("\n🧠 TIER 2: Context-Aware Constraints")
    print("─" * 50)

    session = SessionContext()

    # 6. Context Check (require prior tool)
    print("\n🔗 Context Dependency Rules:")
    r = engine.evaluate("delete_user", {"user_id": "123"}, session)
    check("Block delete_user without prior get_user_details", not r.allowed, r.reason)

    # Simulate calling get_user_details first
    session.record_call("get_user_details", {"user_id": "123"})
    r = engine.evaluate("delete_user", {"user_id": "123"}, session)
    check("Allow delete_user after get_user_details", r.allowed, r.reason)

    # 7. Scope Limit (max per session)
    print("\n🔒 Scope Limit Rules:")
    session2 = SessionContext()
    session2.record_call("get_user_details", {"user_id": "1"})  # satisfy context

    # Delete 3 unique users (should all succeed)
    session2.record_call("delete_user", {"user_id": "1"})
    session2.record_call("delete_user", {"user_id": "2"})
    session2.record_call("delete_user", {"user_id": "3"})

    # 4th unique user should be blocked
    r = engine.evaluate("delete_user", {"user_id": "4"}, session2)
    check("Block 4th unique user deletion (max_scope=3)", not r.allowed, r.reason)

    # Repeating an existing user_id should still be allowed
    r = engine.evaluate("delete_user", {"user_id": "1"}, session2)
    check("Allow repeat of existing user_id (not a new unique value)", r.allowed, r.reason)

    # ──────────────────────────────────────────
    print("\n🔌 INTEGRATION: Full 6-Layer Interceptor Pipeline")
    print("─" * 50)

    # Build a full MCPPolicy with semantic constraints
    full_policy = MCPPolicy.from_yaml_dict({
        "tools": {
            "read_file": {
                "risk_tier": 0,
                "constraints": [
                    {
                        "type": "path_deny",
                        "paths": ["/etc/passwd"],
                        "reason": "System file access denied",
                    }
                ],
            },
            "execute_code": {
                "blocked": True,
            },
        }
    })

    interceptor = MCPInterceptor(full_policy, verbose=False)

    # Test Layer 1 (Policy block)
    r = interceptor.intercept("execute_code", {"code": "import os"})
    check("Layer 1: execute_code blocked by policy", not r.allowed)

    # Test Layer 5 (Semantic block)
    r = interceptor.intercept("read_file", {"path": "/etc/passwd"})
    check("Layer 5: read_file /etc/passwd blocked by semantic policy", not r.allowed)
    check("Layer 5: Correct layer reported", r.layer == "semantic", f"got: {r.layer}")

    # Test clean passthrough
    r = interceptor.intercept("read_file", {"path": "/workspace/safe.txt"})
    check("Layer 5: read_file /workspace/safe.txt allowed (no deny match)", r.allowed)

    # ──────────────────────────────────────────
    print("\n" + "═" * 50)
    print(f"  🏁 RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("═" * 50)

    if failed > 0:
        print("\n❌ SOME TESTS FAILED!")
        sys.exit(1)
    else:
        print("\n🛡️  ALL SEMANTIC POLICY ENGINE TESTS PASSED! 🔥")
        sys.exit(0)


if __name__ == "__main__":
    run_tests()
