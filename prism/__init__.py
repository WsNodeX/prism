"""Prism — a zero-dependency toolkit for building resilient LLM applications.

Prism gives you provider routing, semantic response caching, automatic retries
with jitter, circuit breaking, token/cost metering and a small tool-calling
agent — all on top of the Python standard library, with no third-party
dependencies.
"""

from .core.types import (
    ChatMessage,
    Completion,
    Role,
    Tool,
    ToolCall,
    Usage,
    assistant,
    system,
    tool_result,
    user,
)
from .core.providers import (
    EchoProvider,
    OpenAICompatibleProvider,
    Provider,
    ScriptedProvider,
    parse_sse,
    urllib_transport,
)
from .core.router import Router
from .core.cache import LRUCache, SemanticCache
from .core.retry import RetryExhausted, RetryPolicy, jitter
from .core.breaker import CircuitBreaker
from .core.meter import Meter, Trace
from .core.client import Prism
from .core import agent

__version__ = "1.0.0"

__all__ = [
    "ChatMessage",
    "Completion",
    "Role",
    "Tool",
    "ToolCall",
    "Usage",
    "assistant",
    "system",
    "tool_result",
    "user",
    "EchoProvider",
    "OpenAICompatibleProvider",
    "Provider",
    "ScriptedProvider",
    "parse_sse",
    "urllib_transport",
    "Router",
    "LRUCache",
    "SemanticCache",
    "RetryExhausted",
    "RetryPolicy",
    "jitter",
    "CircuitBreaker",
    "Meter",
    "Trace",
    "Prism",
    "agent",
    "__version__",
]
