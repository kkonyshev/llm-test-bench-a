# Strata standard benchmark: NVIDIA GeForce RTX 5070 Ti

Protocol `strata-qwen38-thinking-v1-draft.1` (draft), run `20261102T233858Z-71ceb661`, started 2026-11-02T23:38:58Z. **Status: complete.**

Written by `strata bench run`. The machine-readable result is [results.json](results.json); every request, its raw usage and timings and the client event offsets are in [outputs.jsonl](outputs.jsonl).

## Hardware and software

- GPU: NVIDIA GeForce RTX 5070 Ti (15.9 GiB dedicated)
- CPU: AMD Ryzen 7 9800X3D 8-Core Processor; RAM: 123.5 GiB
- Storage of the model files: not measured
- OS: Fedora Linux 44 (Workstation Edition) 7.1.13-200.fc44.x86_64; drivers: gpu-driver 615.71.09; runtime: cuda 13.4
- Strata commit: `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`; engine 0.1.55; release build
- Background work: not measured

## Model and configuration

- Model: qwen3.8-flash-next-nvfp4-nvfp4-nvidia; quantization NVFP4; revision not measured; source revision not measured
- Files: `qwen-nvidia-nvfp4-dense.gguf` `0f795ca0cbb908e0...`
- Track: **custom** (no notes given by the operator)
- Context 131072 tokens; server capacity 4 slot(s)
- Sampling: temperature 1.0, top_p 0.95, top_k 20, min_p 0.0, presence_penalty 0.0, repetition_penalty 1.0, reasoning_effort xhigh; thinking on, preserved
- Engine options: `config.json`; chat template: `provenance/chat_template.jinja`

## Method

The frozen requests of `bench/prompts/standard-v1` (corpus `e75eff8b9feea04f...`) were sent over loopback HTTP, streaming, one at a time, in this order: 1 warm-up (excluded), 3 repetitions of the short, 4K and 16K prompts, and the twelve sanity checks. Prompt and decode speed are the engine's own `timings`; time to first token is the client's monotonic clock from dispatch to the first nonempty reasoning, answer or tool-call delta. No request was retried. Time after the model loaded: 2 min 53 s.

## Results

| Case | Prompt tok/s | Decode tok/s | TTFT s | First answer s | Total s | Capped |
| --- | --- | --- | --- | --- | --- | --- |
| short | n/a | 52.9 (51.7-59.2) n=3 | 0.96 (0.91-0.97) n=3 | 2.74 (2.57-4.02) n=3 | 8.6 (5.8-8.7) n=3 | 0/3 |
| prompt-4k | 1567.3 (1562.5-1567.5) n=3 | 55.9 (54.6-56.5) n=3 | 2.64 (2.64-2.65) n=3 | 7.98 (6.26-8.70) n=3 | 11.8 (11.2-12.0) n=3 | 2/3 |
| prompt-16k | 1656.2 (1654.0-1662.7) n=3 | 54.9 (52.9-58.2) n=3 | 9.93 (9.89-9.94) n=3 | 14.56 (12.87-16.25) n=2 | 19.2 (17.8-19.6) n=3 | 2/3 |

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
- Excluded from speed summaries: performance-prompt-16k-r2: first_answer_s is not available for this request
- Prompt-prefix reuse is the shared template prefix only; the cache was not emptied between requests, and the expert cache stays warm and evolves. These are not cold-model measurements.
- Output caps include reasoning; a request that reaches its cap is `truncated` and fails its sanity check.
- The runner cannot see other programs on the machine, the repeat-stop and loop-recovery switches of the server, or the quantization repository's revision; see `missing` in results.json for every value it could not read.
- The server had answered 7 request(s) before this run.
