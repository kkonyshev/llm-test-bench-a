import re
import sys

# Each checker returns True if the extracted answer text for that problem
# is correct. Matching is case-insensitive substring/number matching so
# reasonable phrasing variants are accepted, but the actual right value
# must be present.

def has_number(text, value, tol=0.01):
    for tok in re.findall(r"-?\d+\.?\d*", text):
        try:
            if abs(float(tok) - value) <= tol:
                return True
        except ValueError:
            pass
    return False

def has_all(text, words):
    t = text.lower()
    return all(w.lower() in t for w in words)

CHECKS = {
    1: lambda t: has_number(t, 41.40),
    2: lambda t: has_number(t, 19),
    3: lambda t: has_all(t, ["cleo", "dog"]) and has_all(t, ["ben", "fish"]),
    4: lambda t: has_number(t, 42),
    5: lambda t: has_number(t, 9),
    6: lambda t: has_number(t, 2),
    7: lambda t: "feather" in t.lower() and "kilogram" in t.lower(),
    8: lambda t: has_number(t, 100),
    9: lambda t: has_all(t, ["x", "truth"]) and has_all(t, ["y", "liar"]),
    10: lambda t: has_number(t, 8),
    11: lambda t: has_number(t, 10),
    12: lambda t: has_all(t, ["dan", "tallest"]) and has_all(t, ["ellie", "shortest"]),
}

TOTAL = len(CHECKS)


def extract_answers(text):
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    # Find each "ANSWER n:" marker and capture text up to the next marker
    markers = list(re.finditer(r"ANSWER\s*(\d+)\s*[:.]", text, re.IGNORECASE))
    answers = {}
    for i, m in enumerate(markers):
        n = int(m.group(1))
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        answers[n] = text[start:end].strip()
    return answers


def main():
    path = sys.argv[1]
    text = open(path).read()
    answers = extract_answers(text)

    passed = 0
    for n in range(1, TOTAL + 1):
        ans = answers.get(n, "")
        ok = CHECKS[n](ans) if ans else False
        passed += ok
        status = "PASS" if ok else "FAIL"
        preview = ans[:70].replace("\n", " ")
        print(f"[{status}] Q{n}: {preview}")

    print(f"\n{passed}/{TOTAL} correct")


if __name__ == "__main__":
    main()
