import unittest

from prism.core.types import (
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


class TestTypes(unittest.TestCase):
    def test_message_roundtrip(self):
        m = ChatMessage(Role.USER, "hi", name="alice")
        d = m.to_dict()
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["name"], "alice")
        self.assertEqual(ChatMessage.from_dict(d).content, "hi")

    def test_toolcall_from_dict_string_args(self):
        raw = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'},
        }
        tc = ToolCall.from_dict(raw)
        self.assertEqual(tc.name, "add")
        self.assertEqual(tc.arguments, {"a": 1, "b": 2})

    def test_toolcall_from_dict_dict_args(self):
        raw = {"id": "c", "function": {"name": "f", "arguments": {"x": 3}}}
        tc = ToolCall.from_dict(raw)
        self.assertEqual(tc.arguments, {"x": 3})

    def test_toolcall_to_dict(self):
        tc = ToolCall("c", "f", {"x": 1})
        d = tc.to_dict()
        self.assertEqual(d["function"]["name"], "f")
        self.assertEqual(d["function"]["arguments"], '{"x": 1}')

    def test_usage_add(self):
        a = Usage(1, 2, 3, 0.5)
        b = Usage(4, 5, 9, 0.25)
        s = a + b
        self.assertEqual((s.prompt_tokens, s.completion_tokens, s.total_tokens), (5, 7, 12))
        self.assertAlmostEqual(s.cost_usd, 0.75)

    def test_completion_message(self):
        c = Completion("id", "m", [assistant("hello")], Usage(), "p")
        self.assertEqual(c.message.content, "hello")

    def test_helpers(self):
        self.assertEqual(system("s").role, Role.SYSTEM)
        self.assertEqual(user("u").role, Role.USER)
        self.assertEqual(assistant("a").role, Role.ASSISTANT)
        tr = tool_result("c1", "v", name="f")
        self.assertEqual(tr.role, Role.TOOL)
        self.assertEqual(tr.tool_call_id, "c1")

    def test_tool_to_dict(self):
        t = Tool("f", "does f", {"type": "object", "properties": {}})
        d = t.to_dict()
        self.assertEqual(d["function"]["name"], "f")


if __name__ == "__main__":
    unittest.main()
