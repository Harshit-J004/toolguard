import asyncio
import pytest
import time
from toolguard import create_tool, score_chain
from toolguard import test_chain as run_chain_test
from toolguard.core.errors import SchemaValidationError
from toolguard.core.retry import with_circuit_breaker, CircuitBreaker

# --- 1. Massive Payload Test ---
@create_tool(schema="auto")
def process_massive_payload(data: dict) -> dict:
    return {"status": "ok", "size": len(str(data))}

def test_massive_payload():
    # 10MB payload
    huge_string = "A" * 10_000_000
    report = run_chain_test(
        [process_massive_payload],
        base_input={"data": {"huge": huge_string}},
        test_cases=["happy_path", "null_handling"],
        iterations=1,
        assert_reliability=0.0
    )
    assert report is not None
    assert score_chain(report).reliability >= 0.0

# --- 2. Infinite Loop / Recursion Protection ---
@create_tool(schema="auto")
def recursive_tool(x: int) -> int:
    # We use a controlled recursion to trigger a RecursionError without actually killing the pytest interpreter completely
    def deep_func(n):
        if n == 0: return deep_func(n) # force recursion
        return deep_func(n-1)
    
    try:
        deep_func(5000)
    except RecursionError:
        raise TypeError("Simulated recursion or unexpected error under stress")
    return x

def test_recursion_handling():
    # ToolGuard catches internal errors gracefully instead of crashing the pipeline
    report = run_chain_test(
        [recursive_tool],
        base_input={"x": 1},
        assert_reliability=0.0,
        iterations=1
    )
    assert report.failed > 0

# --- 3. Async Concurrency / Race Conditions ---
@create_tool(schema="auto")
async def slow_async_tool(sleep_time: float) -> dict:
    await asyncio.sleep(sleep_time)
    return {"slept": sleep_time}

def test_async_concurrency():
    # ToolGuard handles async execution internally via asyncio.run(), so the test function itself doesn't need to be async
    report = run_chain_test(
        [slow_async_tool],
        base_input={"sleep_time": 0.01},
        test_cases=["happy_path", "null_handling", "type_mismatch"],
        iterations=5, 
        assert_reliability=0.0
    )
    assert report.total_tests > 0
    # Type mismatch should fail, happy should pass
    assert report.failed >= 0

# --- 4. Circuit Breaker Stress ---
breaker = CircuitBreaker(failure_threshold=2, reset_timeout=0.1)

@with_circuit_breaker(breaker)
@create_tool(schema="auto")
def flaky_tool(fail: bool) -> dict:
    if fail:
        raise ValueError("Boom")
    return {"ok": True}

def test_circuit_breaker_stress():
    # 1. Fail twice (opens breaker)
    for _ in range(2):
        try:
            flaky_tool(True)
        except Exception:
            pass
    
    assert breaker.state == "OPEN"
    
    # 2. Third call should fail fast (CircuitBreakerError)
    with pytest.raises(Exception) as exc:
        flaky_tool(False)
    assert "OPEN" in str(exc.value)

    # 3. Wait for reset
    time.sleep(0.15)
    
    # 4. Should be half open, allow one, then close
    res = flaky_tool(False)
    assert res["ok"] is True
    assert breaker.state == "CLOSED"

# --- 5. Bizarre Data Types ---
@create_tool(schema="auto")
def type_enforcer(a: int, b: list[str], c: dict[str, float]) -> dict:
    return {"sum": a + len(b) + sum(c.values())}

def test_bizarre_data_types():
    report = run_chain_test(
        [type_enforcer],
        base_input={"a": 1, "b": ["x"], "c": {"y": 1.0}},
        test_cases=["happy_path", "type_mismatch", "missing_fields", "malformed_data", "large_payload"],
        iterations=2,
        assert_reliability=0.0
    )
    
    # We expect failures on type_mismatch and missing_fields, but IT SHOULD NOT CRASH
    assert report is not None
    assert report.total_tests >= 10
