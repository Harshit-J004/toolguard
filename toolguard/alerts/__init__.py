"""
toolguard.alerts
~~~~~~~~~~~~~~~~

Production alerting module to capture and dispatch LLM hallucination errors 
(Pydantic ValidationErrors) to external observability sinks (Slack, Discord, Datadog) 
in the background without blocking the agent runtime.
"""

from .config import AlertConfig, configure_alerts, get_alert_config
from .manager import dispatch_alert

__all__ = ["AlertConfig", "configure_alerts", "get_alert_config", "dispatch_alert"]
