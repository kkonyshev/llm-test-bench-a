# Results

Rankings, takeaways and picks in Russian: [`CHAMPIONS.md`](CHAMPIONS.md). VRAM, RAM and CPU
per model: [`RESOURCES.md`](RESOURCES.md).

Two machines' results are recorded here — see `HARDWARE.md` for exact specs
and `MODELS.md` for exact model files. Single run per model per benchmark
on both machines (no repeated trials) — treat scores within 1-2 tests of
each other as noise, not a real gap. Where the same model was tested on
both machines, note where the score itself changed run-to-run (sampling
variance) vs. stayed stable.

---

# Results — MacBook Pro M3 16, late 2023 (baseline)

## Coding benchmark (task tracker REST API, 23 tests)

| Model | Tests passed | Time | Tokens generated | Speed |
|---|---|---|---|---|
| **Gemma4-26B (A4B)** | **23/23** | 320s | 9,152 | 29.6 tok/s |
| GLM-4.7-Flash | 22/23 | 243s | 6,982 | 30.3 tok/s |
| Qwen3-Coder-30B-A3B | 21/23 | 44s | 1,688 | **47.5 tok/s** |
| Qwen3.8-27B | 18/23 | 5,096s (85 min) | 31,872 | 6.3 tok/s |
| Qwen2.5-Coder-7B | 9/23 | 40s | 1,104 | 27.8 tok/s |
| DeepSeek-Coder-V2-Lite | 0/23 | 28s | 1,058 | **52-54 tok/s** |

### Bugs found per model (coding)

- **Gemma4-26B**: none — correctly kept the SQLAlchemy ORM model and the
  Pydantic response schema (`TaskResponse`) as separate classes.
- **GLM-4.7-Flash**: doesn't validate the `priority` query param on the
  list-filter endpoint (accepts invalid values instead of 422). Uses a
  `<think>...</think>` reasoning block before the final answer — that's
  most of its extra token cost vs. Qwen3-Coder.
- **Qwen3-Coder-30B-A3B**: missing title-length validation (accepts >200
  char titles); `DELETE` returns `200` instead of `204`.
- **Qwen3.8-27B**: `ResponseValidationError` on the filter and partial-update
  endpoints (its response doesn't match its own declared response model);
  `DELETE` returns `405 Method Not Allowed` — the route likely wasn't
  registered correctly. Also: never used markdown code fences in its answer
  (unlike every other model), needed unbounded generation to finish, and
  is dense (27B active, not MoE) — by far the slowest model tested.
- **Qwen2.5-Coder-7B**: multiple `KeyError: 'id'` (response shape doesn't
  match what the tests expect); `update` on a missing task returns `422`
  instead of `404`.
- **DeepSeek-Coder-V2-Lite**: defined `Task` as a SQLAlchemy ORM model
  (`class Task(Base)`) and then reused that same class as the FastAPI
  `response_model` — FastAPI requires a Pydantic model there, so every
  single endpoint crashes identically with `FastAPIError: Invalid args for
  response field`. Fastest generator tested, but the output doesn't run.

## Reasoning benchmark (12 self-authored puzzles — math, logic, trick questions)

| Model | Correct | Time | Tokens generated | Speed |
|---|---|---|---|---|
| **Qwen3.8-27B** | **12/12** | 293s | 1,997 | 7.3 tok/s |
| **Gemma4-26B (A4B)** | **12/12** | 216s | 6,338 | 29.6 tok/s |
| Qwen3-Coder-30B-A3B | 11/12 | 34s | 1,107 | 47.5 tok/s |
| GLM-4.7-Flash | 11/12 | 391s | 10,695 | 28.1 tok/s |
| Qwen2.5-Coder-7B | 10/12 | 78s | 1,934 | 26.4 tok/s |
| DeepSeek-Coder-V2-Lite | 8/12 | 30s | 1,162 | 52.3 tok/s |

### Which puzzles tripped up which models

- **Q5 (sheep trick — "all but 9 die")**: GLM-4.7-Flash and DeepSeek both
  answered 8 (misread as "9 die" instead of "9 survive").
- **Q7 (kg of feathers vs. lb of steel)**: Qwen3-Coder-30B-A3B and
  Qwen2.5-Coder-7B both got this wrong (said "the same" / "the pound",
  respectively — a kilogram is heavier).
- **Q3 (pet/drink logic grid)**: Qwen2.5-Coder-7B and DeepSeek both got the
  deduction wrong.
- **Q12 (height comparison)**: DeepSeek misread the transitive chain.
- Every other puzzle was answered correctly by every model.

## Combined picture (Mac)

| Model | Coding | Reasoning | Practical read |
|---|---|---|---|
| Gemma4-26B (A4B) | 23/23 | 12/12 | Best correctness on both, at moderate MoE speed. Best all-rounder found. |
| Qwen3-Coder-30B-A3B | 21/23 | 11/12 | Best speed/correctness tradeoff — the practical daily-driver pick for coding. |
| GLM-4.7-Flash | 22/23 | 11/12 | Comparable correctness to the top models, but always burns tokens on visible `<think>` reasoning — 4-6x slower wall-clock than Qwen3-Coder for similar results. |
| Qwen3.8-27B | 18/23 | 12/12 | Genuinely the best reasoner, but dense (not MoE) — 85 minutes for the coding task is impractical for interactive use. Reasoning-only, low-latency-tolerant use cases only. |
| Qwen2.5-Coder-7B | 9/23 | 10/12 | Reasoning held up reasonably at this size; coding correctness drops hard. Useful as a cheap/fast floor, not a daily driver. |
| DeepSeek-Coder-V2-Lite | 0/23 | 8/12 | Fastest raw generator tested, undermined by one real architectural bug that fails every coding test. Speed doesn't matter if the output doesn't run. |

---

# Results — workstation1 (RTX 5070 Ti)

The original 6-model set was re-run here unchanged, plus 5 more models
added afterward (70B-class dense + one 236B MoE) specifically to explore
the CPU/GPU-offload cliff on a discrete-GPU machine — see `HARDWARE.md`.

## Coding benchmark (23 tests)

| Model | Category | Tests passed | Time | Tokens | Speed | GPU/CPU split |
|---|---|---|---|---|---|---|
| **Gemma4-26B (A4B)** | MoE | **23/23** | 2m 0s | 8,126 | 85.9 tok/s | ~100% GPU |
| **Qwen3.8-27B** | Dense | **23/23** | 39m 30s | 25,541 | 10.9 tok/s | 79% GPU / 21% CPU |
| Qwen3-Coder-30B-A3B | MoE | 21/23 | 22s | 1,532 | 107.3 tok/s | ~100% GPU |
| DeepSeek-Coder-V2-full | MoE, 236B/21B active | 18/23 | 61m 21s | 1,613 | 0.46 tok/s | 8% GPU / 92% CPU |
| Qwen2.5-72B | Dense | 10/23 | 15m 23s | 1,142 | 1.27 tok/s | ~27% GPU / 73% CPU |
| GLM-4.7-Flash | MoE | 10/23 | 1m 2s | 4,400 | 77.3 tok/s | ~100% GPU |
| llama3.1:70b | Dense | 8/23 | 12m 45s | 1,078 | 1.44 tok/s | ~27% GPU / 73% CPU |
| Qwen2.5-Coder-7B | Dense | 6/23 | 17s | 1,122 | 142.5 tok/s | ~100% GPU |
| llama3.3:70b | Dense | 0/23 | 35m 34s\* | 1,523 | 1.4 tok/s | ~27% GPU / 73% CPU |
| Nemotron-70B | Dense | 0/23 | 15m 1s | 1,166 | 1.39 tok/s | ~27% GPU / 73% CPU |
| DeepSeek-Coder-V2-Lite | MoE | 0/23 (arch bug) | 34s | 1,255 | 56.2 tok/s | ~100% GPU |

\* llama3.3:70b's coding run overlapped with concurrent Qwen2.5-72B/
Nemotron-70B downloads competing for CPU — timing is inflated, not clean.
The score (0/23) and eval_tokens_per_s (which reflects only pure generation
time) are unaffected.

### Bugs found per model (coding, workstation1-specific / new models)

- **Qwen3.8-27B, Gemma4-26B, Qwen3-Coder-30B-A3B, GLM-4.7-Flash,
  Qwen2.5-Coder-7B, DeepSeek-Coder-V2-Lite**: same underlying model files
  as the Mac run — see bugs above. Scores differ slightly on a few
  (GLM 22→10, Qwen3.8-27B 18→23, Qwen2.5-Coder-7B 9→6) purely from sampling
  variance between runs, not a hardware effect — worth re-running either
  machine again before trusting any single-test delta this size.
- **llama3.1:70b**: reused the create-only `TaskModel` (which requires
  `title`, no default) as the request body type for `PUT` partial updates —
  any update omitting `title` gets auto-rejected `422` by FastAPI before
  the handler even runs. The update handler itself only ever updates the
  `completed` field, silently ignoring `title`/`description`/`priority`
  even when validation passes.
- **llama3.3:70b**: left a stray debug call, `print(sqlite3.version)`, in
  the shipped code — `sqlite3.version` doesn't exist on this Python's
  `sqlite3` module (removed as part of the module's deprecation cleanup),
  so every request that touches the DB connection crashes with
  `AttributeError: module 'sqlite3' has no attribute 'version'`.
- **Qwen2.5-72B**: same "wrong model reused for update" pattern as
  llama3.1:70b — `AttributeError: 'TaskCreate' object has no attribute
  'completed'` (the create-only Pydantic model has no `completed` field,
  but the update path tries to read/set it directly on that type).
- **Nemotron-70B**: first attempt scored a false 0/23 due to a *harness*
  bug, not a model bug — see "Extraction regex vs. doubled code fences"
  below. After the fix: real bug is `NameError: name 'Depends' is not
  defined` — used FastAPI's `Depends()` throughout without importing it.
- **DeepSeek-Coder-V2-full**: missing title-length validation (`assert 201
  == 422`, same class of bug as Qwen3-Coder-30B-A3B on the Mac run);
  filter-by-`completed`/filter-by-`priority` endpoints return the wrong
  `total` count (`assert 2 == 1`); same "wrong model reused for partial
  update" 422 pattern as llama3.1:70b and Qwen2.5-72B. Notably: this fixed
  the *fatal* architectural bug that made DeepSeek-Coder-V2-**Lite** score
  0/23 (reusing an ORM class as a Pydantic response model) — the full model
  doesn't make that mistake.

## Reasoning benchmark (12 puzzles)

| Model | Correct | Time | Tokens | Speed |
|---|---|---|---|---|
| **Qwen3.8-27B** | **12/12** | 3m 56s | 2,803 | 12.0 tok/s |
| **Gemma4-26B (A4B)** | **12/12** | 1m 13s | 6,266 | 87.0 tok/s |
| Qwen3-Coder-30B-A3B | **12/12** | 10s | 1,026 | 109.9 tok/s |
| GLM-4.7-Flash | **12/12** | 2m 30s | 11,001 | 73.9 tok/s |
| llama3.1:70b | **12/12** | 13m 53s | 1,183 | 1.43 tok/s |
| llama3.3:70b | **12/12** | 52m 3s\* | 1,542 | 1.45 tok/s |
| Qwen2.5-72B | **12/12** | 15m 52s | 1,202 | 1.27 tok/s |
| Nemotron-70B | 11/12 | 18m 30s | — | ~1.4 tok/s |
| DeepSeek-Coder-V2-full | 9/12 | 4m 18s | — | 0.79 tok/s |
| DeepSeek-Coder-V2-Lite | 9/12 | 21s | 1,250 | 61.9 tok/s |
| Qwen2.5-Coder-7B | 6/12 | 8s | 1,226 | 157.9 tok/s |

\* Same contamination caveat as its coding run.

### Which puzzles tripped up which models (new models)

- **Nemotron-70B**: Q3 (pet/drink logic grid) — same puzzle that tripped
  Qwen2.5-Coder-7B and DeepSeek-Coder-V2-Lite on the Mac run.
- **DeepSeek-Coder-V2-full**: Q1 (discount arithmetic), Q2 (age word
  problem), Q3 (pet/drink logic grid) — all three answered with a
  plausible-looking but wrong final value, everything from Q4 onward
  correct.
- **Qwen2.5-Coder-7B, llama3.1/3.3:70b, Qwen2.5-72B**: all 12/12 or same
  puzzle-set pattern as the Mac baseline for the shared models — see above.

## Combined picture (workstation1)

| Model | Coding | Reasoning | Practical read |
|---|---|---|---|
| Qwen3.8-27B | 23/23 | 12/12 | Best all-rounder on this hardware — perfect on both, and 79% GPU-resident keeps it merely slow (not crawling) at 10.9 tok/s. |
| Gemma4-26B (A4B) | 23/23 | 12/12 | Matches Qwen3.8-27B on correctness, ~8x faster (85.9 tok/s) — the clear daily-driver pick here. |
| Qwen3-Coder-30B-A3B | 21/23 | 12/12 | Fastest of the strong performers (107-110 tok/s); best speed/correctness tradeoff for snappy interactive use. |
| DeepSeek-Coder-V2-full | 18/23 | 9/12 | Genuinely decent coding correctness for a model that's 92% CPU-resident — but 0.46 tok/s and a 61-minute single coding run make it impractical regardless of quality. |
| Qwen2.5-72B | 10/23 | 12/12 | Reasoning is fine; coding correctness is mediocre and it's 73% CPU-resident — no redeeming speed to offset the mediocre coding score. |
| GLM-4.7-Flash | 10/23 | 12/12 | Coding score dropped sharply vs. the Mac run (22→10) — flagged as likely sampling variance, worth a repeat run before drawing conclusions. |
| llama3.1:70b | 8/23 | 12/12 | Reasoning holds up; coding fails on spec-adherence details (wrong model reused for partial update) that a newer/code-tuned model wouldn't miss. 73% CPU-resident, 1.44 tok/s — impractical regardless. |
| Qwen2.5-Coder-7B | 6/23 | 6/12 | Both scores dropped vs. the Mac run — again flagged as sampling variance pending a repeat, but even generously this is a fast/cheap floor, not a daily driver. |
| llama3.3:70b | 0/23 | 12/12 | Same base weights as llama3.1:70b, redone post-training didn't fix (or introduced) a coding-side bug (stray debug `print`) — proof that "newer version of the same family" isn't automatically better at this task. Also demonstrates raw size doesn't buy coding correctness: it's beaten on coding by every model half its size or smaller. |
| Nemotron-70B | 0/23 | 11/12 | Same story as llama3.1/3.3 — reasoning intact, coding fails on a basic missing-import bug. All three 70B dense generalists land in the same "fine at puzzles, bad at spec-following code" bucket regardless of which post-training recipe or lab produced them. |
| DeepSeek-Coder-V2-Lite | 0/23 (arch bug) | 9/12 | Same fatal architectural bug as the Mac run — confirmed the full-size sibling model fixes this. |

**Bottom line on workstation1**: raw parameter count does not correlate
with coding correctness in this test set — the two best coding performers
(Gemma4-26B, Qwen3.8-27B) are both ≤27B, and every 70B+ generalist model
tested (Llama 3.1/3.3, Qwen2.5-72B, Nemotron) scored worse on coding than
every sub-30B model except the architecturally-broken DeepSeek-Lite. Size
bought reliable puzzle-reasoning across the board but not meticulous
spec-adherence, which is a training/tuning-era effect, not a scale effect.
Separately: **every model over ~16 GB VRAM runs at 0.4-1.5 tok/s regardless
of size or quality** once it falls off the "fits in VRAM" cliff — going
from 27% GPU-resident (llama3.1:70b) to 8% GPU-resident (DeepSeek-full,
236B) barely changes the tok/s, because CPU/RAM bandwidth — not GPU
compute — sets the pace for the CPU-resident majority of the model either
way (Amdahl's-law effect, confirmed empirically rather than assumed).

## Cross-machine comparison (shared models only)

| Model | Mac coding | WS1 coding | Mac reasoning | WS1 reasoning | WS1 speed vs. Mac |
|---|---|---|---|---|---|
| Gemma4-26B (A4B) | 23/23 @ 29.6 tok/s | 23/23 @ 85.9 tok/s | 12/12 @ 29.6 tok/s | 12/12 @ 87.0 tok/s | ~2.9x faster |
| Qwen3-Coder-30B-A3B | 21/23 @ 47.5 tok/s | 21/23 @ 107.3 tok/s | 11/12 @ 47.5 tok/s | 12/12 @ 109.9 tok/s | ~2.3x faster |
| GLM-4.7-Flash | 22/23 @ 30.3 tok/s | 10/23 @ 77.3 tok/s | 11/12 @ 28.1 tok/s | 12/12 @ 73.9 tok/s | ~2.6x faster |
| Qwen3.8-27B | 18/23 @ 6.3 tok/s | 23/23 @ 10.9 tok/s | 12/12 @ 7.3 tok/s | 12/12 @ 12.0 tok/s | ~1.7x faster |
| Qwen2.5-Coder-7B | 9/23 @ 27.8 tok/s | 6/23 @ 142.5 tok/s | 10/12 @ 26.4 tok/s | 6/12 @ 157.9 tok/s | ~5.4x faster |
| DeepSeek-Coder-V2-Lite | 0/23 @ 52-54 tok/s | 0/23 @ 56.2 tok/s | 8/12 @ 52.3 tok/s | 9/12 @ 61.9 tok/s | ~1.1x faster |

Every model that fits fully in the 5070 Ti's 16 GB VRAM is meaningfully
faster than the same model on the M3 Pro's unified memory — 2-3x is the
typical range, with the smallest model (Qwen2.5-Coder-7B) showing the
largest gap (~5x), likely because it's furthest from saturating either
machine's compute and most exposed to the M3 Pro's lower raw throughput at
small batch/short-sequence workloads. Scores mostly hold within 1-2 tests
of each other (expected noise) except GLM-4.7-Flash and Qwen2.5-Coder-7B,
which dropped more than that on workstation1 — worth a repeat run on both
machines before concluding hardware itself affects correctness (it
shouldn't, in principle, beyond floating-point non-determinism).

---

# Results — workstation1, dual-GPU (RTX 5090 + RTX 5070 Ti)

Same box as Machine 2 (`RESULTS.md`'s "workstation1" section), after adding
a second GPU — see `HARDWARE.md`'s Machine 3 entry for exact specs
(including the native-Ollama-vs-Docker methodology caveat). All 11 models
from the Machine 2 run were re-tested unchanged; scripts were patched to
point at the current Ollama endpoint (`:11434` native, not the old
`ollama-test` Docker container's `:11436`) and `num_ctx` was made
per-model-overridable, since the 236B model still needs `num_ctx=8192` to
avoid a KV-cache OOM (see `MODELS.md`/methodology note 9).

## Machine 3 tag mapping

All 11 models were already present as locally-pulled Ollama models on this
host, under different tags than the ones originally used in `MODELS.md` (in
most cases — verified same underlying GGUF/quant by file size). No
re-downloading was needed.

| MODELS.md name | Machine 3 Ollama tag | Run directory suffix |
|---|---|---|
| qwen3-coder-30b-a3b | `qwen3-coder:30b-a3b-q4_K_M` | (none — new tag, no collision) |
| glm-4.7-flash | `glm-4.7-flash:q4_K_M` | (none) |
| qwen3.8-27b | `qwen3.8:27b-q4_K_M` | (none) |
| qwen2.5-coder-7b-test | `qwen2.5-coder:7b-instruct-q4_K_M` | (none) |
| deepseek-coder-v2-lite | `deepseek-coder-v2:16b-lite-instruct-q4_K_M` | (none) |
| gemma4-26b | `gemma4:26b-a4b-it-q4_K_M` | (none) |
| llama3.1:70b | `llama3.1:70b` | `-dualgpu` (same tag as Machine 2's baseline run — suffixed to avoid overwriting that tracked data) |
| llama3.3:70b | `llama3.3:70b` | `-dualgpu` |
| qwen2.5:72b | `qwen2.5:72b` | `-dualgpu` (two attempts recorded — see below) |
| nemotron:70b | `nemotron:70b` | `-dualgpu` |
| deepseek-coder-v2-full-bench | `deepseek-coder-v2:236b-instruct-q4_K_M` | (none — new tag, no collision) |

## Coding benchmark (23 tests)

| Model | Tests passed | Time | Speed | GPU/CPU split | vs. Machine 2 |
|---|---|---|---|---|---|
| **Qwen3-Coder-30B-A3B** | **23/23** | 11s | 292.2 tok/s | 100% GPU | 21/23 → 23/23, 2.7x faster |
| GLM-4.7-Flash | 10/23 (attempt 1: 0/23) | 52s | 186.6 tok/s | 100% GPU | 10/23 → 10/23 (same), 2.4x faster |
| **Qwen3.8-27B** | **23/23** | 59s | 60.6 tok/s | 100% GPU | 23/23 → 23/23, wall-clock 39m30s → 59s (**40x**) |
| Qwen2.5-Coder-7B | 9/23 | 5s | 263.2 tok/s | 100% GPU | 6/23 → 9/23, 1.8x faster |
| DeepSeek-Coder-V2-Lite | 8/23 (attempt 1: 0/23, arch bug) | 13s | 246.9 tok/s | 100% GPU | 0/23 → 8/23, 4.4x faster |
| Gemma4-26B (A4B) | 22/23 | 35s | 230.2 tok/s | 100% GPU | 23/23 → 22/23 (noise), 2.7x faster |
| Llama3.1:70b | 3/23 | 2m38s | 6.57 tok/s | **14%/86% CPU/GPU** | 8/23 → 3/23 (noise), 4.6x faster |
| Llama3.3:70b | 11/23 | 4m8s | 6.52 tok/s | **14%/86% CPU/GPU** | 0/23\* → 11/23, 4.7x faster |
| Qwen2.5-72B | 0/23 (both attempts) | 5m10s | 4.14 tok/s | 21%/79% CPU/GPU | 10/23 → 0/23 (noise, see below), 3.3x faster |
| Nemotron-70B | 9/23 | 3m10s | 6.56 tok/s | **14%/86% CPU/GPU** | 0/23 → 9/23, 4.7x faster |
| DeepSeek-Coder-V2 (236B) | 20/23 | 15m49s | 1.87 tok/s | 75%/25% CPU/GPU | 18/23 → 20/23, 4x faster |

\* Machine 2's llama3.3:70b coding run was flagged as timing-contaminated by
concurrent downloads (see methodology note 11); its 0/23 score itself was
unaffected by that, so the score comparison above still holds.

**GPU-residency jump for the 70B-class dense models is the story here**:
14-21% CPU / **79-86% GPU** on Machine 3, vs. 27% GPU / 73% CPU on Machine 2
for the same models. The 236B MoE model went from 8% to 25% GPU-resident.
That's the direct cause of the ~4.5-4.7x speedup on every dense 70B+ model.

### Re-running the 0/23 scores (requested check: "is this a dumb error?")

Three models scored 0/23 on the first pass through the full suite:
GLM-4.7-Flash, DeepSeek-Coder-V2-Lite, and Qwen2.5-72B. Each was re-run once
more from scratch (fresh generation, same prompt) specifically to rule out
a harness/extraction fluke before trusting the score. First-attempt
artifacts are preserved under `runs/<tag>-attempt1` (or
`runs/qwen2.5:72b-dualgpu-attempt1` / `-attempt2` for both of Qwen2.5-72B's
tries) alongside the current `runs/<tag>` directory (which holds the
higher-scoring, more-recent attempt for GLM and DeepSeek-Lite).

- **GLM-4.7-Flash**: attempt 1 failed all 23 tests via `NameError:
  declarative_base` — the code called `declarative_base()` but never
  imported it. A real, verified bug (confirmed by reading `main.py`, which
  extracted cleanly at 4419 chars — not an extraction failure). Attempt 2
  scored 10/23, tripping a *different* bug (`TypeError: Priority.validate()
  takes...`). Conclusion: both are real generation bugs, not harness
  errors, but GLM's score is genuinely volatile run-to-run (22 on Mac, 10 on
  Machine 2's original run, 0 then 10 here) — consistent with the variance
  this file already flags for GLM.
- **DeepSeek-Coder-V2-Lite**: attempt 1 failed via `NameError: Depends`
  (used FastAPI's `Depends()` without importing it). Attempt 2 scored 8/23,
  failing instead via `ValueError: "Task" object has no field...` — the
  model again conflated its SQLAlchemy ORM class with a plain object/dict,
  the same *class* of bug (ORM/response-model confusion) documented for
  this model back on Machine 1 and Machine 2. Real, reproducible weakness,
  not a fluke.
- **Qwen2.5-72B**: 0/23 on *both* attempts, and for the same underlying
  reason both times — the model consistently writes Pydantic v1-style code
  (`constr(regex=...)` on attempt 1, `Field(..., regex=...)` on attempt 2)
  against the installed Pydantic v2, which rejects the removed `regex`
  kwarg outright (`PydanticUserError`/`TypeError` depending on call site).
  This is the most solid finding of the three: a genuinely, repeatably
  broken model output on this task, not noise.

## Reasoning benchmark (12 puzzles)

| Model | Correct | Time | Speed | vs. Machine 2 |
|---|---|---|---|---|
| Qwen3-Coder-30B-A3B | **12/12** | 4s | 302.6 tok/s | 12/12 → 12/12, 2.8x faster |
| GLM-4.7-Flash | **12/12** | 22s | 189.6 tok/s | 12/12 → 12/12, 2.6x faster |
| **Qwen3.8-27B** | **12/12** | 30s | 60.9 tok/s | 12/12 → 12/12, wall-clock 3m56s → 30s (~8x) |
| Qwen2.5-Coder-7B | 10/12 | 6s | 264.3 tok/s | 6/12 → 10/12, 1.7x faster |
| DeepSeek-Coder-V2-Lite | 9/12 | 5s | 278.9 tok/s | 9/12 → 9/12 (same), 4.5x faster |
| Gemma4-26B (A4B) | **12/12** | 26s | 231.5 tok/s | 12/12 → 12/12, 2.7x faster |
| Llama3.1:70b | **12/12** | 3m7s | 6.57 tok/s | 12/12 → 12/12, 4.6x faster |
| Llama3.3:70b | 11/12 | 4m0s | 6.55 tok/s | 12/12 → 11/12 (noise), 4.5x faster |
| Qwen2.5-72B | 11/12 | 5m3s | 4.13 tok/s | 12/12 → 11/12 (noise), 3.3x faster |
| Nemotron-70B | **12/12** | 4m34s | 6.55 tok/s | 11/12 → 12/12 (score up), 4.7x faster |
| DeepSeek-Coder-V2 (236B) | 9/12 | 1m29s | 3.15 tok/s | 9/12 → 9/12 (same), 4x faster |

No reasoning score came back at 0/12, so no retries were needed there.

## Combined picture (Machine 3)

| Model | Coding | Reasoning | Practical read |
|---|---|---|---|
| Qwen3-Coder-30B-A3B | 23/23 | 12/12 | Now perfect on coding too (was 21/23) — the clear daily-driver pick on this hardware: fastest strong performer at 292 tok/s. |
| Qwen3.8-27B | 23/23 | 12/12 | Still perfect on both, and the GPU upgrade turned its 85-minute coding run into 59 seconds — no longer a "reasoning-only" tradeoff model on this box. |
| Gemma4-26B (A4B) | 22/23 | 12/12 | Essentially unchanged correctness, 2.7x faster — still an excellent all-rounder. |
| Llama3.3:70b / Nemotron-70B | 11/23, 9/23 | 11/12, 12/12 | Both jumped from 0/23 to double digits on coding once GPU-resident — the dense 70B "fine at puzzles, bad at spec-following code" pattern from Machine 2 still holds, but less severely now. |
| DeepSeek-Coder-V2 (236B) | 20/23 | 9/12 | Still the best absolute coding correctness of the big models, still impractically slow (1.87 tok/s, 16-minute single run) even with 3x better GPU residency. |
| Qwen2.5-72B | 0/23 (reproduced twice) | 11/12 | Reasoning is fine; coding is reliably broken by outdated Pydantic API usage, independent of hardware. |
| GLM-4.7-Flash, DeepSeek-Coder-V2-Lite | volatile / weak | 12/12, 9/12 | Same known weaknesses as prior machines — see retry notes above. |

## Cross-machine comparison (Machine 2 → Machine 3, shared models)

| Model | M2 coding | M3 coding | M2 reasoning | M3 reasoning | M3 speed vs. M2 |
|---|---|---|---|---|---|
| Qwen3-Coder-30B-A3B | 21/23 @ 107.3 tok/s | 23/23 @ 292.2 tok/s | 12/12 @ 109.9 tok/s | 12/12 @ 302.6 tok/s | ~2.7x faster |
| GLM-4.7-Flash | 10/23 @ 77.3 tok/s | 10/23 @ 186.6 tok/s | 12/12 @ 73.9 tok/s | 12/12 @ 189.6 tok/s | ~2.5x faster |
| Qwen3.8-27B | 23/23 @ 10.9 tok/s | 23/23 @ 60.6 tok/s | 12/12 @ 12.0 tok/s | 12/12 @ 60.9 tok/s | ~5.5x faster |
| Qwen2.5-Coder-7B | 6/23 @ 142.5 tok/s | 9/23 @ 263.2 tok/s | 6/12 @ 157.9 tok/s | 10/12 @ 264.3 tok/s | ~1.8x faster |
| DeepSeek-Coder-V2-Lite | 0/23 @ 56.2 tok/s | 8/23 @ 246.9 tok/s | 9/12 @ 61.9 tok/s | 9/12 @ 278.9 tok/s | ~4.5x faster |
| Gemma4-26B (A4B) | 23/23 @ 85.9 tok/s | 22/23 @ 230.2 tok/s | 12/12 @ 87.0 tok/s | 12/12 @ 231.5 tok/s | ~2.7x faster |
| Llama3.1:70b | 8/23 @ 1.44 tok/s | 3/23 @ 6.57 tok/s | 12/12 @ 1.43 tok/s | 12/12 @ 6.57 tok/s | ~4.6x faster |
| Llama3.3:70b | 0/23 @ 1.4 tok/s | 11/23 @ 6.52 tok/s | 12/12 @ 1.45 tok/s | 11/12 @ 6.55 tok/s | ~4.6x faster |
| Qwen2.5-72B | 10/23 @ 1.27 tok/s | 0/23 @ 4.14 tok/s | 12/12 @ 1.27 tok/s | 11/12 @ 4.13 tok/s | ~3.3x faster |
| Nemotron-70B | 0/23 @ 1.39 tok/s | 9/23 @ 6.56 tok/s | 11/12 @ ~1.4 tok/s | 12/12 @ 6.55 tok/s | ~4.7x faster |
| DeepSeek-Coder-V2 (236B) | 18/23 @ 0.46 tok/s | 20/23 @ 1.87 tok/s | 9/12 @ 0.79 tok/s | 9/12 @ 3.15 tok/s | ~4x faster |

**Bottom line on the RTX 5090 upgrade**: every model got faster (2.5-5.5x
depending on how GPU-resident it already was on Machine 2), but the biggest
win by far is for the models that used to fall off the VRAM cliff — the
dense 70B class went from "impractical" (1.3-1.45 tok/s) to "usable"
(6.5-6.6 tok/s), and the 236B MoE model's single coding run dropped from
61 minutes to under 16. Coding/reasoning *correctness* moved in both
directions by a test or two for several models (expected — see the
repeat-run note above and existing single-run-noise caveats), except for
Qwen2.5-72B and DeepSeek-Coder-V2-Lite, whose specific failure *reasons*
changed but whose overall pattern (broken/weak) was independently
reproduced.

---

## Methodology notes / pitfalls hit while building this (read before re-running)

From the original Mac-only build:

1. **Don't use `ollama run --verbose` piped to a file** — it emits ANSI
   terminal control codes into stdout even when not attached to a TTY,
   which can corrupt extracted code. Use the HTTP API (`/api/generate`)
   directly instead — that's what `run_bench.sh` does.
2. **Use streaming (`"stream": true`), not `"stream": false`** — a
   non-streaming call blocks with zero data until the entire generation is
   done. For slow/dense models this can run past any reasonable timeout
   with no visibility into progress. Streaming gives live token counts and
   only needs the *gap* between chunks to stay under the timeout, not the
   total duration.
3. **Don't cap `num_predict` too low for dense/reasoning models.** A hard
   cap can cut a model off mid-answer before it ever produces a code fence
   or final answer, understating its real ability. `num_predict: -1` (no
   cap, bounded only by context length) is what these scripts use.
4. **Reasoning models put throwaway code snippets inside their
   `<think>...</think>` block** — extracting the *first* ```python ```
   block can grab a scratch snippet instead of the final answer. Strip
   everything up to `</think>` first, then extract the *last* code block
   after that.
5. **pytest fixture isolation bug (now fixed in `test_tasks.py`)**: an
   earlier version deleted the SQLite file before every test, but some
   generated apps only create their tables once at import time. Since
   pytest caches the module import, tables never got recreated after the
   first test, failing every subsequent test for a reason that had nothing
   to do with the model's code. Fixed by `importlib.reload()` + entering
   `TestClient` as a context manager on every test, which forces
   re-initialization regardless of whether the model put its init logic at
   module level or in a FastAPI startup/lifespan handler.
6. **Long background runs got killed unpredictably** on the Mac's session
   (observed after anywhere from under a minute to ~50 minutes, with the
   underlying Ollama generation still alive afterward — so it wasn't Ollama
   or the model crashing). Cause not fully diagnosed. Fix: run fully
   detached with `nohup ... & disown` (see `run_detached.sh`) so the
   benchmark survives regardless of what's killing tracked background shell
   tasks in the calling session.

New, found while running on workstation1:

7. **Ollama's default context length is not portable across hosts.** The
   scripts didn't originally set `num_ctx` explicitly, relying on Ollama's
   per-model default. On workstation1 that default turned out to be only
   4096 tokens — far smaller than whatever the Mac's Ollama picked, and
   nowhere near enough for GLM-4.7-Flash's verbose double-pass `<think>`
   style. This truncated its response mid-generation (Ollama's
   `done_reason: "length"`) on **both** benchmarks, producing a
   corrupted/incomplete extraction and a false `0/12` reasoning score.
   **Fix**: set `"num_ctx": 32768` explicitly in the `/api/generate`
   request options. Confirmed the other models weren't silently affected by
   checking `done_reason` (`"stop"` = finished naturally, `"length"` =
   truncated) on every already-completed run before trusting any score.
8. **Extraction regex breaks on a doubled opening code fence.** Some models
   (Nemotron-70B, observed once) emit a malformed doubled fence-open —
   an opening ```python``` marker immediately followed by a second
   ```python``` marker before the real code starts. The original
   extraction regex (non-greedy `python fence ... closing fence`) matches
   from the *first* fence to the very next fence it finds, which is the
   *second* opening marker — producing an **empty** captured block instead
   of the real code, silently scoring a genuinely working model as `0/23`
   by extraction failure, not model failure. **Fix**: collapse the doubled
   opening marker down to a single one before running the extraction
   regex. Caught by noticing `main.py` was 0 bytes despite a non-trivial
   `response.md`, not by any test failure message — worth spot-checking
   extracted file sizes whenever a model scores surprisingly `0`.
   surprisingly `0`.
9. **KV cache memory scales with context length independently of model
   size, and can dwarf the model weights themselves.** Running
   DeepSeek-Coder-V2-full (236B/21B active MoE, 142 GB on disk) at
   `num_ctx=32768` failed outright:
   `ggml_aligned_malloc: insufficient memory (attempted to allocate
   153600.00 MB)` — a ~150 GB KV cache allocation, on a 123 GB RAM machine,
   for a 32K-token context. Reducing to `num_ctx=8192` for this model
   specifically fixed it (its predecessor, DeepSeek-Coder-V2-Lite, was
   never verbose enough to need more). **Takeaway**: for very large/deep
   architectures, KV cache — not model weight size — can be the actual
   memory bottleneck, and needs its own headroom calculation separate from
   "does the model file fit."
10. **Split GGUF files (>50 GB, auto-chunked by Hugging Face) aren't
    reliably loadable by `ollama create` on this Ollama version (0.33.3)** —
    see `MODELS.md` for the full "has N shards, expected M" failure and the
    Python-`gguf`-library merge workaround. Confirmed this is a genuine
    Ollama limitation, not a path/Modelfile placement mistake, by
    reproducing the identical failure with the Modelfile colocated directly
    alongside all 4 shards.
11. **Running downloads concurrently with an active CPU-offloaded
    benchmark measurably inflates its wall-clock time** (llama3.3:70b's
    coding run: `total_duration` 2,134s vs. `eval_duration` (pure
    generation) only 1,091s — a ~1,000s gap that doesn't appear on any other
    run). The large background `hf download`/`ollama pull` processes
    compete for the same CPU cycles the offloaded model layers need.
    **Takeaway**: don't trust wall-clock/`total_duration` numbers for any
    run with concurrent downloads in flight — `eval_tokens_per_s` (pure
    generation rate) is unaffected and remains comparable.
12. **`ollama ps`'s reported CPU/GPU split is the single most useful
    number for predicting a model's speed on a VRAM-constrained machine** —
    far more predictive than parameter count or MoE-vs-dense architecture.
    Every model at ~100% GPU-resident hit 56-142 tok/s; every model below
    ~30% GPU-resident hit under 2 tok/s, regardless of whether it was a 70B
    dense model or a 236B MoE model with only 21B active parameters — MoE
    sparsity doesn't help once the *inactive* experts still need to live in
    (slow) system RAM rather than VRAM.

New, found while re-running on Machine 3 (dual-GPU):

13. **A prior benchmark run's serving setup can silently rot underneath
    you.** `run_bench.sh` on both benchmarks hardcoded `docker exec
    ollama-test ...` and port `11436`, pointing at a Docker container from
    the Machine 2 run that no longer existed by the time Machine 3 was set
    up — a currently-running native `ollama serve` on port `11434` had
    replaced it. Scripts failed silently in a way that would have produced
    empty/garbage results rather than an obvious error if not caught first.
    **Fix**: always verify the target Ollama endpoint (`curl
    localhost:<port>/api/version`, `ollama ps`) actually responds before
    trusting a re-run of old orchestration scripts on new/changed hardware.
14. **Directory-name collisions can silently overwrite tracked baseline
    data.** Several Machine 3 runs reused the exact same Ollama tag (and
    therefore the exact same `runs/<tag>` output directory) as Machine 2's
    already-committed baseline results for `llama3.1:70b`, `llama3.3:70b`,
    `qwen2.5:72b`, and `nemotron:70b` — `run_detached.sh`'s `rm -rf
    "$BENCH/runs/$MODEL"` step overwrote that historical data before the
    overwrite was noticed via `git status`/`git diff`. **Fix**: recovered
    from `git checkout --` since the repo was committed and clean beforehand
    (always confirm a clean working tree before a scripted re-run for
    exactly this reason), then re-ran on `<tag>-dualgpu`-suffixed
    directories to avoid the same collision going forward. If reusing an
    old tag name on new hardware, rename the output directory *before*
    running, not after.
15. **A 0/N score is worth one free re-run before you trust it, but a
    re-run is a *reproducibility* check, not a *fix*.** All three 0/23
    coding scores on Machine 3 (GLM-4.7-Flash, DeepSeek-Coder-V2-Lite,
    Qwen2.5-72B) were re-run from scratch. In every case the `main.py`
    extraction itself was clean (non-empty, matched the response length),
    ruling out an extraction bug like note 8's doubled-fence issue — so all
    three were confirmed to be real model-generated bugs. Two of the three
    (GLM, DeepSeek-Lite) scored higher on the second attempt but failed for
    a *different* reason each time (sampling variance in which mistake the
    model happens to make, not the harness). The third (Qwen2.5-72B) failed
    identically both times for the same root cause (Pydantic v1 `regex=`
    kwarg against an installed Pydantic v2) — that's the one worth trusting
    as a real, stable finding rather than noise.

---

# Results — workstation1, dual-GPU, October 2026 new models

Same machine, scripts and settings as the Machine 3 run above (native Ollama
on `:11434`, `num_ctx=32768`, single run per model). Script:
`run_oct2026_models.sh`. ComfyUI, Strata and the GPU miner were stopped, so
nothing else held VRAM. Both models were already pulled as Ollama tags.

| Model | Ollama tag | Quant / size | Where it ran |
|---|---|---|---|
| NVIDIA Nemotron 3.5 Bolt 74B-A9B (MoE, 9B active, vision) | `nemotron-3.5-bolt:74b-a9b` | IQ2_XXS, 23.8 GB | 100% GPU, RTX 5090 alone |
| InternScience Sage-A1.5 (qwen35moe, 35.5B, 8 of 256 experts) | `sage-a1.5:q4_k_m` | Q4_K_M, 21.7 GB | 100% GPU, RTX 5090 alone |
| InternScience Sage-A1.5 | `sage-a1.5:q8_0` | Q8_0, 37.8 GB | 100% GPU, split 5090 + 5070 Ti |

## Coding benchmark (23 tests)

| Model | Tests passed | Time | Tokens | Speed |
|---|---|---|---|---|
| **Nemotron 3.5 Bolt 74B-A9B (IQ2)** | **23/23** | 1m 42s | 15,588 | 160.3 tok/s |
| Sage-A1.5 Q4_K_M, `num_ctx=65536` (attempt 2) | 13/23 | 2m 42s | 38,579 | 244.0 tok/s |
| Sage-A1.5 Q8_0 | 7/23 | 2m 15s | 23,428 | 182.2 tok/s |
| Sage-A1.5 Q4_K_M, `num_ctx=32768` (attempt 1) | 0/23 | 2m 15s | 31,914 | 245.7 tok/s |

- **Bolt**: no failures. Thinks a lot before answering (15.6K tokens vs.
  ~1.5K for Qwen3-Coder-30B-A3B), so wall-clock is ~9x Qwen3-Coder's despite
  a respectable token rate. Notable that a 2-bit quant scores perfectly.
- **Sage Q4_K_M, attempt 1**: not a code bug. The response hit the context
  limit (854 prompt + 31,914 generated = exactly 32,768). Sage reasons in
  plain text inside the answer, so the code block was never finished and
  only 204 chars were extracted. Re-run with `num_ctx=65536`
  (`runs/sage-a1.5:q4_k_m`; the first attempt is kept as `-attempt1`):
  finished at 38.6K tokens, 13/23. GET/PATCH/DELETE by id return 404 and
  list endpoints return empty results for tasks it just created.
- **Sage Q8_0**: finished within 32K. 7/23: opens SQLite without
  `check_same_thread=False`, so every test that touches the DB from FastAPI's
  threadpool fails with `sqlite3.ProgrammingError`.

## Reasoning benchmark (12 puzzles)

| Model | Correct | Time | Tokens | Speed |
|---|---|---|---|---|
| **Nemotron 3.5 Bolt 74B-A9B (IQ2)** | **12/12** | 38s | 5,995 | 160.5 tok/s |
| **Sage-A1.5 Q4_K_M** | **12/12** | 33s | 8,329 | 252.3 tok/s |
| **Sage-A1.5 Q8_0** | **12/12** | 36s | 6,637 | 185.3 tok/s |

## Combined picture (October 2026 models)

| Model | Coding | Reasoning | Practical read |
|---|---|---|---|
| Nemotron 3.5 Bolt 74B-A9B (IQ2) | 23/23 | 12/12 | Joins Qwen3-Coder-30B-A3B and Qwen3.8-27B as the only perfect scorers; fits one 32 GB card. Slower wall-clock than Qwen3-Coder because of long thinking. |
| Sage-A1.5 (Q4_K_M / Q8_0) | 13/23 / 7/23 | 12/12 | Fast and a strong puzzle solver, but weak at spec-following code here, and its verbose in-answer reasoning needs a 64K context for a task this size. |

Methodology note 16: **a 0/N can be a context-window cutoff, not a bug.**
Check `prompt_eval_count + eval_count` against `num_ctx` before treating a
0/23 as a model failure; Sage Q4's first attempt used exactly the whole
32,768-token window.

---

# Results — Strata: Qwen3.8-Flash-Next Orca Uncensored IQ3_XXS (RTX 5070 Ti)

Not Ollama: this model runs on the Strata engine (`/data/apps/Strata-unsensored`,
its own `run-iq3_xxs.sh`, unchanged), which keeps the hot experts on the GPU and
the rest in RAM, computed on the CPU. The model is
`orcarouter/Qwen3.8-Flash-Next-Uncensored-GGUF` IQ3_XXS (125B MoE), served with
the vision projector and the config's "experimental speed projection" control
vector, 524K max context, on the RTX 5070 Ti alone (5090 idle).

The benchmark talks to Strata's OpenAI-compatible API on `:8081` through
`openai_generate.py` (set `BENCH_OPENAI_URL`; `run_bench.sh` is otherwise
unchanged, and Ollama is still the default). `max_tokens` 100,000; Strata's
default reasoning settings. The model's separate `reasoning_content` is not part
of the graded answer, like a `<think>` block. Script: `run_strata_uncensored.sh`.

| Benchmark | Result | Time | Tokens | Speed |
|---|---|---|---|---|
| Reasoning | **12/12** | 38s | 3,352 | 90.9 tok/s |
| Coding, attempt 2 | **23/23** | 14m 46s | 78,261 | 88.3 tok/s |
| Coding, attempt 1 | 0/23 | 3m 35s | 19,591 | 91.9 tok/s |

- **Attempt 1** produced no answer at all: 19.6K tokens of reasoning that ended
  in a loop printing `1000000…`, which Strata's repeated-token guard (#606)
  cut off (`finish_reason=length`, empty `content`). Kept as `-attempt1`.
- **Attempt 2** reasoned for 78K tokens (drafted `main.py` about two dozen
  times inside its reasoning, re-checking the spec line by line) and then
  answered with a clean 12.7K-char `main.py` that passes everything.
- So: correct when it finishes, but the slowest perfect coding score in this
  repo by wall-clock (vs. 59s for Qwen3.8-27B and 11s for Qwen3-Coder on the
  5090), and one of two runs did not finish at all.

## Resources during the runs (sampled every 5s)

| | Attempt 1 | Attempt 2 |
|---|---|---|
| `strata` CPU | avg 757%, max 808% (~8 cores) | avg 785%, max 808% |
| `strata` RSS | 59.5 GB | 59.5 GB |
| System RAM used / available | 67.7 / 55.7 GB | 67.8 / 55.6 GB |
| Swap used | 4.4 GB (flat, pre-existing) | 4.0-4.4 GB |
| Load average (1 min) | avg 8.0, max 9.6 | avg 8.1, max 8.8 |
| RTX 5070 Ti | 15.7 GB, avg 94% util, max 192 W | 15.7 GB, avg 97% util, max 192 W |

RAM and VRAM stay flat for the whole run (everything is loaded up front). With
~60 GB pinned by Strata, a second Strata instance or another RAM-heavy job
(e.g. ComfyUI's Wan 14B offload) would not fit next to it.
Raw samples: `strata_uncensored_resources_attempt{1,2}.csv`.

## Same engine, original weights: Qwen3.8-Flash-Next GSQ-RCO IQ3_S (RTX 5070 Ti)

The second Strata install (`/data/apps/Strata`, engine 0.1.44, its own
`run-iq3_s.sh` and `strata-iq3_s.json`, unchanged) runs the original
Qwen3.8-Flash-Next weights compressed by ISTA-DASLab (GSQ-RCO IQ3_S), 65,536
context, vision encoder on the GPU, no control vector. Its config pins it to
the RTX 5070 Ti too (`"gpu": 1`), so the hardware matches the uncensored run
exactly. Strata rejects `prompt + max_tokens` above the context window, so
`BENCH_MAX_TOKENS=64000` here (vs. 100,000 for the 524K uncensored config).
Script: `run_strata_iq3s.sh`.

| Benchmark | Result | Time | Tokens | Speed |
|---|---|---|---|---|
| Reasoning | 11/12 by `grade.py`, **12/12 on review** | 56s | 4,472 | 81.3 tok/s |
| Coding | **23/23** (first attempt) | 9m 37s | 49,933 | 86.7 tok/s |

- The one reasoning "fail" is a grader false negative: Q12's answer line is
  `ANSWER 12: Dan; Ellie` (tallest; shortest — correct, and its working says
  `Dan > Farah > Ellie`), but `grade.py` requires the words "tallest" and
  "shortest" in the answer.
- Coding passed on the first try with 50K tokens of reasoning, inside the 64K
  cap.

| | IQ3_S, original (0.1.44) | IQ3_XXS Orca Uncensored (0.1.45) |
|---|---|---|
| Coding | 23/23, 1st attempt, 9m 37s, 50K tokens | 23/23 on 2nd attempt, 14m 46s, 78K tokens (1st: loop, no answer) |
| Reasoning | 12/12 (11/12 by grader) | 12/12 |
| Decode speed | 81-87 tok/s | 88-92 tok/s |
| `strata` RSS | **50.7 GB** | 59.5 GB |
| System RAM available while running | 65.1 GB | 55.6 GB |
| CPU | avg 799%, max 808% (~8 cores), load ~7.7 | avg 785%, max 808%, load ~8 |
| RTX 5070 Ti | 15.7 GB, 99% util, max 196 W | 15.7 GB, 97% util, max 192 W |

Raw samples: `strata_iq3s_resources.csv`.

### IQ3_S moved to the RTX 5090

Same install and settings, with only the config's `"gpu"` changed to `0` by the
owner (RTX 5090, 32 GB). Run directories carry a `-5090` suffix
(`BENCH_LABEL=qwen3.8-flash-next-iq3_s-5090 ./run_strata_iq3s.sh`; Strata
serves any model name, so the label only names the directory).

| Benchmark | RTX 5070 Ti (16 GB) | RTX 5090 (32 GB) | Speed-up |
|---|---|---|---|
| Reasoning | 12/12*, 56s, 81.3 tok/s | **12/12**, 17s, 171.3 tok/s | 2.1x |
| Coding | 23/23, 9m 37s, 86.7 tok/s | **23/23**, 5m 23s, 160.8 tok/s | 1.9x |

\* 11/12 by `grade.py`, see the Q12 note above; on the 5090 the grader counts 12/12.

| Resources while generating | RTX 5070 Ti | RTX 5090 |
|---|---|---|
| GPU memory | 15.7 GB | 32.0 GB (the expert cache fills the card) |
| GPU util / power | 99%, avg 168 W, max 196 W | 99%, avg 371 W, max 470 W |
| `strata` CPU | avg 799% | avg 775% |
| `strata` RSS / RAM available | 50.7 GB / 65.1 GB | 50.7 GB / 65.0 GB |

On the 5090 the decode expert cache hit rate was 95.9%: twice the VRAM keeps
most of the experts a token needs on the card, so less is computed on the CPU
and generation roughly doubles. RAM use is unchanged (all experts stay in RAM
either way). Raw samples: `strata_iq3s_resources_5090.csv`.

---

# Results — GLM-4.7-Flash Q8_0 (dual-GPU)

`glm-4.7-flash:q8_0` (29.9B MoE, 34 GB loaded at `num_ctx=32768`) does not fit
the 5090 alone; Ollama split it 23.1 GB on the RTX 5090 + 10.6 GB on the RTX
5070 Ti, 100% GPU. Every other Ollama model was unloaded first, the miner was
stopped. Script: `run_glm_q8.sh`. Compared with the Q4_K_M rows from the
Machine 3 run above (same tag family, same settings).

| | Q4_K_M (Machine 3 run) | **Q8_0** |
|---|---|---|
| Coding | 10/23 (attempt 1: 0/23) | 11/23 (attempt 1: 0/23) |
| Reasoning | 12/12 | 11/12 by `grade.py`, **12/12 on review** |
| Coding speed | 186.6 tok/s | 166.5 tok/s |
| Reasoning speed | 189.6 tok/s | 166.9 tok/s |

- **Coding attempt 1 (0/23)**: Pydantic v1 API (`Field(regex=...)`, `const=`)
  against the installed Pydantic v2, so `main.py` fails at import. The same
  root cause as Qwen2.5-72B's stable 0/23.
- **Coding attempt 2 (11/23)**: Pydantic v2 API this time, but it passes
  `sqlite3.Row` objects straight into the response model without converting
  them to a dict, so every endpoint that returns a task fails validation
  (`TaskResponse: id Field required, input_type=Row`).
- **Reasoning**: the Q12 answer `Dan, Ellie` is correct; `grade.py` wants the
  words "tallest"/"shortest" (same false negative as Strata IQ3_S on the
  5070 Ti).
- Q8 does not fix GLM's coding: it is still the most run-to-run volatile model
  here and makes a different framework-API mistake each time. Q8 costs ~11%
  speed and the second GPU.

---

# Results — NVIDIA Nemotron 3.5 Lightning 30B-A3B (RTX 5090)

`nemotron-3.5-lightning:30b` (MoE, 30B total / 3B active, Ollama's default
Q4_K_M, 25.4 GB) ran 100% on the RTX 5090 alone (25.2 GB at `num_ctx=32768`;
5070 Ti idle, other Ollama models unloaded). Script:
`run_ollama_model.sh nemotron-3.5-lightning:30b` (generic single-model runner).

| Benchmark | Result | Time | Tokens | Speed |
|---|---|---|---|---|
| Reasoning | **12/12** | 18s | 3,717 | 500.9 tok/s |
| Coding | **23/23** (first attempt) | 27s | 12,532 | 469.3 tok/s |

The fastest model tested in this repo by a wide margin, and a perfect score
on both. It thinks a fair amount (12.5K tokens on the coding task vs. ~1.5K
for Qwen3-Coder-30B-A3B), but at ~470 tok/s the coding run still finishes in
27s, second only to Qwen3-Coder's 11s among the perfect scorers.

---

# Results — Ternary Bonsai 2 27B (PrismML, PQ2_0 ternary GGUF)

Weights `Ternary-Bonsai-2-27B-PQ2_0.gguf` (7.2 GB for 27B params) plus the
Q8_0 mmproj, served by the `llama-server` shipped in `Bonsai-demo/bin/cuda`
(PrismML's llama.cpp fork; stock llama.cpp does not run PQ2_0) with the flags
`scripts/start_llama_server.sh` uses: `-ngl 99 -fa on -c 131072 --temp 1.0
--top-p 0.95 --top-k 20 --min-p 0.05 --jinja`, thinking on, no reasoning
budget. Benchmarked through its OpenAI API (`run_openai_model.sh`,
`max_tokens` 100,000). Dual-GPU: the owner's server on :8081 (both cards
visible). Single-GPU: our own server on :8092 started by
`run_bonsai_per_gpu.sh` / `run_bonsai_followup.sh` with
`CUDA_VISIBLE_DEVICES`; on the 5070 Ti `-c 131072` does not fit (cudaMalloc
out of memory, ~18.7 GB needed), so it ran with `-c 65536` and
`max_tokens` 64,000.

| Setup | Coding | Reasoning | Coding time | Speed (coding / reasoning) |
|---|---|---|---|---|
| 5090 + 5070 Ti (12.6 + 6.1 GB) | **23/23** | **12/12** | 5m 43s, 36K tokens | 105.9 / 117.9 tok/s |
| RTX 5090 alone (17.2 GB), attempt 1 | 0/23 | **12/12** | 4m 0s, 31K tokens | 128.8 / 140.9 tok/s |
| RTX 5090 alone, attempt 2 | 11/23 | — | 4m 14s, 33K tokens | 128.5 tok/s |
| RTX 5070 Ti alone, `-c 65536` (12.7 GB) | 0/23 | **12/12** | 4m 21s, 21K tokens | 81.8 / 88.0 tok/s |

Coding failures, each different:
- 5090 attempt 1: `sqlite3.connect(..., row_factory=...)` (no such argument),
  so every DB call raises `TypeError`.
- 5090 attempt 2: `datetime.iso` instead of `.isoformat()` in the response
  builder, 12 tests fail.
- 5070 Ti: `await request.body()` inside a non-`async` function, a
  `SyntaxError` at import.

Same weights and server flags in every run, so the spread is the model's
run-to-run variance at its recommended `temperature 1.0`, not the GPU. One
perfect run out of four makes it a GLM-like "volatile" coder; reasoning was
perfect every time.

| Resources while generating | Dual-GPU | 5090 alone | 5070 Ti alone |
|---|---|---|---|
| `llama-server` CPU | ~104% (1 core) | ~103% | ~102% |
| `llama-server` RSS | 3.0 GB | 2.5 GB | 2.3 GB |
| GPU util | 53% + 44% | 97% | 98% |
| GPU power | ~310 W + ~145 W | ~492 W | ~250 W |

Everything is GPU-resident; unlike Strata it needs almost no RAM or CPU.
Split over two cards, each GPU idles half the time (layer split runs the
cards in turn), so one 5090 is ~20% faster than both together.
Raw samples: `ternary-bonsai-2-27b-pq2_0*_resources.csv`.

### Smaller Ternary Bonsai 2 sizes: 9B, 4B, 2B (each GPU alone)

Same server binary and flags as the 27B (`-c 131072`, `temp 1.0`, thinking on,
Q8_0 mmproj loaded), our own `llama-server` on :8092 pinned with
`CUDA_VISIBLE_DEVICES`; all three fit either card at the full 131K context.
Scripts: `run_bonsai_9b.sh`, `run_bonsai_9b_retry.sh`, `run_bonsai_size.sh 4B 2B`
(the latter retries a 0/23 coding run once). Coding shows attempt 1 → attempt 2
where attempt 1 was 0/23.

| Model (file size) | GPU | Coding | Reasoning | Speed (reasoning / coding) |
|---|---|---|---|---|
| 9B (2.4 GB) | 5090 | 0/23 → 12/23 | 11/12 | 348 / 335-349 tok/s |
| 9B | 5070 Ti | 0/23 → 5/23 | 10/12 by grader, 11/12 on review | 237 / 232-234 tok/s |
| 4B (1.1 GB) | 5090 | 9/23 | **12/12** | 467 / 474 tok/s |
| 4B | 5070 Ti | 0/23 → 5/23 | **12/12** | 351 / 353-355 tok/s |
| 2B (0.5 GB) | 5090 | 0/23 → 0/23 | 6/12 | 726 / 752 tok/s |
| 2B | 5070 Ti | 0/23 → 0/23 | 9/12 | 599 / 613-616 tok/s |

- Reasoning misses: 9B Q5 ("all but 9 die" → 8) on both cards; 9B on the 5070
  Ti also answered Q3 as "Cleo, Fish" (wrong pairing) and Q12 "Dan, Ellie"
  (correct, grader false negative). 2B misses arithmetic and trick questions
  (Q2, Q4, Q5, Q6, Q7, Q10) and gets Q12 wrong ("Farah" shortest).
- Coding at 9B/4B: code runs but breaks the spec (wrong status codes 200/405/422
  instead of 201, missing validation) or uses wrong APIs
  (`from sqlalchemy import create_async_engine`, Pydantic v1 `validator(mode=)`,
  `main.app` missing). 2B never produced importable code (syntax errors,
  `APIRouter.register`).
- The 4B is the surprise: perfect reasoning on both cards at 350-470 tok/s
  from a 1.1 GB file, but it is not a coder. Only the 27B wrote a fully
  correct `main.py` (once in four runs).

| Resources while generating | 9B | 4B | 2B |
|---|---|---|---|
| VRAM at 131K context (5090 / 5070 Ti) | 8.2 / 7.9 GB | 6.9 / 6.5 GB | 3.6 / 3.2 GB |
| GPU util | 94-96% | 92-94% | 88-90% |
| GPU power, avg (5090 / 5070 Ti) | 389 / 246 W | 292 / 182 W | 265 / 152 W |
| `llama-server` CPU / RSS | ~1 core / 1.6 GB | ~1 core / 1.5 GB | ~1 core / 1.3 GB |

---

# Results — Mistral AI: Devstral Small 2 and Mistral Small 3.2 (24B, RTX 5090)

Benchmarked by `run_queue.sh` (watches Ollama for new Mistral-family tags and
runs `run_ollama_model.sh` on each, one at a time, with resource sampling;
`retry_coding.sh` gives a 0/23 coding run its one retry). Both ran 100% on the
RTX 5090 alone (19 GB at `num_ctx=32768`).

| Model | Coding | Reasoning | Coding time | Speed |
|---|---|---|---|---|
| **Devstral Small 2** (`devstral-small-2:latest`, 24B, vision) | **23/23** (first attempt) | 10/12 | 16s, 1,486 tokens | 95 tok/s |
| **Mistral Small 3.2** (`mistral-small3.2:latest`, 24B, vision) | 0/23 → **23/23** | **12/12** | 23s, 1,726 tokens (attempt 2) | 97-99 tok/s |

- Both answer directly with almost no reasoning (~1.5-1.7K tokens for the
  coding task), so despite a modest ~95 tok/s (dense 24B) the coding run takes
  16-23s, in the same league as Qwen3-Coder-30B-A3B (11s) and Nemotron 3.5
  Lightning (27s).
- Devstral's reasoning misses are real: Q5 ("all but 9 die" → 8) and Q7
  ("a kilogram of feathers or a pound of steel" → "they weigh the same").
- Mistral Small 3.2's first coding attempt called Pydantic `Field()` with
  positional arguments (v2 takes at most one), failing at import; the retry
  passed everything.

### Mistral Medium 3.5 (128B dense), run 1 of 3

`mistral-medium-3.5:latest` (127.7B dense, Q4_K_M, 39 GB loaded at 32K context): Ollama placed 77% on the GPUs and 23% on the CPU, which leaves the cards mostly waiting (0.9 tok/s, ~780% CPU, 78 GB RSS). **12/12 reasoning** (955 tokens, 18m 13s) and **23/23 coding** (1,401 tokens, 25m 48s) on the first run. Runs 2-3 follow (`repeat_runs.sh`).

---

# Efficiency: tokens per solved test

A second axis next to score and speed: how many tokens a model generates to get
there (reasoning included). Full per-run tables, regenerated from the run
directories by `python3 efficiency.py`: [`EFFICIENCY.md`](EFFICIENCY.md). Run
names there are the run directories, so older rows (`*-bench`, plain tags) come
from the earlier machines described above.

Perfect coding runs (23/23), by tokens:

| Model | Coding tokens | Tok/solved test | Wall-clock |
|---|---|---|---|
| Mistral Medium 3.5 (128B dense) | 1,401 | 61 | 25m 48s (0.9 tok/s) |
| Devstral Small 2 | 1,486 | 65 | 16s |
| Qwen3-Coder-30B-A3B | 1,676 | 73 | 11s |
| Mistral Small 3.2 | 1,726 | 75 | 23s |
| Qwen3.8-27B (dual-GPU run) | 3,097 | 135 | 59s |
| Gemma4-26B (5070 Ti run) | 8,126 | 353 | 1m 59s |
| Nemotron 3.5 Lightning | 12,532 | 545 | 27s |
| Nemotron 3.5 Bolt | 15,588 | 678 | 1m 42s |
| Qwen3.8-27B (5070 Ti run) | 25,541 | 1,110 | 39m 30s |
| Ternary Bonsai 2 27B | 36,252 | 1,576 | 5m 43s |
| Strata IQ3_S | 49,933-50,340 | 2,171-2,189 | 5m 23s-9m 37s |
| Strata Orca Uncensored | 78,261 | 3,403 | 14m 46s |

- Two styles: models that answer directly (Mistral, Devstral, Qwen3-Coder)
  need ~1.4-1.7K tokens for the whole task; thinking models need 8-50x more.
- More tokens do not buy correctness: Sage-A1.5 Q4 used 38.6K for 13/23 and
  Bonsai 27B 21-36K for anything from 0 to 23/23.
- Token count decides wall-clock only together with speed: Lightning spends 7.5x
  Qwen3-Coder's tokens but finishes in 27s at ~470 tok/s, while Mistral Medium
  3.5 is the most token-efficient model tested and still the slowest to answer on
  this hardware (0.9 tok/s).
- The same model can vary a lot between runs: Qwen3.8-27B used 25.5K tokens on
  the 5070 Ti box and 3.1K on the dual-GPU box, both 23/23.

---

# Results — heavy models, 3 runs each: Mistral Medium 3.5 and Nemotron 3.5 Super

Three full runs of both benchmarks per model (`repeat_runs.sh`; runs 2-3 live in
`runs/<tag>-run2`, `-run3`), to tell a stable score from a lucky one. Same
settings every run: Ollama, `num_ctx=32768`, every other model unloaded, both
GPUs otherwise idle (miner, ComfyUI and Strata stopped). Resource samples:
`<tag>[-runN]_resources.csv`.

## Mistral Medium 3.5 (`mistral-medium-3.5:latest`, 127.7B dense, Q4_K_M, 80 GB on disk)

| Run | Coding | Coding tokens / time | Reasoning | Reasoning tokens / time |
|---|---|---|---|---|
| 1 | 23/23 | 1,401 / 25m 48s | 12/12 | 955 / 18m 13s |
| 2 | 21/23 | 1,457 / 26m 43s | 12/12 | 1,560 / 28m 58s |
| 3 | 23/23 | 1,485 / 27m 38s | 12/12 | 909 / 17m 15s |
| **Total** | **67/69** | ~1.45K per run | **36/36** | |

- Run 2's two failures: the list filters by `completed` / `priority` pass one
  SQL binding too many (`uses 3, and there are 4 supplied`).
- Stable and the most token-efficient model tested, at 0.9 tok/s on this box:
  ~30 GB on the 5090, 3.6 GB on the 5070 Ti, the rest on the CPU (`ollama ps`:
  23%/77% CPU/GPU). While generating: ~780% CPU, 79 GB RSS, 5090 at ~3% average
  util (~82 W), 5070 Ti idle. Each token passes every layer, so the dense model
  waits on the CPU-resident layers.

## Nemotron 3.5 Super (`nemotron-3.5-super:120b`, 123.6B MoE, 512 experts, Q4_K_M, 90 GB on disk)

| Run | Coding | Coding tokens / time | Reasoning | Reasoning tokens / time |
|---|---|---|---|---|
| 1 | 23/23 | 6,685 / 4m 42s | 12/12 | 2,321 / 2m 04s |
| 2 | 23/23 | 7,575 / 5m 33s | 12/12 | 4,105 / 3m 17s |
| 3 | 23/23 | 11,391 / 8m 14s | 12/12 | 2,521 / 2m 09s |
| **Total** | **69/69** | 6.7-11.4K per run | **36/36** | |

- Perfect in all three runs, 23-25 tok/s, 28x Mistral Medium's speed at a
  similar size because only ~12B parameters are active per token.
- Placement: `ollama ps` reports "40 GB, 2%/98% CPU/GPU", but that counts only
  the GPU-loaded part. The runner's RSS is 84 GB: ~29.6 GB on the 5090 and
  ~9.8 GB on the 5070 Ti hold the shared layers and some experts, and the
  remaining experts sit in RAM and are computed on the CPU (~750-780% CPU while
  generating; both GPUs only 5-8% busy, 84 W + 57 W).
- Token use varies run to run (coding 6.7K to 11.4K) while the score does not.

---

# Results — Devstral 2 (123B dense), 3 runs

`devstral-2:latest`: Mistral's Devstral 2, `mistral3` architecture, 125.0B parameters, dense,
Q4_K_M, 74 GB on disk. Same protocol as the other heavy models: three full runs
(`run_queue.sh` for run 1, `repeat_runs.sh` via `repeat_when_done.sh` for runs 2-3), Ollama
`num_ctx=32768`, model alone on idle GPUs, resource samples in
`devstral-2_latest[-runN]_resources.csv`. Sampling is the Modelfile default,
**temperature 0.15** (see the note on temperatures below).

| Run | Coding | Coding tokens / time | Reasoning | Reasoning tokens / time |
|---|---|---|---|---|
| 1 | 23/23 | 1,373 / 18m 28s | 12/12 | 1,068 / 14m 41s |
| 2 | 23/23 | 1,657 / 22m 17s | 12/12 | 1,074 / 14m 46s |
| 3 | 23/23 | 1,371 / 18m 24s | 12/12 | 1,059 / 14m 23s |
| **Total** | **69/69** | ~1.4-1.7K per run | **36/36** | |

- Perfect in all three runs, 1.25 tok/s on every run.
- Placement: `ollama ps` "53 GB, 13%/87% CPU/GPU": 30.2 GB on the 5090, 13.9 GB on the 5070 Ti,
  the rest read by the CPU from the mmapped file (RssFile ~70 GB, RssAnon 5.6 GB). While
  generating: ~800% CPU, both GPUs ~2% busy, so like Mistral Medium it waits on the CPU; it is
  ~40% faster than Mistral Medium (0.9 tok/s) because a larger share of it sits in VRAM.
- Full per-model memory/CPU table: [`RESOURCES.md`](RESOURCES.md).

## Note on sampling temperatures

The benchmarks send no sampling options, so every Ollama model runs with its Modelfile
defaults: temperature 0.15 for Devstral 2, Devstral Small 2 and Mistral Small 3.2; 1.0 (top_p
0.95) for Nemotron 3.5 Super and Lightning, GLM-4.7-Flash, Sage-A1.5 and Gemma4; no explicit
value (Ollama default 0.8) for Mistral Medium 3.5 and Nemotron 3.5 Bolt. Run-to-run stability
of the Mistral models is therefore partly the low temperature; Super's 3/3 at 1.0 is the
stronger result.
