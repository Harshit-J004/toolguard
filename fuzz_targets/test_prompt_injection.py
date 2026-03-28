from toolguard import test_chain, create_tool
import sys

# Custom object to test __dict__ scanning
class ComplexNestedObject:
    def __init__(self, data):
        self.secret_data = data
        self.circular_ref = self  # Circular reference to test id() tracking

@create_tool
def vulnerable_echo_nested_dict(arg1: str) -> dict:
    """Reflects input deep inside a nested dictionary."""
    return {"level1": {"level2": {"level3": arg1}}}

@create_tool
def vulnerable_echo_custom_class(arg1: str) -> ComplexNestedObject:
    """Reflects input inside a custom class with a circular reference."""
    # We apply a case mutation to test .casefold()
    mutated = arg1.replace("SYSTEM OVERRIDE", "sYsTeM oVeRrIdE")
    return ComplexNestedObject(mutated)

@create_tool
def vulnerable_echo_bytearray(arg1: str) -> dict:
    """Reflects input inside a byte array to test binary scanning."""
    byte_payload = bytearray(arg1, "utf-8")
    return {"binary_data": byte_payload}

@create_tool
def vulnerable_echo_list_circular(arg1: str) -> list:
    """Reflects input in a list that contains a reference to itself."""
    my_list = [1, 2, arg1]
    my_list.append(my_list)
    return my_list

def run_tests():
    tools = [
        vulnerable_echo_nested_dict,
        vulnerable_echo_custom_class,
        vulnerable_echo_bytearray,
        vulnerable_echo_list_circular
    ]
    
    print("Running Recursive Prompt Injection Tests...")
    
    failed_detect = []
    for tool in tools:
        report = test_chain([tool], test_cases=["prompt_injection"], assert_reliability=0.0)
        caught = report.reliability < 1.0
        if not caught:
            failed_detect.append(tool.__name__)
            
    print("\n--- RESULTS ---")
    if not failed_detect:
        print("All 4 Recursive Prompt Injection Tests Passed!")
    else:
        print("FAILED TO DETECT INJECTION IN:")
        for name in failed_detect:
            print(f"- {name}")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
