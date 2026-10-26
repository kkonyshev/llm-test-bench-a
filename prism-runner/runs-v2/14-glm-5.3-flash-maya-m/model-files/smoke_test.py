"""PRISM RUNNER smoke test (Playwright, Python).

Serves the game dir on a free port, drives the game through
title -> playing -> paused -> dead -> restart, screenshots each phase,
and writes smoke-report.txt plus PNGs next to this script.
"""
import random
import socket
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
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
    print(("PASS" if ok else "FAIL") + f"  {name}  {detail}", flush=True)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def make_server(port):
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    port = free_port()
    make_server(port)
    time.sleep(0.5)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=CHROMIUM_ARGS)
        page = browser.new_page(viewport={"width": 960, "height": 640})
        page.on("console", lambda m: console_msgs.append((m.type, m.text)))
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.on("requestfailed", lambda r: failed_requests.append(r.url))

        page.goto(f"http://127.0.0.1:{port}/prism-runner.html",
                  timeout=30000)
        # ---- title screen ----
        page.wait_for_function(
            "() => window.__prism && window.__prism.state === 'title'",
            timeout=20000)
        check("test hook __prism exists", True)
        check("state is title", True)
        page.screenshot(path=str(SHOTS / "1-title.png"))

        # ---- start ----
        page.keyboard.press("Enter")
        page.wait_for_function(
            "() => window.__prism.state === 'playing'", timeout=5000)
        check("state playing after Enter", True)
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOTS / "2-playing.png"))

        # ---- play ~10 s with random inputs ----
        rng = random.Random(7)
        t0 = time.time()
        while time.time() - t0 < 10:
            key = rng.choice(["ArrowLeft", "ArrowRight", "ArrowUp",
                              "ArrowDown", "ArrowLeft"])
            page.keyboard.press(key)
            page.wait_for_timeout(rng.uniform(300, 700))
            d = page.evaluate("() => window.__prism")
            if d["state"] != "playing":
                break
        d = page.evaluate("() => window.__prism")
        dist_incr = d["distance"] > 5
        spd_ok = d["speed"] > 0 and d["speed"] < 1000
        sc_incr = d["score"] > 0
        check("distance increased", dist_incr, f"distance={d['distance']:.1f}")
        check("score increased", sc_incr, f"score={d['score']:.1f}")
        check("speed finite & positive", spd_ok, f"speed={d['speed']:.2f}")
        check("no NaN/inf in sim", all(map(lambda v: v == v and abs(v) < 1e6,
              [d["score"], d["speed"], d["distance"]])), "finite")

        # random-input play may legitimately die; restart before pause checks
        if d["state"] == "dead":
            page.screenshot(path=str(SHOTS / "2b-random-death.png"))
            page.keyboard.press("R")
            page.wait_for_function(
                "() => window.__prism.state === 'playing'", timeout=5000)
            check("restart after random-play death", True)
            page.wait_for_timeout(300)

        # ---- pause freezes score ----
        page.keyboard.press("P")
        page.wait_for_function(
            "() => window.__prism.state === 'paused'", timeout=5000)
        check("state paused", True)
        sc0 = page.evaluate("() => window.__prism.score")
        page.wait_for_timeout(1000)
        sc1 = page.evaluate("() => window.__prism.score")
        check("score frozen while paused", sc0 == sc1, f"{sc0} vs {sc1}")
        page.screenshot(path=str(SHOTS / "3-paused.png"))
        page.keyboard.press("P")
        page.wait_for_function(
            "() => window.__prism.state === 'playing'", timeout=5000)
        check("resumed to playing", True)

        # ---- die: stop steering, wait (max 60 s) ----
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
        dead_score = page.evaluate("() => window.__prism.score")
        page.keyboard.press("R")
        page.wait_for_timeout(120)   # brief: prove score dropped, not zero-claim
        d = page.evaluate("() => window.__prism")
        check("restarted to playing", d["state"] == "playing",
              f"got {d['state']!r}")
        check("score reset on restart", d["score"] < dead_score * 0.5,
              f"before={dead_score:.1f} after={d['score']:.1f}")
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
    check("no console errors/warnings", not errs,
          "; ".join(t for _, t in errs)[:400])
    check("no pageerrors", not page_errors, "; ".join(page_errors)[:400])
    check("no failed requests", not failed_requests,
          "; ".join(failed_requests)[:400])

    with open(REPORT, "w") as f:
        f.write("PRISM RUNNER smoke report\n")
        f.write("=" * 60 + "\n")
        for name, ok, detail in results:
            f.write(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}\n")
        f.write("\nconsole messages (error/warning):\n  ")
        f.write("\n  ".join(f"{t}: {x}" for t, x in errs) or "(none)")
        f.write("\npageerrors:\n  ")
        f.write("\n  ".join(page_errors) or "(none)")
        f.write("\nfailed requests:\n  ")
        f.write("\n  ".join(failed_requests) or "(none)")
        f.write(f"\naverage frame time: {avg_ms:.1f} ms\n")
    print("\nreport written to", REPORT)


if __name__ == "__main__":
    main()
