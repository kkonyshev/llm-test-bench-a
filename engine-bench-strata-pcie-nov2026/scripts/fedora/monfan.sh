#!/bin/sh
f=/data/remote-agent/bench/mon-$1.csv
echo "time,tctl,tccd1,mhz,fan1,fan2,fan3,fan4,gpu_temp,gpu_w" > $f
while :; do
  s=$(sensors 2>/dev/null)
  t=$(echo "$s" | awk "/Tctl/{gsub(/[+°C]/,\"\",\$2);print \$2}"); c=$(echo "$s" | awk "/Tccd1/{gsub(/[+°C]/,\"\",\$2);print \$2}")
  fans=$(echo "$s" | awk "/^fan[1-4]:/{printf \"%s,\", \$2}")
  m=$(awk "/MHz/{s+=\$4;n++} END{printf \"%d\", s/n}" /proc/cpuinfo)
  g=$(nvidia-smi --query-gpu=temperature.gpu,power.draw --format=csv,noheader,nounits | head -1 | tr -d " ")
  echo "$(date +%T),$t,$c,$m,$fans$g" >> $f; sleep 3
done
