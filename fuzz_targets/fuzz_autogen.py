import sys
import json

from toolguard.integrations.autogen import guard_autogen_tool
from toolguard.core.chain import test_chain

# A raw Python function representing a typical backend tool
# an AutoGen agent would have access to. 
def calculate_discount(price: float, discount_percent: int) -> str:
    """Calculates a discounted price.
    
    Args:
        price: The original price in dollars.
        discount_percent: The integer discount percentage (e.g. 20 for 20%).
    """
    # Raw vulnerability: no type checking/None checking!
    # If the LLM passes null or a string, this natively crashes AutoGen's runtime loop.
    final_price = price - (price * (discount_percent / 100.0))
    return f"The discounted price is ${final_price:.2f}"


def run_autogen_fuzz():
    print("Initializing AutoGen FunctionTool...")
    try:
        from autogen_core.tools import FunctionTool
    except ImportError:
        print("autogen_core not installed. Make sure 'autogen-core' is available.")
        sys.exit(1)

    # 1. Standard AutoGen Tool Registration
    autogen_tool = FunctionTool(
        calculate_discount, 
        description="Calculates a discounted price."
    )
    
    # 2. Add the ToolGuard shielding layer
    safe_tool = guard_autogen_tool(autogen_tool)
    
    print("🛡️ Running ToolGuard Fuzzer precisely against the AutoGen FunctionTool...")
    report = test_chain(
        [safe_tool],
        test_cases=["happy_path", "null_handling", "malformed_data", "type_mismatch"],
        iterations=30,
        assert_reliability=0.0
    )
    
    print("\n" + "="*50)
    print("                TEST COMPLETE                ")
    print("="*50)
    print(f"Reliability Score: {report.reliability * 100:.1f}%")
    print(f"Total Tests: {report.total_tests}, Passed: {report.passed}, Failed: {report.failed}")
    
    if report.top_failures:
        print("\n🚨 VULNERABILITIES DETECTED (Intercepted by ToolGuard) 🚨")
        for fail in report.top_failures:
            print(f"- [{fail['count']}x] {fail['error_type']}")
            print(f"  Root cause: {fail['root_cause']}")
            print(f"  Suggestion: {fail['suggestion']}")
            print()
            
    with open("autogen_fuzz_report.json", "w") as f:
        f.write(report.to_json(indent=2))

if __name__ == "__main__":
    run_autogen_fuzz()
