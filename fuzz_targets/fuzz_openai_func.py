"""
Rigorous fuzz testing for OpenAI Function Calling schema parsing.
"""
import sys
from toolguard.core.chain import test_chain
from toolguard.integrations.openai_func import from_openai_function
from toolguard.reporters.console import print_chain_report

# 1. Define a raw OpenAI function schema
openai_schema = {
    "type": "function",
    "function": {
        "name": "book_flight",
        "description": "Book a flight for a user.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "The destination city"},
                "passengers": {"type": "integer", "description": "Number of passengers"},
                "premium": {"type": "boolean", "description": "Premium class?"}
            },
            "required": ["destination", "passengers"]
        }
    }
}

# 2. Define the vulnerable backend function that assumes perfect LLM inputs
def book_flight(**kwargs) -> str:
    # VULNERABILITY: Blindly accessing kwargs, assuming correct types
    # If LLM hallucinates null, .upper() throws AttributeError
    dest = kwargs["destination"].upper() 
    
    # If LLM hallucinates string, math throws TypeError
    price = kwargs["passengers"] * 500   
    
    # If LLM sends string instead of bool
    if kwargs.get("premium"):
        price *= 2
        
    return f"Booked flight to {dest} for {kwargs['passengers']} passengers. Total: ${price}"

# 3. Wrap it with ToolGuard (this parses the OpenAI JSON schema into Pydantic validators)
guarded_tool = from_openai_function(openai_schema, book_flight)

if __name__ == "__main__":
    report = test_chain(
        [guarded_tool],
        base_input={"destination": "Paris", "passengers": 2, "premium": False},
        iterations=40,
        assert_reliability=0.0  # We expect raw to fail, but ToolGuard should intercept
    )
    
    print_chain_report(report)
    
    # Assert that NO ToolGuard internal crashes happened.
    # All failures should be SchemaValidationError (intercepted).
    internal_crashes = [
        step for run in report.runs for step in run.steps 
        if not step.success and step.error_type not in ("SchemaValidationError", "PromptInjectionVulnerability")
    ]
    
    if internal_crashes:
        print("\n❌ FAILED: ToolGuard allowed a native exception to leak!")
        sys.exit(1)
    else:
        print("\n✅ PASSED: All 40 hallucinated attacks intercepted cleanly. Zero native crashes.")
        sys.exit(0)
