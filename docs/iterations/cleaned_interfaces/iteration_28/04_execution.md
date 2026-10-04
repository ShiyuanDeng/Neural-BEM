# PC-002 execution

Approved by the user's “yes” and request to expedite validation and run the
fair nodal spline on the ten scenes. The priority amendment in 03_plan.md
controls execution: NS only, 30 TG-002 cases, one fit worker, four frequency
threads, explicit CUDA, one BLAS thread, no excluded warm-up or localization.

Implemented in the maintained package: bounded exact-curve geometry reuse,
band-matched even nodal seeds, stage-entry field/Jacobian selection, unchanged
trial refinement gates, dispatch-based accounting, selection receipts, and
native plus independent N1024/N2048 endpoint audits. No trial promotion.

Focused validation: 177 unique affected checks pass; one corrected test-fixture
failure is retained in the validation bundle. Frozen TG-002 input seal verifies.
Source is committed before the first fit. Campaign manifest records the exact
source commit and inputs SHA256. Broader comparison arms/repeats are deferred.

NS launched from `1b4dfdab3704967828df75d189e845bd1a6bc08c` after commit/push.
The manifest records this fit source and the frozen input SHA256. Only report
formatting/gallery additions and execution documentation change while fitting;
all maintained numerical sources are unchanged from that commit. The protocol
bundle records their SHA256s and actual environment/worker settings.

Results complete: 30/30 cases, 26 recovered (9/9/8), N130/N386 throughout,
zero escalations/promotions/fallbacks. Median fit 48.18 s, median total 100.58 s;
54.82 s median audits. See [05_results.md](05_results.md).

Post-fit interface cleanup moves independent reference token selection into
NodalKress.audit_reference_resolution; the generic audit no longer selects
nodes by backend name. Resolutions and arithmetic are unchanged. The final
package/interface suite passes 51 tests, including an opaque backend-name
probe. Reports/gallery are regenerated and visually checked; source/input
and all 30 work receipts pass read-only validation. No additional fits.
