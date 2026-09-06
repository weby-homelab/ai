#!/usr/bin/env python3
"""Run a bounded FLORES-200 Ukrainian-English reference comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Example:
    sentence_id: int
    direction: str
    source: str
    reference: str


def select_indices(total: int, limit: int, stride: int) -> list[int]:
    if total < 1 or limit < 1 or stride < 1:
        raise ValueError("total, limit, and stride must be positive")
    return list(range(0, total, stride))[:limit]


def normalize_text(text: str) -> str:
    return " ".join(text.casefold().split())


def expected_script_ratio(text: str, direction: str) -> float:
    expected = "LATIN" if direction == "ukr_en" else "CYRILLIC"
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    return sum(expected in unicodedata.name(char, "") for char in letters) / len(letters)


def load_examples(ukr_file: Path, eng_file: Path, limit: int, stride: int) -> list[Example]:
    ukrainian = ukr_file.read_text(encoding="utf-8").splitlines()
    english = eng_file.read_text(encoding="utf-8").splitlines()
    if len(ukrainian) != len(english):
        raise ValueError("FLORES source files are not aligned")
    examples = []
    for index in select_indices(len(ukrainian), limit, stride):
        sentence_id = index + 1
        examples.extend(
            (
                Example(sentence_id, "ukr_en", ukrainian[index], english[index]),
                Example(sentence_id, "en_ukr", english[index], ukrainian[index]),
            )
        )
    return examples


def _strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<\|channel\|>thought.*?<channel\|>", "", text, flags=re.IGNORECASE | re.DOTALL)
    return text.strip()


def _response_text(response: dict[str, Any]) -> tuple[str, str | None]:
    choice = response["choices"][0]
    message = choice["message"]
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    text = _strip_thinking(str(content) if str(content).strip() else str(reasoning))
    return text, choice.get("finish_reason")


def build_translation_payload(
    model_id: str, instruction: str, source: str, max_tokens: int, seed: int
) -> dict[str, Any]:
    return {
        "model": model_id,
        "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": source},
        ],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": max_tokens,
        "seed": seed,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": False},
    }


def _request_json(
    base_url: str, path: str, payload: dict[str, Any] | None, timeout: float
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"API request failed: {type(exc).__name__}") from exc


def _score(predictions: list[str], references: list[str]) -> tuple[float, float]:
    try:
        import sacrebleu
    except ImportError as exc:
        raise RuntimeError("sacrebleu is required for FLORES scoring") from exc
    bleu = sacrebleu.corpus_bleu(predictions, [references], tokenize="13a").score
    chrf = sacrebleu.corpus_chrf(
        predictions,
        [references],
        char_order=6,
        word_order=2,
        beta=2,
    ).score
    return float(bleu), float(chrf)


def _sentence_score(prediction: str, reference: str) -> tuple[float, float]:
    try:
        import sacrebleu
    except ImportError as exc:
        raise RuntimeError("sacrebleu is required for FLORES scoring") from exc
    bleu = sacrebleu.sentence_bleu(prediction, [reference], tokenize="13a").score
    chrf = sacrebleu.sentence_chrf(
        prediction,
        [reference],
        char_order=6,
        word_order=2,
        beta=2,
    ).score
    return float(bleu), float(chrf)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--ukr-file", type=Path, required=True)
    parser.add_argument("--eng-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--stride", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.limit < 1 or args.stride < 1 or args.max_tokens < 1:
        parser.error("--limit, --stride, and --max-tokens must be positive")
    return args


def main() -> int:
    args = _parse_args()
    try:
        examples = load_examples(args.ukr_file, args.eng_file, args.limit, args.stride)
        model_data = _request_json(args.base_url, "/v1/models", None, args.timeout)
        model_id = args.model_id or model_data["data"][0]["id"]
        import sacrebleu  # noqa: F401  # checked explicitly by _score
    except (KeyError, IndexError, RuntimeError, ValueError, ImportError) as exc:
        print(f"benchmark setup failed: {exc}", file=sys.stderr)
        return 2

    warmup = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply only READY."}],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 8,
        "seed": args.seed,
        "stream": False,
    }
    try:
        _request_json(args.base_url, "/v1/chat/completions", warmup, args.timeout)
    except RuntimeError as exc:
        print(f"warmup failed: {exc}", file=sys.stderr)
        return 2

    records: list[dict[str, Any]] = []
    scored: dict[str, tuple[list[str], list[str]]] = {"ukr_en": ([], []), "en_ukr": ([], [])}
    for example in examples:
        instruction = (
            "Translate the following Ukrainian sentence into English. Return only the translation."
            if example.direction == "ukr_en"
            else "Переклади наведене англійське речення українською мовою. Поверни лише переклад."
        )
        payload = build_translation_payload(
            model_id, instruction, example.source, args.max_tokens, args.seed
        )
        started = time.perf_counter()
        try:
            response = _request_json(args.base_url, "/v1/chat/completions", payload, args.timeout)
            prediction, finish_reason = _response_text(response)
            timings = response.get("timings") or {}
            usage = response.get("usage") or {}
            sentence_bleu, sentence_chrf = _sentence_score(prediction, example.reference)
            if prediction:
                scored[example.direction][0].append(prediction)
                scored[example.direction][1].append(example.reference)
            record = {
                "sentence_id": example.sentence_id,
                "direction": example.direction,
                "status": "ok" if prediction else "empty",
                "finish_reason": finish_reason,
                "script_ratio": round(expected_script_ratio(prediction, example.direction), 6),
                "sentence_bleu": round(sentence_bleu, 6),
                "sentence_chrf_plus_plus": round(sentence_chrf, 6),
                "output_chars": len(prediction),
                "output_sha256": hashlib.sha256(prediction.encode("utf-8")).hexdigest(),
                "wall_ms": round((time.perf_counter() - started) * 1000, 3),
                "usage": usage,
                "timings": timings,
            }
        except (KeyError, IndexError, RuntimeError) as exc:
            record = {
                "sentence_id": example.sentence_id,
                "direction": example.direction,
                "status": "error",
                "error_type": type(exc).__name__,
                "wall_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        records.append(record)
        print(json.dumps(record, ensure_ascii=False))

    aggregates = {}
    for direction, (predictions, references) in scored.items():
        bleu, chrf = _score(predictions, references) if predictions else (0.0, 0.0)
        direction_records = [record for record in records if record["direction"] == direction]
        valid = [record for record in direction_records if record["status"] == "ok"]
        aggregates[direction] = {
            "items": len(direction_records),
            "successful_items": len(valid),
            "corpus_bleu": round(bleu, 4),
            "corpus_chrf_plus_plus": round(chrf, 4),
            "mean_script_ratio": round(
                sum(record["script_ratio"] for record in valid) / len(valid), 4
            )
            if valid
            else 0.0,
            "target_script_compliance_rate": round(
                sum(record["script_ratio"] >= 0.5 for record in valid) / len(valid), 4
            )
            if valid
            else 0.0,
        }

    result = {
        "schema_version": 1,
        "benchmark": "FLORES-200 devtest bounded subset",
        "dataset": {
            "ukr_file_sha256": _sha256(args.ukr_file),
            "eng_file_sha256": _sha256(args.eng_file),
            "total_aligned_sentences": len(args.ukr_file.read_text(encoding="utf-8").splitlines()),
            "sample_limit": args.limit,
            "sample_stride": args.stride,
            "sample_ids": sorted({example.sentence_id for example in examples}),
        },
        "model_id": model_id,
        "base_url": args.base_url,
        "seed": args.seed,
        "max_tokens": args.max_tokens,
        "directions": aggregates,
        "records": records,
    }
    _atomic_write_json(args.output, result)
    return 1 if any(record["status"] == "error" for record in records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
