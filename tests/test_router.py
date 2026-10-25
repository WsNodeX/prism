import unittest

from prism.core.providers import EchoProvider, ScriptedProvider
from prism.core.router import Router


class TestRouter(unittest.TestCase):
    def setUp(self):
        self.a = ScriptedProvider("a")
        self.b = ScriptedProvider("b")
        self.c = ScriptedProvider("c")

    def test_first(self):
        r = Router([self.a, self.b], strategy="first")
        self.assertIs(r.select(), self.a)

    def test_empty(self):
        with self.assertRaises(ValueError):
            Router([]).select()

    def test_round_robin(self):
        r = Router([self.a, self.b, self.c], strategy="round_robin")
        order = [r.select().name for _ in range(4)]
        self.assertEqual(order, ["a", "b", "c", "a"])

    def test_lowest_cost(self):
        r = Router([self.a, self.b, self.c], strategy="lowest_cost")
        r.set_meta("a", cost_per_1k=0.01)
        r.set_meta("b", cost_per_1k=0.02)
        r.set_meta("c", cost_per_1k=0.005)
        self.assertIs(r.select(), self.c)

    def test_lowest_latency(self):
        r = Router([self.a, self.b, self.c], strategy="lowest_latency")
        r.set_meta("a", latency_ms=300)
        r.set_meta("b", latency_ms=80)
        r.set_meta("c", latency_ms=200)
        self.assertIs(r.select(), self.b)

    def test_capability(self):
        r = Router([self.a, self.b], strategy="capability")
        r.set_meta("a", capabilities=["tools"])
        # b has no capabilities; a supports tools
        self.assertIs(r.select(tools=[object()]), self.a)

    def test_capability_fallback(self):
        r = Router([self.b], strategy="capability")
        r.set_meta("b", capabilities=[])
        self.assertIs(r.select(tools=[object()]), self.b)

    def test_unknown_strategy(self):
        r = Router([self.a, self.b], strategy="nope")
        with self.assertRaises(ValueError):
            r.select()

    def test_add(self):
        r = Router([self.a])
        r.add(self.b, cost_per_1k=0.1)
        self.assertEqual(len(r.providers), 2)
        self.assertEqual(r.meta["b"]["cost_per_1k"], 0.1)


if __name__ == "__main__":
    unittest.main()
