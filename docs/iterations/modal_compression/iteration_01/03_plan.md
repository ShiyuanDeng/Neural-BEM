# MC-001 — inspect modal entries, then conditionally test physical reuse

2026-09-21. **Approval status: APPROVED. Execution status: COMPLETE.**
Stage A completed; Stage B was not released because the first-stage gate failed.
The [iteration-02 results](../iteration_02/01_results.md) own the closeout.

The user requested the simple matrix/derivative visualizations and explicitly
authorized proceeding to the rest only if this first test goes well, otherwise
stopping to discuss failure modes. This plan consolidates that instruction and
supersedes the sequencing in `02_proposals/02_next_tests.md`. The old proposal
is retained as history. No new branch or worktree is needed or authorized.

## Question and first-stage decision

Does a freely selected entry pattern substantially reduce a well-resolved
modal Müller system and its derivative family while preserving fields and
physical sensitivities? No centered-band assumption is imposed.

Stage A constructs the complete matrices solely as a diagnostic. Heatmaps show
the four blocks of `A-I` and directional derivatives. Sorted-entry curves
show the smallest retained set at block-relative Frobenius tail tolerances
1e-2, 1e-4, 1e-6, 1e-8. Also report simple relative-entry-threshold counts,
individual derivative masks and their forward/derivative union. Zero blocks
are recognized using measured refinement/FD uncertainty, not amplified by
normalizing roundoff. The identity stays exact and is counted separately.

**Release Stage B** only if at least two of the three noncircular geometries
pass at both kD=2 and 10 with a common forward/derivative mask representing at
most 50% of the smaller independently qualified full modal matrix (including
identity storage), receiver error <=1e-6 and every tested physical directional
data derivative error <=1e-3. Test the predeclared tail ladder; do not tune a
new pattern to a failure. kD=30 is a stress test, reported separately; it does
not veto a explicitly lower-frequency continuation. The circle is a control,
not a qualifying noncircular success. If this gate fails, produce the figures
and failure analysis and stop before B. Small matrix tails alone never release B.

The 50% gate asks for a meaningful first signal; it is not a theorem about
useful compression. A failed gate can still show modest structure worth
discussing. Absolute retained counts and minimal reference dimensions prevent
oversampling from creating a misleading success.

## Fixtures, numerical controls and implementation map

- Four unit-diameter finite Laurent shapes: circle, ellipse, asymmetric star,
  crescent; exact coefficients and acquisition saved before measurement.
  Full-space scalar transmission, equal permeability, `ki/ko=1/sqrt(2)`.
- Exterior kD=2,10,30 at the anchor, fixed physical `ko,ki` in every derivative
  and nearby-shape test. Twelve sources and twelve offset receivers on an
  external ring; no inverse noise for A.
- Six finite-Laurent pure-normal directions:
  `delta z(t) = (-i*z'(t))*cos(p*t)` or its sine version for p=1,3,6,
  normalized to unit RMS physical normal displacement. On noncircles the normal
  speed is `J(t)*cos(p*t)` after normalization, **not** a pure normal harmonic.
  This explicit amendment to the older proposal avoids approximate normal
  projections. A tangential direction is an additional diagnostic, excluded
  from the six physical-direction release gate.
- Hybrid analytic-log/FFT Galerkin assembly from `experiments/laurent_fgm/`,
  imported read-only, with independent nodal Kress field and reciprocal
  sensitivity checks. Differentiate the analytic Hankel/log amplitudes and
  acquisition maps to construct `dA,db,dC`; validate against centered full
  reassembly finite differences at fixed physical waves and multiple step sizes.
  This implementation refinement avoids making FD cancellation the derivative
  sparsity floor. Record grid and FD uncertainty so the 1e-8 plots are not
  mistaken for independently certified resolution below that floor.
- Select the smallest passing trace cutoff in a frozen ladder
  `[16,24,32,40,48,64,80,96]`, against independently refined fields and
  physical sensitivities. Assembly-grid refinement is separate from trace
  refinement. If necessary, a declared qualification-only ceiling K=128 and
  grid=2048 is available; do not enlarge candidate dimensions to improve counts.
- Reference controls: field uncertainty <=1e-8, physical derivative uncertainty
  <=1e-5; aim at tighter values. Full modal-to-Kress receiver discrepancy <=1e-8
  and each non-negligible physical derivative <=1e-5. Record absolute floors
  for near-zero quantities. If a fixture fails qualification, mark it
  unqualified rather than as a compression failure. Two failed noncircular
  low-frequency qualifications stop expansion and require discussion.
- Re-solve on `I + mask*(A-I)`, differentiating the same frozen mask. Compare
  physical fields/JVPs, scaled trace and residual errors; additionally evaluate
  reciprocal/Hadamard derivatives on these traces as a separately labeled arm.
- One new isolated package `experiments/modal_entry_screen/` owns selection,
  orchestration, plots and read-back. No changes to existing numerical sources.
  Unit checks target cumulative tails, union accounting, derivative consistency
  and a physical circle control, not reporting implementation details.

## Conditional Stage B

On the qualifying noncircular shapes at kD=2/10, keep the Stage-A mask fixed and
test two opposite 0.5%-diameter normal offsets, a new normal-speed direction
containing p=9, and shifted illumination. Compare discrete masked derivatives
and reciprocal derivatives separately against fresh Kress controls. Record
whether the mask survives without reselection and whether the physical route
improves derivative quality. No automatic rebuild may turn a failed reuse into
a claimed pass.

If physical fields and worst sensitivities pass at the same storage gate,
perform a bounded regularized local Gauss–Newton trial comparison against the
full model using identical damping, starts and data. Check actual reduction
with the full forward. This is a local inverse-direction test, not a full
inverse or speed qualification. Failure here stops further development and
opens a discussion. Any wider implementation/economic campaign needs a concrete
success-dependent contract within the user's continuing scope; it must not be
launched merely because plots look sparse.

## Budget, artifacts and completion

Stage A: <=30 minutes numerical wall time, <=1000 full assemblies and <=4000
factorizations. Stage B, only if released: an additional <=30 minutes, <=1000
assemblies, <=4000 factorizations. Peak RSS <=8 GiB; one sequential CPU worker,
single-thread BLAS. Budget caps are checked before numerical operations.

Use a fresh `results/validation/modal_compression/MC-001-<stamp>/` directory.
Save configuration, source hashes, matrices/derivatives/masks, qualification,
counts, re-solve errors, timings and failure rows; render PNG/SVG heatmaps and
retention curves with a small navigable HTML gallery. The gallery is a local
artifact, not a hosted website. Recompute gates/counts from saved arrays and
visually inspect figures before delivery. Results open iteration 02; handoff
records whether B ran or the first-stage failure stopped it.

Owner: Codex. Independent reviewer: unassigned. Existing checkout and branch
`feature/ordered-boundary-nystrom`. No commit/push requested.
