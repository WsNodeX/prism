"""Data model for chat messages, completions, tools and usage accounting."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .jsonx import extract_json


class Role:
    """Canonical chat roles used across providers."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ChatMessage:
    """A single message in a conversation."""

    role: str
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List["ToolCall"]] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name is not None:
            d["name"] = self.name
        if self.tool_calls is not None:
            d["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChatMessage":
        tcs = d.get("tool_calls")
        tool_calls = [ToolCall.from_dict(t) for t in tcs] if tcs else None
        return cls(
            role=d["role"],
            content=d.get("content") or "",
            name=d.get("name"),
            tool_calls=tool_calls,
            tool_call_id=d.get("tool_call_id"),
        )


@dataclass
class ToolCall:
    """A request from the model to invoke a tool/function."""

    id: str
    name: str
    arguments: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments, ensure_ascii=False),
            },
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ToolCall":
        fn = d.get("function", d)
        raw = fn.get("arguments", "{}")
        if isinstance(raw, dict):
            args: Dict[str, Any] = raw
        else:
            args = _parse_arguments(raw)
        return cls(id=d.get("id", ""), name=fn.get("name", ""), arguments=args)


def _parse_arguments(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return extract_json(raw) or {}


@dataclass
class Usage:
    """Token and cost accounting for a single completion."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.prompt_tokens + other.prompt_tokens,
            self.completion_tokens + other.completion_tokens,
            self.total_tokens + other.total_tokens,
            self.cost_usd + other.cost_usd,
        )


@dataclass
class Tool:
    """Declarative description of a callable tool exposed to the model."""

    name: str
    description: str
    parameters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class Completion:
    """The result of a model completion request."""

    id: str
    model: str
    choices: List[ChatMessage]
    usage: Usage
    provider: str
    raw: Dict[str, Any] = field(default_factory=dict)
    cached: bool = False

    @property
    def message(self) -> ChatMessage:
        return self.choices[0] if self.choices else ChatMessage(Role.ASSISTANT, "")


def system(text: str) -> ChatMessage:
    return ChatMessage(Role.SYSTEM, text)


def user(text: str) -> ChatMessage:
    return ChatMessage(Role.USER, text)


def assistant(text: str, tool_calls: Optional[List[ToolCall]] = None) -> ChatMessage:
    return ChatMessage(Role.ASSISTANT, text, tool_calls=tool_calls)


def tool_result(tool_call_id: str, content: str, name: Optional[str] = None) -> ChatMessage:
    return ChatMessage(Role.TOOL, content, tool_call_id=tool_call_id, name=name)
