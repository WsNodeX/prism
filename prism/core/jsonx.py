"""Small, dependency-free helpers for robust JSON handling.

The model sometimes wraps JSON in code fences or appends prose around it.
``extract_json`` recovers the first JSON object/array from arbitrary text so
tool-call arguments and structured outputs can be parsed reliably.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> Optional[Any]:
    """Return the first JSON value embedded in ``text``, or ``None``."""
    if not text:
        return None
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    fence = _FENCE.search(text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except Exception:
            pass

    start = None
    opener = None
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            opener = ch
            break
    if start is None:
        return None

    close = "}" if opener == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == opener:
            depth += 1
        elif c == close:
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    return None
    return None


def dumps(obj: Any, **kwargs: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, **kwargs)


def loads(s: str) -> Any:
    return json.loads(s)
