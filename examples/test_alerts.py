"""
Tests that the global alerting system properly dispatches background requests
when a tool fails validation.
"""
import time
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

import toolguard
from toolguard import create_tool

# --- Mock Webhook Server ---
last_alert = None

class MockWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global last_alert
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        last_alert = json.loads(post_data.decode('utf-8'))
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
        
    def log_message(self, format, *args):
        pass # Suppress server logs

server = HTTPServer(('localhost', 9091), MockWebhookHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()

# --- Test ---

# Enable Phase 4 Alerts
toolguard.configure_alerts(generic_webhook_url="http://localhost:9091/alert")

@create_tool(schema="auto")
def compute_salary(hours: int, rate: float) -> dict:
    return {"salary": hours * rate}

if __name__ == "__main__":
    print("🚀 Triggering a hallucinated tool execution (passing string instead of int)...")
    
    try:
        # LLM hallucinates and passes a string 'forty'
        compute_salary(hours="forty", rate=50.0)
    except Exception as e:
        print(f"✅ Tool correctly crashed with: {type(e).__name__} - {e}")
        
    # Wait for background thread dispatcher to finish
    time.sleep(2.5)
    
    if last_alert:
        print("\n✅ Webhook successfully caught the production alert!")
        print("Alert Payload received by server:")
        print(json.dumps(last_alert, indent=2))
        
        # Verify it sent the bad payload
        assert last_alert["payload"]["hours"] == "forty"
        assert last_alert["tool_name"] == "compute_salary"
        assert last_alert["is_schema_error"] is True
    else:
        print("\n❌ Webhook server did NOT receive an alert.")
        exit(1)
