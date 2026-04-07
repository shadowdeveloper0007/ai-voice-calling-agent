from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from typing import Dict, Generic, Optional, Tuple, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(frozen=True)
class _Entry(Generic[V]):
    value: V
    expires_at: float


class TTLCache(Generic[K, V]):
    """Simple in-memory TTL cache (thread-safe)."""

    def __init__(self, ttl_seconds: float = 1800.0, max_items: int = 256) -> None:
        self._ttl = float(ttl_seconds)
        self._max = int(max_items)
        self._lock = RLock()
        self._data: Dict[K, _Entry[V]] = {}

    def get(self, key: K) -> Optional[V]:
        now = time.time()
        with self._lock:
            ent = self._data.get(key)
            if not ent:
                return None
            if ent.expires_at <= now:
                self._data.pop(key, None)
                return None
            return ent.value

    def set(self, key: K, value: V) -> None:
        now = time.time()
        with self._lock:
            # cheap cleanup + cap
            if len(self._data) >= self._max:
                self._purge_expired(now)
                if len(self._data) >= self._max:
                    # drop an arbitrary item (good enough for small cache)
                    self._data.pop(next(iter(self._data)), None)
            self._data[key] = _Entry(value=value, expires_at=now + self._ttl)

    def _purge_expired(self, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        removed = 0
        for k, ent in list(self._data.items()):
            if ent.expires_at <= now:
                self._data.pop(k, None)
                removed += 1
        return removed

