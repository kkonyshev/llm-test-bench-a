#!/bin/bash
# Read-only: samples the GLM engine (build/maya) every 30 s, re-attaching if its PID changes.
D=/data/remote-agent/glm-prism-metrics; OUT=$D/samples.csv; L=/data/apps/project-maya-deep-seek-v4.1/maya-maya-m.log
[ -f $OUT ] || echo "time,pid,etime_s,cpu_pct,rss_gb,gpu0_mem_mib,gpu0_util,gpu0_w,gpu0_pcie,gpu1_mem_mib,gpu1_util,gpu1_w,gpu1_pcie,ram_avail_gb,load1,log_last" > $OUT
while true; do
  PID=$(pgrep -f "^/data/apps/project-maya-deep-seek-v4.1/build/maya " | head -1)
  if [ -n "$PID" ]; then
    read et cpu rss < <(ps -o etimes=,pcpu=,rss= -p $PID)
    g0=$(nvidia-smi -i 0 --query-gpu=memory.used,utilization.gpu,power.draw --format=csv,noheader,nounits | tr -d " ")
    p0=$(nvidia-smi -i 0 --query-gpu=pcie.link.gen.current,pcie.link.width.current --format=csv,noheader | tr -d " " | tr , x)
    g1=$(nvidia-smi -i 1 --query-gpu=memory.used,utilization.gpu,power.draw --format=csv,noheader,nounits | tr -d " ")
    p1=$(nvidia-smi -i 1 --query-gpu=pcie.link.gen.current,pcie.link.width.current --format=csv,noheader | tr -d " " | tr , x)
    av=$(awk "/MemAvailable/{printf \"%.1f\", \$2/1048576}" /proc/meminfo); ld=$(cut -d" " -f1 /proc/loadavg)
    last=$(tail -1 $L 2>/dev/null | tr -d ",\"" | cut -c1-160)
    echo "$(date +%F\ %T),$PID,$et,$cpu,$(awk "BEGIN{printf \"%.1f\", ${rss:-0}/1048576}"),$g0,$p0,$g1,$p1,$av,$ld,\"$last\"" >> $OUT
  fi
  sleep 30
done
