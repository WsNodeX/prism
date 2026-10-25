"""Provider abstraction and concrete providers.

``Provider`` is the only interface Prism depends on. Two offline providers
(``ScriptedProvider`` and ``EchoProvider``) make the whole stack testable and
demoable without network access, while ``OpenAICompatibleProvider`` speaks the
OpenAI Chat Completions protocol over ``urllib`` (no third-party HTTP library).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

from .errors import ProviderError, RateLimitError, ServerError, TimeoutError
from .pricing import estimate
from .types import ChatMessage, Completion, Role, ToolCall, Usage, _parse_arguments

Transport = Callable[[str, str, Dict[str, str], Optional[str]], Tuple[int, str]]


class Provider:
    """Base provider interface."""

    name = "base"

    def complete(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Any]] = None,
        model: Optional[str] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Completion:
        raise NotImplementedError

    def stream(self, messages, tools=None, model=None, **kwargs):
        comp = self.complete(messages, tools=tools, model=model, **kwargs)
        yield comp


def urllib_transport(
    method: str, url: str, headers: Dict[str, str], body: Optional[str]
) -> Tuple[int, str]:
    data = body.encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # network/DNS/SSL failures
        raise TimeoutError(f"transport error: {e}") from e


def parse_sse(text: str):
    """Yield JSON objects from a Server-Sent-Events stream body."""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            return
        try:
            yield json.loads(data)
        except Exception:
            continue


class OpenAICompatibleProvider(Provider):
    """Talks to any OpenAI-compatible ``/chat/completions`` endpoint."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        transport: Optional[Transport] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.transport = transport or urllib_transport
        self.extra_headers = extra_headers or {}

    @property
    def name(self) -> str:
        return f"openai:{self.model}"

    def _headers(self) -> Dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        h.update(self.extra_headers)
        return h

    def complete(self, messages, tools=None, model=None, stream=False, **kwargs):
        model = model or self.model
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
        }
        if tools:
            payload["tools"] = [t.to_dict() for t in tools]
        for k in ("temperature", "top_p", "max_tokens", "n", "stop"):
            if k in kwargs:
                payload[k] = kwargs[k]
        body = json.dumps(payload, ensure_ascii=False)
        status, text = self.transport(
            "POST", f"{self.base_url}/chat/completions", self._headers(), body
        )
        if status == 429:
            raise RateLimitError("rate limited", status=status, provider=self.name)
        if status >= 500:
            raise ServerError(f"server error {status}", status=status, provider=self.name)
        if status != 200:
            raise ProviderError(
                f"unexpected status {status}: {text[:200]}",
                status=status,
                provider=self.name,
            )
        return self._to_completion(json.loads(text), model)

    def _to_completion(self, data: Dict[str, Any], model: str) -> Completion:
        choices: List[ChatMessage] = []
        for c in data.get("choices", []):
            msg = c.get("message", {})
            tcs = msg.get("tool_calls")
            tool_calls = [ToolCall.from_dict(t) for t in tcs] if tcs else None
            choices.append(
                ChatMessage(
                    role=msg.get("role", Role.ASSISTANT),
                    content=msg.get("content") or "",
                    tool_calls=tool_calls,
                )
            )
        u = data.get("usage", {})
        usage = Usage(
            prompt_tokens=u.get("prompt_tokens", 0),
            completion_tokens=u.get("completion_tokens", 0),
            total_tokens=u.get("total_tokens", 0),
        )
        usage.cost_usd = estimate(model, usage.prompt_tokens, usage.completion_tokens)
        return Completion(
            id=data.get("id", "cmpl"),
            model=model,
            choices=choices,
            usage=usage,
            provider=self.name,
            raw=data,
        )

    def stream(self, messages, tools=None, model=None, **kwargs):
        model = model or self.model
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "stream": True,
        }
        if tools:
            payload["tools"] = [t.to_dict() for t in tools]
        body = json.dumps(payload, ensure_ascii=False)
        status, text = self.transport(
            "POST", f"{self.base_url}/chat/completions", self._headers(), body
        )
        if status != 200:
            raise ProviderError(
                f"stream status {status}", status=status, provider=self.name
            )
        for chunk in parse_sse(text):
            yield chunk


class ScriptedProvider(Provider):
    """Deterministic offline provider driven by a list of rules.

    Each rule may match on the last user message (``match`` regex), on the
    presence of a tool result (``after_tool``), or act as a fallback (no keys).
    A rule can return plain content or emit a ``tool_call`` to exercise the
    agent loop end-to-end without any network.
    """

    def __init__(self, name: str = "scripted", script: Optional[List[Dict[str, Any]]] = None):
        self._name = name
        self.script = script or []

    @property
    def name(self) -> str:
        return self._name

    def complete(self, messages, tools=None, model=None, **kwargs) -> Completion:
        last_user = ""
        last_role = None
        for m in messages:
            if m.role == Role.USER:
                last_user = m.content
            last_role = m.role

        # Pass 1: after a tool result, prefer an after_tool rule first so the
        # original user prompt (still present) does not re-trigger an earlier
        # tool-call rule and loop the agent forever.
        if last_role == Role.TOOL:
            for rule in self.script:
                if rule.get("after_tool"):
                    return self._build(rule, model)

        # Pass 2: regular match / fallback rules.
        for rule in self.script:
            if rule.get("after_tool"):
                continue
            pattern = rule.get("match")
            if pattern is None:
                return self._build(rule, model)
            if re.search(pattern, last_user):
                return self._build(rule, model)

        return Completion(
            id="scr",
            model=model or "scripted-1",
            choices=[ChatMessage(Role.ASSISTANT, f"(no script) {last_user}")],
            usage=Usage(3, 3, 6),
            provider=self._name,
        )

    def _build(self, rule: Dict[str, Any], model: Optional[str]) -> Completion:
        content = rule.get("content", "")
        tool_calls = None
        if "tool_call" in rule:
            tc = rule["tool_call"]
            tool_calls = [
                ToolCall(
                    id=tc.get("id", "call_1"),
                    name=tc["name"],
                    arguments=tc.get("arguments", {}),
                )
            ]
        usage_data = rule.get("usage", {"prompt_tokens": 4, "completion_tokens": 4, "total_tokens": 8})
        usage = Usage(**usage_data)
        return Completion(
            id=rule.get("id", "scr"),
            model=model or rule.get("model", "scripted-1"),
            choices=[ChatMessage(Role.ASSISTANT, content, tool_calls=tool_calls)],
            usage=usage,
            provider=self._name,
            raw={"finish_reason": rule.get("finish_reason", "stop")},
        )


class EchoProvider(Provider):
    """Returns the conversation back — handy for smoke tests."""

    def __init__(self, name: str = "echo", model: str = "echo-1"):
        self._name = name
        self.model = model

    @property
    def name(self) -> str:
        return self._name

    def complete(self, messages, tools=None, model=None, **kwargs) -> Completion:
        convo = " | ".join(f"{m.role}: {m.content}" for m in messages)
        tokens = max(1, len(convo) // 4)
        return Completion(
            id="echo",
            model=model or self.model,
            choices=[ChatMessage(Role.ASSISTANT, f"echo: {convo}")],
            usage=Usage(tokens, tokens, tokens * 2),
            provider=self._name,
        )
