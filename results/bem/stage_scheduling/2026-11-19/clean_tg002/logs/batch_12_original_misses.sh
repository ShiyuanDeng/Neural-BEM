#!/bin/bash
# Coordinator batch 12, 19 November 2026: the default (with warm-up), recovered contrast, on the original
# misses at contrasts 0.5 and 4 that have not yet gone through it. One at a time; the GPU is shared with
# the baseline coordinator's GauGal fits. Plan: investigate_bem_stage_scheduling/05.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
for c in cog__c0.5 c_shape__c4 aphex_twin__c4; do
  echo "$(date -u +%FT%TZ) start default_recovered $c" >> $L/batch_12.state
  $P -m experiments.comparison.compare_clean_default_contrasts recovered $c >> $L/batch_12.log 2>&1
  echo "$(date -u +%FT%TZ) end default_recovered $c exit=$?" >> $L/batch_12.state
done
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_12.state
