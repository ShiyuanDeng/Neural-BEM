# `gpr_bem_kress` periodic Nyström/Müller implementation

> **Status: experimental, direct-import implementation snapshot (2026-09-02).**
> This records the sibling solver package `solvers/gpr_bem_kress/`; it is not
> an acceptance record. The package is deliberately absent from the normal
> drivers and `solver_select.SOLVER_NAMES` while its independent block, field,
> and same-scene comparison evidence is established. The governing scope and gates
> remain in
> [`muller_blocks_implementation_guide.md`](muller_blocks_implementation_guide.md)
> and
> [`ordered_boundary_nystrom_plan.md`](ordered_boundary_nystrom_plan.md).

## Verdict

The clean integration seam is one shared solver that accepts an immutable
`PeriodicCurve2D`; it should not be one solver fork per SDF parameterization
method. Methods A, B, and C remain independent upstream geometry producers.
Their scripts or a comparison notebook may discretize each fitted curve at
the same even node counts and feed those frozen curves to this backend. This
keeps the two refinement questions separate:

```text
vary solver node count N on one frozen gamma  -> operator/quadrature error
vary grid resolution or fit bandwidth K      -> geometry representation error
```

The implementation is therefore a peer solver, `gpr_bem_kress`, rather than a
backend nested inside `gpr_bem_mod`. It owns a small package-local `Material`
value type, uses the same audited physics values through explicit scene
conversion, and does not import or alter the current IBIM, kdiff, reference,
adjoint, or inverse pipelines. It should remain direct-import only until the
acceptance ladder is complete.

## Architecture and ownership

```text
PeriodicParameterization2D / an SDF method A, B, or C
                    |
                    | discretize(even N)
                    v
             PeriodicCurve2D
                    |
                    v
       affine adapter to theta in [0, 2 pi)
                    |
                    v
       target/source geometric invariants
                    |
          +---------+----------+
          |                    |
          v                    v
 combined power-log      direct Hankel/Bessel
 near series             difference formulas
          |                    |
          +---------+----------+
                    v
 all-block A log(4 sin^2/2) + B split
                    |
          periodic Kress product weights
                    v
         Delta V, Delta K, Delta Kp, Delta T
                    |
                    v
  [ I-Delta K   Delta V  ] [u_D] = [u_inc,D]
  [-Delta T     I+Delta Kp] [u_N]   [u_inc,N]
                    |
            direct dense solve
                    v
 ExteriorReceiverOperator C = [D_out, -S_out]
                    |
                    v
                 u_sc = C q
```

The modules have deliberately narrow responsibilities:

| Location | Responsibility |
|---|---|
| `solvers/ordered_boundary/` | Solver-neutral continuous producers and immutable node geometry. |
| `solvers/periodic_kress/weights.py` | The universal product weights for the full canonical periodic logarithm; no geometry or Helmholtz knowledge. |
| `gpr_bem_kress/materials.py` | Package-local material values; avoids importing another solver merely for type identity. |
| `gpr_bem_kress/geometry.py` | Validate one `PeriodicCurve2D` and normalize only its parameter coordinate. |
| `gpr_bem_kress/_kernels.py` | Bare, combined exterior-minus-interior kernels and their `log(r)` coefficients. |
| `gpr_bem_kress/operators.py` | Closed diagonal limits, all-block Kress split, and fully weighted difference matrices. |
| `gpr_bem_kress/conventions.py` | Human- and machine-readable convention record. |
| `gpr_bem_kress/system.py` | Compose the visible four blocks and optionally estimate `cond(A)`. |
| `gpr_bem_kress/forward.py` | Incident traces, explicit receiver operator, direct multi-right-hand-side solve, and separated exterior evaluation. |

The guide preferred reuse of existing kernels where suitable. Directly
importing the current implementations was not a clean seam:

- the live `gpr_bem_mod` builders own implicit-band/compressed-cloud geometry,
  finite stand-off traces, and their weight convention;
- `gpr_bem_kdiff` is a frozen compressed-cloud experiment whose local
  diagonal construction and optional SDF curvature do not apply to an ordered
  curve, and it lacks a cancellation-safe near series;
- `nystrom_ref` must remain an independent oracle rather than a production
  dependency.

The Kress solver consequently keeps a small combined-kernel primitive. Its far
branch is the same audited Hankel-difference algebra as kdiff, while its near
branch and closed periodic diagonals are specific missing primitives. It does
not import numerical code from `nystrom_ref`, `gpr_bem_qbx`, or
`gpr_bem_kdiff`.

## Frozen convention package

The code-level record is `PROJECT_MULLER_CONVENTION` in
`gpr_bem_kress/conventions.py`. The following meanings must stay together;
changing one sign in isolation creates a different system.

### Green function, time convention, and material scope

The fundamental solution is

\[
G_k(x,y)=\frac{i}{4}H_0^{(1)}(k|x-y|).
\]

The waveform transform in `gpr_bem_mod/waveforms.py` declares synthesis with
`exp(-i omega t)`, and the outgoing spatial kernel is `H_0^(1)`. The solver
records that convention and obtains

\[
k=\omega\sqrt{\mu_0\mu_r
  \left(\epsilon_0\epsilon_r-i\sigma/\omega\right)}
\]

from its package-local `gpr_bem_kress.Material`. That value type intentionally
mirrors the other solver siblings but does not import one of them. A shared
scene owns the physical scalar values and constructs the corresponding
package-local material objects at each solver boundary.

There is an unresolved repository-wide lossy-medium caveat: the
`-i sigma/omega` material sign is normally paired with the opposite temporal
phasor from the declared `exp(-i omega t)` convention. The canonical current
cases use `sigma=0`. The high-level material API therefore rejects nonzero
conductivity until the sign/branch choice is reconciled and a passive lossy
reference test passes. The lower-level explicit-wavenumber API and its complex
kernel tests establish numerical support only; they do not establish a
physically validated lossy pipeline.

The high-level material builder rejects `mur != 1` and `sigma != 0`. Thus the supported
unknown `u_N` is the ordinary outward normal derivative and no permeability
prefactors multiply the four blocks. Permittivity contrast enters through the
two wavenumbers. Supporting magnetic contrast requires a fresh scaled-flux
derivation, not removal of the guard. The lower-level
`build_muller_system(curve, k_exterior, k_interior)` accepts already-resolved
wavenumbers and intentionally bypasses material interpretation.

### Geometry, operators, and jumps

The component is counterclockwise. A single unit normal

\[
n=(\tau_y,-\tau_x)
\]

points from the inclusion into the exterior and is used for both media. With
that normal,

\[
\begin{aligned}
V_k\phi(x)&=\int_\Gamma G_k(x,y)\phi(y)\,ds_y,\\
K_k\phi(x)&=\operatorname{p.v.}\int_\Gamma
  \partial_{n_y}G_k(x,y)\phi(y)\,ds_y,\\
K'_k\phi(x)&=\operatorname{p.v.}\int_\Gamma
  \partial_{n_x}G_k(x,y)\phi(y)\,ds_y,\\
T_k\phi(x)&=\operatorname{f.p.}\int_\Gamma
  \partial_{n_x}\partial_{n_y}G_k(x,y)\phi(y)\,ds_y.
\end{aligned}
\]

`K` therefore uses the source normal and `Kp` the target normal. These names
mean principal operators only; none includes a trace jump. For limits taken
from the exterior (`+`) and inclusion interior (`-`), respectively,

\[
\gamma_D^+D=K+\tfrac12I,\qquad
\gamma_D^-D=K-\tfrac12I,
\]

\[
\gamma_N^+S=K'-\tfrac12I,\qquad
\gamma_N^-S=K'+\tfrac12I.
\]

`V` and `T` have the corresponding continuous trace used in the derivation.

The unknown vector contains unweighted total traces in the order

\[
q=[u_D,u_N]^T.
\]

For an exterior line source, the right-hand side contains the **positive**
incident Dirichlet and outward-normal traces. For source point `s`, boundary
point `x`, and complex strength `alpha`, these are

\[
u_D^{inc}(x)=\alpha\frac{i}{4}H_0^{(1)}(k_o|x-s|),
\]

\[
u_N^{inc}(x)=-\alpha\frac{i k_o}{4}H_1^{(1)}(k_o|x-s|)
\frac{(x-s)\cdot n_x}{|x-s|}.
\]

The exterior scattered field is

\[
u^{sc}=D_o u_D-S_o u_N,
\qquad u^{tot}=u^{inc}+u^{sc}.
\]

Consequently, at a separated receiver `z`, the implemented quadrature is

\[
u^{sc}(z)\approx\sum_j w_j\left[
\frac{i k_o}{4}H_1^{(1)}(k_o|z-y_j|)
\frac{(z-y_j)\cdot n_j}{|z-y_j|}(u_D)_j
-\frac{i}{4}H_0^{(1)}(k_o|z-y_j|)(u_N)_j
\right].
\]

### Exact sign translation

Let `Delta X = X_out - X_in`. Applying the jumps above to the exterior
scattered representation and the interior Green representation, then adding
the two equations, gives the Dirichlet pair

\[
(\tfrac12I-K_o)u_D+V_o u_N=u_D^{inc},
\qquad
(\tfrac12I+K_i)u_D-V_i u_N=0,
\]

and the Neumann pair

\[
-T_o u_D+(\tfrac12I+K'_o)u_N=u_N^{inc},
\qquad
T_i u_D+(\tfrac12I-K'_i)u_N=0.
\]

Their sums give

\[
\boxed{
A=
\begin{bmatrix}
I-\Delta K & \Delta V\\
-\Delta T & I+\Delta K'
\end{bmatrix}.}
\]

This lower-left sign is important. The displayed target in section 3.1 of the
implementation guide uses `+Delta T`, but that symbol was explicitly subject
to translation through repository definitions. Under the `T` definition
above, the accepted repository system uses **`-Delta T`**. In the older
`gpr_bem_mod` vocabulary the stored hypersingular operator is `W=-T`, so the
same lower-left block is **`+Delta W`**. Those are equivalent statements, not
two competing formulations. The identity appears exactly once in `A11` and
`A22`; the four difference matrices contain no hidden jump.

## `PeriodicCurve2D` contract

The solver accepts one `ordered_boundary.PeriodicCurve2D`, not an SDF,
marching polygon, fit object, or callable evaluator. The input object owns:

- a stable `component_id` and provenance;
- a canonical, endpoint-free, uniform native parameter grid;
- read-only points, first and second derivatives, and optional third
  derivatives;
- positive speeds, tangents, outward normals, curvatures, and ordinary
  arc-length weights derived from those node jets; and
- positive signed area, hence counterclockwise orientation.

The adapter additionally requires at least eight nodes, an even node count,
finite positive speed, consistent `ds` weights, and no intersections in the
sampled closed node polygon. It preserves node order, cyclic phase, points,
normals, and physical weights. If the native period is `P` with origin `t0`,
it changes coordinates only:

\[
\theta=\frac{2\pi(t-t_0)}{P},\qquad
\gamma_\theta=\frac{P}{2\pi}\gamma_t,
\qquad \theta_j=\frac{2\pi j}{N}.
\]

No hidden off-node evaluator exists in the adapter. This is intentional: all
self limits used below are analytic curve-local limits, so changing `N`
requires the caller to discretize its continuous producer again rather than
letting the solver invent a second geometry.

Each assembled difference matrix already contains its source Jacobian and
parameter quadrature factor exactly once. Unknowns are plain nodal values and
the action is simply `block @ density`. Multiplying again by
`curve.arc_length_weights` is an error.

## Cancellation-safe kernels

For a target-source pair define

\[
d=x-y,\quad r=|d|,\quad
a=d\cdot n_x,\quad b=d\cdot n_y,\quad c=n_x\cdot n_y,
\]

and `g(r)=G_ko(r)-G_ki(r)`. If `p=g'(r)/r` and
`q=g''(r)-g'(r)/r`, the bare difference kernels evaluated together are

\[
\Delta V=g,\qquad
\Delta K=-p b,\qquad
\Delta K'=p a,\qquad
\Delta T=-p c-q\frac{ab}{r^2}.
\]

For

\[
\max(|k_o|,|k_i|)r \leq \eta,
\]

the default `eta=0.75` branch represents `g` as

\[
g(r)=\sum_{m=0}^{M-1}r^{2m}
\left(P_m\log r+Q_m\right),\qquad M=24\ \text{by default},
\]

and differentiates the same series analytically for `p` and `q`. Crucially,
the exterior and interior coefficients are combined before evaluating the
series; no two `O(r^-2)` hypersingular values are formed and subtracted.

Beyond the switch, the code uses direct differences of `H0`, `k H1`, and
`k^2 H2`. Replacing the Hankel terms by Bessel `J` terms with the matching
prefactor provides the coefficient of `log(r)` for the Kress split. Equal
wavenumbers are handled as an exact zero-difference path. When node pairs
exist in the band `[0.5 eta, 1.5 eta]`, diagnostics evaluate both branches
there and report a mixed relative discrepancy for every block. An empty
overlap set on a coarse grid is reported as zero pairs, not interpreted as a
successful overlap test.

`MullerAssemblyConfig` exposes the switch, series length, overlap toggle,
maximum sampled overlap-pair count, and target-row chunk size. Chunking avoids
retaining all temporary kernel/coefficient arrays at once; the four completed
dense matrices are still materialized.

## All-block Kress split and diagonals

The reusable Kress package uses the **full** canonical logarithm

\[
L(\theta-s)=\log\left(4\sin^2\frac{\theta-s}{2}\right)
\]

on an even, endpoint-free `2 pi` grid, including the special Nyquist term.
If `C_X(theta,s)` is the coefficient of `log(r)` in a bare physical
difference kernel and `v(s)=|gamma_theta'(s)|`, the operator builder uses

\[
A_X(\theta,s)=\tfrac12 C_X(\theta,s)v(s),
\]

\[
B_X(\theta,s)=\Delta X(\theta,s)v(s)-A_X(\theta,s)L(\theta-s).
\]

Thus the dense matrix is

\[
(\Delta X)_N[i,j]=R_{i-j}A_X(\theta_i,\theta_j)
  +h B_X(\theta_i,\theta_j),\qquad h=2\pi/N,
\]

where `R` integrates the full `L`. This split is applied coherently to
`Delta V`, `Delta K`, `Delta Kp`, and `Delta T`, including the weaker
off-diagonal power-log terms whose diagonal coefficient vanishes.

No singular function is called at `i == j`, and no Richardson/off-node
extrapolation is used. With

\[
\delta=k_o^2-k_i^2,\qquad c_\delta=-\frac{\delta}{4\pi},
\qquad v=|\gamma_\theta'|,
\]

the implemented diagonal values of the parameterized split are:

| Block | `A_X(theta,theta)` | `B_X(theta,theta)` |
|---|---:|---:|
| `Delta V` | `0` | `v (log(k_i)-log(k_o))/(2 pi)` |
| `Delta K` | `0` | `0` |
| `Delta Kp` | `0` | `0` |
| `Delta T` | `c_delta v / 2` | `v (C_T + c_delta log(v))` |

Here

\[
C_T=\frac{i\delta}{8}-\frac{
\delta(\gamma_E-\tfrac12-\log 2)
+k_o^2\log k_o-k_i^2\log k_i}{4\pi},
\]

using the complex logarithm consistently with the kernel branch. At zero
contrast, all coefficients, remainders, and completed matrices are exactly
zero. The `Delta V` expression deliberately subtracts the two principal
logarithms instead of taking `log(k_i/k_o)`: those expressions can differ by
`2 pi i` across the complex-log branch cut.

## System and forward API

The direct-import surface is:

- `build_muller_difference_blocks(curve, k_exterior, k_interior, ...)`;
- `build_muller_system(curve, k_exterior, k_interior, ...)`;
- `build_kress_tmz_frequency_system(curve, omega, exterior=..., interior=...,
  ...)`;
- `build_exterior_receiver_operator(curve, receiver_points, k_exterior, ...)`;
- `solve_kress_tmz_total_field_batch(...)`; and
- `solve_kress_tmz_frequency_response(...)`.

The public records use solver-specific names: `KressSolveConfig`,
`KressTMzFrequencySystem`, `KressTMzForwardResult`, and
`KressTMzMultiFrequencyForwardResult`. `gpr_bem_kress.Material` is a small
package-local value type. Comparison orchestration constructs equivalent MOD
and Kress material values from one scene specification; neither solver imports
the other for class identity or physics helpers.

The system is dense `complex128` NumPy and is solved as `A q = b`, never by
squaring `A` or forming normal equations. Multiple sources are columns of one
right-hand-side solve. Receiver arrays retain the full source-by-receiver
cross product; the multifrequency result has source, frequency, and receiver
axes.

Sources and receivers must be outside the sampled polygon and farther from its
line segments than a configurable multiple of the largest `ds` weight.
Receiver evaluation uses ordinary periodic trapezoidal quadrature because this
phase supports safely separated receivers only. `ExteriorReceiverOperator`
retains the fully weighted single- and double-layer rows and the explicit
state matrix

```text
C = [D, -S],       q = [u_D, u_N]^T,       u_sc = C q.
```

The forward path applies those stored rows rather than rebuilding an implicit
receiver convention. This is also the clean seam for a future discrete
adjoint. For a full receiver-array dual `Psi`, solve
`A^H lambda = C^H Psi` using the literal conjugate transposes of the matrices
accepted by the forward solve. An ACC pair vector is different: if `P` selects
the source/receiver diagonal, then `y=P(Cq+u_inc)` and the reverse path is
`Psi=P^H psi`, where `P^H` scatters the pair dual onto that diagonal. Passing a
24-vector directly to `apply_adjoint` means one RHS, not 24 paired RHSs. A
future typed measurement/adjoint context must own and validate `P/P^H`. The
solver does not yet implement a shape derivative or an adjoint pipeline.

Immutable result objects retain the four difference blocks and four matrix
views separately, resolved wavenumbers, right-hand side, solved state, traces,
the receiver operator, separated single- and double-layer contributions,
incident/scattered/total fields, and timings. Geometry is referenced rather
than mutated. Multiple sources are columns of `q`; receiver fields retain an
explicit `(source, receiver)` cross product. Pairing for an ACC scan is an
orchestration concern, not a hidden solver convention.

The accepted forward snapshot retains the typed solve and assembly configs,
material values, constants, `A`, `b`, `q`, and `C`. A future geometry tangent
must still be defined as a coupled fixed-grid direction for `gamma` and its
parameter derivatives, with `N`, ordering, phase, period, and origin frozen.
Normals, speed, and weights must be differentiated from that direction rather
than held fixed. Near/direct kernel branch decisions also need to be frozen or
tested across their overlap before tight derivative finite differences are
used as evidence.

## Diagnostics and metrics

The implementation currently exposes:

- a content-derived geometry identifier, node count, orientation, and normal
  convention;
- the Kress-log normalization and explicit source-Jacobian/parameter-step
  ownership;
- analytic diagonal and combined near-series strategy names;
- near/direct pair counts and optional series/direct overlap errors by block;
- infinity norms of all four difference blocks;
- target-row chunk size plus pair-geometry, shared-kernel, per-block, and
  overlap-diagnostic assembly timings;
- convention record, unknown ordering, matrix formula, and jump ownership;
- optional `cond(A)`;
- aggregate and per-source ordinary linear residuals;
- incident exterior-representation leak;
- minimum reported source/receiver distance; and
- block/system assembly, solve, receiver-evaluation, and total wall times.

The checked validation runner adds independent circle Fourier-mode block-action
errors, total-trace errors, absolute and scaled receiver errors against Mie or
`nystrom_ref`, adjacent-`N` convergence ratios, exact retained dense-core
storage, and separated runtimes. Explicit exterior/interior transmission
residuals, noncircular reference block actions, process peak memory, and
reference-solver self-convergence remain promotion evidence rather than
implemented result columns. Geometry SDF residuals, normal error, Fourier
coefficient tail, and the earlier scalar Kress-proxy error remain upstream
geometry/product-rule metrics; they are not substitutes for PDE errors.

No single score or visual comparison selects a winner. Exact curves should be
tested first. For SDF methods, freeze each fitted `gamma` while increasing
`N`, then vary extraction grid and bandwidth separately.

### Validation snapshot: 2026-09-02

The solver-owned fast tests are documented in
[`pytest/gpr_bem_kress/README.md`](../pytest/gpr_bem_kress/README.md). They
cover isolation/API contracts, canonical Kress modes and the Nyquist term,
near/direct overlap and small-separation stability, independent analytic
circle actions for all four difference blocks, exact system signs, a
manufactured modal solve, zero contrast, analytic boundary traces, and
penetrable-cylinder Mie receiver fields at 0.5, 2.5, and 8 GHz (`N=128` at
8 GHz). These are genuine operator/solve/field checks, unlike the upstream
geometry and scalar Kress-proxy metrics.

The current peer-package regression command

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  pytest/gpr_bem_kress
```

reported `41 passed in 0.34s` (`1.57s` process wall time) after the sibling
move, derived receiver matrix, and explicit receiver-operator addition. The
earlier pre-move `/usr/bin/time` snapshot reported
`38 passed in 0.27s`, `wall=1.60`, and `maxrss_kb=655712`; that RSS is the
high-water mark of the entire Python test process, not isolated solver memory.

The compact persisted evidence is indexed at
[`results/ordered_boundary_nystrom/README.md`](../results/ordered_boundary_nystrom/README.md).
The exact circle/ellipse/star run contains 27 rows over
`N={64,128,256}` and 0.5, 2.5, and 8 GHz; all nine configured largest-`N`
smoke checks pass. Its worst `N=256` receiver/trace errors are `1.22e-8` and
`1.11e-8`, respectively. The separate frozen Method-B run uses the accepted
finest-input circle `K=4` and ellipse/star `K=32` curves, holds each continuous
curve fixed while varying `N={128,256}`, and also passes all nine configured
checks. Its worst `N=256` receiver/trace errors are `4.79e-9` and `3.56e-9`.
At `N=256`, retained four-block-plus-system storage is exactly 8 MiB; the
slowest timed analytic Kress cell, including a separate raw condition
estimate, is about 325 ms on the recorded single-thread environment.

These are genuine solver errors and useful convergence evidence, but not a
Phase-4 closeout. The checked runs use three of the six declared frequencies;
the noncircular oracle is frozen at `N=512` without a stored oracle
self-convergence ladder; and explicit transmission residuals, lossy physics,
grid/bandwidth convergence through the solver, full-ring FDTD evidence, and
normal pipeline wiring remain open. The fixed-resolution same-SDF MOD/Kress
comparison is recorded separately in
[`results/solver_comparisons/kress-peer-20260902/summary.md`](../results/solver_comparisons/kress-peer-20260902/summary.md).
That comparison's acceptance helper gates receiver L2 and superiority to MOD
at all six reported frequencies, rather than enforcing only the original
0.5/1.5/2.5 GHz subset. The machine-readable export uses strict JSON (`null`
for unavailable metrics) and records the actual receiver work per solver:
MOD/Kress materialize `24 x 24`, whereas the retained kdiff implementation
contracts the 24 paired receiver fields directly.

## Scope, known hazards, and promotion gates

Implemented scope:

- one smooth, simple, counterclockwise component;
- homogeneous, lossless, nonmagnetic exterior and inclusion;
- line sources and safely separated exterior receivers;
- dense CPU assembly and direct solve; and
- direct, explicit imports only.

Deliberately absent:

- multicomponent and near-touching blocks;
- close receiver evaluation;
- a material-region graph or magnetic/scaled-flux transmission;
- corners and open boundaries;
- GPU/FMM acceleration;
- differentiation through geometry, assembly, or solve;
- shape differentiation and adjoint/inverse integration; and
- normal-driver or solver-selector wiring.

Known implementation hazards to keep visible during validation:

- simplicity is checked on the sampled node polygon, not certified for the
  continuous curve;
- topology checking remains `O(N^2)` in work, although it is row-chunked to
  avoid an `N x N` peak allocation;
- exterior/clearance checks use the sampled polygon segments rather than the
  unknown continuous curve, so they remain a guard for clearly separated
  points rather than a close-evaluation certificate;
- the overlap diagnostic can have no eligible pairs at coarse `N`; its bounded
  deterministic sample is spread across target chunks but is not exhaustive;
- increasing `target_chunk_size` increases temporary memory even though the
  default remains 64;
- dense matrices cost `O(N^2)` memory, while a direct solve and condition
  estimate cost `O(N^3)`; condition estimation is therefore opt-in;
- the reported raw 2-norm condition number mixes Dirichlet and Neumann units,
  changes under length-unit rescaling, and is diagnostic rather than a fair
  cross-geometry score;
- the package-local `Material` mirrors the current solver-sibling convention;
  a future shared scene layer must convert material values explicitly rather
  than pass one solver's class into another;
- the receiver operator makes the discrete `C^H` seam explicit, but no
  factorization reuse, derivative of `A`, derivative of the incident trace, or
  derivative of `C` exists yet; and
- the lossy material-sign issue above remains unresolved.

Before promotion, retain independent evidence for near/direct overlap, every
circle Fourier-mode block action, manufactured transmission, zero contrast,
Mie receiver fields across frequency, noncircular exact curves, and frozen
Method-B SDF curves. Report assembly, condition-estimation, solve, and receiver
costs separately. The first same-SDF comparisons now run in the existing smooth
circle, ellipse, and star ACC scenes: one immutable scene feeds independent MOD
compression and Method-B-to-`PeriodicCurve2D` extraction before receiver errors
are compared. Current gprMax caches cover only the index-0 Tx/Rx pair,
so their table value is a one-pair relative error at each frequency, not a
24-pair spatial L2. Square and two-component scenes remain outside this
solver's geometry contract.

Only after those gates pass should this package be registered as a normal
solver choice or considered for an adjoint/inverse path. Direct import as
`gpr_bem_kress` does not by itself promote it into the operational pipeline.
