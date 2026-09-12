#!/bin/bash
# Usage: ./run_bench.sh <ollama-model-name>
set -uo pipefail

MODEL="$1"
BASE="$(cd "$(dirname "$0")" && pwd)"
OUT="$BASE/runs/$MODEL"
mkdir -p "$OUT"

echo "=== $MODEL ==="

docker exec ollama-test ollama ps > "$OUT/ollama_ps_before.txt" 2>&1

START_EPOCH=$(date +%s)

python3 - "$MODEL" "$BASE/puzzles.md" "$OUT/raw_response.json" <<'PYEOF'
import json, sys, time, urllib.request

model, prompt_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
prompt = open(prompt_path).read()

req = urllib.request.Request(
    "http://localhost:11436/api/generate",
    data=json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"num_predict": -1, "num_ctx": 32768},
    }).encode(),
    headers={"Content-Type": "application/json"},
)

partial_path = out_path.replace("raw_response.json", "partial_response.txt")
full_text = []
final = None
token_count = 0
last_report = time.time()
with urllib.request.urlopen(req, timeout=21600) as resp:
    for line in resp:
        line = line.decode().strip()
        if not line:
            continue
        chunk = json.loads(line)
        full_text.append(chunk.get("response", ""))
        token_count += 1
        if time.time() - last_report > 10:
            print(f"  ...{token_count} tokens so far", file=sys.stderr, flush=True)
            last_report = time.time()
            open(partial_path, "w").write("".join(full_text))
        if chunk.get("done"):
            final = chunk

final["response"] = "".join(full_text)
open(out_path, "w").write(json.dumps(final))
PYEOF

END_EPOCH=$(date +%s)
echo "wall_clock_seconds=$((END_EPOCH - START_EPOCH))" > "$OUT/wall_clock.txt"

docker exec ollama-test ollama ps > "$OUT/ollama_ps_after.txt" 2>&1

python3 - "$OUT/raw_response.json" "$OUT" <<'PYEOF'
import json, sys

raw_path, out_dir = sys.argv[1], sys.argv[2]
d = json.load(open(raw_path))

open(f"{out_dir}/response.md", "w").write(d.get("response", ""))

def ns_to_s(ns):
    return round(ns / 1e9, 3) if ns is not None else None

timing = {
    "total_duration_s": ns_to_s(d.get("total_duration")),
    "load_duration_s": ns_to_s(d.get("load_duration")),
    "prompt_eval_count": d.get("prompt_eval_count"),
    "prompt_eval_duration_s": ns_to_s(d.get("prompt_eval_duration")),
    "eval_count": d.get("eval_count"),
    "eval_duration_s": ns_to_s(d.get("eval_duration")),
}
if timing["eval_count"] and timing["eval_duration_s"]:
    timing["eval_tokens_per_s"] = round(timing["eval_count"] / timing["eval_duration_s"], 2)

json.dump(timing, open(f"{out_dir}/timing.json", "w"), indent=2)
print(json.dumps(timing, indent=2))
PYEOF

echo "--- wall clock ---"
cat "$OUT/wall_clock.txt"
echo "--- grading ---"
python3 "$BASE/grade.py" "$OUT/response.md" | tee "$OUT/grade_result.txt"
