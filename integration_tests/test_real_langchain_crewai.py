"""
REAL Integration Tests — LangChain and CrewAI — FULL FUZZING
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This test suite uses the REAL pip-installed versions of:
  - langchain_core.tools.tool
  - crewai.tools.BaseTool

Every test runs the FULL fuzzing suite — null, malformed, type mismatch,
missing fields — to produce REAL reliability scores.
"""

import pytest
from toolguard.core.chain import test_chain as run_chain_test
from toolguard.core.validator import GuardedTool

FULL_FUZZ_CASES = [
    "happy_path",
    "null_handling",
    "malformed_data",
    "type_mismatch",
    "missing_fields",
]


# ═══════════════════════════════════════════════════════════
#  1. REAL LangChain Integration — FULL FUZZING
# ═══════════════════════════════════════════════════════════

def test_real_langchain_full_fuzz():
    """Use the REAL langchain_core @tool decorator with FULL fuzzing."""
    from langchain_core.tools import tool
    from toolguard.integrations.langchain import guard_langchain_tool

    @tool
    def multiply_lc(a: int, b: int) -> int:
        """Multiply two numbers together (LangChain)."""
        return a * b

    guarded = guard_langchain_tool(multiply_lc)

    assert isinstance(guarded, GuardedTool)
    assert guarded.name == "multiply_lc"

    report = run_chain_test(
        [guarded],
        test_cases=FULL_FUZZ_CASES,
        base_input={"a": 4, "b": 5},
        assert_reliability=0.0,
    )

    print(f"\n  🔬 LangChain FULL FUZZ:")
    print(f"     Tool: {guarded.name}")
    print(f"     Reliability: {report.reliability:.1%}")
    print(f"     Total runs: {len(report.runs)}")
    print(f"     Passed: {sum(1 for r in report.runs if r.success)}")
    print(f"     Failed: {sum(1 for r in report.runs if not r.success)}")

    happy_runs = [r for r in report.runs if r.test_case_type == "happy_path"]
    assert all(r.success for r in happy_runs), "Happy path should always succeed"
    assert 0.0 < report.reliability <= 1.0


# ═══════════════════════════════════════════════════════════
#  2. REAL CrewAI Integration — FULL FUZZING
# ═══════════════════════════════════════════════════════════

def test_real_crewai_full_fuzz():
    """Use the REAL crewai.tools.BaseTool class with FULL fuzzing."""
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field
    from toolguard.integrations.crewai import guard_crewai_tool

    class CalcDiscountSchema(BaseModel):
        price: float = Field(..., description="The original price")
        percent: float = Field(..., description="The discount percentage")

    class CalcDiscountTool(BaseTool):
        name: str = "crew_calc_discount"
        description: str = "Calculate a discounted price (CrewAI)."
        args_schema: type[BaseModel] = CalcDiscountSchema

        def _run(self, price: float, percent: float) -> float:
            return price * (1 - percent / 100)

    crew_tool = CalcDiscountTool()
    guarded = guard_crewai_tool(crew_tool)

    assert isinstance(guarded, GuardedTool)
    assert guarded.name == "crew_calc_discount"

    report = run_chain_test(
        [guarded],
        test_cases=FULL_FUZZ_CASES,
        base_input={"price": 200.0, "percent": 10.0},
        assert_reliability=0.0,
    )

    print(f"\n  🔬 CrewAI FULL FUZZ:")
    print(f"     Tool: {guarded.name}")
    print(f"     Reliability: {report.reliability:.1%}")
    print(f"     Total runs: {len(report.runs)}")
    print(f"     Passed: {sum(1 for r in report.runs if r.success)}")
    print(f"     Failed: {sum(1 for r in report.runs if not r.success)}")

    happy_runs = [r for r in report.runs if r.test_case_type == "happy_path"]
    assert all(r.success for r in happy_runs), "Happy path should always succeed"
    assert 0.0 < report.reliability <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
