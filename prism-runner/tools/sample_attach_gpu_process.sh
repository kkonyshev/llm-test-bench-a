#!/bin/bash
# attach sampler to the largest non-miner GPU compute process (and re-attach on restart)
D=/data/remote-agent/nemotron-metrics; LAST=""
while true; do
  P=$(nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader,nounits | grep -viE "srbminer|vision|speaches|whisper" | sort -t, -k2 -nr | head -1 | cut -d, -f1 | tr -d " ")
  if [ -n "$P" ] && [ "$P" != "$LAST" ]; then
    echo "$(date +%F\ %T) attach $P: $(ps -o user=,args= -p $P | cut -c1-600)" >> $D/attach.txt
    nohup $D/sample.sh $P >/dev/null 2>&1 &
    LAST=$P
  fi
  sleep 15
done
