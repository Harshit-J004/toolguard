"""
toolguard.alerts.discord
~~~~~~~~~~~~~~~~~~~~~~~~
Formats and sends rich embed messages to Discord webhooks.
"""

import json
import urllib.request
import urllib.error

def send_discord_alert(webhook_url: str, alert_data: dict) -> None:
    """Fires a formatted Embed alert to Discord."""
    
    title = f"🚨 LLM Hallucinated Payload in `{alert_data['tool_name']}`" if alert_data["is_schema_error"] else f"🚨 Tool Crash in `{alert_data['tool_name']}`"
    
    payload_str = json.dumps(alert_data["payload"], indent=2)
    # Discord limit is 4096 for descriptions
    if len(payload_str) > 2000:
        payload_str = payload_str[:1997] + "..."
        
    embed = {
        "title": title,
        "color": 16711680 if alert_data["is_schema_error"] else 16753920, # Red or Orange
        "description": f"**Error details:**\n```\n{alert_data['error_msg']}\n```\n**Traceback:**\n```python\n{alert_data['traceback']}\n```\n**Attempted JSON Payload:**\n```json\n{payload_str}\n```",
        "timestamp": alert_data["timestamp"],
        "footer": {
            "text": f"UUID: {alert_data['correlation_id']} | ToolGuard"
        }
    }
    
    req_data = {"embeds": [embed]}
    
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(req_data).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "ToolGuard"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            response.read()
    except urllib.error.URLError:
        pass
