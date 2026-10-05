# GGB-004 — Translation and radius before deformation

2026-10-05. Preregistered before execution. The user directly requested:
"no i think we should have an initial stage where only translation (and scaling?)
are allowed. we monitor on this same case 8, when that converge. run this
immediately i dont think this would take long."
This latest instruction authorizes this specific immediate follow-up and the
case-8 exception; GGB-004 is its tracking ID. It supersedes a separate ID
approval round trip for this run. It does not authorize a branch/worktree.

## Frozen intervention

One initial restricted stage W with only centre x, centre y and radius.
Start from the original centred 0.35 m circle at storage band 32. Exact
positive uniform scaling preserves the circle and cannot create protrusions.
The three local coordinates are physical metres: tx, ty and radius increment
dr. Use the existing 18/18/12 mm coordinate caps. Change c0 by tx+i*ty and
multiply every nonzero Fourier coefficient by 1+dr/R, where R is the current
physical area-equivalent radius. Reject nonpositive scale; preserve domain,
field-resolution and decrease checks. No centre prior or truth-selected step.

Reuse sealed GGB-002 F4 data exactly: 0.5/0.75/1/1.25 GHz, 512 pairs each,
5% noise, known material. Use current modal_muller full-panel adapter, CUDA,
one frequency thread and single-thread BLAS. No frequency change, grid,
new initialization, restarts, damping tuning or multiple candidate runs.
Retain original scheduled damping, trace cutoffs 64/96, 1e-4 field gate,
original weights and loss discrepancy. One ordinary fit_stage call with
100-iteration limit, 2600-unit stage quota, 8000 global work cap and 2400 s
fit cap. No normal shape updates in this pilot.

Save and inspect the restricted endpoint before shape continuation. The
user has been asked whether later ordinary shape stages should follow;
the default pilot stops here. Any approved continuation must retain this
endpoint and receipt rather than rerun the initial stage.

## Convergence and evidence

Print/save centre, radius, residual, objective and elapsed time at every
accepted update; keep exact coefficient and trial histories. Keep the
ordinary solver's stop. Gradient tolerance establishes restricted-space
stationarity, not full inverse recovery. No-decreasing-step is a stall,
unless the endpoint model gain is negligible at the existing acceptance
precision. An iteration/work/time cap is not convergence.

After the stage, independently evaluate its three-coordinate Jacobian and
residual at both cutoffs. Save gradient, undamped least-squares Gauss-Newton
step, predicted gain, and the existing acceptance margin. Compare model
gain with that margin and report resolution dependence. This audit does not
take another inverse step or tune stopping settings. Audit all fitted fields
and the archived 0.4 GHz holdout as in GGB-003; score geometry only afterward.

Before fitting, require exact similarity invariance, metre conversion,
finite-trial coefficient tangents, circle preservation, positive radius,
and full-panel finite-difference derivatives on CPU/CUDA (all three columns,
all four frequencies, error <=1e-5). Run appropriate package/controller
tests. Preserve failed checks as well as successful evidence. Fresh source
and input seals go under results/validation/cleaned_interfaces/GGB-004.

Compare descriptively with the saved GGB-003 control and translation/shape
interleaving; do not rerun them. Preserve the initial-stage endpoint,
convergence plots, direct boundary video via the existing encoder, report
and timing receipts. Validate, commit and push after this run, including
failures. No claim of equal-data superiority over GauGal follows from this
single known-material, four-frequency pilot.
