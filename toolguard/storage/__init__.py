"""
toolguard.storage
~~~~~~~~~~~~~~~~~

Persistent storage for ToolGuard test results using SQLite.
Tracks chain reliability over time for historical analysis.
"""

from toolguard.storage.db import ResultStore

__all__ = ["ResultStore"]
