#!/usr/bin/env python3
"""Reasoning check for an OpenAI-compatible server: the yacht puzzle (unique solution, verified by brute force).
Usage: KEY=... python3 reason.py <label> <base_url> [effort]   effort: high (default) / medium / max
Thinking on, up to 32K output tokens. Scores the final answer automatically (10 points) and appends to reason.csv;
the full reply (thinking + answer) is saved as reason-<label>-<time>.txt next to the script."""
import json, os, re, sys, time, urllib.request

label, base = sys.argv[1], sys.argv[2].rstrip("/")
effort = sys.argv[3] if len(sys.argv) > 3 else "high"
key = os.environ.get("KEY", "")
here = os.path.dirname(os.path.abspath(__file__))

PUZZLE = """Пять яхтсменов (Анна, Брам, Кор, Дирк и Эва) выходят из гавани в 8, 9, 10, 11 и 12 часов, каждый в своё время. У каждого лодка своей длины (6, 7, 8, 9 или 10 м) и своего цвета (красный, синий, зелёный, белый или жёлтый). Известно:
1. Лодка Анны длиннее лодки Брама, но короче зелёной лодки.
2. Красная лодка ровно на 2 м длиннее синей.
3. Лодка Эвы не самая короткая и не самая длинная, и она не белая.
4. Лодки выходят почти строго от самой длинной к самой короткой: если взять любые две лодки, то более длинная выходит раньше, кроме ровно одной пары, где более короткая выходит раньше более длинной.
5. Жёлтая лодка выходит ровно через час после Кора.
6. Дирк выходит до полудня, и длина его лодки нечётная.
7. Сумма часов отправления красной и зелёной лодок равна длине белой лодки плюс 12.
8. Брам выходит не первым.
9. Длина лодки Анны чётная.
10. Жёлтая лодка длиннее лодки Анны.

Вопросы:
а) Определи длину, цвет и время отправления лодки каждого.
б) Докажи, что решение единственное.
в) Сколько решений было бы без условий 9 и 10? А только без условия 9?

Рассуждай по шагам и проверь итоговый ответ по каждому условию. В самом конце выведи строки строго в формате:
ИТОГ: Имя; длина; цвет; час
(по одной строке на каждого из пяти) и строку
ИТОГ-В: <число без условий 9 и 10>; <число без условия 9>"""

TRUTH = {"анна": (8, "красн", 11), "брам": (6, "син", 12), "кор": (10, "зел", 8), "дирк": (7, "бел", 10), "эва": (9, "жёлт", 9)}

def model_id():
    r = urllib.request.Request(base + "/v1/models", headers={"Authorization": "Bearer " + key})
    return json.load(urllib.request.urlopen(r, timeout=30))["data"][0]["id"]

model = model_id()
body = {"model": model, "messages": [{"role": "user", "content": PUZZLE}], "max_tokens": 32768, "temperature": 0.6,
        "stream": True, "stream_options": {"include_usage": True}, "reasoning_effort": effort}
req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
t0 = time.time(); first = None; think, answer, usage = [], [], {}
with urllib.request.urlopen(req, timeout=7200) as resp:
    for raw in resp:
        line = raw.decode("utf-8", "ignore").strip()
        if not line.startswith("data:") or line == "data: [DONE]":
            continue
        d = json.loads(line[5:])
        if d.get("usage"):
            usage = d["usage"]
        for ch in d.get("choices") or []:
            delta = ch.get("delta") or {}
            r_part = delta.get("reasoning_content") or delta.get("reasoning") or ""
            c_part = delta.get("content") or ""
            if (r_part or c_part) and first is None:
                first = time.time()
            think.append(r_part); answer.append(c_part)
t1 = time.time()
text = "".join(answer)

score, notes = 0, []
rows = {}
for m in re.finditer(r"ИТОГ:\s*([А-Яа-яЁё]+)\s*;\s*(\d+)[^;]*;\s*([А-Яа-яЁё]+)[^;]*;\s*(\d+)", text):
    rows[m.group(1).lower()] = (int(m.group(2)), m.group(3).lower(), int(m.group(4)))
ok_a = len(rows) == 5 and all(n in rows and rows[n][0] == L and rows[n][1].startswith(C) and rows[n][2] == T
                              for n, (L, C, T) in TRUTH.items())
if ok_a:
    score += 4
else:
    notes.append("a: wrong or unparsed %s" % rows)
m = re.search(r"ИТОГ-В:\s*(\d+)\s*;\s*(\d+)", text)
if m and (m.group(1), m.group(2)) == ("7", "3"):
    score += 3
else:
    notes.append("v: %s (expected 7; 3)" % (m.groups() if m else "unparsed"))
proof = re.search(r"единствен", text.lower()) is not None
notes.append("b: proof-like text %s (3 pts are manual)" % ("found" if proof else "missing"))

ts = time.strftime("%Y%m%d-%H%M%S")
with open(os.path.join(here, "reason-%s-%s.txt" % (label, ts)), "w") as f:
    f.write("=== THINKING ===\n" + "".join(think) + "\n=== ANSWER ===\n" + text)
out = os.path.join(here, "reason.csv"); new = not os.path.exists(out)
gen = usage.get("completion_tokens")
with open(out, "a") as f:
    if new:
        f.write("time,label,model,effort,auto_score_of_7,total_s,completion_tokens,tok_s,notes\n")
    f.write('%s,%s,%s,%s,%d,%.0f,%s,%s,"%s"\n' % (time.strftime("%F %T"), label, model, effort, score, t1 - t0, gen,
            round(gen / (t1 - first), 1) if gen and first else "", " | ".join(notes)))
print("%s: auto score %d/7 (+ proof 0-3 by hand), %.0f s, %s tokens; %s" % (label, score, t1 - t0, gen, " | ".join(notes)))
