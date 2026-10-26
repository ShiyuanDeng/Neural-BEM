# Direct evidence for Haibing items 3 and 9

## Item 3 coefficient safe region

**Answer:** the step certificate is useful on ordinary trajectories. The
simple near-circle bound covers 69/146 actual accepted steps. The sharper
A1 reciprocal bound covers 22/24 steps sampled across the same trajectories.
On those same 24 steps, the simple bound covers 17/24; the sharper bound adds five.

| Default TG-002 trajectory | Simple bound all same-stage steps | Sharper bound eight selected steps |
|---|---:|---:|
| circle c4 | 16/16 | 8/8 |
| peanut c4 | 36/38 | 8/8 |
| hook c13.3 | 17/92 | 6/8 |

This directly tests original §5, inequalities (13–14), on actual stored
coefficient changes after the refit. It improves on TA-001's test of four
refusal states. Same-stage transitions span early localisation through late
shape stages; stage changes are excluded because they can change the space.

The selected hook steps near the end have maximum certified fractions 0.783
and 0.189 of the accepted coefficient displacement. They were accepted by the
original run; failure of this sufficient bound does not establish invalidity.
A strict certificate-only policy could unnecessarily shorten these steps.

The sharper bound took 0.015–5.342 seconds per selected anchor on four allowed
CPU cores with single-thread BLAS; 23/24 took at most 1.128 seconds. Computing
it solely to replace a cheap sampled check is not a demonstrated speed-up.
Reusing the A1 bound already computed for physics is the plausible use.

**Limit:** these are replayed accepted transitions, not a new acceptance
policy. A1's residual inequality is exact in exact arithmetic, but its FFT
rounding allowance is heuristic; this is not interval-verified certification.
Frozen upper intervals and sensor separation still require their own checks.

## Item 9 separate update band and frequency information

**Answer:** the saved physical Jacobians show why update bandwidth and data
frequency must be managed separately. Adding shape parameters alone produces
many weak directions; adding frequencies strengthens some, but not all.

Whiten using the mean squared *actual normal displacement* of the saved
geometry-update derivative. Normalize each frequency by its observed data
norm. Counts below use the illustrative threshold 0.001 of the largest
singular value of that particular whitened Jacobian.

| Saved state | Update band M | Parameters | Low frequencies ≤0.75 GHz | All 19 real frequencies |
|---|---:|---:|---:|---:|
| hook release, slider | 3 | 7 | 7 | 7 |
| hook release, slider | 11 | 23 | 23 | 23 |
| hook final, slider | 3 | 7 | 7 | 7 |
| hook final, slider | 11 | 23 | 23 | 23 |
| hook final, slider | 67 | 135 | 33 | 106 |
| peanut final, spectral | 3 | 7 | 7 | 7 |
| peanut final, spectral | 11 | 23 | 21 | 23 |
| peanut final, spectral | 37 | 75 | 21 | 45 |

For hook M67, the smallest/largest singular-value ratio rises from 8.07e-13
to 5.43e-6. For peanut M37 it rises from 6.08e-11 to 1.18e-5. All shape metrics
retain full numerical rank. Changing parameter units over a factor of 100
changes the whitened spectra by at most 1.87e-13 relative L2.

This directly evaluates original §19 equation (57) on the real scattering
Jacobian and actual update map. It does not infer information from frequency
interpolation error. Geometry and trace bandwidth remain fixed for each state.

**Limit:** this threshold is a diagnostic choice, not a noise-calibrated
identifiability guarantee. These are local spectra, not recovery results.
No adaptive schedule was implemented; no general benefit of increasing N
or K was tested. The hook states use the optional H3 slider policy.

## Evidence and execution

The [plan](03_plan.md) fixed three trajectories, 24 sharper checks and three
saved Jacobian states. The [driver](../../../../experiments/haibing_geometry/study.py)
finished successfully; its parameter-unit invariance check passed. There were
no new inverse fits or forward solves and no maintained solver changes.

[Per-step results and spectra](../../../../results/validation/cleaned_interfaces/HB-002-geometry/)
include input SHA256 hashes, source revision, CPU affinity, load, complete
singular spectra and A1 residual receipts. All computations used existing
EMNerf, CPU cores 4–7, and single-thread BLAS.
