#!/bin/bash
# Coordinator batch 10, 19 November 2026: the default (with warm-up) with the true contrast supplied,
# the ten clean contrast-13.3 cases, one at a time. Plan: investigate_bem_stage_scheduling/04.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
for s in circle kite peanut star asymmetric c_shape hook cross cog aphex_twin; do
  c=${s}__c13.3
  echo "$(date -u +%FT%TZ) start default_known $c" >> $L/batch_10.state
  $P -m experiments.comparison.compare_clean_default_contrasts known $c >> $L/batch_10.log 2>&1
  echo "$(date -u +%FT%TZ) end default_known $c exit=$?" >> $L/batch_10.state
done
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_10.state
