#!/bin/bash
# Usage: ./run_detached.sh <coding-benchmark|reasoning-benchmark> <ollama-model-tag>
#
# Runs a benchmark fully detached (nohup + disown) so it survives session/
# terminal interruptions, then polls the log until the run finishes.
#
# Why this exists: on some setups, a plain backgrounded process tied to the
# calling session can get killed mid-run (observed after 15-50+ minutes,
# inconsistently) even though the model itself is still generating fine.
# Fully detaching avoids losing a long run to that.
set -uo pipefail

DIR="$1"
MODEL="$2"
BASE="$(cd "$(dirname "$0")" && pwd)"
BENCH="$BASE/$DIR"

if [ ! -d "$BENCH" ]; then
  echo "Unknown benchmark dir: $DIR (expected coding-benchmark or reasoning-benchmark)"
  exit 1
fi

rm -rf "$BENCH/runs/$MODEL"
cd "$BENCH"
LOG="runs_${MODEL}.log"
nohup ./run_bench.sh "$MODEL" > "$LOG" 2>&1 &
PID=$!
disown
echo "launched $DIR for $MODEL with PID $PID, logging to $BENCH/$LOG"

MARKER="pytest summary"
if [ "$DIR" = "reasoning-benchmark" ]; then
  MARKER="grading"
fi

while ! grep -q "$MARKER" "$LOG" 2>/dev/null; do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "process $PID no longer running (may have finished or died — check the log)"
    break
  fi
  sleep 15
done

echo "=== done ==="
grep -v "tokens so far" "$LOG"
