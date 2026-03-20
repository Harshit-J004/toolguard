"""
toolguard.alerts.datadog
~~~~~~~~~~~~~~~~~~~~~~~~
Sends telemetry directly to Datadog's API (using v1 metrics / v2 logs).
"""

import json
import urllib.request
import urllib.error
from datetime import datetime

def send_datadog_metric(api_key: str, site: str, alert_data: dict) -> None:
    """Fires an increment metric and an event/log to Datadog."""
    
    metric_url = f"https://api.{site}/api/v1/series"
    log_url = f"https://http-intake.logs.{site}/api/v2/logs"
    
    headers = {
        "Content-Type": "application/json",
        "DD-API-KEY": api_key,
        "User-Agent": "ToolGuard"
    }
    
    tags = [
        f"tool:{alert_data['tool_name']}",
        f"error_type:{'schema_violation' if alert_data['is_schema_error'] else 'runtime_exception'}"
    ]
    
    # 1. Send Metric Increment
    now = int(datetime.now().timestamp())
    metric_data = {
        "series": [
            {
                "metric": "toolguard.agent.tool_failure",
                "type": "count",
                "points": [[now, 1]],
                "tags": tags
            }
        ]
    }
    
    req = urllib.request.Request(metric_url, data=json.dumps(metric_data).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=3) as _:
            pass
    except urllib.error.URLError:
        pass # Best effort

    # 2. Send Rich Log
    log_payload = {
        "ddsource": "toolguard",
        "service": "agent_tools",
        "hostname": "toolguard-agent",
        "tags": ",".join(tags),
        "message": f"LLM Tool Failure in {alert_data['tool_name']}: {alert_data['error_msg']}",
        "payload": alert_data["payload"],
        "traceback": alert_data["traceback"],
        "tool_name": alert_data["tool_name"],
        "uuid": alert_data["correlation_id"]
    }
    
    req_log = urllib.request.Request(log_url, data=json.dumps([log_payload]).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req_log, timeout=3) as _:
            pass
    except urllib.error.URLError:
        pass
