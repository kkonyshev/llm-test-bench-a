# Maya engine: card combinations, context size, RAM speed and PCIe

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

## Memory and PCIe states that were measured

The board splits its two CPU slots x8/x8 when both are used. Four states were benchmarked:

| Label | Dates | RAM | 5090 link | 5070 Ti link | Maya's RAM read test |
|---|---|---|---|---|---|
| **3600** | until 2026-10-25 22:04 | 3600 MT/s, no EXPO | Gen5 x8 | Gen5 (`gen.max 5` on 10-22) | not logged |
| **6400 auto** | 10-25 22:04 → 10-26 13:19 | EXPO I 6400, CL40 | Gen5 x8 | **Gen3 x8** (6.7 GB/s) | 62–64 GB/s |
| **6000** | 10-26 13:25 → 14:20 | 6000 set by hand, EXPO timings lost | Gen5 x8 | Gen5 x8 | 51 GB/s |
| **6400 + Gen5** | from 10-26 14:23 | EXPO I 6400, slot speed **Gen5 set by hand** | Gen5 x8 | **Gen5 x8** (26.5 GB/s) | 54 GB/s (one sample) |

- **Gen3 was a side effect of EXPO with the slot speed on Auto**, not a slot limit. On Auto the
  5070 Ti trained at Gen3 after enabling EXPO; at 6000 it trained at Gen5; at 6400 with the slot
  speed forced to Gen5 it holds Gen5 with zero AER errors after ~20 benchmark runs. Idle power is
  unchanged: both links still drop to Gen1 at idle (12.9 W and 13.1 W per card).
- "Maya's RAM read test" is the `the host reads RAM at N GB/s` line Maya prints at start-up (GLM).
  It is a quick probe and varies by ~10% between starts.
- The **6000** state was slower than 6400 by far more than the 6% clock difference: the CPU took
  ~49% longer per expert. Setting 6000 by hand dropped the EXPO timings (and possibly UCLK=MEMCLK
  or FCLK). Those runs show what loose memory settings cost, not what 6000 MT/s costs.

## DeepSeek-V4.1-Flash

| Maya | GPUs | Context | RAM / 5070 Ti link | Decode tok/s | Prefill 2K / 8K | Experts in VRAM | Bound by |
|---|---|---|---|---|---|---|---|
| v1.1.26 | 5090 | 262K | 3600 | 15.4 | 200 / 672 | — | old engine; CPU experts at 3600 |
| v1.1.28 | 5090 | 1M | 3600 | 16.9 cold / 18.5 warm | 194 / 660 | — | CPU experts, RAM 3600 |
| v1.1.28 | 5090 + 5070 Ti | 1M | 3600 / Gen5 | 17.3 | 208 / 631 | — | CPU experts, RAM 3600 |
| v1.1.28 | 5070 Ti alone | 1M | 3600 | 9.8 | 19 / 22 | 321 | NVMe: Ollama had evicted the page cache |
| v1.1.28 | 5090 | 1M | 6400 auto | 19.1 cold / **20.7** warm | 249–266 / 807–853 | 681 | CPU experts |
| v1.1.28 | 5090 + 5070 Ti | 1M | 6400 auto / **Gen3** | 19.1 cold / 18.7 warm | 167–174 / 527–535 | 2,050 + 717 | prefill: 5070 Ti PCIe Gen3 |
| v1.1.28 | 5090 | 512K | 6400 auto | 19.4 | 261 / 836 | 736 | CPU experts |
| v1.1.28 | 5090 | 256K | 6400 auto | **21.7** | 275 / 871 | 763 | CPU experts |
| v1.1.28 | 5090 | 128K | 6400 auto | 21.1 | 275 / 857 | 774 | CPU experts |
| v1.1.28 | 5090 | 128K | 6400 + Gen5 | 18.6 cold / **21.5** warm | 270–272 / 862–871 | 776 | CPU experts |
| v1.1.28 | 5090 | 1M | 6400 + Gen5 | 20.4 | 265 / 849 | 684 | CPU experts |
| v1.1.28 | 5090 + 5070 Ti | 1M | 6400 + Gen5 | 19.7 / 19.0 | **282–294** / 768–794 | 2,052 + 717 | CPU experts; the HTML prompt drops to 16–17 tok/s |

"Experts in VRAM" is out of 15,360 routed experts (Maya's start-up line). With one GPU the fast
path streams experts in place instead of keeping more of them resident.

- **One 5090 is still the best setting for DeepSeek, but only by 5–7% now.** With the 5070 Ti at
  Gen5, two cards reach 19.0–19.7 tok/s against 20.4–20.7 on the 5090 alone (both at 1M). Two of
  the three test prompts run at 20.5–21.6 on two cards; the HTML prompt stays at 16–17.
- **Gen5 on the 5070 Ti fixed two-card prefill:** 167–174 → 282–294 at 2K (+70%) and
  527–535 → 768–794 at 8K (+48%). At 2K two cards now beat one; at 8K one card is still ~7% faster.
- **RAM 3600 → 6400 MT/s** gave decode +12% and prefill +30–36% (one 5090).
- **Context size costs little.** From 128K to 1M decode changes by ≤5%. The KV cache is
  0.12–0.97 GB, because DeepSeek stores it in FP4.
- Maya's setup menu offers DeepSeek only 32K–256K. A larger `--max-context` in `maya-ds4.json` works.
- `--calibrate` and `--speed-calibration` (DSpark) were not re-run for DeepSeek.

## GLM-5.3-Flash, Maya-M

All with the DFlash2 drafter (acceptance 82–99%; licence CC BY-NC-ND). "Token" and "CPU lane"
are the averages of Maya's per-answer `glm stat` lines: total time per token, and the part spent
computing RAM-resident experts on the CPU.

| GPUs | Context | RAM / 5070 Ti link | Decode tok/s | Prefill 2K / 8K | Token / CPU lane, ms | VRAM hit | Bound by |
|---|---|---|---|---|---|---|---|
| 5090 + 5070 Ti | 128K | 6400 auto / Gen3 | 40.3 / 39.7 | 469–472 / 1,097–1,101 | 24.5 / 21.0 | 76% | prefill: 5070 Ti PCIe Gen3 (6.7 GB/s); decode: CPU lane |
| 5090 + 5070 Ti | 512K | 6400 auto / Gen3 | 39.9 / 40.4 | 464 / 1,072–1,077 | 24.8 / 21.1 | 76% | same |
| 5090 + 5070 Ti | 512K | 6000 / Gen5 | 35.9 / 34.9 / 34.9 | 656–661 / 1,495–1,502 | 27.9 / 14.5–19.1 | 79% | decode: slow CPU experts (loose RAM settings) |
| 5090 + 5070 Ti | 512K | 6000, `MAYA_GLM_CPU_LANE=2` | 33.1 / 34.0 | 661 / 1,499–1,501 | 29.2 / 11.4–15.9 | 79% | 2 CPU threads per card: an expert takes 0.53–0.65 ms |
| **5090 + 5070 Ti** | **128K** | **6400 + Gen5** | **45.9 / 45.0** | **676–679 / 1,547–1,550** | **22.0** / 10.4–13.4 | 79% | decode: CPU lane; prefill: layer split runs the cards in turn |
| **5090 + 5070 Ti** | **512K** | **6400 + Gen5** | **44.7** | 666 / 1,501 | 22.1 / 10.4 | 80% | same |
| 5090 | 128K | 6400 auto | 31.7 cold / 31.9 warm | 660 / 2,148–2,149 | 30.1 / 18.1 | 65% | decode: VRAM size + CPU lane; prefill: 5090 PCIe x8 copies (25 GB/s) |
| 5090 | 128K | 6000 | 25.1 / 25.1 | 653 / 2,128 | 37.6 / 26.5 | 65% | decode: slow CPU experts (same routing as 6400, +46% CPU time) |
| 5090 | 512K | 6000 | 24.8 cold | 652 / 2,091 | 38.0 / 26.9 | 65% | same |
| 5090 | 512K | 6000, `MAYA_GLM_CPU_LANE=2` | 22.8 / 22.8 | 649 / 2,076–2,078 | 41.4 / 21.2 | 67% | 2 CPU threads instead of 8 |
| 5070 Ti alone | 512K | 6000 | 15.4 / 15.4 | 202 / 220 | 61.7 / 45.1 | 39% | VRAM size (741 expert slots); CPU lane 45 ms/token |

`--calibrate` results:

| Run | Result |
|---|---|
| 5090, 6400 auto | 30.8 tok/s, default settings best |
| 5090 + 5070 Ti, 6400 auto | 40.0 tok/s, default settings best |
| 5090 + 5070 Ti, 6000 | wrote `"env": {"MAYA_GLM_CPU_LANE": "2"}` into `maya-maya-m.json`. The benchmark then ran **3–8% slower** (table above); remove it |
| 5070 Ti alone, 6000 | default settings best (and removed the `env` entry) |

What the GLM runs show:
- **The best setting is 6400 EXPO with the second slot forced to Gen5:** 45–46 tok/s decode
  (+12–14% over 6400 auto) and +44% prefill. Decode gained because the CPU lane got cheaper: with
  the 5070 Ti at Gen3, Maya timed a PCIe expert copy at 1.19 ms and sent 6–7 of 8 RAM-tier experts
  to the CPU; at Gen5 a copy takes 0.30 ms and the work is split between CPU and PCIe.
- **The second card is worth it for GLM:** 45 vs 32 tok/s on the 5090 alone (+41%), and 15 on
  the 5070 Ti alone. At 8K prefill one 5090 is still faster (2,149 vs 1,550), because the layer
  split runs the two cards one after the other (CUDA0 2.7 s, then CUDA1 2.4 s).
- **Memory settings matter more than the clock.** At 6000 with lost EXPO timings the routing was
  identical to 6400 (same VRAM hits, same 69/87/72 experts per token on the CPU), yet the CPU lane
  took 16–21 → 24–30 ms per token, and decode dropped 21% on one card and 14% on two.
- **Context:** 512K costs 1–3% against 128K on two cards. The KV cache is 0.81 + 0.55 GB. Maya's
  menu caps GLM at 128K, but `--max-context` in `maya-maya-m.json` is passed through unchecked.

### Why two-card prefill was slow before: PCIe

With RAM at 6400 auto, Maya's prefill log for the 2,047-token prompt (raw file
`2026-10-25_2344__glmM_512K_ram6400.txt`):

| Card | Copy lane | Moved over PCIe | Wall time |
|---|---|---|---|
| 5090 (Gen5 x8) | **26.6 GB/s** | 37.4 GB | 1,686 ms |
| 5070 Ti (Gen3 x8) | **6.7 GB/s** | 13.1 GB, plus 1,383 experts computed on the CPU | 2,444 ms |

With the 5070 Ti at Gen5 (`2026-10-26_1425__glmM_gpu01_128K_ram6400gen5_run1.txt`) both cards copy
at 26.5–26.8 GB/s, and the 5070 Ti finishes its share in 1,203 ms.

## How decode scales: notes for other hardware

- Decode here is mostly latency- and CPU-bound, not bandwidth-bound. In DeepSeek's log 12% of
  experts held in VRAM served ~87% of expert picks. The remaining picks go to the CPU, and those
  set the speed. For GLM on two cards the CPU lane is 10–21 ms of a 22–28 ms token.
- Moving the whole model into VRAM is the big step, worth 2–3×. Faster cards beyond that give
  sublinear gains. In Maya's community table, RTX PRO 6000 vs A6000 is 2.3× the bandwidth for 1.33×
  the speed.
- On one card the 5090's x8 link limits prefill: ~96% of GLM's 2K prefill is the copy lane at
  25 GB/s. A x16 slot (only one card in the board, or a Lenovo P620) should lift that toward the RAM
  read limit (~51–64 GB/s here). Not measured yet.
- Estimates for a Lenovo P620 (3995WX, 8-channel DDR4-3200, 256 GB, PCIe 4.0 x16) are in
  [`../HARDWARE.md`](../HARDWARE.md#machine-4-planned-lenovo-p620).

## Gotchas met while benchmarking

- **EXPO can silently drop a slot to Gen3.** Check `nvidia-smi --query-gpu=pcie.link.gen.max
  --format=csv` after any BIOS memory change; force the slot speed if it fell.
- **Setting the RAM clock by hand can drop the EXPO timings.** Keep EXPO on and change only the
  frequency, or re-check timings, UCLK=MEMCLK and FCLK.
- **`--calibrate` can pick a worse setting.** Benchmark after it and compare.
- **Another model in Ollama next to Maya ruins the numbers.** Nemotron in Ollama raised the load to
  ~20 and evicted Maya's page cache, so experts came from NVMe and prefill stalled. Unload other
  models first.
- **The first run after a restart is "cold".** Experts are not yet in the page cache, so take the
  second run.
- **After `git pull`, run `./maya.sh --setup`.** It rebuilds when the source hash differs from
  `build/MAYA-BUILD.json`; a plain start skips the rebuild. `--rebuild` forces it.
