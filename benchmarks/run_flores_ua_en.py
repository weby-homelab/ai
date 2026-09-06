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
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

EXPECTED_DEVTEST_ROWS = 1012
EXPECTED_UKR_SHA256 = "7bb8f160a455fca27032bdd292dd65838b7aa5a8324c6aedd03ccdf92e20dbc4"
EXPECTED_ENG_SHA256 = "612e9fbe87997617c0fa8fa8929654a4f49b728d96738112c2b86ef6a1d78d88"


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


def validate_base_url(raw_url: str) -> str:
    parts = urlsplit(raw_url)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or parts.path not in {"", "/"}
    ):
        raise ValueError(
            "base URL must be a loopback HTTP(S) origin without credentials/query/fragment"
        )
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def attest_server_process(
    server_pid: int,
    model_file: Path,
    engine_binary: Path,
    expected_spec: str,
    expected_port: int,
) -> None:
    if server_pid < 1 or not engine_binary.is_file():
        raise ValueError("server PID or engine binary is invalid")
    proc_dir = Path(f"/proc/{server_pid}")
    try:
        actual_exe = (proc_dir / "exe").resolve()
        command = (proc_dir / "cmdline").read_bytes().split(b"\0")
        environment = (proc_dir / "environ").read_bytes().split(b"\0")
    except OSError as exc:
        raise ValueError("cannot attest server process") from exc
    if actual_exe != engine_binary.resolve():
        raise ValueError("server executable does not match --engine-binary")
    if str(model_file.resolve()).encode() not in command:
        raise ValueError("server command line does not contain --model-file")
    if b"--port" not in command or str(expected_port).encode() not in command:
        raise ValueError("server command line does not contain the requested API port")
    environment_set = set(environment)
    if b"CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=50" not in environment_set:
        raise ValueError("server process is not bound to MPS policy 50")
    if b"CUDA_DEVICE_MAX_CONNECTIONS=1" not in environment_set:
        raise ValueError("server process is not bound to CUDA connection policy")
    if expected_spec == "none" and b"--spec-type" in command:
        raise ValueError("server command line unexpectedly enables speculation")
    if expected_spec != "none" and expected_spec.encode() not in command:
        raise ValueError("server command line does not contain expected speculation mode")


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


def validate_dataset_files(ukr_file: Path, eng_file: Path) -> None:
    ukr_lines = ukr_file.read_text(encoding="utf-8").splitlines()
    eng_lines = eng_file.read_text(encoding="utf-8").splitlines()
    if len(ukr_lines) != EXPECTED_DEVTEST_ROWS or len(eng_lines) != EXPECTED_DEVTEST_ROWS:
        raise ValueError("unexpected FLORES-200 devtest row count")
    if _sha256(ukr_file) != EXPECTED_UKR_SHA256 or _sha256(eng_file) != EXPECTED_ENG_SHA256:
        raise ValueError("FLORES-200 files do not match the pinned reference snapshot")


def _strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<\|channel>thought.*?<channel\|>", "", text, flags=re.IGNORECASE | re.DOTALL)
    return text.strip()


def _response_text(response: dict[str, Any]) -> tuple[str, str | None]:
    choice = response["choices"][0]
    message = choice["message"]
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    text = _strip_thinking(str(content))
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
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--model-file", type=Path, required=True)
    parser.add_argument("--engine-binary", type=Path, required=True)
    parser.add_argument("--server-pid", type=int, required=True)
    parser.add_argument("--engine-build", required=True)
    parser.add_argument("--run-profile", required=True)
    parser.add_argument("--expected-spec", required=True)
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
        base_url = validate_base_url(args.base_url)
        api_port = urlsplit(base_url).port
        if api_port is None:
            raise ValueError("base URL must include an explicit API port")
        if not args.model_file.is_file():
            raise ValueError("model file does not exist")
        if not args.engine_binary.is_file():
            raise ValueError("engine binary does not exist")
        model_sha256 = _sha256(args.model_file)
        engine_sha256 = _sha256(args.engine_binary)
        attest_server_process(
            args.server_pid,
            args.model_file,
            args.engine_binary,
            args.expected_spec,
            api_port,
        )
        validate_dataset_files(args.ukr_file, args.eng_file)
        examples = load_examples(args.ukr_file, args.eng_file, args.limit, args.stride)
        if len({example.sentence_id for example in examples}) != args.limit:
            raise ValueError("sample selection did not produce the requested item count")
        model_data = _request_json(base_url, "/v1/models", None, args.timeout)
        available_models = {entry["id"] for entry in model_data["data"]}
        if args.model_id not in available_models:
            raise ValueError("requested model ID is not advertised by the server")
        model_id = args.model_id
        import sacrebleu  # noqa: F401  # checked explicitly by _score
    except (KeyError, IndexError, OSError, RuntimeError, ValueError, ImportError) as exc:
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
        _request_json(base_url, "/v1/chat/completions", warmup, args.timeout)
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
            response = _request_json(base_url, "/v1/chat/completions", payload, args.timeout)
            prediction, finish_reason = _response_text(response)
            timings = response.get("timings") or {}
            usage = response.get("usage") or {}
            status = (
                "ok"
                if prediction and finish_reason == "stop"
                else "incomplete"
                if prediction
                else "empty"
            )
            scoring_prediction = prediction if status == "ok" else ""
            sentence_bleu, sentence_chrf = _sentence_score(scoring_prediction, example.reference)
            scored[example.direction][0].append(scoring_prediction)
            scored[example.direction][1].append(example.reference)
            record = {
                "sentence_id": example.sentence_id,
                "direction": example.direction,
                "status": status,
                "finish_reason": finish_reason,
                "script_ratio": round(
                    expected_script_ratio(scoring_prediction, example.direction), 6
                ),
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
                "script_ratio": 0.0,
                "sentence_bleu": 0.0,
                "sentence_chrf_plus_plus": 0.0,
                "wall_ms": round((time.perf_counter() - started) * 1000, 3),
            }
            scored[example.direction][0].append("")
            scored[example.direction][1].append(example.reference)
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
            "incomplete_items": sum(
                record["status"] == "incomplete" for record in direction_records
            ),
            "empty_items": sum(record["status"] == "empty" for record in direction_records),
            "error_items": sum(record["status"] == "error" for record in direction_records),
            "corpus_bleu": round(bleu, 4),
            "corpus_chrf_plus_plus": round(chrf, 4),
            "mean_script_ratio": round(
                sum(record["script_ratio"] for record in direction_records)
                / len(direction_records),
                4,
            ),
            "target_script_compliance_rate": round(
                sum(record["script_ratio"] >= 0.5 for record in direction_records)
                / len(direction_records),
                4,
            )
            if direction_records
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
        "base_url": base_url,
        "model_file": str(args.model_file),
        "model_sha256": model_sha256,
        "engine_binary": str(args.engine_binary),
        "engine_binary_sha256": engine_sha256,
        "server_pid": args.server_pid,
        "engine_build": args.engine_build,
        "run_profile": args.run_profile,
        "expected_spec": args.expected_spec,
        "seed": args.seed,
        "max_tokens": args.max_tokens,
        "directions": aggregates,
        "records": records,
    }
    _atomic_write_json(args.output, result)
    return 1 if any(record["status"] != "ok" for record in records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
