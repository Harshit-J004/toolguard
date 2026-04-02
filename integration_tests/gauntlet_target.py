import sys
import json
import logging
from toolguard.mcp.interceptor import MCPInterceptor
from toolguard.mcp.policy import MCPPolicy

# Hide verbose internal logging to keep stdout clean for the OS pipe tests
logging.basicConfig(level=logging.CRITICAL)

def main():
    if len(sys.argv) < 2:
        print("Usage: python gauntlet_target.py <json_payload>")
        sys.exit(1)

    payload_str = sys.argv[1]
    
    try:
        data = json.loads(payload_str)
        tool_name = data.get("tool")
        args = data.get("args", {})
    except Exception as e:
        print(f"FAILED_PARSE: {e}")
        sys.exit(1)

    # 1. Instantiate the absolute core 7-layer defense proxy naturally
    policy_dict = {
        "tools": {
            "delete_database": {"risk_tier": 2, "blocked": False}, # Requires Terminal Input
            "read_file": {"constraints": [{"type": "path_deny", "paths": ["/etc/*"]}]},
            "rate_tool": {"rate_limit": 50},
            "spoofer": {"blocked": True}
        }
    }
    policy = MCPPolicy.from_yaml_dict(policy_dict)
    interceptor = MCPInterceptor(policy)

    # 2. Strike the proxy! If hitting L2, natural sys.stdin terminal block happens here!
    result = interceptor.intercept(tool_name, args)

    # 3. Print definitive output for the OS pipe to read
    print(f"INTERCEPT_RESULT||{result.allowed}||{result.layer}||{result.reason}")

if __name__ == "__main__":
    main()
