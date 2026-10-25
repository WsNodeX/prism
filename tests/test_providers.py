import json
import unittest

from prism.core.errors import ProviderError, RateLimitError, ServerError
from prism.core.providers import (
    EchoProvider,
    OpenAICompatibleProvider,
    ScriptedProvider,
    parse_sse,
)
from prism.core.types import ChatMessage, Completion, Role, ToolCall, Usage, assistant, user


def fake_transport(method, url, headers, body):
    payload = json.loads(body)
    data = {
        "id": "x",
        "model": payload["model"],
        "choices": [{"message": {"role": "assistant", "content": "hi"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    return (200, json.dumps(data))


def status_transport(code):
    def transport(method, url, headers, body):
        return (code, json.dumps({"error": "x"}))

    return transport


class TestOpenAIProvider(unittest.TestCase):
    def test_to_completion(self):
        p = OpenAICompatibleProvider(api_key="k", model="gpt-4o-mini", transport=fake_transport)
        c = p.complete([user("hi")])
        self.assertIsInstance(c, Completion)
        self.assertEqual(c.message.content, "hi")
        self.assertEqual(c.provider, "openai:gpt-4o-mini")

    def test_tools_in_payload(self):
        captured = {}

        def t(method, url, headers, body):
            captured["body"] = json.loads(body)
            return fake_transport(method, url, headers, body)

        p = OpenAICompatibleProvider(api_key="k", transport=t)
        tool = type("_T", (), {})()
        tool.to_dict = lambda: {"type": "function", "function": {"name": "f"}}
        p.complete([user("hi")], tools=[tool])
        self.assertIn("tools", captured["body"])

    def test_rate_limit(self):
        p = OpenAICompatibleProvider(api_key="k", transport=status_transport(429))
        with self.assertRaises(RateLimitError):
            p.complete([user("hi")])

    def test_server_error(self):
        p = OpenAICompatibleProvider(api_key="k", transport=status_transport(503))
        with self.assertRaises(ServerError):
            p.complete([user("hi")])

    def test_unexpected_status(self):
        p = OpenAICompatibleProvider(api_key="k", transport=status_transport(401))
        with self.assertRaises(ProviderError):
            p.complete([user("hi")])

    def test_parse_sse(self):
        sse = "data: {\"x\":1}\n\ndata: {\"x\":2}\n\ndata: [DONE]\n"
        out = list(parse_sse(sse))
        self.assertEqual(out, [{"x": 1}, {"x": 2}])


class TestScriptedProvider(unittest.TestCase):
    def test_match(self):
        p = ScriptedProvider("s", script=[{"match": "weather", "content": "sunny"}])
        self.assertEqual(p.complete([user("what is the weather")]).message.content, "sunny")

    def test_default_fallback(self):
        p = ScriptedProvider("s", script=[{"content": "fallback"}])
        self.assertEqual(p.complete([user("anything")]).message.content, "fallback")

    def test_no_match(self):
        p = ScriptedProvider("s", script=[{"match": "zzz", "content": "nope"}])
        c = p.complete([user("hello")])
        self.assertIn("(no script)", c.message.content)

    def test_after_tool(self):
        script = [
            {"match": "calc", "tool_call": {"id": "c1", "name": "calc", "arguments": {"a": 1}}, "content": ""},
            {"after_tool": True, "content": "done"},
        ]
        p = ScriptedProvider("s", script=script)
        first = p.complete([user("please calc")])
        self.assertIsNotNone(first.message.tool_calls)
        second = p.complete([user("please calc"), assistant("", tool_calls=first.message.tool_calls),
                             ChatMessage(Role.TOOL, "1", tool_call_id="c1")])
        self.assertEqual(second.message.content, "done")

    def test_tool_call_building(self):
        p = ScriptedProvider("s", script=[{"match": "x", "tool_call": {"id": "c1", "name": "f", "arguments": {"a": 1}}}])
        c = p.complete([user("x")])
        self.assertEqual(c.message.tool_calls[0].name, "f")
        self.assertEqual(c.message.tool_calls[0].arguments, {"a": 1})


class TestEchoProvider(unittest.TestCase):
    def test_echo(self):
        p = EchoProvider()
        c = p.complete([user("hello"), user("world")])
        self.assertIn("user: hello", c.message.content)
        self.assertIn("user: world", c.message.content)


if __name__ == "__main__":
    unittest.main()
