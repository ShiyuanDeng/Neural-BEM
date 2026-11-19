#!/bin/bash
# Coordinator batch 02, 19 November 2026. Waits for batch 01, then:
#  (a) real 0.25 GHz warm-up on the 15 remaining clean passes (controls), one at a time, alone on the GPU;
#  (b) the two measured-cylinder fits (warm-up attempt_02 and first_cap) side by side; they have no binding wall limit.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
until grep -q "BATCH DONE" $L/batch_01.state; do sleep 10; done
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
for c in circle__c0.5 kite__c0.5 peanut__c0.5 peanut__c4 star__c0.5 star__c4 asymmetric__c0.5 asymmetric__c4 \
         c_shape__c0.5 hook__c0.5 hook__c4 cross__c0.5 cross__c4 cog__c4 aphex_twin__c0.5; do
  echo "$(date -u +%FT%TZ) start warmup $c" >> $L/batch_02.state
  $P -m experiments.comparison.compare_clean_schedules warmup $c >> $L/batch_02.log 2>&1
  echo "$(date -u +%FT%TZ) end warmup $c exit=$?" >> $L/batch_02.state
done
echo "$(date -u +%FT%TZ) TG CONTROLS DONE" >> $L/batch_02.state
M=results/bem/baseline_data/measured_schedule/2026-11-19
mkdir -p $M/logs
unset PYTHONPATH
echo "$(date -u +%FT%TZ) start measured warmup and first_cap" >> $L/batch_02.state
$P experiments/bem_on_baseline_data/csi_measured_schedule.py warmup > $M/logs/warmup_attempt_02.log 2>&1 &
W=$!
$P experiments/bem_on_baseline_data/csi_measured_schedule.py first_cap > $M/logs/first_cap_attempt_01.log 2>&1 &
F=$!
wait $W; echo "$(date -u +%FT%TZ) end measured warmup exit=$?" >> $L/batch_02.state
wait $F; echo "$(date -u +%FT%TZ) end measured first_cap exit=$?" >> $L/batch_02.state
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_02.state
