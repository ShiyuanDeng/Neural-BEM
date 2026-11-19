#!/bin/bash
# Coordinator batch 08, 19 November 2026: the 0.25 GHz warm-up on the frozen 1% noise draw 0, all 30 cases.
# Waits for batch 07.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
until grep -q "BATCH DONE" $L/batch_07.state 2>/dev/null; do sleep 10; done
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
for s in circle kite peanut star asymmetric c_shape hook cross cog aphex_twin; do
  for q in 0.5 4 13.3; do
    c=${s}__c${q}
    echo "$(date -u +%FT%TZ) start warmup_n1d0 $c" >> $L/batch_08.state
    $P -m experiments.comparison.compare_noisy_warmups $c --draw 0 >> $L/batch_08.log 2>&1
    echo "$(date -u +%FT%TZ) end warmup_n1d0 $c exit=$?" >> $L/batch_08.state
  done
done
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_08.state
