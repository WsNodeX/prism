import unittest

from prism import (
    CircuitBreaker,
    Meter,
    Prism,
    RetryPolicy,
    Router,
    ScriptedProvider,
    SemanticCache,
    user,
)
from prism.core.errors import CircuitOpenError, RetryExhausted, ServerError
from prism.core.providers import Provider
from prism.core.types import Completion, Role, ToolCall, Usage, assistant


class FlakyProvider(Provider):
    def __init__(self):
        self.calls = 0

    @property
    def name(self):
        return "flaky"

    def complete(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise ServerError("boom")
        return Completion("x", "m", [assistant("ok")], Usage(1, 1, 2), "flaky")


class AlwaysFailProvider(Provider):
    @property
    def name(self):
        return "fail"

    def complete(self, messages, **kwargs):
        raise ServerError("always")


class TestClient(unittest.TestCase):
    def test_chat_caches(self):
        prism = Prism(router=Router([ScriptedProvider("s", script=[{"match": ".*", "content": "hi"}])]),
                      cache=SemanticCache())
        a = prism.chat([user("hello")])
        b = prism.chat([user("hello")])
        self.assertFalse(a.cached)
        self.assertTrue(b.cached)
        self.assertEqual(b.message.content, a.message.content)

    def test_register_tool_schema(self):
        prism = Prism(router=Router([ScriptedProvider("s")]))

        @prism.register_tool(description="Multiply.")
        def multiply(a: int, b: int) -> int:
            return a * b

        specs = prism.tool_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].name, "multiply")
        params = specs[0].parameters
        self.assertEqual(params["type"], "object")
        self.assertIn("a", params["properties"])
        self.assertEqual(params["properties"]["a"]["type"], "integer")
        self.assertEqual(params["required"], ["a", "b"])

    def test_retry_integration(self):
        p = FlakyProvider()
        prism = Prism(router=Router([p]), retry=RetryPolicy(attempts=3, sleep=lambda d: None), breaker=None)
        c = prism.chat([user("hi")])
        self.assertEqual(c.message.content, "ok")
        self.assertEqual(p.calls, 2)
        self.assertEqual(prism.meter.totals()["calls"], 1)

    def test_breaker_integration(self):
        p = AlwaysFailProvider()
        prism = Prism(
            router=Router([p]),
            retry=RetryPolicy(attempts=1, sleep=lambda d: None),
            breaker=CircuitBreaker(failure_threshold=1, reset_timeout=1000),
        )
        with self.assertRaises(RetryExhausted) as ctx1:
            prism.chat([user("hi")])
        self.assertIsInstance(ctx1.exception.cause, ServerError)
        self.assertEqual(prism.breaker.state, prism.breaker.OPEN)
        # CircuitOpenError is non-retryable, so it propagates unwrapped.
        with self.assertRaises(CircuitOpenError):
            prism.chat([user("hi")])

    def test_stream_yields_completion(self):
        prism = Prism(router=Router([ScriptedProvider("s", script=[{"match": ".*", "content": "hi"}])]))
        chunks = list(prism.chat([user("hi")], stream=True))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].message.content, "hi")


if __name__ == "__main__":
    unittest.main()
