# ON 001 Overnight adaptive boundary inversion

Prepared 2026-10-05. Approval status: **APPROVED by direct launch, 2026-10-05**.
Execution status: **CLOSED — USEFUL PARTIAL RESULT**. Implementation owner: ON-001 Agent 1.
Actual user instruction: `Go ON-001 using docs/iterations/OVERNIGHT_AGENT_TRACKS.md`.
Start: **2026-10-05 01:37:21 UTC**. Deadline: **2026-10-05 09:37:21 UTC**.
No new arms after 05:47:21 UTC; final closeout reserve begins 08:57:21 UTC.
The historical proposed plan below is unchanged; direct launch approves its
bounded conditional execution, not branches/worktrees or other experiments.

## Objective and scope

Produce a substantially faster or more capable cleaned inverse in one
eight-hour campaign. First test reach-informed step clipping and required-accuracy
stopping, then fewer-frequency proposals. A Gaussian displacement with a global
Lipschitz bound is the conditional geometry recovery route. Physical trust/fidelity
control and objective homotopy address different measured failure mechanisms.
The [big-picture brief](02_proposals/01_overnight_research_brief.md) explains the
choices. The [seven-idea integration and mathematical review](02_proposals/02_gaugal_restructuring_integration.md)
records the supplied report's additions and the limits of their guarantees.

Approval of **ON-001** covers the arms, one-time repairs, confirmation and
closeout below. Passing a gate automatically releases its next stage. It does
not approve ON-002 or ON-003, new branches/worktrees, changed observations or an
unbounded successor search. Work in the existing checkout; inspect and retain
its current branch and other users' work.

## Fixed comparison

- TG-002 only: all ten scenes at 0.5, 4 and 13.3, frozen placements and inputs.
- One centred 65 mm circle, localization none, no grid search or restarts.
- Base physics `modal_muller`; base map `certified_spectral`; existing
  `CumulativePolicy`. Material information and catalog stay fixed.
- Keep current independent endpoint field/Jacobian/full-trial derivative
  checks and TG-002 recovery gates: RMS 1 mm, Hausdorff upper bound 2 mm,
  each real-frequency residual 0.003 for these noiseless inputs.
- Compare fresh baseline and candidate under identical workers, CPU threads,
  device, warm-up convention, audit and output boundaries.
- Use one case worker, four frequency threads, one BLAS thread. Keep at most
  one GPU numerical campaign active. Read-only reviewers may work concurrently.
- Every new full inverse starts from the prescribed circle. Archived states
  support diagnostics; they do not count as fresh recoveries.

The fixed eight-case development screen is Aphex at all three contrasts,
hook13.3, circle4, c_shape13.3, kite0.5 and star13.3. It contains the four
failures, a fast control, a high-contrast success and two costly successes.
Algorithm selection uses this declared development screen. Freeze the chosen
algorithm before the all-30 comparison; report all 30 as benchmark/development
evidence, not an untouched generalization set.

## What constitutes success

| Classification | Required outcome |
|---|---|
| Major speed success | Preserve every fresh-baseline recovery; median paired ratio of baseline/candidate time to audited endpoint at least 2; 10th percentile of that paired speedup at least 1; unchanged endpoint gates |
| Major recovery success | Preserve all 26 historical successes, reproduce them in the fresh control where its cap permits, and recover at least two of the four historical failures; median fitting time on common successes at most 1.5 times baseline |
| Combined success | Both major criteria |
| Useful partial result | Retain baseline recoveries and either add one recovery or save at least 20% audited time |
| Closed negative | An allowed repair fails to remove a recovery regression, or no new recovery and less than 20% time saving; closure after a prescribed screen is labelled screen-negative |
| Incomplete | Deadline or unresolved qualification prevents an assigned stage from finishing; full-suite success claims require all-30 coverage |

Use paired per-case times, not a ratio between two independently computed
medians. Report fitting and total times separately. For timing distributions,
use common recovered cases; show failures, timeouts and total suite cost
alongside them. A baseline failure is never credited as a fast reconstruction.
If the fresh baseline does not reproduce an old success, report the mismatch
and withhold a clean retention claim until its cause is resolved within budget.

## Arms and frozen initial settings

**B, baseline.** Unchanged current recipe, with added phase timing and receipt
capture shared with every arm. Do not bundle an unmeasured optimization into B.

**G, reach-informed normal clipping.** Keep the existing finite map and all
final validity checks. At each newly accepted curve, estimate reach using
the pair quotient `|x-y|^2/(2*dist(y-x,T_x))`, including the local curvature
radius limit. Evaluate on 1024 and 2048 uniformly spaced parameter samples,
with analytic Fourier tangents/curvatures. Omit identical pairs; use the
curvature limit for unresolved near-diagonal cancellation and record its
threshold. A zero normal chord component has infinite quotient. Take the
smaller finite positive estimate; if the estimates differ by more than 10%,
allow one 4096-sample refinement and again take the smaller. Cache by exact
accepted coefficients and resolution. Charge the entire estimate, including
any device transfers. No valid positive estimate means fall back to the
ordinary step cap and log proxy-unavailable; never invent a radius.

The sampled radius is in stored solver length units. Convert it to metres
as `rho_m=length_unit_m*rho_est`, matching the normal LM coefficients. For
real normal harmonics use `S=|c0|+sum hypot(c_cos,c_sin)` in metres and scale
the whole LM direction by `alpha=min(1,0.8*rho_m/S)` after the unchanged
baseline coefficient cap.
Handle S=0 directly. Recompute predicted decrease for the actual scaled
coordinates. Reuse the estimate during retries at the same base. This is a
**heuristic reach proxy**, not a lower-bound certificate. Even exact raw
normal-graph admissibility does not certify the projected Fourier curve.
Keep projection, area, regularity and simplicity checks active and logged.
Do not assert exact K+M storage bandwidth or a fixed reach floor across steps.

G initially retains B's stopping and full frequencies to isolate clipping.
One screen repair is allowed: replace the factor 0.8 globally by 0.4 if
postprojection geometry refusals persist. If shrinking only removes progress,
close G and consider F under the branch below. A zero-refusal result alone
does not qualify G for adoption.

**E, required-accuracy exit.** At accepted full-real-catalog states, explicitly
check the maximum normalized per-frequency residual. When it is at most
0.003, request the current endpoint audit and terminate on a passed audit.
No truth geometry enters this decision. If the audit fails, continue from the
same accepted state and charge the audit; retry only after the maximum
residual halves or the storage/physics resolution changes. If E loses a
development-screen recovery, allow exactly one stricter global variant at
0.001. If that also loses a recovery, disable this shortcut for subsequent
arms. A geometry gate failure is a scored failure, not permission for an
online truth-dependent continuation.
Reserve at least 10 seconds of the aggregate audit allowance for a terminal
audit before performing optional early audits. If insufficient allowance
remains, disable further early checks and continue ordinary fitting.

**GE.** Combine G and E only after their isolated screens retain B's recoveries
and each shows useful progress: a new recovery or at least 20% less audited
time. If only one qualifies, carry that arm forward. A mechanistic improvement
in refusal time can release F or R, but does not by itself qualify GE.

**W, working-frequency proposals.** Add W to the selected B/G/E/GE recipe,
recording that parent explicitly; compare its marginal gain against that
parent. Leave damped stages unchanged. For a 19-frequency real
stage, choose sorted catalog indices 0, 4, 9, 14 and 18. Form the proposal
Jacobian and initial trial screen on these five. Expand promising candidates
to every active frequency, and apply the original production/refined loss
decrease and per-frequency numerical gates before committing acceptance.
Reuse selected-frequency evaluations when expanding; bill all new work.

Select two additional frequencies with the largest normalized residuals from
the last full accepted-state evaluation, excluding existing anchors. If a
full objective rejects a subset-improving trial, add the omitted frequency
with the largest increase in squared normalized residual. Retain added
frequencies to stage end; cap at nine, then use all 19. Full checks cannot
silently adopt subset weights. Rebuild the model on working-set changes.
At maximum full-real residual below 0.01, use all 19 for final polishing.
Thus the initial proposal set has seven frequencies: five anchors plus two
residual-selected entries. The subset model retains the original relative
weights renormalized to sum one. Its predicted decrease is an approximate
model for full loss; the acceptance objective always uses the original full
weights.

**R, physical trust and bounded fidelity.** This is a conditional arm, not an
obligatory extra campaign. Retain the selected E choice but initially disable
G and W to isolate this mechanism. Use existing
physical normal-displacement measurement to scale the entire LM direction.
Initial maximum displacement radius 6 mm; lower limit 0.05 mm; upper 12 mm.
In R, use actual/predicted full-objective gain. When combined with W, divide actual full loss
decrease by predicted decrease of W's declared subset surrogate; this ratio
is an approximate-model diagnostic, not a full Gauss–Newton prediction.
Shrink radius by half on geometry
refusal, numerical refusal or ratio below 0.25; increase by 1.5 up to the
ceiling when an accepted step reaches at least 80% of the radius and its
ratio exceeds 0.75. Otherwise retain the radius. Nonpositive predicted gain
rebuilds the model/increases damping and cannot justify radius growth.

Keep the current initial trace pair. When the retained base is qualified but
a candidate is not, shrink/retry first. After two numerical refusals at the
same accepted state, test the next trace pair with both cutoffs raised by 32
and existing workspace margins retained. Allow at most two such promotions
per stage. An inaccurate retained base must qualify at a finer pair before
another proposal. Every promotion rebuilds the production linearization and
invalidates incompatible caches. At the ceiling reject inaccurate trials;
if none qualify, return an accuracy-limited outcome. Never lower a tolerance.

**Combined candidates.** Combine only separately qualifying mechanisms, with
a charged eight-case combined screen. G and R, if combined, apply the tighter
of their caps and recompute the model for that step. Record names explicitly
(for example GEW or EWR); do not label an untested combination the winner.

## The first results and automatic branches

First run B, G and E on the eight-case screen after focused validation. Compare
G and E independently, then combine qualifying changes. Unless a major target
already releases confirmation, screen W on the retained parent. Capture plots and a concise result table as each
arm completes; do not wait until morning to expose progress.

| Observation | Required next action |
|---|---|
| G adds a recovery or saves at least 20% audited time, retaining B recoveries | Eligible for GE/W and full confirmation; if already a major result, confirm now |
| G cuts invalid-proposal time at least 30% but gives no useful endpoint gain | Retain the diagnostic; do not promote merely because refusals vanished |
| More than half of G's nonzero proposals on a stalled failed case have alpha below 0.1 | Release F if clipping makes no useful accepted progress; do not keep shrinking indefinitely |
| E retains every B screen recovery and saves at least 20% audited time | Keep E; test GE if G qualified, otherwise W |
| E retains recovery but saves less than 20% | Record partial mechanism evidence; omit E from the default finalist |
| E loses a B recovery | Try the one 0.001 repair; otherwise close E |
| W retains parent screen recoveries and saves at least 20% median audited time | Eligible for combination and full confirmation |
| W loses a recovery | One repair: use nine evenly spread anchors, no two-step bursts; otherwise close W |
| Repeated numerical refusals or poor model gain block an otherwise qualified path | Release R if F was not released |
| R adds a screen recovery or saves at least 20% audited time without losing successes | Eligible for combined screen and full confirmation |
| R changes no recovery and increases common-success time by more than 50% | Close R; retain only evidence |
| A combined candidate already satisfies a major screen target | Freeze it and move directly to all-30 confirmation; skip new mechanisms |
| Failures remain, and invalid geometry/projection consumes at least 30% of a failed case's fit time | Release F below |
| A qualified base at damped-to-real handoff cannot obtain a qualified decreasing real-objective step | Release H below if neither F nor R was released; do not compare loss values from different objectives |
| W is useful, but full acceptance consumes at least 50% of its fitting time | Release W2 below if no other conditional arm was released |

At most **one of F, R, H and W2** runs. Priority is F, then R, H and W2 when
several criteria hold. A screen can close a line; it cannot establish the
all-30 headline. If no branch criterion holds, confirm the best qualifying
existing arm or close without another invention.

## Conditional Gaussian displacement

**F** changes the finite geometry map and replaces G's reach cap. Retain the
base controller and unchanged baseline coefficient cap, plus E if E qualified.
Keep the same normal Fourier coordinates and
state bands. At an accepted curve, use equally spaced arclength control
points, count `max(32, 2*(2*M+1))`. Interpolate prescribed boundary vectors
`(h_m/length_unit_m)*n` with a Gaussian ambient vector field plus a constant
translation, keeping centres, width and field displacements in solver units;
width is twice the median neighbouring control-point distance. Use a
relative diagonal ridge of `1e-10`. For each Cartesian component solve
`[K+ridge*I, 1; 1^T, 0] [w;b] = [v;0]`, with normalized kernel diagonal one,
and field `sum_j w_j exp(-|x-x_j|^2/(2*width^2)) + b`. Refuse a condition
estimate above `1e12` or control-point velocity error above `1e-4` relative
to the nonzero prescribed velocity norm. Record both quantities. Handle the
zero vector directly. Do not silently change the intended velocity.

Compute dimensionless `C=exp(-1/2)*sum_j norm(w_j,2)/width` and
`alpha=min(1,0.8/C)`, with C=0 handled directly. Retain the original fitted
field `v_a` and apply `phi(x)=x+alpha*v_a(x)` exactly once; do not additionally
rescale its stored momenta/translation. Record `a_used=alpha*a` as the actual
LM coordinates. Do not integrate an ODE.
The constant translation contributes nothing to C. In exact arithmetic this
raw map satisfies `|phi(x)-phi(y)| >= 0.2*|x-y|` everywhere. Interpolation
is linear in the direction, so this scaling preserves its fitted relation.
Recompute the LM prediction for the scaled coordinates.

Perform the existing spectral arclength projection and centred base
correction so a zero update returns exactly the same stored curve. The raw
map's guarantee does not survive projection automatically. Validate the
resulting stored curve with all current checks; record raw-map bounds,
projection displacement and final validity separately.

Differentiate the complete finite map, including interpolation and
projection, at zero for the local model; include active scaling when checking
finite nonzero-direction derivatives. Handle clipping kinks with declared
one-sided/directional checks, not a fictitious smooth derivative. Batched geometry-only differences are allowed; the physical
Jacobian still uses the reciprocal derivative. Do not reuse an old tangent
unless equality is actually established. Reuse the existing `prepare`,
`velocities`, `measure`, `trial` protocol and implement the new numerical
class inside `solvers/bem_inverse/`.

Qualify on screen initial/accepted states and then run the screen from the
centred start. Allow one repair: halve the Gaussian width globally if the
interpolation condition/error gate fails. No width search or RK4 rescue is
allowed. If complete-trial derivatives remain unqualified after one focused
implementation correction, close F. If F loses a baseline recovery, is more than 2x slower on
common successes, or projection reproduces the same obstruction, close F.
If F retains baseline recoveries and (adds a recovery or saves at least 20% audited time),
take it to full confirmation. If refusals vanish but clipping prevents useful
progress, close F; the continuum guarantee alone is not a pipeline result. Combine it
with W only if W separately qualified and remaining time allows the screen.

## Conditional alternatives

**H, objective homotopy.** Use the same four prefix frequencies in both
catalogs. Retain selected G/E rules and use all
stage frequencies. Replace the abrupt transition by
`L_t=(1-t)*L_damped + t*L_real`, initially at t=0.25, 0.5, 0.75, 1.
Preserve original normalization within each catalog; differentiate this
actual objective. Each trial is accepted only against the same t at base and
candidate. On exhaustion without a qualified decrease, retry halfway between
the last successful t and the failed t from the last successful checkpoint,
retaining consumed work. Permit one bisection per failed increment, minimum
increment 0.125; another failure closes the transition. Total transition work cannot
exceed the original undamped-stage quota. Then use the unchanged full-real
suffix. This creates no observations at a new physical damping value.
Advance H only if it retains parent recoveries and (adds a recovery or saves
at least 20% audited time). A lower failure residual without such improvement
is diagnostic evidence; close H after the screen. Do not add another damping
catalog or restart.

**W2, two-step speculative work.** Up to two locally accepted working-set
steps may occur before full-objective validation. Inherit qualified W and its
declared parent. Retain the last full
checkpoint, including curve, tangent/model state, damping and ledger.
The full production/refined gate compares that checkpoint with the block
endpoint. A failure rolls back numerical state but keeps all consumed work
and elapsed time. Expand to nine/all frequencies and reduce burst length to
one after a failed block. Only fully checked states may be returned or used
for an early exit. Close W2 if rollback exceeds 30% of fitting time or it
loses a control. Advance only if it retains parent recoveries and (adds a
recovery or saves at least 20% audited time). Otherwise close it after the
screen. This arm is approximate optimization, not identical decisions.

## Eight hour allocation and hard stops

| Phase | Maximum minutes | Deliverable |
|---|---:|---|
| Freeze inputs, baseline screen, instrumentation | 30 | Matched control receipts |
| G and E implementation, validation and isolated screens | 80 | First geometry and speed results |
| W and at most one of F/R/H/W2, including qualification | 95 | A stronger candidate or a closed branch |
| Allowed repairs and combined screen | 45 | One frozen finalist |
| Fresh B and finalist on all 30; confirmation timing and selected independent audits | 170 | Complete comparison |
| Contingency within the global deadline | 20 | Repairs or completion, never new mechanisms |
| Required regression checks, gallery, report, commit and verified push | 40 | Reviewable morning output |

Eight hours is the hard overall ceiling, including implementation and reporting.
Unused phase time may fund an already declared later phase. Stop opening new
arms at minute 250 and reserve the final 40 minutes for closeout. Each fit is
capped at 120 seconds and 13,412 existing work units; audits have a separate
aggregate 30-second case cap covering initial, optional early and terminal
audits. Keep failures and budget stops. A cap may make a difficult
recovery inconclusive; do not raise it silently.

The complete paired campaign's nominal case-cap allocation is 150 minutes;
checks between numerical calls can overshoot a case deadline and must be
reported against the global ceiling.
Use the remaining confirmation allowance for two extra sequential timing
repeats on circle4, kite0.5 and star13.3 and independent finer nodal checks
on every newly recovered hard case. Start only repetitions/audits whose
declared remaining caps fit. If a new recovery lacks its independent check,
label it provisional. If repeated timings cannot finish, report the single
paired comparison without a repeated-timing claim.

Select the finalist by retained screen recovery first, additional recovery
second and audited time third. No per-scene choice of algorithm by truth.
The selected single recipe, including any truth-free rollback/fallback rule,
must be frozen before the complete suite. Diagnostic and development costs
are reported separately from deployment time and also included in night totals.

## Implementation and validation map

| Area | Maintained location | Intended work |
|---|---|---|
| Early exit and policy | `solvers/bem_inverse/policy.py`, `runner.py` | Full-real data criterion, charged audit/continue |
| Trust, fidelity and checkpointing | `continuation/lm_backend.py` | Opt-in gain control and backend-owned modal response |
| Working frequencies | `Objective` in `continuation/lm_backend.py` | Subset proposal model, exact full acceptance, reuse and accounting |
| Modal stage profile | `modal_muller.py` | Declared cutoff pairs and receipts; current default unchanged |
| Reach proxy and clipping | Geometry helpers and `continuation/lm_backend.py` | Cached estimate, harmonic bound, actual-step model |
| Gaussian displacement | New module under `solvers/bem_inverse/`, `geometry_selection.py` | Complete finite map and derivative |
| Campaign and scoring | `experiments/benchmark/` | Small ON-001 driver, truth separation, gallery and report |

Required focused checks include: subset improvement with full loss increase
must reject; promotion rebuilds the Jacobian; unresolved retained bases cannot
continue; early exit uses all real frequencies; failed audits remain charged;
rollback preserves total work; complete-map FD covers real/damped fields;
zero displacement preserves the curve; invalid/underresolved projection refuses;
positive circle-normal displacement expands radius; harmonic amplitude bounds
hold; Gaussian momenta satisfy the raw Lipschitz bound. Sampling-based checks
are implementation tests, not a proof that the reach proxy is conservative.
Reuse the existing package, modal and resolution/resume tests. Run the package
README's validation suite and affected shared-continuation/solver suites for
changes at those layers. Numerical checks must pass before dispatch or commit.

Record phase-separated fit/audit timers, accepted/refused proposals, maximum
full residual, model gain ratio, active frequencies, fidelity level,
certificate time, projection time, work and all fallback events. Log coefficients
and clipping factors, reach-proxy resolution/time, Gaussian momenta norm bound,
raw-versus-projected displacement and postprojection refusal reason. Log
or reproducible directions for refused proposals so first-failure analysis is
possible. Keep source/config/input hashes and the original failure evidence.

## Closeout and subsequent direction

After each completed new experiment batch, validate, commit and push its code,
documentation and results, including failures; verify remote HEAD and working
tree. Do not mutate numerical sources while a batch is being measured.

Publish results under `results/validation/cleaned_interfaces/ON-001/`; open
iteration 31 with the results and update the track handoff. Deliver the all-30
table, boundary gallery, time-to-audited-output plot, the retained recipe and
an explicit success/partial/negative/incomplete classification.
For a screen-negative closeout, retain the 30-case inventory and mark cases
not launched as such; do not imply complete benchmark execution.

On a major success, **close ON-001** after confirmation. Recommend a later
noise/material/measurement generalization study instead of further overnight
tuning. On Gaussian-map success, propose the finite-map/projection error analysis needed for
the scientific claim. On speed-only success, consider ON-002 for direct
GauGal parity. On a closed negative, name the failed mechanisms and stop this
contract. Ewald, shape-Taylor, T-matrix, IBIM, atlas and Krylov work are not
extra ON-001 branches; their disposition is in the integration review.
Any such later experiment needs its own named approval.


## Actual closeout

Closed 2026-10-05 03:19:15 UTC (101.91 min elapsed). All 30 B/E pairs, declared repeats and uncontended circle replacement completed. 26/30 retained, no additions; median 1.545838x. [Results](../iteration_31/01_results.md). The pre-registered bounded decision tree above is preserved.
