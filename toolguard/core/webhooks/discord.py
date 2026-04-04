import httpx
from typing import Any, Dict
from toolguard.core.webhooks.base import WebhookProvider

class DiscordWebhookProvider(WebhookProvider):
    """
    Sends interactive approval notifications to Discord using a simple webhook URL.
    Ideal for solo developers, researchers, and small teams.
    """
    
    def __init__(self, webhook_url: str, approval_base_url: str = "http://localhost:8000"):
        self.webhook_url = webhook_url
        self.approval_base_url = approval_base_url.rstrip("/")
        
    def send_approval_request(self, tool_name: str, arguments: Dict[str, Any], grant_id: str, timeout: int) -> bool:
        approve_url = f"{self.approval_base_url}/toolguard/approve?grant_id={grant_id}"
        deny_url = f"{self.approval_base_url}/toolguard/deny?grant_id={grant_id}"
        
        args_str = "```json\\n" + str(arguments) + "\\n```"
        
        payload = {
            "username": "ToolGuard Enforcer",
            "avatar_url": "https://img.icons8.com/color/96/000000/shield.png",
            "embeds": [{
                "title": f"🛡️ Approval Required: {tool_name}",
                "description": f"An agent is attempting to execute a restricted tool. Execution has been paused.\\n\\n**Arguments:**\\n{args_str}",
                "color": 16753920, # Orange
                "fields": [
                    {"name": "Timeout", "value": f"{timeout} seconds", "inline": True},
                    {"name": "Grant ID", "value": f"`{grant_id[:8]}...`", "inline": True}
                ]
            }],
            "components": [{
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "label": "Approve",
                        "style": 3,
                        "url": approve_url
                    },
                    {
                        "type": 2,
                        "label": "Deny",
                        "style": 4,
                        "url": deny_url
                    }
                ]
            }]
        }
        
        try:
            # Discord components (buttons) on webhooks require a bot token or a complex setup if using pure link buttons.
            # For pure webhooks without a registered App, we just use standard markdown links.
            fallback_payload = {
                "username": "ToolGuard Enforcer",
                "embeds": [{
                    "title": f"🛡️ Approval Required: `{tool_name}`",
                    "description": f"The agent has been paused.\\n\\n**Arguments:**\\n{args_str}\\n\\n✅ **[APPROVE EXECUTION]({approve_url})**  |  ❌ **[DENY EXECUTION]({deny_url})**",
                    "color": 16753920
                }]
            }
            
            response = httpx.post(self.webhook_url, json=fallback_payload, timeout=10.0)
            return response.status_code in (200, 204)
        except Exception:
            return False
