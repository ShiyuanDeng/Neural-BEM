#!/bin/bash
# Coordinator batch 06, 19 November 2026: round four, frontier-capped bands on all 30 clean cases, then four controls.
# Waits for batch 04.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
until grep -q "BATCH DONE" $L/batch_04.state 2>/dev/null; do sleep 10; done
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
one() { arm=$1; c=$2
  echo "$(date -u +%FT%TZ) start $arm $c" >> $L/batch_06.state
  $P -m experiments.comparison.compare_clean_frontier_caps $arm $c >> $L/batch_06.log 2>&1
  echo "$(date -u +%FT%TZ) end $arm $c exit=$?" >> $L/batch_06.state; }
for s in circle kite peanut star asymmetric c_shape hook cross cog aphex_twin; do for q in 0.5 4 13.3; do one frontier_capped ${s}__c${q}; done; done
for c in circle__c4 kite__c4 star__c13.3 aphex_twin__c0.5; do one frontier_measured $c; done
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_06.state
