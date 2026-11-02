#!/usr/bin/env bash
set -uo pipefail
cd /home/drdeng/Neural_SDF_BEM_AD_organised
run_dir=results/validation/cleaned_interfaces/MR-001/S4_slider_sampled_log_interval
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
/home/drdeng/miniconda3/envs/EMNerf/bin/python -u "$run_dir/replay.py" > "$run_dir/replay.log" 2>&1
replay_status=$?
printf '%s\n' "$replay_status" > "$run_dir/replay_exit_code.txt"
if [ "$replay_status" -ne 0 ]; then exit "$replay_status"; fi
timeout 900s /home/drdeng/miniconda3/envs/EMNerf/bin/python -u -m experiments.benchmark run \
  --cases cog__c13.3 aphex_twin__c0.5 aphex_twin__c4 aphex_twin__c13.3 \
  --solver modal_muller --geometry-update slider --localization none \
  --device auto --frequency-threads 4 --workers 1 \
  --run-dir "$run_dir" > "$run_dir/run.log" 2>&1
run_status=$?
printf '%s\n' "$run_status" > "$run_dir/exit_code.txt"
exit "$run_status"
