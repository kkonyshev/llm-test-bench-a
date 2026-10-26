# Maya engine: card combinations, context size and RAM speed

[Project Maya](https://huggingface.co/peasantsmith) runs two large MoE models with its own engines.
It keeps the most-routed experts in VRAM, the next ones in RAM and the rest on NVMe:
- **DeepSeek-V4.1-Flash-1017** (748B, Maya-S quant, ~175 GB) with `build/maya-ds4`;
- **GLM-5.3-Flash** (321B, ~18B active; Maya-M IQ2_S quant, 116 GB) with `build/maya`.

These numbers come from Maya's built-in benchmark, `./maya.sh --bench`. It decodes 3 answers of
256 tokens with greedy sampling and thinking off, then reads a 2,048-token and an 8,192-token prompt.
The benchmark writes `maya-bench.txt`. [`watch_bench.sh`](watch_bench.sh) copied each new result
to `raw/<time>__<label>.txt`. The GPU set is the `"gpu"` field of the model's JSON config, and the
`setup:` line in each file shows the set actually used.

Host: Machine 3 ([`../HARDWARE.md`](../HARDWARE.md)), 9800X3D, 4 × 32 GB DDR5,
RTX 5090 (GPU 0) and RTX 5070 Ti (GPU 1). Maya v1.1.28 unless noted; v1.1.28 added a fast decode
path for one GPU (DeepSeek only, Linux + NVIDIA + one GPU).

## DeepSeek-V4.1-Flash

| Maya | GPUs | Context | RAM | Decode tok/s | Prefill 2K / 8K tok/s | Note |
|---|---|---|---|---|---|---|
| v1.1.26 | 5090 | 262K | 3600 MT/s | 15.4 | 200 / 672 | old engine |
| v1.1.28 | 5090 | 1M | 3600 | 16.9 cold / 18.5 warm | 194 / 660 | one-GPU path |
| v1.1.28 | 5090 + 5070 Ti | 1M | 3600 | 17.3 | 208 / 631 | two-GPU path |
| v1.1.28 | 5070 Ti alone | 1M | 3600 | 9.8 | 19 / 22 | page cache had been evicted by Ollama |
| v1.1.28 | 5090 | 1M | **6400** | 19.1 cold / **20.7** warm | 249–266 / 807–853 | after the EXPO change |
| v1.1.28 | 5090 + 5070 Ti | 1M | 6400 | 19.1 cold / 18.7 warm | 167–174 / 527–535 | |
| v1.1.28 | 5090 | 512K | 6400 | 19.4 | 261 / 836 | |
| v1.1.28 | 5090 | 256K | 6400 | **21.7** | 275 / 871 | |
| v1.1.28 | 5090 | 128K | 6400 | 21.1 | 275 / 857 | |

- **One 5090 now beats 5090 + 5070 Ti.** With v1.1.28 decode is +11% and prefill +60% on the 5090
  alone. With the older engine (PRISM RUNNER run 2) the second card had given +25–30%.
- **RAM 3600 → 6400 MT/s** gave decode +12% and prefill +30–36%.
- **Context size costs little.** From 128K to 1M decode changes by ≤5%. The KV cache is
  0.12–0.97 GB, because DeepSeek stores it in FP4. Keeping 1M costs little.
- Maya's setup menu offers DeepSeek only 32K–256K. A larger `--max-context` in `maya-ds4.json` works.
- `--calibrate` and `--speed-calibration` (DSpark) were not re-run for DeepSeek after the RAM change.

## GLM-5.3-Flash, Maya-M

| GPUs | Context | Decode tok/s | Prefill 2K / 8K tok/s | `--calibrate` result |
|---|---|---|---|---|
| 5090 | 128K | 31.7 cold / 31.9 warm | 660 / 2,149 | 30.8, default settings best |
| 5090 + 5070 Ti | 128K | 40.3 cold / 39.7 warm | 469–472 / 1,097–1,101 | 40.0, default settings best |
| 5090 + 5070 Ti | 512K | 39.9 / 40.4 | 464 / 1,072–1,077 | — |

All runs at RAM 6400 MT/s. The drafter was DFlash2, with acceptance of 88–99% in use (licence
CC BY-NC-ND).

- **The second card helps GLM's decode (+25%) but hurts prefill (−29% at 2K, −49% at 8K).**
- **GLM vs DeepSeek on the 5090:** decode ×1.5, prefill ×2.5.
- **Context:** 512K costs nothing measurable. The KV cache is 0.81 + 0.55 GB. Maya's menu caps GLM
  at 128K, but `--max-context` in `maya-maya-m.json` is passed through unchecked.

### Why prefill drops with two cards: PCIe

`nvidia-smi` under load shows the **5090 at PCIe 5.0 x8 and the 5070 Ti at PCIe 3.0 x8**. GLM's
prefill streams experts from RAM to each card. Maya's prefill log for the 2,047-token prompt (raw
file `2026-10-25_2344__glmM_512K_ram6400.txt`):

| Card | Copy lane | Moved over PCIe | Wall time |
|---|---|---|---|
| 5090 | **26.6 GB/s** | 37.4 GB | 1,686 ms |
| 5070 Ti | **6.7 GB/s** | 13.1 GB, plus 1,383 experts computed on the CPU | 2,444 ms |

The 5070 Ti's link is ~4× slower, and the whole prefill waits for it. A slot running at PCIe 4.0
x16 would remove most of the penalty; the planned Lenovo P620 has that.

## How decode scales: notes for other hardware

- Decode here is mostly latency- and overhead-bound, not bandwidth-bound. In DeepSeek's log 12% of
  experts held in VRAM served ~87% of expert picks. The remaining picks go to the CPU, and those
  set the speed.
- Moving the whole model into VRAM is the big step, worth 2–3×. Faster cards beyond that give
  sublinear gains. In Maya's community table, RTX PRO 6000 vs A6000 is 2.3× the bandwidth for 1.33×
  the speed.
- Estimates for a Lenovo P620 (3995WX, 8-channel DDR4-3200, 256 GB, PCIe 4.0 x16) are in
  [`../HARDWARE.md`](../HARDWARE.md#machine-4-planned-lenovo-p620).

## Gotchas met while benchmarking

- **Another model in Ollama next to Maya ruins the numbers.** Nemotron in Ollama raised the load to
  ~20 and evicted Maya's page cache, so experts came from NVMe and prefill stalled. Unload other
  models first.
- **The first run after a restart is "cold".** Experts are not yet in the page cache, so take the
  second run.
- **After `git pull`, run `./maya.sh --setup`.** It rebuilds when the source hash differs from
  `build/MAYA-BUILD.json`; a plain start skips the rebuild. `--rebuild` forces it.
