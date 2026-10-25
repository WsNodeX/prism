"""The ``Prism`` facade: compose providers, resilience and observability."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from . import agent as agent_mod
from .breaker import CircuitBreaker
from .cache import SemanticCache
from .errors import ProviderError
from .meter import Meter, Trace
from .providers import Provider
from .retry import RetryPolicy
from .router import Router
from .types import (
    ChatMessage,
    Completion,
    Tool,
    _parse_arguments,
)
from .agent import ToolRegistry, infer_schema


class Prism:
    def __init__(
        self,
        providers: Optional[List[Provider]] = None,
        router: Optional[Router] = None,
        strategy: str = "first",
        cache: Optional[SemanticCache] = None,
        retry: Optional[RetryPolicy] = None,
        breaker: Optional[CircuitBreaker] = None,
        meter: Optional[Meter] = None,
        default_model: Optional[str] = None,
    ):
        self.router = router or Router(providers or [], strategy=strategy)
        if router is None and providers:
            for p in providers:
                self.router.add(p)
        self.cache = cache
        self.retry = retry or RetryPolicy()
        self.breaker = breaker
        self.meter = meter or Meter()
        self.default_model = default_model
        self._tools: Dict[str, Callable] = {}
        self._tool_specs: List[Tool] = []

    @property
    def providers(self) -> List[Provider]:
        return self.router.providers

    def use_cache(self, cache: Optional[SemanticCache] = None) -> SemanticCache:
        self.cache = cache or SemanticCache()
        return self.cache

    def use_retry(self, policy: Optional[RetryPolicy] = None) -> RetryPolicy:
        self.retry = policy or RetryPolicy()
        return self.retry

    def use_breaker(self, breaker: Optional[CircuitBreaker] = None) -> CircuitBreaker:
        self.breaker = breaker or CircuitBreaker()
        return self.breaker

    def register_tool(
        self,
        func: Optional[Callable] = None,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Callable:
        def deco(f: Callable) -> Callable:
            tname = name or f.__name__
            desc = description or (f.__doc__ or tname).strip()
            params = parameters or infer_schema(f)
            spec = Tool(name=tname, description=desc, parameters=params)
            self._tools[tname] = f
            self._tool_specs.append(spec)
            return f

        if func is not None:
            return deco(func)
        return deco

    def tool_specs(self) -> List[Tool]:
        return list(self._tool_specs)

    def build_registry(self) -> ToolRegistry:
        reg = ToolRegistry()
        for name, fn in self._tools.items():
            reg.register(fn, name=name)
        return reg

    def _resolve(self, strategy: Optional[str]) -> Provider:
        return self.router.select(strategy=strategy)

    def chat(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Tool]] = None,
        model: Optional[str] = None,
        strategy: Optional[str] = None,
        use_cache: bool = True,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        model = model or self.default_model
        tools = tools or (self._tool_specs if self._tools else None)

        if stream:
            return self._stream(messages, tools=tools, model=model, strategy=strategy, **kwargs)

        if use_cache and self.cache:
            cached = self.cache.get(messages, model, tools)
            if cached is not None:
                from dataclasses import replace

                cached = replace(cached, cached=True)
                tr = self.meter.span(cached.provider, model or "")
                tr.finish(True, cached.usage)
                self.meter.record(tr, cached=True)
                return cached

        provider = self._resolve(strategy)

        def attempt() -> Completion:
            return provider.complete(messages, tools=tools, model=model, **kwargs)

        tr = self.meter.span(provider.name, model or "")
        try:
            comp = self._with_resilience(attempt, provider.name, model)
        except Exception as e:  # noqa: BLE001
            tr.finish(False, error=str(e))
            self.meter.record(tr)
            raise
        tr.finish(True, comp.usage)
        self.meter.record(tr)
        if self.cache:
            self.cache.put(messages, model, tools, comp)
        return comp

    def _with_resilience(self, attempt: Callable[[], Completion], provider_name: str, model: Optional[str]) -> Completion:
        if self.breaker:
            wrapped = attempt
            fn: Callable[[], Completion] = lambda: self.breaker.call(wrapped)  # noqa: E731
        else:
            fn = attempt
        return self.retry.run(fn)

    def _stream(self, messages, tools=None, model=None, strategy=None, **kwargs):
        provider = self._resolve(strategy)
        yield from provider.stream(messages, tools=tools, model=model, **kwargs)

    def agent(
        self,
        messages: List[ChatMessage],
        *,
        max_iter: int = 5,
        model: Optional[str] = None,
        strategy: Optional[str] = None,
        use_cache: bool = False,
        **kwargs: Any,
    ) -> agent_mod.AgentResult:
        return agent_mod.run_agent(
            self,
            messages,
            max_iter=max_iter,
            model=model,
            strategy=strategy,
            use_cache=use_cache,
            **kwargs,
        )
