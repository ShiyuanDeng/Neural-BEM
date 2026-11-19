#!/bin/bash
# Coordinator batch, 19 November 2026: real 0.25 GHz warm-up on the 13 remaining clean misses,
# then the planned longer-stage and longer-wall fits. One fit at a time, alone on the GPU.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
for c in cog__c0.5 kite__c4 circle__c13.3 asymmetric__c13.3 c_shape__c4 aphex_twin__c4 \
         kite__c13.3 peanut__c13.3 star__c13.3 c_shape__c13.3 hook__c13.3 cross__c13.3 cog__c13.3 aphex_twin__c13.3; do
  echo "$(date -u +%FT%TZ) start warmup $c" >> $L/batch_01.state
  $P -m experiments.comparison.compare_clean_schedules warmup $c >> $L/batch_01.log 2>&1
  echo "$(date -u +%FT%TZ) end warmup $c exit=$?" >> $L/batch_01.state
done
echo "$(date -u +%FT%TZ) start longer_stage asymmetric__c13.3" >> $L/batch_01.state
$P -m experiments.comparison.compare_clean_schedules longer_stage asymmetric__c13.3 >> $L/batch_01.log 2>&1
echo "$(date -u +%FT%TZ) end longer_stage asymmetric__c13.3 exit=$?" >> $L/batch_01.state
echo "$(date -u +%FT%TZ) start longer_wall c_shape__c13.3" >> $L/batch_01.state
$P -m experiments.comparison.compare_clean_schedules longer_wall c_shape__c13.3 >> $L/batch_01.log 2>&1
echo "$(date -u +%FT%TZ) end longer_wall c_shape__c13.3 exit=$?" >> $L/batch_01.state
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_01.state
