import unittest

from prism.core.breaker import CircuitBreaker
from prism.core.errors import CircuitOpenError


def _boom():
    raise RuntimeError("x")


class TestBreaker(unittest.TestCase):
    def test_closed_allows(self):
        b = CircuitBreaker(failure_threshold=2)
        self.assertTrue(b._allow())
        self.assertEqual(b.state, b.CLOSED)

    def test_opens_after_threshold(self):
        b = CircuitBreaker(failure_threshold=2, now=lambda: 0)
        with self.assertRaises(RuntimeError):
            b.call(_boom)
        self.assertEqual(b.state, b.CLOSED)
        with self.assertRaises(RuntimeError):
            b.call(_boom)
        self.assertEqual(b.state, b.OPEN)

    def test_open_rejects(self):
        b = CircuitBreaker(failure_threshold=1, now=lambda: 0)
        with self.assertRaises(RuntimeError):
            b.call(_boom)
        with self.assertRaises(CircuitOpenError):
            b.call(lambda: 1)

    def test_half_open_success_closes(self):
        clock = {"t": 0.0}
        b = CircuitBreaker(failure_threshold=1, reset_timeout=10, now=lambda: clock["t"])
        with self.assertRaises(RuntimeError):
            b.call(_boom)  # open
        clock["t"] = 20  # past reset
        self.assertEqual(b.call(lambda: 1), 1)  # half-open probe succeeds
        self.assertEqual(b.state, b.CLOSED)
        self.assertEqual(b.failures, 0)

    def test_half_open_failure_reopens(self):
        clock = {"t": 0.0}
        b = CircuitBreaker(failure_threshold=1, reset_timeout=10, now=lambda: clock["t"])
        with self.assertRaises(RuntimeError):
            b.call(_boom)
        clock["t"] = 20
        with self.assertRaises(RuntimeError):
            b.call(_boom)  # probe fails -> open
        self.assertEqual(b.state, b.OPEN)

    def test_success_resets_failures(self):
        b = CircuitBreaker(failure_threshold=3, now=lambda: 0)
        with self.assertRaises(RuntimeError):
            b.call(_boom)
        self.assertEqual(b.call(lambda: 1), 1)
        self.assertEqual(b.failures, 0)
        self.assertEqual(b.state, b.CLOSED)


if __name__ == "__main__":
    unittest.main()
