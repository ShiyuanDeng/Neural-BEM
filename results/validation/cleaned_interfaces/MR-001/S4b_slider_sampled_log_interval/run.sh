#!/usr/bin/env bash
set -uo pipefail
cd /home/drdeng/Neural_SDF_BEM_AD_organised
root=results/validation/cleaned_interfaces/MR-001/S4b_slider_sampled_log_interval
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
overall_status=0
for case in aphex_twin__c4 aphex_twin__c13.3; do
  run_dir="$root/$case"
  mkdir -p "$run_dir"
  timeout 300s /home/drdeng/miniconda3/envs/EMNerf/bin/python -u -m experiments.benchmark run \
    --cases "$case" --solver modal_muller --geometry-update slider --localization none \
    --device auto --frequency-threads 4 --workers 1 \
    --run-dir "$run_dir" > "$run_dir/run.log" 2>&1
  run_status=$?
  printf '%s\n' "$run_status" > "$run_dir/exit_code.txt"
  if [ "$run_status" -ne 0 ]; then overall_status="$run_status"; fi
done
exit "$overall_status"
