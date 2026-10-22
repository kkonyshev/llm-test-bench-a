#!/bin/bash
# Usage: ./repeat_when_done.sh <tag-regex> <total-runs>
# For a model whose exact tag is not known yet (still downloading): waits until run_queue.sh
# has benchmarked a tag matching <tag-regex> (listed in queue_done.txt), then hands it to
# repeat_runs.sh for runs 2..<total-runs>.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
RE="$1"; N="$2"
until TAG=$(grep -E "$RE" queue_done.txt 2>/dev/null | head -1) && [ -n "$TAG" ]; do sleep 60; done
echo "=== MATCHED $TAG $(date -u +%FT%TZ) ==="
exec ./repeat_runs.sh "$TAG" "$N"
