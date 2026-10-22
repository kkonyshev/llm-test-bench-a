#!/bin/bash
# Usage: ./vision_probe.sh <ollama-tag>...
# Checks whether each model really reads images: renders a PNG with a known code and asks the
# model what it says. Results: resources/vision_probe.txt. Holds .bench.lock.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
mkdir -p resources
IMG=resources/vision_probe.png
magick -size 640x200 xc:white -font DejaVu-Sans -pointsize 44 -fill black \
  -annotate +30+80 "Order code: 7341" -fill blue -annotate +30+150 "Colour: BLUE" "$IMG"
B64=$(base64 -w0 "$IMG")
exec 9>.bench.lock; flock 9
for TAG in "$@"; do
  for m in $(curl -s localhost:11434/api/ps | python3 -c "import json,sys;[print(m['name']) for m in json.load(sys.stdin)['models']]"); do ollama stop "$m" >/dev/null 2>&1; done
  OUT=$(curl -s --max-time 900 localhost:11434/api/chat -d "{\"model\":\"$TAG\",\"stream\":false,\"think\":false,
    \"messages\":[{\"role\":\"user\",\"content\":\"What order code and colour are written in this image? Answer in one line.\",\"images\":[\"$B64\"]}],
    \"options\":{\"num_ctx\":8192,\"num_predict\":200}}")
  ANS=$(echo "$OUT" | python3 -c "import json,sys
d=json.load(sys.stdin)
print(('ERROR: '+d['error']) if 'error' in d else d['message']['content'].strip().replace(chr(10),' ')[:200])" 2>&1)
  if echo "$ANS" | grep -q 7341 && echo "$ANS" | grep -qi blue; then V=READS; else V=NO; fi
  echo "$TAG | $V | $ANS" | tee -a resources/vision_probe.txt
  ollama stop "$TAG" >/dev/null 2>&1
done
flock -u 9
echo VISION_DONE
