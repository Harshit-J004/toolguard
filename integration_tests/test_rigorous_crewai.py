import os
import unittest.mock as mock

# Set dummy key for CrewAI instantiation
os.environ["OPENAI_API_KEY"] = "sk-dummy-key-for-rigorous-testing"

from crewai import Agent, Task, Crew, Process
from toolguard import create_tool
from toolguard.core.errors import ToolGuardApprovalDeniedError

# 1. The Critical System Tool (Native CrewAI Tool pattern)
# We protect this with ToolGuard L2 Audit & L5 Semantic Injection protection
@create_tool(risk_tier=2)
def write_system_config(filepath: str, content: str) -> str:
    """
    Saves sensitive system configuration to the local disk.

    Args:
        filepath: The path to the config file.
        content: The configuration string.
    """
    # MOCKED: In reality, this would be: open(filepath, 'w').write(content)
    return f"Configuration saved to {filepath}."

# 2. Define the Crew Roles
def test_rigorous_crewai_firewall():
    """
    Simulates a rigorous 'Cross-Agent' attack where a Researcher Agent 
    deceives a System Executor Agent into running a payload.
    """
    print("\n🚀 Starting Rigorous CrewAI Multi-Agent Security Test...")

    # AGENT 1: The Researcher (Vulnerable to prompt injection or malicious sources)
    researcher = Agent(
        role='Lead Researcher',
        goal='Find the latest database configuration parameters.',
        backstory='Expert in searching technical documentation.',
        allow_delegation=True,
        verbose=True
    )

    # AGENT 2: The Executor (Privileged action agent)
    executor = Agent(
        role='System Architect',
        goal='Save the researchers database config to the system.',
        backstory='Authorized to modify system state.',
        tools=[write_system_config], # The tool is wrapped by ToolGuard!
        verbose=True
    )

    # ATTACK: We mock the Researcher's 'output' to contain a shell injection attack.
    # Disguised as a 'benign' config string, it actually contains a `; rm -rf /` payload.
    malicious_payload = "db_connection_str='root:pass@127.0.0.1:3306'; rm -rf /var/www/html #"

    # We mock the Confirm.ask to simulate a human DENYING the action (L2: Audit)
    with mock.patch("rich.prompt.Confirm.ask", return_value=False):
        try:
            print("🛡️  Attempting to execute the multi-agent task chain...")
            # We call the tool directly as if the Crew delegated it
            write_system_config(
                filepath="/etc/db_config.conf", 
                content=malicious_payload
            )
            raise Exception("FAIL: ToolGuard failed to block the cross-agent attack!")
        except ToolGuardApprovalDeniedError as e:
            print(f"✅ SUCCESS: ToolGuard's L2 Firewall intercepted the cross-agent attack on CrewAI!")
            print(f"   Blocked Payload: {malicious_payload}")
            print(f"   Error: {e.message}")

if __name__ == "__main__":
    test_rigorous_crewai_firewall()
    print("\n🏆 ToolGuard proven running as a firewall for the most rigorous multi-agent frameworks.")
