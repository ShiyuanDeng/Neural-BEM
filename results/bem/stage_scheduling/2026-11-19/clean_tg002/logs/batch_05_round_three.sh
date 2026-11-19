#!/bin/bash
# Coordinator batch 05, 19 November 2026: round three, circle stages on several frequency sets, all 30 clean cases.
# Waits for batch 08 (order: 03, 04, 07, 08, 05).
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
until grep -q "BATCH DONE" $L/batch_08.state 2>/dev/null; do sleep 10; done
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
for arm in circle_then_default circle_then_full; do
  for s in circle kite peanut star asymmetric c_shape hook cross cog aphex_twin; do
    for q in 0.5 4 13.3; do
      c=${s}__c${q}
      echo "$(date -u +%FT%TZ) start $arm $c" >> $L/batch_05.state
      $P -m experiments.comparison.compare_clean_circle_ladders $arm $c >> $L/batch_05.log 2>&1
      echo "$(date -u +%FT%TZ) end $arm $c exit=$?" >> $L/batch_05.state
    done
  done
done
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_05.state
