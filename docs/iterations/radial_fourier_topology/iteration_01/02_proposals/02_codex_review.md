# Codex review: topology-aware Explicit Radial Fourier brief

This review follows the
[initial implementation brief](01_radial_fourier_topology_initial_instructions.md)
and the project [handoff](../../README.md). It compares the proposal with the
current Explicit Radial Fourier state, the direct multi-component boundary
seam, the Kress/Müller implementation and its independent cylinder oracles.
Reviewed on 2026-09-08 on `feature/ordered-boundary-nystrom` at
`34864abd9d42e0b1d1c6498e60fc3e6aa2b50356`. The inspected solver and inverse
code is unchanged from the brief's `f5a77ff` baseline. Uncommitted work in the
checkout concerns the separate implicit-MLP iteration and was not used or
modified.

**Verdict: adopt the hybrid fixed-topology-refinement/component-birth
architecture after amendment.** The proposed scope, state ownership, staged
gates and insistence on actual-objective acceptance are appropriate. Before an
agreed plan authorizes implementation, make the production objective and its
measurement indexing explicit, use the repository's independent circle
oracles, define an empty-background branch, route ordinary objective calls
through the existing direct multi-component seam, and specify how the
one-curve optimizer will be adapted. Birth acceptance also needs a
cross-resolution error margin rather than a deterministic-repeatability
margin.

This review authorizes no implementation or experiment.

## Review decisions and confidence

| Decision | Review | Confidence |
|---|---|---|
| Hybrid architecture | Accept fixed-topology radial refinement alternating with discrete, non-differentiated component birth | High |
| First scope | Accept one birth for separated, same-material circles; retain all stated merge/split/delete/material deferrals | High |
| Current-domain TD | Require the TD of the non-empty current domain for T1–T4 and validate it by finite insertions | High |
| Exact TD formula | Do not freeze the displayed sign, conjugation or prefactor in the plan; derive them from the repository objective and pass insertion asymptotics | High that this gate is required; medium on the unimplemented closed form |
| Truth data | Use the independent one-cylinder Mie oracle for T0 and the independent multi-cylinder oracle for T1–T4 | High |
| Measurement set | Form the TD only from observed source/receiver entries; paired data must not silently become the full source-by-receiver matrix | High |
| Multi-component forward | Use `predict_multicomponent_kress_paired_boundary_response` for ordinary inverse objective calls and retained low-level Kress results for TD work | High |
| Multi-radial state | Add a small immutable tuple of the existing `RadialFourierCurveState`; its members already own stable `component_id` values | High |
| Optimizer reuse | Reuse the objective, FD/LM policy and radial retraction, but do not treat either current inverse entry point as already multi-component | High |
| Numerical acceptance | Qualify topology, objective decrease and TD asymptotics under component-node refinement; set margins from cross-resolution error | High |
| Threshold and circular seed | Retain configurable `C0=0.15` as a declared first proposal rule, with grid/connectivity conventions fixed in advance | Medium-high |
| Automatic topology loop | Keep deferred until the complete T0–T4 sequence passes | High |

## What should be retained

The brief correctly separates the two kinds of update. A
`RadialFourierCurveState` is a positive, star-shaped, fixed-component chart;
continuous coefficient steps cannot create another object. A topological
derivative should therefore propose a discrete state transition, after which a
fresh fixed-topology optimization stage begins. The 2019 hybrid paper does use
topological derivatives to update object count and regularized Gauss–Newton to
sharpen fixed-topology shapes, while the 2018 iterative paper explicitly
derives topological sensitivities when approximate domains already exist. The
brief's distinction between an empty-background indicator and
`D_T J(z; Omega_current)` is well founded.

Also retain these implementation principles:

- preserve the accepted components exactly during a disjoint birth;
- append a new stable component ID and rebuild parameter offsets;
- validate the actual finite proposal with the unchanged training objective;
- restart damping, Jacobian and dimension-dependent optimizer state after a
  birth;
- keep raw physical TD and any frequency-normalized localization indicator as
  separately named fields;
- stop at the first failed gate and report which layer failed;
- keep holdout data out of threshold, radius and acceptance choices.

The literature values `C0=0.15`, `0.2` and `tau=1.01` are reported accurately,
but are settings from a different three-dimensional holography problem. The
brief already treats them as non-universal; the agreed plan should preserve
that caveat. The cited two-dimensional Fresnel work supports the scalar
dielectric and multifrequency context, but is a one-step imaging study. It does
not by itself supply the exact non-empty-domain TMz formula required here.

## Required amendment 1: write the exact observed-data objective first

The current production residual is defined in
[`normalized_complex_residual`](../../../../../solvers/sdf_inverse/optimization.py).
For predicted and observed paired scattered responses `p_sf` and `d_sf`, it
implements

\[
J(p)=\frac12\sum_f \frac{w_f}{s_f^2}
\sum_s |p_{sf}-d_{sf}|^2,
\]

where `s_f` is the fixed observed-column norm with the recorded scale-aware
floor. Therefore the complex residual weight entering a derivation is
proportional to

\[
\frac{w_f}{s_f^2}\,\overline{(p_{sf}-d_{sf})},
\]

subject to the final adjoint convention. It is not enough to refer loosely to
"the residual" because the stored real residual contains one factor
`sqrt(w_f)/s_f`, while differentiating its squared norm supplies the second.
Use the same helper to evaluate every insertion and birth objective, and save
`s_f`, `w_f`, the raw complex misfit and the real stacked residual convention.

The current paired forward computes a full source-by-receiver Kress matrix and
then selects its diagonal. That implementation detail must not widen the data
set. For paired acquisition, source `s` contributes only its declared paired
receiver. A future multistatic arm may sum over a declared measurement index
set, but unobserved cross entries cannot enter the TD or acceptance objective.
Write the derivation over a measurement set `M_f`; specialize it to the paired
diagonal in the first experiment.

The physical source strength is already part of each forward total field.
Auxiliary receiver-as-source solves used to construct a reciprocal Green field
should use a unit source unless the derivation assigns a different factor.
Record that distinction and include the existing source-strength scaling
regression in G1.

## Required amendment 2: use the independent cylinder oracles

The proposed targets are circles, so generating all observations with the same
multi-component Kress solver is unnecessary. The repository already has:

- [`gpr_bem_ref.penetrable_cylinder_frequency_response`](../../../../../solvers/gpr_bem_ref/cylinder_reference.py)
  for T0's one-circle observations;
- [`multicylinder_ref`](../../../../../solvers/multicylinder_ref/README.md) for
  disjoint same-material circular cylinders, including line-source strength
  and a convergence-controlled truncation;
- an existing
  [two-cylinder/Kress comparison](../../../../../pytest/sdf_bem_multicomponent/test_split_fixture.py)
  at the exact endpoint of the Cassini fixture.

Use the one-cylinder Mie series for T0 and the multi-cylinder series for T1–T4
training and holdout observations. Use Kress for the current domain, insertion
quotients, birth candidates and radial refinement. First compare Kress truth
responses against each independent oracle at the exact target and the exact
planned materials, frequencies, acquisition and node counts. This makes G0 a
real forward qualification and removes a same-solver inverse crime from the
first topology result.

The Cassini endpoint supplies a useful pre-existing geometry: two radius
`0.045 m` circles centred at `(0.34, 0.50) m` and `(0.66, 0.50) m`, with
`0.23 m` surface clearance. Reuse its geometry or its construction pattern,
but rerun the oracle comparison with the production material pair
`epsr_ext=6`, `epsr_int=3`, the selected acquisition and selected frequencies;
the recorded fixture test used a different material pair and 1.2 GHz.

## Required amendment 3: T0 needs an explicit empty-background branch

`OrderedBoundary2D` requires at least one component and the multi-component
Kress adapter likewise assumes a non-empty boundary. Do not create a zero-size
or zero-contrast sentinel component to represent the background.

For T0, define the empty current state analytically:

- predicted scattered response is exactly zero;
- the current total forward field is the repository's free-space line-source
  Green field;
- the adjoint/backpropagated field uses the corresponding free-space Green
  response;
- each non-empty insertion candidate is evaluated through the ordinary Kress
  path.

This keeps T0 a clean convention check. T1 and later then exercise the actual
non-empty current-domain machinery.

## Required amendment 4: use the seams that already exist

The brief points to `gpr_bem_kress.multicomponent`, but the normal inverse-level
entry point already exists in
[`sdf_bem_multicomponent.forward`](../../../../../solvers/sdf_bem_multicomponent/forward.py):
`predict_multicomponent_kress_paired_boundary_response`. It accepts an
already-owned `OrderedBoundary2D`, structurally copies the active
`PairedForwardProblem`, performs no SDF extraction, preserves component IDs and
offsets, and returns the paired response plus every retained low-level Kress
solve. Use it for all ordinary objective evaluations.

TD field evaluation will need more than the paired diagonal. At each frequency
it needs current total fields on the inspection grid for the physical sources
and reciprocal total Green responses from the observed receiver locations.
Use the retained frequency system/receiver-operator primitives or a small
batched helper around `gpr_bem_kress.multicomponent`; do not loop over grid
points and do not duplicate Kress kernels. If a new helper is required, make
its source strengths, full matrix orientation and field-point clearance
explicit and validate selected entries against ordinary forward calls.

`RadialFourierCurveState` already contains a validated, persistent
`component_id`. A new `MultiRadialFourierState` need only own an immutable tuple,
enforce non-empty unique IDs and define deterministic flatten/unflatten slices.
It should build each component through `radial_fourier_state_curve(...,
full_validation=True)` and concatenate the curves into `OrderedBoundary2D` in
stored order. Do not add a second ID registry that can disagree with the member
states.

## Required amendment 5: optimizer reuse is algorithmic, not yet an API call

Neither current optimizer can consume a multi-radial state directly:

- `run_alternating_neural_inverse` owns one `PeriodicCurve2D`, one optional
  `RadialFourierCurveState`, MLP representation policy and one-curve records;
- `run_parameter_fd_inverse` is reusable mathematically, but its evaluator is
  tied to a Torch parameter controller and the single-component
  `predict_paired_response` path.

The existing multi-component README already warns that injecting a different
predictor into the one-curve optimizer would leave its state space at `M=1`.
The agreed plan must choose one explicit adaptation:

1. extract the bounded FD/LM loop behind a small evaluator/controller protocol,
   then use it for both the existing parameter path and the new multi-radial
   state; or
2. add an opt-in topology experiment optimizer that reuses
   `normalized_complex_residual`, the declared FD stencils, scaled LM damping,
   strict decrease and backtracking policies without importing MLP
   re-distancing.

The first option reduces duplicated numerical policy but has a wider regression
surface. The second is smaller for this one experiment but must document any
policy difference. In either case, T3 should use six active variables for two
`K=1` states: each component has mean radius, centre x and centre y, with its
mode-one radial slots fixed by the existing gauge. Parameter names and
trajectory rows must include component IDs.

## Required amendment 6: qualify numerical error by refinement

The current validation layers are complementary:

- `radial_fourier_state_curve(..., full_validation=True)` validates each
  continuous radial parameterization at an independent resolution;
- `OrderedBoundary2D` preserves component identity and rejects duplicate IDs;
- `adapt_multicomponent_boundary` checks intersection, nesting and clearance
  on the sampled component polygons;
- ordinary cross-component and off-surface quadrature has no close-evaluation
  correction.

Consequently, a production-grid pass is not a continuous two-component
topology certificate. For G0, G1 and every candidate considered acceptable in
G3, rebuild all components at a declared finer even node count. Require stable
topology/clearance classification, stable objective difference and a converged
insertion quotient over a resolved radius window. Record both component node
counts and the required/observed clearance at each resolution.

The solver is deterministic, so repeating the same solve may give zero or tiny
repeatability error while retaining discretization bias. Set the birth
acceptance margin from a bound supported by node-refinement changes in
`J_new-J_old`, with a floating-point floor. Accept only when the loss decrease
has the same sign at production and refined resolution and exceeds that bound.
Apply the same logic to the desired 10% insertion-asymptotic target; do not use
an unresolved smallest disk merely because its quotient is closest to the
formula.

## Required amendment 7: make raster proposal conventions reproducible

The threshold and circular seed are suitable for a first proposal, subject to
fixed raster conventions:

- define whether grid values live at cell centres or nodes;
- declare 4- or 8-neighbour connectedness;
- compute mask area with the physical cell area and the selected valid cells;
- use the same area weights for the centroid;
- keep the global minimum separately even if its threshold component is later
  rejected;
- reject a mask component touching the grid boundary;
- define the minimum resolvable seed radius before looking at truth or holdout;
- extend radius backtracking deterministically down to that minimum rather
  than stopping at a hard-coded `0.35 r_eq` when a smaller resolved disk could
  still realize the negative asymptotic direction.

Equivalent-area radius is a proposal scale, not an estimator proven to recover
the missing object's size. Report its dependence on TD grid refinement and
`C0`. Do not tune either from the target overlay.

## Existing checks and new checks

The brief's Phase-0 requirements should call existing tests instead of
duplicating them. The current suite already checks:

- exact one-component agreement between multi- and single-component Müller
  systems and direct paired response;
- component-permutation similarity and receiver-field invariance;
- intersection, nesting, clearance and field-point rejection;
- nonzero-contrast receiver convergence under node refinement;
- a two-cylinder Kress field against the independent multi-cylinder oracle.

For this review, the focused multi-Kress/direct-boundary tests passed:
`32 passed`; the direct-curve/radial-state tests passed: `14 passed`; and the
independent endpoint-oracle test passed: `1 passed`. No inverse, TD evaluation
or new BEM experiment was run.

Add only the missing topology-inverse coverage: multi-radial state slicing and
rollback, exact observed-measurement selection, empty-background convention,
TD formula/scaling, finite-insertion convergence, deterministic raster birth,
cross-resolution acceptance, and component-keyed multi-radial FD columns.

## Recommended gated order for the agreed plan

| Order | Bounded work | Required evidence before advancing |
|---|---|---|
| 1 | Freeze scene, paired measurement indices, one training frequency, holdout, material, source strength, objective scales and component/node resolutions | Complete configuration with no target-derived setting |
| 2 | Re-run one- and two-cylinder Kress comparisons against independent converged oracles at that configuration | Response and refinement errors below predeclared G0 limits |
| 3 | Add the immutable multi-radial builder and objective seam; test `M=1`, `M=2`, ID/slice stability and refined topology guards | Bitwise or tolerance-qualified seam agreement and local rollback |
| 4 | Derive and implement the empty-domain TD; run T0 insertion sequences | Correct sign and convergent quotient at strong and background probes |
| 5 | Derive and implement the non-empty current-domain TD; run T1 only | Paired-indexed objective derivative, resolved insertion convergence and localization without truth-guided settings |
| 6 | Freeze raster conventions and run the one-event T2 birth line search | Refined actual-objective decrease from a TD-only centre/radius proposal |
| 7 | Restart and run the six-variable, two-`K=1` T3 refinement | Monotone training objective plus separately reported holdout and geometry |
| 8 | Run T4 with one predeclared wrong-A perturbation | Missing-B discovery without setting changes; otherwise stop with the failed gate |

Do not combine the one-frequency G1 derivation test with the multifrequency
localization comparison. Do not start T2 while the formula merely localizes
well but lacks insertion-asymptotic agreement. Do not treat a successful T2 as
evidence that T3's multi-radial optimizer is correct.

## Decisions still required in `03_plan.md`

The agreed plan must fix, before implementation or data generation:

1. the exact two-circle scene, paired acquisition and single T0/T1 frequency;
2. production and refined component node counts, insertion radii and numerical
   error limits;
3. the measured-index representation used by the TD derivation;
4. whether the TD helper reuses a retained frequency system or performs two
   declared source batches;
5. the optimizer adaptation option and exact FD/LM settings;
6. grid bounds, shape, connectivity, `C0`, minimum seed radius and radius
   backtracking rule;
7. G0–G5 pass thresholds and the holdout set.

Confidence is **high** for findings established by explicit repository
contracts, tests or the cited algorithm structure; **medium-high** where the
recommendation is numerically standard but still requires a project-specific
threshold; and **medium** for the expected local field-product TD until its
sign, conjugation and prefactor are derived under the exact repository
convention and verified by finite-radius insertion.
