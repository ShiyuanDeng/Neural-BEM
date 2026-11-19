#!/bin/bash
# Coordinator batch 04, 19 November 2026: band-1 warm-up at 0.5 GHz instead of 0.25 GHz on the four rescued cases.
# Waits for batch 03.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
until grep -q "BATCH DONE" $L/batch_03.state 2>/dev/null; do sleep 10; done
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
for c in circle__c13.3 cog__c0.5 kite__c4 aphex_twin__c4; do
  echo "$(date -u +%FT%TZ) start warmup_050 $c" >> $L/batch_04.state
  $P -m experiments.comparison.check_warmup_frequency $c >> $L/batch_04.log 2>&1
  echo "$(date -u +%FT%TZ) end warmup_050 $c exit=$?" >> $L/batch_04.state
done
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_04.state
