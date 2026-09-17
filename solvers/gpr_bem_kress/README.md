# `gpr_bem_kress`

This is the ordered periodic Kress/Nyström Müller solver. It is a sibling of
`gpr_bem_mod`, not a MOD backend.

Its geometry boundary is deliberately narrow:

```text
PeriodicCurve2D
  -> cancellation-safe Delta V/K/Kp/T assembly
  -> direct unsquared Muller solve
  -> explicit exterior receiver operator C = [D, -S]
  -> full source x receiver fields
```

The package does not import an SDF extractor, fitting method, MOD, gprMax, or
either Nyström oracle. Upstream orchestration freezes an SDF-derived
`PeriodicCurve2D` for a forward/adjoint pair. The explicit `C` matrix and the
actual assembled system matrix are retained so the opt-in adjoint can apply
`C.conj().T` and solve with `A.conj().T` rather than recreating either
operator. Forward snapshots also retain the typed assembly/solve settings and
material values needed to replay the accepted primal discretization.

The ACC measurement is not the full receiver matrix. If `P` selects the
source/receiver diagonal, its data path is

```text
y = P(C q + u_inc),       Psi = P^H psi,       A^H lambda = C^H Psi.
```

Here `P^H` scatters a paired residual vector onto the diagonal of a full
`(num_sources, num_receivers)` dual. Passing that vector directly to
`ExteriorReceiverOperator.apply_adjoint` would instead mean one RHS and is not
the ACC adjoint. Pair selection belongs in the typed
`shape_derivative.KressPairedObjectiveAdjoint` context, not inside this general
receiver operator. It supports arbitrary paired indices and accumulates
repeated selections, including complex source strengths.

The geometry adjoint needs a legal fixed-grid `KressDirection` that
perturbs `gamma`, `gamma_theta`, and the remaining jets coherently, deriving
normal, speed, and `ds` changes from the same direction. Point-only
perturbations with frozen normals or weights are invalid. The returned shape
quantity is a real directional derivative of the discrete data objective,
not an unweighted normal-density estimate. Arc factors already belong to the
operators; a caller must not multiply the returned covector by `ds` again.

Explicit imports from `gpr_bem_kress.shape_derivative` provide
`linearize_kress_forward` and `build_paired_objective_adjoint`. They
differentiate the actual near-series/direct-kernel branches, analytic
diagonals, normals, weights, incident traces and receiver map, with optional
real positive-lossless material and complex source-strength directions.

`gpr_bem_kress.geometry_pullback.build_kress_geometry_pullback` supplies the
geometry reverse of that objective: one reverse pass per frequency returns
already-weighted covectors on native positions and first derivatives. Compose
both with a coherent curve/Method-B construction. These arrays are not normal
velocities or an unweighted density, and require no extra arc factors. The
implicit neural inverse uses this API to update weights directly.
Native node correspondence, period, frequency, acquisition and topology stay
fixed. Primal reassembly is checked against the retained forward arrays;
branch margins are diagnostics, not permission to cross a branch or validity
threshold inside one derivative check. The second/third direction jets are
validated when supplied but unused by the current cancelled operators.

The [follow-up report](../../docs/reports/sdf_kress_followup_2026-09-06.md) records
independent Mie/Nyström, matched-material analytic, finite-difference and
physical-refinement checks. This module does not differentiate extraction,
change the production optimizer, implement multi-component derivatives, or
infer a unique arbitrary normal-gradient density from coefficient derivatives.

The established package exports support one smooth, simple, counterclockwise
component in lossless nonmagnetic media, with safely separated exterior
sources and receivers. They remain direct-import only and are not registered
in `solver_select` or an operational inverse pipeline.

An additive multi-object implementation is available by explicit import from
`gpr_bem_kress.multicomponent`. It accepts `OrderedBoundary2D`, applies the
existing Kress implementation independently to every self interaction, and
uses exterior-only smooth quadrature between disjoint components. It is not
re-exported here, so enabling it is an intentional future routing decision and
cannot change existing single-component callers.

## Optional coupled Jacobians and execution settings (SPD-001)

`gpr_bem_kress.coupled_shape_derivative` promotes BIE-004's exact coupled
shape derivative. `build_coupled_base` retains one LU per geometry/frequency;
`directional_operators` and `tangent_response` reuse it for all source RHSs and
coefficient directions. Self and both directed cross interactions, incident
traces and receiver maps are differentiated. The per-direction primal
consistency check remains active. This API covers fixed-topology, disjoint,
same-material lossless nonmagnetic components.

The Cartesian state bridge is
`sdf_inverse.analytic_jacobian.cartesian_residual_jacobian`. The existing
`run_multiradial_fd_inverse` retains its historical name. Since SPD-002, its
shared inverse runtime defaults to **analytic Cartesian Jacobians + fast CPU
kernels**. Radial coefficients retain FD. Topology refinement, candidate
refinement and current-pipeline continuation inherit this default.

```python
from gpr_bem_kress.execution import execution
from sdf_inverse.radial_topology import run_multiradial_fd_inverse

with execution(kernels="real_bessel", device="cpu") as work:
    result = run_multiradial_fd_inverse(
        initial_state, data, geometry_config,
        solve_config=solve_config, config=optimizer_config,
        cartesian_gauge=True, jacobian_mode="analytic",
    )
```

Normal topology commands need no additional flag. Use `--inverse-runtime
reference` on the topology controller, topology benchmark, challenge driver or
TOP-025 runner to restore FD/reference CPU. `SDF_INVERSE_RUNTIME=reference`
works for all callers and is inherited by spawned workers. In Python:

```python
from sdf_inverse.runtime import inverse_runtime

with inverse_runtime("reference"):
    result = run_multiradial_fd_inverse(...)  # FD/reference CPU
```

SPD-005 adds an opt-in `--inverse-runtime reciprocal` (or
`SDF_INVERSE_RUNTIME=reciprocal`, `inverse_runtime("reciprocal")`). It uses the
same Kress forward and optimizer, with coupled source/receiver trace products
for Cartesian shape derivatives. Unit receiver illuminations reuse each base
LU; shape columns are boundary contractions. Complex source strength is applied
once, through the primal trace, and the reciprocal product has no conjugation.
The runtime retains operator derivatives when any component has fewer than
128 nodes. Explicit `method="reciprocal"` calls bypass that guard for diagnostics.
`fast` remains the explicit operator-derivative comparison profile. The reciprocal
identity approximates the continuous shape derivative, so accuracy on coarse
grids must be qualified; see the [SPD-005 plan](../../docs/iterations/speedup/iteration_04/03_plan.md).
The existing high-level lossless/nonmagnetic material restriction and
`fd_compatible` constraint policy apply. Passive counters distinguish primal
RHSs, reciprocal RHS batches/columns and contractions; budget ledgers charge
one reciprocal batch without calling it another matrix assembly.

Execution choices are `kernels="reference"` or `"real_bessel"`, and
`device="cpu"` or `"cuda"`. They are scoped to the context. The standalone
forward solver retains reference kernels when called without a context;
inverse entry points supply the fast CPU context. Explicit contexts take
precedence over inverse defaults. CUDA is explicit,
requires an available device and lazily imports Torch. CPU use does not load
Torch. All paths retain double precision. The fast special functions use a
real-positive-argument path and the existing general complex fallback; the
near-interaction series and diagonals are unchanged.

`analytic_constraint_policy="true"` uses the actual analytic column even when
an FD stencil would lose a side; physical candidate feasibility is still
checked. The default `"fd_compatible"` policy reproduces stencil refusals and
uses measured one-sided FD only where needed, reporting those fallback columns.
Analytic derivatives and finite-step quotients can still give slightly
different iterates. Explicit analytic requests for unsupported non-Cartesian
coefficient bridges fail; the default `auto` selection uses FD for those states.

`work.counts` and `work.seconds` distinguish dense factor/solve calls, retained
factorizations, RHS solves, derivative assemblies and transfers. Phase times
can be nested and must not simply be summed. The inverse's passive work ledger
adds analytic-base, derivative-assembly, tangent-solve and retained-factor
counters; legacy forward/TD counters continue to describe their existing
paths. For total factorizations use the execution context or combine the
legacy forward/TD system counts with the additional retained-factor count.
Current pipeline budgets charge both full systems and analytic directional
assemblies/tangents. `total_attempted` remains a full-system count;
`budget_work_units` additionally includes attempted derivative assemblies.

The [SPD-001 plan](../../docs/iterations/speedup/iteration_01/03_plan.md) owns
the original bounded numerical/runtime comparison. The user authorized default
promotion under [SPD-002](../../docs/iterations/speedup/iteration_02/03_plan.md).

### Compiled Kress inverse backend (default)

The default `compiled` profile (also selected explicitly with
`--inverse-runtime compiled` or `SDF_INVERSE_RUNTIME=compiled`) uses the
SPD-006 reduced scattering backend inside analytic Cartesian fits at 256 or
more nodes. Multi-object states use local Kress regular-wave compilations and
a small coupled outgoing-wave system. Single-object states retain reciprocal
Kress. Existing 64-node topology fits, TD fields, readiness, independent refined
candidate checks and final endpoint checks keep full Kress. `fast` is the
previous operator comparison profile; standalone forward APIs retain their own settings.

The compiler preserves the full production Cartesian shape space and gauge.
Reciprocal source/receiver traces reconstructed from the local regular-wave
solutions supply the shape Jacobian. Its cache belongs to one fit and reuses
unchanged local coefficients, including pure translations. Rotations expressed
as changed Cartesian coefficients recompile. Cylindrical normalization uses a
fixed 0.1 m scale; a separate coefficient-sum radius certifies geometric bounds.

Each new state compares outgoing orders 20/24, then 24/28 or 28/32 if needed.
Prediction changes must be <=1e-11 and whole/worst-column derivative changes
<=1e-7. Local and reduced linear residuals must be <=1e-10. Failure falls back
to full Kress and is recorded, as do overlapping bounding circles, acquisition
points within a bounding circle, unsupported materials and requested full
condition-number diagnostics. Original geometry/clearance checks still apply.

Work ledgers charge a `compiled` frequency batch separately from physical full
systems and reciprocal RHS batches. Passive counters additionally report local
factorizations/RHS columns, local cache hits, reduced solves/RHS columns and
fallbacks. Angular retries are included in the batch and their reduced solves
are counted individually. `compiled_backend.json` in continuation stage results
records convergence checks and fallback reasons.

Saved-state qualification passed 33/33 checks and 114 regression tests passed
(one unavailable-CUDA skip). All 16 matched full workers recovered. With the
same readiness wrapper, compiled continuation reduced full runtime by 4.5% on
central ellipse/star and 5.6% on two stars; death and the single-object merge
control were unchanged. Following SPD-007 default promotion, the normal TOP-025
full pipeline enables readiness with the compiled profile. Comparison profiles
(`fast`, `reciprocal`, `reference`) retain the full continuation schedule. See the
[default-promotion record](../../docs/iterations/speedup/iteration_07/01_results.md).
See the [SPD-006 results and remaining-cost profile](../../docs/iterations/speedup/iteration_06/01_results.md).
