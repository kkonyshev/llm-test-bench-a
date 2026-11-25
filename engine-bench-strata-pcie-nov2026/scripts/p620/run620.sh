#!/bin/bash
# run620.sh FAMILY MODEL CONTEXT: start the test Strata on 8097, bench it with resource monitoring, stop it
fam=$1; mod=$2; ctx=$3
C=/data/apps/strata-test/strata-components; P=$C/control/0.1.68; export STRATA_COMPONENTS_DIR=$C
S="$P/python/bin/python3.12 $P/strata.py"; B=/home/konstantin/bench; D=/data/apps/strata-test/data
L=p620-$fam-$mod-$(date +%H%M)
echo "=== $L start $(date +%T)"
cd /data/apps/strata-test
timeout 2400 $S launch --family $fam --model $mod --context $ctx --data-dir $D --port 8097 --access local --no-api-key --no-tui --yes --restart --tune skip > $B/launch-$L.log 2>&1
echo "launch rc=$? $(date +%T)"; grep -iE "error|fail" $B/launch-$L.log | tail -2 | cut -c1-200
ok=0; for i in $(seq 1 30); do python3 -c "
import urllib.request,json,sys
b=json.dumps({\"model\":\"x\",\"messages\":[{\"role\":\"user\",\"content\":\"Say OK\"}],\"max_tokens\":4}).encode()
try: urllib.request.urlopen(urllib.request.Request(\"http://127.0.0.1:8097/v1/chat/completions\",data=b,headers={\"Content-Type\":\"application/json\"}),timeout=600); sys.exit(0)
except Exception: sys.exit(1)" && { ok=1; break; }; sleep 10; done
if [ $ok = 1 ]; then
  echo "ready $(date +%T); RAM used $(free -g | awk "/Mem:/{print \$3}") GB; VRAM $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
  nohup $B/mon620.sh $L >/dev/null 2>&1 & MP=$!
  sleep 5; python3 $B/bench2.py $L http://127.0.0.1:8097 2>&1 | tail -1; sleep 6; kill $MP
  python3 -c "
import csv
r=list(csv.DictReader(open(\"$B/mon620-$L.csv\")))
def n(x):
  try: return float(x)
  except: return None
for k in (\"tctl\",\"tccd_max\",\"ram_used_gb\",\"load1\",\"gpu_temp\",\"gpu_w\",\"gpu_util\",\"gpu_mem\"):
  v=[n(x[k]) for x in r if n(x[k]) is not None]
  print(\"  %-12s avg %7.1f  max %7.1f\" % (k, sum(v)/len(v), max(v)))"
else echo "FAILED: never answered"; tail -5 $B/launch-$L.log | cut -c1-200; fi
$S launch --stop >/dev/null 2>&1; sleep 10
echo "=== $L end $(date +%T)"
