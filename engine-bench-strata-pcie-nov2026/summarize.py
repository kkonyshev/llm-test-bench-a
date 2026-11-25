#!/usr/bin/env python3
"""Summarise the 2026-11-25 Strata runs: speed per run label (data/*/results.csv) and resources (data/*/mon*.csv)."""
import csv, glob, os, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
KINDS = ["prefill2048", "prefill8192", "prefill32768", "prefill131072"]


def speed():
    print("| run | model | decode 3x256 | decode 1024 | " + " | ".join(k.replace("prefill", "prompt ") for k in KINDS) + " |")
    print("|---|---|---|---|" + "---|" * len(KINDS))
    for path in sorted(glob.glob(os.path.join(HERE, "data", "*", "results.csv"))):
        runs = {}
        for r in csv.DictReader(open(path)):
            runs.setdefault(r["label"], []).append(r)
        for label, rows in runs.items():
            by = {}
            for r in rows:
                if r["tok_s"] not in ("", "None"):  # a failed request (crashed engine) is recorded as None
                    by.setdefault(r["kind"], []).append(float(r["tok_s"]))
            dec = by.get("decode")
            cells = [f"{statistics.mean(dec):.1f}" if dec else "—", f"{by['decode1k'][0]:.1f}" if "decode1k" in by else "—"]
            cells += [f"{by[k][0]:.0f}" if k in by else "—" for k in KINDS]
            print(f"| {label} | {rows[0]['model']} | " + " | ".join(cells) + " |")


def resources():
    cols = ["tctl", "tccd1", "tccd_max", "fan2", "ram_used_gb", "load1", "gpu_temp", "gpu_w", "gpu_mem"]
    print("\n| monitor file | samples | " + " | ".join(f"{c} avg/max" for c in cols) + " |")
    print("|---|---|" + "---|" * len(cols))
    for path in sorted(glob.glob(os.path.join(HERE, "data", "*", "mon*.csv"))):
        rows = list(csv.DictReader(open(path)))
        cells = []
        for c in cols:
            v = []
            for r in rows:
                try:
                    v.append(float(r[c]))
                except (KeyError, TypeError, ValueError):
                    pass
            cells.append(f"{statistics.mean(v):.0f}/{max(v):.0f}" if v else "—")
        print(f"| {os.path.relpath(path, HERE)} | {len(rows)} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    speed()
    resources()
