#!/bin/bash
# Read-only: copies each new maya-bench.txt (detected by content hash) into this folder with a label.
D=/data/remote-agent/maya-bench-results; F=/data/apps/project-maya-deep-seek-v4.1/maya-bench.txt
last=$(md5sum < $F)
while true; do
  h=$(md5sum < $F 2>/dev/null)
  if [ -n "$h" ] && [ "$h" != "$last" ]; then sleep 5; h=$(md5sum < $F); cp $F "$D/$(date -d @$(stat -c %Y $F) +%F_%H%M)__$(cat $D/label.txt).txt"; last=$h; fi
  sleep 10
done
