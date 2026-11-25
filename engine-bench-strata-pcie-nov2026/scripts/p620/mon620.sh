#!/bin/sh
f=/home/konstantin/bench/mon620-$1.csv
echo "time,tctl,tccd_max,ram_used_gb,load1,gpu_temp,gpu_w,gpu_util,gpu_mem" > $f
while :; do
  s=$(sensors 2>/dev/null)
  t=$(echo "$s" | awk "/Tctl/{gsub(/[+°C]/,\"\",\$2);print \$2}")
  c=$(echo "$s" | awk "/Tccd/{gsub(/[+°C]/,\"\",\$2); if(\$2>m)m=\$2} END{print m}")
  r=$(free -g | awk "/Mem:/{print \$3}"); l=$(cut -d" " -f1 /proc/loadavg)
  g=$(nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used --format=csv,noheader,nounits | head -1 | tr -d " ")
  echo "$(date +%T),$t,$c,$r,$l,$g" >> $f; sleep 5
done
