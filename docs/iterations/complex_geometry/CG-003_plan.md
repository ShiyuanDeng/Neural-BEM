# CG-003 — directed loop search for a real measured-data minimum

Pre-registered 2026-10-11, before new physics evaluation. The user requested
code experiments with numerical results, following the literature/theory
audit, and already approved the existing `feature/shape-frequency-continuation`
branch. This authorizes the run. No branch or worktree is created.

## Question and falsifiable outcome

Can deliberately selected complex loops reach a numerically qualified real
minimum at t=1 from the single prescribed centered start, when CG-002's three
simple doglegs could not? Success requires a complete reproduced path from
that start and independent endpoint physics. Failure means no qualifying
return in this bounded route search; it is not a global impossibility result.

The instrument is unchanged: TG-002 circle observations, contrast 13.3,
1.5 GHz, fixed real center, complex radius q in 50 mm units. Start q0=1.3,
t=0. This deliberately mismatched radius-only family is a continuation
component experiment, not a full 30-case inverse campaign or shape-recovery
score. There is no grid-search initializer, alternate start, truth-based
selection, complex frequency, or change to maintained inverse defaults.

The [derivation](DERIVATION.md) establishes local sheet exchange and the
regular real stationary graph `t(q)=A(q)/B(q)` where B is nonzero. The
[literature audit](LITERATURE_THEORY_AUDIT.md) gives the applicable fold,
monodromy and shape-holomorphy assumptions. Instead of increasing a dogleg's
height, this study applies different route-defined monodromy actions.
Loops centered at real fold values are not claimed to isolate exactly one
complex critical value.

## Frozen complex search

1. Recompute the seed from q0,t0 along `[0,.01i,1+.01i,1]`. Do not import a
   saved CG-002 endpoint as a new start. Require completion, regularity and
   numerical refinement before queueing its endpoint.
2. Use only the 46 qualified real folds of the saved CG-001
   `run-02/census_02.json`, a previously registered data-only diagnostic.
   No new fold scan or loss-based generator selection. For each queued root,
   order candidates by `abs(q_fold-q_root)`, then t_fold, then q_fold.
3. For fold value c, set
   `rho=min(.01,.2*nearest_other_real_fold_distance,.2*abs(c-1))`.
   If rho<1e-5, record a skip; never enlarge a loop to defeat the spacing
   rule. The stem is `[1,1+.05i,c+.05i,c+rho*i]`; follow a 256-segment
   counterclockwise circle once, then exactly retrace the stem to t=1.
   Use the qualified predictor/full-Newton tracker with max parameter step
   .004, minimum step 1e-8 and 20,000 attempts per arm.
   Both production and refined complex trackers additionally require
   Re(q) in [.5,2] and Re(t) in [-2,3], matching the real control's slice;
   retain the inherited |Im(q)|<.5 and transmission denominator guards.
   Record the real-radius and real-parameter extrema of each path.
4. Maintain a FIFO queue of distinct endpoints, with ancestry back to the
   seed. Deduplicate within 1e-7 q units and record nearest-root distances;
   this may merge unresolved close roots and is not a complete orbit count.
   A distinct new edge must pass a half-step replay (max step .002) and
   reverse-path restoration within 1e-7 before its child may be expanded.
   Never restart on a known real fold, independently minimized radius,
   projected complex endpoint, or target chosen from truth.
5. Stop at the first independently confirmed real minimum, otherwise after
   3 expanded roots, 120 discovery loops, or the time budget. Maximum total
   time is 900 seconds, with discovery stopped at 720 seconds to reserve
   time for confirmation and evidence preservation. Confirmation calls and
   failed arms are charged. Candidate ordering and stopping rules do not
   change after seeing endpoints.

## Strong real continuation control

The earlier pseudo-arclength corrector stopped at a regular point. Use the
same scalar stationary curve, evaluated directly as `t(q)=A/B`, to avoid
that Newton residual floor. Trace both q directions from the same q0=1.3.
The declared real domain is q in [.5,2], t in [-2,3]; stop at the first
resolved boundary/denominator obstruction, without reconnecting beyond it.

Adaptive radius steps have maximum 1e-5 and minimum 1e-10, at most 20,000
accepted steps per direction. Evaluate start, midpoint and end. Require
finite real jets, the existing physical pole guard, same nonzero sign of B,
and both half-segment parameter changes <=.001. For each half of radius
length h, require `h*max(abs(B')) <= .1*min(abs(B))` and
`h*max(abs(T')) <= .002`, using sampled endpoint values and `T'=Fq/B`.
Reject and halve otherwise. These are numerical resolution checks, not
certified derivative supremum bounds or proof of no hidden poles.

Repeat both directions with maximum radius step 5e-6. Detect t=1 crossings
only inside accepted consecutive-state brackets and refine `F(q,1)=0`
inside that q bracket. Classify reality, Hessian, stationarity and loss;
such roots remain control results and never seed the complex search.
Record domain stops and crossing agreement rather than treating the
absence of a crossing as a global nonexistence result.

## Qualification and reported numbers

All paths retain accepted and rejected states, route waypoints, counters and
termination reasons. Refine 65 evenly spaced states plus endpoint, minimum
pole-margin state and maximum imaginary-radius state at cutoff+12. Require
relative field/Hessian differences and scaled stationarity <=1e-8. A queued
t=1 root must have `abs(Fq)>1e-6`. Reality requires `abs(Im(q))<=1e-8`;
a real strict radius minimum also requires real `Fq>1e-6` at both cutoffs.
This is numerical qualification, not a formal interval certificate.

Before declaring success, replay the entire successful ancestry from q0,t0
with half parameter steps and separately with cutoff+12; endpoint differences
must be <=1e-7. Refine every accepted state on the successful full path.
Reverse the full parameter path and require return to q0 within 1e-7.
Finally compare endpoint fields against CPU nodal Kress N512/N1024 with both
field disagreement and nodal refinement <=1e-8. An unconfirmed candidate is
retained but cannot count as success or terminate the search positively.

Report the number of discovery loops and distinct endpoints, loop ancestry,
real and imaginary endpoint radius in mm, normalized measured-data loss
`Phi`, relative residual `sqrt(2*Phi)`, Hessian sign, scaled stationarity,
refinement/replay errors, all failures, production/refinement jet counts,
wall time and process peak memory. Compare with the initial q0 measured-data
loss, CG-002's 0/3 real returns, and the real connected-branch controls.
Improved radius-family loss does not imply benchmark recovery or global
optimality. Runtime counts include search and verification, with no speedup
claim against the ordinary inverse solver.

## Implementation, validation and preservation

- `solvers/bem_inverse/complex_paths.py`: isolated opt-in real graph
  continuation and route construction, without experiment/result imports.
- `experiments/benchmark/cg003.py`: frozen search, controls and full receipts.
- `pytest/bem_inverse/test_complex_paths.py`: independent polynomial fold,
  route reversal and denominator/domain refusal checks.
- `results/validation/complex_geometry/CG-003/run-01/`: fresh output only;
  preserve manifests, source snapshots, partial work and exceptions.

Before measurement run focused complex-continuation tests and the TG-002
input seal check. Freeze/hash this plan, source dependencies and census;
record current commit/environment. After measurement, validate saved results,
independently review the interpretation, commit/push this experiment's code,
documentation and results including failures, and verify remote and workspace
status. Concurrent unrelated work must be preserved. Any implementation
correction requires retaining the original run and documenting the change
before a separately named rerun.
