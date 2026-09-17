import json, os, re

models = [
    ("qwen3-coder:30b-a3b-q4_K_M", "qwen3-coder-30b-a3b"),
    ("glm-4.7-flash:q4_K_M", "glm-4.7-flash"),
    ("qwen3.8:27b-q4_K_M", "qwen3.8-27b"),
    ("qwen2.5-coder:7b-instruct-q4_K_M", "qwen2.5-coder-7b-test"),
    ("deepseek-coder-v2:16b-lite-instruct-q4_K_M", "deepseek-coder-v2-lite"),
    ("gemma4:26b-a4b-it-q4_K_M", "gemma4-26b"),
    ("llama3.1:70b", "llama3.1:70b"),
    ("llama3.3:70b", "llama3.3:70b"),
    ("qwen2.5:72b", "qwen2.5:72b"),
    ("nemotron:70b", "nemotron:70b"),
    ("deepseek-coder-v2:236b-instruct-q4_K_M", "deepseek-coder-v2-full-bench"),
]

header = ["model", "cod_pass", "cod_toks", "cod_time", "gpu_split", "rsn_pass", "rsn_toks", "rsn_time"]
print(" | ".join(h.ljust(12) for h in header))

for tag, label in models:
    cdir = f"coding-benchmark/runs/{tag}"
    rdir = f"reasoning-benchmark/runs/{tag}"

    cpass = "?"
    pr = f"{cdir}/pytest_result.txt"
    if os.path.exists(pr):
        txt = open(pr).read()
        m = re.search(r"(\d+) failed, (\d+) passed", txt)
        m2 = re.search(r"(?<!\d )(\d+) passed(?! .*failed)", txt)
        m3 = re.search(r"(\d+) errors", txt)
        if m:
            f, p = int(m.group(1)), int(m.group(2))
            cpass = f"{p}/{p+f}"
        elif m2 and "passed" in txt:
            p = int(m2.group(1))
            total = p
            cpass = f"{p}/{max(p,23)}"
        elif m3:
            cpass = f"0/23"

    ctiming = {}
    if os.path.exists(f"{cdir}/timing.json"):
        ctiming = json.load(open(f"{cdir}/timing.json"))
    ctoks = ctiming.get("eval_tokens_per_s", "?")
    cwall = "?"
    if os.path.exists(f"{cdir}/wall_clock.txt"):
        m = re.search(r"wall_clock_seconds=(\d+)", open(f"{cdir}/wall_clock.txt").read())
        if m: cwall = m.group(1) + "s"

    gpu_split = "?"
    if os.path.exists(f"{cdir}/ollama_ps_after.txt"):
        txt = open(f"{cdir}/ollama_ps_after.txt").read()
        m = re.search(r"(\d+%/\d+% \S+/\S+|\d+% \S+)", txt)
        if m: gpu_split = m.group(1)

    rpass = "?"
    gr = f"{rdir}/grade_result.txt"
    if os.path.exists(gr):
        txt = open(gr).read()
        m = re.search(r"(\d+)/12 correct", txt)
        if m: rpass = m.group(0)

    rtiming = {}
    if os.path.exists(f"{rdir}/timing.json"):
        rtiming = json.load(open(f"{rdir}/timing.json"))
    rtoks = rtiming.get("eval_tokens_per_s", "?")
    rwall = "?"
    if os.path.exists(f"{rdir}/wall_clock.txt"):
        m = re.search(r"wall_clock_seconds=(\d+)", open(f"{rdir}/wall_clock.txt").read())
        if m: rwall = m.group(1) + "s"

    row = [tag, cpass, str(ctoks), cwall, gpu_split, rpass, str(rtoks), rwall]
    print(" | ".join(v.ljust(12) for v in row))
