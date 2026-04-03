"""
toolguard.mcp.policy
~~~~~~~~~~~~~~~~~~~~
YAML-based security policy engine for MCP tool calls.

Defines per-tool rules: risk tiers (1-4), rate limits, blocked tools,
and injection scanning toggles. Supports a `defaults` block
that applies to any tool not explicitly configured.

Risk Tier Definitions:
  Tier 1 (Standard):   Auto-approve. Full trace logging.
  Tier 2 (Restricted): Human approval required. Configurable timeout + approval caching.
  Tier 3 (Critical):   Human double-confirm (must type tool name). No caching.
  Tier 4 (Forbidden):  Always denied. No override possible.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


# Valid risk tier range
_MIN_TIER = 1
_MAX_TIER = 4


def _clamp_tier(value: int) -> int:
    """Clamp risk_tier to valid range [1, 4]. Unknown high = Forbidden (fail-safe)."""
    return max(_MIN_TIER, min(_MAX_TIER, value))


@dataclass
class ToolPolicy:
    """Security policy for a single MCP tool.

    Risk Tiers:
        1 = Standard   (auto-approve)
        2 = Restricted  (human approval, configurable timeout + caching)
        3 = Critical    (human double-confirm, must type tool name)
        4 = Forbidden   (always deny, no override)
    """
    risk_tier: int = 1
    rate_limit: int = 50          # calls per minute
    blocked: bool = False
    scan_injection: bool = True
    constraints: list[dict] = field(default_factory=list)  # Semantic constraints
    approval_timeout: int = 30    # Seconds before auto-deny (Tier 2+). 0 = wait forever.
    approval_ttl: int = 0         # Seconds to cache approval (Tier 2 only). 0 = ask every time.


@dataclass
class MCPPolicy:
    """Complete security policy for an MCP proxy session.
    
    Load from a YAML dict or use sensible defaults:
    
        policy = MCPPolicy.from_yaml_dict({"defaults": {"risk_tier": 1}, "tools": {...}})
        
    Or use zero-config defaults:
    
        policy = MCPPolicy.default()
    """

    tools: dict[str, ToolPolicy] = field(default_factory=dict)
    defaults: ToolPolicy = field(default_factory=ToolPolicy)
    auto_approve: bool = field(default=False)
    
    def __post_init__(self):
        # Honor the TOOLGUARD_AUTO_APPROVE environment variable
        if os.environ.get("TOOLGUARD_AUTO_APPROVE", "") == "1":
            self.auto_approve = True

    def get_tool_policy(self, tool_name: str) -> ToolPolicy:
        """Get the policy for a specific tool, falling back to defaults.
        
        Hardened: Automatically normalizes tool names (case-insensitive & stripped)
        to prevent casing bypasses.
        """
        name = tool_name.strip().casefold()
        return self.tools.get(name, self.defaults)

    def is_blocked(self, tool_name: str) -> bool:
        return self.get_tool_policy(tool_name).blocked

    def get_risk_tier(self, tool_name: str) -> int:
        return self.get_tool_policy(tool_name).risk_tier

    def get_rate_limit(self, tool_name: str) -> int:
        return self.get_tool_policy(tool_name).rate_limit

    def should_scan_injection(self, tool_name: str) -> bool:
        return self.get_tool_policy(tool_name).scan_injection

    @classmethod
    def default(cls) -> MCPPolicy:
        """Create a zero-config policy that scans everything at tier-1."""
        return cls()

    @classmethod
    def from_yaml_dict(cls, data: dict[str, Any]) -> MCPPolicy:
        """Parse a policy from a YAML-loaded dictionary.
        
        Expected format:
            defaults:
              risk_tier: 1
              rate_limit: 50
              scan_injection: true
              approval_timeout: 30
              approval_ttl: 0
            tools:
              delete_file:
                risk_tier: 2
                rate_limit: 5
                approval_ttl: 300
              execute_code:
                blocked: true
              shutdown_server:
                risk_tier: 3
              nuclear_launch:
                risk_tier: 4
        """
        defaults_data = data.get("defaults", {})
        defaults = ToolPolicy(
            risk_tier=_clamp_tier(defaults_data.get("risk_tier", 1)),
            rate_limit=defaults_data.get("rate_limit", 50),
            blocked=defaults_data.get("blocked", False),
            scan_injection=defaults_data.get("scan_injection", True),
            approval_timeout=defaults_data.get("approval_timeout", 30),
            approval_ttl=defaults_data.get("approval_ttl", 0),
        )

        tools = {}
        for tool_name, tool_data in data.get("tools", {}).items():
            # Hardened: Store normalized names to prevent protocol spoofing
            name = tool_name.strip().casefold()
            tools[name] = ToolPolicy(
                risk_tier=_clamp_tier(tool_data.get("risk_tier", defaults.risk_tier)),
                rate_limit=tool_data.get("rate_limit", defaults.rate_limit),
                blocked=tool_data.get("blocked", defaults.blocked),
                scan_injection=tool_data.get("scan_injection", defaults.scan_injection),
                constraints=tool_data.get("constraints", []),
                approval_timeout=tool_data.get("approval_timeout", defaults.approval_timeout),
                approval_ttl=tool_data.get("approval_ttl", defaults.approval_ttl),
            )

        return cls(tools=tools, defaults=defaults)

    @classmethod
    def from_yaml_file(cls, path: str) -> MCPPolicy:
        """Load a policy from a YAML file on disk."""
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for loading policy files. "
                "Install it with: pip install pyyaml"
            )
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls.from_yaml_dict(data or {})
