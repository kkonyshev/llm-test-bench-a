#!/bin/sh
# mon.sh LABEL: sample CPU/GPU temps, power and clocks every 5 s into mon-LABEL.csv until killed
f=/data/remote-agent/bench/mon-$1.csv
echo "time,tctl,tccd1,cpu_mhz_avg,load1,gpu_temp,gpu_w,gpu_util,gpu_mem_mib" > $f
while :; do
  t=$(sensors 2>/dev/null | awk "/Tctl/{gsub(/[+°C]/,\"\",\$2);print \$2}"); c=$(sensors 2>/dev/null | awk "/Tccd1/{gsub(/[+°C]/,\"\",\$2);print \$2}")
  m=$(awk "/MHz/{s+=\$4;n++} END{printf \"%d\", s/n}" /proc/cpuinfo); l=$(cut -d" " -f1 /proc/loadavg)
  g=$(nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used --format=csv,noheader,nounits | head -1 | tr -d " ")
  echo "$(date +%T),$t,$c,$m,$l,$g" >> $f; sleep 5
done
