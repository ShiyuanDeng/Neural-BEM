# SC-020/021/022 outsider-review audit — 2026-09-24

[Verdict and derivations](../../../../docs/iterations/shape_frequency_continuation/iteration_08/02_proposals/01_codex_outsider_review.md)
are the authoritative interpretation. This directory stores the reproducible
checks behind it, separate from the original experiment records.

`audit.py` reads saved artifacts, verifies hashes, replays atlas/backend step
consistency and accepted-step model gains, and computes an analytic offset-circle
counterexample to treating closest distance as current-normal displacement.
It also compares three local coordinate sets at the same final-star atlas
state. Those counterfactuals are linear solves on saved matrices, not inverse
experiments or demonstrations of improved recovery.

```bash
PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/shape_continuation/review-20260924/audit.py
```

Requires the six local SC-022 `atlas.npz` and
`true_error_EVALUATION_ONLY.npz` pairs. It performs no forward or inverse
solves and writes only this directory's `audit.json`. The original files
remain unchanged. The report identifies the reviewed Git commit and checks
the original input, numerical-source and dense-artifact hashes.

Targeted validation, independently rerun during the review:

```bash
PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  experiments/shape_continuation/test_lm_backend.py \
  experiments/shape_continuation/test_atlas_survey.py
```

Result: **12 passed in 2.68 s**; 13 existing Matplotlib/Pyparsing deprecation
warnings. This review did not rerun the complete recovery campaigns.
