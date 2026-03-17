"""
Demo Failing Chain — The "Aha Moment"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This example shows EXACTLY why ToolGuard exists.

Run this WITHOUT ToolGuard → silent failure, wrong data, no error.
Run this WITH ToolGuard → instant detection, root cause, fix suggestion.

This is the demo you show on the README, the HN post, and the first
time someone installs ToolGuard.

Run: python run_demo.py
"""

from toolguard import create_tool


# ──────────────────────────────────────────────────────────
#  Tool 1: Fetch stock price (simulates an API that sometimes returns null)
# ──────────────────────────────────────────────────────────

@create_tool(schema="auto")
def fetch_stock_price(ticker: str, exchange: str = "NYSE") -> dict:
    """Fetch the current price for a stock ticker."""
    # Simulated API — some tickers return null price (the silent killer)
    prices = {
        "AAPL": 189.50,
        "GOOGL": 141.80,
        "MSFT": 378.91,
        "TSLA": None,       # ← BUG: API returns null for TSLA
        "META": 505.75,
    }

    return {
        "ticker": ticker,
        "price": prices.get(ticker),  # ← Returns None for unknown tickers too
        "exchange": exchange,
        "currency": "USD",
    }


# ──────────────────────────────────────────────────────────
#  Tool 2: Calculate position value (crashes on null price)
# ──────────────────────────────────────────────────────────

@create_tool(schema="auto")
def calculate_position(ticker: str, price: float = 0.0, exchange: str = "", currency: str = "USD") -> dict:
    """Calculate portfolio position value from price data."""
    shares = 100  # assume 100 shares

    # ← This will crash if price is None (null propagation!)
    position_value = price * shares
    daily_change = price * 0.02  # simulated 2% daily change

    return {
        "ticker": ticker,
        "shares": shares,
        "position_value": position_value,
        "daily_pnl": daily_change * shares,
        "currency": currency,
    }


# ──────────────────────────────────────────────────────────
#  Tool 3: Generate risk alert (wrong type cascades)
# ──────────────────────────────────────────────────────────

@create_tool(schema="auto")
def generate_risk_alert(
    ticker: str,
    shares: int = 0,
    position_value: float = 0.0,
    daily_pnl: float = 0.0,
    currency: str = "USD",
) -> dict:
    """Generate a risk alert based on position data."""
    # This tool expects float but might get None from cascade
    risk_level = "HIGH" if abs(daily_pnl) > 500 else "MEDIUM" if abs(daily_pnl) > 100 else "LOW"

    return {
        "alert": risk_level != "LOW",
        "risk_level": risk_level,
        "message": f"{ticker}: ${position_value:,.2f} position, ${daily_pnl:,.2f} daily P&L",
        "action": "REVIEW" if risk_level == "HIGH" else "MONITOR",
    }
