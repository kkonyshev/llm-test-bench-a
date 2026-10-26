#!/usr/bin/env python3
"""PRISM RUNNER smoke test.

Serves the directory on a free port, drives the game in headless Chromium
(SwiftShader WebGL), records console/page errors and failed requests,
checks all state transitions, writes smoke-report.txt + PNG screenshots.
"""
import http.server
import os
import random
import socketserver
import sys
import threading
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

RESULTS = []          # (check, ok, detail)
CONSOLE = []          # console error/warning messages
PAGE_ERRORS = []
FAILED_REQS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (("  | " + detail) if detail else ""), flush=True)


def state_of(page):
    return page.evaluate("window.__prism ? window.__prism.state : 'NO_HOOK'")


def metrics(page):
    return page.evaluate(
        "window.__prism ? {s: window.__prism.score, d: window.__prism.distance, "
        "v: window.__prism.speed} : {s:-1, d:-1, v:-1}")


class Quiet(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, *a):
        pass


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    srv = Quiet(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/prism-runner.html"
    print("serving on", url, flush=True)

    avg_frame_ms = None
    frames_measured = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                  "--ignore-gpu-blocklist"])
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda m: CONSOLE.append(f"[{m.type}] {m.text}")
                if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: PAGE_ERRORS.append(str(e)))
        page.on("requestfailed",
                lambda r: FAILED_REQS.append(f"{r.method} {r.url} -> {r.failure}"))

        page.goto(url, wait_until="load", timeout=30000)

        # ---- boot / title screen ----
        try:
            page.wait_for_function(
                "window.__prism && window.__prism.state === 'title'", timeout=20000)
            check("boot: page loads, __prism hook, state == 'title'", True)
        except Exception as e:
            check("boot: page loads, __prism hook, state == 'title'", False,
                  str(e)[:300])
        page.screenshot(path="shot-01-title.png")

        # ---- start with Enter ----
        page.keyboard.press("Enter")
        try:
            page.wait_for_function("window.__prism.state === 'playing'", timeout=5000)
            check("start: Enter -> state == 'playing'", True)
        except Exception as e:
            check("start: Enter -> state == 'playing'", False, str(e)[:200])
        page.screenshot(path="shot-02-playing.png")

        # ---- measure frame times (~3 s) while playing ----
        try:
            ts = page.evaluate("""() => new Promise(res => {
                const out = []; let last = performance.now(); let n = 0;
                function tick(now){ out.push(now-last); last=now;
                  if (++n < 150) requestAnimationFrame(tick); else res(out); }
                requestAnimationFrame(tick);
            })""")
            ts = [t for t in ts if t > 0]
            frames_measured = len(ts)
            avg_frame_ms = sum(ts) / max(1, len(ts))
        except Exception as e:
            check("frame timing measured", False, str(e)[:200])

        # ---- play ~10 s with random inputs ----
        keys = ["ArrowLeft", "ArrowRight", "Space", "ArrowDown", "KeyA",
                "KeyD", "KeyS", "Space"]
        t_end = time.time() + 10.0
        while time.time() < t_end:
            page.keyboard.press(random.choice(keys))
            time.sleep(0.35)
        m1 = metrics(page)
        st = state_of(page)
        check("play: state still alive after 10 s", st in ("playing", "dying", "dead"),
              f"state={st}")
        check("play: distance increased", m1["d"] > 30, f"distance={m1['d']:.1f}")
        check("play: score increased", m1["s"] > 0, f"score={m1['s']:.1f}")
        check("play: speed finite and positive",
              m1["v"] == m1["v"] and m1["v"] > 0 and m1["v"] < 1e6,
              f"speed={m1['v']:.2f}")
        page.screenshot(path="shot-03-after-play.png")

        # ---- pause / resume ----
        if state_of(page) != "playing":
            # died during random play -> restart, then retry pause test
            page.keyboard.press("r")
            page.wait_for_function("window.__prism.state === 'playing'", timeout=5000)
            time.sleep(1.0)
        page.keyboard.press("p")
        try:
            page.wait_for_function("window.__prism.state === 'paused'", timeout=3000)
            check("pause: P -> state == 'paused'", True)
        except Exception as e:
            check("pause: P -> state == 'paused'", False, str(e)[:200])
        page.screenshot(path="shot-04-paused.png")
        s_a = metrics(page)["s"]
        time.sleep(1.0)
        s_b = metrics(page)["s"]
        check("pause: score frozen for 1 s", abs(s_b - s_a) < 1e-9,
              f"before={s_a:.2f} after={s_b:.2f}")
        page.keyboard.press("p")
        try:
            page.wait_for_function("window.__prism.state === 'playing'", timeout=3000)
            check("resume: P again -> state == 'playing'", True)
        except Exception as e:
            check("resume: P again -> state == 'playing'", False, str(e)[:200])

        # ---- death: stop steering, drive into obstacles (max 60 s) ----
        died = False
        t_end = time.time() + 60.0
        while time.time() < t_end:
            st = state_of(page)
            if st == "dead":
                died = True
                break
            if st == "playing":
                page.keyboard.press("ArrowUp")   # a few jumps to vary patterns
                time.sleep(1.2)
            time.sleep(0.4)
        check("death: reaches state 'dead' within 60 s", died, f"state={state_of(page)}")
        page.screenshot(path="shot-05-dead.png")
        if died:
            m2 = metrics(page)
            check("death: score accumulated", m2["s"] > 10, f"score={m2['s']:.1f}")

        # ---- restart with R ----
        page.keyboard.press("r")
        try:
            page.wait_for_function("window.__prism.state === 'playing'", timeout=5000)
            m3 = metrics(page)
            check("restart: R -> state == 'playing', score reset",
                  m3["s"] < 10, f"score={m3['s']:.2f}")
        except Exception as e:
            check("restart: R -> state == 'playing', score reset", False, str(e)[:200])
        page.screenshot(path="shot-06-restart.png")

        # ---- reload-free second start: die again quickly is not required; just stop ----
        browser.close()
    srv.shutdown()

    # ---- report ----
    real_errors = [c for c in CONSOLE if c.startswith("[error]")] + PAGE_ERRORS
    warnings = [c for c in CONSOLE if c.startswith("[warning]")]
    lines = []
    lines.append("PRISM RUNNER SMOKE REPORT")
    lines.append("=" * 60)
    all_ok = True
    for name, ok, detail in RESULTS:
        all_ok = all_ok and ok
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    lines.append("")
    lines.append(f"console errors: {len(real_errors)}")
    for e in real_errors:
        lines.append("  " + e[:300])
    lines.append(f"page errors   : {len(PAGE_ERRORS)}")
    for e in PAGE_ERRORS:
        lines.append("  " + e[:300])
    lines.append(f"failed requests: {len(FAILED_REQS)}")
    for e in FAILED_REQS:
        lines.append("  " + e[:300])
    lines.append(f"warnings (informational, swiftshader): {len(warnings)}")
    for e in warnings[:10]:
        lines.append("  " + e[:300])
    lines.append("")
    if avg_frame_ms is not None:
        lines.append(f"avg frame time: {avg_frame_ms:.1f} ms over {frames_measured} frames"
                     f" (headless SwiftShader software rendering)")
    lines.append("")
    lines.append("OVERALL: " + ("PASS" if all_ok and not real_errors and not FAILED_REQS else "FAIL"))

    report = "\n".join(lines) + "\n"
    with open("smoke-report.txt", "w") as f:
        f.write(report)
    print(report)
    return 0 if "OVERALL: PASS" in report else 1


if __name__ == "__main__":
    sys.exit(main())
