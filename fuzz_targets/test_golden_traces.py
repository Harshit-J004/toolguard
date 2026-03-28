import time
import threading
from concurrent.futures import ThreadPoolExecutor
from toolguard import create_tool, TraceTracker
from toolguard.core.errors import ToolGuardTraceMismatchError

@create_tool
def auth_tool(token: str) -> str:
    time.sleep(0.05)
    return "authorized"

@create_tool
def fetch_tool(doc_id: int) -> dict:
    time.sleep(0.05)
    return {"data": "confidential"}

@create_tool
def process_tool(data: dict) -> str:
    time.sleep(0.05)
    return "processed"

@create_tool
def refund_tool(tx_id: int) -> str:
    time.sleep(0.05)
    return "refunded"

def run_golden_traces_test():
    print("🚀 Running Golden Traces & DAG Verifications...")

    # TEST 1: Basic Trace and Sequence Assertions
    print("\n[TEST 1] Testing Basic ContextVar Tracer & Subsequence")
    with TraceTracker() as trace:
        auth_tool("tok_123")
        fetch_tool(99)
        process_tool({"a": 1})
        
        # Subsequence check: fetch_tool must happen after auth_tool
        try:
            trace.assert_sequence(["auth_tool", "process_tool"])
            print("✅ PASS: assert_sequence recognized [auth -> process] inside [auth -> fetch -> process]")
        except Exception as e:
            print(f"❌ FAIL: {e}")
            return

    # TEST 2: ignore_retries Duplicate Collapsing
    print("\n[TEST 2] Testing ignore_retries=True Duplicate Collapsing")
    with TraceTracker() as trace:
        auth_tool("abc")
        fetch_tool(1)
        # Simulate autonomous LLM retry loop
        fetch_tool(1)
        fetch_tool(1)
        refund_tool(500)
        
        try:
            # Expected path mathematically collapses consecutive duplicates
            trace.assert_golden_path(["auth_tool", "fetch_tool", "refund_tool"], ignore_retries=True)
            print("✅ PASS: assert_golden_path successfully collapsed 3 fetch_tool calls down to 1.")
        except Exception as e:
            print(f"❌ FAIL: {e}")
            return

    # TEST 3: Path Assertion Failure Catching
    print("\n[TEST 3] Testing Strict Path Rejections")
    with TraceTracker() as trace:
        auth_tool("abc")
        refund_tool(500)
        
        try:
            trace.assert_golden_path(["auth_tool", "fetch_tool"])
            print("❌ FAIL: assert_golden_path completely missed the violation!")
            return
        except ToolGuardTraceMismatchError:
            print("✅ PASS: assert_golden_path successfully threw an Exception when the AI went off script.")

    # TEST 4: ThreadPoolExecutor Global Fallback
    print("\n[TEST 4] Testing ThreadPool Survival for CrewAI Swarms")
    tracer = TraceTracker()
    global_trace = tracer.set_global()  # Fallback since threads lose contextvars
    
    def worker(val):
        auth_tool(str(val))
        return val

    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(worker, [1, 2, 3]))
        
    tracer.reset_global()

    try:
        # Since threads are concurrent, the exact order is non-deterministic 
        # but there absolutely MUST be 3 nodes named "auth_tool".
        if len(global_trace.nodes) == 3 and all(n.tool_name == "auth_tool" for n in global_trace.nodes):
            print("✅ PASS: TraceTracker successfully survived the thread boundary.")
        else:
            print("❌ FAIL: Nodes lost across threads!")
            return
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return

    # TEST 5: Latency Metrics
    print("\n[TEST 5] Testing Sub-Millisecond Node Latency Metrics")
    node = global_trace.nodes[0]
    if node.latency_ms > 0:
        print(f"✅ PASS: Node Latency calculated precisely at {node.latency_ms:.2f}ms")
    else:
        print("❌ FAIL: TraceNode missed latency calculation")
        return

    print("\n🎉 All 5 DAG Instrumentation Tests Passed!")

if __name__ == "__main__":
    run_golden_traces_test()
