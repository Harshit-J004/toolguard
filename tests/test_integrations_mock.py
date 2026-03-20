import pytest

from toolguard.core.chain import test_chain as run_chain_test
from toolguard.integrations.autogen import guard_autogen_tool
from toolguard.integrations.fastapi import as_fastapi_tool
from toolguard.integrations.llamaindex import guard_llamaindex_tool
from toolguard.integrations.swarm import guard_swarm_agent

# Detect if real libraries are installed (adapters enforce isinstance in that case)
try:
    import llama_index.core
    _has_real_llamaindex = True
except ImportError:
    _has_real_llamaindex = False

try:
    import autogen_core
    _has_real_autogen = True
except ImportError:
    _has_real_autogen = False


# --- 1. FastAPI Verification ---
def dummy_fastapi_endpoint(user_id: int) -> dict:
    return {"status": "ok", "user": user_id}

def test_fastapi_integration():
    guarded = as_fastapi_tool(dummy_fastapi_endpoint)
    # The fuzzer should catch that 'user_id' requires an int when we pass a string.
    # We test it with just the happy path to ensure the wrapper works.
    report = run_chain_test([guarded], test_cases=["happy_path"], base_input={"user_id": 12})
    assert report.reliability == 1.0


# --- 2. LlamaIndex Verification ---
def _llama_query_func(query: str) -> str:
    """A mock tool for fetching data."""
    return f"Llama Data for {query}"

class MockLlamaMetadata:
    name = "mock_llama_tool"
    description = "A mock tool for fetching data."

class MockLlamaTool:
    def __init__(self):
        self.metadata = MockLlamaMetadata()
        self.fn = _llama_query_func

@pytest.mark.skipif(
    _has_real_llamaindex,
    reason="Real llama-index-core is installed; use test_real_integrations.py instead"
)
def test_llamaindex_integration():
    mock_tool = MockLlamaTool()
    guarded = guard_llamaindex_tool(mock_tool)
    
    assert guarded.name == "mock_llama_tool"
    
    report = run_chain_test([guarded], test_cases=["happy_path"], base_input={"query": "test"})
    assert report.reliability == 1.0


# --- 3. AutoGen Verification ---
def _autogen_process_func(amount: float) -> str:
    """A mock tool for processing."""
    return f"Processed ${amount}"

class MockAutoGenTool:
    def __init__(self):
        self.name = "mock_autogen_tool"
        self.description = "A mock tool for processing."
        self._func = _autogen_process_func

@pytest.mark.skipif(
    _has_real_autogen,
    reason="Real autogen-core is installed; use test_real_integrations.py instead"
)
def test_autogen_integration():
    mock_tool = MockAutoGenTool()
    guarded = guard_autogen_tool(mock_tool)
    
    assert guarded.name == "mock_autogen_tool"
    
    report = run_chain_test([guarded], test_cases=["happy_path"], base_input={"amount": 99.99})
    assert report.reliability == 1.0


# --- 4. OpenAI Swarm Verification ---
class MockSwarmAgent:
    def __init__(self):
        self.functions = [self.swarm_func_1, self.swarm_func_2]
        
    def swarm_func_1(self, instruction: str) -> int:
        return len(instruction)
        
    def swarm_func_2(self, length: int) -> bool:
        return length > 5

def test_swarm_integration():
    mock_agent = MockSwarmAgent()
    guarded_tools = guard_swarm_agent(mock_agent)
    
    assert len(guarded_tools) == 2
    assert guarded_tools[0].name == "swarm_func_1"
    
    # We can pass the whole extracted array natively into test_chain!
    report = run_chain_test(
        guarded_tools, 
        test_cases=["happy_path"], 
        base_input={"instruction": "test_chain"}
    )
    assert report.reliability == 1.0
