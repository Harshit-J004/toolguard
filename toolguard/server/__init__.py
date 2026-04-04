"""
ToolGuard Server Package.

Provides:
  - create_app: Full FastAPI application factory
  - create_approval_router: Webhook approval routes
  - create_intercept_router: HTTP proxy sidecar routes
"""

from toolguard.server.routes import create_app, create_approval_router, create_intercept_router
