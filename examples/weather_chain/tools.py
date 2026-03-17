"""
Weather Chain Example
~~~~~~~~~~~~~~~~~~~~~

A complete working example showing ToolGuard's core features:
  1. Three tools wrapped with @create_tool
  2. Chain testing with edge cases
  3. Beautiful console output

Run with: python run_tests.py
"""

from pydantic import BaseModel, Field
from typing import Optional

from toolguard import create_tool


# ──────────────────────────────────────────────────────────
#  Output Models (optional, for strict output validation)
# ──────────────────────────────────────────────────────────

class WeatherOutput(BaseModel):
    temperature: float = Field(..., ge=-100, le=150)
    units: str
    location: str
    conditions: Optional[str] = None


class ForecastOutput(BaseModel):
    forecast: str
    severity: str
    temp_f: Optional[float] = None


class AlertOutput(BaseModel):
    sent: bool
    message: str
    channel: str = "email"


# ──────────────────────────────────────────────────────────
#  Tools
# ──────────────────────────────────────────────────────────

@create_tool(schema="auto", output_model=WeatherOutput)
def get_weather(location: str, units: str = "metric") -> dict:
    """Fetch current weather for a location."""
    # Simulated API response
    temps = {
        "NYC": 22.5, "London": 15.0, "Tokyo": 28.0,
        "Sydney": 19.5, "Mumbai": 35.0,
    }
    conditions_map = {
        "NYC": "partly cloudy", "London": "rainy",
        "Tokyo": "sunny", "Sydney": "windy", "Mumbai": "humid",
    }

    temp = temps.get(location, 20.0)

    return {
        "temperature": temp,
        "units": units,
        "location": location,
        "conditions": conditions_map.get(location, "clear"),
    }


@create_tool(schema="auto", output_model=ForecastOutput)
def process_forecast(temperature: float, units: str = "metric", location: str = "", conditions: str = "clear") -> dict:
    """Process weather data into a human-readable forecast."""
    # Convert to Fahrenheit if needed
    temp_f = temperature * 9 / 5 + 32 if units == "metric" else temperature

    if temp_f > 95:
        severity = "high"
        forecast = f"🔥 Extreme heat alert in {location}! {temp_f:.0f}°F with {conditions} skies."
    elif temp_f > 80:
        severity = "medium"
        forecast = f"☀️ Warm day in {location}. {temp_f:.0f}°F, {conditions}."
    elif temp_f > 50:
        severity = "low"
        forecast = f"🌤️ Pleasant weather in {location}. {temp_f:.0f}°F, {conditions}."
    else:
        severity = "medium"
        forecast = f"❄️ Cold weather in {location}. {temp_f:.0f}°F, {conditions}."

    return {
        "forecast": forecast,
        "severity": severity,
        "temp_f": temp_f,
    }


@create_tool(schema="auto", output_model=AlertOutput)
def send_alert(forecast: str, severity: str = "low", temp_f: float = 0.0) -> dict:
    """Send a weather alert if severity warrants it."""
    should_send = severity in ("medium", "high")

    if should_send:
        message = f"⚠️ WEATHER ALERT: {forecast}"
    else:
        message = f"ℹ️ Weather update: {forecast}"

    return {
        "sent": should_send,
        "message": message,
        "channel": "email" if severity == "medium" else "sms" if severity == "high" else "log",
    }
