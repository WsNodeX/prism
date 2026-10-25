import unittest

from prism.core.meter import Meter, Trace
from prism.core.types import Usage


class TestMeter(unittest.TestCase):
    def test_span_record(self):
        m = Meter()
        tr = m.span("p", "m")
        tr.finish(True, Usage(10, 5, 15, 0.01))
        m.record(tr)
        self.assertEqual(m.calls, 1)
        self.assertEqual(m.total_tokens, 15)
        self.assertAlmostEqual(m.total_cost, 0.01)

    def test_cached_hits(self):
        m = Meter()
        tr = m.span("p", "m")
        tr.finish(True, Usage(1, 1, 2))
        m.record(tr, cached=True)
        self.assertEqual(m.cached_hits, 1)
        self.assertAlmostEqual(m.totals()["hit_rate"], 1.0)

    def test_errors(self):
        m = Meter()
        tr = m.span("p", "m")
        tr.finish(False, error="boom")
        m.record(tr)
        self.assertEqual(m.errors, 1)
        self.assertEqual(m.totals()["calls"], 1)

    def test_totals_empty(self):
        self.assertEqual(Meter().totals()["calls"], 0)


if __name__ == "__main__":
    unittest.main()
