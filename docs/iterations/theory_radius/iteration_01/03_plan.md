# TR-001–003: local radius, archived handoffs, and stationary branches

Approved by the user's “alr go” after the October 3 theory review. Existing
`feature/shape-frequency-continuation` checkout; no branch/worktree creation.
Implementation owner: Codex. No independent reviewer assigned. No production
defaults or existing numerical sources are changed. The running FM-003 campaign
and its source seals are preserved.

## Decision and scope

Measure whether local stability/nonlinearity explains the early paired C failure,
whether the proposed sufficient handoff rule is usable on saved trajectories,
and whether a small real stationary branch supplies evidence for folds. This
authorizes the three diagnostic experiments, not a new inverse controller or a
complex-geometry solver. Truth is explicit diagnostic input, never an online
inverse decision. Negative, refused and budget-limited evidence is retained.

## API and coordinate map

`experiments/theory_radius/` owns all new code. `bem_inverse.physics.NodalKress`
supplies existing full-matrix real/damped solves and reciprocal derivatives;
`benchmark` and `fm001` supply the frozen production acquisition and catalogs.
`FourierCurve`, `ProjectedUpdate`, and `normalize` are reused without changes.

The radius experiment uses an affine Cartesian representation of a **fixed**
normal chart, not differences of Jacobians in independently re-centred charts.
Its directions are Fourier harmonics in the base arclength, projected at K192,
with the projected normal mass metric whitened so coefficient norm is RMS mm
at the chart origin. At displaced curves the fixed Cartesian velocity is dotted
with the displaced normal. Projection error and finite-difference/refinement
checks are recorded. Realification is [Re J; Im J]; structural null columns
are retained in reported minimum singular values.

## TR-001: empirical radius atlas (90 minute / 30,000 frequency-solve cap)

Cases: a 30 mm circle at contrast 13.3, development C at contrasts 4 and 13.3,
and shifted star at contrast 13.3. Base is the known truth. Production 24-pair
ring and full 24x24 control, real and gamma=.25 damped observations. Full solves
provide paired diagonals, preserving their distinct objective normalization.

Probe bands M=3,5,7,9,15; baseline spectra additionally at M=23,31. Probe frequency
sets are the cumulative prefixes .5; .5/.75; .5/.75/1; .5/.75/1/1.25 GHz. The
complete 19-frequency catalog supplies an additional baseline spectrum only.
For each band: four fixed Gaussian directions (seed 20261003), plus the weakest
paired and full directions of the four-frequency stack; both signs at RMS
0.01, 0.1, 1 mm. Invalid geometries are recorded without replacement.

For each acquisition/prefix measure sigma_min, L_sample from J(q)-J(0) and
opposite-point differences, direct TCC remainder ratios, and rho_sample=
sigma_min/(4 L_sample). Recompute direct TCC probes at 0.5,1,2 times rho_sample
in the weakest direction, capped at 1 mm. These are **empirical estimates**,
not bounds or certificates. Resolution qualification: N512/1024, field relative
error <=1e-7, whole-Jacobian relative error <=1e-5; FD direction error <=1e-4
at 0.001/0.0003 mm (whole-Jacobian absolute scale for tiny directions). A failed
quality gate stops that row's interpretation, not deletion of its evidence.
Circle fields and constant-normal derivative also use the independent Mie disk.

Save per-frequency base Gram matrices/spectra, probe measurements, qualification,
work/time/source/input receipts and rebuildable summary. Validate and commit/push
TR-001 before dispatching TR-002.

## TR-002: retrospective handoffs (30 minute / 10,000 solve cap)

Use archived paired CI-001 and full FM-001 C4, C13.3, star13.3 endpoints. Test
stage1->2, 2->3, 3->4 and damped4->real4 (24 handoffs). No new reconstruction.
Recover the endpoint as a normal graph over truth using normal intersections;
require a single monotone winding and compatible tangent orientation. Record
graph failures, geometric band truncation, projection residual and data model
error. Reuse TR-001 constants with the exact objective weights and common
physical metric. A remote endpoint outside the tested chart/radius cannot be
certified by a small residual. Report such rows as inapplicable; do not force
an inequality result. Any computed handoff indicator remains empirical.

Read completed FM-003 census summaries only if their completion records exist;
otherwise mark this supporting evidence pending. No duplicated census.
Validate and commit/push TR-002 before dispatching TR-003.

## TR-003: stopping and real branch diagnostics (60 minute / 20,000 solve cap)

At paired/full stage2 endpoints for C4/C13.3, use an affine chart with exactly the
production projected-update tangent (M5,K12), whitened in physical RMS mm.
Evaluate the gradient and full objective Hessian via centred differences of
the gradient at steps 0.002/0.001 mm, N512/1024. Include residual curvature;
record Hessian asymmetry, resolution/step disagreement, inertia and GN comparison.
Check the actual nonlinear production trial along gradient/weak-curvature
directions and retain archived acceptance margins. An affine-tangent Hessian
is explicitly not the Hessian of the finite projected retraction away from
stationarity. No “no_decreasing_step” stop is renamed stationary automatically.

For each paired C, start a fixed-chart data homotopy at its archived stage1
curve: d(t)=(1-t)G(0)+t*d_stage2, t real, fixed damped .5/.75 GHz. Track stationary
points with pseudo-arclength; q is RMS mm, the continuation coordinate is 5t.
Maximum 40 accepted steps, initial/max arc step .5/1 mm, minimum .015625 mm,
eight corrector iterations, gradient tolerance 1e-8, ||q||<=15 mm, -0.1<=t<=1.5.
Crossing t=1 triggers a bounded fixed-t correction. Refusals and partial paths
are preserved. A fold requires a resolved tangent reversal and stationary
branch evidence; a small eigenvalue alone is only a candidate. Toy folded-branch
tests verify the continuation implementation independently of BEM.

## Execution and interpretation

Existing EMNerf environment, one experiment worker, four frequency threads,
single-threaded BLAS; record overlapping FM-003 work. Wall times under concurrent
load are diagnostic costs, not comparative performance benchmarks. Commands
refuse existing output files; each phase is source/input sealed and has a fresh
failure receipt on exceptions. Production/refinement costs count in the caps.
Numerical tests precede campaigns; artifact validation precedes each commit/push.
Results open iteration_02 and the evidence bundle, leaving this plan unchanged.
