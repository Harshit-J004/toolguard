"""
toolguard.alerts.manager
~~~~~~~~~~~~~~~~~~~~~~~~
Dispatches background alerts via ThreadPoolExecutor to prevent blocking agent runtime.
"""

import json
import logging
import uuid
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .config import get_alert_config
from .slack import send_slack_alert
from .discord import send_discord_alert
from .datadog import send_datadog_metric
from .webhook import send_generic_webhook

logger = logging.getLogger("toolguard.alerts")

# Use a global thread pool so we don't block the caller
# Max workers = 5 since this is just IO-bound HTTP requests on error
_WORKER_POOL = ThreadPoolExecutor(max_workers=5, thread_name_prefix="tg_alert")

def dispatch_alert(tool_name: str, payload_attempted: dict, error: Exception) -> None:
    """Dispatches a hallucination alert to all configured sinks asynchronously.
    
    Args:
        tool_name: The name of the tool that was called.
        payload_attempted: The raw dict payload the LLM attempted to pass.
        error: The caught Pydantic ValidationError or standard Exception.
    """
    config = get_alert_config()
    
    # If no alerting is configured, exit immediately (O(1) fast path)
    if not any([
        config.slack_webhook_url, 
        config.discord_webhook_url, 
        config.datadog_api_key,
        config.generic_webhook_url
    ]):
        return
        
    # Serialize the error early so the caller can garbage collect it
    error_msg = str(error)
    tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__)) if error.__traceback__ else ""
    correlation_id = str(uuid.uuid4())
    timestamp_iso = datetime.now(timezone.utc).isoformat()
    
    try:
        # Pydantic ValidationError check for better display
        import pydantic
        is_schema_error = isinstance(error, pydantic.ValidationError)
    except ImportError:
        is_schema_error = False

    alert_data = {
        "tool_name": tool_name,
        "payload": payload_attempted,
        "error_msg": error_msg,
        "traceback": tb_str if not config.strip_traceback else "[STRIPPED — enable strip_traceback=False to view]",
        "is_schema_error": is_schema_error,
        "correlation_id": correlation_id,
        "timestamp": timestamp_iso
    }

    # Dispatch to background threads
    if config.slack_webhook_url:
        _WORKER_POOL.submit(_safe_call, send_slack_alert, config.slack_webhook_url, alert_data)
        
    if config.discord_webhook_url:
        _WORKER_POOL.submit(_safe_call, send_discord_alert, config.discord_webhook_url, alert_data)
        
    if config.datadog_api_key:
        _WORKER_POOL.submit(_safe_call, send_datadog_metric, config.datadog_api_key, config.datadog_site, alert_data)
        
    if config.generic_webhook_url:
        _WORKER_POOL.submit(_safe_call, send_generic_webhook, config.generic_webhook_url, alert_data)


def _safe_call(func, *args) -> None:
    """Wrapper to catch and log errors inside the background thread."""
    try:
        func(*args)
    except Exception as e:
        logger.error(f"ToolGuard background alert failed ({func.__name__}): {e}")
