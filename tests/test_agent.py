import unittest

from prism import Prism, Router, ScriptedProvider, user
from prism.core.types import Role, assistant


def make_agent_prism():
    script = [
        {
            "match": r"7\s*(times|x|\*)\s*5|7\s*乘\s*5",
            "tool_call": {"id": "c1", "name": "multiply", "arguments": {"a": 7, "b": 5}},
            "content": "",
        },
        {"after_tool": True, "content": "The product is 35."},
    ]
    prism = Prism(router=Router([ScriptedProvider("agent-provider", script=script)], strategy="first"), cache=None)
    return prism


class TestAgent(unittest.TestCase):
    def test_tool_call_then_answer(self):
        prism = make_agent_prism()

        @prism.register_tool(description="Multiply two integers.")
        def multiply(a: int, b: int) -> int:
            return a * b

        res = prism.agent([user("What is 7 times 5?")], max_iter=4)
        self.assertEqual(res.answer, "The product is 35.")
        self.assertEqual(len(res.steps), 1)
        self.assertEqual(res.steps[0][0], "multiply")
        self.assertEqual(res.steps[0][2], 35)

    def test_max_iter_guard(self):
        # provider that always emits a tool call -> never finishes -> max_iter bounds it
        script = [
            {"match": ".*", "tool_call": {"id": "c", "name": "loop", "arguments": {}}, "content": ""},
            {"after_tool": True, "content": "final"},
        ]
        prism = Prism(router=Router([ScriptedProvider("p", script=script)], strategy="first"), cache=None)

        @prism.register_tool()
        def loop() -> int:
            return 1

        res = prism.agent([user("go")], max_iter=3)
        self.assertLessEqual(len(res.steps), 3)
        self.assertIsInstance(res.answer, str)

    def test_build_registry(self):
        prism = make_agent_prism()

        @prism.register_tool()
        def add(a: int, b: int) -> int:
            return a + b

        reg = prism.build_registry()
        from prism.core.types import ToolCall

        self.assertEqual(reg.dispatch(ToolCall("c", "add", {"a": 1, "b": 2})), 3)


if __name__ == "__main__":
    unittest.main()
