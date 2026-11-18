# Strata standard benchmark: NVIDIA GeForce RTX 5070 Ti

Protocol `strata-qwen38-thinking-v1-draft.1` (draft), run `20261118T192522Z-da757a97`, started 2026-11-18T19:25:22Z. **Status: complete.**

Written by `strata bench run`. The machine-readable result is [results.json](results.json); every request, its raw usage and timings and the client event offsets are in [outputs.jsonl](outputs.jsonl).

## Hardware and software

- GPU: NVIDIA GeForce RTX 5070 Ti (15.9 GiB dedicated)
- CPU: AMD Ryzen Threadripper PRO 3995WX 64-Cores; RAM: 247.2 GiB
- Storage of the model files: nvme KINGSTON SNV3S500G (nvme)
- OS: Ubuntu 26.04.1 LTS 7.0.0-43-generic; drivers: gpu-driver 615.71.09; runtime: cuda 13.4
- Strata commit: `870aedd9e1ebe1c91f94da93b59af17729f6c5c0`; engine 0.1.60; source build
- Background work: not measured

## Model and configuration

- Model: qwen3.8-flash-next-nvfp4-nvfp4-nvidia; quantization NVFP4; revision not measured; source revision not measured
- Files: `qwen-nvidia-nvfp4-dense.gguf` `0f795ca0cbb908e0...`
- Track: **custom** (no notes given by the operator)
- Context 32768 tokens; server capacity 1 slot(s)
- Sampling: temperature 1.0, top_p 0.95, top_k 20, min_p 0.0, presence_penalty 0.0, repetition_penalty 1.0, reasoning_effort xhigh; thinking on, preserved
- Engine options: `config.json`; chat template: `provenance/chat_template.jinja`

## Method

The frozen requests of `bench/prompts/standard-v1` (corpus `e75eff8b9feea04f...`) were sent over loopback HTTP, streaming, one at a time, in this order: 1 warm-up (excluded), 3 repetitions of the short, 4K and 16K prompts, and the twelve sanity checks. Prompt and decode speed are the engine's own `timings`; time to first token is the client's monotonic clock from dispatch to the first nonempty reasoning, answer or tool-call delta. No request was retried. Time after the model loaded: 1 min 56 s.

## Results

| Case | Prompt tok/s | Decode tok/s | TTFT s | First answer s | Total s | Capped |
| --- | --- | --- | --- | --- | --- | --- |
| short | n/a | 65.6 (58.5-66.5) n=3 | 0.47 (0.37-0.50) n=3 | 1.96 (1.59-3.01) n=3 | 5.2 (4.7-6.0) n=3 | 0/3 |
| prompt-4k | 1567.5 (1566.6-1570.4) n=3 | 67.7 (67.4-70.8) n=3 | 2.64 (2.64-2.64) n=3 | 7.03 (6.21-8.50) n=3 | 10.2 (9.5-10.2) n=3 | 2/3 |
| prompt-16k | 3863.5 (3863.0-3864.2) n=3 | 64.9 (63.2-67.6) n=3 | 4.28 (4.28-4.28) n=3 | 7.75 (7.16-8.34) n=2 | 11.8 (11.6-12.4) n=3 | 2/3 |

Cells are median (min-max) n=samples. Short is a prompt of about 80 tokens: its prompt rate is dominated by the fixed cost of a request, so it is not shown; read prompt speed from prompt-4k and prompt-16k. Capped = requests that reached the 512-token cap, reasoning and answer together. A capped request's total time is the time to the cap, not to an answer, and it has no first-answer time when it was still reasoning.

| Phase | Planned | Completed | Truncated | Failed | Skipped |
| --- | ---: | ---: | ---: | ---: | ---: |
| warmup | 1 | 0 | 1 | 0 | 0 |
| performance | 9 | 5 | 4 | 0 | 0 |
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
- Excluded from speed summaries: performance-prompt-16k-r3: first_answer_s is not available for this request
- Prompt-prefix reuse is the shared template prefix only; the cache was not emptied between requests, and the expert cache stays warm and evolves. These are not cold-model measurements.
- Output caps include reasoning; a request that reaches its cap is `truncated` and fails its sanity check.
- The runner cannot see other programs on the machine, the repeat-stop and loop-recovery switches of the server, or the quantization repository's revision; see `missing` in results.json for every value it could not read.
- The server had answered 7 request(s) before this run.
