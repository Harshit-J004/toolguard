"""
ToolGuard Webhook Providers.

Ship-ready providers for every major platform:
  - Discord  (solo devs, students, open-source)
  - Slack    (startups, tech companies)
  - Teams    (Fortune 500, banks, government)
  - Generic  (any HTTP endpoint / Zapier / n8n)
"""

from toolguard.core.webhooks.base import WebhookProvider
from toolguard.core.webhooks.discord import DiscordWebhookProvider
from toolguard.core.webhooks.slack import SlackWebhookProvider
from toolguard.core.webhooks.teams import TeamsWebhookProvider
from toolguard.core.webhooks.generic import GenericWebhookProvider

__all__ = [
    "WebhookProvider",
    "DiscordWebhookProvider",
    "SlackWebhookProvider",
    "TeamsWebhookProvider",
    "GenericWebhookProvider",
]
