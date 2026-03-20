"""
toolguard.alerts.config
~~~~~~~~~~~~~~~~~~~~~~~
Global configuration state for production alerting.
"""

from __future__ import annotations
from dataclasses import dataclass

@dataclass
class AlertConfig:
    """Configuration for production safety alerts."""
    slack_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    datadog_api_key: str | None = None
    datadog_site: str = "datadoghq.com"
    generic_webhook_url: str | None = None

# Global configuration instance
_GLOBAL_ALERT_CONFIG = AlertConfig()

def configure_alerts(
    slack_webhook_url: str | None = None,
    discord_webhook_url: str | None = None,
    datadog_api_key: str | None = None,
    datadog_site: str = "datadoghq.com",
    generic_webhook_url: str | None = None,
) -> None:
    """Configure the global alerting sinks for ToolGuard in production.
    
    If an LLM hallucinates an invalid JSON payload that fails Pydantic validation 
    inside a GuardedTool, an alert will be dispatched asynchronously to the 
    configured sinks.
    """
    global _GLOBAL_ALERT_CONFIG
    _GLOBAL_ALERT_CONFIG = AlertConfig(
        slack_webhook_url=slack_webhook_url,
        discord_webhook_url=discord_webhook_url,
        datadog_api_key=datadog_api_key,
        datadog_site=datadog_site,
        generic_webhook_url=generic_webhook_url,
    )

def get_alert_config() -> AlertConfig:
    """Retrieve the current global alerting configuration."""
    return _GLOBAL_ALERT_CONFIG
