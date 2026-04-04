import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from toolguard.mcp.policy import MCPPolicy
from toolguard.mcp.interceptor import MCPInterceptor

def worker_node(node_id: int, policy: MCPPolicy, results: list):
    """
    Simulates a Kubernetes Pod (Agent deployment) firing an aggressive
    payload at the infrastructure.
    """
    # 1. Instantiate Interceptor (simulating completely standalone pod creation)
    # Using local backend since we don't have a live Redis container accessible.
    interceptor = MCPInterceptor(policy)
    
    # Simulate agent requesting highly protected resource
    result = interceptor.intercept("shutdown_server", {"force": True})
    
    layer_result = {
        "node_id": node_id,
        "allowed": result.allowed,
        "reason": result.reason
    }
    results.append(layer_result)

if __name__ == "__main__":
    import json
    import fakeredis
    from toolguard.core.storage.redis_backend import RedisStorageBackend
    
    print("=" * 70)
    print("  ToolGuard V6.1 — Distributed Swarm Rate Limit Test")
    print("=" * 70)
    
    # Policy: Strict 5 allowed
    policy = MCPPolicy.from_yaml_dict({
        "defaults": {"rate_limit": 5, "risk_tier": 0},
        "tools": {"shutdown_server": {}}
    })

    def run_swarm(name: str, backend_factory, is_redis=False):
        print(f"\n🚀 Phase: {name} (20 Concurrent Nodes)")
        results = []
        threads = []
        for i in range(20):
            # In K8s, each pod creates its own interceptor instance.
            interceptor = MCPInterceptor(policy)
            if backend_factory:
                interceptor.storage = backend_factory()
            
            t = threading.Thread(target=worker_node, args=(i, interceptor.policy, results))
            # Inject the custom interceptor through a dirty local binding for the test
            t.run_interceptor = interceptor
            
            def custom_worker(node, p, res, i_ceptor):
                r = i_ceptor.intercept("shutdown_server", {"force": True})
                res.append({"node_id": node, "allowed": r.allowed, "reason": r.reason})
                
            t = threading.Thread(target=custom_worker, args=(i, policy, results, interceptor))
            threads.append(t)
            t.start()
            
        for t in threads: t.join()

        allowed = sum(1 for r in results if r["allowed"])
        denied = sum(1 for r in results if not r["allowed"])
        print(f"\nEXPECTED LIMIT : 5")
        print(f"ACTUAL ALLOWED : {allowed}")
        return allowed == 5

    # --- Phase 1: Local Backend (JSON without OS lock) ---
    cache_path = ".toolguard/rate_limits.json"
    if os.path.exists(cache_path): os.remove(cache_path)
    
    local_pass = run_swarm("LOCAL BACKEND (Kuberntes Multi-Pod)", None)
    if not local_pass:
        print("\n⚠️ RESULT: MASSIVE CONCURRENCY LEAK. Local JSON overwritten continuously.")

    # --- Phase 2: Enterprise Redis Storage ---
    fake_pool = fakeredis.FakeRedis()
    def get_redis():
        r = RedisStorageBackend("redis://ignore")
        r.client = fake_pool  # inject the shared memory
        return r
        
    redis_pass = run_swarm("REDIS DISTRIBUTED BACKEND", get_redis)
    if redis_pass:
        print("\n🏆 RESULT: PERFECT DISTRIBUTED ENFORCEMENT. Network backend blocked the swarm.")
    
    print("=" * 70)
