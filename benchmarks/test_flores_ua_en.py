import unittest

from benchmarks.run_flores_ua_en import (
    build_translation_payload,
    expected_script_ratio,
    normalize_text,
    select_indices,
)


class FloresHelpersTest(unittest.TestCase):
    def test_select_indices_is_deterministic_and_bounded(self):
        self.assertEqual(select_indices(1012, limit=4, stride=20), [0, 20, 40, 60])

    def test_normalize_text_collapses_case_and_whitespace(self):
        self.assertEqual(normalize_text("  Hello\nWORLD! "), "hello world!")

    def test_expected_script_ratio_distinguishes_translation_direction(self):
        self.assertGreater(expected_script_ratio("This is English.", "ukr_en"), 0.9)
        self.assertGreater(expected_script_ratio("Це українською.", "en_ukr"), 0.9)

    def test_translation_payload_disables_thinking_for_language_scoring(self):
        payload = build_translation_payload("local", "Translate only.", "Hello", 256, 42)

        self.assertEqual(payload["chat_template_kwargs"]["enable_thinking"], False)


if __name__ == "__main__":
    unittest.main()
