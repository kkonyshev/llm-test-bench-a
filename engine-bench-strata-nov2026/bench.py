#!/usr/bin/env python3
"""Same-workload speed check for an OpenAI-compatible DeepSeek server (Maya or Strata).
Usage: KEY=... python3 bench.py <label> <base_url>   e.g.  strata-gpu0 http://127.0.0.1:8081
Decode: 3 prompts x 256 tokens, greedy, thinking off. Prefill: fresh ~2K / 8K / 32K-token prompts (random nonce first,
nothing reused), 16 tokens out; prefill speed = prompt tokens / time to first token. Appends to results.csv next to it."""
import json, os, random, sys, time, urllib.error, urllib.request

label, base = sys.argv[1], sys.argv[2].rstrip("/")
key = os.environ.get("KEY", "")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.csv")

def model_id():
    r = urllib.request.Request(base + "/v1/models", headers={"Authorization": "Bearer " + key})
    return json.load(urllib.request.urlopen(r, timeout=30))["data"][0]["id"]

def run(model, prompt, max_tokens):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "temperature": 0, "stream": True, "stream_options": {"include_usage": True},
            "reasoning_effort": "none", "chat_template_kwargs": {"enable_thinking": False}}
    r = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time(); first = None; usage = {}; n = 0
    with urllib.request.urlopen(r, timeout=3600) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            d = json.loads(line[5:])
            if d.get("usage"):
                usage = d["usage"]
            for ch in d.get("choices") or []:
                delta = ch.get("delta") or {}
                if delta.get("content") or delta.get("reasoning_content"):
                    if first is None:
                        first = time.time()
                    n += 1
    t1 = time.time()
    first = first or t1
    return usage.get("prompt_tokens"), usage.get("completion_tokens") or n, first - t0, t1 - first

def filler(tokens):
    words = "the quick brown fox jumps over a lazy dog while seven sailors read old maps near the harbour".split()
    rnd = random.Random(tokens)
    return " ".join(rnd.choice(words) for _ in range(int(tokens * 0.95)))

model = model_id()
rows = []
for p in ["Write a Python function that parses a CSV file into a list of dictionaries, with type hints and a docstring.",
          "Explain how photosynthesis works, step by step, for a high-school student.",
          "Write a complete HTML page with a canvas that draws a bouncing ball animation in JavaScript."]:
    pt, ct, ttft, gen = run(model, p, 256)
    rows.append(("decode", pt, ct, round(ttft, 2), round(ct / gen, 1) if gen > 0 else None))
    print(rows[-1], flush=True)
for size in (2048, 8192, 32768):
    nonce = "%08x" % random.getrandbits(32)
    try:
        pt, ct, ttft, gen = run(model, "[%s] Summarise this text in one sentence:\n%s" % (nonce, filler(size)), 16)
    except urllib.error.HTTPError as e:
        print("prefill%d: HTTP %s %s" % (size, e.code, e.read()[:300].decode("utf-8", "ignore")), flush=True)
        continue
    rows.append(("prefill%d" % size, pt, ct, round(ttft, 2), round(pt / ttft, 0) if pt and ttft else None))
    print(rows[-1], flush=True)
new = not os.path.exists(out)
with open(out, "a") as f:
    if new:
        f.write("time,label,model,kind,prompt_tokens,completion_tokens,ttft_s,tok_s\n")
    for k, pt, ct, ttft, v in rows:
        f.write("%s,%s,%s,%s,%s,%s,%s,%s\n" % (time.strftime("%F %T"), label, model, k, pt, ct, ttft, v))
dec = [r[4] for r in rows if r[0] == "decode" and r[4]]
print("%s: decode mean %.1f tok/s; prefill %s" % (label, sum(dec) / len(dec), ", ".join("%s=%s" % (r[0][7:], r[4]) for r in rows if r[0].startswith("prefill"))))
