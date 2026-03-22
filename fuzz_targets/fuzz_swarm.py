"""
Rigorous fuzzer for OpenAI Swarm Agent tools.

Swarm agents expose plain Python functions via the `Agent.functions` list.
When an LLM hallucinates invalid arguments (wrong types, nulls, missing fields),
Swarm passes them straight through with zero validation, causing native
TypeErrors, AttributeErrors, and KeyErrors that crash the entire agent loop.

ToolGuard's `guard_swarm_agent` extracts every function from the agent,
wraps each one with Pydantic schema enforcement, and intercepts all
crashes before they can propagate.
"""

import sys

try:
    from swarm import Agent
except ImportError as e:
    print(f"Failed to import OpenAI Swarm: {e}")
    sys.exit(1)

from toolguard.integrations.swarm import guard_swarm_agent
from toolguard.core.chain import test_chain


# --- Realistic Swarm Agent Functions (mimicking production use) ---

def transfer_funds(source_account: str, destination_account: str, amount: float, currency: str = "USD") -> dict:
    """Transfer funds between two accounts."""
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")
    return {
        "status": "completed",
        "source": source_account,
        "destination": destination_account,
        "amount": amount,
        "currency": currency,
        "tx_id": "TX-" + source_account[:4] + destination_account[:4]
    }

def lookup_customer(customer_id: int, include_history: bool = False) -> dict:
    """Lookup customer information by ID."""
    return {
        "customer_id": customer_id,
        "name": f"Customer_{customer_id}",
        "tier": "gold" if customer_id % 2 == 0 else "silver",
        "history": [{"date": "2026-01-01", "action": "signup"}] if include_history else []
    }

def schedule_appointment(patient_name: str, doctor_id: int, date: str, duration_minutes: int = 30) -> dict:
    """Schedule a medical appointment."""
    return {
        "confirmed": True,
        "patient": patient_name,
        "doctor_id": doctor_id,
        "date": date,
        "duration": duration_minutes
    }


def run_swarm_fuzz():
    # Build a realistic Swarm Agent with multiple tools
    print("🔧 Building OpenAI Swarm Agent with 3 production tools...")
    agent = Agent(
        name="FinanceBot",
        instructions="You are a helpful finance assistant.",
        functions=[transfer_funds, lookup_customer, schedule_appointment]
    )

    print("🛡️ Extracting & shielding all agent functions with ToolGuard...")
    guarded_tools = guard_swarm_agent(agent)
    print(f"   → Wrapped {len(guarded_tools)} tools: {[t.name for t in guarded_tools]}")

    # RIGOROUS: run 60 iterations across ALL fuzz categories
    print("\n🚀 Running 60 RIGOROUS LLM hallucinations against ALL Swarm tools...")
    report = test_chain(
        guarded_tools,
        test_cases=[
            "happy_path",
            "null_handling",
            "malformed_data",
            "type_mismatch",
            "missing_fields",
            "extra_fields",
            "empty_input",
            "large_payload",
            "prompt_injection",
        ],
        iterations=60,
        assert_reliability=0.0
    )

    print("\n" + "=" * 60)
    print("             OPENAI SWARM FUZZ TEST COMPLETE              ")
    print("=" * 60)
    print(f"Reliability Score: {report.reliability * 100:.1f}%")
    print(f"Total Tests: {report.total_tests}")
    print(f"Passed: {report.passed}")
    print(f"Failed (Intercepted): {report.failed}")

    if report.top_failures:
        print("\n🚨 VULNERABILITIES DETECTED (Intercepted by ToolGuard) 🚨")
        for fail in report.top_failures:
            print(f"\n  [{fail['count']}x] {fail['error_type']} on '{fail['tool_name']}'")
            print(f"    Root cause: {fail['root_cause']}")
            print(f"    Suggestion: {fail['suggestion']}")

    with open("swarm_fuzz_report.json", "w") as f:
        f.write(report.to_json(indent=2))

    print(f"\n📄 Full report saved to swarm_fuzz_report.json")


if __name__ == "__main__":
    run_swarm_fuzz()
