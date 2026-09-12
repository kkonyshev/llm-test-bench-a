# Local LLM Bench

A small, self-contained harness for comparing local (Ollama-served) LLMs on
two axes: **coding ability** (build a small REST API to spec, graded by a
fixed pytest suite) and **general reasoning** (12 self-authored logic/math
puzzles, graded by exact-answer matching). Built to let you compare the
*same* models under the *same* tests across different hardware.

## What's in here

```
local-llm-bench/
├── README.md               (this file)
├── HARDWARE.md             (spec of the machine the baseline was measured on)
├── MODELS.md               (exact HF repo/file/size for every model tested)
├── RESULTS.md              (full results, per-model bugs found, methodology notes)
├── setup.sh                (one-time: installs deps, creates shared venv)
├── pull_and_build.sh       (download a GGUF from HF + register it in Ollama)
├── run_detached.sh         (run a benchmark, resilient to session kills)
├── coding-benchmark/
│   ├── spec.md             (the exact task given to the model)
│   ├── test_tasks.py       (23 pytest cases graded against the model's output)
│   └── run_bench.sh        (calls Ollama, extracts code, runs pytest)
└── reasoning-benchmark/
    ├── puzzles.md          (12 puzzles given to the model, answer format spec)
    ├── grade.py            (extracts + grades each puzzle answer)
    └── run_bench.sh        (calls Ollama, runs the grader)
```

## Quick start (reproducing on new hardware)

```bash
cd local-llm-bench
./setup.sh                                     # installs hf CLI + python venv

# Pull + register a model in Ollama (repeat per model — see MODELS.md)
./pull_and_build.sh unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF \
    Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf qwen3-coder-30b-a3b

# Run both benchmarks against it
./run_detached.sh coding-benchmark qwen3-coder-30b-a3b
./run_detached.sh reasoning-benchmark qwen3-coder-30b-a3b
```

Each run prints a live token count, then a final summary (timing + pass
count) to the terminal, and writes everything to
`<benchmark-dir>/runs/<model-tag>/`:

| File | Contents |
|---|---|
| `response.md` | The model's raw output |
| `main.py` (coding only) | The extracted code that was actually tested |
| `timing.json` | Load/prompt/eval duration, tokens generated, tokens/sec |
| `pytest_result.txt` (coding) / `grade_result.txt` (reasoning) | Full test/grading output |
| `wall_clock.txt` | Total wall-clock time for the run |
| `ollama_ps_before.txt` / `ollama_ps_after.txt` | Memory footprint while loaded (`ollama ps`) |

## Checking results

```bash
# Coding: pass/fail count is at the bottom of pytest_result.txt
tail -5 coding-benchmark/runs/<model-tag>/pytest_result.txt

# Reasoning: per-question PASS/FAIL + total is in grade_result.txt
cat reasoning-benchmark/runs/<model-tag>/grade_result.txt

# Speed/timing for either
cat coding-benchmark/runs/<model-tag>/timing.json
```

To compare against the baseline, fill in the same tables from `RESULTS.md`
with your new hardware's numbers — the model list and grading are fixed,
so scores and tok/s are directly comparable (see `HARDWARE.md` for what to
expect to differ vs. not).

## Adding a new model to the comparison

1. Find a GGUF quant on Hugging Face sized to your available memory (see
   the sizing snippet in `MODELS.md`).
2. `./pull_and_build.sh <repo> <file> <tag>`
3. `./run_detached.sh coding-benchmark <tag>`
4. `./run_detached.sh reasoning-benchmark <tag>`
5. Add a row to your results table.

## Before you trust a "kill" or timeout

If a run dies unexpectedly, check `ollama ps` — if the model is still
listed as loaded/generating, the underlying inference didn't fail, only the
watching process did. `run_detached.sh` already runs the actual benchmark
fully detached from the calling shell for this reason; if it still dies,
check the model's own log/response first before assuming it's a model
problem (see the methodology notes at the bottom of `RESULTS.md` for the
specific issues hit while building this).
