# Qwen3.5 9B vs Gemma 4 12B — WS benchmark

**Дата:** 6 вересня 2026 року

## Короткий висновок

- **Qwen3.5-9B MTP** швидший: 64.33 проти 38.70 t/s у генерації на
  глибині контексту 2K; 58.75 проти 38.15 t/s на 8K.
- **Gemma 4 12B** має невелику перевагу в перекладі українська → англійська.
- **Qwen** трохи кращий у напрямку англійська → українська за BLEU/chrF++.
- Для інтерактивного inference на WS практичніший Qwen; для перекладу якість
  двох моделей близька.

## Умови тесту

| Параметр | Значення |
|---|---|
| Host | WS |
| GPU | NVIDIA GeForce RTX 2080 Ti, 11 GB |
| CPU | Intel Xeon E5-2666 v3, 10 фізичних ядер |
| RAM | 128 GB DDR4 ECC |
| NVIDIA driver | 610.57.04 |
| CUDA | 13.3 |
| Engine build | BeeLlama.cpp `85e22ea` |
| GPU offload | повний (`-ngl 999`) |
| Context | 32,768 tokens |
| KV cache | q8_0 K/V |
| Batch | 512, ubatch 256 |
| Slots | 1 |
| Sampling для quality tests | temperature 0, seed 42 |

Для вимірювання steady-state навантаження використовувався MPS з default
`50%`. Host governor, який дозує процес імпульсами STOP/CONT, у вимірювальному
вікні не застосовувався. Тому `nvidia-smi` показував фактичний engine-busy
99–100%, а MPS policy залишалась `50.0%`.

## Моделі

### Qwen3.5-9B MTP

- Official base: [`Qwen/Qwen3.5-9B`](https://huggingface.co/Qwen/Qwen3.5-9B)
- GGUF: [`unsloth/Qwen3.5-9B-MTP-GGUF`](https://huggingface.co/unsloth/Qwen3.5-9B-MTP-GGUF)
- Quantization: Q4_0
- Runtime file: `Qwen3.5-9B-MTP-Q4_0.gguf`
- File size: 5,551,599,968 bytes
- SHA-256: `1b69b7e765387778195c044b5aa1db9c5232568f9dbdc4704b940f612b7d7498`
- Native MTP: `draft-mtp`, `n-max=2`

### Gemma 4 12B

- Official base: [`google/gemma-4-12B-it`](https://huggingface.co/google/gemma-4-12B-it)
- GGUF: [`google/gemma-4-12B-it-qat-q4_0-gguf`](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf)
- Quantization: Google QAT Q4_0
- Runtime file: `gemma-4-12b-it-qat-q4_0.gguf`
- File size: 6,975,879,296 bytes
- SHA-256: `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b`
- MTP: incompatible on this GGUF/runtime; standard decode used

Обидві моделі тестувалися у форматі Q4_0. Quantization pipeline різний: Qwen
завантажений як Unsloth GGUF від official base, Gemma — official Google QAT
GGUF.

## 1. Офіційний llama.cpp throughput test

Використано upstream `llama-bench`. Документація: [llama.cpp
llama-bench](https://github.com/ggml-org/llama.cpp/tree/master/tools/llama-bench).
Кожен профіль повторювався 5 разів; у таблиці наведено median.

### Prompt processing

| Context depth | Prompt tokens | Qwen3.5-9B MTP | Gemma 4 12B | Qwen/Gemma |
|---:|---:|---:|---:|---:|
| 2,048 | 128 | **1,444.95 t/s** | 963.81 t/s | 1.50× |
| 2,048 | 512 | **1,534.30 t/s** | 1,056.18 t/s | 1.45× |
| 2,048 | 2,048 | **1,516.10 t/s** | 1,050.92 t/s | 1.44× |
| 8,192 | 128 | **1,320.10 t/s** | 862.43 t/s | 1.53× |
| 8,192 | 512 | **1,401.62 t/s** | 944.55 t/s | 1.48× |
| 8,192 | 2,048 | **1,396.65 t/s** | 940.56 t/s | 1.49× |

### Text generation

| Context depth | Generated tokens | Qwen3.5-9B MTP | Gemma 4 12B | Qwen/Gemma |
|---:|---:|---:|---:|---:|
| 2,048 | 128 | **64.332 t/s** | 38.696 t/s | **1.66×** |
| 8,192 | 128 | **58.750 t/s** | 38.149 t/s | **1.54×** |

Це порівняння без speculative decoding, тому воно найкраще показує різницю
самих runtime-моделей. Qwen зберігає перевагу приблизно 1.5×.

## 2. Однакові практичні задачі

Цей набір — локальний machine-graded test, не офіційний leaderboard. Для
кожної моделі використано однакові 8 запитів:

1. генерація Python SHA-256 function;
2. виправлення функції ділення на нуль;
3. exact JSON schema;
4. арифметика;
5. пояснення українською;
6. structured function call;
7. пошук needle у довгому контексті;
8. checklist безпечної заміни моделі.

| Задача | Qwen3.5-9B MTP | Qwen decode | Gemma 4 12B | Gemma decode |
|---|---:|---:|---:|---:|
| Code generation | PASS | 82.97 t/s | PASS | 39.08 t/s |
| Debugging | PASS | 85.83 t/s | PASS | 39.51 t/s |
| Structured JSON | PASS | 83.80 t/s | PASS | 39.65 t/s |
| Math | PASS | 90.56 t/s | PASS | 39.46 t/s |
| Ukrainian explanation | PASS | 82.84 t/s | PASS | 38.91 t/s |
| Structured tool call | PASS | 56.98 t/s | PASS | 39.29 t/s |
| Long-context retrieval | PASS | 75.00 t/s | PASS | 35.99 t/s |
| Operations checklist | **FAIL** | 87.20 t/s | PASS | 38.93 t/s |
| **Разом** | **7/8** | — | **8/8** | — |

Єдина невдача Qwen: у checklist відсутнє буквальне слово `rollback`. Це не
означає, що Gemma краща в усіх agentic-задачах; це результат конкретного
детермінованого contract test.

## 3. Багатомовний тест UA↔EN із reference

Використано human-translated **FLORES-200 devtest** — незалежний reference для
машинного перекладу:

- [FLORES-200 dataset card](https://huggingface.co/datasets/Muennighoff/flores200)
- [FLORES+ dataset card](https://huggingface.co/datasets/openlanguagedata/flores_plus)
- [NLLB/FLORES paper](https://arxiv.org/abs/2207.04672)

Оригінальний devtest містить 1,012 aligned речень. Для bounded тесту вибрано
50 ID: `1, 21, 41, ..., 981`. Обидві моделі отримали однакові 100 запитів:
50 у кожному напрямку.

Reference files:

```text
eng_Latn.devtest SHA-256: 612e9fbe87997617c0fa8fa8929654a4f49b728d96738112c2b86ef6a1d78d88
ukr_Cyrl.devtest SHA-256: 7bb8f160a455fca27032bdd292dd65838b7aa5a8324c6aedd03ccdf92e20dbc4
```

Scoring: SacreBLEU 2.5.1, BLEU tokenizer `13a`; chrF++ з
`char_order=6`, `word_order=2`, `beta=2`. Thinking було вимкнено, щоб тестувати
переклад, а не довжину reasoning.

### Результат проти reference

| Напрямок | Модель | BLEU | chrF++ | Target script |
|---|---|---:|---:|---:|
| Ukrainian → English | Qwen3.5-9B MTP | 43.5096 | 66.6242 | 100% |
| Ukrainian → English | Gemma 4 12B | **44.7479** | **67.2039** | 100% |
| English → Ukrainian | Qwen3.5-9B MTP | **26.9537** | **55.0531** | 100% |
| English → Ukrainian | Gemma 4 12B | 26.8086 | 54.5833 | 100% |

### Model vs model на тих самих реченнях

Для кожного aligned речення перемагала модель із вищим sentence-level score.

| Напрямок | Метрика | Qwen wins | Gemma wins | Ties |
|---|---|---:|---:|---:|
| Ukrainian → English | sentence BLEU | 20 | **23** | 7 |
| Ukrainian → English | sentence chrF++ | 22 | **23** | 5 |
| English → Ukrainian | sentence BLEU | 23 | **26** | 1 |
| English → Ukrainian | sentence chrF++ | **26** | 24 | 0 |
| **Обидва напрямки** | sentence BLEU | 43 | **49** | 8 |
| **Обидва напрямки** | sentence chrF++ | **48** | 47 | 5 |

Повний machine-readable pairwise result: [`flores-pairwise-2026-09-06.json`](./flores-pairwise-2026-09-06.json).

### Translation speed

| Модель | Ukrainian → English | English → Ukrainian |
|---|---:|---:|
| Qwen3.5-9B MTP | **84.58 t/s** | **75.73 t/s** |
| Gemma 4 12B | 41.19 t/s | 40.63 t/s |

## 4. Speculative decoding

Qwen MTP успішно стартував. На окремому math probe:

- draft tokens generated: 304;
- accepted: 282;
- acceptance: **92.76%**;
- decode: **91.97 t/s**.

Для Gemma з тим самим `draft-mtp` запуском отримано `failed to create MTP
context`. Непідтверджений сторонній drafter не використовувався; Gemma цифри
вище — standard decode.

## 5. GPU evidence

У steady window `nvidia-smi` показував реальний engine-busy, а не штучну стелю
50%:

| Модель | Samples | Util max | Samples ≥90% | VRAM peak | Free minimum |
|---|---:|---:|---:|---:|---:|
| Qwen3.5-9B MTP | 627 | 99% | 79.47% | 8,642 MiB | 2,187 MiB |
| Gemma 4 12B | 619 | 100% | 75.36% | 9,714 MiB | 1,115 MiB |

MPS control у цих серіях залишався `50.0`. Значення 99–100% — це engine-busy
telemetry; воно не суперечить MPS compute-share policy.

## Обмеження

1. FLORES показує bounded subset 50/1,012, а не full leaderboard result.
2. BLEU/chrF++ не замінюють human evaluation і можуть штрафувати коректні
   перефразування.
3. Local practical suite перевіряє contracts; generated code не виконується.
4. Порівняння текстове; image/audio можливості моделей не тестувалися.
5. Qwen throughput у practical/API тестах включає native MTP, Gemma працює
   без speculative decoding. No-spec `llama-bench` таблиця є чеснішим порівнянням
   базової швидкості.

## Висновок

- Для швидкого локального coding/agent inference: **Qwen3.5-9B MTP**.
- Для найкращого результату саме в `ukr→en` перекладі: невелика перевага
  **Gemma 4 12B**.
- Для `en→ukr` результати практично рівні; Qwen має малу перевагу за BLEU і
  chrF++.
- Загалом це не безумовна перемога однієї моделі: **Qwen — швидкість,
  Gemma — трохи сильніша reference-relative якість перекладу**.
