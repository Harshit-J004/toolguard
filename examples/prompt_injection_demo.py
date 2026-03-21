from toolguard import create_tool
from toolguard.core.chain import test_chain
from toolguard.reporters.console import print_chain_report

# VULNERABLE TOOL: Takes user bio and returns it exactly as a profile object.
# If an attacker puts an injection in their bio, this tool acts as a pass-through
# and feeds the injection directly back to the LLM orchestrator.
@create_tool
def fetch_user_profile(user_query: str) -> dict:
    # A real tool might hit an API or DB layer here.
    return {
        "status": "success",
        "data": {
            "name": "Target User",
            "bio_notes": user_query  # <-- Passes input directly to output! Danger!
        }
    }

print("\n🚀 Fuzzing tool chain for Prompt Injection vulnerabilities...")

report = test_chain(
    [fetch_user_profile],
    base_input={"user_query": "Harshit is a great engineer."},
    test_cases=["prompt_injection"],
    assert_reliability=0.0  # Allow it to fail so we can print the report
)

print_chain_report(report)
