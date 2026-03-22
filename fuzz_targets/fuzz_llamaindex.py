import sys

try:
    from llama_index.core.tools import FunctionTool
except ImportError as e:
    print(f"Failed to import LlamaIndex: {e}")
    sys.exit(1)

from toolguard.integrations.llamaindex import guard_llamaindex_tool
from toolguard.core.chain import test_chain

def load_financial_data(ticker: str, year: int) -> dict:
    """Loads financial performance data for a given ticker and year."""
    # When natively executed by LlamaIndex, an LLM hallucination of a string 
    # instead of an int for the `year` argument causes Pydantic to throw an
    # unhandled native ValidationError crashing the Python orchestrator loop.
    return {"ticker": ticker, "year": year, "revenue": 1000000 * year}

def run_llamaindex_fuzz():
    print("Initialize native LlamaIndex FunctionTool...")
    llama_tool = FunctionTool.from_defaults(fn=load_financial_data)
    
    print("Shielding with ToolGuard...")
    safe_tool = guard_llamaindex_tool(llama_tool)
    
    print("🛡️ Running 40 LLM hallucinations against the LlamaIndex Tool...")
    report = test_chain(
        [safe_tool],
        test_cases=["happy_path", "null_handling", "malformed_data", "type_mismatch"],
        iterations=40,
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
            
    with open("llamaindex_fuzz_report.json", "w") as f:
        f.write(report.to_json(indent=2))

if __name__ == "__main__":
    run_llamaindex_fuzz()
