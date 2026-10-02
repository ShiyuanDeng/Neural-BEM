#!/usr/bin/env bash
# NU-004 (iteration 12 plan): modal Müller + spline-free map (MS) and modal + spline control (MN).
# Run from the repository root after preparing both campaigns:
#   python -m experiments.cleaned_interface.nu004 prepare --arm MS --output results/validation/cleaned_interfaces/NU-004-MS
#   python -m experiments.cleaned_interface.nu004 prepare --arm MN --output results/validation/cleaned_interfaces/NU-004-MN
set -euo pipefail
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
BASE=results/validation/cleaned_interfaces
LOGS=${LOGS:-$BASE/NU-004-logs}
mkdir -p "$LOGS"
# One case at a time; MS then MN for each case so complete pairs land early.
for case in core__wrong_circle core__peanut core__circle_to_c core__hook core__circle_to_star core__kite; do
  for arm in MS MN; do
    python -m experiments.cleaned_interface.nu004 run --output "$BASE/NU-004-$arm" --cases "$case" \
      --device auto --frequency-threads "${FREQUENCY_THREADS:-4}" > "$LOGS/${arm}__$case.log" 2>&1 || echo "FAILED $arm $case"
  done
done
for arm in MS MN; do
  python -m experiments.cleaned_interface.nu004 report --output "$BASE/NU-004-$arm" > "$LOGS/report_$arm.json"
done
python -m experiments.cleaned_interface.nu004 drift --output "$BASE/NU-004-drift" > "$LOGS/drift.json"
