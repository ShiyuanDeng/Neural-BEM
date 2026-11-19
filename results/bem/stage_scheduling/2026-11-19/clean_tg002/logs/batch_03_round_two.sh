#!/bin/bash
# Coordinator batch 03, 19 November 2026: round two on the contrast-13.3 misses. Waits for batch 02.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
until grep -q "BATCH DONE" $L/batch_02.state 2>/dev/null; do sleep 10; done
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
one() { tag=$1; c=$2; shift 2
  echo "$(date -u +%FT%TZ) start $tag $c" >> $L/batch_03.state
  $P -m experiments.comparison.compare_clean_warmups $tag $c "$@" >> $L/batch_03.log 2>&1
  echo "$(date -u +%FT%TZ) end $tag $c exit=$?" >> $L/batch_03.state; }
for c in kite__c13.3 peanut__c13.3 asymmetric__c13.3 hook__c13.3 cross__c13.3 cog__c13.3; do one two_sided $c --start two_sided; done
for c in star__c13.3 c_shape__c13.3 aphex_twin__c13.3; do one warmup_long $c --warmup-iterations 220 --warmup-quota 3000; done
for c in kite__c13.3 peanut__c13.3 asymmetric__c13.3 hook__c13.3 cross__c13.3 cog__c13.3; do one two_sided_long $c --start two_sided --warmup-iterations 220 --warmup-quota 3000; done
for c in star__c13.3 c_shape__c13.3 aphex_twin__c13.3; do one warmup_long_wall600 $c --warmup-iterations 220 --warmup-quota 3000 --seconds 600; done
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_03.state
