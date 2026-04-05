"""
ToolGuard Server — FastAPI Application & Routes.

Provides:
  1. Webhook approval endpoints (GET /toolguard/approve, /deny, /status)
  2. HTTP Proxy Sidecar endpoint (POST /v1/intercept)
  3. Health check (GET /v1/health)

Mount into an existing FastAPI app:

    from toolguard.server import create_app
    app = create_app(policy_path="security.yaml")

Or run standalone:

    toolguard serve --policy security.yaml --port 8080
"""

from __future__ import annotations

import os
import time
import json
from typing import Any, Dict, Optional

try:
    from fastapi import APIRouter, FastAPI, Query, Request, HTTPException, Depends
    from fastapi.responses import HTMLResponse, JSONResponse
    from starlette.concurrency import run_in_threadpool
    from pydantic import BaseModel
except ImportError:
    raise ImportError(
        "FastAPI is required for the ToolGuard Server. "
        "Install with: pip install toolguard[server]"
    )

from toolguard.core.storage.base import StorageBackend
from toolguard.core.storage import create_storage_backend
from toolguard.mcp.policy import MCPPolicy
from toolguard.mcp.interceptor import MCPInterceptor


# ──────────────────────────────────────────────
#  Request / Response Models
# ──────────────────────────────────────────────

class InterceptRequest(BaseModel):
    """The payload from any language's agent."""
    tool_name: str
    arguments: Dict[str, Any] = {}


class InterceptResponse(BaseModel):
    """The security verdict returned to the agent."""
    allowed: bool
    reason: str
    layer: str
    latency_ms: float


# ──────────────────────────────────────────────
#  API Key Authentication Middleware
# ──────────────────────────────────────────────

def create_api_key_dependency(api_key: Optional[str] = None):
    """
    Returns a FastAPI dependency that validates the Bearer token.
    If no api_key is configured, all requests are allowed (local dev mode).
    """
    async def verify_api_key(request: Request):
        if api_key is None:
            return  # No auth required (local dev mode)
        
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or malformed Authorization header. Expected: Bearer <api_key>"
            )
        
        token = auth_header[7:]  # Strip "Bearer "
        if token != api_key:
            raise HTTPException(
                status_code=403,
                detail="Invalid API key. Access denied."
            )
    
    return verify_api_key


# ──────────────────────────────────────────────
#  Approval Router (Webhook Callbacks)
# ──────────────────────────────────────────────

def create_approval_router(storage: StorageBackend) -> APIRouter:
    """
    Factory function that creates a FastAPI APIRouter wired to
    the given StorageBackend. This allows the router to resolve
    execution grants in the same Redis/SQLite instance that
    the interceptor is polling against.
    """
    router = APIRouter(prefix="/toolguard", tags=["ToolGuard Approvals"])

    @router.get("/approve", response_class=HTMLResponse)
    def approve_grant(grant_id: str = Query(..., description="The execution grant UUID")):
        """Approve a pending execution grant."""
        status = storage.check_grant_status(grant_id)
        
        if status is None:
            return _render_page(
                "⏱️ Grant Expired",
                f"Grant <code>{grant_id[:12]}...</code> has expired or does not exist.",
                color="#e74c3c"
            )
        
        if status != "PENDING":
            return _render_page(
                "ℹ️ Already Resolved",
                f"Grant <code>{grant_id[:12]}...</code> was already <b>{status}</b>.",
                color="#3498db"
            )
        
        resolved = storage.resolve_execution_grant(grant_id, "APPROVED")
        if resolved:
            return _render_page(
                "✅ Execution Approved",
                f"Grant <code>{grant_id[:12]}...</code> has been approved.<br>"
                f"The agent will resume execution momentarily.",
                color="#2ecc71"
            )
        
        return _render_page(
            "❌ Resolution Failed",
            "Could not resolve this grant. It may have been resolved by another approver.",
            color="#e74c3c"
        )

    @router.get("/deny", response_class=HTMLResponse)
    def deny_grant(grant_id: str = Query(..., description="The execution grant UUID")):
        """Deny a pending execution grant."""
        status = storage.check_grant_status(grant_id)
        
        if status is None:
            return _render_page(
                "⏱️ Grant Expired",
                f"Grant <code>{grant_id[:12]}...</code> has expired or does not exist.",
                color="#e74c3c"
            )
        
        if status != "PENDING":
            return _render_page(
                "ℹ️ Already Resolved",
                f"Grant <code>{grant_id[:12]}...</code> was already <b>{status}</b>.",
                color="#3498db"
            )
        
        resolved = storage.resolve_execution_grant(grant_id, "DENIED")
        if resolved:
            return _render_page(
                "🛡️ Execution Denied",
                f"Grant <code>{grant_id[:12]}...</code> has been denied.<br>"
                f"The agent's tool call has been blocked.",
                color="#e74c3c"
            )
        
        return _render_page(
            "❌ Resolution Failed",
            "Could not resolve this grant. It may have been resolved by another approver.",
            color="#e74c3c"
        )

    @router.get("/status")
    def grant_status(grant_id: str = Query(...)):
        """Check the current status of a grant (JSON API)."""
        status = storage.check_grant_status(grant_id)
        return {"grant_id": grant_id, "status": status or "EXPIRED"}

    return router


# ──────────────────────────────────────────────
#  Intercept Router (HTTP Proxy Sidecar)
# ──────────────────────────────────────────────

def create_intercept_router(interceptor: MCPInterceptor, 
                            api_key_dep=None) -> APIRouter:
    """
    Factory function that creates the core HTTP Proxy endpoint.
    This is the entry point for TypeScript, Go, Rust, or any
    language that wants to use ToolGuard's 7-layer security pipeline.
    """
    deps = [Depends(api_key_dep)] if api_key_dep else []
    router = APIRouter(prefix="/v1", tags=["ToolGuard Proxy"], dependencies=deps)

    @router.post("/intercept", response_model=InterceptResponse)
    async def intercept_tool_call(request: InterceptRequest):
        """
        Run the full 7-layer ToolGuard security pipeline on a tool call.
        
        This is the primary endpoint for cross-language agent integration.
        Any application — TypeScript, Go, Rust, Java — can POST a tool call
        and receive a security verdict.
        
        Returns:
            InterceptResponse with allowed/denied status, reason, and layer.
        """
        start = time.perf_counter()
        
        # Offload blocking intercept (which may poll for webhook approval)
        # to a background thread so the event loop stays responsive.
        result = await run_in_threadpool(
            interceptor.intercept, request.tool_name, request.arguments
        )
        
        latency_ms = (time.perf_counter() - start) * 1000
        
        return InterceptResponse(
            allowed=result.allowed,
            reason=result.reason,
            layer=result.layer,
            latency_ms=round(latency_ms, 3)
        )

    @router.get("/health")
    async def health_check():
        """Health check endpoint for Kubernetes liveness probes."""
        return {
            "status": "healthy",
            "service": "toolguard-proxy",
            "timestamp": time.time()
        }

    return router


# ──────────────────────────────────────────────
#  Application Factory
# ──────────────────────────────────────────────

def create_app(policy: MCPPolicy | None = None,
               policy_path: str | None = None,
               storage_url: str | None = None,
               api_key: str | None = None) -> FastAPI:
    """
    Creates a fully configured FastAPI application with all ToolGuard routes.
    
    Args:
        policy: A pre-loaded MCPPolicy object.
        policy_path: Path to a YAML policy file (used if policy is None).
        storage_url: Redis/SQLite connection URL.
        api_key: Optional Bearer token for authentication.
    """
    # Resolve API key from argument or environment variable
    resolved_api_key = api_key or os.environ.get("TOOLGUARD_API_KEY")
    
    # Load policy
    if policy is None and policy_path and os.path.exists(policy_path):
        policy = MCPPolicy.from_yaml(policy_path)
    elif policy is None:
        # Default minimal policy (used when no file is mounted in Docker)
        policy = MCPPolicy.from_yaml_dict({
            "defaults": {"risk_tier": 0, "rate_limit": 60},
            "tools": {}
        })
    
    # Create core components
    storage = create_storage_backend(storage_url)
    interceptor = MCPInterceptor(policy, storage_url=storage_url)
    
    # Create auth dependency
    api_key_dep = create_api_key_dependency(resolved_api_key)
    
    # Build FastAPI app
    app = FastAPI(
        title="ToolGuard Proxy",
        description="HTTP Sidecar Proxy for the ToolGuard 7-Layer Security Pipeline. "
                    "Enables any language (TypeScript, Go, Rust, Java) to use ToolGuard.",
        version="6.1.0",
    )
    
    # Mount routers
    app.include_router(create_intercept_router(interceptor, api_key_dep))
    app.include_router(create_approval_router(storage))
    
    @app.get("/")
    async def root():
        return {
            "service": "ToolGuard Proxy",
            "version": "6.1.0",
            "docs": "/docs",
            "intercept": "POST /v1/intercept",
            "health": "GET /v1/health",
            "auth": "Bearer token" if resolved_api_key else "disabled (local dev mode)"
        }
    
    return app


# ──────────────────────────────────────────────
#  Confirmation Page Renderer
# ──────────────────────────────────────────────

def _render_page(title: str, message: str, color: str = "#2ecc71") -> str:
    """Renders a minimal, beautiful confirmation page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ToolGuard — {title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }}
        .card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 48px;
            max-width: 480px;
            text-align: center;
            box-shadow: 0 16px 48px rgba(0,0,0,0.4);
        }}
        h1 {{
            color: {color};
            font-size: 24px;
            margin-bottom: 12px;
        }}
        p {{
            color: #8b949e;
            font-size: 15px;
            line-height: 1.6;
        }}
        code {{
            background: #0d1117;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 13px;
            color: #79c0ff;
        }}
        .badge {{
            display: inline-block;
            margin-top: 24px;
            padding: 6px 16px;
            background: {color}22;
            border: 1px solid {color}44;
            border-radius: 20px;
            font-size: 12px;
            color: {color};
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{title}</h1>
        <p>{message}</p>
        <div class="badge">ToolGuard Security</div>
    </div>
</body>
</html>"""
