# Overnight options for a faster and more capable inverse

Prepared 2026-10-05 for the user's request for visible overnight progress.
Reviewed checkout: `6f2c1408`, existing `feature/shape-frequency-continuation` branch.
This is a research recommendation. The accompanying experiment contracts are
proposed; no numerical experiment was performed while writing this brief.

The recommendation is to spend the next night building an adaptive BEM inverse
that clips steps using the current geometry, stops at the required reconstruction
accuracy, and spends fewer frequency solves on proposals. Start with a reach
proxy; if clipping prevents useful progress, replace the finite normal update
with a Gaussian displacement whose raw map has a global injectivity bound.
The ambition is a visibly faster pipeline or additional recovered hard shapes.
A few percent saved in certificates is a supporting improvement.

There are three separately bounded alternatives:

- **ON-001, recommended:** improve our pipeline in an eight-hour campaign,
  with speed and recovery branches under one conditional contract.
  [Execution plan](../03_plan.md).
- **ON-002:** put an adapted GauGal and our BEM on exactly TG-002, then pursue
  direct parity or a volume-to-boundary hybrid. This is its own eight-hour
  alternative because the GauGal adapter is substantial work.
  [Comparison plan](../../../CI-SPD/iteration_01/03_plan.md).
- **ON-003:** test Ewald-style geometry/frequency factorization of the full
  Müller service. This is the operator novelty bet, with a forward-only
  eight-hour feasibility contract before any inverse integration.
  [Operator plan](../../../CI-SPD/iteration_01/04_ON003_ewald_plan.md).

The [seven-idea integration review](02_gaugal_restructuring_integration.md)
maps every suggestion in the supplied report into these plans or a later
research direction, and corrects the assumptions that affect execution.
Approval of a named ID would cover its specified conditional stages.
The experiment owner should follow the decision tree through confirmation and
closeout, without stopping after the first result to ask what to do next.

## What would count as visible progress

These are proposed targets, not forecasts.

| Outcome | Overnight target | Stretch target |
|---|---|---|
| Faster current pipeline | Preserve every baseline recovery; at least 2x faster median time to an audited endpoint | Median fitting below 10 seconds and at least 3x faster audited endpoint time |
| Better inverse | Preserve the 26 current recoveries and recover at least two of the four failures | 30/30 from the same centred circle |
| Direct GauGal parity | Same information; BEM retains its reference successes and recovers every case GauGal recovers; paired median total-time ratio BEM/GauGal at most 1.25 | BEM faster with sharper qualified shapes |
| Combined method | A deterministic hybrid beats both constituent methods on recovery or audited time | Same recoveries at materially lower time than either constituent |

One extra recovered case is useful progress and should be retained; two extra
cases is the proposed threshold for calling the night a substantial recovery
advance. Fast failed runs do not improve the speed score. The morning report
must show the 30-case inventory and actual boundary overlays for every executed
case, with screened-out or unrun cases explicit.

## Why this is the right scale of ambition

Three materially different implementations recover the same 26/30 TG-002
cases. The modal failures are Aphex at all three contrasts and hook at 13.3.
Nodal promotion to N1024/2048 moved these four further but recovered none.
The current problem therefore merits changing how the inverse takes steps
and allocates work. [PC-001](../../../../../results/validation/cleaned_interfaces/PC-001/README.md)
and [PC-002](../../iteration_28/05_results.md).

There is also room to stop earlier. The noiseless stage loss tolerance is
`1e-14`, whereas benchmark recovery allows per-frequency residual 0.003.
Reading saved M1 histories found an earlier full-real-catalog accepted/base state
meeting a sufficient data-fit bound in every recovered case. The arithmetic
suggests about 40% of their combined fit time lies after those states.
Their geometry and endpoint audits have not been checked at those earlier
states. This makes an excellent first experiment: a direct test of whether
we are spending time on accuracy the benchmark does not require.

The bound uses the actual equal-frequency objective:
`L = sum(r_f**2)/(2*19)`. Thus `L <= 0.003**2/(2*19)` implies every production
frequency residual is at most 0.003. The proposed implementation checks each
frequency explicitly and requires the endpoint audit; it does not rely on a
scalar loss as a shape certificate. The read-only estimate is motivation,
not a speedup result.

Reproduction uses `results/validation/cleaned_interfaces/PC-001/M1/runs/`:
take the earliest `history[].work.seconds` in `release_*.json` and
`fixed_*.json` with `history[].loss` below the stated bound, including stage
entry rows. Compare with `fit_result.json.fit_and_localization_seconds`.
The 26 qualifying cases total 786.55 seconds of fitting, of which 316.69
seconds follow those states. Kite0.5 reaches the bound at 19.70 seconds
against 87.74 seconds final fitting. This is read-only receipt arithmetic.

For GauGal, the existing three-cylinder pilot measured 0.81–1.26 seconds of
optimization. Our good cylinder control took 1.93 seconds, while two difficult
paths took 36 and 348 seconds. This suggests that avoiding unsuccessful work
is as important as accelerating kernels. Those numbers concern a different
single-frequency acquisition and cannot serve as a TG-002 parity measurement.
[Existing comparison](../../../CI-SPD/01_results.md).

## The options and their research value

| Option | What changes | Why it could deliver a large gain | Position in the night |
|---|---|---|---|
| Reach-informed step clipping | Cached reach proxy and harmonic amplitude bound | Avoids repeatedly proposing geometrically excessive steps | First geometry ablation; final validity checks stay active |
| Stop at the required accuracy | Full-catalog stopping and endpoint audit | Removes long polishing tails | First speed ablation, independently of clipping |
| Use fewer frequencies to propose steps | Small Jacobian/cheap proposal screen, full-data acceptance | Avoids many of the 19-frequency evaluations and derivatives | Main speed route |
| Couple physical step size and numerical fidelity | Gain-ratio trust control; bounded modal resolution response | Replaces fatal inaccurate proposals and repeated backtracking with informed retries | Conditional reliability route |
| Gaussian Lipschitz-bounded displacement | New finite map, same Fourier state and physics | Globally injective raw moves, composed over the inverse path | Bold conditional recovery route when reach clipping stalls |
| Adapt the damped-to-real objective transition | Blend the two existing objectives | May avoid a bad handoff when a fully resolved path still stalls | Predeclared fallback, only if that mechanism appears |
| GauGal to BEM hybrid | Volume evolution followed by a sharp boundary inverse | Combines a flexible volume path with accurate boundary refinement | ON-002, after its adapter works |
| Ewald geometry/frequency factorization | Shared geometry moments, frequency multipliers and matched near terms | Analytic derivatives and amortized multi-frequency physics; possible GPU/3D path | Separate ON-003 forward feasibility |
| GPU spline, analytic GPU tangent, certificate reuse | Cheaper implementation of existing work | Useful supporting gains | Only when receipts identify the relevant cost |

Geometry clipping, inexpensive frequency proposals and required-accuracy
stopping form a coherent pipeline. The Gaussian map changes the finite
deformation mechanism. The hybrid changes the inverse representation, while
Ewald changes the forward operator architecture. These are distinct bets;
we should complete one bounded comparison rather than open all of them at once.

## The speed route

Keep all existing damped-prefix frequencies. In the 19-frequency real stages,
start with five spread anchors, including both endpoints, plus the two omitted
frequencies with the largest current residuals: seven initially. Build the
proposal Jacobian on that set. Evaluate a cheap proposal there, then evaluate
the full real catalog before accepting it. Reuse already computed selected
frequency work. Add a frequency when the full-data test exposes what the small
set missed. Near termination, return to all frequencies.

This deliberately changes proposal directions. Its protection is the full
objective and numerical-accuracy check at accepted states. If full acceptance
becomes the dominant cost, the plan allows short, explicitly speculative
two-step bursts with rollback to the last fully validated state. Every wasted
solve and rollback is charged. This is a genuine algorithmic change, with an
opportunity for a several-fold gain; it is not described as exact cache reuse.

The existing physical step cap, predicted-decrease logging, refined caches and
checkpoints give this route a head start. A current-curve accuracy controller
can shrink a bad step before paying for a larger wavefield system. Promotion
has a finite ceiling. The target is reliable decrease per second.

If it succeeds, freeze the controller, run the complete comparison and close
the speed experiment. Do not add an atlas, a new optimizer or more thresholds
after already reaching the target.

## The pipeline leap

Start by scaling each normal direction so its harmonic amplitude bound fits
inside 80% of an estimated current reach. This turns geometric scale into an
explicit step limit. A sampled reach is a proxy, not a certified lower bound;
projection and final admissibility checks remain active. Measure whether
this reduces total time and improves progress, not just the rejection count.

If the reach cap starves the difficult path, fit the same normal direction
with `v(x)=b+sum p_i exp(-|x-q_i|^2/(2*sigma^2))` and use `x -> x+v(x)`.
Scale the momenta so `exp(-1/2)*sum ||p_i||/sigma <= 0.8`. The exact raw map
then retains at least 20% of every pair separation. Repeated compositions
allow large cumulative deformation without an ODE integrator. Keep the same
unknown normal coordinates initially, so this tests the finite map rather
than a larger parameter count.

Fourier projection can break that raw-map guarantee. Its validity checks and
complete-map derivative remain required. The normal map is not exactly
band-limited at geometry-band plus update-band on a generic stored curve.
These distinctions are part of the proposed method, not reasons to defer it.

The compelling result would be more qualified recovery with fewer invalid
proposals. A smoother animation alone is insufficient. If the first screen
shows that the Gaussian map avoids folds but reaches the same inaccurate or wrong
endpoint, record that result and close the mechanism instead of spending
the night tuning Gaussian widths.

Diffeomorphic shape optimization is established. The proposed contribution
is its specific complete finite update and its interaction with modal
accuracy and accepted inverse progress in difficult transmission shapes.
The novelty case becomes stronger through a mechanism, an ablation and a
benchmark gain. [Hiptmair and Paganini](https://doi.org/10.1515/cmam-2015-0013).

The supplied GGB hard-case timing makes this a compelling experiment, but
320 seconds is the non-physics remainder, not a measured geometry timer.
Its 92% cannot be transferred to all TG-002 cases. That is why required-accuracy
stopping and frequency work stay in the plan even after adding reach clipping.

## The larger operator bet

ON-003 tests whether reusable geometry moments and wavenumber-dependent
diagonals can reproduce the complete Müller service. Its first result is a
circle/curved-state accuracy and cost table, with real and damped frequencies,
both media and the actual flux-coordinate basis. A flat single-layer match
alone is insufficient. The near erf symbol is a useful starting formula,
but its infinite-time propagating limit in the report is incorrect; outgoing
shell treatment, local curvature terms and close nonlocal interactions must
be handled consistently.

If the full operator is accurate and fast, qualify its shape derivative and
close forward feasibility before proposing inverse integration. If the
flat approximation fails on concave curves, permit one complete-near numerical
correction. If that is accurate but slower, close with the measured crossover.
The stronger claim would be the complete qualified factorization and its
derivative, with geometry reused across both media and frequencies at a fixed
shape. It would not be a claim to have invented Ewald splitting.

Shape-Taylor screening, T-matrix sensor reuse, operator atlases and Krylov
recycling remain follow-on options. IBIM/KFBI is the longer route to a sharp
implicit interface; its transmission accuracy and regular zero-set geometry
need separate work. The integration review records a decision for every idea.

## The strongest theory claim to pursue

The unfinished question in the modal vision is how numerical wavefield error
and finite-deformation error affect a useful shape step. MA-006 already showed
that acceptable field/Jacobian error can coexist with a noticeably inaccurate
local step. Its missing component is a cheap prospective estimator.
[Modal vision](../../../../reports/fully_modal_muller_atlas_research_vision.md)
and [MA-006](../../../modal_atlas/iteration_07/01_results.md).

A successful overnight method could motivate the claim:

> An adaptive modal boundary inverse coordinates frequency work, finite
> deformation and numerical accuracy to obtain more reliable shape recovery
> at a lower cost per independently qualified reconstruction.

The overnight evidence can establish a useful algorithm and a measured
mechanism. A later theoretical phase would formalize directional error and
acceptance conditions. Existing goal-oriented Gauss–Newton theory is a
starting point for that work. [Kaltenbacher, Kirchner and Veljović](https://arxiv.org/abs/1309.6800).

The scalar convergence-radius chain already failed to provide a useful
handoff rule, generic atlas band selection already received negative tests,
and relaxed BIE already received controlled tests. Complex-geometry winding,
global convexification and another compression atlas are lower priorities
for this night because they require more new machinery before a full inverse
can improve. [TR closeout](../../../theory_radius/iteration_02/01_results.md).

## What matching GauGal actually requires

ON-002 compares on TG-002 with the same paired observations and the same
centred initial object. It ports the useful GauGal execution structure:
fixed-domain kernels, separable Gaussian projections, FFT propagation and
batched warm starts. It does not rerun retired scene sets.

The main adapter issues are concrete. TG-002 contrast is the material ratio,
so 0.5 means volume contrast minus 0.5; the released nonnegative material
clamp cannot represent it unchanged. Use known-contrast occupancy
`chi=(contrast-1)*occupancy`, with occupancy in [0,1], to match BEM's material
information. Share one occupancy across frequencies. Generate physical
operators for the actual TG acquisition, including its existing complex
frequencies. Preserve the paired mask.

The old 64-pixel grid cannot simply be copied into a millimetre-accuracy
benchmark. Grid refinement, contour extraction and its independent BEM audit
all count in the result. The resulting comparator is explicitly an adapted
GauGal, not a reproduction of the released cylinder timings.

If this adapter qualifies quickly, the hybrid becomes attractive: evolve the
same centred occupancy, extract one boundary by a fixed rule, and let BEM
finish. The volume phase is part of the charged inverse; there is no grid
search or selection among starts. If a cheap volume phase cannot produce a
useful qualified contour, close that branch.

## How to direct work after the first result

| First result | Immediate next action | When to close |
|---|---|---|
| Reach clipping retains recovery and gives useful time/progress gains | Combine only with independently qualifying stopping/frequency changes | Confirm and close if the major target is reached |
| Reach clipping makes most useful directions tiny | Try the bounded Gaussian displacement | Close if projection or global momenta clipping recreates the obstruction |
| Required-accuracy stopping preserves recovery | Add working-frequency proposals | Close the shortcut if the one stricter threshold still loses a control |
| Speed arm reaches 2x with retained recovery | Confirm all 30 and repeat matched timings | Close as a speed success; stop adding mechanisms |
| Trust/fidelity arm recovers new hard cases | Test its isolated and combined versions on all 30 | Close as a recovery advance once reproduced |
| Geometry refusals still dominate | Run the specified Gaussian update | Close if projection recreates the problem or cost overwhelms benefit |
| Accurate path stalls at damped-to-real handoff | Try the specified objective blend | Close if it merely adds iterations without recovery |
| Full-data checks dominate an otherwise useful speed arm | Try two-step speculative bursts with rollback | Close bursts if rollback exceeds 30% of fitting time |
| GauGal is faster and equally accurate | Test charged volume-to-boundary refinement | Adopt the faster baseline if refinement adds no value |
| BEM matches adapted GauGal | Complete timing and quality comparison | Close parity; use the result in the project claim |
| Ewald full fields qualify and total cost improves | Qualify complete shape derivatives and repeat timings | Close ON-003; propose a later inverse test |
| Ewald qualifies only with expensive local/grid work | Measure and report the full cost | Close as accurate but slower; do not start a 3D rewrite |
| Neither route improves the first screen | Apply only its one specified repair, then stop | Close with preserved negative evidence and a definite decision |

ON-001, ON-002 and ON-003 spell out the numerical choices, time limits and terminal
states. Their thresholds select development algorithms, never truth-based
actions inside a fit. The morning output should contain a completed method
comparison, a gallery, timings, failure explanations, tested code and pushed
evidence. An unfinished run should appear explicitly as unfinished.
