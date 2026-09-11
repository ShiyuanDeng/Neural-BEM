# Boundary–BIE track — iteration 01 research brief

**Status: PROPOSED — NOT APPROVED FOR EXECUTION.**

**Track:** [Boundary–BIE](../../README.md)
**Baseline:** [B0 — 2026-09-10](../../../../baselines/B0_2026-09-10.md)
**Date:** 2026-09-11
**Author role:** proposal. Nothing here is a plan, and nothing here authorises
implementation. Approval is per experiment ID.

This brief opens the track from existing evidence rather than from
`01_results.md`; there is no prior cycle in this track to produce one. It
deliberately does **not** select a winning mechanism — selecting one is the
first deliverable, `BIE-001`.

## 1. Question

> Which properties of smooth-boundary representations can improve the accuracy,
> conditioning, differentiation, or cost of the BIE inverse?

Not "how do we replace Kress". Kress/Nyström may well remain; the question is
which property of the boundary representation is currently limiting, and the
answer might be in the geometry coordinates, the trace representation, the
formulation, or the derivative path.

## 2. What the baseline actually does

Read from the source at B0, not from earlier summaries.

### 2.1 Forward solve

`gpr_bem_kress` is an ordered periodic Kress/Nyström **Müller** solver:

```text
PeriodicCurve2D
  -> cancellation-safe Delta V/K/K'/T assembly
  -> direct unsquared Muller solve
  -> explicit exterior receiver operator C = [D, -S]
```

The system is dense and **`2N × 2N`** with two nodal densities per node
(`system.py:117`–`:121`), solved directly. Resolution is `N = 64` production and
`N = 128` refined, **per component**. A multi-component assembly adds
cross-component clearance constraints, which is why candidates get rejected with
`… too close for ordinary cross-component quadrature`.

Condition number is computable but **off by default**
(`forward.py:127`), and the code explicitly labels what it would return:
`"condition_number_kind": "raw_mixed_unit_nodal_2_norm"`,
`"condition_number_scale_invariant": false`. That is an honest warning: the
existing number is not a scale-invariant conditioning measure and should not be
used as one without work.

### 2.2 Boundary-trace representation

There is none in the modal sense. The unknown is nodal density on the Nyström
grid. **`K_u` does not exist at B0.** Any statement about "modal traces" is a
proposal, not a description of the current system.

The `contour_modes = 8` setting in the topology controller is a *geometry*
contour-fitting bandwidth for candidate construction. It is not a trace
bandwidth, and it must not be reported as one.

### 2.3 Geometry coordinates and the gauge

The explicit state is `MultiRadialFourierState`, holding radial or Cartesian
Fourier components. Two distinct optimizer paths exist and are frequently
conflated:

| Path | Jacobian columns | Gauge handling |
|---|---|---|
| Single-component driver (`run_explicit_cartesian_fourier_inverse.py`) | full `4K + 2` coefficients, phase direction projected out | one re-gauging per accepted step |
| Topology path (`run_multiradial_fd_inverse(cartesian_gauge=True)`) | the gauge-fixed subspace: `3` for `K ≤ 2`, `2K − 1` above | converged gauge, steps and Jacobians inside the subspace |

The subspace fact is exact and worth restating precisely
(`curve_updates.py:1399`): the gauge-fixed set is a **linear** subspace — a
curve is gauge-fixed exactly when it is `m + rho(theta) e(theta)` for a
band-`K−1` radial profile with no mode one. So the gauge-fixed Cartesian chart
at band `K` is the radial chart at band `K−1`.

**This is a property of the policy, not of Cartesian Fourier curves.** B0 §7
records the distinction. The un-gauged chart was measured and rejected on
optimisation grounds — parameter drift along data-invisible directions, degraded
quadrature, stalled shape progress — and 63 of its proposed steps were rejected
as unprojectable against 1 in the radial chart. What the gauge *costs* in
representable geometry is an open question for this track, not a settled one.

### 2.4 Derivatives

- The explicit multi-component inverse is **finite-difference only**: central FD
  columns through `run_multiradial_fd_inverse` with Levenberg damping,
  backtracking and exact rollback. Each column costs forward solves.
- A **validated analytic discrete** Kress shape derivative exists
  (`gpr_bem_kress/shape_derivative.py`) — it differentiates the actual
  near-series/direct-kernel branches, analytic diagonals, normals, weights,
  incident traces and receiver map, with a legal fixed-grid `KressDirection`
  that perturbs `gamma`, `gamma_theta` and the remaining jets coherently.
- That derivative is **single-interface**. Its consumers are the material
  inverses (`sdf_inverse/material_inverse.py`,
  `robust_material_inverse.py`) and the implicit-MLP pullback
  (`geometry_pullback.py`). Neither `radial_topology.py` nor
  `topology_controller.py` imports it.

So the largest single derivative fact at B0 is: **an analytic discrete
derivative exists and the explicit multi-component path does not use it.**
Whether extending it to multiple interfaces is worthwhile — and whether it would
beat FD once assembly cost is counted — is unmeasured.

### 2.5 Cost, as measured

The topology optimizer's Jacobian costs `2K − 1` columns rather than `4K + 2`;
the ellipse/star challenge case took 1769 forward solves in the Cartesian chart
against 1756 radial. The single-component driver still pays the full `4K + 2`
and was not changed. Wall-clock numbers in the dated bundles are not controlled
comparisons (B0 §8.5).

## 3. Candidate directions

Grouped as three families. Nothing here is selected.

### 3.1 Geometry and optimisation coordinates

- **What the gauge costs.** The gauge-fixed set is the radial chart one band
  lower, so under the current policy the Cartesian chart buys nothing in
  representable geometry. Is there a target in this project's family that is
  band-limited in polar angle but *not* star-shaped about its own mean? If one
  exists, it separates the charts; if none does, the gauge is free and the
  question closes.
- **Parameterisation freedom.** The record that shapes everything: the five-lobed
  star has exactly three active Cartesian modes in polar angle and band 6
  contains it to `6.4e-17 m`, while the same curve resampled to arc length is not
  band-limited at any practical bandwidth (band 32 leaves `1.069e-04 m`).
  Parameterisation, not bandwidth, sets the ceiling. What is the right
  parameterisation for a target whose polar-angle representation is *not* sparse?
- **The re-gauge accuracy floor**, still open from the Cartesian cycle's
  iteration 2 and unaffected by iteration 3.
- **Coordinate-dependent trust region.** The Cartesian record notes the trust
  region depends on coordinates; a metric on coefficient space that reflects
  boundary motion rather than coefficient magnitude is a candidate.

### 3.2 Boundary-field representation and formulation

- **Modal traces.** Represent the density in a Fourier basis of bandwidth `K_u`
  instead of nodally. Possible gains: fewer unknowns for smooth data, a natural
  place to precondition, and derivative structure that follows the geometry
  modes. Possible costs: the Müller kernel's near-singular structure is what the
  Kress quadrature is built for, and a modal basis does not remove that.
- **Weak / Galerkin formulations.** A genuine change of discretisation, with its
  own quadrature and its own conditioning behaviour.
- **A soft physics-residual penalty in the optimisation loss is a different
  thing entirely.** It does not change the discretisation; it changes what is
  optimised, and it can hide a discretisation error as an optimisation
  trade-off. Keep these two separated in every proposal, comparison and report.
- **Decoupling `K_gamma`, `K_u` and `N`.** At B0 only `K_gamma` and `N` exist,
  and they are set per case rather than derived from each other. Do not assume
  `K_u = K_gamma` or `N = c·K`. What each one controls, and where each one binds,
  is measurable at fixed geometry.

### 3.3 Derivatives, preconditioning, and optimisation metrics

- **Multi-interface analytic derivative.** Extend the validated single-interface
  discrete derivative to the multi-component assembly and compare against FD on
  accuracy, total solves, and behaviour near the clearance constraints.
- **Preconditioning.** The Müller formulation is chosen for its second-kind
  structure; whether the *inverse* problem's Gauss–Newton system benefits from a
  boundary-aware preconditioner is separate and unmeasured.
- **A physically meaningful metric.** The optimisation currently measures steps
  in coefficient units with a millimetre-scale cap. A metric derived from
  boundary displacement, or from the data's sensitivity, would make the trust
  region chart-independent.
- **Scale-invariant conditioning.** Before conditioning can be a metric, the
  existing condition number needs replacing; the code already declares that the
  current one is raw, mixed-unit and not scale-invariant.

## 4. Candidate experiments

### BIE-001 — Compare the mechanisms and select one discriminating prototype

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION
- **Execution status:** NOT STARTED
- **Question:** Which single mechanism from §3 is most likely to change the
  accuracy, conditioning, differentiation cost or solve cost of this specific
  BIE inverse, and what is the cheapest prototype that would discriminate it?
- **Falsifiable hypothesis:** There exists a mechanism whose expected effect can
  be estimated from the existing code and bundles well enough to rank it above
  the others. Falsified if the ranking is dominated by unmeasured quantities —
  in which case the deliverable becomes a named measurement, not a prototype.
- **Baseline:** B0. Reference behaviour: the Kress/Müller forward at 64/128
  nodes, the FD Jacobian in the gauge-fixed subspace, and the recorded costs in
  §2.5.
- **Intervention:** **none to production code.** This is a comparison and
  selection deliverable, carried out by reading the existing implementation and
  the existing bundles.
- **Controls:** no production file is modified; no result bundle is written to;
  no expensive run is launched. Any measurement made to inform the comparison is
  a **review diagnostic** with its own declared scope and budget, recorded as
  such and not as an experiment result.
- **Scope and shared interfaces:** read-only over `gpr_bem_kress/`,
  `sdf_inverse/radial_topology.py`, `sdf_inverse/curve_updates.py`, and the
  committed result bundles.
- **Metrics and comparison criteria:** each mechanism scored on — expected
  effect on forward accuracy at fixed geometry; expected effect on the
  conditioning of the solved system and of the inverse Gauss–Newton system;
  expected effect on derivative cost (solves per Jacobian) and derivative
  accuracy; implementation cost and blast radius across shared interfaces; and
  what would have to be true for it to fail. Rankings must state which inputs
  are measured, which are estimated, and which are unknown.
- **Compute budget and stopping rules:** desk study. No inverse runs. If a
  discriminating estimate genuinely requires a forward measurement, name it as a
  separate diagnostic with its own budget rather than folding it in.
- **Artifacts:** `02_proposals/02_mechanism_comparison.md` in this iteration,
  containing the ranked comparison, the selected prototype, and the contract
  (`BIE-002`) for building it.
- **Decision criteria:** **Adopt** — one mechanism ranks clearly ahead and its
  discriminating prototype is writable within a declared budget; the deliverable
  is that prototype's contract. **Reject** — no mechanism separates from the
  others; the deliverable is the named measurement that would separate them.
  **Investigate further** — the ranking depends on a property of the current
  solver that is not measured; name the diagnostic.
- **Owner:** unassigned. **Reviewer:** unassigned.

**No literature review is in scope here.** What the later research phase must
investigate is recorded in §5, not resolved now.

### BIE-002 — The prototype selected by BIE-001 (placeholder)

Reserved. Its contract is written by `BIE-001`, not before it. Recording the ID
now is not a commitment to any particular mechanism.

### BIE-003 — Resolution decoupling at fixed geometry (stub)

Measure independently what `K_gamma` and `N` each control — forward accuracy
against the independent oracle, and system conditioning — on fixed analytic
geometries including the star and the pre-event topology states. Establishes
whether the current `64/128` choice binds anywhere, and gives `K_u` a reference
to be judged against if a modal trace is ever built. **Not a contract; not
approved.**

### BIE-004 — Multi-interface analytic discrete derivative (stub)

Extend the validated single-interface derivative to the multi-component assembly
and compare against the current FD Jacobian on accuracy and total solves, at
fixed geometry and fixed topology. Note the shared-interface blast radius:
this touches the solver interface the topology track depends on and must be
declared before implementation. **Not a contract; not approved.**

### BIE-005 — Modal boundary trace (stub, explicitly not pre-selected)

A `K_u`-bandwidth modal density against the current nodal Nyström unknown, at
fixed geometry first. Listed as a candidate because it is the most frequently
proposed direction, and marked here precisely so it is not adopted by default.
**Not a contract; not approved.**

## 5. What the later research phase must investigate

Recorded so the desk study does not have to re-derive it, and so no one mistakes
this brief for having done it:

- Whether Galerkin/weak formulations of the Müller system offer conditioning or
  accuracy benefits that survive the near-singular kernel treatment Kress
  quadrature already provides.
- Whether modal-density formulations for smooth closed curves have an
  established accuracy/conditioning result for transmission problems, and under
  what smoothness assumptions.
- Established practice for scale-invariant conditioning measures for
  mixed-unit boundary-integral systems.
- Shape-derivative practice for multi-interface transmission problems, and how
  clearance and quadrature constraints interact with the derivative near
  topology events.
- Whether any established boundary parameterisation handles targets that are not
  sparse in polar angle without losing the band-limitedness that makes this
  chart work.

## 6. What this brief does not claim

- It does not claim Kress should be replaced, kept, or modified.
- It does not select modal traces, Galerkin, or analytic derivatives as the
  winner. `BIE-005` is on the list specifically so it cannot be adopted silently.
- It does not claim the gauge restriction is a limitation of Cartesian Fourier
  curves. It is a limitation of the current policy; what it costs is open.
- It does not claim `K_gamma`, `K_u` and `N` should be equal, coupled, or
  independent. It claims only that at B0 two of them exist, they are set per
  case, and their coupling is unmeasured.
