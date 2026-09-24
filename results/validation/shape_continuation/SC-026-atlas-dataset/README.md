# SC-026 — consolidated atlas dataset

[Plan](../../../../docs/iterations/shape_frequency_continuation/iteration_09/03_plan.md) ·
[first analysis](ANALYSIS.md).
Every accepted state recorded by SC-022, SC-024 and SC-025 has the full
per-frequency atlas. That is 49 trajectories, 2,066 state records and
**1,286 unique curves**, over six cases:
- development: wrong circle, five-lobe star, C;
- former held-out: kite, peanut, hook.

The trajectories are the SC-022 and SC-024 ladder and fixed-32 runs (backend
variants V0–V3 and V2x4), and SC-025's ladder, fixed32, progress and atlas
arms.

## Contents

| File | Content |
|---|---|
| `cells/<case>.npz` (local) | Per unique state (`state_key`, curve `coefficients`), for 19 frequencies of 0.25–2.5 GHz: the Jacobian `jacobian` (S, 19, 48, 97), the residual `residual` (S, 19, 48), the loss, the relative residual and the solver residual |
| `evaluation/<case>_EVALUATION_ONLY.npz` (local) | The normal-ray error per harmonic (exact current-normal move to the truth), with its beyond-48 RMS, coverage and misalignment; the closest-distance proxy; symmetric RMS and Hausdorff distances; tightest curvature radius; refit error at K=192; speed ratio; perimeter |
| `index.json` | Every unique state, with each place it occurs: bundle, run, stage, iteration, band, loss, damping. Plus its distance and radius |
| `manifest.json`, `summary.json` | Source and input hashes, the file SHA-256 values, the build time |
| `analyze.py`, `analysis*.json`, `analysis.png`, `ANALYSIS.md` | The [first analysis](ANALYSIS.md) |

**Conventions** (as in SC-022):
- Coordinates are a0, a1…a48, b1…b48, in metres, of the normal distance in
  the state's normalized arclength.
- Each frequency is normalized as a single-frequency stage with weight 1.
- Rows are the real parts, then the imaginary parts, of the 24 paired
  responses.
- G = JᵀJ and g = Jᵀr. A stage block is the weighted sum over its
  frequencies.
- N=512 nodes, with the SC-022/SC-025 observations and oracles.

**Build checks:**
- JᵀJ and Jᵀr reproduce SC-022's stored Gauss–Newton blocks and gradients to
  ≤ 1.0e-15 relative, and the losses exactly, on all 159 SC-022 state records
  (`build_check.json`).
- Every input hash equals its source bundle's manifest.
- The largest solver residual over all 24,434 cells is 7.8e-14 (`summary.json`).

## Loading

```python
from experiments.shape_continuation.atlas_dataset import load
data = load("results/validation/shape_continuation/SC-026-atlas-dataset", "circle_to_c")
data["gauss_newton"].shape  # (S, 19, 97, 97); data["gradient"]: (S, 19, 97)
```

## Reproduce

```bash
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.shape_continuation.atlas_dataset \
    --output <fresh bundle> --workers 22        # ~30 min; resumable from work/
```

The `.npz` files are local (about 1 GB). Their hashes are tracked in
`summary.json`. The build is deterministic, so they can be regenerated.
