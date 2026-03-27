import sys
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_client():
    # If arguments are provided, use them as the server command (e.g., toolguard proxy ...)
    server_cmd = sys.argv[1:] if len(sys.argv) > 1 else ["python", "fuzz_targets/real_mcp_server.py"]
    print(f"🔌 [Client] Connecting via: {' '.join(server_cmd)}")
    
    server_params = StdioServerParameters(
        command=server_cmd[0],
        args=server_cmd[1:],
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ [Client] Session initialized with server.\n")
                
                # ── Test 1: Safe Tool (Should Pass) ──
                print("🧪 [Client] Attempting to call safe tool: get_weather('Tokyo')")
                try:
                    result = await session.call_tool("get_weather", arguments={"location": "Tokyo"})
                    print(f"✅ [Client] Safe tool executed successfully.")
                    print(f"   Response: {result.content[0].text}\n")
                except Exception as e:
                    print(f"❌ [Client] Unexpectedly failed: {e}\n")

                # ── Test 2: Dangerous Tool (Should Block via ToolGuard) ──
                print("⚠️ [Client] Attempting to call dangerous tool: execute_sql('DROP TABLE users')")
                try:
                    result = await session.call_tool("execute_sql", arguments={"query": "DROP TABLE users"})
                    print(f"❌ [Client] FATAL: Dangerous tool executed! ToolGuard was bypassed.")
                    print(f"   Response: {result.content[0].text}\n")
                except Exception as e:
                    # mcp.shared.exceptions.McpError is correctly expected here!
                    print(f"✅ [Client] ToolGuard safely blocked the dangerous tool!")
                    print(f"   Intercept Exception: {e}\n")
                    
    except Exception as e:
        print(f"❌ [Client] Failed to connect to server: {e}")

if __name__ == "__main__":
    asyncio.run(run_client())
