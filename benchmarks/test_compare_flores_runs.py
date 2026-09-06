import unittest

from benchmarks.compare_flores_runs import compare_results


def _run(model_id: str, model_sha256: str, bleu: float, chrf: float) -> dict:
    records = [
        {
            "sentence_id": 1,
            "direction": "ukr_en",
            "status": "ok",
            "sentence_bleu": bleu,
            "sentence_chrf_plus_plus": chrf,
        },
        {
            "sentence_id": 1,
            "direction": "en_ukr",
            "status": "ok",
            "sentence_bleu": bleu,
            "sentence_chrf_plus_plus": chrf,
        },
    ]
    return {
        "schema_version": 1,
        "benchmark": "FLORES-200 devtest bounded subset",
        "dataset": {"sample_ids": [1], "sample_limit": 1, "sample_stride": 20},
        "model_id": model_id,
        "model_sha256": model_sha256,
        "engine_binary_sha256": "c" * 64,
        "engine_build": "85e22ea",
        "run_profile": "steady",
        "seed": 42,
        "max_tokens": 256,
        "records": records,
    }


class CompareFloresRunsTest(unittest.TestCase):
    def test_compare_results_counts_the_higher_score_as_a_win(self):
        result = compare_results(
            _run("qwen", "a" * 64, 2.0, 4.0),
            _run("gemma", "b" * 64, 1.0, 5.0),
        )

        self.assertEqual(
            result["overall"]["sentence_bleu"],
            {"left": 2, "right": 0, "ties": 0, "mean_delta_left_minus_right": 1.0},
        )
        self.assertEqual(
            result["overall"]["sentence_chrf_plus_plus"],
            {"left": 0, "right": 2, "ties": 0, "mean_delta_left_minus_right": -1.0},
        )

    def test_compare_results_rejects_different_dataset_contracts(self):
        left = _run("qwen", "a" * 64, 2.0, 4.0)
        right = _run("gemma", "b" * 64, 1.0, 5.0)
        right["dataset"]["sample_ids"] = [2]

        with self.assertRaises(ValueError):
            compare_results(left, right)

    def test_compare_results_rejects_incomplete_records(self):
        left = _run("qwen", "a" * 64, 2.0, 4.0)
        right = _run("gemma", "b" * 64, 1.0, 5.0)
        left["records"][0]["status"] = "incomplete"

        with self.assertRaises(ValueError):
            compare_results(left, right)


if __name__ == "__main__":
    unittest.main()
