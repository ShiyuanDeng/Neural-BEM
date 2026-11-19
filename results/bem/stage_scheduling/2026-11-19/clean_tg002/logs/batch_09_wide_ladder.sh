#!/bin/bash
# Coordinator batch 09, 19 November 2026: warm-up plus wider early bands, all 30 clean cases. Waits for batch 05.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
until grep -q "BATCH DONE" $L/batch_05.state 2>/dev/null; do sleep 10; done
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
for s in c_shape circle kite peanut star asymmetric hook cross cog aphex_twin; do
  for q in 4 0.5 13.3; do
    c=${s}__c${q}
    echo "$(date -u +%FT%TZ) start warmup_wide $c" >> $L/batch_09.state
    $P -m experiments.comparison.compare_clean_wide_ladder $c >> $L/batch_09.log 2>&1
    echo "$(date -u +%FT%TZ) end warmup_wide $c exit=$?" >> $L/batch_09.state
  done
done
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_09.state
