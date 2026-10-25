"""Observability: per-call traces and aggregate token/cost accounting."""

from __future__ import annotations

import time
from typing import List, Optional

from .types import Usage


class Trace:
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.start = time.time()
        self.end = 0.0
        self.latency = 0.0
        self.ok = False
        self.error: Optional[str] = None
        self.usage: Optional[Usage] = None

    def finish(self, ok: bool, usage: Optional[Usage] = None, error: Optional[str] = None) -> None:
        self.end = time.time()
        self.latency = self.end - self.start
        self.ok = ok
        self.error = error
        self.usage = usage


class Meter:
    def __init__(self):
        self.traces: List[Trace] = []
        self.total_prompt = 0
        self.total_completion = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.calls = 0
        self.errors = 0
        self.cached_hits = 0

    def span(self, provider: str, model: str) -> Trace:
        t = Trace(provider, model)
        self.traces.append(t)
        return t

    def record(self, trace: Trace, cached: bool = False) -> None:
        self.calls += 1
        if cached:
            self.cached_hits += 1
        if not trace.ok:
            self.errors += 1
        if trace.usage:
            self.total_prompt += trace.usage.prompt_tokens
            self.total_completion += trace.usage.completion_tokens
            self.total_tokens += trace.usage.total_tokens
            self.total_cost += trace.usage.cost_usd

    def totals(self) -> dict:
        return {
            "calls": self.calls,
            "errors": self.errors,
            "prompt_tokens": self.total_prompt,
            "completion_tokens": self.total_completion,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.total_cost, 6),
            "cached_hits": self.cached_hits,
            "hit_rate": (self.cached_hits / self.calls) if self.calls else 0.0,
        }
