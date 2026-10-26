# PRISM RUNNER: an agentic coding task for local LLMs

The two benchmarks in the repository root grade one-shot answers. This section is about a
**long agentic task**: the model gets one prompt in Open WebUI with a terminal attached
(`open-terminal` tools: `run_command`, `write_file`, `read_file`, `replace_file_content`,
`get_process_status`, ...). It has to build a complete single-file Three.js game, save it in the
terminal's workspace, and check its own work. No human help during the run.

It shows things the pytest suite does not:
- whether a model explores its environment;
- whether it recovers from tool errors;
- whether it really verifies its output;
- what a long tool loop costs in time, tokens and context.

- Prompt as used: [`prompts/prism-runner-v1.md`](prompts/prism-runner-v1.md). An improved v2 with
  an environment and test section is [`prompts/prism-runner-v2.md`](prompts/prism-runner-v2.md);
  no run has used v2 yet.
- Hardware: Machine 3 in [`../HARDWARE.md`](../HARDWARE.md): Ryzen 7 9800X3D, 123 GB DDR5,
  RTX 5090 32 GB + RTX 5070 Ti 16 GB. During runs 1, 3 and 5 the 5070 Ti was busy with a miner
  and the model had the 5090 alone.
- Dates: 24–26 October 2026. One run per model unless noted. Temperature and other sampling
  settings were left at each engine's default.

## The task in short

Exactly one `prism-runner.html`: a third-person endless runner on a 3-lane neon track with jump,
slide, pause, restart and mute. It has to support touch and fair obstacle patterns, and use a
fixed-timestep simulation, pooled objects, synthesized WebAudio and `localStorage` with failure
handling. The file should be 700–1200 lines with Three.js pinned through an importmap, and must
not contain TODOs. The prompt ends with a self-verification list: re-read the file, trace three
scenarios, check fairness, and load the page in a browser if one is available. The model must not
claim anything it did not verify.

## Results

How each game was judged: the reviewer loaded every file in headless Chrome on a Mac
([`tools/headless_check.js`](tools/headless_check.js), puppeteer-core with Metal ANGLE). The check
loads the page, takes a screenshot, presses START or Enter, then steers and jumps, takes a second
screenshot ~5.5 s later, and collects page errors, console errors and failed requests. *Works*
means no errors, a rendered scene, and score and distance that grow after start.

| # | Model (engine, quant) | GPUs used | Context | Wall time | Generated tokens | Decode tok/s | Saved the file | Real self-test | Lines | Game works |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **DeepSeek-V4.1-Flash-1017** (Maya v1.1.26 `maya-ds4`, Maya-S) | 5090 | 262K | ~5 h 50 min | ~250–260K | ~18 | ✅ | ✅ built a browser test rig | 1200 | ✅ |
| 2 | **DeepSeek-V4.1-Flash-1017** (Maya, same quant) | 5090 + 5070 Ti | 262K | 4 h 55 min | 357K | 22.8 | ✅ | ✅ test rig again, bot runs | 1198 | ✅ |
| 3 | **Qwen3.8-Flash-Next IQ3_S** (Strata, speculative decoding) | 5090 | 64K | **27 min** | 88K | **~176** | ✅ | ⚠️ installed Node, never ran it on the game | 1253 | ✅ best visuals |
| 4 | **GLM-5.3-Flash Maya-M IQ2_S** (Maya v1.1.28, DFlash2 drafter) | 5090 + 5070 Ti | 512K | **48 min** | 94.5K | ~33 | ✅ after one `~` failure | ⚠️ JS parse (esprima) and manual traces, no browser | 1056 | ✅ |
| 5 | Nemotron 3.5 Super 120B (Ollama, MTP) | 5090 + CPU | 90K+ | 1 h 17 min | ~13K in the last reply | ~24 | ✅ | ❌ `wc`, `tail`, brace count, `http.server` | 860 | ❌ missing `_resize()` |
| 6 | Nemotron 3.5 Lightning 30B-A3B (Ollama, MTP) | 5090 + 5070 Ti | — | ~3 min | — | **~385** | ✅ found the path itself | ❌ `wc`, `grep`, `curl`, no JS execution | 1470 | ❌ CSS pasted into JS |
| 7 | Qwen3-Coder 30B-A3B (Ollama) | 5090 | 85K peak | ~15 min | 70K | 62–73 | ❌ 7 × `Permission denied`, then claimed success | ❌ none | 1376 | ❌ black screen |
| 8 | Devstral Small 2 24B (Ollama), best of 3 attempts | 5090 | 40K, q8_0 KV | ~2.5 min | — | 70.9 | ⚠️ wrote to `/tmp` | ❌ none | 1005 | ❌ `THREE is not defined` |
| 9 | Devstral 2 125B dense (Ollama) | mostly CPU | 64K | 2 h 24 min | 13.6K | **0.81** | ❌ 2 × `Permission denied`, gave up | ❌ none | 677 | ❌ black screen |
| 10 | Nanbeige4.3-33B Q4_K_M (Ollama, bartowski GGUF) | 5090 + 5070 Ti | 512K → 64K | ~2.5 h, then failed | ~64K per attempt | 3 → 45 | ❌ nothing written | ❌ none | — | ❌ context full |

Working games: **DeepSeek (both runs), Strata and GLM**. Every model at 30B or below, and both dense
Mistral-family models, shipped a game that does not start.

Screenshots, the exact files and 30-second resource samples are in `runs/<NN-model>/`.

### Per-run notes

**1–2. DeepSeek-V4.1-Flash on Maya: the only real agent.** Run 1 made ~155 tool calls
(116 `run_command`, 17 `write_file`, 14 `read_file`). Run 2 made ~228, plus 88 polls of background
processes. It built a test environment in a container without root and without a browser:
- It downloaded Node 20. `.tar.xz` failed because `xz` was missing, so it used `.tar.gz`.
- It installed puppeteer with Chrome. Chrome would not start without libgbm, libxcb, pango,
  cairo, asound and others. It fetched those `.deb` packages with `apt-get download`, unpacked
  them into `/tmp/sysroot` with `dpkg -x`, and pointed `LD_LIBRARY_PATH` there.
- WebGL2 was unavailable. It wrote a probe script and searched Chrome flags until a SwiftShader
  combination worked.
- It then drove the game with scripts:
  - console errors and screenshots;
  - HUD and overlay state;
  - an audit of tens of thousands of generated obstacle patterns. Run 1 found 81 violations of
    the "never block all 3 lanes / ≥0.9 s reaction window" rules and fixed them;
  - a memory-growth check (+0.57 MB) and a frame-time check.
- In run 2 a bot drove 655 m without a collision. The model also found and fixed a row-spacing bug.
- It rewrote the file several times to fit the 1200-line limit. The first full version in run 1
  had 1545 lines (`prism-runner.v1-first-write.html`). After each edit it re-checked the syntax
  with Node.

Most of the time went into verification, which is why it produced the most complete game.

Run 2 **hit the context limit**: the last reply stopped at 261,542 + 594 of 262,144 tokens, so the
final test round and the summary are missing. The saved file is the one from the previous round,
and it works. The second GPU gave +25–30% decode, from ~17–18 to 22.8 tok/s.

**3. Qwen3.8-Flash-Next on Strata: clean code on the first try.** It checked `$HOME`, the
workspace, `node`/`chromium` and access to unpkg. It downloaded Node 20 into `/tmp` (unpacking the
`.tar.xz` with Python) and confirmed `node ok v20.18.1`. Then it made a single `write_file` and
stopped: it never ran Node or a browser against the game. The game works anyway, and has the best
visuals: glowing pillars, particles, a star field and a coyote-time input buffer. Two caveats:
- the context peaked at 65,181 of 65,536, so there was no room left for another round;
- the file is 4% over the line limit.

**4. GLM-5.3-Flash on Maya: best balance.** It made about 20 tool calls: 6 `run_command`, 7
`get_process_status`, 2 `write_file`, 3 `replace_file_content`, 1 `read_file` and 1
`list_processes`. The first `write_file` to `~` failed; the second, to the absolute path, worked.
It verified with an esprima ES-module parse (`PARSE OK`), checked every Three.js API it used against
r160, and traced start, death and restart, pause in mid-jump, and fairness by hand. It did not try
to get a browser.

It used 4× fewer output tokens than DeepSeek (94.5K) and finished in 48 min. The 14.5K-token file
write ran at 36.9 tok/s, with the DFlash2 drafter accepting 98.7% of proposed tokens. The game works.

**5. Nemotron 3.5 Super 120B.** It saved the file by absolute path and "verified" it with `wc`,
`tail`, a Python brace counter and `curl` to `http.server`, none of which execute JavaScript. The
`Game` constructor calls `this._resize.bind(this)`, but the method was never written, so the page
throws on load and START does nothing. With the 5-line method added
(`prism-runner.fixed-by-reviewer.html`) the game runs, but the scene is primitive and the camera is
wrong. It is also the simplest game against the requirements: no fixed timestep, no seeded
patterns, no coyote time.

**6. Nemotron 3.5 Lightning 30B.** The fastest model, at ~385 tok/s with MTP; the whole task took
~3 minutes. After `Permission denied` on `~` it switched to `/home/user/workspace/...` by itself.
But the WebGL-fallback block contains raw CSS inside JavaScript (line 295:
`warning.style.top: 0; left: 0; ...`), so the script never parses. The bug is already in its first
write (`prism-runner.first-write.html`), not an artefact of its later `sed` edits. `node --check`
would have caught it in a second.

**7. Qwen3-Coder 30B.** It made no exploratory commands, only 7 `write_file` calls to `~/...` or
relative paths, all `Permission denied`. **Then it told the user "I've successfully created the
complete Prism Runner game."** The code, recovered from the tool-call arguments, has no console
errors but renders a black screen with distance stuck at 0.

**8. Devstral Small 2 24B, three attempts.**

| Attempt | Context and KV | Placement | Decode | Saved | Game |
|---|---|---|---|---|---|
| 1 | 256K FP16 | 5090 + 5070 Ti + CPU (55 GB) | 6.5 tok/s | no, printed into chat ("no permission") | `THREE is not defined`; with the import added: `Assignment to constant variable`, audio `stop()` before `start()`, black screen |
| 2 | 64K FP16 | 5090 + 5070 Ti (29.5 GB) | 50.8 tok/s | restarted by the user | — |
| 3 | 40K q8_0 | 5090 only (18 GB) | 70.9 tok/s (89.9 on a 4K prompt) | to `/tmp` | `THREE is not defined` again |

The model repeatedly forgets the `import * as THREE from 'three'` line even though the importmap is
there.

**9. Devstral 2 125B (dense).** The weights are ~75 GB and the FP16 KV cache at 64K is ~22 GB, so
most layers ran on the CPU at ~790% CPU with the 5090 at ~4% load. Decode was **0.81 tok/s**, and
13.6K tokens took 2 h 24 min. Two `write_file` calls to `~` and to a relative path failed; it wrote
"let me try another way" and stopped. The last tool-call code has 677 lines and renders a black
screen.

**10. Nanbeige4.3-33B (dense, released 2026-10-24), failed.**
- Attempt 1 ran with `num_ctx` 524288. The KV cache was ~112 GB (~208 KB per token, 52 layers,
  8 KV heads), so only ~17 of 52 layers fit in 44 GB of VRAM. The CPU did the rest at 3 tok/s with
  both GPUs at 0%.
- Attempt 2 used 64K, temperature 1.0, top_p 0.95 and top_k 0 (the model card's agentic
  settings). Everything fit in VRAM and decode was **45 tok/s**. But its first reply ran 66K tokens
  without a single tool call. At 64K Ollama's `--context-shift --keep 4` silently dropped half the
  history, including the task. The user then restarted the turn.
- Attempt 3 filled the 64K window again without writing a file and stopped with
  `request (65536 tokens) exceeds the available context size (65536 tokens)`. Context shift only
  trims during generation; a request larger than the window is rejected. The working directory
  stayed empty. 96K would fit in VRAM (~20 GB of KV at bf16), but the model spends its budget on
  reasoning and drafts in chat; prompt v2 (write the file first, report only path and hash) is the
  better retry.

## Resources

Medians over the active samples (30 s interval); peaks are maxima.

| # | Model | RAM / 5070 Ti link | Process RAM peak | CPU median | 5090: load / W / VRAM peak | 5070 Ti: load / W / VRAM peak | Bound by |
|---|---|---|---|---|---|---|---|
| 1 | DeepSeek (Maya), 1 GPU | 3600 / Gen5 | 111 GB | ~600% | 99% / 159 W / 31.0 GB | miner | CPU experts + RAM + NVMe |
| 2 | DeepSeek (Maya), 2 GPUs | 3600 / Gen5 | 110 GB | ~890% | 44% / 153 W / 31.0 GB | 99% / 88 W / 15.1 GB | CPU experts + NVMe reads (~0.8 GB/s); 5070 Ti |
| 3 | Qwen3.8 (Strata) | 3600 / Gen5 | 51 GB | ~210% | ~100% / ~376 W while decoding / 31.3 GB (275 MB free) | miner | 5090 VRAM |
| 4 | GLM-5.3 (Maya) | 6400 / **Gen3** | 94 GB | ~800% | 80% / 222 W / 31.0 GB | 94% / 104 W / 15.1 GB | CPU experts + PCIe; 5070 Ti at PCIe 3.0 x8 |
| 5 | Nemotron Super 120B | 3600 / Gen5 | 70 GB | ~690% | 4% / 81 W / 30.3 GB | miner, later ~10 GB | CPU |
| 6 | Nemotron Lightning 30B | 3600 / Gen5 | 5.8 GB | ~380% | 35% / 206 W / 17.8 GB | 52% / 146 W / 11.6 GB | both GPUs in turn |
| 7 | Qwen3-Coder 30B | 3600 / Gen5 | 1.1 GB | ~450% | 96% / 500 W / 24.6 GB | idle | 5090 VRAM (KV at 85K) |
| 8 | Devstral Small 2, attempt 1 / 3 | 3600 / Gen5 | 24 GB / 14.5 GB | ~790% / ~410% | 6% / 95 W, then 95% / 500 W | 5%, then idle | CPU, then 5090 VRAM |
| 9 | Devstral 2 125B | 3600 / Gen5 | 82 GB | ~800% | 0–4% / 79 W / 30.4 GB | 0% / 43 W / 14.5 GB | CPU + RAM (~40 GB/s) |
| 10 | Nanbeige 33B, 64K | 6400 / **Gen3** | 2.2 GB | ~450% | 50% / 339 W / 23.5 GB | 44% / 142 W / 11.3 GB | both GPUs in turn |

RAM is the memory clock in MT/s (3600 before EXPO was enabled on 2026-10-25 22:04). The 5070 Ti
link is from `nvidia-smi`: "Gen5" for runs before that reboot is inferred from `gen.max 5` on
2026-10-22. Runs 4 and 10 had the 5070 Ti at PCIe 3.0 x8; with Gen5 forced, GLM's benchmark rose
from ~40 to ~45 tok/s ([`../engine-bench-maya/`](../engine-bench-maya/)).

CPU around 400–450% for a model that is fully on the GPU is llama.cpp threads busy-waiting. CPU
around 800% means 8 threads doing real work.

Where the time goes (DeepSeek run 2): generation 258 min (92%), prompt reading 24 min (8%). KV reuse
is ~99.7%, so each tool step only re-reads the new 400–4000 tokens. Long agentic runs on this box
are **bound by decode speed × tokens generated**: DeepSeek generated 357K tokens at 22.8 tok/s, GLM
94.5K at ~33, Strata 88K at ~176.

What filled DeepSeek's 262K context in run 2 (characters, reasoning excluded):

| Item | Characters | Share |
|---|---|---|
| `write_file` with the whole file, 10 × ~55 KB | 318K | ~43% |
| `get_process_status`, 88 polls | 172K | ~23% |
| `run_command` and output | 152K | ~21% |
| `replace_file_content` | 41K | ~6% |
| `read_file` | 33K | ~4% |

The 700–1200-line limit made it rewrite the whole file 5–6 times. Most of the context went to those
rewrites.

## What we learned

1. **The terminal tool is a trap, and how a model handles it is a test in itself.** `~` is not
   expanded (it becomes `/app/~`), and the working directory `/app` is read-only, so only absolute
   paths like `/home/user/workspace/...` work. Models that started by exploring (`pwd`, `ls ~`)
   found the right path at once. Qwen3-Coder and both Devstrals never looked. Lightning and GLM hit
   the error once and recovered.
2. **Saving is not verifying.** Both Nemotrons "verified" with `wc`, `head`, brace counting and
   `curl`, none of which execute JavaScript, and shipped games that do not start. Every working game
   came from a model that either ran the code (DeepSeek) or writes clean code on the first try
   (Strata, GLM).
3. **Only DeepSeek behaved like a full agent.** It built its own browser test rig without root.
   That is also why it took 5–6 hours: most of the time was verification, not writing.
4. **Honesty matters.** Qwen3-Coder reported success after seven failed writes. For an agent this
   is worse than failing.
5. **Context settings matter more than the model for speed.**
   - Devstral Small 2: 6.5 tok/s at 256K → 70.9 tok/s at 40K q8_0.
   - Nanbeige 33B: 3 tok/s at 512K → 45 tok/s at 64K, and 64K then ran out before it wrote a file.

   An oversized `num_ctx` turns into a KV cache that pushes whole layers to the CPU.
6. **Ollama silently drops history when the context is full** (`--context-shift --keep 4`). The
   model keeps going without the task. Maya refuses a request that does not fit instead, which is
   easier to notice. Size the context with headroom, and watch `n_prompt_tokens` in llama-server's
   `/slots`.
7. **Dense 120B+ models are not practical on this box.** Devstral 2 managed 0.8 tok/s. Big models
   only work here as MoE on expert-offload engines: Maya and Strata.
8. **Speculative decoding pays off on code.** Strata reached ~176 tok/s, Lightning ~385 with MTP,
   and GLM's DFlash2 had 98.7% acceptance while writing the file.
9. **The environment carries state between runs.** DeepSeek left Playwright/Chromium in the
   container and libraries in `/tmp/sysroot`, so later models found a browser they did not install.
   For a fair comparison, either reset the container before each run or keep it deliberately and
   say so. `/tmp` is wiped when the container restarts.

## Prompt v2

[`prompts/prism-runner-v2.md`](prompts/prism-runner-v2.md) keeps the task and adds:
- a workspace and tools section: absolute paths only, check every write, the environment facts
  (Debian 13, user `user`, no root, Python 3.12 with `pip --user`, internet);
- a test environment recipe (Playwright via `pip --user`, `apt-get download` + `dpkg -x` for
  missing libraries, SwiftShader flags) with a **budget of ~20 commands**, after which the model
  falls back to static checks and says what failed;
- a mandatory `smoke_test.py` (start, 10 s of play, pause, death and restart, console errors, a
  report file) using a read-only `window.__prism` hook;
- no full file in the answer (path, line count and sha256 instead), which saves 12–15K output
  tokens per run.

Suggested additions from these runs: "edit with `replace_file_content` instead of rewriting the
whole file", "tests print a ≤20-line summary", and "think and write in English". Russian costs ~1.6×
the tokens on DeepSeek's tokenizer.

## Prompt v2 runs (2026-10-26)

Same task with [`prompts/prism-runner-v2.md`](prompts/prism-runner-v2.md), each in a new Open WebUI
chat. Machine state: RAM 6400 EXPO, both GPUs at PCIe Gen5 x8. Files are in
[`runs-v2/`](runs-v2/): `model-files/` is what the model left in its working directory, `review/`
holds the reviewer's headless-Chrome screenshots.

| # | Model | Context | Wall time | Decode tok/s | Saved the file | Ran its own test | Lines | Game works |
|---|---|---|---|---|---|---|---|---|
| 11 | Nanbeige4.3-33B Q4_K_M (Ollama) | 120K, then 32K in a new chat | ~40 min, no result | 27 at 46K deep, ~45 short | ❌ | ❌ | — | ❌ no tool call at all |
| 12 | Qwen3-Coder 30B-A3B (Ollama) | 120K | **~2 min** | not measured | ✅ first try, absolute path | ❌ wrote `smoke_test.py`, never ran it | 1050 | ❌ `let audioContext` declared twice |
| 13 | **Qwen3.8-Flash-Next IQ3_S** (Strata) | 64K → **262K** | **~6 min** (2nd attempt) | 143–172 | ✅ | ✅ **12/12 PASS**, 6 screenshots | 888 | ✅ |
| 14 | **GLM-5.3-Flash Maya-M IQ2_S** (Maya v1.1.28, 2 GPUs) | 512K | ~62 min, of which ~23 min a hung tool call | ~37 | ✅ | ✅ **18/18 PASS** after the reviewer killed its orphaned server | 877 | ✅ |

**11. Nanbeige4.3-33B.** In the 120K chat the first step already had a 32K prompt and the model
generated ~16K tokens without a tool call. A new chat started with Open WebUI's default 32K
context: one reply ran to **~69.5K tokens** while Ollama's context shift dropped half the window
five times; the model never called a tool and the directory stayed empty. With four failed attempts
over v1 and v2, this model does not do agentic tool use in this setup.

**12. Qwen3-Coder 30B.** Prompt v2 fixed what broke run 7: the file was saved on the first try to
`/home/user/workspace/qwen3-coder-30b/`, and a Playwright `smoke_test.py` was written. The model
then stopped without running the test, so it never saw the error. Deleting the second
`let audioContext = null;` (line 204) is enough to start the game (reviewer's check; the HUD
shows no score after start).

**13. Qwen3.8-Flash-Next (Strata).** The first attempt ran out of Strata's `--max-context 65536`
after saving a working 907-line game (`attempt1-64k/`, no errors in the reviewer's check). After
raising it to 262144 in `strata-iq3_s.json` (`--kv-resident 32768` keeps only 32K positions in VRAM,
so the larger window costs ~3.5 GB of RAM and no VRAM), the rerun took ~6 minutes, peaked at an
81K-token prompt, and finished every step of v2: the game, `smoke_test.py` through the
`window.__prism` hook (boot, start, 10 s of play, score and distance growth, pause freezes the
score, resume, death within 60 s, restart resets), `smoke-report.txt` with **OVERALL: PASS**, and
six screenshots. Compared with run 3 under v1 (27 min, Node installed but never run on the game),
v2 cut the time 4.5× and added a real browser test. Strata warned of only 272 MiB of free VRAM at
request start (`--vision` keeps ~1.4 GB for the image encoder); decode did not suffer here.

**14. GLM-5.3-Flash (Maya, both GPUs).** Saved the game four minutes in, revised it three times
over ~23 minutes and wrote a Playwright `smoke_test.py`, then ran it as
`timeout 180 python3 smoke_test.py 2>&1 | tail -40`. The test started `http.server` in a thread with
`subprocess.run` and never stopped it. After `timeout` killed the test, the orphaned server kept the
pipe open, `tail` never got EOF, and the terminal tool never returned: the shell sat as a zombie
and Maya idled for **~23 minutes**. Open WebUI did not time it out. The user then killed the server
(`docker exec open-terminal kill <pid>`), the tool returned, and GLM fixed its test in three more
rounds (~10 minutes): `smoke-report.txt` with **18/18 PASS** (hook, start, distance/score growth,
no NaN, a random-play death and restart, pause freezes the score, resume, death, restart resets
the score, 16.7 ms per frame, no console errors), plus six screenshots. The game file itself did
not change after 16:51 (sha256 `e8148da4…`); the reviewer's headless check also passed (score
10 → 76 in 3 s). Against run 4 under v1 (48 min, ~33 tok/s, no browser test), v2 at RAM 6400 +
Gen5 decoded faster (~37 tok/s) and ended with a real browser test.
Lesson for prompt v3: "start servers with `Popen` and kill them in `finally`; never pipe a
command that can leave a child behind into `tail`".

| # | RAM / links | Process RAM peak | CPU median | 5090: W / VRAM peak | Bound by |
|---|---|---|---|---|---|
| 11 | 6400 / Gen5 | 2.3 GB | ~465% | ~348 W / 30.3 GB at 120K | 5090 + 5070 Ti VRAM; attention at depth |
| 12 | 6400 / Gen5 | ~1 GB | ~420% | ~349 W / 29.9 GB | 5090 VRAM |
| 13 | 6400 / Gen5 | 54 GB | ~520% | ~373 W / 32.0 GB | 5090 VRAM (full) |
| 14 | 6400 / Gen5 | 93 GB | ~705% | ~245 W / 31.6 GB (5070 Ti 15.4 GB) | CPU experts + both GPUs |

What v2 changed, in short: absolute paths and "check every write" removed the `Permission denied`
failures; asking for a test made three of four models write one, and both large MoE models (Strata, GLM)
ended with a PASS report; GLM only after a human killed the web server its first test left behind.
A missing `num_ctx` in a new Open WebUI chat silently means 32K, and Strata's own
`--max-context` is a second, separate limit: set both before a run.

## Cost if run on paid APIs

From the Open WebUI database (2026-09-06 to 10-25: 203M input tokens, of which 146M cached, and
3.8M output): one DeepSeek PRISM run would cost about **$1.2 on DeepSeek's API** and about **$14 on
Claude Sonnet 5.5**. All local usage over those seven weeks would have cost about $11–25 on DeepSeek
or GLM APIs and about $170–200 on Sonnet 5.5.

## Files

- `runs-v2/<NN-model>/`: prompt v2 runs (see above): `model-files/` as left by the model,
  `review/` the reviewer's screenshots, `samples.csv` resource samples.

- `runs/<NN-model>/prism-runner*.html`: the game as the model left it.
  - `*.fixed-by-reviewer.html` and `*.import-added-by-reviewer.html` are the reviewer's minimal
    patches, used only to see how far the code gets;
  - `*.from-toolcall.html` and `*.last-toolcall.html` were recovered from tool-call arguments when
    the model failed to save;
  - `*.from-chat.html` was printed into the chat.
- `runs/<NN-model>/title.png`, `play.png`: headless-Chrome screenshots (1280×720).
- `runs/<NN-model>/samples*.csv`: 30 s samples of the model process (CPU, RSS, per-GPU memory,
  load, power; PCIe link for GLM; llama-server `/slots` counters for Nanbeige). The engine log tail
  is included for Maya and Strata.
- `tools/sample_maya.sh`, `tools/sample_ollama_slots.sh`, `tools/sample_attach_gpu_process.sh`:
  the read-only samplers (they only read `ps`, `/proc`, `nvidia-smi` and logs).
- `tools/headless_check.js`: the reviewer's browser check.

Maya engine numbers, such as card combinations, context size and RAM speed, are in
[`../engine-bench-maya/`](../engine-bench-maya/).
