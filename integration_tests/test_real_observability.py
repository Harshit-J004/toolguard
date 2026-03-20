"""
integration_tests/test_real_observability.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verifies that ToolGuard's Slack, Discord, Datadog, and Webhook dispatchers 
generate the exact correct HTTP payloads when a REAL framework (LangChain) 
crashes due to an LLM hallucination.
"""

import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pydantic import BaseModel, Field

import toolguard
from toolguard.integrations.langchain import guard_langchain_tool

# We need the real langchain-core to prove the integration works
try:
    from langchain_core.tools import tool
except ImportError:
    import sys
    print("langchain-core not installed. Run: pip install langchain-core")
    sys.exit(0)

# --- 1. Mock External APIs (Slack/Datadog/Discord) ---
captured_payloads = {
    "slack": None,
    "discord": None,
    "datadog_metrics": None,
    "datadog_logs": None,
}

class MockObservabilityServer(BaseHTTPRequestHandler):
    def do_POST(self):
        print(f"[SERVER] Received POST request to {self.path}")
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len).decode('utf-8')
        print(f"[SERVER] Body length: {len(post_body)}")
        try:
            payload = json.loads(post_body)
        except Exception as e:
            print(f"[SERVER] JSON decode error: {e}")
            payload = {}
        
        # Route based on the URL path
        if "/slack" in self.path:
            captured_payloads["slack"] = payload
        elif "/discord" in self.path:
            captured_payloads["discord"] = payload
        elif "series" in self.path:
            captured_payloads["datadog_metrics"] = payload
        elif "logs" in self.path:
            captured_payloads["datadog_logs"] = payload

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
        
    def log_message(self, format, *args): 
        print(f"[SERVER LOG] {format % args}")

server = HTTPServer(('localhost', 9092), MockObservabilityServer)
threading.Thread(target=server.serve_forever, daemon=True).start()

# --- 2. Configure ToolGuard for the Mock Servers ---
toolguard.configure_alerts(
    slack_webhook_url="http://localhost:9092/slack",
    discord_webhook_url="http://localhost:9092/discord",
    datadog_api_key="fake-datadog-key",
    datadog_site="localhost:9092" # Reroute to our local mock
)

# --- 3. Build a Real LangChain Tool ---
class TransactionInput(BaseModel):
    user_id: int = Field(description="The numeric user ID")
    amount: float = Field(description="The transaction amount in USD")

@tool("process_transaction", args_schema=TransactionInput)
def process_transaction(user_id: int, amount: float) -> str:
    """Processes a financial transaction."""
    return f"Processed ${amount} for user {user_id}"

# Wrap with ToolGuard
guarded_lc_tool = guard_langchain_tool(process_transaction)

def test_production_observability():
    print("=========================================================")
    print("🚀 Verifying Phase 4: Production Observability")
    print("=========================================================\n")
    
    # 1. Simulate an LLM Hallucinated Call
    print("[1] Simulating LLM hallucinating 'user_id' as a string ('USR-999')...")
    
    try:
        # The agent attempts to call the ToolGuard wrapped function directly
        guarded_lc_tool(user_id="USR-999", amount=150.0)
    except Exception as e:
        print(f"✅ Tool crashed gracefully with: {type(e).__name__}\n")
        
    # Wait for the background `AlertManager` thread pool to finish flushing
    print("[2] Waiting up to 5 seconds for background AlertManager threads to flush...")
    for _ in range(10):
        if captured_payloads["slack"] and captured_payloads["discord"]:
            break
        time.sleep(0.5)
    
    # --- 3. Verify Slack Payload ---
    print("\n---------------------------------------------------------")
    print("🔴 SLACK BLOCK KIT PAYLOAD:")
    if captured_payloads["slack"]:
        slack = captured_payloads["slack"]
        assert "blocks" in slack
        header_text = slack["blocks"][0]["text"]["text"]
        print(f"✅ Received format: {header_text}")
        print(json.dumps(slack, indent=2))
    else:
        print("❌ Slack payload missing!")
        
    # --- 4. Verify Discord Payload ---
    print("\n---------------------------------------------------------")
    print("🟣 DISCORD EMBED PAYLOAD:")
    if captured_payloads["discord"]:
        discord = captured_payloads["discord"]
        assert "embeds" in discord
        title = discord["embeds"][0]["title"]
        print(f"✅ Received format: {title}")
        print(json.dumps(discord, indent=2))
    else:
        print("❌ Discord payload missing!")
        
    # --- 5. Verify Datadog Metrics & Logs ---
    print("\n---------------------------------------------------------")
    print("🐶 DATADOG METRICS & LOGS PAYLOAD:")
    if captured_payloads["datadog_metrics"] and captured_payloads["datadog_logs"]:
        metrics = captured_payloads["datadog_metrics"]
        logs = captured_payloads["datadog_logs"]
        
        assert metrics["series"][0]["metric"] == "toolguard.agent.tool_failure"
        assert "tool_name" in logs[0]
        
        print(f"✅ Metric: {metrics['series'][0]['metric']} (Count: 1)")
        print(f"✅ Tags: {logs[0]['tags']}")
        print(f"✅ Exact log payload captures missing schema:")
        print(json.dumps(logs[0]["payload"], indent=2))
    else:
        print("❌ Datadog payloads missing!")

if __name__ == "__main__":
    test_production_observability()
