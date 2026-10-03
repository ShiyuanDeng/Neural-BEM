#!/usr/bin/env bash
# Phase L and Phase 0 are already complete. Wait for the fixed Phase 1 process,
# then execute the remaining phases in the approved order and preserve each one.
set -euo pipefail
cd /home/drdeng/Neural_SDF_BEM_AD
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
fm_python=/home/drdeng/miniconda3/envs/EMNerf/bin/python
fm_output=results/validation/cleaned_interfaces/FM-003
fm_pid=${1:?Pass the active phase-1 PID}
while kill -0 "$fm_pid" 2>/dev/null; do sleep 5; done

preserve_phase() {
  "$fm_python" -m experiments.cleaned_interface.fm003 verify
  "$fm_python" -m experiments.cleaned_interface.fm003 report
  git diff --check
  git add experiments/cleaned_interface/fm003_review.py experiments/cleaned_interface/fm003_suffix.py experiments/cleaned_interface/test_fm003_suffix.py docs/iterations/cleaned_interfaces/iteration_20/05_suffix_entry.md "$fm_output" docs/iterations/cleaned_interfaces/iteration_21/01_results.md
  git commit -m "$1"
  git push
  test "$(git rev-parse HEAD)" = "$(git rev-parse '@{upstream}')"
  git status --short
}

"$fm_python" -m experiments.cleaned_interface.fm003_review validate --phase phase1
preserve_phase 'FM-003: complete and validate paired high-contrast stage-2 census'
"$fm_python" -u -m experiments.cleaned_interface.fm003_suffix > "$fm_output/phase2.log" 2>&1
"$fm_python" -m experiments.cleaned_interface.fm003_review distances
preserve_phase 'FM-003: continue the paired census winner with the frozen CI-001 suffix'
"$fm_python" -u -m experiments.cleaned_interface.fm003 census --phase phase3 > "$fm_output/phase3.log" 2>&1
"$fm_python" -m experiments.cleaned_interface.fm003_review validate --phase phase3
preserve_phase 'FM-003: complete and validate full-matrix high-contrast control census'
"$fm_python" -u -m experiments.cleaned_interface.fm003 census --phase phase4 > "$fm_output/phase4.log" 2>&1
"$fm_python" -m experiments.cleaned_interface.fm003_review validate --phase phase4
"$fm_python" -m experiments.cleaned_interface.fm003_review synthesis
preserve_phase 'FM-003: complete paired contrast-4 control and synthesize registered gates'
printf '%s\n' 'All frozen experimental phases completed and pushed.'
