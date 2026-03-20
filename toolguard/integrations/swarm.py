"""
toolguard.integrations.swarm
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integration for OpenAI Swarm Agents.
Allows automatic extraction and fuzzing of all tools assigned to a Swarm Agent.
"""

from __future__ import annotations

from typing import Any

from toolguard.core.validator import GuardedTool, create_tool


def guard_swarm_agent(agent: Any) -> list[GuardedTool]:
    """Extract and wrap all functions from an OpenAI Swarm Agent.
    
    Args:
        agent: An instance of `swarm.Agent`.
        
    Returns:
        A list of GuardedTool instances representing the agent's full tool stack,
        ready to be passed directly into `test_chain`.
    """
    if not hasattr(agent, "functions"):
        raise TypeError(f"Expected an OpenAI Swarm Agent (with a .functions list), got {type(agent)}")
        
    guarded_tools = []
    
    for func in agent.functions:
        if isinstance(func, GuardedTool):
            guarded_tools.append(func)
        else:
            guarded_tools.append(create_tool(schema="auto")(func))
            
    return guarded_tools
