#!/usr/bin/env bash
set -uo pipefail
cd /home/drdeng/Neural_SDF_BEM_AD_organised
run_dir=results/validation/cleaned_interfaces/MR-001/S3_slider_no_log_cap
timeout 900s env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -u -m experiments.benchmark run \
  --cases hook__c0.5 aphex_twin__c0.5 --solver modal_muller --geometry-update slider \
  --localization none --device auto --frequency-threads 4 --workers 1 \
  --run-dir "$run_dir" > "$run_dir/run.log" 2>&1
run_status=$?
printf '%s\n' "$run_status" > "$run_dir/exit_code.txt"
exit "$run_status"
