#!/usr/bin/env bash
# NU-003 spectral increment map on the six core configurations (iteration 11 plan).
# Run from the repository root after the pre-check passes and after:
#   python -m experiments.cleaned_interface.nu003 prepare --output results/validation/cleaned_interfaces/NU-003
set -euo pipefail
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
BASE=results/validation/cleaned_interfaces
LOGS=${LOGS:-$BASE/NU-003-logs}
mkdir -p "$LOGS"
# One case at a time, four frequency threads (the nodal Kress audit peaks near 9 GB).
for case in core__wrong_circle core__peanut core__circle_to_c core__hook core__circle_to_star core__kite; do
  python -m experiments.cleaned_interface.nu003 run --output "$BASE/NU-003" --cases "$case" \
    --device auto --frequency-threads "${FREQUENCY_THREADS:-4}" > "$LOGS/$case.log" 2>&1 || echo "FAILED $case"
done
python -m experiments.cleaned_interface.nu003 report --output "$BASE/NU-003" > "$LOGS/report.json"
python -m experiments.cleaned_interface.nu003 drift --output "$BASE/NU-003-drift" > "$LOGS/drift.json"
