"""
Enterprise Demo
This script demonstrates the "Minimal API" and "Coverage" features.
"""

from typing import Annotated
from pydantic import Field
from toolguard import create_tool, quick_check

# 1. We create a tool with strict semantic constraints
@create_tool(schema="auto")
def process_payment(
    user_id: int, 
    amount: Annotated[float, Field(gt=0)]  # Must be greater than 0
) -> dict:
    
    # Simulate a deep, hidden bug that only crashes on Nulls
    if amount is None:
        raise ValueError("CRITICAL SYSTEM CRASH: Amount cannot be None")
        
    return {"status": "success", "processed": amount}

if __name__ == "__main__":
    print("\n🚀 [1] Running ToolGuard's Minimal 1-Line API...")
    # 2. We test it using exactly 1 line of code!
    # Notice we purposely only test the Happy Path to prove the Coverage metrics work!
    quick_check(process_payment, test_cases=["happy_path"])
