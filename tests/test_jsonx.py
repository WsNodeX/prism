import unittest

from prism.core.jsonx import dumps, extract_json, loads


class TestJsonx(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(extract_json('{"a": 1}'), {"a": 1})

    def test_code_fence(self):
        self.assertEqual(extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_trailing_prose(self):
        self.assertEqual(extract_json('here: {"x": [1,2]} done'), {"x": [1, 2]})

    def test_nested(self):
        self.assertEqual(extract_json('prefix {"a": {"b": [1, {"c": 2}]}} suffix'), {"a": {"b": [1, {"c": 2}]}})

    def test_no_json(self):
        self.assertIsNone(extract_json("nothing here"))

    def test_array(self):
        self.assertEqual(extract_json("arr: [1,2,3]"), [1, 2, 3])

    def test_dumps_loads(self):
        s = dumps({"k": "中文"})
        self.assertEqual(loads(s)["k"], "中文")


if __name__ == "__main__":
    unittest.main()
