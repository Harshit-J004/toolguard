"""
pytest configuration and shared fixtures for ToolGuard test suite.
"""
import pytest

from toolguard.core.validator import create_tool


@pytest.fixture
def happy_tool():
    """A perfectly working tool that always returns valid output."""
    @create_tool(schema="auto")
    def fetch_user(user_id: int, role: str = "member") -> dict:
        return {"id": user_id, "name": "Alice", "role": role, "active": True}
    return fetch_user


@pytest.fixture
def process_tool():
    """A second tool in a chain that transforms user data."""
    @create_tool(schema="auto")
    def format_greeting(id: int, name: str, role: str = "member", active: bool = True) -> dict:
        return {"greeting": f"Hello {name} (#{id})", "is_active": active}
    return format_greeting


@pytest.fixture
def buggy_null_tool():
    """A tool that sometimes returns None — demonstrates null propagation."""
    @create_tool(schema="auto")
    def get_score(user_id: int) -> dict:
        if user_id == 0:
            return None  # Bug: returns None instead of dict
        return {"score": 95, "user_id": user_id}
    return get_score
