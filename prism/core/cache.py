"""Response caching: an LRU store and a deterministic semantic cache.

The ``SemanticCache`` keys on a normalized view of (messages, model, tools),
so semantically identical requests hit the same entry. An optional TTL expires
stale entries, which is useful for fast-moving data.
"""

from __future__ import annotations

import json
import time
from typing import Dict, Optional

from .types import ChatMessage, Completion, Tool


class LRUCache:
    def __init__(self, maxsize: int = 128):
        self.maxsize = maxsize
        self._store: Dict[str, object] = {}
        self._order: list = []

    def _touch(self, k: str) -> None:
        if k in self._order:
            self._order.remove(k)
        self._order.append(k)

    def get(self, k: str):
        if k in self._store:
            self._touch(k)
            return self._store[k]
        return None

    def put(self, k: str, v: object) -> None:
        if k in self._store:
            self._touch(k)
        else:
            self._order.append(k)
        self._store[k] = v
        while len(self._order) > self.maxsize:
            old = self._order.pop(0)
            self._store.pop(old, None)

    def pop(self, k: str) -> None:
        if k in self._store:
            self._order.remove(k)
            del self._store[k]

    def contains(self, k: str) -> bool:
        return k in self._store

    def __len__(self) -> int:
        return len(self._store)


def _normalize(messages, model, tools) -> str:
    msgs = [m.to_dict() for m in messages]
    ttools = [t.to_dict() for t in tools] if tools else []
    return json.dumps(
        {"m": msgs, "model": model, "tools": ttools},
        sort_keys=True,
        ensure_ascii=False,
    )


class SemanticCache:
    def __init__(self, maxsize: int = 256, ttl: Optional[float] = None):
        self.lru = LRUCache(maxsize)
        self.ttl = ttl
        self._ts: Dict[str, float] = {}
        self.hits = 0
        self.misses = 0

    def key(self, messages, model, tools) -> str:
        return _normalize(messages, model, tools)

    def get(self, messages, model, tools):
        k = self.key(messages, model, tools)
        if not self.lru.contains(k):
            self.misses += 1
            return None
        if self.ttl is not None:
            if time.time() - self._ts.get(k, 0) > self.ttl:
                self.lru.pop(k)
                self._ts.pop(k, None)
                self.misses += 1
                return None
        self.hits += 1
        return self.lru.get(k)

    def put(self, messages, model, tools, completion) -> None:
        k = self.key(messages, model, tools)
        self.lru.put(k, completion)
        self._ts[k] = time.time()

    def stats(self) -> Dict[str, object]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": (self.hits / total) if total else 0.0,
        }
