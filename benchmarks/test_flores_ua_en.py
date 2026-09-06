import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks.run_flores_ua_en import (
    _response_text,
    build_translation_payload,
    expected_script_ratio,
    normalize_text,
    select_indices,
    validate_base_url,
    validate_dataset_files,
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

    def test_translation_response_does_not_fallback_to_hidden_reasoning(self):
        text, finish_reason = _response_text(
            {
                "choices": [
                    {
                        "message": {"content": None, "reasoning_content": "hidden"},
                        "finish_reason": "length",
                    }
                ]
            }
        )

        self.assertEqual(text, "")
        self.assertEqual(finish_reason, "length")

    def test_flores_base_url_rejects_credentials(self):
        with self.assertRaises(ValueError):
            validate_base_url("https://user:secret@example.test")

    def test_dataset_validation_rejects_unpinned_files(self):
        with TemporaryDirectory() as directory:
            ukr_file = Path(directory) / "ukr_Cyrl.devtest"
            eng_file = Path(directory) / "eng_Latn.devtest"
            ukr_file.write_text("not FLORES\n", encoding="utf-8")
            eng_file.write_text("not FLORES\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                validate_dataset_files(ukr_file, eng_file)


if __name__ == "__main__":
    unittest.main()
