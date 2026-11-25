#!/bin/bash
unset STRATA_COMPONENTS_DIR
export STRATA_PYTHON=/data/remote-agent/venv-strata/bin/python3
export STRATA_DSV41_EXE=/data/remote-agent/dsv41/engine-dsv41/0.1.56-linux-x86_64-cuda-cuda13/strata-dsv41
S="/data/remote-agent/Strata/bin/strata"; B=/data/remote-agent/bench; D=/data/remote-agent/strata-data
L=fed-x16-deepseek-$(date +%H%M); cd /data/remote-agent/Strata
echo "=== $L start $(date +%T)"
timeout 3000 $S launch --family deepseek41 --model ist-das-2.25bpw --context 1m --set prefill-chunk=16384 --data-dir $D --port 8097 --access local --no-api-key --no-tui --yes --restart --tune skip > $B/launch-$L.log 2>&1
echo "launch rc=$? $(date +%T)"; grep -iE "error|fail|experts|RAM|ssd|in place" $B/launch-$L.log | tail -6 | cut -c1-200
ok=0; for i in $(seq 1 60); do python3 -c "
import urllib.request,json,sys
b=json.dumps({\"model\":\"x\",\"messages\":[{\"role\":\"user\",\"content\":\"Say OK\"}],\"max_tokens\":4,\"reasoning_effort\":\"none\"}).encode()
try: urllib.request.urlopen(urllib.request.Request(\"http://127.0.0.1:8097/v1/chat/completions\",data=b,headers={\"Content-Type\":\"application/json\"}),timeout=900); sys.exit(0)
except Exception: sys.exit(1)" && { ok=1; break; }; sleep 15; done
if [ $ok = 1 ]; then
  echo "ready $(date +%T); RAM $(free -g | awk "/Mem:/{print \$3\" used, \"\$6\" cache\"}") GB; VRAM $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
  nohup $B/monfan.sh $L >/dev/null 2>&1 & MP=$!
  sleep 5; KEY=none python3 $B/bench.py $L http://127.0.0.1:8097 2>&1 | tail -1; sleep 6; kill $MP
  python3 -c "
import csv
r=list(csv.DictReader(open(\"$B/mon-$L.csv\")))
def n(x):
  try: return float(x)
  except: return None
for k in (\"tctl\",\"tccd1\",\"fan2\",\"gpu_temp\",\"gpu_w\"):
  v=[n(x[k]) for x in r if n(x[k]) is not None]
  print(\"  %-10s avg %7.1f  max %7.1f\" % (k, sum(v)/len(v), max(v)))"
else echo "FAILED"; tail -6 $B/launch-$L.log | cut -c1-200; fi
$S launch --stop >/dev/null 2>&1
echo "=== end $(date +%T)"
