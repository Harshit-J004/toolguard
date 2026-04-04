"""
Slack Webhook Provider — Block Kit interactive messages.

Sends rich approval requests to Slack channels using the
Incoming Webhooks API with interactive approve/deny buttons.
"""

import httpx
from typing import Any, Dict
from toolguard.core.webhooks.base import WebhookProvider


class SlackWebhookProvider(WebhookProvider):
    """
    Sends approval notifications to Slack using Block Kit formatting.
    
    Usage:
        provider = SlackWebhookProvider(
            webhook_url="https://hooks.slack.com/services/T00/B00/XXX",
            approval_base_url="https://your-server.com"
        )
    """
    
    def __init__(self, webhook_url: str, approval_base_url: str = "http://localhost:8000"):
        self.webhook_url = webhook_url
        self.approval_base_url = approval_base_url.rstrip("/")

    def send_approval_request(self, tool_name: str, arguments: Dict[str, Any], 
                              grant_id: str, timeout: int) -> bool:
        approve_url = f"{self.approval_base_url}/toolguard/approve?grant_id={grant_id}"
        deny_url = f"{self.approval_base_url}/toolguard/deny?grant_id={grant_id}"
        
        args_preview = str(arguments)[:200]
        
        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🛡️ ToolGuard — Approval Required",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Tool:*\n`{tool_name}`"},
                        {"type": "mrkdwn", "text": f"*Risk Tier:*\nRestricted / Critical"},
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Arguments:*\n```{args_preview}```"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Grant ID: `{grant_id[:12]}...` | Timeout: {timeout}s"
                        }
                    ]
                },
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Approve Execution", "emoji": True},
                            "style": "primary",
                            "url": approve_url,
                            "action_id": "toolguard_approve"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Deny Execution", "emoji": True},
                            "style": "danger",
                            "url": deny_url,
                            "action_id": "toolguard_deny"
                        }
                    ]
                }
            ]
        }
        
        try:
            response = httpx.post(self.webhook_url, json=payload, timeout=10.0)
            return response.status_code == 200
        except Exception:
            return False
