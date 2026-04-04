"""
Microsoft Teams Webhook Provider — Adaptive Card messages.

Sends rich approval requests to Teams channels using the
Incoming Webhook Connector with Adaptive Card formatting.
"""

import httpx
from typing import Any, Dict
from toolguard.core.webhooks.base import WebhookProvider


class TeamsWebhookProvider(WebhookProvider):
    """
    Sends approval notifications to Microsoft Teams using Adaptive Cards.
    
    Setup:
        1. In your Teams channel, click ••• → Connectors → Incoming Webhook
        2. Copy the webhook URL
    
    Usage:
        provider = TeamsWebhookProvider(
            webhook_url="https://outlook.office.com/webhook/...",
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
        
        args_preview = str(arguments)[:300]
        
        # Teams Adaptive Card payload
        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "ColumnSet",
                            "columns": [
                                {
                                    "type": "Column",
                                    "width": "auto",
                                    "items": [{
                                        "type": "Image",
                                        "url": "https://img.icons8.com/color/48/000000/shield.png",
                                        "size": "Small"
                                    }]
                                },
                                {
                                    "type": "Column",
                                    "width": "stretch",
                                    "items": [
                                        {
                                            "type": "TextBlock",
                                            "text": "ToolGuard — Approval Required",
                                            "weight": "Bolder",
                                            "size": "Medium",
                                            "color": "Warning"
                                        },
                                        {
                                            "type": "TextBlock",
                                            "text": "An AI agent has been paused awaiting human authorization.",
                                            "spacing": "None",
                                            "isSubtle": True,
                                            "wrap": True
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Tool", "value": f"`{tool_name}`"},
                                {"title": "Grant ID", "value": f"`{grant_id[:12]}...`"},
                                {"title": "Timeout", "value": f"{timeout} seconds"},
                            ]
                        },
                        {
                            "type": "TextBlock",
                            "text": "Arguments",
                            "weight": "Bolder",
                            "spacing": "Medium"
                        },
                        {
                            "type": "TextBlock",
                            "text": f"```{args_preview}```",
                            "wrap": True,
                            "fontType": "Monospace",
                            "size": "Small"
                        }
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "✅ Approve Execution",
                            "url": approve_url,
                            "style": "positive"
                        },
                        {
                            "type": "Action.OpenUrl",
                            "title": "❌ Deny Execution",
                            "url": deny_url,
                            "style": "destructive"
                        }
                    ]
                }
            }]
        }
        
        try:
            response = httpx.post(self.webhook_url, json=payload, timeout=10.0)
            return response.status_code == 200
        except Exception:
            return False
