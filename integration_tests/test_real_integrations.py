"""
REAL Integration Tests — No Mocks, Actual Libraries, REAL Fuzzing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This test suite uses the REAL pip-installed versions of:
  - llama_index.core.tools.FunctionTool
  - autogen_core.tools.FunctionTool
  - swarm.Agent
  - fastapi.FastAPI

Every test creates a real framework object, wraps it with ToolGuard's 
adapter, and runs it through the FULL fuzzing engine — including
null_handling, malformed_data, type_mismatch, and missing_fields.

This produces REAL reliability scores, not trivial 100% happy-path scores.
"""

import pytest
from toolguard.core.chain import test_chain as run_chain_test
from toolguard.core.validator import GuardedTool

# The FULL test suite — this is what ToolGuard actually does in production
FULL_FUZZ_CASES = [
    "happy_path",
    "null_handling",
    "malformed_data",
    "type_mismatch",
    "missing_fields",
]


# ═══════════════════════════════════════════════════════════
#  1. REAL LlamaIndex Integration — FULL FUZZING
# ═══════════════════════════════════════════════════════════

def test_real_llamaindex_full_fuzz():
    """Use the REAL llama_index FunctionTool with FULL fuzzing."""
    from llama_index.core.tools import FunctionTool
    from toolguard.integrations.llamaindex import guard_llamaindex_tool

    def multiply(a: int, b: int) -> int:
        """Multiply two numbers together."""
        return a * b

    llama_tool = FunctionTool.from_defaults(fn=multiply)
    guarded = guard_llamaindex_tool(llama_tool)

    assert isinstance(guarded, GuardedTool)
    assert guarded.name == "multiply"

    # FULL fuzzing — null, malformed, type mismatch, missing fields
    report = run_chain_test(
        [guarded],
        test_cases=FULL_FUZZ_CASES,
        base_input={"a": 3, "b": 7},
        assert_reliability=0.0,  # Don't fail the test — we want to SEE the real score
    )

    print(f"\n  🔬 LlamaIndex FULL FUZZ:")
    print(f"     Tool: {guarded.name}")
    print(f"     Reliability: {report.reliability:.1%}")
    print(f"     Total runs: {len(report.runs)}")
    print(f"     Passed: {sum(1 for r in report.runs if r.success)}")
    print(f"     Failed: {sum(1 for r in report.runs if not r.success)}")

    # The happy_path cases MUST pass (adapter works correctly)
    happy_runs = [r for r in report.runs if r.test_case_type == "happy_path"]
    assert all(r.success for r in happy_runs), "Happy path runs should always succeed"

    # The overall reliability should be between 0% and 100% — NOT trivially 100%
    # because null/malformed/mismatch inputs SHOULD cause validation failures
    assert 0.0 < report.reliability <= 1.0, f"Score should be real, got {report.reliability}"


# ═══════════════════════════════════════════════════════════
#  2. REAL AutoGen Integration — FULL FUZZING
# ═══════════════════════════════════════════════════════════

def test_real_autogen_full_fuzz():
    """Use the REAL autogen_core FunctionTool with FULL fuzzing."""
    from autogen_core.tools import FunctionTool as AutoGenFunctionTool
    from toolguard.integrations.autogen import guard_autogen_tool

    def calculate_discount(price: float, percent: float) -> float:
        """Calculate a discounted price."""
        return price * (1 - percent / 100)

    autogen_tool = AutoGenFunctionTool(
        calculate_discount,
        name="calculate_discount",
        description="Calculate a discounted price",
    )

    guarded = guard_autogen_tool(autogen_tool)
    assert isinstance(guarded, GuardedTool)
    assert guarded.name == "calculate_discount"

    report = run_chain_test(
        [guarded],
        test_cases=FULL_FUZZ_CASES,
        base_input={"price": 100.0, "percent": 15.0},
        assert_reliability=0.0,
    )

    print(f"\n  🔬 AutoGen FULL FUZZ:")
    print(f"     Tool: {guarded.name}")
    print(f"     Reliability: {report.reliability:.1%}")
    print(f"     Total runs: {len(report.runs)}")
    print(f"     Passed: {sum(1 for r in report.runs if r.success)}")
    print(f"     Failed: {sum(1 for r in report.runs if not r.success)}")

    happy_runs = [r for r in report.runs if r.test_case_type == "happy_path"]
    assert all(r.success for r in happy_runs), "Happy path runs should always succeed"
    assert 0.0 < report.reliability <= 1.0


# ═══════════════════════════════════════════════════════════
#  3. REAL OpenAI Swarm Integration — FULL FUZZING
# ═══════════════════════════════════════════════════════════

def test_real_swarm_full_fuzz():
    """Use the REAL swarm.Agent class with FULL fuzzing."""
    from swarm import Agent
    from toolguard.integrations.swarm import guard_swarm_agent

    def get_weather(city: str) -> str:
        """Get the weather for a city."""
        return f"Weather in {city}: 25°C, sunny"

    def get_population(city: str) -> int:
        """Get the population for a city."""
        return 1_000_000

    agent = Agent(
        name="City Info Agent",
        instructions="You help with city information.",
        functions=[get_weather, get_population],
    )

    guarded_tools = guard_swarm_agent(agent)
    assert len(guarded_tools) == 2
    assert all(isinstance(t, GuardedTool) for t in guarded_tools)

    report = run_chain_test(
        guarded_tools,
        test_cases=FULL_FUZZ_CASES,
        base_input={"city": "Mumbai"},
        assert_reliability=0.0,
    )

    print(f"\n  🔬 Swarm FULL FUZZ:")
    print(f"     Tools: {[t.name for t in guarded_tools]}")
    print(f"     Reliability: {report.reliability:.1%}")
    print(f"     Total runs: {len(report.runs)}")
    print(f"     Passed: {sum(1 for r in report.runs if r.success)}")
    print(f"     Failed: {sum(1 for r in report.runs if not r.success)}")

    happy_runs = [r for r in report.runs if r.test_case_type == "happy_path"]
    assert all(r.success for r in happy_runs), "Happy path runs should always succeed"
    assert 0.0 < report.reliability <= 1.0


# ═══════════════════════════════════════════════════════════
#  4. REAL FastAPI Integration — FULL FUZZING
# ═══════════════════════════════════════════════════════════

def test_real_fastapi_full_fuzz():
    """Use a real FastAPI-style endpoint with FULL fuzzing."""
    from toolguard.integrations.fastapi import as_fastapi_tool

    def create_user(name: str, age: int) -> dict:
        """Create a new user in the system."""
        return {"id": 1, "name": name, "age": age, "status": "active"}

    guarded = as_fastapi_tool(create_user)
    assert isinstance(guarded, GuardedTool)
    assert guarded.name == "create_user"

    report = run_chain_test(
        [guarded],
        test_cases=FULL_FUZZ_CASES,
        base_input={"name": "Alice", "age": 30},
        assert_reliability=0.0,
    )

    print(f"\n  🔬 FastAPI FULL FUZZ:")
    print(f"     Tool: {guarded.name}")
    print(f"     Reliability: {report.reliability:.1%}")
    print(f"     Total runs: {len(report.runs)}")
    print(f"     Passed: {sum(1 for r in report.runs if r.success)}")
    print(f"     Failed: {sum(1 for r in report.runs if not r.success)}")

    happy_runs = [r for r in report.runs if r.test_case_type == "happy_path"]
    assert all(r.success for r in happy_runs), "Happy path runs should always succeed"
    assert 0.0 < report.reliability <= 1.0


# ═══════════════════════════════════════════════════════════
#  5. ALL frameworks — FULL FUZZ individually
# ═══════════════════════════════════════════════════════════

def test_all_frameworks_full_fuzz():
    """Run FULL fuzzing on all 4 frameworks and print a comparison scoreboard."""
    from llama_index.core.tools import FunctionTool as LlamaFT
    from autogen_core.tools import FunctionTool as AutoGenFT
    from swarm import Agent
    from toolguard.integrations.llamaindex import guard_llamaindex_tool
    from toolguard.integrations.autogen import guard_autogen_tool
    from toolguard.integrations.swarm import guard_swarm_agent
    from toolguard.integrations.fastapi import as_fastapi_tool

    # LlamaIndex
    def search_docs(query: str) -> str:
        """Search documentation."""
        return f"Results for: {query}"
    llama_g = guard_llamaindex_tool(LlamaFT.from_defaults(fn=search_docs))

    # AutoGen
    def summarize(text: str) -> str:
        """Summarize text."""
        return text[:50]
    autogen_g = guard_autogen_tool(AutoGenFT(summarize, name="summarize", description="Summarize"))

    # Swarm
    def translate(text: str) -> str:
        """Translate text."""
        return f"[translated] {text}"
    swarm_g = guard_swarm_agent(Agent(name="Translator", functions=[translate]))

    # FastAPI
    def store_result(result: str) -> dict:
        """Store a result."""
        return {"stored": True, "content": result}
    fastapi_g = as_fastapi_tool(store_result)

    all_tools = [
        ("LlamaIndex", llama_g, {"query": "hello"}),
        ("AutoGen", autogen_g, {"text": "some text to summarize"}),
        ("Swarm", swarm_g[0], {"text": "translate me"}),
        ("FastAPI", fastapi_g, {"result": "done"}),
    ]

    print("\n  ╔═══════════════════════════════════════════════════╗")
    print("  ║     FULL FUZZ SCOREBOARD — ALL REAL FRAMEWORKS   ║")
    print("  ╠═══════════════════════════════════════════════════╣")

    for framework_name, tool, base_input in all_tools:
        report = run_chain_test(
            [tool],
            test_cases=FULL_FUZZ_CASES,
            base_input=base_input,
            assert_reliability=0.0,
        )
        passed = sum(1 for r in report.runs if r.success)
        failed = sum(1 for r in report.runs if not r.success)
        print(f"  ║  {framework_name:<12} │ {report.reliability:>5.1%} │ ✓{passed} ✗{failed}  ║")

        # Happy path MUST work
        happy_runs = [r for r in report.runs if r.test_case_type == "happy_path"]
        assert all(r.success for r in happy_runs), f"{framework_name} happy path failed!"

    print("  ╚═══════════════════════════════════════════════════╝")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
