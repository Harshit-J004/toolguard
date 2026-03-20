"""
toolguard.alerts.webhook
~~~~~~~~~~~~~~~~~~~~~~~~
Sends the raw alert payload to any generic JSON ingest endpoint.
"""

import json
import urllib.request
import urllib.error

def send_generic_webhook(webhook_url: str, alert_data: dict) -> None:
    """Fires a raw POST request with the JSON payload to a generic webhook."""
    
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(alert_data).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "ToolGuard"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            response.read()
    except urllib.error.URLError:
        pass
