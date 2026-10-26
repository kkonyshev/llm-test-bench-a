"""PRISM RUNNER smoke test (Playwright, Python).

Serves the game dir on a free port, drives the game through
title -> playing -> paused -> dead -> restart, screenshots each phase,
and writes smoke-report.txt plus PNGs next to this script.
"""
import json
import random
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "prism-runner.html"
REPORT = ROOT / "smoke-report.txt"
SHOTS = ROOT / "shots"
SHOTS.mkdir(exist_ok=True)

CHROMIUM_ARGS = [
    "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
    "--ignore-gpu-blocklist", "--no-sandbox",
    "--disable-dev-shm-usage",
]

results = []          # (name, ok, detail)
console_msgs = []     # (type, text)
page_errors = []
failed_requests = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS" if ok else "FAIL") + f"  {name}  {detail}")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def serve(port):
    subprocess.run(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=ROOT, check=False,
    )


def main():
    port = free_port()
    threading.Thread(target=serve, args=(port,), daemon=True).start()
    time.sleep(0.8)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=CHROMIUM_ARGS)
        page = browser.new_page(viewport={"width": 960, "height": 640})
        page.on("console", lambda m: console_msgs.append((m.type, m.text)))
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.on("requestfailed", lambda r: failed_requests.append(r.url))

        page.goto(f"http://127.0.0.1:{port}/prism-runner.html",
                  wait_until="load", timeout=30000)
        page.wait_for_timeout(2500)          # let module + CDN load settle

        # ---- title screen ----
        hook_ok = page.evaluate("() => !!window.__prism")
        check("test hook __prism exists", hook_ok)
        st = page.evaluate("() => window.__prism.state")
        check("state is title", st == "title", f"got {st!r}")
        page.screenshot(path=str(SHOTS / "1-title.png"))

        # ---- start ----
        page.keyboard.press("Enter")
        page.wait_for_timeout(600)
        st = page.evaluate("() => window.__prism.state")
        check("state playing after Enter", st == "playing", f"got {st!r}")

        # ---- play ~10 s with random inputs ----
        rng = random.Random(7)
        t0 = time.time()
        frames = 0
        while time.time() - t0 < 10:
            key = rng.choice(["ArrowLeft", "ArrowRight", "ArrowUp",
                              "ArrowDown", "ArrowLeft"])
            page.keyboard.press(key)
            page.wait_for_timeout(rng.uniform(300, 700))
            frames += 1
        d = page.evaluate("() => window.__prism")
        alive = d["state"] == "playing"
        dist_incr = d["distance"] > 5
        spd_ok = d["speed"] > 0 and d["speed"] < 1000
        check("still alive after 10s of steering", alive, f"state={d['state']}")
        check("distance increased", dist_incr, f"distance={d['distance']:.1f}")
        check("speed finite & positive", spd_ok, f"speed={d['speed']:.2f}")
        page.screenshot(path=str(SHOTS / "2-playing.png"))

        # ---- pause freezes score ----
        page.keyboard.press("P")
        page.wait_for_timeout(300)
        st = page.evaluate("() => window.__prism.state")
        sc0 = page.evaluate("() => window.__prism.score")
        check("state paused", st == "paused", f"got {st!r}")
        page.wait_for_timeout(1000)
        sc1 = page.evaluate("() => window.__prism.score")
        check("score frozen while paused", sc0 == sc1, f"{sc0} vs {sc1}")
        page.screenshot(path=str(SHOTS / "3-paused.png"))
        page.keyboard.press("P")
        page.wait_for_timeout(300)
        st = page.evaluate("() => window.__prism.state")
        check("resumed to playing", st == "playing", f"got {st!r}")

        # ---- die: stop steering, wait for death (max 60 s) ----
        t1 = time.time()
        while time.time() - t1 < 60:
            st = page.evaluate("() => window.__prism.state")
            if st == "dead":
                break
            page.wait_for_timeout(400)
        st = page.evaluate("() => window.__prism.state")
        check("reached dead state", st == "dead", f"got {st!r}")
        page.screenshot(path=str(SHOTS / "4-dead.png"))

        # ---- restart with R ----
        page.keyboard.press("R")
        page.wait_for_timeout(500)
        d = page.evaluate("() => window.__prism")
        check("restarted to playing", d["state"] == "playing", f"got {d['state']!r}")
        sc = d["score"]
        check("score reset on restart", sc < 5, f"score={sc}")
        page.screenshot(path=str(SHOTS / "5-restart.png"))

        # ---- average frame time from rAF deltas ----
        avg_ms = page.evaluate("""() => new Promise(res => {
            let n = 0, sum = 0, last = 0;
            function cb(t){ if(last){ sum += t-last; n++; } last = t;
                if(n < 60) requestAnimationFrame(cb); else res(sum/n); }
            requestAnimationFrame(cb);
        })""")
        check("average frame time measured", avg_ms > 0, f"{avg_ms:.1f} ms")

        browser.close()

    # ---- console hygiene ----
    errs = [m for m in console_msgs if m[0] in ("error", "warning")]
    check("no console errors/warnings", not errs, "; ".join(t for _, t in errs)[:400])
    check("no pageerrors", not page_errors, "; ".join(page_errors)[:400])
    check("no failed requests", not failed_requests,
          "; ".join(failed_requests)[:400])

    with open(REPORT, "w") as f:
        f.write("PRISM RUNNER smoke report\n")
        f.write("=" * 60 + "\n")
        for name, ok, detail in results:
            f.write(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}\n")
        f.write("\nconsole messages (error/warning):\n")
        f.write("\n".join(f"  {t}: {x}" for t, x in errs) or "  (none)")
        f.write("\npageerrors:\n" + ("\n".join(page_errors) or "  (none)"))
        f.write("\nfailed requests:\n" + ("\n".join(failed_requests) or "  (none)"))
        f.write(f"\naverage frame time: {avg_ms:.1f} ms\n")
    print("\nreport written to", REPORT)


if __name__ == "__main__":
    main()
