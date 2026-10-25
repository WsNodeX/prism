"""Tool registry and a minimal ReAct-style agent loop.

The agent repeatedly asks the model for a completion; whenever the model emits
tool calls it executes them locally, feeds the results back, and continues
until the model returns a final answer or ``max_iter`` is reached.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional

from .errors import ToolError
from .types import ChatMessage, Role, Tool, ToolCall, tool_result


def _ann_to_json(ann: Any) -> str:
    return {
        int: "integer",
        float: "number",
        str: "string",
        bool: "boolean",
        list: "array",
        dict: "object",
    }.get(ann, "string")


def infer_schema(func: Callable) -> Dict[str, Any]:
    """Build a JSON schema for ``func`` from its signature and annotations."""
    sig = inspect.signature(func)
    props: Dict[str, Any] = {}
    required: List[str] = []
    for pname, p in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        jtype = _ann_to_json(p.annotation)
        props[pname] = {"type": jtype, "description": ""}
        if p.default is inspect.Parameter.empty:
            required.append(pname)
    return {"type": "object", "properties": props, "required": required}


class ToolRegistry:
    def __init__(self):
        self._funcs: Dict[str, Callable] = {}
        self._specs: List[Tool] = []

    def register(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Callable:
        tname = name or func.__name__
        desc = description or (func.__doc__ or tname).strip()
        params = parameters or infer_schema(func)
        self._funcs[tname] = func
        self._specs.append(Tool(name=tname, description=desc, parameters=params))
        return func

    def specs(self) -> List[Tool]:
        return list(self._specs)

    def dispatch(self, call: ToolCall) -> Any:
        fn = self._funcs.get(call.name)
        if fn is None:
            raise ToolError(f"unknown tool {call.name}")
        try:
            return fn(**call.arguments)
        except Exception as e:  # noqa: BLE001
            raise ToolError(f"tool {call.name} failed: {e}") from e


class AgentResult:
    def __init__(self, answer: str, steps: List[tuple], transcript: List[ChatMessage]):
        self.answer = answer
        self.steps = steps
        self.transcript = transcript


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        import json

        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
    except Exception:
        pass
    return str(value)


def run_agent(
    prism,
    messages: List[ChatMessage],
    *,
    max_iter: int = 5,
    model: Optional[str] = None,
    strategy: Optional[str] = None,
    use_cache: bool = False,
    system_prompt: Optional[str] = None,
) -> AgentResult:
    if system_prompt:
        messages = [ChatMessage(Role.SYSTEM, system_prompt)] + list(messages)

    tools = prism.tool_specs()
    registry = prism.build_registry()
    steps: List[tuple] = []
    transcript: List[ChatMessage] = []
    working = list(messages)

    for _ in range(max_iter):
        comp = prism.chat(
            working, tools=tools or None, model=model, strategy=strategy, use_cache=use_cache
        )
        msg = comp.message
        transcript.append(msg)

        if msg.tool_calls:
            working.append(msg)
            for tc in msg.tool_calls:
                try:
                    res = registry.dispatch(tc)
                except ToolError as e:
                    res = f"ERROR: {e}"
                steps.append((tc.name, tc.arguments, res))
                working.append(tool_result(tc.id, _stringify(res), name=tc.name))
        else:
            return AgentResult(msg.content, steps, transcript)

    last = transcript[-1] if transcript else None
    return AgentResult(last.content if last else "", steps, transcript)
