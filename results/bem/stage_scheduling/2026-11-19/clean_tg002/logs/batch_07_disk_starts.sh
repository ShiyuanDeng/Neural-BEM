#!/bin/bash
# Coordinator batch 07, 19 November 2026: disk-start diagnostic on four contrast-13.3 misses. Waits for batch 04 (batch 06 was withdrawn at 03:35 UTC).
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
until grep -q "BATCH DONE" $L/batch_04.state 2>/dev/null; do sleep 10; done
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
for c in cog__c13.3 kite__c13.3 star__c13.3 cross__c13.3; do
  echo "$(date -u +%FT%TZ) start disk_start $c" >> $L/batch_07.state
  $P -m experiments.comparison.check_localized_real_warmup $c >> $L/batch_07.log 2>&1
  echo "$(date -u +%FT%TZ) end disk_start $c exit=$?" >> $L/batch_07.state
done
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_07.state
