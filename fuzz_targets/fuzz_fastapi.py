import sys
import json
from pydantic import BaseModel, Field

from toolguard.integrations.fastapi import as_fastapi_tool
from toolguard.core.chain import test_chain

class UserProfile(BaseModel):
    username: str = Field(..., min_length=3)
    age: int = Field(..., ge=18, description="User age must be an adult")
    email: str

def create_user_endpoint(profile: UserProfile, is_admin: bool = False) -> str:
    """FastAPI route handler to create a new user.
    
    Args:
        profile: The user's profile details natively validated by Pydantic.
        is_admin: Admin flag.
    """
    # This simulates the backend logic.
    # There is ZERO manual validation here - FastAPI natively handles validation
    # at the HTTP boundary. But when exposed to an LLM, that HTTP boundary is bypassed!
    
    # If the LLM passes an invalid payload directly to this function, Pydantic blows up
    # with a native ValidationError trace, crashing the agent.
    
    db_id = 999
    return json.dumps({"status": "success", "id": db_id, "username": profile.username, "admin": is_admin})

def run_fastapi_fuzz():
    print("Initializing raw FastAPI backend endpoint...")
    
    # Wrap it with ToolGuard to make it safe for LLM orchestration
    safe_tool = as_fastapi_tool(create_user_endpoint)
    
    print("🛡️ Running ToolGuard Fuzzer against the FastAPI Route Handler...")
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
            
    with open("fastapi_fuzz_report.json", "w") as f:
        f.write(report.to_json(indent=2))

if __name__ == "__main__":
    run_fastapi_fuzz()
