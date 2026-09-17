# LAU-001 audit — API, scaling and sign map

Written at G0, before numerical execution. Every imported module is read-only.

## Reference assembler and block layout

`CoefficientGeometry.assemble(ko, ki, cutoff, terms)` is **the reference**. It
returns

```text
A = [[ I - K,  V ],
     [   -T ,  I + K' ]]
```

on the mode grid `m, n = -K_u ... +K_u`, state `(u_D_hat, q_hat)` with
`q = |z'| d_n u` (canonical flux, parameter-weighted, not an extra field).
Each nonidentity block is `kernel_matrix(P, S, K_u)`:

```text
block[m,n] = 2*pi*( S[m,-n] + sum_l L_l * P[m-l, l-n] ),   L_l = -1/|l|, L_0 = 0
```

The `2*pi` is inside `kernel_matrix`. `S` is indexed at `[m, -n]`, so the smooth
part is a two-variable polynomial coefficient lookup, not a convolution.

**Maue term.** `T = -m*n*V + kernel_matrix(P_nn, S_nn)`. `-m*n*V` is a mode-index
reweighting of `V`, not an independent kernel, so it inherits `V`'s own split:
`-m*n*V_log` with the log part, `-m*n*V_smooth` with the smooth part. Protecting
it separately while compressing the `(1,2)` occurrence of `V` would make the two
occurrences inconsistent.

## Three assemblers agree

`assemble` builds `K'` from `target_dot`; `ModalMomentFamily` and `ShapeOperator`
use `k[::-1,::-1].T`. Measured 2026-09-17, circle/ellipse/star at 0.5 and
1.25 GHz, `K_u=24, B=64, terms=28`, relative Frobenius:

| Pair | Worst |
|---|---:|
| `ModalMomentFamily` vs `assemble` | `8.5e-15` |
| `ShapeOperator.a` vs `assemble` | `1.1e-16` |

Carried forward as `test_algebra.test_three_assemblers_agree`.

## Split extraction

By linearity of `kernel_matrix`: `kernel_matrix(P, 0)` is the exact log-symbol
contribution, `kernel_matrix(0, S)` the smooth lookup. `adapters.forward_arguments`
reproduces the exact `(P, S)` arguments `ShapeOperator.__init__` uses, including
the `-2*source_dot` and `normal_dot` products. Reconstruction was verified to
`7.6e-17`-`1.2e-16` on every executed case and is asserted in the test suite.

## Derivative

`ShapeOperator.derivative(direction)` returns `D_v A` in the same block layout
with the identity dropped (`D_v I = 0` exactly). `adapters._derivative_arguments`
mirrors its `(P, S)` arguments so the same split applies.
`ShapeFields.derivative(dz)` supplies `D_v b` and `D_v C`; the tangent uses all
three, since holding `b` and `C` fixed differentiates a different model.

`adapters.masked_data_derivative` was checked against the qualified
`NativeShapeForward.jacobian` at full mask: `<1e-12` relative on all three
fixtures (`test_derivatives.test_data_derivative_matches_the_qualified_jacobian`).

## Geometry perturbation convention

`adapters.moved_geometry` uses `dataclasses.replace` and holds `center` and
`scale` **fixed**, so `dz` is a fixed physical displacement `scale*dz` at every
step and the `FixedAcquisition` cache stays valid. Re-normalising through
`LaurentGeometry.from_coefficients` would change `scale` and invalidate the
acquisition. Directions are RMS-normalised so a unit step gives RMS boundary
displacement `a_ref`; the normal component of each is recorded in `summary.json`.

## Projected-Nyström control

`modal.ModalSystem.from_nodal` applies the flux similarity
`S_q = diag(I, diag J)` via `state_scale` (`speeds * period / (2*pi)`), projects
with a **unitary** DFT (`norm='ortho'`), and reports the lifted residual
`||A*lift(x) - b|| / ||b||`. The unitary convention differs from the plan's
physical-coefficient `E P = I` convention; because RHS, receivers and state are
all transformed consistently inside that class, the receiver data and residual
are convention-independent and are what this experiment compares. The square
full-DFT control is checked at `N=128`, `K_u=63` (exactly `N` distinct modes, no
Nyquist double count). No assembled Nyström matrix is multiplied by a second
quadrature weight, and `S_q` is applied once.

`adapters.lift` is an independent reimplementation of the modal-to-nodal lift,
written so the package does not import a `run_*` driver.

## Difference from BIE-002

BIE-002 projected an **assembled Nyström** matrix into Fourier coordinates,
protected only the identity, tested fixed centered bands, and built directional
references by finite differences. LAU-001 compresses the **independently
constructed node-free** operator, protects a **verified analytic log-symbol
split**, adds adaptive forward and derivative-aware rules plus an
analytic-support arm, and builds every directional reference from the
**analytic** `D_v A`, using finite differences only as the check. BIE-002's
centered band is retained here as its negative control and reproduces its
original negative result.

## Read-only guarantee

`experiments/laurent_compression/adapters.py` is the only module importing
`modal_muller_research`, and imports library modules only (`coefficient_operator`,
`coefficient_derivative`, `coefficient_fields` via those, `modal`,
`scattering_library`) -- never `run_*`, `plot_*` or `probe`. No file under
`solvers/`, `experiments/modal_muller_research/` or any prior result bundle was
modified. Imported source hashes are recorded before and after in `manifest.json`.
