You are a senior creative WebGL engineer. Build a complete, playable 3D game that runs  
entirely from a single HTML file.  
  
## DELIVERABLE  
- Exactly one file: `prism-runner.html`. Self-contained: no build step, no bundler, no npm,  
  no server-side code, no external assets (no images, models, textures, fonts, or audio files).  
- Only external dependency allowed: Three.js, pinned to an exact version, loaded from a CDN  
  via `<script type="importmap">` (e.g. `https://unpkg.com/three@0.160.0/build/three.module.js`).  
  Everything else — geometry, materials, audio, UI — must be generated in code.  
- No placeholders, no `TODO`, no `...` elisions, no "add your code here". The file must run  
  as-is on first load. Assume it is served over HTTP `python3 -m http.server`); if you want  
  it to also work from `file://`, note that in the run instructions and use a build that allows it.  
- Target size: 700–1200 lines, readable. Organize with clear section banners.  
  
## GAME: "PRISM RUNNER"  
Third-person endless runner in a dark neon void.  
  
- Player: a glowing, spinning icosahedron riding a magnetic hoverboard on a 3-lane track that  
  streams toward the camera. Track surface: grid-lines with emissive accents, slight vertical  
  curvature per segment so the horizon feels alive.  
- Controls:  
  - ← / A and → / D: switch lane (lerp fast, snap on arrive, ±1 lane per press, no key-repeat spam)  
  - ↑ / W / Space: jump (short, readable arc with a visible shadow/ground marker)  
  - ↓ / S: slide/dash (0.4s, passes under high gates)  
  - P or Esc: pause. R: restart. M: mute. Enter/Space: start from title screen.  
  - Touch: swipe left/right/up/down, tap to start/restart. Must be genuinely playable on phone.  
- Core loop: procedurally generate track segments ahead of the player, recycle them behind  
  (object pooling, zero per-frame allocation). Spawn obstacles and collectible "shards".  
  Speed ramps with distance; score = distance travelled + shards × multiplier; multiplier  
  builds with a clean streak and resets on hit. One collision = game over.  
- Fairness rules (non-negotiable): every obstacle pattern must be solvable with the mechanics  
  available — never block all 3 lanes at once; guarantee at least one open lane through every  
  gate; respect a minimum reaction window based on current speed (min ~0.9s of travel between  
  consecutive pattern starts); ease the first ~15 seconds in.  
- Feel: sub-50ms input latency, spring-damped camera follow with slight roll on lane change,  
  FOV punch that scales with speed, screen shake + 80ms hit-stop on collision, particle burst  
  on shard pickup and on death, subtle vignette/scanline, bloom-like glow via emissive  
  materials + additive sprites (do NOT require postprocessing passes — keep it one render pass).  
  
## TECHNICAL REQUIREMENTS  
- Game states: title → playing → paused → dead → restart, with no page reload. Clean reset  
  function that recycles/reinitialises everything correctly.  
- Fixed-timestep simulation (e.g. 1/120s accumulator) with clamped delta (max 100ms) so physics  
  is frame-rate independent; render interpolation optional.  
- Rendering: `InstancedMesh` or pooled meshes for repeated obstacles/shards; cap total draw  
  calls and keep the scene under ~120k triangles; `renderer.setPixelRatio(Math.min(devicePixelRatio, 2))`;  
  handle resize; reuse Vector3/Quaternion/Color temporaries (no `new` inside the loop).  
- Audio: fully synthesized with WebAudio (oscillators + noise + envelopes) — jump, lane whoosh,  
  shard pickup with rising pitch per combo, crash, plus a low drone/music bed. Must only start  
  after a user gesture (autoplay policy). Mute toggle persisted.  
- Persistence: `localStorage` best score, muted state. Corrupt/blocked storage must not crash.  
- Accessibility & robustness: fully playable keyboard-only; `prefers-reduced-motion` reduces  
  shake/FOV punch; pause automatically on `visibilitychangeblur`; guard against NaN,  
  negative speeds, and missing WebGL2 with a graceful message.  
- Code quality: strict-ish module scope (no globals leaking), named tuning constants at the top  
  `SPEED_START`, `SPEED_MAX`, `LANE_WIDTH`, `GRAVITY`, `JUMP_V`, `SPAWN_AHEAD`, ...) so values  
  are tweakable in one place, comments only where the reasoning isn't obvious from the code.  
  
## SELF-VERIFICATION (do this before answering)  
1. Re-read your file end to end. Confirm every Three.js API you call exists in the pinned  
   version, every `addEventListener` has a matching removal or a documented single-fire, and  
   every state transition is reachable.  
2. Trace three scenarios mentally: start → first 10s of play, a collision → death → restart,  
   and pause during a jump. Find and fix anything that leaks objects, double-spawns, or leaves  
   the game soft-locked.  
3. Confirm the fairness rules hold for the worst-case generated pattern.  
4. If you have a browser or headless environment available, load the page and confirm zero  
   console errors and a visible first frame; state what you observed. If not, say so explicitly  
   and list what you verified statically.  
5. Do not claim anything works that you did not verify.  
  
## OUTPUT FORMAT  
1. The complete file in one fenced ```html code block.  
2. Run instructions (3–5 lines: how to serve and open it, controls table).  
3. A short table of the tuning constants and a one-line note on what to change for a harder or  
   gentler game.
  
  
  
save result on attached terminal - working directory ~/workspace/Nanbeige_Nanbeige4.3-33B/ (create if missing)
