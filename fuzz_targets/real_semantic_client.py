"""
real_semantic_client.py
~~~~~~~~~~~~~~~~~~~~~~~
Real-world integration test for the ToolGuard Semantic Policy Engine.

Uses the OFFICIAL Anthropic `mcp` SDK to connect a genuine stdio_client
through the `toolguard proxy` with semantic constraints, proving that
the 7-layer interceptor works on live JSON-RPC traffic.
"""

import sys
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run_tests():
    server_cmd = sys.argv[1:] if len(sys.argv) > 1 else ["python", "fuzz_targets/real_semantic_server.py"]
    print(f"🔌 [Client] Connecting via: {' '.join(server_cmd)}")

    server_params = StdioServerParameters(
        command=server_cmd[0],
        args=server_cmd[1:],
    )

    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  ✅ {name}")
        else:
            failed += 1
            print(f"  ❌ {name} — {detail}")

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ [Client] Session initialized.\n")

                # ── TEST 1: Safe file read (should PASS) ──
                print("📁 Test 1: read_file('/workspace/data.csv') — should ALLOW")
                try:
                    result = await session.call_tool("read_file", arguments={"path": "/workspace/data.csv"})
                    check("Safe file read ALLOWED", True)
                    print(f"   Response: {result.content[0].text}\n")
                except Exception as e:
                    check("Safe file read ALLOWED", False, str(e))

                # ── TEST 2: System file read (should BLOCK via path_deny) ──
                print("🚫 Test 2: read_file('/etc/passwd') — should BLOCK (path_deny)")
                try:
                    result = await session.call_tool("read_file", arguments={"path": "/etc/passwd"})
                    check("System file BLOCKED by semantic policy", False, f"Got: {result.content[0].text}")
                except Exception as e:
                    check("System file BLOCKED by semantic policy", "Semantic Policy" in str(e) or "prohibited" in str(e).lower())
                    print(f"   Intercept: {e}\n")

                # ── TEST 3: .env file read (should BLOCK via path_deny) ──
                print("🚫 Test 3: read_file('/home/user/.env') — should BLOCK (path_deny)")
                try:
                    result = await session.call_tool("read_file", arguments={"path": "/home/user/.env"})
                    check(".env file BLOCKED by semantic policy", False, f"Got: {result.content[0].text}")
                except Exception as e:
                    check(".env file BLOCKED by semantic policy", "Semantic Policy" in str(e) or "prohibited" in str(e).lower())
                    print(f"   Intercept: {e}\n")

                # ── TEST 4: Safe SQL query (should PASS) ──
                print("✅ Test 4: execute_sql('SELECT * FROM users') — should ALLOW")
                try:
                    result = await session.call_tool("execute_sql", arguments={"query": "SELECT * FROM users"})
                    check("Safe SQL ALLOWED", True)
                    print(f"   Response: {result.content[0].text}\n")
                except Exception as e:
                    check("Safe SQL ALLOWED", False, str(e))

                # ── TEST 5: Destructive SQL (should BLOCK via regex_deny) ──
                print("🚫 Test 5: execute_sql('DROP TABLE users') — should BLOCK (regex_deny)")
                try:
                    result = await session.call_tool("execute_sql", arguments={"query": "DROP TABLE users"})
                    check("DROP TABLE BLOCKED by semantic policy", False, f"Got: {result.content[0].text}")
                except Exception as e:
                    check("DROP TABLE BLOCKED by semantic policy", "Semantic Policy" in str(e) or "forbidden" in str(e).lower())
                    print(f"   Intercept: {e}\n")

                # ── TEST 6: DELETE FROM (should BLOCK via regex_deny) ──
                print("🚫 Test 6: execute_sql('DELETE FROM orders WHERE id=5') — should BLOCK")
                try:
                    result = await session.call_tool("execute_sql", arguments={"query": "DELETE FROM orders WHERE id=5"})
                    check("DELETE FROM BLOCKED by semantic policy", False, f"Got: {result.content[0].text}")
                except Exception as e:
                    check("DELETE FROM BLOCKED by semantic policy", "Semantic Policy" in str(e) or "forbidden" in str(e).lower())
                    print(f"   Intercept: {e}\n")

                # ── TEST 7: Safe email (should PASS) ──
                print("✅ Test 7: send_email('user@external.com') — should ALLOW")
                try:
                    result = await session.call_tool("send_email", arguments={
                        "recipient": "user@external.com",
                        "subject": "Hello",
                        "body": "Test message"
                    })
                    check("External email ALLOWED", True)
                    print(f"   Response: {result.content[0].text}\n")
                except Exception as e:
                    check("External email ALLOWED", False, str(e))

                # ── TEST 8: Internal email (should BLOCK via value_deny) ──
                print("🚫 Test 8: send_email('ceo@internal.company.com') — should BLOCK")
                try:
                    result = await session.call_tool("send_email", arguments={
                        "recipient": "ceo@internal.company.com",
                        "subject": "Hack",
                        "body": "Malicious"
                    })
                    check("Internal email BLOCKED by semantic policy", False, f"Got: {result.content[0].text}")
                except Exception as e:
                    check("Internal email BLOCKED by semantic policy", "Semantic Policy" in str(e) or "company" in str(e).lower())
                    print(f"   Intercept: {e}\n")

                # ── RESULTS ──
                print("═" * 55)
                print(f"  🏁 REAL SDK RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
                print("═" * 55)

                if failed > 0:
                    print("\n❌ SOME TESTS FAILED!")
                else:
                    print("\n🛡️  ALL REAL-WORLD SEMANTIC POLICY TESTS PASSED! 🔥")

    except Exception as e:
        print(f"❌ [Client] Connection failed: {e}")


if __name__ == "__main__":
    asyncio.run(run_tests())
