# ON-001 — results

Status: **CLOSED — USEFUL PARTIAL RESULT**, authorized by `Go ON-001 using docs/iterations/OVERNIGHT_AGENT_TRACKS.md`.
Start 2026-10-05 01:37:21 UTC; eight-hour deadline 09:37:21 UTC.
Plan: [iteration 30](../iteration_30/03_plan.md). No branches/worktrees created.


## Confirmed result and closure

**Terminal classification: useful partial result.** All 30 fresh B/E pairs
completed: **26/30 recovered in each**, distributed 9/10, 9/10, 8/10 across
contrasts 0.5, 4, 13.3. Both reproduce all 26 historical PC-001 M1 successes.
There are **zero recovery regressions and zero new recoveries**. All common
recoveries are faster: median paired audited-output speedup **1.545838x**,
10th percentile **1.225445x**. The 2x major-speed threshold was
not reached. Suite output time including all failures falls from
803.352s to 550.986s
(31.41% less).
This is the frozen-recipe TG-002 confirmation, not a generalization study.

Retain **E only**: `modal_muller` + `certified_spectral`, full real-catalog
maximum residual <= .003 at an accepted state, passed independent current
endpoint audit, centred start, `localization none`, original continuation
schedule/coefficient caps/resolution. G/W/F are disabled. The API controls are
opt-in; no default pipeline or solver was changed. No per-scene recipe choice
uses truth. Truth scoring runs only after the inverse returns.

| Quantity | B | E |
|---|---:|---:|
| All-30 audited output seconds | 803.352 | 550.986 |
| All-30 fit seconds | 685.959 | 438.032 |
| All-30 audit seconds | 95.961 | 93.737 |
| Median common-success fit seconds | 18.435 | 9.976 |
| Median common-success audited output seconds | 22.408 | 13.724 |
| All-30 fit plus audit units | 63619 | 41531 |
| Proposals | 2511 | 2145 |
| Accepted | 1826 | 1572 |
| Geometry refusals | 43 | 43 |

Times start at campaign case entry and end after `fit_result.json` is written,
including setup and all charged initial/early/final audits. Python imports and
truth scoring are excluded; child-process and case times remain in receipts.
Fit and audit times use the internal runner boundaries, so they need not sum
exactly to the broader output time. Component physics seconds sum threaded
calls; geometry timers overlap. They are diagnostic costs, not additive wall
time fractions. Detailed geometry/certificate/projection, physics, proposal,
refusal, fallback and work totals are in `final_comparison.json`.

No fit/audit time cap or fit-work cap was exceeded. Maximum B/E fit times are
62.563/39.382s; maximum audits
3.953/3.610s; maximum fit units
4856/3659, below 120s/30s/13,412.
The four failures are the three Aphex contrasts and hook/13.3. Both arms stop
because a candidate leaves the frozen numerical-resolution regime; early exit
does not remove that obstruction. No newly recovered hard case exists, so the
conditional finer nodal endpoint check is not triggered.

### Repeated timing checks

Two extra sequential matched repeats were completed on the three declared
cases. All repeated numerical cases retain recovery. The first repeated circle
pair overlapped read-only gallery generation; its timing is explicitly excluded
and preserved. A circle-only uncontended replacement completed within the
original confirmation allowance. Eligible timing pairs are:

| Case | Eligible pairs including all-30 | B/E speedups | Median |
|---|---|---|---|
| circle__c4 | 3 | 1.240 / 1.242 / 1.238 | 1.240 |
| kite__c0.5 | 3 | 3.857 / 3.894 / 3.829 | 3.857 |
| star__c13.3 | 3 | 1.600 / 1.566 / 1.604 | 1.600 |

Only these eligible samples support the repeated-timing claim. They use fresh
interpreters, one case worker/four frequency threads/one BLAS thread and shared
B/E settings. Compute/source locks make each pair contiguous; source hashes
match at both ends. All 30 confirmation pairs share one source fingerprint.
Input seals and frozen configuration were verified; each pair was read back,
validated, committed and pushed after releasing numerical locks. Publication
receipts and immutable source archives are included in the evidence bundle.

### Mechanism decisions, cost and next direction

G closed screen-negative (4/8 retained, no additions, median .924x vs B);
its .4 repair was not released after hard-case geometry refusals vanished.
E independently qualified (4/8 retained, median 1.430x). W on E closed
screen-negative (4/8, every common success slower; marginal median .890x).
No stricter E or nine-anchor W repair was released because no recovery was lost.
Conditional F was released by B's Aphex/13.3 geometry-refusal cost. It failed
saved-state finite-trial qualification: original 11/16, exact-active correction
10/16. All interpolation gates passed, so the half-width repair was not
released. The unchanged 1e-7m audit direction exceeded the usable local
neighbourhood under the conservative global Gaussian momenta bound at some
curved endpoints. Raw injectivity does not qualify the projected pipeline.
Both failed qualification bundles remain preserved; **F had zero fresh fits**.
R/H/W2 and unreleased repairs are explicitly unrun.

The four development screens cost 939.667s at the internal audited boundary
(961.948s including case scoring/setup); F qualification states cost 39.370s
across both preserved attempts. These development/diagnostic costs are separate
from deployment and included in the actual overnight elapsed time. Complete
child-process timings, validation logs, numerical failures and queue waits
remain available. Actual closeout: **2026-10-05 03:19:15 UTC**, elapsed
**101.91 minutes** since authorized launch; within the eight-hour ceiling.

Validation: 218 package/campaign plus 348 shared checks before baseline;
W focused 20 and regression 554; F focused 12 and regression 560; exact-active
correction 35 focused/package/modal checks. Original failed preflight/fixture
logs are preserved. Final comparison/receipt/source/input read-back and visual
QA completed. No unrelated benchmark or reference inputs were modified.

**ON-001 is closed.** The retained E option is a measured speed improvement,
with the same four recovery failures. ON-002 is separately authorized and owned;
this result does not claim GauGal parity or absorb its unfinished adapter.
ON-003 independently closed at a negative circle control, without qualified
full-field/derivative/inverse integration. Future noise/material/measurement
coverage or a targeted resolution-response experiment needs its own named plan
and approval; no further ON-001 tuning is launched.

Artifacts: [all-30 comparison](../../../../results/validation/cleaned_interfaces/ON-001/final_table.md),
[boundary gallery](../../../../results/validation/cleaned_interfaces/ON-001/confirmation_boundaries.png),
[timing plot](../../../../results/validation/cleaned_interfaces/ON-001/confirmation_timings.png),
[structured comparison](../../../../results/validation/cleaned_interfaces/ON-001/final_comparison.json),
[evidence index](../../../../results/validation/cleaned_interfaces/ON-001/README.md).


## Preserved execution record

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

## E — required-accuracy exit

Completed **4/8 recovered**, retaining all B successes with no new recovery.
Audited endpoint times: circle 4.23s, c_shape 23.65s, kite 16.82s and star
29.37s. Median paired speedup **1.430x**, P10 **1.213x**: E qualifies for W but
not the 2x major target. All exits used a full-real accepted-state criterion
and passed current endpoint audit; no truth informed stopping. Kite stopped
at RMS 0.1883mm and Hausdorff upper bound 0.6647mm, within unchanged gates.
No stricter repair is released because there is no screen regression.
G is not combined. **W parent is E**, with initial seven-frequency proposals
and exact original full-frequency acceptance. Conditional F remains eligible
if no W major screen result closes into confirmation.

W focused preflight: **20 passed**. Adversarial subset improvement/full loss
increase rejects, expands the omitted worst frequency and rebuilds the model.
Selected evaluations are reused exactly when expanding to the full catalog,
all work is charged, relative weights are renormalized for proposals, and
full weights remain unchanged for acceptance. At residual below 0.01, all
19 return for polishing. W checkpointing is explicitly refused without W2
qualification. Its default-disabled implementation is in the maintained
package, independent of benchmark/scoring.

Published ON-001 milestone commits: B `a8c50ded`, G `eead6877`, E `4333b13a`.
Other tracks may publish independent commits on the same branch between them;
actual numerical source hashes in every batch remain authoritative.

W pre-dispatch package/shared regressions: **554 passed**, 15 warnings,
165.33s. EW screen dispatched with E as its named parent. Full acceptance
retains production/refined original loss and every per-frequency numerical
gate. Added frequencies persist to stage end, the set grows to at most nine
then all 19, and each change rebuilds the proposal model. All-19 polishing
begins below maximum full residual 0.01. Defaults remain full-frequency.

## EW — working-frequency proposals on E

Completed **4/8 recovered**, preserving E and B successes, adding none.
Every common success was slower than E: circle 4.27s, c_shape 27.42s, kite
18.74s, star 33.31s versus E's 4.23/23.65/16.82/29.37s. W does not qualify
marginally and is **closed screen-negative**. No nine-anchor repair is
released because it did not lose a recovery. The combination is not retained
merely because E still makes it faster than B. Full acceptance stayed exact,
all numerical work was charged, and the source-hash check passed.

F is now the single conditional arm, released by B Aphex13.3 invalid geometry
using 50.3% of its fitting time. R/H/W2 will not run. F keeps the base
coefficient cap and the independently qualifying E choice, replaces G's
clipping and keeps W disabled. Qualification precedes its fresh eight-case
screen. E remains the best qualifying existing recipe if F closes.

F implementation preflight: **12 passed**, including zero and actively clipped
complete field FD in both real/damped catalogs, the raw lower-Lipschitz bound,
exact zero update, circle expansion, projection refusal and separate one-sided
checks at the clipping kink. One initial test fixture was clockwise; its
original failed log is retained and the fixture corrected. The implementation
uses the analytic derivative of the complete discrete projection of its own
interpolated field at zero, including speed, arclength weight and phase. The
Gaussian saddle solve is linear in coordinates and scaling is locally identity
at zero; this does not reuse the ordinary normal-map tangent. Nonzero clipping
is included in the finite-direction qualification.

## F qualification — original width

Pre-dispatch regression gate: **560 passed**. Qualification completed all 16
saved states (eight starts, eight B endpoints), with zero/active clipped
field checks in real/damped catalogs. **11/16 states passed**. Every initial
circle passed; several curved endpoints failed the complete-trial FD gate.
All interpolation gates passed (condition estimates below 1e12 and relative
velocity errors below 1e-4), so the half-width repair is **not released**.
The source-hash check passed and original failed evidence is preserved in
`qualification_F/`. No fresh F fits have been launched.

The zero-state FD errors on kite/star appear consistent with clipping at the
unchanged 1e-7m audit perturbation. The first active-direction diagnostic used
a geometry FD tangent at half that step; a focused implementation correction
will replace that tangent with the exact derivative through the active norm
bound and discrete projection, then repeat this bounded qualification once.
The fixed endpoint FD step and original acceptance tolerances remain unchanged.

## F closeout and frozen finalist

Exact active-scaling derivative preflight: **35 passed**. One corrected repeat
of all 16 saved-state qualifications completed; **10/16 passed**. F remains
unqualified, so **F closes qualification-negative, with no fresh F screen**.
The permitted width repair is not triggered: interpolation gates all passed.
No further map repair or R/H/W2 branch is opened.

At the saved kite/star endpoints, the fixed 1e-7m zero-state audit directions
have clipping factors **0.06994196** and **0.17744565**. Their predicted
relative discrepancy `1/alpha-1` is **13.2975691** and **4.6355283**, matching
observed real-field FD errors **13.2975692** and **4.6355283**. This diagnoses
an insufficient usable local neighbourhood under the conservative global
momenta bound at these coordinates. Field/column numerical agreement can
remain good while the unchanged finite-trial gate fails. Exact active finite
derivatives also fail that prescribed FD check on some endpoints. The raw
ambient injectivity guarantee is consequently insufficient for this pipeline.
Original and corrected failed evidence remain in `qualification_F/` and
`qualification_F_exact/`, including all directions/configurations/sources.

**Finalist frozen: E only**, required accuracy .003, ordinary certified spectral
map, modal Müller, G/W/F disabled, centred start, localization none, unchanged
policy schedule/coefficient caps/resolution and endpoint gates. Confirmation
will run all 30 fresh B/E pairs, each contiguous under compute/source locks,
releasing locks between pairs. Per-pair source/input checks and publication
are required. Screen selection is development evidence, not generalization.

Confirmation uses contiguous B/E pairs, releasing compute/source locks before
reporting and publication and between every pair. Each completed/failed pair
is validated and committed/pushed independently. Primary confirmation time
runs from campaign case entry through fit-return (including backend setup and
final fit-result output); truth scoring and fresh Python imports are excluded.
Internal fit/audit timers and complete child-process wall times remain separate.
The screen used the same internal fit boundary for all screen arms. These two
timing boundaries are reported explicitly rather than silently mixed.
A read-back of the eight recorded B/E screen pairs reproduced the original
median paired speedup; sealed inputs and the frozen finalist were verified.

The historical PC-001 M1 inventory was read back: 26/30 recovered, with
exactly the three Aphex contrasts and hook13.3 failing. Confirmation will
compare the fresh B and E sets against that inventory, including cap-related
mismatches if any. Early matched circle/kite pairs have no recovery regression;
full-suite classification is withheld until all 30 are complete.

Screen timing metadata correction: `screen_paired.json` now explicitly names
its internal fit-runner boundary. Original screen receipts predate
`audited_output_seconds`; the numeric times and ratios are unchanged.
Full confirmation uses the broader case-entry-to-fit-return boundary specified
above. This prevents the shared summary format from implying identical timing
boundaries across the development screen and confirmation.

All 30 fresh pairs completed at approximately 03:11 UTC: **B 26/30, E 26/30**,
exactly the historical recovery set, no regressions or additions. The median
paired audited-output speedup is **1.545838x**. Two sequential declared timing
repeats are running. A read-only gallery-generation process inadvertently
overlapped the first repeated circle pair; its numerical evidence is preserved,
its timing is excluded, and one circle-only uncontended replacement will use
the remaining declared confirmation allowance. No numerical recipe changes.
