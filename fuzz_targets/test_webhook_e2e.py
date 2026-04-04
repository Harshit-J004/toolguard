"""
ToolGuard V6.1 — End-to-End Webhook Approval Test
===================================================
Simulates a HEADLESS agent (no terminal) that:
1. Hits a Tier 2 restricted tool
2. Fires a webhook notification (mocked)
3. Enters the polling sleep loop
4. A separate "Manager" thread approves the grant via the StorageBackend
5. The interceptor wakes up and allows execution

This proves the entire async webhook pipeline works without
a real Slack/Discord server.
"""

import os
import sys
import time
import json
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from toolguard.mcp.policy import MCPPolicy
from toolguard.mcp.interceptor import MCPInterceptor
from toolguard.core.webhooks.base import WebhookProvider


# ─── Mock Webhook Provider ───────────────────────────────────
class MockWebhookProvider(WebhookProvider):
    """Captures the grant_id instead of sending a real HTTP request."""
    
    def __init__(self):
        self.last_grant_id = None
        self.sent = False
    
    def send_approval_request(self, tool_name, arguments, grant_id, timeout):
        self.last_grant_id = grant_id
        self.sent = True
        print(f"  📨 [MockWebhook] Notification sent! Grant ID: {grant_id[:12]}...")
        return True


# ─── Simulate a Manager Approving ────────────────────────────
def simulate_manager_approval(storage, provider, delay=4):
    """Waits `delay` seconds, then approves the grant."""
    def _approve():
        time.sleep(delay)
        grant_id = provider.last_grant_id
        if grant_id:
            storage.resolve_execution_grant(grant_id, "APPROVED")
            print(f"  ✅ [Manager] Approved grant {grant_id[:12]}... after {delay}s delay")
    
    t = threading.Thread(target=_approve, daemon=True)
    t.start()
    return t


def simulate_manager_denial(storage, provider, delay=4):
    """Waits `delay` seconds, then denies the grant."""
    def _deny():
        time.sleep(delay)
        grant_id = provider.last_grant_id
        if grant_id:
            storage.resolve_execution_grant(grant_id, "DENIED")
            print(f"  ❌ [Manager] Denied grant {grant_id[:12]}... after {delay}s delay")
    
    t = threading.Thread(target=_deny, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    print("=" * 70)
    print("  ToolGuard V6.1 — End-to-End Webhook Approval Test")
    print("=" * 70)

    policy = MCPPolicy.from_yaml_dict({
        "defaults": {"risk_tier": 0, "rate_limit": 100},
        "tools": {
            "shutdown_server": {
                "risk_tier": 2,
                "approval_timeout": 30,
                "approval_ttl": 0,
            },
        },
    })

    # ─── TEST 1: Headless Approval via Webhook ────────────────
    print("\n📋 TEST 1: Headless Agent → Webhook → Manager Approves")
    print("-" * 70)
    
    mock_provider = MockWebhookProvider()
    interceptor = MCPInterceptor(policy, webhook_provider=mock_provider, verbose=True)
    
    # Simulate headless: override _is_interactive to return False
    interceptor._is_interactive = lambda: False
    
    # Start the manager thread that will approve after 4 seconds
    manager_thread = simulate_manager_approval(interceptor.storage, mock_provider, delay=4)
    
    start = time.time()
    result = interceptor.intercept("shutdown_server", {"force": True, "reason": "scheduled maintenance"})
    elapsed = time.time() - start
    
    manager_thread.join()
    
    assert mock_provider.sent, "Webhook was not sent!"
    assert result.allowed, f"Expected ALLOWED but got DENIED: {result.reason}"
    print(f"\n  🎯 Result: {'ALLOWED ✅' if result.allowed else 'DENIED ❌'}")
    print(f"  ⏱️  Resolved in {elapsed:.1f}s (manager approved after ~4s)")
    
    test1_pass = result.allowed and elapsed < 10

    # ─── TEST 2: Headless Denial via Webhook ──────────────────
    print("\n📋 TEST 2: Headless Agent → Webhook → Manager Denies")
    print("-" * 70)
    
    mock_provider2 = MockWebhookProvider()
    interceptor2 = MCPInterceptor(policy, webhook_provider=mock_provider2, verbose=True)
    interceptor2._is_interactive = lambda: False
    
    manager_thread2 = simulate_manager_denial(interceptor2.storage, mock_provider2, delay=3)
    
    start2 = time.time()
    result2 = interceptor2.intercept("shutdown_server", {"force": True})
    elapsed2 = time.time() - start2
    
    manager_thread2.join()
    
    assert not result2.allowed, "Expected DENIED but got ALLOWED!"
    print(f"\n  🎯 Result: {'ALLOWED ✅' if result2.allowed else 'DENIED ❌'}")
    print(f"  ⏱️  Resolved in {elapsed2:.1f}s (manager denied after ~3s)")
    
    test2_pass = not result2.allowed and elapsed2 < 8

    # ─── TEST 3: No Webhook Provider (Legacy Fail-Close) ─────
    print("\n📋 TEST 3: Headless Agent → No Webhook → Fail-Close")
    print("-" * 70)
    
    interceptor3 = MCPInterceptor(policy, verbose=True)
    interceptor3._is_interactive = lambda: False
    
    result3 = interceptor3.intercept("shutdown_server", {"force": True})
    
    print(f"\n  🎯 Result: {'ALLOWED ✅' if result3.allowed else 'DENIED ❌ (Fail-Close)'}")
    
    test3_pass = not result3.allowed

    # ─── TEST 4: Interactive Terminal (Original Behavior) ─────
    print("\n📋 TEST 4: Interactive Terminal → Standard stdin prompt")
    print("-" * 70)
    
    mock_provider4 = MockWebhookProvider()
    interceptor4 = MCPInterceptor(policy, webhook_provider=mock_provider4, verbose=True)
    interceptor4._is_interactive = lambda: True
    
    # Force a "no" response by overriding input via thread timeout
    interceptor4._request_approval = lambda t, a, tier, to: False
    result4 = interceptor4.intercept("shutdown_server", {"force": True})
    
    print(f"\n  🎯 Result: {'ALLOWED ✅' if result4.allowed else 'DENIED ❌ (user said no)'}")
    # Webhook should NOT have been called since terminal was available
    assert not mock_provider4.sent, "Webhook was fired when terminal was available!"
    
    test4_pass = not result4.allowed and not mock_provider4.sent

    # ─── Final Report ─────────────────────────────────────────
    print("\n" + "=" * 70)
    tests = [
        ("Headless → Webhook → Approve", test1_pass),
        ("Headless → Webhook → Deny", test2_pass),
        ("Headless → No Webhook → Fail-Close", test3_pass),
        ("Interactive → stdin (no webhook fired)", test4_pass),
    ]
    
    all_pass = True
    for name, passed in tests:
        icon = "✅" if passed else "❌"
        print(f"  {icon} {name}")
        if not passed:
            all_pass = False
    
    total = sum(1 for _, p in tests if p)
    print(f"\n  Score: {total}/{len(tests)}")
    
    if all_pass:
        print("\n  🏆 PERFECT SCORE: Webhook Approval Engine is PRODUCTION-READY.")
    else:
        print("\n  ⚠️  Some tests failed. Review above output.")
    
    print("=" * 70)
    sys.exit(0 if all_pass else 1)
