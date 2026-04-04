import os

from toolguard.core.storage.base import StorageBackend
from toolguard.core.storage.local_backend import LocalStorageBackend
from toolguard.core.storage.redis_backend import RedisStorageBackend

def create_storage_backend(storage_url: str = None) -> StorageBackend:
    """Factory to instantiate the correct storage backend.
    
    Falls back to the TOOLGUARD_STORAGE_URL environment variable if
    no explicit URL is passed. This ensures Docker/K8s deployments
    automatically connect to Redis without code changes.
    """
    resolved_url = storage_url or os.environ.get("TOOLGUARD_STORAGE_URL")
    
    if resolved_url and resolved_url.startswith("redis"):
        return RedisStorageBackend(connection_url=resolved_url)
    
    # Defaults to local fallback if no URL or sqlite/local is specified
    return LocalStorageBackend()
