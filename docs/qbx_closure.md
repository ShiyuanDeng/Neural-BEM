# QBX/kdiff investigation closure

Status: **closed decision record for the current compressed-IBIM boundary representation**

Date: 2026-09-01

Current pipeline: [`current_architecture.md`](current_architecture.md). Living
next-step checklist:
[`ordered_boundary_nystrom_plan.md`](ordered_boundary_nystrom_plan.md).

## Decision

Stop tuning QBX on the current compressed boundary cloud. Retain full-row QBX
as an explicit research diagnostic and retain the `gpr_bem_kdiff` `TAssembler`
seam, but do not promote either QBX source strategy as the production forward
solver. Freeze `gpr_bem_kdiff` as a fast compressed-cloud experimental
baseline rather than continuing local diagonal or near-neighbour tuning.

The next forward-solver effort is an ordered, component-aware boundary
representation followed by a coherent Kress/Nyström discretization. QBX may be
reconsidered only after that representation exists and QBX demonstrates a
specific advantage over Kress on the same geometry.

This is **not** a conclusion that QBX is mathematically wrong. Ideal
ordered-geometry controls validate the implemented QBX `T` construction
strongly. The negative result is architectural: on the current compressed
IBIM targets, the tested same-node and oversampled source bridges do not give
an admissible, consistently accurate, cost-effective forward method.

## Executive evidence

The defensible closeout statement is:

> On the measured six-frequency/five-shape workload, every QBX realization is
> substantially slower than both `gpr_bem_mod` and `gpr_bem_kdiff`.
> Same-node QBX is consistently less accurate than `gpr_bem_mod`.
> Oversampled QBX has isolated accuracy wins, but no configuration gives a
> geometry-robust, clearance-valid improvement. Further radius, order,
> oversampling, or IDW tuning on the compressed cloud is therefore not
> justified.

It would be inaccurate to shorten this to “QBX is less accurate in every
cell.” The stored Fourier-source row reports lower errors in parts of the
circle and two-circle cases, and raw-SDF QBX has a few modest wins. Those rows
still use compressed targets, and their nonzero invalid-clearance counts make
them inadmissible as convergence evidence. They show promising numerical
values in selected cases, not a validated production method.

## Measured runtime

Each number below is one measured complete sweep over six frequencies. Every
BEM row covers the full 24-pair ring. Timings are summed across the five stored
shape runs in
`results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md`.

| Method | Five-shape total | Relative to `mod` | Relative to `kdiff` |
|---|---:|---:|---:|
| `gpr_bem_mod` | 13.48 s | 1.0x | 3.4x |
| `gpr_bem_kdiff` | 3.98 s | 0.30x | 1.0x |
| same-node full-row QBX | 118.31 s | 8.8x | 29.7x |
| Fourier-source QBX | 214.25 s | 15.9x | 53.8x |
| raw-SDF-source QBX | 1151.11 s | 85.4x | 289.2x |

Per-shape measured ranges were:

| Method | Minimum | Maximum |
|---|---:|---:|
| `gpr_bem_mod` | 1.50 s | 4.32 s |
| `gpr_bem_kdiff` | 0.47 s | 1.41 s |
| same-node full-row QBX | 15.15 s | 34.81 s |
| Fourier-source QBX | 18.54 s | 66.60 s |
| raw-SDF-source QBX | 108.71 s | 572.63 s |

These are measurements of the present dense diagnostic implementations, not
an asymptotic QBX benchmark. They have no repetitions, error bars, or
hardware/thread normalization. They are sufficient for the local engineering
decision: the tested QBX implementations do not buy a dependable accuracy
gain that could justify their measured cost. They must not be compared to the
single-pair gprMax timings without accounting for different work coverage.

Source: [`results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md`](../results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md).
This dated bundle contains the physical solver-field errors used for this
decision; the separate SDF-boundary geometry and scalar-proxy metrics do not.

## Measured field accuracy

The cells below are relative scattered-field errors at `2.5 / 8.0 GHz`.
Circle uses the analytic Mie series, ellipse and star use the independent
N=512 Nyström oracle, and square and two-circle use the available
representative gprMax pair. The latter two therefore provide weaker ranking
evidence than circle, ellipse, and star.

| Shape | `mod` | `kdiff` | QBX 1x | QBX Fourier 8x | QBX raw-SDF 8x grid |
|---|---:|---:|---:|---:|---:|
| Circle | 0.0342 / 1.7981 | 0.0128 / 1.7235 | 0.1776 / 12.4023 | 0.0030 / 1.3669 | 0.0178 / 2.5959 |
| Ellipse | 0.0529 / 0.9050 | 0.0573 / 0.6045 | 0.1812 / 2.1016 | 6.2554 / 9.9403 | 0.0890 / 0.5400 |
| Square | 0.0195 / 0.3875 | 4.4554 / 24.9875 | 3.7205 / 16.0044 | 3.8141 / 17.9050 | 4.1944 / 17.9769 |
| Star | 0.0358 / 0.7484 | 0.0733 / 0.7589 | 0.2498 / 1.3350 | 0.7181 / 10.0311 | 0.0792 / 0.7047 |
| Two circle | 0.0691 / 0.2928 | 0.0278 / 0.6233 | 0.1193 / 2.2075 | 0.0221 / 0.3599 | 0.0258 / 1.4094 |

The full six-frequency tables are the authoritative record. Their important
features are:

- Same-node full-row QBX is worse than `gpr_bem_mod` at every reported
  shape/frequency cell. On the parameterized circle control it is also
  underresolved: the T-action error is `1.438e-1`.
- Fourier 8x QBX reports low errors on the circle at low/mid frequency and is
  competitive on parts of the two-circle case, but both rows have invalid
  clearance and remain diagnostic. It is catastrophic on the ellipse and
  star, reaching relative errors of `20.0085` at ellipse 4 GHz and `10.0311`
  at star 8 GHz.
- Raw-SDF QBX gives isolated modest improvements, including ellipse 8 GHz
  (`0.5400` versus kdiff's `0.6045`) and star 8 GHz (`0.7047` versus mod's
  `0.7484`). It is not uniformly better and requires roughly 33--80 source
  points per target in these runs.
- The small linear residuals, normally around `1e-14` and at worst `5e-12`,
  prove that the discrete systems were solved accurately. They do not prove
  that the discretized operators or fields are accurate.

Sources: the [circle](../results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md#circle),
[ellipse](../results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md#ellipse),
[square](../results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md#square),
[star](../results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md#star), and
[two-circle](../results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md#two-circle) tables.

## QBX admissibility and transfer diagnostics

The cells below are `actual source ratio / invalid-clearance pairs / Fourier
collocation condition`. A dash means that the source strategy does not use a
Fourier transfer matrix.

| Shape | QBX 1x | QBX Fourier 8x | QBX raw-SDF 8x grid |
|---|---:|---:|---:|
| Circle | 1 / 0 / -- | 8 / 140 / 2.21e2 | 39.95 / 628 / -- |
| Ellipse | 1 / 0 / -- | 8 / 210 / 1.78e6 | 56.12 / 1,484 / -- |
| Square | 1 / 8 / -- | 8 / 100 / 3.39 | 50.71 / 620 / -- |
| Star | 1 / 0 / -- | 8 / 324 / 3.09e4 | 32.91 / 1,244 / -- |
| Two circle | 1 / 0 / -- | 8 / 230 / 2.43e2 | 79.75 / 2,208 / -- |

Every oversampled production-boundary row contains invalid
expansion/source pairs. Ellipse and star also have poorly conditioned
nonuniform Fourier transfer. Finite matrices and fields from those rows are
diagnostics, not evidence of an admissible convergent QBX method.

The raw values and per-frequency `TAssemblyReport` objects are retained in:

- [`circle/metrics.json`](../results/solver_comparisons/legacy/qbx-closeout-20260901/circle/metrics.json)
- [`ellipse/metrics.json`](../results/solver_comparisons/legacy/qbx-closeout-20260901/ellipse/metrics.json)
- [`square/metrics.json`](../results/solver_comparisons/legacy/qbx-closeout-20260901/square/metrics.json)
- [`star/metrics.json`](../results/solver_comparisons/legacy/qbx-closeout-20260901/star/metrics.json)
- [`two_circle/metrics.json`](../results/solver_comparisons/legacy/qbx-closeout-20260901/two_circle/metrics.json)

## What QBX did validate

The mathematical and wiring controls passed:

1. The legacy near-band QBX row formula agrees with the closed-form separated
   kernels to about `1e-13` on the tested well-separated pair.
2. At the tested node counts, radius, and expansion order, the 1x full-row
   T-QBX control was underresolved. On ordered analytic curves, increasing to
   8x sources at expansion order 16 reduced T-action errors over 0.5--2.5 GHz
   to approximately `1e-9` on circle/ellipse and `1e-7` on star.
3. A hybrid structured diagnostic using Nyström S/D/K' blocks, ordered target
   geometry, Fourier density transfer, and full-row QBX T reached field errors
   from `5.22e-11` to `2.21e-7` on circle, ellipse, and star.
4. The focused contract tests show that default kdiff equals explicit
   `LegacyLocalT`, a QBX strategy changes only T, disconnected component
   transfers remain separated, and only the lower-left Müller system quadrant
   changes.

These controls rule out a basic Graf expansion, derivative sign, Müller sign,
or `TAssembler` wiring error. They validate QBX T on smooth ordered geometry;
they do not validate a complete all-QBX solver or the compressed-cloud bridge.
They cover only 0.5--2.5 GHz in the ideal structured solve, not the full
4--8 GHz production range or exact corners.

The recorded N=64 five-density circle diagnostic reports a maximum T-action
error of `3.94e-9`. The current executable regression is intentionally weaker:
N=32, one cosine density, and a `<1e-6` gate. Treat the stronger number as
recorded diagnostic evidence until the executable test is expanded to match.

Source: [`validation_change_log.md`](validation_change_log.md), especially
“Source oversampling fixes the T operator” and “Parameterized diagnostic solve
with oversampled T-QBX.”

## Why source-side fixes are no longer the next step

The “perfect boundary knowledge” experiment retained the compressed targets
and their S/D/K' blocks, but replaced raw/IDW sources with exact analytic
sources plus one ordered periodic-spline density-transfer construction.
Ellipse still plateaued near `5.35e-3`, worse than kdiff's `4.32e-3`, while
star plateaued near `7.27e-3`. No gross clearance violation was reported, but
strict admissibility was not established beyond equality/tolerance-level
pairs.

Consequently, raw source count and the original IDW transfer are not the whole
explanation. The remaining floor may involve one or more of:

- compressed-target geometry and weights;
- the unchanged direct S/D/K' quadrature on that cloud; and
- a curvature-sensitive QBX target error in T; or
- residual error in the tested periodic-spline transfer.

That is enough to stop source-only tuning. It is not enough to claim that any
one target-side or transfer mechanism has been proved solely responsible.

## Architectural reading

The compressed boundary stores points, normals, weights, and merge metadata.
Weighted bin merging does not retain the solver-grade structure needed for
high-order singular quadrature:

- ordered, oriented closed components;
- stable component identity and cyclic phase;
- arclength or periodic curve parameters;
- mutually consistent tangents, normals, curvature, and weights;
- off-node curve evaluation and high-order panel/curve geometry;
- stable component-local density transfer; and
- explicit corner classification.

Reconstructing all of that only to support QBX also constructs most of what
Kress/Nyström needs. Kress is already validated in the independent
`nystrom_ref` oracle and discretizes all four Müller blocks coherently, whereas
the current QBX strategy replaces only T and leaves S/D/K' on the compressed
target cloud.

## Retained code and status

Retain:

- `solvers/gpr_bem_kdiff/t_assembly.py` as the isolated experimental `dT`
  strategy contract;
- `LegacyLocalT` and exact default-parity tests as the frozen kdiff baseline;
- `solvers/gpr_bem_qbx/full_row_t.py` as the full-row QBX diagnostic;
- same-node, parameterized/component-Fourier, and raw-SDF/IDW source modes as
  named controls, not defaults;
- `TAssemblyReport` source-count, transfer, conditioning, clearance, and
  timing diagnostics;
- `scratchpad/legacy/qbx/qbx_diagonal_probe.py`,
  `scratchpad/legacy/qbx/qbx_legacy_near_band.py`, and the measured
  negative-result data;
- `gpr_bem_mod` as the current inverse/adjoint-capable operational baseline;
  and
- `nystrom_ref` as an independent forward oracle.

Do not restore a duplicated QBX solver stack, expose QBX through the normal
solver selector, or describe any stored QBX row as a validated production
solver.

Ordinary shape comparisons omit QBX. Reproduce the stored rows only with
`--include-qbx-archive`; those constructors explicitly set
`allow_invalid_clearance=True`. `FullRowQBX` otherwise rejects invalid
clearance before assembling the matrix. The opt-in records a negative result;
it does not waive QBX admissibility.

## Next path: ordered SDF boundary to Kress/Nyström

This section records the handoff rationale at closure. The living sequence,
scope, and acceptance gates are maintained only in
[`ordered_boundary_nystrom_plan.md`](ordered_boundary_nystrom_plan.md).

The next production candidate is:

```text
neural SDF
  -> ordered zero-level components
  -> projection back to phi=0
  -> smooth periodic curve per component
  -> consistent points/tangents/normals/curvature/weights
  -> component-wise Kress/Nyström Müller assembly
```

This keeps the SDF as the geometry and optimization variable. It replaces the
boundary discretization consumed by the high-accuracy forward solver.

The repository already has the beginning of this path in
`solvers/gpr_bem_mod/neural_sdf.py`: marching-squares extraction of ordered
multi-component contours, polygonal arclength resampling, and construction of
a multi-surface `BoundaryMesh2D`. `BoundaryMesh2D.from_closed_curves` already
preserves component connectivity. Promote those facilities instead of trying
to infer an ordering after cloud compression.

The marching-squares polygon is a topology carrier and fitting seed, not the
final Kress quadrature. For each smooth component, build one periodic evaluator
for `x(t)`, `x'(t)`, and `x''(t)` and derive points, speeds, tangents, outward
normals, curvature, and arc-length weights from it consistently. Use the SDF
gradient to project onto `phi=0` and validate orientation, not as an
independent source of solver normals.

Build the production candidate separately from `nystrom_ref`, which must stay
an independent oracle. Do not implement Kress as another `TAssembler`: Kress
must assemble S, D, K', and T consistently, with per-component log weights and
ordinary smooth quadrature for cross-component interactions.

The SDF inverse coupling can continue to freeze extraction/remeshing during
one forward/adjoint/backward step and use the existing shape-density surrogate
to update SDF parameters. There is no requirement to differentiate through
marching squares; re-extract after each outer update.

The initial Kress path is smooth-only. It must reject exact corners rather
than silently smoothing a square. Corners need a later piecewise-smooth panel
backend with corner endpoints, graded panels, one-sided normals, and suitable
product integration. Nested material regions likewise require a later
containment/material-adjacency model.

## Reopening criteria for QBX

Do not reopen QBX for another radius, expansion-order, oversampling-factor, or
IDW sweep. Reopen only after all of the following exist:

1. An ordered, oriented, component-aware boundary representation with stable
   parameters, tangents, normals, weights, and high-order curve/panel geometry.
2. Explicit handling of disconnected components and a separate policy for
   corners.
3. A stable, component-local transfer to oversampled sources.
4. Zero invalid QBX clearance pairs, enforced as an acceptance condition.
5. Monotone target and source refinement for T-action and full scattered
   fields on circle, ellipse, star, and a disconnected-component case.
6. Operator-action comparisons on several smooth density modes against the
   independent Nyström oracle.
7. A demonstrated accuracy, geometry, or complexity advantage over the
   Kress/Nyström implementation on the same ordered boundary.

## Scope limits

This decision covers the tested 2-D TMz homogeneous full-space transmission
problem and the current compressed-IBIM target grids. It does not establish a
general negative result about QBX on panelized or high-order boundaries.

The square is outside the smooth global-QBX/Kress assumptions and should not be
used as the primary evidence against smooth QBX. Two-circle currently has no
full-ring independent Nyström oracle and uses analytic component information
that a production extractor does not yet supply. The strongest closeout
evidence is therefore the Mie circle control, Nyström ellipse/star controls,
operator-action diagnostics, clearance reports, and the failure of exact
source-side reconstruction to remove the compressed-target plateau.
