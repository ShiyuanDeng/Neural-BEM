# Adapt the BEM inverse to BRG's data

## Status and authority

Draft for coordinator review, 17 November 2026. Requested during activity 02;
**not authorized to implement or run**. No `solvers/` or
`experiments/comparison/` file was edited while preparing this plan.
The coordinator assigns the solver lock before implementation, because CSI
will need the same unpaired-data support. This plan uses the maintained
`modal_muller` + `slider` path, real data, one centred unit-circle start,
no localization and no warm-up. Contrast is known for this comparison.

Read first: [solver README](../../../../solvers/bem_inverse/README.md),
[A1–C12 chain](../../../reference/inverse_information_chain.md),
[activity 01 data handoff](../01_run_published_examples/data_handoff.md),
and [activity 02 plan](../02_rebuild_paper_examples/plan.md).

## Questions and success criteria

1. Can the default modal forward and its derivative consume the exact
   BRG plane-wave, receiver-by-direction data without a sign, transpose,
   normalization or unit mismatch?
2. Does that forward agree with BRG on every actual true shape/material
   before an inverse fit is attempted?
3. With known material and a declared frequency schedule, how much of each
   boundary can our inverse recover, at what cost and up to what qualified k?

Success of the adapter means correct data semantics and a checked forward
and derivative; success of a fit is reported as raw relative area error,
residual and time. A 5% classification remains the coordinator's U5 decision.
Failure at high k is a result to retain, not permission to weaken accuracy
checks or replace modal Müller with a different solver.

## Exact input contract

Read activity 02's saved `measurement` records, not a regenerated BEM data
set. Save the input-file hashes, generator version, upstream patches,
contrast, shape-fit hashes and data-resolution checks in the case manifest.
Star and cavity remain labelled **recovered from the paper's figure files**.
Forward checks use their frozen Cartesian coefficients, exactly as BRG did.

BRG stores a flat vector with direction varying fastest, then receiver.
Its MATLAB `meshgrid` has shape `(Ndir,Nreceiver)` before column-major
flattening. Recover the conceptual table `D[receiver,direction]`; the
existing Python `Acquisition.data_shape` is `(direction,receiver)`, so the
adapter transposes once into that documented contract. No complex
conjugation and no diagonal selection. Verify every saved pair against the
corresponding receiver coordinates and direction, including a rectangular
200-by-10 limited-star table. Do not infer order from square array sizes.

These are unit-amplitude, positive-spatial-phase incident plane waves and
**scattered fields at radius 10**, with the outgoing first-kind Hankel
Green function and negative time convention. They are neither total fields
nor normalized far-field amplitudes. Keep the complex amplitude and phase;
no fitted phase, gain, source strength or data-dependent normalization.

BRG's `eta` is the squared interior/exterior wavenumber ratio. In our code,
`Problem.contrast` and the modal solver's `contrast` already mean **eta**,
not susceptibility `eta-1`. Pass 0.33, 0.9, 2 or 10 directly; never pass
sqrt(eta), and never pass a negative susceptibility as `contrast`.

## Changes in the A1–C12 chain

The table identifies the default-path code and the smallest proposed work.
Files listed here are proposed changes, not permission to edit them yet.

| Chain / need | Present behavior | Smallest change and files |
|---|---|---|
| Input / plane waves | `continuation/forward.py:Acquisition` already holds unit directions and receivers; its older nodal solver supports plane waves. Default modal validation rejects it. | Reuse `Acquisition`, expose/document it if needed in `__init__.py`; branch validation and dispatch in `forward_solvers/modal_muller.py`. No new acquisition hierarchy and no nodal fallback. |
| A1 / geometry | `FourierCurve` already stores the required Cartesian coefficients. | No core change. Adapter constructs the exact glider Fourier curve and loads the frozen star/cavity fits for forward checks only. Inverse input contains only the unit circle. |
| A2 / material and eta below 1 | `ki=k*sqrt(contrast)`; checks require positive eta, not eta greater than one. | No positivity-rule change in `problem.py`, `checks.py` or `a2_muller.py`. Check eta 0.33/0.9 explicitly. The signed B7 material difference must remain negative in these cases. |
| A3 / incident waves | `a3_waves.point_kernels` makes point-source and reciprocal receiver coefficients using Graf expansions. | Add `plane_wave_kernels` in `a3_waves.py` for incident trace and speed-weighted normal flux. Use a converged Fourier projection of the analytic plane wave on the stored curve, with doubled-grid coefficient checks. This quadrature is for the smooth RHS, not boundary collocation of A2. Keep point kernels for the reciprocal receivers; preserve the old paired branch. |
| A4 / full table | `a4_fields.solve_and_predict` contracts only the matched receiver diagonal. | Add explicit full-table mode: receiver operator times all incident trace columns, then transpose to `(direction,receiver)`. Factor the Müller matrix once, retain all direction traces and one receiver batch. Touch `a4_fields.py` and `forward_solvers/modal_muller.py`. |
| B5 / changing data sizes | `Problem` requires identical acquisition at all frequencies. `forward_batch.py` uses `column_stack`; `fit_stage.py` and residual code assume equal-length columns. Counts grow with k in BRG. | Allow differing real acquisitions under an explicit default-false option in `Problem`; retain matched real/damped rules. Introduce a small shared block layout for frequency offsets/scales, use it in `forward_batch.py`, `b5_residual.py`, `b8_gauss_newton.py`, `fit_stage.py`, and `runner.py` (accepted-state maximum residual). Concatenate complete per-frequency vectors, normalize each by its own observed norm, then stack all real followed by all imaginary rows. No zero padding presented as measurements. |
| B6 / slider directions | Default slider supplies Cartesian coefficient velocities independently of acquisition. | No mathematical change to `geometry_update_methods/slider.py`; use its existing preparation and complete-trial map. |
| B7 / unpaired derivative | `hadamard` multiplies matched forward and reciprocal columns. | Add an explicit all-direction/all-receiver contraction in `b7_data_jacobian.py`, retaining the same LU reuse, normal weights, signed material factor and nonconjugated reciprocity. Block the pair contraction to avoid a modes-by-300-by-300-by-update tensor. Flatten rows in exactly A4's declared order. |
| B8 / real Jacobian | `residual_jacobian` stacks equal-sized frequency blocks. | Apply the same block layout and B5 scales to every derivative column. Keep gradient, Gauss–Newton matrix and real/imaginary order. Update recorded data-layout metadata in `recording.py` only where existing consumers require it. |
| C9, geometry update, C11–C12 | LM proposal, slider trial, acceptance and iteration commitment are independent of wave type. | No change to their decision rules. Use the shared block layout in `runner.py` accepted-state callbacks instead of their current equal-length `column_stack`. Fit records must carry the per-frequency data offsets and actual k values so failures and residuals remain interpretable. |
| Known contrast | `runner.fit(..., material=None)` already freezes `problem.contrast`; `MaterialUnknown` is optional. | Adapter passes `material=None`. No core material change, no material derivative column or fit bound. Assert the manifest and final record retain the supplied eta. |
| Wavenumber units / schedule | `Observation.wavenumber` is already explicit, while `frequency_hz` labels/order and default `RealOnlyPolicy` prefixes use GHz. Geometry has physical-unit metadata. | Adapter uses one BRG coordinate unit as one declared reference metre, origin zero, k unchanged, receivers unchanged; `frequency_hz=c0*k/(2*pi)` is the corresponding reference frequency, not a claimed experimental frequency. Set bounds to a declared centred box containing the starts/truths. Add a BRG real-only schedule in `real_only_policy.py` (or a dedicated small policy module), selecting explicit observed k values rather than the TG-002 GHz prefix. |

The block layout must work for both constant and varying acquisitions, so
CSI can later reuse it. Keep equal per-frequency relative weights for clean
BRG data. Do not let the 90,000 samples at k=30 automatically outweigh the
100 at k=1 merely because the table is larger. Existing paired TG-002
behavior must retain its old ordering, weights and predictions.
Its recovered-contrast variant must also retain the material finite-difference
column; route that column through the same block layout rather than leaving
the current rectangular `column[:,j]` assumption in `fit_stage.py`.

## Forward checks before any inversion

Perform these on the exact inputs that each fit will receive. Truth is
available only in the experiment harness and scoring, never in `Problem`
or solver stopping rules. Six material/acquisition cases share three shapes;
one shape check does not qualify a different eta.

1. Adapter-only checks: reshape/reflatten the saved complex data exactly;
   verify every direction and radius-10 receiver, unit amplitude, k and eta.
   Compare a selected table entry by its actual pair, not array position alone.
2. Low-cost analytic circle check at k=1, eta=0.33 and 2: plane-wave modal
   prediction versus a disk series; one rectangular table establishes the
   direction/receiver ordering. This is not an inverse experiment or start search.
3. For every case use its true frozen curve and BRG data at k=1, 5, 10,
   15 and 30, proceeding low to high. Record full-table relative complex
   Frobenius error, maximum absolute error, row/column error distributions,
   solve residual, and modal trace/workspace/radial diagnostics. If those
   checks pass, check every remaining frequency in the declared inversion
   schedule before starting the fit. For star
   limited, check its actual 200-by-10 table separately.
4. Increase modal trace cutoff and coefficient workspace once to measure
   forward convergence. Do not qualify a result solely from a small linear
   system residual. Use BRG's eta>1 finer-grid check at k=30 as independent
   data evidence; where needed at a failed comparison, do one BRG refinement
   of that same input rather than altering the fitted observations.
5. Proposed numerical threshold: BEM refinement difference <=1e-6 and
   BEM-versus-BRG field difference <=max(1e-5,10 times measured BRG data
   refinement error). If the BRG error itself exceeds 1e-4, document it and
   return to the coordinator before treating a larger threshold as adequate.
   Figure-recovery error is disclosed separately: both solvers see the same
   recovered curve, so it is not an excuse for forward disagreement.
6. On each qualified shape/material at one low k, check B7 directional
   derivatives against centred differences of the complete slider trial,
   with two finite-difference steps. Check the full rectangular table and
   several selected entries. The derivative error should decrease with step
   until it meets the forward error floor; require <=1e-3 relative error.

The inversion for a case starts only after its planned frequency range has
passed the true-shape forward checks. A refusal or mismatch at high k is
reported with the last qualified frequency. Do not silently omit failing
frequencies from the declared comparison or raise a cancellation tolerance.

## Proposed frequency schedule and limits

Use a declared subset of the 117 saved frequencies, with no interpolated or
synthetic frequencies: k = 1, 1.25, 1.5, 1.75, 2, 2.5, 3, 3.5, 4, 5, 6,
7, 8, 10, 12, 15, 20, 25, 30. Keep the full catalog available as provenance.
The first four stages grow a cumulative low-frequency prefix. Then add the
remaining entries in order, carrying the accepted curve forward. Retain
earlier observations with equal frequency weights; no data-driven schedule
search, extra start, localization or warm-up.

This is an explicit BRG schedule, not an unchanged TG-002 recipe. Keep the
default slider and LM rules. Start the update band from the existing real-only
rule based on exterior k, use compact storage during the ladder, and record
both the band and measured frontier. The exact stage quotas and maximum
band must be fixed after forward costs are known and before inverse runs;
the coordinator reviews them. In particular, eta=10 may require substantially
more trace resolution than an exterior-k rule predicts.

Proposed activity budget, **not yet authorized**: at most 1 h for shared
adapter/derivative checks and 1 h per case for forward checks, followed by
at most 4 h per inverse case, with a separate capped post-fit score. Use one
heavy BEM worker at a time, record CPU/GPU/thread settings and overlap, and
stop on the first unmet forward requirement. No inverse reruns for tuning.
The coordinator can change these budgets before the plan becomes executable.

## High-k risks to resolve before claiming full-range support

- A3's current point-kernel regular-wave construction bounds cancellation
  by machine epsilon times the modified-Bessel growth. The check in
  `checks.require_wave_cancellation` rejects large exterior k times bounding
  radius. Radius-10 receivers still need these reciprocal kernels, even
  after plane-wave incident support exists. At k=30 on these shapes this is
  a likely hard limit. A stable coefficient construction may be a separate
  numerical task; do not bypass the refusal or replace the entire solver.
- A2 radial degree and trace bandwidth rise with both k and interior k;
  glider eta=10 reaches interior k about 94.9. Its matrix can be well solved
  yet underresolved. Check trace and coefficient-workspace convergence.
- Narrow cavity openings and close boundary segments stress A1 log-distance
  certificates and the slider geometry map. The public BRG cavity itself
  can settle at a wrong shape; neither successful forward agreement nor a
  small residual proves the inverse recovered the cavity.
- Full tables grow to 90,000 complex entries per frequency. The full
  Jacobian, retained traces and concurrent frequencies can dominate memory.
  Block B7 contractions and use one frequency worker initially; retain the
  existing work accounting and actual wall time separately.
- Curve coefficients recovered from figures carry finite accuracy (activity
  02 reports it). At high k this affects comparison with the paper's absent
  original shape, even when our forward agrees with the generated BRG data.

## Implementation order, commands and evidence

After review and solver-lock assignment: implement input/table and A3/A4
support first; pass the circle and low-k forward checks; then implement B7
and ragged B5/B8; check derivatives and paired-data regressions; finally add
the explicit schedule and run the per-case true-shape checks. No inversion
before all relevant forward checks pass.

Proposed experiment entry point, to be added under owned paths:
`python experiments/baselines/brg/run_bem_adaptation.py --phase forward`
then `--phase inverse --case <case>` only after recorded forward acceptance.
Use `results/brg/bem_adaptation/<date>/<case>/` for compact manifests,
per-frequency errors, curve histories and timings; `local/` for ignored bulk
with commands and SHA-256. Report figures belong in this activity's
`figures/`. Commit and push each run, including failures, using explicit paths.

Final report compares each BEM endpoint with its activity 02 BRG endpoint
using normalized symmetric-difference area and native/adapted timings shown
separately. Include the actual accepted frequency range, known eta, forward
agreement, data hashes, numerical failures, and geometry-recovery limits.

## Decisions needed from the coordinator

Review the proposed Fourier-projected plane-wave RHS, shared ragged-table
representation, frequency schedule and staged budgets; assign the solver
lock (U2) before changes. U5 affects success labels only, not saved scores.
Any high-k wave-kernel redesign needs its own concrete proposal after the
current failure is measured. No question or permission prompt goes directly
to the user from this agent.
