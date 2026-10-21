# Geometry update implementation

Implemented on 2026-10-21 in the existing `organised` branch. The requested
`/home/drdeng/Neural_SDF_BEM_AD` checkout was unavailable; work used the supplied
`/Users/sean/Projects/Neural-BEM` workspace. No branch or worktree was created.

## Delivered structure

Each retained method has a file in
`solvers/bem_inverse/geometry_update_methods/` and exports `geometry_update()`.
Preparation, measurements, metrics, diagnostics and prepared records live with
their method. The update classes have no update-class inheritance chain.

`fit_stage()` binds the selected method once and calls it inside backtracking.
The active `spectral.py` constructs each displaced curve, calls direct area,
speed and intersection checks, projects on two grids, compares those projections,
and checks the stored candidate. Batched derivative preparation is retained.

The maintained fixed pipelines and TG-002 now select sampled spectral validity.
Bare `fit()` keeps its spline default. Optional certificate logic lives in
`certified_spectral.py`, with its mathematics in `certificates.py`.

Curve values, signed area, resizing and cleanup live beside `FourierCurve` in
`continuation/geometry.py`. The upper `geometry.py`, `continuation/updates.py`
and old method paths contain compatibility exports. Old `trial()` entry points
delegate to the new construction. The retained certificate replay uses the new
entry point and records its concrete intermediate curves.

This intentionally changes spectral admissibility: sampled refusals are final,
with no certificate override. Sampled checks do not establish continuous-curve
nonintersection. No speedup or full inverse recovery result is claimed.

## Focused verification

Commands used Python 3.12 on macOS/arm64 with `PYTHONPATH=solvers:.` and
`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`.
Test paths below are relative to `pytest/bem_inverse/`.

| Existing or new tests | Result |
| --- | --- |
| `test_similarity.py` | 5 passed |
| `test_continuation_policy.py` | 8 passed |
| `test_pipelines.py`, `test_refactor_contract.py` | 8 passed |
| `test_geometry_update_methods.py`, `test_resolution_resume.py`, `test_entry_reuse.py` | 16 passed, 1 failed |
| `test_validity_order.py` | 1 passed, 2 failed |

Total: **38 passed, 3 failed**. The three failures require exact coefficient
equality. The resume comparison differs by at most `3.61e-18`; the optional
certificate-order comparisons differ by at most `3.93e-17` in the paired
diagnostic. All 40 paired certificate trials have matching accept/refuse
decisions and refusal reasons. No tolerances or reference arrays were changed.

The same strict-equality failure types were previously reproduced on the
untouched baseline on this platform; see
[the existing precision record](../../../reference/inverse_refactor_status.md).
They remain unresolved; this is not a fully passing test result.

The two new tests cover the retained batched derivative/projection construction,
zero-step identity, absence of certificates on the active path, crossing refusal,
base-curve preservation and compatibility-entry accounting. All six selectable
methods also passed preparation and zero/nonzero-step smoke checks.

CUDA was unavailable, so device arithmetic was not executed. No new inverse
experiment or benchmark run was performed. Historical inputs and saved evidence
were not regenerated.
