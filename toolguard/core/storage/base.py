from abc import ABC, abstractmethod
from typing import Optional

from toolguard.core.drift import SchemaFingerprint

class StorageBackend(ABC):
    """
    Unified storage interface for ToolGuard's memory state.
    Provides methods for distributed rate-limiting, approval caching, and
    schema drift fingerprints. Designed to support massive Kubernetes swarms.
    """

    # -- Rate Limiting --
    @abstractmethod
    def check_and_increment_rate_limit(self, tool_name: str, limit: int, window: int) -> bool:
        """
        Atomically checks if a limit is reached and increments the counter.
        Returns True if the request is ALLOWED (under limit), False if EXCEEDED.
        
        Args:
            tool_name: The tool being called
            limit: Maximum requests allowed in the window
            window: Evaluation window in seconds
        """
        pass

    # -- Approval Cache (L2 Risk Tiers) --
    @abstractmethod
    def cache_approval(self, tool_name: str, ttl: int) -> None:
        """
        Caches human approval for a specific tool.
        
        Args:
            tool_name: The approved tool
            ttl: Time-to-live in seconds
        """
        pass

    @abstractmethod
    def check_approval(self, tool_name: str) -> bool:
        """
        Checks if a valid, unexpired approval exists for the tool.
        Returns True if exists, False otherwise.
        """
        pass

    @abstractmethod
    def clear_approval_cache(self) -> None:
        """
        Instantly purges all human approval caches. Use on policy reloads.
        """
        pass

    # -- Async Execution Grants (Webhook/RBAC) --
    @abstractmethod
    def create_execution_grant(self, grant_id: str, payload: str, expires_in: int) -> None:
        """
        Registers a pending execution grant in the storage layer.
        """
        pass
        
    @abstractmethod
    def check_grant_status(self, grant_id: str) -> Optional[str]:
        """
        Returns the current status of the grant: "PENDING", "APPROVED", "DENIED", or None if expired.
        """
        pass
        
    @abstractmethod
    def resolve_execution_grant(self, grant_id: str, status: str) -> bool:
        """
        Resolves a pending grant to "APPROVED" or "DENIED".
        Returns True if successfully resolved, False if it was not PENDING or not found.
        """
        pass

    # -- Schema Fingerprints (L6 Drift Engine) --
    @abstractmethod
    def save_fingerprint(self, fingerprint: SchemaFingerprint) -> None:
        """
        Upserts a schema fingerprint.
        """
        pass

    @abstractmethod
    def get_fingerprint(self, tool_name: str) -> Optional[SchemaFingerprint]:
        """
        Retrieves the exact schema fingerprint for a tool.
        Returns None if no footprint exists.
        """
        pass
