import unittest

import prism.core.cache as cache_mod
from prism.core.cache import LRUCache, SemanticCache
from prism.core.types import Completion, Usage, user


class TestLRU(unittest.TestCase):
    def test_eviction(self):
        c = LRUCache(maxsize=2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        self.assertFalse(c.contains("a"))
        self.assertTrue(c.contains("c"))

    def test_recency(self):
        c = LRUCache(maxsize=2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")  # touch a -> most recent
        c.put("c", 3)  # evicts b
        self.assertFalse(c.contains("b"))
        self.assertTrue(c.contains("a"))


class TestSemanticCache(unittest.TestCase):
    def setUp(self):
        self.msg = [user("hello")]
        self.comp = Completion("x", "m", [], Usage(1, 1, 2), "p")

    def test_put_get(self):
        c = SemanticCache()
        self.assertIsNone(c.get(self.msg, "m", None))
        c.put(self.msg, "m", None, self.comp)
        self.assertIs(c.get(self.msg, "m", None), self.comp)
        self.assertEqual(c.stats()["hits"], 1)

    def test_deterministic_key(self):
        c = SemanticCache()
        k1 = c.key(self.msg, "m", None)
        k2 = c.key([user("hello")], "m", None)
        self.assertEqual(k1, k2)
        k3 = c.key([user("different")], "m", None)
        self.assertNotEqual(k1, k3)

    def test_different_model_different_key(self):
        c = SemanticCache()
        self.assertNotEqual(c.key(self.msg, "m1", None), c.key(self.msg, "m2", None))

    def test_ttl_expiry(self):
        fake = {"t": 1000.0}
        cache_mod.time.time = lambda: fake["t"]
        c = SemanticCache(ttl=10)
        c.put(self.msg, "m", None, self.comp)
        self.assertIsNotNone(c.get(self.msg, "m", None))
        fake["t"] = 1020  # advance beyond TTL
        self.assertIsNone(c.get(self.msg, "m", None))
        self.assertEqual(c.stats()["misses"], 1)


if __name__ == "__main__":
    unittest.main()
