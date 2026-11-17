#!/usr/bin/env bash
set -uo pipefail
cd /home/drdeng/Neural_SDF_BEM_AD_organised
run_dir=results/validation/cleaned_interfaces/GGB-002/T0_timing
export PYTHONPATH=solvers:.:/home/drdeng/Gau-Gal/src
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
timeout 600s /home/drdeng/miniconda3/envs/EMNerf/bin/python -u -m experiments.gaugal_comparison \
  ggb-run --cases circle__c4 --grid 51 --sigma-scale .7 --lambda-scale .5 \
  --step-size 1 --contrast-max 15 --num-iter 10 --frequencies 19 \
  --out "$run_dir" > "$run_dir/run.log" 2>&1
run_status=$?
printf '%s\n' "$run_status" > "$run_dir/exit_code.txt"
exit "$run_status"
