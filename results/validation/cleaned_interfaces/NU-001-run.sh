#!/usr/bin/env bash
# NU-001 arms A and B on the six core configurations.
# Run from the repository root after preparing both campaigns:
#   python -m experiments.cleaned_interface.n_update_audit prepare --arm A --output results/validation/cleaned_interfaces/NU-001-A
#   python -m experiments.cleaned_interface.n_update_audit prepare --arm B --output results/validation/cleaned_interfaces/NU-001-B
set -euo pipefail
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
BASE=results/validation/cleaned_interfaces
LOGS=${LOGS:-$BASE/NU-001-logs}
mkdir -p "$LOGS"
# Shortest CI-001 cases first, alternating arms, so complete pairs land early.
jobs=()
for case in core__wrong_circle core__peanut core__circle_to_c core__hook core__circle_to_star core__kite; do
  for arm in A B; do jobs+=("$arm $case"); done
done
# One case at a time with four frequency threads: the nodal Kress audit alone
# peaks at about 9 GB (any update), so concurrent cases are OOM-killed on 16 GB.
printf '%s\n' "${jobs[@]}" | xargs -P "${PARALLEL:-1}" -L 1 bash -c \
  'python -m experiments.cleaned_interface.n_update_audit run --output '"$BASE"'/NU-001-$0 --cases $1 \
     --device auto --frequency-threads '"${FREQUENCY_THREADS:-4}"' > '"$LOGS"'/$0__$1.log 2>&1 || echo "FAILED $0 $1"'
for arm in A B; do
  python -m experiments.cleaned_interface.n_update_audit report --output "$BASE/NU-001-$arm" > "$LOGS/report_$arm.json"
done
python -m experiments.cleaned_interface.n_update_audit drift --output "$BASE/NU-001-drift" \
  --campaigns "$BASE/CI-001" "$BASE/NU-001-A" "$BASE/NU-001-B" > "$LOGS/drift.json"
