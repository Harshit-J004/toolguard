import json
import time
import functools
import logging
from typing import Optional

try:
    import redis
except ImportError:
    redis = None

from toolguard.core.storage.base import StorageBackend
from toolguard.core.drift import SchemaFingerprint

logger = logging.getLogger("toolguard.storage.redis")


def _retry_on_transient(max_retries: int = 3, base_delay: float = 0.1):
    """Zero-dependency retry decorator for transient Redis errors.
    
    Uses exponential backoff: 0.1s -> 0.2s -> 0.4s.
    Only retries on ConnectionError / TimeoutError.
    Fatal errors (AuthenticationError, etc.) propagate immediately.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except redis.exceptions.AuthenticationError:
                    # AuthenticationError inherits from ConnectionError.
                    # We must catch it explicitly and fail-fast without retrying.
                    raise
                except (redis.exceptions.ConnectionError, 
                        redis.exceptions.TimeoutError,
                        redis.exceptions.BusyLoadingError) as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"Redis transient error (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
            # Exhausted retries - re-raise so the interceptor can fail-close
            raise last_exc
        return wrapper
    return decorator


class RedisStorageBackend(StorageBackend):
    """
    Ultra-high performance distributed Redis backend.
    Enforces true global capacity across multi-node swarms.
    Requires `redis` pip package.
    """
    
    def __init__(self, connection_url: str):
        if redis is None:
            raise ImportError("The 'redis' package is required for the Enterprise Redis Backend. Run: pip install toolguard[enterprise] or pip install redis")
            
        self.client = redis.Redis.from_url(
            connection_url, 
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=3,
            retry_on_timeout=True,
        )
        self.PREFIX = "toolguard:"

    # -- Interface Implementations --

    @_retry_on_transient()
    def check_and_increment_rate_limit(self, tool_name: str, limit: int, window: int) -> bool:
        name = tool_name.strip().casefold()
        key = f"{self.PREFIX}rate_limit:{name}"
        
        # We use a simple counter with an expiration. 
        # A more precise sliding window could use ZADD, but INCR is fiercely fast and atomic.
        pipeline = self.client.pipeline()
        pipeline.incr(key)
        # Only set EXPIRE if it's the very first hit in this window
        pipeline.ttl(key)
        
        results = pipeline.execute()
        count = results[0]
        ttl = results[1]
        
        if ttl == -1: # No TTL was set somehow
            self.client.expire(key, window)
            
        if count > limit:
            return False
            
        return True

    @_retry_on_transient()
    def cache_approval(self, tool_name: str, ttl: int) -> None:
        if ttl <= 0:
            return
        name = tool_name.strip().casefold()
        key = f"{self.PREFIX}approval_cache:{name}"
        self.client.setex(key, ttl, "APPROVED")

    @_retry_on_transient()
    def check_approval(self, tool_name: str) -> bool:
        name = tool_name.strip().casefold()
        key = f"{self.PREFIX}approval_cache:{name}"
        return self.client.exists(key) > 0

    @_retry_on_transient()
    def clear_approval_cache(self) -> None:
        # SCAN and purge all approval keys
        cursor = 0
        while True:
            cursor, keys = self.client.scan(cursor, match=f"{self.PREFIX}approval_cache:*")
            if keys:
                self.client.delete(*keys)
            if cursor == 0:
                break

    # -- Execution Grants --
    @_retry_on_transient()
    def create_execution_grant(self, grant_id: str, payload: str, expires_in: int) -> None:
        key = f"{self.PREFIX}grant:{grant_id}"
        self.client.hset(key, mapping={"status": "PENDING", "payload": payload})
        self.client.expire(key, expires_in)

    @_retry_on_transient()
    def check_grant_status(self, grant_id: str) -> Optional[str]:
        key = f"{self.PREFIX}grant:{grant_id}"
        status = self.client.hget(key, "status")
        return status if status else None

    @_retry_on_transient()
    def resolve_execution_grant(self, grant_id: str, status: str) -> bool:
        key = f"{self.PREFIX}grant:{grant_id}"
        
        # Watch the key to prevent race conditions during the check-and-set
        with self.client.pipeline() as pipe:
            try:
                pipe.watch(key)
                current_status = pipe.hget(key, "status")
                if current_status == "PENDING":
                    pipe.multi()
                    pipe.hset(key, "status", status)
                    pipe.execute()
                    return True
                return False
            except redis.WatchError:
                return False

    @_retry_on_transient()
    def save_fingerprint(self, fingerprint: SchemaFingerprint) -> None:
        name = fingerprint.tool_name.strip().casefold()
        key = f"{self.PREFIX}fingerprint:{name}"
        payload = {
            "tool_name": fingerprint.tool_name,
            "prompt": fingerprint.prompt,
            "model": fingerprint.model,
            "timestamp": fingerprint.timestamp,
            "json_schema": json.dumps(fingerprint.json_schema),
            "sample_output": json.dumps(fingerprint.sample_output, default=str),
            "checksum": fingerprint.checksum
        }
        self.client.hset(key, mapping=payload)

    @_retry_on_transient()
    def get_fingerprint(self, tool_name: str) -> Optional[SchemaFingerprint]:
        name = tool_name.strip().casefold()
        key = f"{self.PREFIX}fingerprint:{name}"
        
        data = self.client.hgetall(key)
        if not data:
            return None
            
        return SchemaFingerprint(
            tool_name=data["tool_name"],
            prompt=data["prompt"],
            model=data["model"],
            timestamp=data["timestamp"],
            json_schema=json.loads(data["json_schema"]),
            sample_output=json.loads(data["sample_output"]),
            checksum=data["checksum"],
        )
