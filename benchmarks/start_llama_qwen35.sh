#!/usr/bin/env bash
set -Eeuo pipefail

BEE_BIN="${BEE_BIN:-/root/beellama.cpp/build/bin/llama-server}"
MODEL_PATH="${MODEL_PATH:-/mnt/nvme-models/Qwen3.5-9B-Q4_0.gguf}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"
THREADS="${THREADS:-10}"
CONTEXT_SIZE="${CONTEXT_SIZE:-32768}"
BATCH_SIZE="${BATCH_SIZE:-512}"
UBATCH_SIZE="${UBATCH_SIZE:-256}"

export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE="${CUDA_MPS_ACTIVE_THREAD_PERCENTAGE:-50}"
export CUDA_DEVICE_MAX_CONNECTIONS="${CUDA_DEVICE_MAX_CONNECTIONS:-1}"

if [[ ! -x "$BEE_BIN" ]]; then
    printf 'llama-server binary is not executable: %s\n' "$BEE_BIN" >&2
    exit 1
fi
if [[ ! -r "$MODEL_PATH" ]]; then
    printf 'model is not readable: %s\n' "$MODEL_PATH" >&2
    exit 1
fi

printf '==> BeeLlama | model=%s | context=%s | batch=%s/%s | q8 KV\n' \
    "$MODEL_PATH" "$CONTEXT_SIZE" "$BATCH_SIZE" "$UBATCH_SIZE"

exec "$BEE_BIN" \
    -m "$MODEL_PATH" \
    -ngl 999 \
    -t "$THREADS" -Cr 0-9 -Crb 0-9 --cpu-strict 1 \
    -c "$CONTEXT_SIZE" \
    -fa on -ctk q8_0 -ctv q8_0 \
    --metrics -np 1 -b "$BATCH_SIZE" -ub "$UBATCH_SIZE" \
    -fit off --no-mmap --mlock \
    --temp 0.3 --top-p 0.95 --top-k 40 \
    --chat-template-kwargs '{"preserve_thinking":true}' \
    --host "$HOST" --port "$PORT"
