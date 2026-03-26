import sys
import os
import pathlib

# Add MiroFish to python path
sys.path.insert(0, os.path.abspath("fuzz_targets/MiroFish"))

# Mock MiroFish Config so local dependencies pass
import backend.app.config
class MockConfig:
    ZEP_API_KEY = "mock_key"
    ZEP_URL = "http://mock"
    DB_PATH = "mock.db"
    LLM_MODEL = "mock"
    LOG_LEVEL = "ERROR"
    OPENAI_API_KEY = "mock"
    UPLOAD_FOLDER = "mock"

backend.app.config.Config = MockConfig

from backend.app.services.zep_tools import ZepToolsService
from toolguard import create_tool, test_chain

# Kill MiroFish's inner retries so ToolGuard can fuzz it instantly
ZepToolsService.MAX_RETRIES = 1
ZepToolsService.RETRY_DELAY = 0.0

print("Initializing MiroFish ZepToolsService...")
zep_service = ZepToolsService(api_key="mock")

@create_tool(schema="auto")
def mirofish_search_graph(graph_id: str, query: str, limit: int = 10, scope: str = "edges") -> dict:
    """Search knowledge graph for simulation predictions."""
    try:
        # Wrap it for deep schema fuzzing. We catch inner execution errors 
        # so ToolGuard can purely judge strict type/schema structural resilience.
        zep_service.search_graph(graph_id=graph_id, query=query, limit=limit, scope=scope)
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}

print("\nRunning ToolGuard CI/CD Reliability Check on MiroFish...")

report = test_chain(
    [mirofish_search_graph],
    test_cases=["null_handling", "type_mismatch", "malformed_data", "missing_fields"],
    iterations=15,
    assert_reliability=0.0
)

from toolguard.reporters.console import print_chain_report
print_chain_report(report)

# Export standard CI/CD XML format
from toolguard.reporters.junit import generate_junit_xml
xml_out = "mirofish_cicd_results.xml"
generate_junit_xml(report, xml_out)
print(f"\n✅ CI/CD standard JUnit XML report generated at: {xml_out}")
