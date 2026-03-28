"""
toolguard.alerts.slack
~~~~~~~~~~~~~~~~~~~~~~
Formats and sends rich block-kit messages to Slack webhooks.
"""

import json
import urllib.request
import urllib.error

def send_slack_alert(webhook_url: str, alert_data: dict) -> None:
    """Fires a formatted Block Kit alert to Slack."""
    
    title = f"🚨 LLM Hallucinated Payload in `{alert_data['tool_name']}`" if alert_data["is_schema_error"] else f"🚨 Tool Crash in `{alert_data['tool_name']}`"
    
    payload_str = json.dumps(alert_data["payload"], indent=2)
    # Truncate if massive
    if len(payload_str) > 2000:
        payload_str = payload_str[:1997] + "..."
        
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title,
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Error details:*\n```\n{alert_data['error_msg']}\n```"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Attempted JSON Payload:*\n```json\n{payload_str}\n```"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Traceback:*\n```python\n{alert_data['traceback']}\n```"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"UUID: `{alert_data['correlation_id']}`  |  Time: {alert_data['timestamp']} UTC"
                }
            ]
        }
    ]
    
    req_data = {"blocks": blocks}
    
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(req_data).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "ToolGuard"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            response.read()
    except urllib.error.URLError:
        pass  # Eaten by the _safe_call wrapper wrapper in manager.py
