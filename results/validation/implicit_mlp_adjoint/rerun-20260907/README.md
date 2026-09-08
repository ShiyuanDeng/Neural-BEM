# Implicit-MLP reruns after the repairs — 2026-09-07

Four full inverse runs with the repaired defaults. They establish that **the
Method-B Fourier bandwidth, not the optimizer, bounded both earlier targets**,
and that the circle stops on its iteration budget once that bound is removed.
Recovery gates still FAIL on both targets. No production target defaults were
changed by these runs.

| Run | Bandwidth | Accepted updates | Stop | Final train rel. L2 | Final holdout rel. L2 | Audited conversion error |
|---|---:|---:|---|---:|---:|---:|
| [circle](circle/summary.md) | 10 | 11 | `no_decreasing_neural_step` | 5.653e-1 | 1.172e+0 | **1.99997e-4 m** |
| [circle-bw20](circle-bw20/summary.md) | 20 | **60 / 60** | `maximum_iterations` | **1.795e-3** | **7.053e-2** | 7.984e-5 m |
| [star](star/summary.md) | 48 | 27 | `no_decreasing_neural_step` | 6.526e-1 | 1.023e+0 | **1.99947e-4 m** |
| [star-bw96](star-bw96/summary.md) | 96 | 32 | `no_decreasing_neural_step` | 5.966e-1 | 1.078e+0 | 1.061e-4 m |

**1. Confirmed: the production bandwidths, not the line search, stopped the
first two runs.** Both terminated with an audited conversion error pinned to
the `2.0e-4 m` budget to six significant figures, so every further candidate
was rejected by the fidelity guard before its BEM solve. The circle's training
loss was still falling monotonically (`9.210e-1` to `3.080e-1`) when it stopped.
This is the guard working as designed: it converted a silent conversion error
into a visible stop.

**2. Confirmed: the limiting parameter is Fourier bandwidth, not extraction
grid or sample density.** Frozen final checkpoints were re-extracted at fixed
production settings while only the conversion resolution changed.

| Checkpoint | Grid / samples / bandwidth | Audited conversion error |
|---|---|---:|
| circle | 129 / 64 / 10 (production) | 0.199997 mm |
| circle | 257 / 128 / 10 | 0.199854 mm |
| circle | 257 / 128 / 20 | **0.061105 mm** |
| star | 257 / 128 / 48 (production) | 0.199947 mm |
| star | 513 / 256 / 48 | 0.185563 mm |
| star | 513 / 256 / 64 | 0.083916 mm |
| star | 513 / 256 / 96 | **0.020594 mm** |
| star | 1025 / 512 / 96 | 0.020008 mm |

A 4x grid and 2x sampling refinement at fixed bandwidth changes the star's
error by 0.6 micrometres; raising the bandwidth from 48 to 96 changes it by
165 micrometres. These are sampled polygonal set distances at the stated
densities, not certified continuous Hausdorff distances.

**3. The circle reaches its previous accuracy with a resolved conversion, and
no longer stalls.** `circle-bw20` accepts all 60 updates with loss still
decreasing at the budget, and ends at an audited conversion error of
`7.984e-5 m` whose refinement change is `1.6e-9 m`. Its accuracy is within
noise of the earlier ungated `circle-verified-20260907` run (holdout `7.053e-2`
against `7.072e-2`; centre `0.0311 mm` against `0.0238 mm`). The earlier run's
reported accuracy was therefore not dominated by conversion error, which was
about `2e-4 m` while its boundary error was about `1.04e-3 m`. What changed is
that the conversion is now measured and refinement-converged, and that the
premature stop is gone. Five of nine gates pass; the two substantive failures
are against the exact-target fitting control, at `1.122 mm` boundary against a
`0.567 mm` allowance and `7.053e-2` holdout against `2.80e-2`.

**4. The star's lobe modes move the wrong way at bandwidth 96.** Its audited
conversion error is `1.061e-4 m`, comfortably inside the budget on the accepted
state. This was originally read here as a real line-search stop with the guard
no longer binding; the
[2026-09-08 checkpoint audit](../review-20260908/README.md) disproves that.
Probing the same frozen checkpoint shows the guard's refinement-change
condition rejecting the last permitted backtrack at `1.15825e-5 m` against a
`1e-5 m` limit, while backtracks 9, 10 and 12 satisfy every production
condition. The stop is a joint guard and search-budget effect, not a stationary
point. The available fallback steps are small — backtrack 9 lowers the loss by
`0.039%` — so this changes why the run stopped, not why its geometry is wrong.
Recovery is almost unchanged from bandwidth 48. Against an initialization of
centre `(0.48, 0.52)`, mean radius `0.060`, amplitude `0.12` and rotation
`0.25 rad`, and a target of `(0.50, 0.50)`, `0.05`, `0.25` and `0` rad:

| Star shape mode | Initial error | Final error (bw 96) | Direction |
|---|---:|---:|---|
| Centre | 28.3 mm | 15.5 mm | improved |
| Mean radius | 10.0 mm | 4.83 mm | improved |
| Lobe amplitude | 0.130 | 0.143 | **worse** |
| Lobe rotation | 0.250 rad | 0.525 rad | **worse** |

The optimizer lowers training loss while degrading lobe amplitude and phase.
The low-order modes are recovered and the lobe modes are driven backwards.
This is consistent with the training band: `StarTarget` records that lobe
amplitude and phase are nearly invisible below about 1 GHz, and only one of
the two training frequencies (0.5 and 1.5 GHz) sits above that. This is one
seed at one acquisition; it identifies a direction, not a proven root cause.
No matched acquisition ablation, Jacobian spectrum or multi-start study was run.

**5. Remaining gap.** The circle's final training relative L2 is `1.795e-3`
against a holdout of `7.053e-2`, a factor of 39. Spending more iterations
descends training loss into that gap rather than closing it. Each run still
fits 8,577 weights to 8 pairs at two frequencies. The evidence here points at
acquisition, and for the star specifically at higher training frequencies
rather than more pairs at the existing ones, but neither was tested.

## Reproduce

The conversion resolution is now reachable from the CLI. These commands
reproduce the two repaired runs; the two production-bandwidth runs are the
same commands without the three resolution flags.

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python run_implicit_mlp_inverse.py \
  --max-iterations 60 --num-pairs 8 --num-nodes 64 \
  --bandwidth 20 --grid-resolution 257 --projected-samples 128 \
  --no-gate --output-dir results/validation/implicit_mlp_adjoint/rerun-20260907/circle-bw20

OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python run_implicit_mlp_inverse.py \
  --target star --max-iterations 60 --num-pairs 8 --num-nodes 194 \
  --bandwidth 96 --grid-resolution 513 --projected-samples 256 \
  --no-gate --output-dir results/validation/implicit_mlp_adjoint/rerun-20260907/star-bw96
```

The runs themselves were produced before `--bandwidth`, `--grid-resolution`
and `--projected-samples` existed, by setting the same three target attributes
from a wrapper script. The flags default to each target's own values, so the
commands above are equivalent; each run's `metrics.json` records the
`geometry_config` actually used. Wall times were 2632 s and 2995 s.

## Artifacts

`metrics.json`, `summary.md` and the driver logs are tracked. The per-weight
`kress_trajectory.csv` files are **not committed**: they carry one column per
network weight and total 89 MB across these four runs. Rerunning the commands
above regenerates them. Checkpoints, plots and response archives follow the
repository's existing ignore rules.
