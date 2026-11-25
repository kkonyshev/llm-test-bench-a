#!/bin/bash
# runs every test model on my Strata copy (user components) at port 8097, one after another
C=/data/remote-agent/strata-components; P=$C/control/0.1.68; export STRATA_COMPONENTS_DIR=$C
S="$P/python/bin/python3.12 $P/strata.py"; B=/data/remote-agent/bench; D=/data/remote-agent/strata-data
cd /data/remote-agent/Strata
echo "start $(date +%T)"
nvidia-smi --query-gpu=pcie.link.gen.max,pcie.link.width.current --format=csv,noheader
while read fam mod ctx extra; do
  L=x16-$fam-$mod-$(date +%H%M)
  echo "=== $fam $mod $ctx $extra $(date +%T)"
  timeout 1800 $S launch --family $fam --model $mod --context $ctx --data-dir $D --port 8097 --access local --no-api-key --no-tui --yes --restart --tune skip $extra > $B/launch-$L.log 2>&1
  echo "launch rc=$?"; tail -2 $B/launch-$L.log | cut -c1-200
  ok=0; for i in $(seq 1 60); do python3 -I -c "
import urllib.request,json,sys
b=json.dumps({\"model\":\"x\",\"messages\":[{\"role\":\"user\",\"content\":\"Say OK\"}],\"max_tokens\":4}).encode()
try: urllib.request.urlopen(urllib.request.Request(\"http://127.0.0.1:8097/v1/chat/completions\",data=b,headers={\"Content-Type\":\"application/json\"}),timeout=600); sys.exit(0)
except Exception as e: print(\"probe:\",str(e)[:120]); sys.exit(1)" && { ok=1; break; }; sleep 10; done
  if [ $ok = 1 ]; then
    nohup $B/monfan.sh $L >/dev/null 2>&1 & MP=$!
    sleep 5; KEY=none python3 -I $B/bench.py $L http://127.0.0.1:8097 2>&1 | tail -1; sleep 6; kill $MP
    python3 -I -c "
import csv
r=list(csv.DictReader(open(\"$B/mon-$L.csv\")))
def n(x):
  try: return float(x)
  except: return None
print(\" \".join(\"%s max %s\"%(k,max(n(x[k]) for x in r if n(x[k]) is not None)) for k in (\"tctl\",\"tccd1\",\"fan2\",\"gpu_temp\",\"gpu_w\")))"
    grep -hE "link reads" ~/.local/share/strata/*.log $D/../Strata/*.log /data/remote-agent/Strata/*.log 2>/dev/null | tail -1 | cut -c40-110
  else echo "SKIPPED: never answered"; fi
  $S runtime stop >/dev/null 2>&1; pkill -u remote-agent -f "strata(-[a-z0-9]+)? --serve" 2>/dev/null; sleep 15
done <<LIST
nvfp4 nvfp4 512k
qwen36 q8_0 128k
qwen iq3_s 64k
inkling-2-mini ud-q4_k_xl 32k
unsloth ud-q4_k_xl 32k
hy4-flash sq-128 128k
LIST
echo "ALL DONE $(date +%T)"
