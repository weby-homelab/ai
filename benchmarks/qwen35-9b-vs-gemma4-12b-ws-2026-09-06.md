# Qwen3.5-9B vs Gemma 4 12B на WS

> **Статус:** завершено 2026-09-06
>
> **Мета:** порівняти дві моделі на однаковому WS-профілі та порівняти їх із
> незалежним reference для багатомовного тесту UA↔EN.

## 1. Executive summary

| Питання | Переможець / результат |
|---|---|
| Чиста генерація без speculative decoding | **Qwen3.5-9B MTP GGUF:** 64.33 t/s проти 38.70 t/s Gemma на depth 2K; 58.75 проти 38.15 на depth 8K |
| Практична генерація з доступним MTP | **Qwen3.5-9B MTP:** 71.56–90.91 t/s у фінальній suite; Gemma MTP не стартував на цьому GGUF |
| Локальні реальні tasks (machine-only) | Gemma **8/8**, Qwen **7/8**; Qwen пропустив literal `rollback` у checklist |
| FLORES-200 `ukr→en` проти reference | Невелика перевага Gemma: BLEU **44.7479** проти 43.5096; chrF++ **67.2039** проти 66.6242 |
| FLORES-200 `en→ukr` проти reference | BLEU: Qwen **26.9537** проти 26.8086; chrF++: Qwen **55.0531** проти 54.5833 |
| FLORES pairwise | BLEU: Gemma виграла 49/100, Qwen 43/100, 8 ties; chrF++: Qwen 48, Gemma 47, 5 ties |
| Рекомендований default для інтерактивного WS | **Qwen3.5-9B MTP** — значно швидший і стабільно проходить long-context retrieval |

**Короткий висновок:** Gemma має дуже близьку, а на `ukr→en` трохи кращу
reference-relative якість. Qwen має істотну перевагу в latency/throughput,
нативно працює з MTP і тому залишений активним default-сервісом WS. Ці висновки
не змішують якість перекладу зі швидкістю speculative decoding.

## 2. Тестове середовище

| Компонент | Фактичне значення |
|---|---|
| Host | WS |
| CPU | Intel Xeon E5-2666 v3, 10 фізичних ядер / 20 потоків |
| RAM | 128 GB DDR4 Registered ECC; Linux бачить приблизно 121 GiB |
| GPU | NVIDIA GeForce RTX 2080 Ti, 11,264 MiB total / 10,828 MiB runtime |
| NVIDIA driver | **610.57.04** |
| CUDA | 13.3 runtime/toolchain |
| OS/kernel | Ubuntu 26.04.1 LTS, `7.0.0-31-generic` |
| Engine | BeeLlama.cpp `85e22ea`, build number 1 |
| CPU affinity | `0x3ff`, 10 фізичних ядер, `--cpu-strict 1` |
| Context | 32,768 tokens |
| KV cache | `q8_0` для K/V; для Qwen MTP також draft K/V `q8_0` |
| Batch | `-b 512 -ub 256` |
| Slots | `-np 1` |
| Flash Attention | `on` |
| Sampling | `temperature=0.3`, `top_p=0.95`, `top_k=40` для server; quality harness використовує `temperature=0` |

### GPU guard і benchmark mode

У WS активний `nvidia-cuda-mps.service`; MPS control socket протягом тестів
повертав **`50.0`**. Для штатного сервісу `ExecStart` проходить через
`/usr/local/bin/ws-gpu-task-50`.

Цей wrapper є host governor, а не жорстким обмеженням поля
`nvidia-smi utilization.gpu`:

```text
pause_at=45
resume_at=35
```

Він кожні приблизно 50 мс робить `STOP` процесу при utilization понад 45% і
відновлює його після падіння до 35% або нижче. Через це штатний guarded service
такий, як задумано політикою, працює імпульсами.

Для **об'єктивного steady-state benchmark** за явним дозволом користувача
використано окреме тимчасове вікно:

- MPS policy залишена `50%`;
- `CUDA_DEVICE_MAX_CONNECTIONS=1` залишено;
- host `STOP/CONT` wrapper не запускався;
- кожен тест мав один процес і один slot;
- після кожної серії persistent service і guard відновлювалися.

У цьому режимі `nvidia-smi utilization.gpu` закономірно доходив до 99–100%.
Це **engine-busy telemetry**, а не доказ того, що MPS policy була скасована.

## 3. Артефакти моделей і provenance

### Qwen3.5-9B

| Поле | Значення |
|---|---|
| Official base | [`Qwen/Qwen3.5-9B`](https://huggingface.co/Qwen/Qwen3.5-9B) |
| Runtime artifact | [`unsloth/Qwen3.5-9B-MTP-GGUF`](https://huggingface.co/unsloth/Qwen3.5-9B-MTP-GGUF) |
| Local file | `/mnt/nvme-models/Qwen3.5-9B-MTP-Q4_0.gguf` |
| Quantization | Q4_0 |
| File size | 5,551,599,968 bytes |
| Runtime params | 9,197,093,888 (includes MTP tensors) |
| SHA-256 | `1b69b7e765387778195c044b5aa1db9c5232568f9dbdc4704b940f612b7d7498` |
| Speculation | native `draft-mtp`, `--spec-draft-n-max 2` |

Qwen standard Q4_0 GGUF також був завантажений як ablation:
`/mnt/nvme-models/Qwen3.5-9B-Q4_0.gguf`, SHA-256
`17670346b4260ddcb0173965145155885024f3c9a4a24389a3370751edbcde24`.
Основні фінальні цифри нижче використовують MTP artifact, а не цей standard
файл.

### Gemma 4 12B

| Поле | Значення |
|---|---|
| Official base | [`google/gemma-4-12B-it`](https://huggingface.co/google/gemma-4-12B-it) |
| Official runtime GGUF | [`google/gemma-4-12B-it-qat-q4_0-gguf`](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf) |
| Local file | `/mnt/nvme-models/gemma-4-12b-it-qat-q4_0.gguf` |
| Quantization | Google QAT Q4_0 |
| File size | 6,975,879,296 bytes |
| Runtime params | 11,907,350,576 |
| SHA-256 | `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b` |
| Speculation | standard decode; MTP context creation failed closed |

Обидва основні артефакти — Q4_0, але вони не є bit-identical quantization
pipeline: Qwen — Unsloth conversion від official Qwen base, Gemma — official
Google QAT GGUF. Це важливе обмеження для інтерпретації якості.

## 4. Methodology

### 4.1 Official llama.cpp throughput test

Використано `llama-bench` із BeeLlama build `85e22ea`. Upstream документація
пояснює, що `pp` — prompt processing, `tg` — text generation, `-d` — context
depth, а JSON містить індивідуальні samples кожного repetition:

- [llama.cpp `tools/llama-bench` README](https://github.com/ggml-org/llama.cpp/tree/master/tools/llama-bench)
- [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

Параметри: 5 repetitions, однакові `pp=128/512/2048`, `depth=2048/8192`,
`tg=128`, batch `512/256`, full GPU offload (`-ngl 999`) і q8 KV. У таблицях
наведено median samples; всі raw JSON залишено локально під
`/tmp/opencode/llm-compare-20260906/` і не публікуються разом із звітом.

### 4.2 Real local task suite

`benchmarks/compare_llms.py` виконує однакові 8 задач через OpenAI-compatible
`/v1/chat/completions`, `seed=42`, `temperature=0`, `max_tokens=4096`:

1. Python SHA-256 function contract;
2. safe division debugging contract;
3. exact structured JSON;
4. exact arithmetic;
5. Ukrainian infrastructure explanation;
6. real function-call schema;
7. buried long-context retrieval needle;
8. safe model-swap operations checklist.

Grader не запускає generated Python і не передає model output у shell. Python
оцінюється через `ast.parse`, JSON — через стандартний parser, інші задачі —
через обмежені текстові contracts. Тому це machine-only functional contract
test, а не SWE-bench і не human quality score.

### 4.3 Independent UA↔EN reference test

Для багатомовності використано original **FLORES-200 devtest** corpus. Офіційний
опис підтверджує 1,012 aligned devtest sentences; reference text не генерується
моделлю:

- [FLORES-200 dataset card](https://huggingface.co/datasets/Muennighoff/flores200)
- [Current FLORES+ card](https://huggingface.co/datasets/openlanguagedata/flores_plus)
- [Original NLLB/FLORES paper](https://arxiv.org/abs/2207.04672)

Використано original public archive
[`flores200_dataset.tar.gz`](https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz):

```text
archive SHA-256: b8b0b76783024b85797e5cc75064eb83fc5288b41e9654dabc7be6ae944011f6
eng_Latn.devtest SHA-256: 612e9fbe87997617c0fa8fa8929654a4f49b728d96738112c2b86ef6a1d78d88
ukr_Cyrl.devtest SHA-256: 7bb8f160a455fca27032bdd292dd65838b7aa5a8324c6aedd03ccdf92e20dbc4
```

Щоб тест був bounded, але не залежав лише від початкових рядків, вибрано 50
aligned IDs: `1, 21, 41, ..., 981`. Для кожного ID виконано обидва напрямки:
`ukr_Cyrl→eng_Latn` та `eng_Latn→ukr_Cyrl`. Отже кожна модель отримала 100
translation requests, а обидві — той самий input/reference set.

Scoring: `sacrebleu==2.5.1`, corpus BLEU з tokenizer `13a` і chrF++ з
`char_order=6`, `word_order=2`, `beta=2`. Це **bounded subset result**, не
офіційний full-corpus leaderboard score.

## 5. Official llama-bench: чиста швидкість

### Prompt processing (pp)

| Context depth | Prompt | Qwen3.5-9B MTP (t/s) | Gemma 4 12B (t/s) | Qwen/Gemma |
|---:|---:|---:|---:|---:|
| 2,048 | 128 | **1,444.95** | 963.81 | 1.50× |
| 2,048 | 512 | **1,534.30** | 1,056.18 | 1.45× |
| 2,048 | 2,048 | **1,516.10** | 1,050.92 | 1.44× |
| 8,192 | 128 | **1,320.10** | 862.43 | 1.53× |
| 8,192 | 512 | **1,401.62** | 944.55 | 1.48× |
| 8,192 | 2,048 | **1,396.65** | 940.56 | 1.49× |

### Token generation (tg)

| Context depth | Tokens | Qwen3.5-9B MTP (t/s) | Gemma 4 12B (t/s) | Qwen/Gemma |
|---:|---:|---:|---:|---:|
| 2,048 | 128 | **64.332** | 38.696 | **1.66×** |
| 8,192 | 128 | **58.750** | 38.149 | **1.54×** |

Падіння Qwen від depth 2K до 8K: приблизно 8.7%. Gemma майже не падає на
цьому короткому `tg=128` профілі, але початкова швидкість значно нижча.

## 6. Real task comparison через API

### 6.1 Result table

| Task | Qwen MTP | Qwen gen | Qwen MTP accept | Gemma | Gemma gen | Interpretation |
|---|---|---:|---:|---|---:|---|
| Code generation | PASS | 82.76 t/s | 79.11% | PASS | 39.13 t/s | Обидва дали валідний static Python contract |
| Debugging | PASS | 86.14 t/s | 83.90% | PASS | 39.22 t/s | Обидва знайшли zero-denominator guard |
| Structured JSON | PASS | 84.12 t/s | 81.37% | PASS | 39.35 t/s | Exact schema matched |
| Math | PASS | 90.91 t/s | **92.76%** | PASS | 39.19 t/s | Exact `346` |
| Ukrainian explanation | PASS | 82.73 t/s | 80.12% | PASS | 38.70 t/s | Language coverage contract matched |
| Tool call | PASS | 71.56 t/s | 80.00% | PASS | 39.61 t/s | Structured `restart_service` / `llama-server` / OOM contract |
| Long-context retrieval | PASS | 74.75 t/s | 83.79% | PASS | 35.73 t/s | Needle hidden only in final record |
| Operations checklist | **FAIL** | 87.80 t/s | 89.10% | PASS | 38.66 t/s | Qwen omitted literal `rollback` |
| **Total** | **7/8** | — | — | **8/8** | — | Contract pass rate only |

### 6.2 What this does and does not prove

- Qwen MTP roughly doubles API decode speed on this workload.
- Gemma produced a complete answer for the operations checklist where Qwen did
  not include the required literal `rollback`.
- This is not a claim that Gemma wins every coding or agent benchmark: the
  grader checks syntax/contract, not execution or human preference.
- The long-context test is now valid as a retrieval check: the marker appears
  exactly once, in the buried record, not in the leading instruction.

## 7. FLORES-200 UA↔EN: model vs independent reference

### 7.1 Corpus scores

| Direction | Model | Items | BLEU | chrF++ | Target-script compliance |
|---|---|---:|---:|---:|---:|
| Ukrainian → English | Qwen3.5-9B MTP | 50 | 43.5096 | 66.6242 | 100% |
| Ukrainian → English | Gemma 4 12B | 50 | **44.7479** | **67.2039** | 100% |
| English → Ukrainian | Qwen3.5-9B MTP | 50 | **26.9537** | **55.0531** | 100% |
| English → Ukrainian | Gemma 4 12B | 50 | 26.8086 | 54.5833 | 100% |

### 7.2 Aligned pairwise wins

For each of the same 100 aligned translations, the higher sentence-level score
wins. Ties use exact equality of the rounded metric emitted by the harness.

| Direction | Metric | Qwen wins | Gemma wins | Ties | Mean Qwen−Gemma |
|---|---|---:|---:|---:|---:|
| Ukrainian → English | sentence BLEU | 20 | **23** | 7 | -0.1508 |
| Ukrainian → English | sentence chrF++ | 22 | **23** | 5 | -0.2530 |
| English → Ukrainian | sentence BLEU | 23 | **26** | 1 | -0.6109 |
| English → Ukrainian | sentence chrF++ | **26** | 24 | 0 | -0.3452 |
| **Both directions** | sentence BLEU | 43 | **49** | 8 | -0.3809 |
| **Both directions** | sentence chrF++ | **48** | 47 | 5 | -0.2991 |

The corpus and pairwise values are close. Gemma has a small BLEU advantage in
this sample overall, while chrF++ is effectively a split decision. The result
supports a nuanced recommendation: Gemma is a strong translation-quality
choice; Qwen is the faster interactive bilingual service.

### 7.3 Translation throughput

The same FLORES request shape was run with thinking disabled in the request
template (`enable_thinking=false`, `preserve_thinking=false`) so that the metric
measures translation rather than an arbitrary reasoning budget.

| Model | `ukr→en` mean decode | `en→ukr` mean decode | Notes |
|---|---:|---:|---|
| Qwen3.5-9B MTP | 84.36 t/s | 75.55 t/s | Native MTP active |
| Gemma 4 12B | 41.22 t/s | 40.65 t/s | Standard decode |

## 8. Speculative decoding result

### Qwen MTP gate

Qwen MTP started successfully with the target model itself as the MTP source:

```text
--spec-type draft-mtp
--spec-draft-n-max 2
-ctkd q8_0 -ctvd q8_0
```

On the math probe:

| Metric | Value |
|---|---:|
| Draft tokens generated | 304 |
| Draft tokens accepted | 282 |
| Acceptance | **92.76%** |
| Decode (dedicated compatibility probe) | **91.97 t/s** |
| Decode (final 8-task suite, math row) | **90.91 t/s** |

The two decode values are intentionally not collapsed: the first is a dedicated
short probe, while the second is the final suite row with its own server state
and request timing.

Across the 8 quality tasks, Qwen MTP acceptance ranged from 79.11% to 92.76%
and remained active in every request (`draft_n` / `draft_n_accepted` present).

### Gemma MTP gate

The official Google QAT GGUF was tested with the same native MTP invocation.
Startup failed closed with:

```text
load_model: failed to create MTP context
llama_server: exiting due to model loading error
```

No unofficial drafter was substituted. Gemma results in this report are
therefore standard-decode results. Google’s launch material describes Gemma 4
12B as drafter-ready, but that does not prove that this particular downloaded
GGUF contains a compatible self-MTP context on this BeeLlama build.

## 9. GPU/VRAM/power evidence

The following values come from 200-ms `nvidia-smi` samples during the final
steady API quality runs. They are workload telemetry, not a power-limit claim.

| Model/profile | Samples | Util max | Samples ≥90% | VRAM peak | Free minimum | Temp peak | Power peak |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.5-9B MTP + MTP API | 624 | 99% | 79.81% | 8,650 MiB | 2,179 MiB | 66°C | 258.72 W |
| Gemma 4 12B standard API | 618 | 100% | 20.71% | 9,714 MiB | 1,115 MiB | 65°C | 242.92 W |

Both profiles pass the operational 1 GiB VRAM safety buffer in the final API
run. Gemma is close to the boundary; the conservative `-b 512 -ub 256` profile
is intentional. The old Gemma `-b 1024` probe left only 907 MiB free and was not
accepted as the final profile.

The monitored steady probes reached 100% `nvidia-smi` utilization for the
standard-Qwen ablation and Gemma; the final Qwen MTP API suite reached 99%.
MPS remained `50.0` before and after. This is the evidence that the benchmark
was not being dosed by the 45/35 host governor in steady mode.

## 10. Driver, service, and configuration changes

### NVIDIA driver

No driver package was changed. The installed kernel driver is `610.57.04`; APT
exposed `610.43.02` as the candidate, which would be a downgrade. Applying it
would violate the update goal and risk the CUDA runtime. The final report
therefore records a verified **no-op**, not a false “driver updated” claim.

### Persistent service

Installed and validated:

| Artifact | Final state |
|---|---|
| `/usr/local/libexec/start_llama_qwen35.sh` | Qwen3.5-9B MTP default, `32768` context, q8 KV, batch 512/256 |
| `/etc/systemd/system/llama-server.service` | `enabled` + `active` |
| `ExecStart` | `/usr/local/bin/ws-gpu-task-50 /usr/local/libexec/start_llama_qwen35.sh` |
| API | `http://127.0.0.1:8080`, `/v1/models` ready |
| MPS | `nvidia-cuda-mps.service` `enabled` + `active`, default `50.0` |
| Guard marker | `WS_GPU_GUARD_ACTIVE=1`; direct script launch refuses without it |
| Service user | `root` retained for BeeLlama client compatibility with root-owned MPS control socket |
| Runtime | `draft-mtp` initialized, model loaded, no final OOM |
| systemd hardening | `NoNewPrivileges`, `ProtectHome`, `ProtectSystem=strict`, `MemoryMax=32G`, `TasksMax=256` |

The service remains `User=root` because a controlled non-root probe hung while
the BeeLlama CUDA client connected to the root-owned MPS control socket. No
unverified permission workaround was applied. The network exposure was still
reduced to loopback and the executable/model paths are no longer under `/root`.
The root residual is an explicit follow-up risk for an MPS service redesign, not
a claim of full least privilege.

Reviewable source templates are in:

- [`start_llama_qwen35.sh`](./start_llama_qwen35.sh)
- [`llama-server-qwen35.service`](./llama-server-qwen35.service)

Backups created on WS before the two replacements:

- `/root/start_llama.sh.pre-qwen35-20260906`
- `/root/llama-server.service.pre-qwen35-20260906`
- `/root/start_llama.sh.pre-mtp-20260906`
- `/root/llama-server.service.pre-mtp-20260906`
- `/root/start_llama.sh.pre-hardening-20260906`
- `/root/llama-server.service.pre-hardening-20260906`

Operational caveat: stopping the systemd unit while the wrapper is in its
polling path can produce the wrapper message
`nvidia-smi utilization query failed` and a transient systemd `failed` state.
The exact unit was reset and restarted after every isolated model swap; final
state is active and healthy. This caveat is not counted as a model failure.

The script supports a safe Gemma override without editing the file:

```bash
MODEL_PATH=/mnt/nvme-models/gemma-4-12b-it-qat-q4_0.gguf \
SPEC_TYPE=none \
WS_GPU_GUARD_ACTIVE=1 \
/usr/local/bin/ws-gpu-task-50 /usr/local/libexec/start_llama_qwen35.sh
```

## 11. Reproduction

### Throughput matrix

Run from WS after stopping the persistent service for exclusive VRAM access;
for steady results export MPS variables but do not use the host pause wrapper:

```bash
env CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=50 CUDA_DEVICE_MAX_CONNECTIONS=1 \
  /root/beellama.cpp/build/bin/llama-bench \
  -m /mnt/nvme-models/Qwen3.5-9B-MTP-Q4_0.gguf \
  -p 128,512,2048 -n 128 -d 2048,8192 \
  -ngl 999 -t 10 -C 0x3ff --cpu-strict 1 \
  -fa on -ctk q8_0 -ctv q8_0 -b 512 -ub 256 -r 5 -o json
```

Use the Gemma path in `-m` for the second run. The production service must be
restored through `systemctl enable --now llama-server.service` afterward.

### Local task suite

```bash
python3 benchmarks/compare_llms.py \
  --base-url http://127.0.0.1:8080 \
  --model-id Qwen3.5-9B-MTP-Q4_0.gguf \
  --model-file /mnt/nvme-models/Qwen3.5-9B-MTP-Q4_0.gguf \
  --engine-build 85e22ea \
  --run-profile steady-mps50-no-host-pause \
  --output /tmp/compare.json \
  --repeats 1 --max-tokens 4096 --timeout 900
```

### FLORES reference test

```bash
python3 -m venv /tmp/flores-venv
/tmp/flores-venv/bin/python -m pip install 'sacrebleu==2.5.1'
/tmp/flores-venv/bin/python benchmarks/run_flores_ua_en.py \
  --base-url http://127.0.0.1:8080 \
  --model-id Qwen3.5-9B-MTP-Q4_0.gguf \
  --model-file /mnt/nvme-models/Qwen3.5-9B-MTP-Q4_0.gguf \
  --engine-build 85e22ea \
  --run-profile steady-mps50-no-host-pause \
  --ukr-file /path/to/ukr_Cyrl.devtest \
  --eng-file /path/to/eng_Latn.devtest \
  --output /tmp/flores-result.json \
  --limit 50 --stride 20 --max-tokens 256 --seed 42
```

Run the command once per model with the same corpus, then derive the pairwise
comparison from the checked-in comparator:

```bash
python3 benchmarks/compare_flores_runs.py \
  --left /tmp/qwen-flores.json \
  --right /tmp/gemma-flores.json \
  --output /tmp/flores-pairwise.json
```

The comparator refuses different dataset contracts, sample IDs, seeds, runtime
profiles, or model digests.

## 12. Content-addressed evidence

Raw model outputs and telemetry CSVs remain local under
`/tmp/opencode/llm-compare-20260906/`. The report is accompanied by these
content hashes for the non-secret derived evidence:

The same provenance is machine-readable in
[`evidence-manifest-2026-09-06.json`](./evidence-manifest-2026-09-06.json),
which also pins the engine, driver, MPS policy, model digests and dataset
snapshot.

| Evidence | SHA-256 |
|---|---|
| Qwen MTP `llama-bench` matrix | `905448e0c6001628524ad9e4212ba2a3fbd8ce9f587c9214736a0191dce5314a` |
| Gemma `llama-bench` matrix | `d70ad7181d2624be79e37eb710702ffffe6c534d06614fb9598654bf47606df9` |
| Qwen MTP strict quality JSON | `5bed07a8db8ca174d9f5c46f4404610bd86e077712edfc4ed23451602b70530b` |
| Gemma strict quality JSON | `ebca262c7b3b95616a7504473d19b47e04e9f43a0dedd81888ac4ea1f55ee1c4` |
| Qwen strict FLORES JSON | `bf040a603a06ca0c534493d8369673ff48164c82a8b97ec0eb7154ab7afe0cf7` |
| Gemma strict FLORES JSON | `cb016d9dcacc99372a4101ddf389e864d7b9677400c9dfcc0a85670516f98a04` |
| Derived FLORES pairwise JSON | `c658aba6fb6d37921da0b5fcbb31d9b69be7ef75fa7d909410326dc52ec55ee1` |

## 13. Limitations and next gate

1. FLORES result is a deterministic 50/1012 subset in each direction, not the
   full 1,012-row benchmark or a leaderboard submission.
2. BLEU penalizes valid paraphrases; chrF++ is included to reduce dependence on
   exact word segmentation. No human adjudication was performed.
3. The local code/agent grader is static and safe by design; it does not run
   generated code, shell commands, or a repository patch.
4. The comparison is text-only. Qwen3.5 and Gemma 4 are multimodal families,
   but no image/audio benchmark was run because the requested WS comparison
   targeted llama.cpp text/agent serving.
5. Qwen’s practical speed includes native MTP while Gemma ran standard decode.
   The no-spec `llama-bench` table is the cleaner engine comparison; API MTP
   figures answer the deployable-service question.
6. CI now runs the pure helper/unit suite, but a future quality gate should add
   executable sandbox tests for generated code contracts and a larger/full
   FLORES devtest run if the runtime budget permits.

## 14. Final recommendation for WS

- **Default interactive/agent model:** Qwen3.5-9B MTP. It is active, healthy,
  fits with a multi-GiB VRAM buffer, and is approximately 1.5–1.7× faster even
  without speculation and about 2× faster through the API with MTP.
- **Translation-quality alternative:** Gemma 4 12B. On this bounded reference
  sample it has a small BLEU/chrF++ edge in `ukr→en` and passed all 8 local
  contracts, at the cost of roughly half the decode throughput.
- **Resource policy:** keep steady benchmark mode opt-in only. Production
  service remains behind `ws-gpu-task-50`; do not interpret `nvidia-smi` 100%
  as a reason to remove MPS or the host governor.

---

Built in Ukraine under air raid sirens & blackouts ⚡ © 2026 Weby Homelab
