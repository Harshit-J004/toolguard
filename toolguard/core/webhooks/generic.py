"""
Generic HTTP Webhook Provider.

Posts a JSON payload to any arbitrary URL. Works with custom
internal services, Zapier, Make.com, n8n, or any HTTP endpoint.
"""

import httpx
from typing import Any, Dict
from toolguard.core.webhooks.base import WebhookProvider


class GenericWebhookProvider(WebhookProvider):
    """
    Sends a standardized JSON payload to any HTTP endpoint.
    
    Usage:
        provider = GenericWebhookProvider(
            webhook_url="https://your-api.com/toolguard-alerts",
            approval_base_url="https://your-server.com"
        )
    """
    
    def __init__(self, webhook_url: str, approval_base_url: str = "http://localhost:8000",
                 headers: Dict[str, str] | None = None):
        self.webhook_url = webhook_url
        self.approval_base_url = approval_base_url.rstrip("/")
        self.headers = headers or {"Content-Type": "application/json"}

    def send_approval_request(self, tool_name: str, arguments: Dict[str, Any], 
                              grant_id: str, timeout: int) -> bool:
        payload = {
            "event": "toolguard.approval_required",
            "tool_name": tool_name,
            "arguments": arguments,
            "grant_id": grant_id,
            "timeout_seconds": timeout,
            "approve_url": f"{self.approval_base_url}/toolguard/approve?grant_id={grant_id}",
            "deny_url": f"{self.approval_base_url}/toolguard/deny?grant_id={grant_id}",
        }
        
        try:
            response = httpx.post(self.webhook_url, json=payload, 
                                  headers=self.headers, timeout=10.0)
            return 200 <= response.status_code < 300
        except Exception:
            return False
