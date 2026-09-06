#!/usr/bin/env python3
"""Derive reproducible pairwise wins from two pinned FLORES run files."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import tempfile
from pathlib import Path
from statistics import mean
from typing import Any

METRICS = ("sentence_bleu", "sentence_chrf_plus_plus")
IDENTITY_FIELDS = (
    "benchmark",
    "dataset",
    "seed",
    "max_tokens",
    "engine_build",
    "run_profile",
    "engine_binary_sha256",
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _record_map(run: dict[str, Any]) -> dict[tuple[int, str], dict[str, Any]]:
    records = run.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("run has no records")
    mapped = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("run has a non-object sentence record")
        key = (record.get("sentence_id"), record.get("direction"))
        if not isinstance(key[0], int) or not isinstance(key[1], str) or key in mapped:
            raise ValueError("run has invalid or duplicate sentence records")
        if record.get("status") != "ok":
            raise ValueError("pairwise comparison requires complete successful records")
        if any(metric not in record for metric in METRICS):
            raise ValueError("run record is missing a pairwise metric")
        for metric in METRICS:
            value = record[metric]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("run record contains a non-numeric pairwise metric")
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError("run record contains an out-of-range pairwise metric")
        mapped[key] = record
    return mapped


def _counts(left_values: list[float], right_values: list[float]) -> dict[str, Any]:
    if len(left_values) != len(right_values) or not left_values:
        raise ValueError("pairwise score vectors are empty or misaligned")
    left_wins = sum(left > right for left, right in zip(left_values, right_values))
    right_wins = sum(right > left for left, right in zip(left_values, right_values))
    ties = len(left_values) - left_wins - right_wins
    deltas = [left - right for left, right in zip(left_values, right_values)]
    return {
        "left": left_wins,
        "right": right_wins,
        "ties": ties,
        "mean_delta_left_minus_right": round(mean(deltas), 6),
    }


def compare_results(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    for field in IDENTITY_FIELDS:
        if left.get(field) != right.get(field):
            raise ValueError(f"runs disagree on {field}")
    left_sha = left.get("model_sha256")
    right_sha = right.get("model_sha256")
    if not isinstance(left_sha, str) or not SHA256_PATTERN.fullmatch(left_sha):
        raise ValueError("left model SHA-256 is missing or invalid")
    if not isinstance(right_sha, str) or not SHA256_PATTERN.fullmatch(right_sha):
        raise ValueError("right model SHA-256 is missing or invalid")
    if left_sha == right_sha:
        raise ValueError("left and right model SHA-256 values must differ")
    engine_sha = left.get("engine_binary_sha256")
    if not isinstance(engine_sha, str) or not SHA256_PATTERN.fullmatch(engine_sha):
        raise ValueError("engine binary SHA-256 is missing or invalid")

    left_records = _record_map(left)
    right_records = _record_map(right)
    if set(left_records) != set(right_records):
        raise ValueError("runs do not contain the same aligned sentence IDs")

    sample_ids = left.get("dataset", {}).get("sample_ids")
    if (
        not isinstance(sample_ids, list)
        or not sample_ids
        or any(not isinstance(value, int) for value in sample_ids)
        or len(set(sample_ids)) != len(sample_ids)
        or left["dataset"].get("sample_limit") != len(sample_ids)
    ):
        raise ValueError("dataset sample_ids are missing or invalid")
    expected_keys = {
        (sentence_id, direction) for sentence_id in sample_ids for direction in ("ukr_en", "en_ukr")
    }
    if set(left_records) != expected_keys:
        raise ValueError("run records do not match both expected FLORES directions")

    directions = sorted({key[1] for key in left_records})
    direction_results = {}
    overall_values = {metric: {"left": [], "right": []} for metric in METRICS}
    for direction in directions:
        keys = sorted(key for key in left_records if key[1] == direction)
        direction_results[direction] = {}
        for metric in METRICS:
            left_values = [float(left_records[key][metric]) for key in keys]
            right_values = [float(right_records[key][metric]) for key in keys]
            overall_values[metric]["left"].extend(left_values)
            overall_values[metric]["right"].extend(right_values)
            direction_results[direction][metric] = _counts(left_values, right_values)

    return {
        "schema_version": 1,
        "benchmark": left["benchmark"],
        "left": {
            "model_id": left.get("model_id"),
            "model_file": left.get("model_file"),
            "model_sha256": left_sha,
        },
        "right": {
            "model_id": right.get("model_id"),
            "model_file": right.get("model_file"),
            "model_sha256": right_sha,
        },
        "shared_dataset": left["dataset"],
        "shared_runtime": {
            field: left[field]
            for field in (
                "seed",
                "max_tokens",
                "engine_build",
                "run_profile",
                "engine_binary_sha256",
            )
        },
        "directions": direction_results,
        "overall": {
            metric: _counts(values["left"], values["right"])
            for metric, values in overall_values.items()
        },
    }


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare_results(
            json.loads(args.left.read_text(encoding="utf-8")),
            json.loads(args.right.read_text(encoding="utf-8")),
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(f"comparison failed: {exc}")
    _atomic_write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
