import unittest

from prism.core.errors import RetryExhausted, ServerError
from prism.core.retry import RetryPolicy, jitter


def _server_boom():
    raise ServerError("x")


def _value_boom():
    raise ValueError("nope")


class TestRetry(unittest.TestCase):
    def test_success_first_try(self):
        p = RetryPolicy(attempts=3)
        self.assertEqual(p.run(lambda: 42), 42)

    def test_retries_then_succeeds(self):
        state = {"n": 0}

        def flaky():
            state["n"] += 1
            if state["n"] < 3:
                raise ServerError("boom")
            return "ok"

        p = RetryPolicy(attempts=5, sleep=lambda d: None)
        self.assertEqual(p.run(flaky), "ok")
        self.assertEqual(state["n"], 3)

    def test_exhausted(self):
        p = RetryPolicy(attempts=2, sleep=lambda d: None)
        with self.assertRaises(RetryExhausted) as ctx:
            p.run(_server_boom)
        self.assertEqual(ctx.exception.attempts, 2)
        self.assertIsInstance(ctx.exception.cause, ServerError)

    def test_non_retryable_raises_immediately(self):
        p = RetryPolicy(attempts=5, sleep=lambda d: None)
        with self.assertRaises(ValueError):
            p.run(_value_boom)

    def test_delay_bounds(self):
        p = RetryPolicy(attempts=10, base_delay=0.1, max_delay=1.0, backoff=2.0)
        self.assertTrue(0.08 <= p.delay_for(1) <= 0.12)
        self.assertTrue(0.16 <= p.delay_for(2) <= 0.24)
        self.assertTrue(0.32 <= p.delay_for(3) <= 0.48)
        self.assertLessEqual(p.delay_for(10), 1.2)

    def test_jitter_bounds(self):
        for _ in range(50):
            d = jitter(1.0, spread=0.2)
            self.assertTrue(0.8 <= d <= 1.2)

    def test_sleep_called(self):
        calls = []
        p = RetryPolicy(attempts=3, sleep=lambda d: calls.append(d))
        try:
            p.run(_server_boom)
        except RetryExhausted:
            pass
        self.assertEqual(len(calls), 2)  # one sleep between each of 3 attempts


if __name__ == "__main__":
    unittest.main()
