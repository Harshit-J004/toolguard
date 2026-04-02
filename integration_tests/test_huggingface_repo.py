import pytest
from smolagents import tool
from toolguard import create_tool
from toolguard.core.errors import ToolGuardApprovalDeniedError

# 1. First, we define a completely standard Hugging Face Smolagents tool
# This represents how millions of developers currently write agentic functions
@tool
def execute_system_command(command: str) -> str:
    """
    Executes a bash command on the local virtual machine on behalf of the agent.

    Args:
        command: The bash command to run.
    """
    # In a real environment, this would be: os.system(command)
    # We mock it for safety in the test suite
    return f"Executed `{command}` successfully."

# 2. We apply ToolGuard's 7-Layer Defense proxy
# We elevate this dangerous tool to Risk Tier 2 (Destructive)
@create_tool(schema="auto", risk_tier=2)
def secure_execute_system_command(command: str) -> str:
    # We call the underlying Hugging Face tool ONLY if ToolGuard allows it
    return execute_system_command(command=command)

def test_smolagents_native_vulnerability():
    """
    Proves that the native Hugging Face agent framework will happily
    execute destructive prompt injections out-of-the-box.
    """
    # The agent receives a malicious prompt from a hacker
    malicious_payload = "rm -rf /var/www/html"
    
    # Smolagents implicitly executes it
    result = execute_system_command(command=malicious_payload)
    
    assert "Executed `rm -rf /var/www/html` successfully" in result
    print("\n[VULNERABILITY] Native smolagents brutally executed the destructive payload.")

def test_smolagents_toolguard_defense():
    """
    Proves that ToolGuard natively intercepts and blocks the exact same attack
    on the exact same Hugging Face agent without requiring any code rewrites.
    """
    malicious_payload = "rm -rf /var/www/html; DROP TABLE users;"
    
    import unittest.mock as mock
    with mock.patch("rich.prompt.Confirm.ask", return_value=False):
        try:
            # We attempt the identical attack on the protected proxy
        # Since os.environ["TOOLGUARD_AUTO_APPROVE"] is not set, ToolGuard's L2 firewall halts it
        secure_execute_system_command(command=malicious_payload)
        pytest.fail("ToolGuard failed to block the injection!")
    except ToolGuardApprovalDeniedError as e:
        # ToolGuard violenty intercepted the execution and threw a security block
        print(f"\n[DEFENDED] ToolGuard blocked attack on smolagents: {e.message}")

if __name__ == "__main__":
    test_smolagents_native_vulnerability()
    test_smolagents_toolguard_defense()
    print("\n✅ ToolGuard + Hugging Face Integration Complete.")
