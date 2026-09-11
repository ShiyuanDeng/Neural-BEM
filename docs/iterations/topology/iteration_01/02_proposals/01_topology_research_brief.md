# Topology track — iteration 01 research brief

**Status: PROPOSED — NOT APPROVED FOR EXECUTION.**

**Track:** [Topology](../../README.md)
**Baseline:** [B0 — 2026-09-10](../../../../baselines/B0_2026-09-10.md)
**Date:** 2026-09-11
**Author role:** proposal. Nothing here is a plan, and nothing here authorises
implementation. Approval is per experiment ID.

This brief opens the track from existing evidence rather than from
`01_results.md`; there is no prior cycle in this track to produce one.

## 1. Question

> How can the inverse choose and execute topology changes more reliably,
> without a prescribed object count or excessive BIE cost?

"Reliably" is deliberately concrete: the same problem, perturbed slightly,
should reach the same topology decision, and the accepted event should be the
one that is actually best rather than the one that happened to receive optimizer
effort.

## 2. The four intervention points, separated

The current controller couples these; a proposal that changes two at once cannot
attribute its result.

### 2.1 Event triggering — *when* is a topology pass proposed?

At B0 the trigger is not a measured stagnation criterion. It is whatever stop
reason the inner fixed-topology optimizer happened to return
(`topology_controller.py:562`): `loss_change_tolerance`,
`relative_step_tolerance`, `no_decreasing_step` or `infeasible_jacobian`, plus
the two structural cases `empty_domain` and `component_radius_floor`. A
topology pass therefore runs after *every* inner solve, and the recorded
`trigger` field is a label for why the inner optimizer stopped, not a decision.

Open: is an explicit trigger — a measured stagnation rate, a topological-
derivative magnitude threshold, a residual-structure test — better than "always
try"? "Always try" is cheap to reason about and expensive to run; nothing at B0
measures the trade.

### 2.2 Candidate construction — *which* events are considered?

Births come from exterior topological-derivative regions with an equivalent-
radius ladder; splits from interior TD corridors parameterised by width, angle,
offset and contour mode count; deaths by removing components; merges by
refitting one outer contour. Candidates are grouped into families and capped at
`maximum_candidates_per_type = 48`.

The search is **finite and discrete**, and B0 shows it is the search — not the
representation — that decides some cases (§3).

### 2.3 Candidate refinement / budget allocation — *which* candidates get effort?

This is the sharpest current limitation, and it is **still present at B0**
(verified by reading `topology_controller.py:610`–`:617` in the working tree,
not from an earlier report):

```python
refinement_groups = sorted(set((kind, child_count) for … in feasible))
for kind, component_count in refinement_groups:
    group = sorted(<candidates in this group>, key=raw_loss)
    if group and config.candidate_refinement_iterations:
        loss, candidate, row = group[0]        # <- only the best raw candidate
```

Exactly **one** candidate per `(event kind, resulting component count)` group
receives `candidate_refinement_iterations = 3` LM steps. Every other candidate is
compared at its *raw* loss against a polished one. Candidates are then accepted
on the polished score (`:654`).

### 2.4 Event acceptance — *whether* the winner is committed

A candidate must decrease the production objective by more than
`acceptance_absolute_margin + acceptance_relative_margin · base_loss`, and the
decrease must survive at 128 nodes within `cross_resolution_factor = 5`. The
lowest production loss among survivors wins. Geometry validity is checked first.

## 3. Motivating evidence, read from the baseline artifacts

Three observations, all read from committed or audit bundles at B0. None was
regenerated for this brief.

**(a) The split case is the recorded failure.** In the fresh Cartesian audit run
the split recovers to `6.87e-06` relative L2 with sampled Hausdorff error
`175.21 µm`; the radial reference reaches `2.89e-07` and `15.60 nm` — about four
orders of magnitude better geometry on a case both runs call `recovered`. Both
stop at the same `relative_error_tolerance`, so neither refines further.

**(b) The two runs accepted different cuts, and the polish rule decided it.**
From `topology_passes.json` in each bundle:

| Run | Winning `(split, 2)` candidate | Raw loss | After polish | Result |
|---|---|---:|---:|---|
| Radial reference | `interior_td_corridor; width=0.012; angle=0.0; offset=-0.25; modes=1` | `0.20136` | `3.65e-08` | accepted, `15.60 nm` |
| Cartesian, audit | `interior_td_corridor; width=0.032; angle=-0.785; offset=0.0` | `0.040361` | `2.675e-03` | accepted, `175.21 µm` |

In the Cartesian pass the `modes=1` circle-style cut scores raw `0.0856`, is
never polished, and loses to a raw score it might well beat after three LM
steps — which is exactly what happens to the analogous candidate in the radial
pass, where it is the one that gets polished and wins by seven orders of
magnitude.

**(c) The selection margin is far below any meaningful accuracy.** The two best
raw `(split, 2)` candidates in the Cartesian pass score `0.040360768` and
`0.040360960` — a relative difference of `4.7e-06`. Whichever of those two
wins the raw comparison receives the entire refinement budget for its group.
Event selection is being decided at a margin smaller than the objective's own
modelling accuracy.

That is a hypothesis about mechanism, not a demonstrated cause. The Cartesian
iteration-3 record is careful on this point: candidate-search sensitivity to a
sub-millimetre pre-split geometry change is *consistent* with the observations
and is not isolated from chart-dependent contour fitting.

## 4. Candidate experiments

Only `TOP-001` is written as a full contract. The others are scoped stubs, kept
on the list so they are not forgotten and not so detailed that they look agreed.

---

### TOP-001 — Does candidate-refinement allocation, rather than extra compute, decide the event?

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION
- **Execution status:** NOT STARTED
- **Question:** When the controller commits a topology event, is the winner
  chosen by which candidate is best, or by which candidate received the
  refinement budget?
- **Falsifiable hypothesis:** Allowing a second candidate per group to be
  refined changes the accepted cut on the split case and improves its geometry
  error, **at matched total solve count**. It is falsified if the accepted event
  is unchanged, or if the improvement disappears once compute is matched.
- **Baseline:** B0, commit `345038a`. Reference runs:
  `results/inverse/radial_fourier/topology_controller/iteration-02-20260909/split`
  and the audit's
  `results/validation/cartesian_fourier/pipeline-audit-20260910/controller/split`.
- **Intervention:** the refinement-allocation rule at
  `topology_controller.py:610`–`:617`, and nothing else. Three arms:

  | Arm | Policy | Purpose |
  |---|---|---|
  | **A** | current: best raw candidate per group, 3 LM steps | reference |
  | **B** | best **two** raw candidates per group, 3 LM steps each | does more refinement help at all? |
  | **C** | best two per group at a reduced per-candidate budget chosen so total refinement solves ≈ arm A | does *allocation* help, independent of compute? |

  Arm C is what makes the experiment interpretable; B−A measures added compute,
  C−A measures allocation. Do not run B alone.
- **Replay design:** restart from **saved pre-event states** rather than whole
  inversions. Each controller bundle's `trajectory.json` contains a frame
  labelled `before split` carrying the full component parameters (radial split:
  one `parent` component, `maximum_mode = 2`,
  `[0.0510625, 0.5, 0.5, 0.04296875, −9.75e-09]`). Replay each arm from that
  state, in both charts, under declared perturbations of the pre-event state —
  a small isotropic coefficient perturbation at a few declared magnitudes
  (proposed: relative `1e-4`, `1e-3`, `1e-2` of the mean radius) with declared
  seeds. The perturbation magnitudes and seed list must be fixed before the runs
  and recorded in the manifest.
- **Controls (must not change):** observations and oracle; frequency; 64/128
  node resolutions; candidate families and the 48-per-type cap; acceptance
  margins and `cross_resolution_factor`; `relative_error_tolerance`; the inner
  optimizer; the gauge policy; random seeds for the perturbations.
- **Scope and shared interfaces:** `topology_controller.py` refinement block and
  the controller driver's metrics writer. **Declare before implementing:** the
  driver `run_fourier_topology_controller.py` is shared with the boundary–BIE
  track's validation path. Do not change `MultiRadialFourierState`, the
  objective, the candidate generator, or any solver interface.
- **Required instrumentation (part of this experiment):** the controller driver
  records no solve counts at B0 (B0 §8.4). Add per-pass and total
  `evaluation_count` to the controller metrics, matching the field
  `run_radial_fourier_topology_challenges.py` already writes. Without it the
  compute-matched arm cannot be evaluated.
- **Metrics — all required in the report:**
  1. **Event-selection stability:** which candidate is accepted, per arm, per
     perturbation magnitude, per seed; and the fraction of replays that select
     the same event as the unperturbed run.
  2. **Measurement error:** final training and holdout relative L2.
  3. **Geometry error:** sampled Hausdorff and relative L2 against truth.
  4. **Accepted/rejected event sequences:** the full sequence, not just the
     final count.
  5. **Total BIE evaluations** and per-stage counts; wall-clock only with
     declared concurrency, and never as the primary comparison.
  6. **Rejection reasons, separated by class** — never a single "rejected"
     count. The taxonomy is below.
- **Compute budget and stopping rules:** proposed ceiling — the split case only,
  three arms × two charts × three perturbation magnitudes × three seeds, plus
  the two unperturbed references. Stop early and report if arm A fails to
  reproduce the recorded reference event on the unperturbed replay: that would
  mean the replay harness, not the policy, is being measured.
- **Artifacts:** a fresh directory under
  `results/validation/topology/TOP-001-<date>/`, one subdirectory per
  arm/chart/perturbation, each with `manifest.json` (including the source hash
  set, as B0 does), `metrics.json`, `topology_passes.json`, `trajectory.json`
  and the rejection-class summary. No existing bundle is modified.
- **Decision criteria:**
  - **Adopt** the two-candidate policy if arm C changes the accepted event on
    the split case and improves geometry error without increasing total solves.
  - **Reject** it if arm C matches arm A while arm B improves only through extra
    compute — that would make the finding "buy more refinement", not "allocate
    better", and the next question becomes where the budget should come from.
  - **Investigate further** if event selection is unstable in *both* arms under
    the smallest perturbation: the problem would then be candidate construction
    or the raw scoring, and the track should move to §2.2 rather than §2.3.
- **Owner:** unassigned. **Reviewer:** unassigned.

#### Rejection-reason taxonomy for `TOP-001` metric 6

Every rejected candidate is reported in exactly one class. The reason strings
below are the ones the controller actually emits at B0.

| Class | Reason strings at B0 |
|---|---|
| Representation restriction | `Gauge-fixed polar-angle fit loses contour features`; `Candidate violates topology feature-radius floor`; `unsupported_nested_hole` rejected masks |
| Numerical-resolution failure | `… too close for ordinary cross-component quadrature`; `cross_resolution_margin_failed` |
| Poor objective value | `production_objective_not_decreased` |
| Geometric inadmissibility | `… intersect or touch` |

The fourth class is listed separately rather than forced into one of the three:
two components intersecting is neither a representation limit nor a resolution
failure, and collapsing it into either would mislead.

**A prerequisite check the review must confirm, not assume:** this brief states
that the best-one polishing rule is still present at B0, verified by reading the
working-tree source. If a reviewer finds it has since changed, `TOP-001` should
be replaced rather than patched — pick a still-open question supported by
current evidence, such as `TOP-003`.

---

### TOP-002 — An explicit event trigger (stub)

Replace "propose after every inner stop" with a declared trigger, and measure
what is lost. Candidate triggers: measured objective-stagnation rate, TD
magnitude above a declared threshold within the inspection region, or a residual
structure test. Metric of interest is solves spent on topology passes that
produce no accepted event. **Not written as a contract; not approved.**

### TOP-003 — Candidate construction and its sensitivity (stub)

The corridor family is parameterised by width, angle, offset and mode count, and
B0 shows the retained set differs between charts off pre-split geometries that
agree to `0.14 mm` — six families radial against nine Cartesian. Question:
is the family enumeration, its diversity rule, or the 48-per-type cap the thing
that determines which cuts are reachable? **Not written as a contract; not
approved.**

### TOP-004 — Acceptance on geometry as well as data (stub)

The split case passes acceptance and stops `recovered` with `175.21 µm`
geometry error against a reference at `15.60 nm`. The acceptance rule and the
`relative_error_tolerance` stopping rule are both purely data-side. Question:
would a geometry-aware or resolution-aware stopping rule separate these cases,
and at what cost? **Not written as a contract; not approved.**

## 5. 3D Gaussian Splatting: on the candidate list, not transferred

3DGS-style adaptive representation management — densification by gradient
magnitude, opacity-based pruning, split-versus-clone rules, budgeted primitive
counts — is a natural source of policies for §2.1–§2.4, and it stays on the
candidate list.

It is **not** claimed to transfer. The setting differs in ways that matter and
that this track would have to establish rather than assume:

- 3DGS primitives are additive and independent; boundary components are
  *interfaces* whose admissibility is coupled — clearance, non-intersection,
  feature radius, quadrature resolution.
- 3DGS densification reads a cheap per-primitive gradient; here the analogous
  signal is a topological derivative requiring BIE solves, and candidate scoring
  costs a forward solve each.
- 3DGS tolerates a large, growing primitive count; here every extra component
  raises the dense system's cost and the cross-component quadrature constraints.
- 3DGS has no analogue of the cross-resolution acceptance check.

Any 3DGS-inspired proposal should name which of these it handles and which it
sidesteps, and should reach the same experiment-contract standard as `TOP-001`.

## 6. What this brief does not claim

- It does not claim the polish rule *causes* the split gap. It states that the
  rule decided which candidate was refined, that the margin deciding it was
  `4.7e-06` relative, and that this is testable.
- It does not claim the Cartesian chart is worse than the radial chart. B0 §7
  records why that framing is wrong.
- It does not claim any of `TOP-001`–`TOP-004` is worth running. That is the
  review's decision.
