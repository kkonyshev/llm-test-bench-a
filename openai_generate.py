"""Run one benchmark prompt against an OpenAI-compatible /v1/chat/completions server.

Writes raw_response.json in the same shape run_bench.sh gets from Ollama's
/api/generate (response, prompt_eval_count, eval_count, *_duration in ns), so
the rest of the benchmark (extraction, pytest, grading) is unchanged.

Usage: openai_generate.py <base-url> <model> <prompt-file> <raw_response.json>
Env: BENCH_MAX_TOKENS (default 100000), BENCH_API_KEY (optional).
The model's separate reasoning (reasoning_content) is not part of the answer,
like a <think> block; it is kept in raw_response.json as "reasoning".
"""
import json
import os
import sys
import time
import urllib.request

base, model, prompt_path, out_path = sys.argv[1:5]
prompt = open(prompt_path).read()
headers = {"Content-Type": "application/json"}
if os.environ.get("BENCH_API_KEY"):
    headers["Authorization"] = "Bearer " + os.environ["BENCH_API_KEY"]

req = urllib.request.Request(
    base.rstrip("/") + "/v1/chat/completions",
    data=json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": int(os.environ.get("BENCH_MAX_TOKENS", "100000")),
    }).encode(),
    headers=headers,
)

partial_path = out_path.replace("raw_response.json", "partial_response.txt")
answer, reasoning = [], []
usage, timings, finish = {}, {}, None
chunks = 0
start = time.time()
first = None
last_report = start
with urllib.request.urlopen(req, timeout=21600) as resp:
    for raw in resp:
        line = raw.decode().strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        chunk = json.loads(data)
        usage = chunk.get("usage") or usage
        timings = chunk.get("timings") or timings
        for choice in chunk.get("choices", []):
            delta = choice.get("delta", {})
            if delta.get("content") or delta.get("reasoning_content"):
                first = first or time.time()
                chunks += 1
            answer.append(delta.get("content") or "")
            reasoning.append(delta.get("reasoning_content") or "")
            finish = choice.get("finish_reason") or finish
        if time.time() - last_report > 10:
            print(f"  ...{chunks} tokens so far", file=sys.stderr, flush=True)
            last_report = time.time()
            open(partial_path, "w").write("".join(reasoning) + "\n\n=== answer ===\n" + "".join(answer))
end = time.time()

ms = lambda v: int(v * 1e6) if v is not None else None  # noqa: E731  (ms -> ns)
gen_tokens = usage.get("completion_tokens") or timings.get("predicted_n") or chunks
gen_ns = ms(timings.get("predicted_ms")) or int((end - (first or start)) * 1e9)
prompt_ns = ms(timings.get("prompt_ms")) or int(((first or end) - start) * 1e9)
out = {
    "model": model,
    "response": "".join(answer),
    "reasoning": "".join(reasoning),
    "done_reason": finish,
    "total_duration": int((end - start) * 1e9),
    "load_duration": 0,
    "prompt_eval_count": usage.get("prompt_tokens") or timings.get("prompt_n"),
    "prompt_eval_duration": prompt_ns,
    "eval_count": gen_tokens,
    "eval_duration": gen_ns,
    "usage": usage,
    "timings": timings,
}
open(out_path, "w").write(json.dumps(out))
print(f"finish_reason={finish} completion_tokens={gen_tokens}", file=sys.stderr)
