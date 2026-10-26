# AN-001: full-trace anchoring on recorded shape changes

**Questions:** Can an earlier LU factorization solve nearby full trace systems
accurately and cheaply? Does any solve saving survive matrix/wave construction?
Do coefficient step bounds cover the actual useful shape changes?

Finalized 2026-10-26. User decisions: investigate anchoring separately from
compact modal reduction; combine Haibing 5 with measured error control from 8;
measure item 3 on unchanged moves; report empirical accuracy and exact fallback.

**Status:** scope agreed; implementation and measurements not started.
The user requested these experiments and accepted the remaining scope. No
separate approval naming AN-001 is required by the repository instructions.

The immediate instruction is to finalize this plan. It records the agreed
experiment for execution; writing it does not mean results already exist.
Working branch: `organised`; reference source snapshot: `4c5fa8baf`.

## Ranking and combination

| Priority | Haibing items | What happens in this plan |
|---:|---|---|
| 1 | 5 + measured parts of 8 | Compare full current-system solves using a reference LU with fresh current LU; measure fields, sensitivities, residuals and full cost |
| 2 | 3 | Measure two existing coefficient bounds on the same shape changes; keep their cost and conclusions separate |
| Deferred | 4 | Incremental matrix differences need their own accuracy/cost question; not needed for this full-matrix comparison |
| Deferred | New part of 2 | Singular-weight extraction changes assembly and would obscure the solve-reuse question |
| Deferred | 11 | Riccati/ItI shape flow needs substantially different mathematics |
| Excluded | 6, 7 | No Schur reduction, compact modal basis, reduced trace space or tangent-enriched ROM |

The [directions document](../../../directions.md) retains all 13 families,
their updated ranking and previous failures. This plan schedules only the
first two rows above, with no automatic expansion to other ideas.

## What anchoring means here

The unknown boundary traces and the current matrix keep their full dimension.
At a reference curve, store the LU of its matrix. For nearby curves, assemble
the actual new matrix and use that reference LU as a right preconditioner.

This changes the A4 and B7 linear solves in the [A1–C12 chain][chain]. A1–A3
construction remains exact at the working resolution. This experiment therefore
tests factorization reuse, not an approximation that avoids new matrix assembly.

The [BIE-006 operator model][bie006] and [LAU-003 reduced traces][lau003] remain
prior evidence. Their failures must not be presented as new results, nor
their different constructions silently substituted for this one.

## Frozen inputs: 15 changed-curve systems

Use the saved [GU-002 CUDA-slider run][gu002], `hook__c13.3`, under:

`results/validation/cleaned_interfaces/GU-002/slider/runs/hook__c13.3/`.

In each stage file take `history[0]` as the reference curve and `history[1:4]`
as three subsequent accepted curves. Preserve coefficients exactly. Each
block holds storage band, trace dimension and physical parameters fixed.

| Stage file | M | Stored band | Resolution token / trace cutoff | Frequencies used | Changed systems |
|---|---:|---:|---|---|---:|
| `stage_1_damped.json` | 3 | 8 | 512 / 64 | 0.5 GHz with recorded 25% damping | 3 |
| `release_M11.json` | 11 | 192 | 1024 / 128 | 0.5 and 2.5 GHz, real | 6 |
| `fixed_M55.json` | 55 | 192 | 1024 / 128 | 0.5 and 2.5 GHz, real | 6 |

This gives five reference matrices and fifteen changed matrices per pass.
All 24 paired source RHS and 24 reciprocal RHS are included at each frequency.
There are nine physical curve changes for the geometry-bound diagnostic.

`fixed_M55` is the last recorded fixed stage with at least four history curves.
M61 and M67 have only the initial record. The late stage supplies tiny changes;
the earlier stages provide larger changes without inventing a perturbation grid.

Read observations, units, execution settings, workspace and stage metadata
from the sealed benchmark and saved run. Preserve real/damped distinctions.
Save input hashes and chosen history indices before measuring.

The two-frequency large-stage subset is a component study, not the full stage
loss. It cannot establish C11 acceptance agreement over all 19 frequencies,
retention of 26 recoveries, or an inverse speedup. There are **zero new fits**.

## Two arms, identical current systems

### E: exact current factorization

For every current curve, assemble A1–A3, factor its full matrix once, solve
all source and reciprocal columns, and calculate predicted data and B7
sensitivities. This is the working-resolution reference, not a refined solve.

### A: anchored full-system solve

Use the fixed reference LU within each curve/frequency block. Begin each RHS
with its reference-LU solution. Solve the remaining current-system residual
with right-preconditioned GMRES and the same fixed reference LU.

If `P` applies the reference inverse, the correction solves `A_current P y = r`;
add `P y` to the initial solution. Always compute the final residual with the
trusted current matrix. No contraction-norm or Neumann convergence claim is needed.

Use complex128, a true per-column relative residual target of `1e-10`, zero
absolute tolerance, and at most 20 Krylov matrix-vector products per RHS.
Count actual products rather than relying on a library's restart-count convention.

If any nonzero RHS misses this target, is nonfinite, or reaches its limit,
stop the anchored attempt for that matrix. Factor the current matrix afresh
and solve the whole source/reciprocal batch exactly. Charge all attempted work.

Handle a zero RHS exactly without dividing by its norm. Keep the reference
anchor fixed after fallback so later moves still measure reuse distance from
the same anchor; adaptive anchor refreshing is a separate future question.

The exact arm's already available LU must not become a free fallback for A.
Time a new factorization/solve for the fallback and save pre-fallback errors
where available. Report anchored successes and fallback deliveries separately.

## Sensitivities and accuracy

The current [reciprocal derivative][b7] directly uses `state.factors`. Merely
placing reference factors there would differentiate using the wrong system.
Correct both source and reciprocal solves against the current matrix.

Use the current slider B6 preparation at each saved curve and its recorded M.
Share the resulting normal-velocity weights between E and A. Apply the existing
`hadamard` contraction to the corresponding current-system traces.

Record all of the following before and after fallback:

- Maximum per-RHS true relative residual, source and reciprocal separately.
- Relative error of the complete 24-entry predicted-data vector: target `1e-8`.
- Relative error of each non-negligible complex data-Jacobian column: target
  `1e-6`. Use a denominator floor of `1e-12` times the largest reference-column
  norm, and also report absolute errors and reference norms.
- B5-normalized residual difference using the selected observations and their
  existing weights. Label it the selected-frequency residual, not the full loss.
- Iterations, anchor age, displacement, fallback reason and arithmetic/device.

These approximation targets are deliberately tighter than the benchmark's
endpoint comparison. They measure agreement with the full current matrix;
they do not independently establish physical discretization accuracy.

If the entire reference field or Jacobian is zero, report absolute error
and mark its relative comparison undefined. Treat nonzero approximate output
in that case as a failed accuracy comparison rather than divide by zero.

A true residual passing while fields or derivatives miss their targets is
a recorded failure of the stopping rule. Preserve it and do not tune the
tolerance or GMRES cap after seeing the result.

Haibing item 8 is used here for error-aware evaluation, not a rigorous
acceptance theorem. The physical reciprocal RHS is not automatically the
Hermitian-adjoint RHS of a generic dual-weighted error formula.

No new adjoint estimator, approximate LM proposal, certified loss acceptance
or changed optimizer policy is included. Exact comparisons provide the evidence
needed to decide whether any such integration deserves subsequent work.

## Geometry-bound diagnostic: same nine moves

Compare the simple coefficient lower bound proposed in Haibing item 3 with
the existing inverse-residual bound. Reuse the implementation in
[`geometry_update_methods/certificates.py`][certificates] where applicable.

For each reference curve form its divided-difference squared modulus `q`.
The simple estimate subtracts the sum of nonconstant coefficient magnitudes
from the constant coefficient; a nonpositive result is unresolved.

For each actual coefficient difference `d`, compute `sum |m| |d_m|`. The
simple bound permits a move only when this is below the positive reference
lower bound on `|W|`. Log the predicted lower/upper interval and its margin.

For the existing method, record `curve_certificate` and `increment_bound`,
including setup cost, per-move cost and unresolved results. A failed base
construction is retained as a diagnostic result, not silently replaced.

Do not clip steps, reject recorded curves, change the anchor, freeze a
Chebyshev interval or alter any solve because of this diagnostic. Geometric
validity and convergence of a reference-preconditioned solve are separate claims.

These existing float64 bounds use heuristic rounding allowances, not verified
interval arithmetic. Present their numerical coverage as measured evidence;
an unresolved bound does not establish that a curve is invalid.

## Timing, budget and stopping

Use one machine for both arms. Prefer the GU-002 RTX 5090 host, CUDA assembly,
CPU LU/Krylov, and single-threaded BLAS. Run frequency systems sequentially
for this component timing so cost categories do not overlap across threads.

If that machine is unavailable, use one explicitly recorded CPU machine for
both arms and label the result CPU-only. Do not compare it numerically against
historical GPU timings or silently substitute devices within an arm.

One recorded first-use warm-up at the first reference system is allowed.
Then run exactly **three warmed passes** over the five reference/three-change
streams: 20 systems per pass, 60 in total, plus that one warm-up system.

Record A1–A3 common construction once per system/pass. Time E and A solves
separately on those identical arrays, with E first to supply the observer's
reference arrays. Record that fixed order. Include
array conversion, synchronization, residual calculation and fallback costs.

Report two comparisons: linear-solve time and the common A1–A3 time plus
each arm's A4/B7 time. The latter is reconstructed serial component cost,
not a measured whole-fit acceleration. Charge reference setup in both streams.

B6 preparation is shared, performed once per unique curve, and reported
separately; neither arm changes it. Geometry-bound work is also a separate
diagnostic cost, not a hidden contribution to the anchoring speedup.

Use a **30-minute wall cap for the complete measured job**, including the
geometry diagnostic and all fixed repeats. Stop at the cap and retain partial
rows. No extra repeats, cases, restart sizes, tolerances or new fits follow.

An implementation/reference mismatch stops the comparison; preserve the
failure instead of treating it as a scientific rejection. A repair requires
an explicit recorded amendment before another measured job.

Exact presentation date/time was not supplied. This plan therefore promises
bounded work, not completion by an invented clock deadline. Reserve two hours
before the presentation for explaining saved results when its time is known.

## Decision rules

1. **Accuracy:** all anchored deliveries satisfy the declared field and
   Jacobian limits; all fallbacks agree with E. Otherwise the tested stopping
   rule is insufficient and there is no integration claim.
2. **Useful computation result:** the anchor stream, including setup and
   fallback, costs less than E in at least one declared block while satisfying
   accuracy. Report the other blocks even when they lose.
3. **Stronger speed evidence:** identify a block as consistently faster only
   if all three warmed complete-cost comparisons favor anchoring. Report
   the median and range; three repeats are not a confidence interval.
4. **Geometry usefulness:** report coverage out of nine moves, margins and
   cost. Do not call the bound useful for step selection solely because it
   succeeds on the tiny late moves.

A negative result is sufficient for the presentation: for example, correct
anchoring may save LU work but lose overall because corrections or unchanged
assembly dominate. It does not authorize another idea or a wider run.

## Implementation and retained outputs

- Driver: proposed `experiments/benchmark/an001.py`; results under a fresh
  `results/validation/anchoring/AN-001/run-01/` directory.
- Numerical helper: proposed `solvers/bem_inverse/anchoring.py`, containing
  the fixed-anchor full-system solve. No dependency on experiment paths or truth.
- Reuse the modal observer for A, source/reciprocal RHS and receiver maps.
  The observer already performs exact solves: count those as the E arm and
  do not silently include an extra exact solve in A's claimed cost.
- Keep maintained inverse defaults unchanged. The component harness calls
  the two solve paths explicitly; no production `ModalState` factor substitution.
- Save source/input hashes, parameters, matrix dimensions, hardware, all
  timing/error rows, fallback failures, and the reference/current coefficient pairs.
- Minimum checks: the reference-curve identity case embedded in the stream,
  a small deterministic residual/fallback check, and the recorded physical
  comparisons above. Reuse existing modal/slider validation; no broad rerun.

After the measured job, commit and push code, plan and evidence, including
failures, to the current configured remote. Verify push and working-tree status
as required by AGENTS.md. No branch or worktree creation is part of this plan.

## Presentation package from saved results

Produce a short Markdown results page and two standalone figures:

1. **Cost and accuracy:** exact versus anchoring by stage/frequency, with
   unchanged construction, solve/correction and fallback costs visible.
2. **Useful reuse range:** actual curve changes, geometry-bound margins,
   Krylov work and field/Jacobian errors against distance from the anchor.

Include one plain-language diagram: reference curve → saved LU → full new
matrix + corrected solve. State what changed, what was tested, what improved
or failed, and what remains unknown. Do not create a slide deck unless requested.

Generate figures from retained rows, with no new forward solves for recording.
The result page opens `iteration_02/01_results.md` and links the full artifacts;
update the directions status without erasing previous evidence.

[chain]: ../../../reference/inverse_information_chain.md
[gu002]: ../../../../results/validation/cleaned_interfaces/GU-002/README.md
[bie006]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/boundary_bie/iteration_04/01_results.md
[lau003]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/laurent/iteration_05/01_results.md
[b7]: ../../../../solvers/bem_inverse/b7_data_jacobian.py
[certificates]: ../../../../solvers/bem_inverse/geometry_update_methods/certificates.py
