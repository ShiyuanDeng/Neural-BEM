# Geometry comparison: evidence entering GC-001

2026-10-04. This cycle opens from the completed [PC-002](../iteration_28/05_results.md)
and the user's request for a purely geometric spline/spectral runtime and precision
comparison, including attribution of the differences. No new geometry experiment
has run in this cycle.

## Existing measurements

[NU-003](../iteration_11/01_results.md) replayed 72 archived states and 648 moves,
without physics. Preparation summed to 20.071 s for spline and 54.196 s for CPU
spectral. Median normalized coarse/fine trial differences were 3.1e-12 and
1.7e-14, respectively; worst differences were 3.988e-6 and 1.028e-10. The
largest relative geometry-column disagreement was 2.305e-7. These are refinement
diagnostics, not errors against exact geometry. The old scene set is historical
evidence only and will not be rerun.

[NU-006](../iteration_14/01_results.md) compared spectral CPU and GPU preparation
on another 72-state replay: 44.149 s versus 0.924 s, with worst column difference
9.669e-9. It did not measure the current spline against current GPU spectral.
NU-007a subsequently qualified GPU certificate evaluation; its results concern
validity checking, a distinct cost from reparameterization.

PC-001 and PC-002 whole-inverse times cannot answer the geometry-only question:
their physical discretizations, workers, geometry choices and audit workloads
differ. GC-001 will reuse TG-002 curves, without fitting or physical solves.

## Current implementation findings, not new measurements

Both maps share Fourier curve sampling, normal displacement, FFT storage of the
moved curve, and spectral integration of speed to normalized arclength. Their
main mathematical difference starts after that common arclength map:

- `geometry.project` inverts sampled arclength with a default-boundary cubic
  spline, evaluates a periodic cubic position spline at the inferred parameters,
  and FFT-crops to the retained Cartesian band.
- `spectral.arclength_quadrature` computes the retained coefficients directly by
  a change-of-variables quadrature. It also reconstructs the cropped curve to
  calculate an intentional-smoothing diagnostic.
- Both preparations use central finite differences, normally at 1e-7 m. Errors
  in two nearby projections can be amplified by division by twice that step.
  A geometry-column difference is not a field-Jacobian error measurement.
- `batched.batched_projection` batches all perturbations on the selected device,
  reuses base jets/basis within the batch, uses direct exponentials rather than
  CPU recurrence, and returns coefficients to the host. It does not compute the
  crop-error reconstruction that CPU preparation computes and then discards.
  Thus the preparation speed difference includes work removal and batching,
  as well as device execution; it cannot all be attributed to GPU arithmetic.
- `DeviceCertifiedUpdate` uses GPU batched preparation and GPU certificates,
  but its finite trial projection still calls CPU `arclength_quadrature` through
  `CertifiedSpectralUpdate._moved`. Whole geometry is not GPU-resident.
- Spline and plain spectral use sampled validity checks. Certified spectral
  adds coefficient-based acceptance tiers and retains sampled fallback. Its
  lazy accepted-curve certificate is reused within a prepared space.
- `intentional_projection_mm` is evaluated on different parameter grids in the
  spline and spectral implementations. The raw diagnostics are not a direct
  same-point precision comparison.

These findings motivate the controlled comparisons and ablations in the
[GC-001 pre-registration](03_plan.md). Actual attribution awaits those measurements.

## Whole-inverse context from existing receipts

Read-only aggregation on 2026-10-04 of all 30 `fit_result.json` files in each
PC-001 M1, PC-001 N1 and PC-002 NS arm. Define recorded geometry-update time as
`geometry_work.preparation_seconds + geometry_work.trial_seconds`. Certificate
seconds are nested inside trial seconds and are **not** added again. These
counters include initial/final audit geometry as well as fitting. Use each
case's `total_seconds` as the matching denominator.

| Existing arm | Summed geometry-update seconds | Summed total seconds | Geometry share of summed total | Median per-case geometry share |
|---|---:|---:|---:|---:|
| PC-001 M1: modal + certified spectral | 196.94 | 1,031.21 | 19.10% | 15.54% |
| PC-001 N1: fixed-floor nodal + certified spectral | 1,509.51 | 9,926.08 | 15.21% | 3.08% |
| PC-002 NS: fair nodal + spline | 636.86 | 3,273.75 | 19.45% | 15.61% |

The N1 aggregate is dominated by long failed/promoted cases and certificate
work; its typical case has a much smaller geometry share than the sum suggests.
NS preparation alone sums to 612.53 s, with only 24.33 s in trial construction.
M1 preparation sums to 42.77 s and trial work to 154.17 s, of which 102.72 s
is certificate work. These show different optimization targets. They are not
matched comparisons of algorithms, nor a basis for replacing one arm's times
with another's: the actual curves, update spaces, step counts and audits differ.

For M1/NS's approximately 19% recorded share, doubling the speed of *all*
geometry updates would reduce complete runtime by approximately 9.5–9.7%
(about 1.11x speedup). Eliminating that entire measured category gives a
fixed-work upper bound of about 1.24x. This is Amdahl's law, conditional on
identical physical work, decisions and audits—not a prediction of an inverse
run after changing its geometry map. For N1's median-case 3.08% share,
doubling geometry speed would save only about 1.54% for that representative share.

Do not claim an exact fitting-only share: dividing the full-run counters by
fitting time would improperly include audit geometry in the numerator. For NS
that ratio is 38.99%, which is only an upper bound on the aggregate fitting
geometry share, not its measured value. Conversely, physical BEM geometry
preparation/assembly lives inside physics receipts, outside these update
counters. The table does not measure every operation involving geometry.

The bigger-picture result therefore needs two answers: the bounded direct
runtime saving at fixed work, and whether more accurate geometry changes trial
refusals, accepted steps or numerical-resolution stops. GC-001 can test map
accuracy and replay decisions; it cannot establish changed inverse trajectories
or recoveries without a separately authorized inverse experiment.
