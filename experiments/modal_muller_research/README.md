# Node-free Laurent Müller research code

Isolated research code for the coefficient-space (Laurent/Fourier) boundary
integral pipeline built on 2026-09-16. **No production solver default depends on
anything here.** `solvers/` is imported read-only, as an independent control.

The research records live in the [Laurent track](../../docs/iterations/laurent/README.md);
the four original exploration notebooks stay in
[Boundary–BIE iteration 05](../../docs/iterations/boundary_bie/iteration_05/01_exploration.md).
Measurements live under `results/experiments/modal_muller_20260916/`.

```bash
cd /home/drdeng/Neural_SDF_BEM_AD
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:. MPLCONFIGDIR=/tmp/modal-matplotlib
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q experiments/modal_muller_research
```

30 tests, ~9 s. Last confirmed 2026-09-17.

## These files are pinned by recorded evidence — do not reorganise them

**11 result bundles record `sha256` hashes of these `.py` files** as the measured
source state: the six `modal_muller_20260916/*` manifests, both
`laurent_neighbour_20260916` manifests, `laurent_calibration_20260916`, and
`scattering_library/findings.json`. Renaming, moving, reformatting or
deduplicating a module silently breaks the provenance chain for every report
that cites it, and the iteration workflow requires results to stay rebuildable
from their saved artifacts.

So: **extend by adding a new package; do not tidy this one.** If a genuine defect
is found, repair it in scope, revalidate, and record the new hashes beside the
old ones rather than replacing them.

### The duplication here is mostly deliberate

Four separate nodal control surfaces (`run_native.nodal`,
`inverse.NodalShapeForward`, `coupled_inverse.NodalScene`,
`deformation_inverse.NodalDeformableEvaluator`) and several separate
evaluations of the reciprocal identity exist because the recorded
qualifications are of the form *"the native path agrees with an independent
nodal implementation to 9e-15."* Merging them into one shared helper would
remove the independence that makes those numbers mean anything. Genuine
copy-paste (`relative`, `boundary`, `metrics`, `chart_record`, `fixture`
appearing twice) is confined to the `run_*` drivers and does not affect any
library consumer.

## Module map

### Library — the stable surface for outside consumers

| Module | Owns |
|---|---|
| `coefficient_operator.py` | Laurent geometry, the right-half-plane log certificate, and node-free Müller assembly. `kernel_matrix` builds every block as `2π(smooth[m,−n] + Σ_ℓ L_ℓ·P[m−ℓ,ℓ−n])` with `L_ℓ = −1/\|ℓ\|`, so the exact singular split is available by linearity. `kernel_matrix_reference` is the retained literal contraction. `ModalMomentFamily` compiles geometry once and reuses it across frequencies |
| `coefficient_fields.py` | Sources, receivers and disconnected-component interaction from cylindrical waves and Graf's addition formula. No boundary grid |
| `coefficient_derivative.py` | Analytic `D_v A` (`ShapeOperator.derivative`), the reciprocal/Hadamard Jacobian (`NativeShapeForward.hadamard_jacobian`), and the fixed-acquisition caches |
| `modal.py` | The nodal→modal flux similarity `S_q` plus a **unitary** (`norm='ortho'`) DFT projection, and the lifted residual. This is the projected-Nyström control object, not the native operator |
| `inverse.py` · `coupled_inverse.py` | Radial charts, evaluators, bounded inverses, residual-driven harmonic selection, matrix-free `TraceJacobian` |
| `scattering_library.py` · `pose_inverse.py` | `T = P A⁻¹ B` compilation, `(I − TU)β = Ta`, rotation phases, analytic pose derivatives |
| `deformable_scattering.py` · `deformation_inverse.py` | `dT/dx_j` in Laurent coordinates at fixed cylindrical normalisation; joint shape+pose inversion with fresh-recompilation acceptance |

The three assemblers agree. Checked 2026-09-17 on circle/ellipse/star at
0.5 and 1.25 GHz, `K_u=24`, `B=64`, `terms=28`: `ModalMomentFamily` versus
`CoefficientGeometry.assemble` `≤8.5e-15` relative Frobenius, and
`ShapeOperator.a` versus the same `≤1.1e-16`.

### Drivers, diagnostics and plots — not a stable API

`run_*.py`, `plot_*.py`, and `probe.py`. They write the bundles under
`results/experiments/modal_muller_20260916/`.

**Known accidental interface.** Three outside packages already import from this
group rather than from the library: `support_certificates/{independent,
cross_qualification}.py` and `laurent_calibration/model.py` import
`run_native.nodal`, and `laurent_neighbour/model.py` imports `probe.assemble`.
`probe.py` additionally depends on `experiments/bie002_modal_diagnostic/fixtures.py`,
which several `run_*` drivers also use as a shared fixture source. This is
recorded, not endorsed: **new consumers import library modules only.**

## Test coverage, and the one gap that matters

The 30 tests cover forward identities, analytic Mie, all Müller blocks against a
dense oracle, compiled-family reuse, cross translation, coupled derivatives
versus the differentiated operator and versus centered differences, complex
strengths, paired and full acquisition, adjoint identities, symmetry selection
rules, local-model quadratic error, cache reuse, and explicit failures when
boundary sampling or online reassembly is attempted.

**Gap.** `test_coefficients.test_flux_muller_all_blocks_against_dense_oracle`
checks the forward operator `A` **blockwise**. Nothing checks `D_v A`
blockwise — every derivative test validates the resulting *data* Jacobian
`D_v Y`, in which a per-block error can partially cancel. That is sufficient for
everything measured so far, and insufficient for any successor that masks or
truncates `D_v A` entry by entry. Such a successor must add its own entrywise
`D_v A`-versus-finite-difference test in its own package.

## Standing physical limits

Lossless, equal (unit relative) permeability, scalar TMz, one interface per
component. The log quotient needs `Re(W/z₁) > 0`; the series bound is an L2
bound on the projected coefficient recurrence and **does not** certify the
finite coefficient window — refine `bandwidth` to assess that separately. The
Bessel power series cancels at high argument (good at 2.5 GHz, broken at 5 GHz
with 28 terms). Disjoint bounding circles, external sources and receivers, known
component count and identity, locally constrained initial guesses.
