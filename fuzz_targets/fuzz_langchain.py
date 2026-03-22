import sys
import json

try:
    from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
    from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
except ImportError as e:
    print(f"Failed to import LangChain: {e}")
    sys.exit(1)

from toolguard.integrations.langchain import guard_langchain_tool
from toolguard.core.chain import test_chain

def run_langchain_fuzz():
    print("Initializing LangChain Wikipedia Tool...")
    
    api_wrapper = WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=100)
    lc_tool = WikipediaQueryRun(api_wrapper=api_wrapper)
    
    # Wrap it with ToolGuard to make it safe for LLM orchestration
    safe_tool = guard_langchain_tool(lc_tool)
    
    print("🛡️ Running ToolGuard Fuzzer against LangChain's Wikipedia Tool...")
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
            
    with open("langchain_fuzz_report.json", "w") as f:
        f.write(report.to_json(indent=2))

if __name__ == "__main__":
    run_langchain_fuzz()
