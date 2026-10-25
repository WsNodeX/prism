"""Provider selection strategies.

A ``Router`` holds one or more providers and decides which one answers a given
request. Strategies include round-robin load balancing, cost- and latency-aware
selection, and capability-based routing (e.g. only providers that support
tools).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from .providers import Provider
from .types import ChatMessage


class Router:
    def __init__(self, providers: Optional[List[Provider]] = None, strategy: str = "first"):
        self.providers: List[Provider] = list(providers or [])
        self.strategy = strategy
        self._rr = 0
        self.meta: Dict[str, dict] = {}

    def set_meta(self, name: str, **kw: object) -> None:
        self.meta[name] = kw

    def add(self, provider: Provider, **meta: object) -> Provider:
        self.providers.append(provider)
        if meta:
            self.set_meta(provider.name, **meta)
        return provider

    def select(
        self,
        messages: Optional[List[ChatMessage]] = None,
        tools: Optional[List[object]] = None,
        strategy: Optional[str] = None,
    ) -> Provider:
        strategy = strategy or self.strategy
        if not self.providers:
            raise ValueError("no providers registered")
        if strategy == "first" or len(self.providers) == 1:
            return self.providers[0]

        if strategy == "round_robin":
            p = self.providers[self._rr % len(self.providers)]
            self._rr += 1
            return p

        if strategy == "lowest_cost":
            return min(self.providers, key=lambda p: self.meta.get(p.name, {}).get("cost_per_1k", 1.0))

        if strategy == "lowest_latency":
            return min(self.providers, key=lambda p: self.meta.get(p.name, {}).get("latency_ms", 1_000_000))

        if strategy == "capability":
            caps: Set[str] = set()
            if tools:
                caps.add("tools")
            for p in self.providers:
                pc = set(self.meta.get(p.name, {}).get("capabilities", []))
                if caps <= pc:
                    return p
            return self.providers[0]

        raise ValueError(f"unknown strategy {strategy}")
