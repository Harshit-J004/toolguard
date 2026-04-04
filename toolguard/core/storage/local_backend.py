import json
import threading
import time
from pathlib import Path
from typing import Optional

from toolguard.core.storage.base import StorageBackend
from toolguard.core.drift import SchemaFingerprint
from toolguard.core.drift_store import FingerprintStore

class LocalStorageBackend(StorageBackend):
    """
    Zero-config local storage backend using JSON tracking and SQLite.
    Provides in-memory locks for atomic operations locally.
    """
    
    def __init__(self, base_dir: str = ".toolguard"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Rate Limiting State
        self._calls: dict[str, list[float]] = {}
        self._rl_lock = threading.Lock()
        self._rl_cache_file = self.base_dir / "rate_limits.json"
        
        # Approval Cache State (tool_name -> expiry_timestamp)
        self._approval_cache: dict[str, float] = {}
        self._ac_lock = threading.Lock()
        
        # Async Grants State (grant_id -> {"status": str, "payload": str, "expiry": float})
        self._grants: dict[str, dict] = {}
        self._grant_lock = threading.Lock()
        
        # Load local state
        self._fingerprint_store = FingerprintStore(self.base_dir / "drift.db")
        self._load_rl_cache()

    # -- Internal Cache loading --
    def _load_rl_cache(self) -> None:
        try:
            if self._rl_cache_file.exists():
                self._calls = json.loads(self._rl_cache_file.read_text("utf-8"))
        except Exception:
            self._calls = {}

    def _save_rl_cache(self) -> None:
        try:
            self._rl_cache_file.write_text(json.dumps(self._calls), "utf-8")
        except Exception:
            pass

    # -- Interface Implementations --

    def check_and_increment_rate_limit(self, tool_name: str, limit: int, window: int) -> bool:
        name = tool_name.strip().casefold()
        now = time.time()
        window_start = now - window

        with self._rl_lock:
            if name not in self._calls:
                self._calls[name] = []

            # Prune old entries
            self._calls[name] = [t for t in self._calls[name] if t > window_start]

            if len(self._calls[name]) >= limit:
                self._save_rl_cache()
                return False

            self._calls[name].append(now)
            self._save_rl_cache()
            return True

    def cache_approval(self, tool_name: str, ttl: int) -> None:
        if ttl <= 0:
            return
        name = tool_name.strip().casefold()
        with self._ac_lock:
            self._approval_cache[name] = time.time() + ttl

    def check_approval(self, tool_name: str) -> bool:
        name = tool_name.strip().casefold()
        with self._ac_lock:
            expiry = self._approval_cache.get(name)
            if expiry and time.time() < expiry:
                return True
            # Evict if expired
            if name in self._approval_cache:
                del self._approval_cache[name]
        return False

    def clear_approval_cache(self) -> None:
        with self._ac_lock:
            self._approval_cache.clear()

    # -- Execution Grants --
    def create_execution_grant(self, grant_id: str, payload: str, expires_in: int) -> None:
        with self._grant_lock:
            self._grants[grant_id] = {
                "status": "PENDING",
                "payload": payload,
                "expiry": time.time() + expires_in
            }

    def check_grant_status(self, grant_id: str) -> Optional[str]:
        with self._grant_lock:
            grant = self._grants.get(grant_id)
            if not grant:
                return None
            if time.time() > grant["expiry"]:
                del self._grants[grant_id]
                return None
            return grant["status"]

    def resolve_execution_grant(self, grant_id: str, status: str) -> bool:
        with self._grant_lock:
            grant = self._grants.get(grant_id)
            if grant and grant["status"] == "PENDING" and time.time() <= grant["expiry"]:
                grant["status"] = status
                return True
            return False

    def save_fingerprint(self, fingerprint: SchemaFingerprint) -> None:
        self._fingerprint_store.save_fingerprint(fingerprint)

    def get_fingerprint(self, tool_name: str) -> Optional[SchemaFingerprint]:
        # Local SQLite schema retrieval logic
        # For simplicity in the proxy logic, we retrieve the latest active baseline.
        return self._fingerprint_store.get_latest_fingerprint_for_tool(tool_name)
    
    def close(self):
        self._fingerprint_store.close()
