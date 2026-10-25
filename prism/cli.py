"""Command-line entry point for Prism (offline demonstration mode)."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import (
    CircuitBreaker,
    Meter,
    Prism,
    RetryPolicy,
    Router,
    ScriptedProvider,
    SemanticCache,
    user,
)


def _build_demo() -> Prism:
    p1 = ScriptedProvider(
        "mock-gpt",
        script=[
            {
                "match": "weather|temperature|rain",
                "content": "It is sunny, 24°C, no rain expected.",
                "usage": {"prompt_tokens": 6, "completion_tokens": 8, "total_tokens": 14},
            }
        ],
    )
    p2 = ScriptedProvider(
        "mock-claude",
        script=[
            {
                "match": "weather|temperature|rain",
                "content": "Clear skies, around 24 degrees, dry.",
                "usage": {"prompt_tokens": 6, "completion_tokens": 9, "total_tokens": 15},
            }
        ],
    )
    router = Router([p1, p2], strategy="round_robin")
    return Prism(
        router=router,
        cache=SemanticCache(),
        retry=RetryPolicy(attempts=2),
        breaker=CircuitBreaker(),
        meter=Meter(),
    )


def run_demo(message: str) -> int:
    prism = _build_demo()
    msgs = [user(message)]
    c1 = prism.chat(msgs)
    c2 = prism.chat(msgs)
    print(f"provider : {c1.provider}")
    print(f"answer   : {c1.message.content}")
    print(f"cached   : {c2.cached}")
    print(f"meter    : {prism.meter.totals()}")
    print(f"cache    : {prism.cache.stats()}")

    @prism.register_tool(description="Multiply two integers.")
    def multiply(a: int, b: int) -> int:
        return a * b

    agent_prism = Prism(
        router=Router(
            [
                ScriptedProvider(
                    "agent-provider",
                    script=[
                        {
                            "match": r"7\s*(times|x|\*)\s*5|7\s*乘\s*5",
                            "tool_call": {"id": "c1", "name": "multiply", "arguments": {"a": 7, "b": 5}},
                            "content": "",
                        },
                        {
                            "after_tool": True,
                            "content": "The product is 35.",
                            "usage": {"prompt_tokens": 4, "completion_tokens": 4, "total_tokens": 8},
                        },
                    ],
                )
            ],
            strategy="first",
        ),
        cache=None,
    )
    agent_prism.register_tool(multiply)
    res = agent_prism.agent([user("What is 7 times 5?")], max_iter=4)
    print(f"agent    : {res.answer}")
    print(f"steps    : {res.steps}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="prism", description="Prism LLM resilience toolkit (offline demo mode)."
    )
    sub = parser.add_subparsers(dest="cmd")
    demo = sub.add_parser("demo", help="Run the offline demonstration.")
    demo.add_argument("--message", default="What is the weather today?")
    args = parser.parse_args(argv)

    if args.cmd == "demo":
        return run_demo(args.message)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
