#!/usr/bin/env python3
"""Builds RESOURCES.md: VRAM per GPU, process RAM, context, CPU/GPU load per model.

Sources: the 5-second resource samples taken during benchmark runs (<tag>[-runN]_resources.csv
from run_queue.sh / repeat_runs.sh, Strata and Bonsai CSVs) and the probes from probe_mem.sh
(resources/probe_<tag>.csv + .txt: same context, RssAnon/RssFile split, `ollama ps` CPU/GPU
split). Runs of one model are merged: VRAM and RAM are peaks; CPU and GPU load are medians over
the samples where the model was generating, taken from the benchmark runs when there are any.
"""
import csv
import glob
import os
import re
import statistics

BASE = os.path.dirname(os.path.abspath(__file__))
OLLAMA_CTX = 32768  # BENCH_NUM_CTX default in run_ollama_model.sh / repeat_runs.sh / probe_mem.sh
STRATA = "GPU + эксперты в RAM"

# Runs outside Ollama: csv -> (model, context, GPU index for single-GPU CSVs, where the weights are)
EXPLICIT = {
    "strata_iq3s_resources.csv": ("Strata IQ3_S (Qwen3.8-Flash-Next) — 5070 Ti", 65536, 1, STRATA),
    "strata_iq3s_resources_5090.csv": ("Strata IQ3_S (Qwen3.8-Flash-Next) — 5090", 65536, 0, STRATA),
    "strata_uncensored_resources_attempt1.csv": ("Strata Orca Uncensored IQ3_XXS — 5070 Ti", 524288, 1, STRATA),
    "strata_uncensored_resources_attempt2.csv": ("Strata Orca Uncensored IQ3_XXS — 5070 Ti", 524288, 1, STRATA),
    "ternary-bonsai-2-27b-pq2_0_resources.csv": ("Ternary Bonsai 2 27B — обе карты", 131072, None, "100% GPU"),
    "ternary-bonsai-2-27b-pq2_0-rtx5090_resources.csv": ("Ternary Bonsai 2 27B — 5090", 131072, None, "100% GPU"),
    "ternary-bonsai-2-27b-pq2_0-rtx5070ti-ctx64k_resources.csv": ("Ternary Bonsai 2 27B — 5070 Ti", 65536, None, "100% GPU"),
}
for size in ("9b", "4b", "2b"):
    for gpu, name in (("rtx5090", "5090"), ("rtx5070ti", "5070 Ti")):
        EXPLICIT[f"ternary-bonsai-2-{size}-pq2_0-{gpu}_resources.csv"] = (
            f"Ternary Bonsai 2 {size.upper()} — {name}", 131072, None, "100% GPU")


def num(r, *keys):
    for k in keys:
        if r.get(k) not in (None, ""):
            return float(r[k])
    return None


def load(path, single_gpu=None):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                cpu = num(r, "proc_cpu_pct", "strata_cpu_pct") or 0.0
                rss = num(r, "proc_rss_gb", "strata_rss_gb") or 0.0
                if "gpu0_mem_mib" in r and "gpu1_mem_mib" in r:
                    g = [(num(r, "gpu0_util"), num(r, "gpu0_mem_mib")),
                         (num(r, "gpu1_util"), num(r, "gpu1_mem_mib"))]
                else:
                    g = [(0.0, 0.0), (0.0, 0.0)]
                    g[single_gpu] = (num(r, "gpu_util", "gpu1_util", "gpu0_util"),
                                     num(r, "gpu_mem_mib", "gpu1_mem_mib", "gpu0_mem_mib"))
                if any(x is None for pair in g for x in pair):
                    continue
            except (TypeError, ValueError):
                continue
            rows.append({"cpu": cpu, "rss": rss, "anon": num(r, "rss_anon_gb"),
                         "file": num(r, "rss_file_gb"), "gpu": g})
    return rows


def split_of(txt):
    """The PROCESSOR column of the saved `ollama ps` line: '100% GPU' or '23%/77% CPU/GPU'."""
    m = re.search(r"(\d+%/\d+% CPU/GPU|100% GPU|100% CPU)", open(txt).read())
    return m.group(1) if m else "?"


groups = {}  # model -> {"ctx", "split", "bench": [rows], "probe": [rows], "runs"}
for path in sorted(glob.glob(os.path.join(BASE, "*_resources*.csv"))):
    name = os.path.basename(path)
    if name in EXPLICIT:
        model, ctx, gpu, split = EXPLICIT[name]
    elif name.startswith(("strata", "ternary-bonsai")):
        continue  # unknown layout: add it to EXPLICIT
    else:
        model, ctx, gpu, split = re.sub(r"(-run\d+)?_resources\.csv$", "", name), OLLAMA_CTX, None, None
    g = groups.setdefault(model, {"ctx": ctx, "split": split, "bench": [], "probe": [], "runs": 0})
    g["bench"] += load(path, gpu)
    g["runs"] += 1
# `ollama ps` saved by the benchmark runs, for models without a probe
for d in glob.glob(os.path.join(BASE, "*-benchmark", "runs", "*")):
    g = groups.get(os.path.basename(d).replace(":", "_"))
    ps = os.path.join(d, "ollama_ps_after.txt")
    if g is not None and g["split"] is None and os.path.exists(ps):
        g["split"] = split_of(ps)
for path in sorted(glob.glob(os.path.join(BASE, "resources", "probe_*.csv"))):
    model = os.path.basename(path)[len("probe_"):-len(".csv")]
    g = groups.setdefault(model, {"ctx": OLLAMA_CTX, "split": None, "bench": [], "probe": [], "runs": 0})
    g["probe"] += load(path)
    txt = path[:-4] + ".txt"
    if os.path.exists(txt):
        g["split"] = split_of(txt)


def active(rows):
    return [r for r in rows if r["cpu"] > 30 or r["gpu"][0][0] > 5 or r["gpu"][1][0] > 5]


def gib(mib):
    return f"{mib / 1024:.1f}" if mib > 200 else "—"


def verdict(split, cpu, util):
    in_ram = split == STRATA or "CPU" in (split or "")
    top = max([u for u in util if u is not None] or [0])
    if not in_ram:
        return "нет"
    if top < 50:
        return "**да** — карты простаивают, ждут CPU"
    return "частично — CPU считает свою часть, карты заняты"


table = []
for model, g in groups.items():
    rows = g["bench"] + g["probe"]
    if not rows:
        continue
    vram = [max(r["gpu"][i][1] for r in rows) for i in (0, 1)]
    load_rows = active(g["bench"]) or active(g["probe"]) or rows
    cpu = statistics.median(r["cpu"] for r in load_rows)
    util = [statistics.median(r["gpu"][i][0] for r in load_rows) if vram[i] > 200 else None for i in (0, 1)]
    anon = [r["anon"] for r in g["probe"] if r["anon"] is not None]
    if anon:
        ram = f"{max(anon):.1f}"
        cache = f"{max(r['file'] for r in g['probe'] if r['file'] is not None):.1f}"
    else:
        ram, cache = f"{max(r['rss'] for r in rows):.1f}*", "—"
    table.append((sum(vram) / 1024, model, g, vram, ram, cache, cpu, util))

out = [
    "# Ресурсы: видеопамять, RAM и загрузка CPU по моделям",
    "",
    "Сгенерировано `python3 resources.py`. Источники: замеры каждые 5 с во время прогонов",
    "(`*_resources.csv`) и пробы `probe_mem.sh` (`resources/probe_*`: модель одна на свободных",
    "картах, тот же контекст, генерация 3000 токенов, у Super и Mistral Medium 100).",
    "",
    "- **Контекст** — с каким окном модель запускалась в тестах (у Ollama‑моделей `num_ctx` 32K).",
    "- **VRAM** — пик занятой памяти карты: веса + KV‑кэш этого контекста + буферы CUDA.",
    "- **RAM своя** — RssAnon процесса: веса, скопированные в RAM, кэш и буферы. Её нужно",
    "  иметь свободной. `*` — для старых замеров известен только общий RSS.",
    "- **Кэш файла** — RssFile: страницы отображённого (mmap) файла GGUF. У моделей целиком на",
    "  GPU это остаток загрузки, ядро освободит его при нехватке памяти. У моделей с частью весов",
    "  на CPU (`X%/Y% CPU/GPU`) именно отсюда CPU читает свои веса, поэтому эту память нужно",
    "  держать свободной: примерно размер файла минус то, что легло в VRAM.",
    "- **Где веса** — колонка PROCESSOR из `ollama ps` (для Ollama) или устройство движка.",
    "- **CPU** — медиана загрузки процесса во время генерации, 100 % = одно ядро. **GPU** —",
    "  медиана загрузки каждой используемой карты.",
    "- **Ждёт CPU** — часть весов в RAM, и карты при этом загружены слабо: каждый токен",
    "  упирается в процессор и память.",
    "- CPU ~450 % у моделей целиком на GPU — это потоки llama.cpp в активном ожидании, а не",
    "  вычисления; у моделей с весами на CPU ~800 % — 8 потоков, которые реально считают.",
    "",
    "| Модель | Контекст | VRAM 5090, ГБ | VRAM 5070 Ti, ГБ | RAM своя, ГБ | Кэш файла, ГБ | Где веса | CPU | GPU 5090 / 5070 Ti | Ждёт CPU? |",
    "|---|---|---|---|---|---|---|---|---|---|",
]
for _, model, g, vram, ram, cache, cpu, util in sorted(table, key=lambda x: (x[0], x[1])):
    u = " / ".join(f"{x:.0f} %" if x is not None else "—" for x in util)
    runs = f" ({g['runs']} прогона)" if g["runs"] > 1 else ""
    out.append(f"| {model}{runs} | {g['ctx'] // 1024}K | {gib(vram[0])} | {gib(vram[1])} | {ram} | "
               f"{cache} | {g['split'] or '?'} | {cpu:.0f} % | {u} | {verdict(g['split'], cpu, util)} |")

with open(os.path.join(BASE, "RESOURCES.md"), "w") as f:
    f.write("\n".join(out) + "\n")
print("\n".join(out[-len(table) - 2:]))
