import sys
import json

try:
    from crewai_tools import ScrapeWebsiteTool
except ImportError as e:
    print(f"Failed to import CrewAI: {e}")
    sys.exit(1)

from toolguard.integrations.crewai import guard_crewai_tool
from toolguard.core.chain import test_chain

def run_crewai_fuzz():
    print("Initialize native CrewAI ScrapeWebsiteTool...")
    c_tool = ScrapeWebsiteTool()
    
    print("Shielding with ToolGuard...")
    safe_tool = guard_crewai_tool(c_tool)
    
    print("🛡️ Running 40 LLM hallucinations against the CrewAI Tool...")
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
            
    with open("crewai_fuzz_report.json", "w") as f:
        f.write(report.to_json(indent=2))

if __name__ == "__main__":
    run_crewai_fuzz()
