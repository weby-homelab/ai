import json
import unittest

from benchmarks.compare_llms import (
    TASKS,
    build_long_context_prompt,
    build_request_payload,
    extract_json_object,
    grade_response,
    grade_task,
    grade_tool_call_message,
    validate_base_url,
)


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

    def test_grade_json_rejects_surrounding_prose(self):
        passed, detail = grade_task("structured_json", 'answer: {"service":"llama-server"}')

        self.assertFalse(passed)
        self.assertEqual(detail, "schema mismatch")

    def test_grade_code_rejects_invalid_python(self):
        passed, detail = grade_task("code_generation", "```python\ndef broken(:\n```")

        self.assertFalse(passed)
        self.assertTrue(detail.startswith("syntax error:"))

    def test_math_requires_only_the_expected_integer(self):
        passed, _ = grade_task("math", "The answer is 346.")

        self.assertFalse(passed)
        self.assertTrue(grade_task("math", "346")[0])

    def test_long_context_requires_only_the_buried_marker(self):
        passed, _ = grade_task("long_context", "The marker is WS-BENCHMARK-NEEDLE-7F3A-2026.")

        self.assertFalse(passed)

    def test_tool_call_task_declares_a_function_schema(self):
        task = next(task for task in TASKS if task.task_id == "tool_call")

        payload = build_request_payload(task, {"model": "local"})

        self.assertEqual(payload["tools"][0]["function"]["name"], "restart_service")
        self.assertEqual(payload["tool_choice"]["function"]["name"], "restart_service")

    def test_tool_call_grading_requires_structured_arguments(self):
        passed, detail = grade_tool_call_message(
            {
                "tool_calls": [
                    {
                        "function": {
                            "name": "restart_service",
                            "arguments": '{"name":"llama-server","reason":"OOM recovery"}',
                        }
                    }
                ]
            }
        )

        self.assertTrue(passed)
        self.assertEqual(detail, "structured tool call matched")

    def test_base_url_rejects_embedded_credentials(self):
        with self.assertRaises(ValueError):
            validate_base_url("http://user:password@127.0.0.1:8080")

    def test_length_limited_response_is_incomplete(self):
        passed, detail = grade_response("math", "346", "length")

        self.assertFalse(passed)
        self.assertEqual(detail, "incomplete: max_tokens reached")

    def test_long_context_needle_is_not_leaked_in_the_instruction(self):
        prompt = build_long_context_prompt()

        self.assertEqual(prompt.count("WS-BENCHMARK-NEEDLE-7F3A-2026"), 1)


if __name__ == "__main__":
    unittest.main()
