# ON-001 — live execution record

Status: **IN PROGRESS**, authorized by `Go ON-001 using docs/iterations/OVERNIGHT_AGENT_TRACKS.md`.
Start 2026-10-05 01:37:21 UTC; eight-hour deadline 09:37:21 UTC.
Plan: [iteration 30](../iteration_30/03_plan.md). No branches/worktrees created.

Evidence: [live table](../../../../results/validation/cleaned_interfaces/ON-001/table.md),
[structured receipts](../../../../results/validation/cleaned_interfaces/ON-001/report.json).
All 30 TG-002 cases will remain in the inventory; unlaunched cases are unrun.

Execution uses one fresh case interpreter, four frequency threads, one BLAS
thread, explicit CUDA on the RTX 5090. Every arm uses a 120-second fit cap,
13,412 work units and an aggregate 30-second audit allowance, with 10 seconds
reserved for terminal audit. There is no excluded warmup: CUDA startup,
initial/endpoint audits and output writes are charged. Scoring/output outside
the fit are reported separately as case time.

The numerical recipe is unchanged in B; opt-in receipt timing is shared by
all arms. G/E hooks are present but disabled in B. Immutable reference sources
at parent HEAD `6f2c1408` are preserved in
`results/validation/cleaned_interfaces/ON-001/reference_HEAD_sources.tar.gz`;
each numerical batch archives and hashes its actual imported source separately.
Compute/source locks cover the full numerical process. Queue waiting counts
against the overnight ceiling.

## Validation and corrections

Initial preflight: 35 passed, 2 failed. The new zero-residual audit retry needed
a strict improvement check; nondeterministic proposal timing needed to be
opt-in to preserve exact resume receipts. Both were corrected before any fit.
The original failed log is preserved under `ON-001/validation/preflight.log`.
The archived-policy test now adds the neutral default `reach_fraction=0`
when comparing the historical optimizer receipt, preserving the old source.

No numerical results or success claims yet.

Pre-dispatch regression gates passed: **218 package/campaign tests** in 139.67s
and **348 shared-continuation/lower-level tests** in 26.65s. Logs are retained.
Eight-case B screen dispatched after these gates, with sources frozen under
the shared source lock and an exclusive compute lock for the complete batch.

## B — baseline screen

Completed all eight development cases: **4/8 recovered** (circle4,
c_shape13.3, kite0.5, star13.3). All four expected hard failures remained
failures (Aphex at all contrasts and hook13.3), each stopped by the frozen
physics-resolution gate. No historical screen success was lost to the cap.
Total time to audited endpoints: **259.22 seconds**, excluding fresh-process
imports and post-fit scoring; complete case times are recorded separately.
Source-hash check passed. Per-case evidence is in the live table/gallery.

Aphex13.3 used 19.79s on refused geometry proposals, 50.3% of its 39.36s
fit. This releases F under the declared decision tree if no earlier major
screen result closes into confirmation. G and E still run independently
first. No new recipe is selected from this baseline result alone.

## G — reach-informed clipping

Completed **4/8 recovered**, no new recoveries and no regression. All four
common successes are slower (circle 6.15s, c_shape 30.39s, kite 69.80s, star
49.86s; baseline 5.43, 27.96, 65.78, 46.28s). G therefore does not qualify for
adoption or GE. The 0.4 repair is not released: projected geometry refusals
vanished rather than persisted. Its useful mechanism evidence is retained,
including Aphex13.3 passing farther along continuation with zero geometry
refusals, but its endpoint still failed. Original endpoint gates stayed active.
Sources remained frozen; read-back and source-hash checks passed. **G closed
screen-negative**; E is next, independently. The conditional F remains
released by baseline Aphex13.3 geometry cost, unless E earns immediate major
confirmation.
