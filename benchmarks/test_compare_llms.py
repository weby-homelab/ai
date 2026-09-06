import json
import unittest

from benchmarks.compare_llms import extract_json_object, grade_task


class CompareLLMsHelpersTest(unittest.TestCase):
    def test_extract_json_object_ignores_surrounding_text(self):
        payload = extract_json_object('answer: {"port": 8080, "tls": true} done')

        self.assertEqual(payload, {"port": 8080, "tls": True})

    def test_grade_json_requires_the_expected_contract(self):
        output = json.dumps(
            {"service": "llama-server", "port": 8080, "tls": True},
            ensure_ascii=False,
        )

        passed, detail = grade_task("structured_json", output)

        self.assertTrue(passed)
        self.assertEqual(detail, "schema matched")

    def test_grade_code_rejects_invalid_python(self):
        passed, detail = grade_task("code_generation", "```python\ndef broken(:\n```")

        self.assertFalse(passed)
        self.assertTrue(detail.startswith("syntax error:"))


if __name__ == "__main__":
    unittest.main()
