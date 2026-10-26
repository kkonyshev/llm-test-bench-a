#!/bin/bash
# Read-only: samples Ollama llama-server (Nanbeige) every 30 s via /slots, ps and nvidia-smi; re-attaches on restart.
D=/data/remote-agent/nanbeige-prism-metrics; OUT=$D/samples.csv
[ -f $OUT ] || echo "time,pid,etime_s,cpu_pct,rss_gb,port,n_ctx,prompt_tokens,prompt_processed,decoded,processing,gpu0_mem,gpu0_util,gpu0_w,gpu1_mem,gpu1_util,gpu1_w,ram_avail_gb,load1" > $OUT
while true; do
  PID=$(pgrep -f "^/usr/local/lib/ollama/llama-server" | head -1)
  if [ -n "$PID" ]; then
    read et cpu rss < <(ps -o etimes=,pcpu=,rss= -p $PID)
    PORT=$(tr "\0" " " < /proc/$PID/cmdline | grep -oP "(?<=--port )\d+")
    S=$(curl -s --max-time 5 localhost:$PORT/slots | python3 -c "import json,sys
try:
  s=json.load(sys.stdin)[0]; print(\"%s,%s,%s,%s,%s\"%(s[\"n_ctx\"],s.get(\"n_prompt_tokens\",\"\"),s.get(\"n_prompt_tokens_processed\",\"\"),s[\"next_token\"][0][\"n_decoded\"],s[\"is_processing\"]))
except Exception: print(\",,,,\")")
    g=$(nvidia-smi --query-gpu=memory.used,utilization.gpu,power.draw --format=csv,noheader,nounits | tr -d " " | paste -sd,)
    av=$(awk "/MemAvailable/{printf \"%.1f\", \$2/1048576}" /proc/meminfo); ld=$(cut -d" " -f1 /proc/loadavg)
    echo "$(date +%F\ %T),$PID,$et,$cpu,$(awk "BEGIN{printf \"%.1f\", ${rss:-0}/1048576}"),$PORT,$S,$g,$av,$ld" >> $OUT
  fi
  sleep 30
done
