# Strata standard benchmark: NVIDIA GeForce RTX 5070 Ti

Protocol `strata-qwen38-thinking-v1-draft.1` (draft), run `20261118T205938Z-74bd1be5`, started 2026-11-18T20:59:38Z. **Status: complete.**

Written by `strata bench run`. The machine-readable result is [results.json](results.json); every request, its raw usage and timings and the client event offsets are in [outputs.jsonl](outputs.jsonl).

## Hardware and software

- GPU: NVIDIA GeForce RTX 5070 Ti (15.9 GiB dedicated)
- CPU: AMD Ryzen Threadripper PRO 3995WX 64-Cores; RAM: 247.2 GiB
- Storage of the model files: nvme KINGSTON SNV3S500G (nvme)
- OS: Ubuntu 26.04.1 LTS 7.0.0-43-generic; drivers: gpu-driver 615.71.09; runtime: cuda 13.4
- Strata commit: `870aedd9e1ebe1c91f94da93b59af17729f6c5c0`; engine 0.1.60; source build
- Background work: not measured

## Model and configuration

- Model: qwen3.8-flash-next-unsloth-q8_0; quantization Q8_0; revision not measured; source revision not measured
- Files: `Qwen3.8-Flash-Next-Q8_0-00001-of-00006.gguf` `2dabcbb53ca537a7...`; `Qwen3.8-Flash-Next-Q8_0-00002-of-00006.gguf` `494ca4ed3dbf97bc...`; `Qwen3.8-Flash-Next-Q8_0-00003-of-00006.gguf` `34efd79a80a1ce54...`; `Qwen3.8-Flash-Next-Q8_0-00004-of-00006.gguf` `bfa634025fabbd26...`; `Qwen3.8-Flash-Next-Q8_0-00005-of-00006.gguf` `232a8f14cc0fa426...`; `Qwen3.8-Flash-Next-Q8_0-00006-of-00006.gguf` `538a93bca9180649...`
- Track: **custom** (no notes given by the operator)
- Context 32768 tokens; server capacity 1 slot(s)
- Sampling: temperature 1.0, top_p 0.95, top_k 20, min_p 0.0, presence_penalty 0.0, repetition_penalty 1.0, reasoning_effort xhigh; thinking on, preserved
- Engine options: `config.json`; chat template: `provenance/chat_template.jinja`

## Method

The frozen requests of `bench/prompts/standard-v1` (corpus `e75eff8b9feea04f...`) were sent over loopback HTTP, streaming, one at a time, in this order: 1 warm-up (excluded), 3 repetitions of the short, 4K and 16K prompts, and the twelve sanity checks. Prompt and decode speed are the engine's own `timings`; time to first token is the client's monotonic clock from dispatch to the first nonempty reasoning, answer or tool-call delta. No request was retried. Time after the model loaded: 3 min 5 s.

## Results

| Case | Prompt tok/s | Decode tok/s | TTFT s | First answer s | Total s | Capped |
| --- | --- | --- | --- | --- | --- | --- |
| short | n/a | 50.0 (48.2-52.6) n=3 | 0.69 (0.57-0.73) n=3 | 3.20 (2.46-3.22) n=3 | 6.9 (6.7-9.1) n=3 | 0/3 |
| prompt-4k | 858.7 (850.4-858.9) n=3 | 46.1 (45.7-52.8) n=3 | 4.80 (4.80-4.85) n=3 | 11.07 (11.07-11.07) n=1 | 15.9 (14.5-16.0) n=3 | 3/3 |
| prompt-16k | 1732.6 (1732.3-1733.1) n=3 | 48.3 (47.4-50.0) n=3 | 9.50 (9.49-9.51) n=3 | 17.65 (14.89-19.06) n=3 | 20.1 (19.7-20.3) n=3 | 3/3 |

Cells are median (min-max) n=samples. Short is a prompt of about 80 tokens: its prompt rate is dominated by the fixed cost of a request, so it is not shown; read prompt speed from prompt-4k and prompt-16k. Capped = requests that reached the 512-token cap, reasoning and answer together. A capped request's total time is the time to the cap, not to an answer, and it has no first-answer time when it was still reasoning.

| Phase | Planned | Completed | Truncated | Failed | Skipped |
| --- | ---: | ---: | ---: | ---: | ---: |
| warmup | 1 | 0 | 1 | 0 | 0 |
| performance | 9 | 3 | 6 | 0 | 0 |
| sanity | 12 | 12 | 0 | 0 | 0 |
| concurrency | 0 | 0 | 0 | 0 | 0 |

Sanity checks: **12 of 12**.

| Case | Result | Reason |
| --- | --- | --- |
| I1 | pass | the expected JSON value |
| I2 | pass | the expected JSON value |
| I3 | pass | the expected JSON value |
| I4 | pass | the exact expected text |
| R1 | pass | the exact expected text |
| R2 | pass | the exact expected text |
| R3 | pass | the exact expected text |
| R4 | pass | the expected JSON value |
| T1 | pass | the expected tool call |
| T2 | pass | the expected tool call |
| T3 | pass | the expected tool call |
| T4 | pass | the expected tool call |

## Failures, exclusions and limitations

- No request failed.
- Excluded from speed summaries: performance-prompt-4k-r2: first_answer_s is not available for this request
- Excluded from speed summaries: performance-prompt-4k-r3: first_answer_s is not available for this request
- Prompt-prefix reuse is the shared template prefix only; the cache was not emptied between requests, and the expert cache stays warm and evolves. These are not cold-model measurements.
- Output caps include reasoning; a request that reaches its cap is `truncated` and fails its sanity check.
- The runner cannot see other programs on the machine, the repeat-stop and loop-recovery switches of the server, or the quantization repository's revision; see `missing` in results.json for every value it could not read.
- The server had answered 7 request(s) before this run.
