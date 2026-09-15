# Topology research evidence

| Bundle | Role and outcome |
|---|---|
| [TOP-025 all-scene gallery](TOP-025-20260915-210356-all-scenes-current/README.md) | 7/12 fresh scenes pass the current H → cumulative-F protocol; twelve scene videos plus overview; all failures retained |
| [TOP-024 bounded damping pair](TOP-024-20260915-201101-bounded-damping-pair/README.md) | NEITHER_ARM_RECOVERED; 7,504 new calls, 0 failed/refused. Unchanged 256/512 and recovery gates; fresh/full-suite qualification remains open |
| [TOP-023 terminal model diagnosis](TOP-023-20260915-181302-terminal-model/README.md) | Selected derivative checks pass; damping 1e-2 gives 3.978× baseline step gain using 8 versus 24 candidate calls. 396 total calls, zero failed. No inverse or recovery qualification; bounded continuation comparison next |
| [TOP-022 fresh direct-frequency integration](TOP-022-20260915-165552-fresh-direct-two-stars/README.md) | Numerically qualified but recovery fails: 9.755053 mm, IoU 0.830130, worst development error 0.619185. 8,247 charged calls; maximum iterations with terminal gradient 0.014276, above tolerance. No full-suite release |
| [TOP-020 fresh two-star integration](TOP-020-20260915-153359-fresh-two-stars/README.md) | All numerical gates pass but fresh recovery fails: 9.97354 mm, IoU 0.828248, worst development error 0.601150. 9,375 charged calls, 9,308 completed systems, 67 geometry refusals; TOP-021 not released |
| [TOP-019 qualified merge pair](TOP-019-20260915-144340-qualified-merge/README.md) | Both K=17 S/F arms recover at 256/512. F improves boundary/prediction accuracy by 4.01×/5.08× for 3.77× work. 6,232 completed solves, zero failed; all quotas and numerical gates pass |
| [TOP-018 S/F video](TOP-018-20260915-two-star-video/README.md) | 50-second side-by-side playback of all saved accepted-state records, from COMMON to the prescribed final endpoints; no new numerical solves |
| [TOP-018 qualified two-star pair](TOP-018-20260915-resolution-qualified-pair/README.md) | Both 256/512 schedules qualify; F recovers at 0.00167644 mm while S fails at 11.793168 mm. 8,336 completed solves, zero failed; original post-schedule reporting failures retained and repaired without reruns. No promotion or successor |
| [TOP-017 engineering follow-up](TOP-017-followup-20260914-engineering/README.md) | One fresh central-circle pipeline passes; three saved two-star states qualify at 256/512. Historical evidence reused by TOP-018 |
| [TOP-017 staged continuation](TOP-017-20260914-staged-continuation/README.md) | Central F recovers; historical two-star arms stop at 128/256 numerical gates. Central success and the merge-control interpretation remain preserved |
| [TOP-009 independent review](TOP-009-20260912-review/README.md) | 13/14 ladder refinements stopped on small loss change; neither stationarity nor unique recovery is established. Promotion counters repaired; 108 focused tests pass. Proposed next diagnostic separates stopping from stationarity |
| [TOP-010 stopping versus stationarity](TOP-010-20260912-stopping-vs-stationarity/README.md) | Neither saved state is stationary: terminal gradient 4013x the optimizer's tolerance with a full-rank Jacobian, and three restarts of the unmodified optimizer recover 1.7x objective. Matched error moves 11.849 to 11.991 mm and IoU is unchanged, so repairing the stopping rules would not recover these shapes |
| [TOP-009 bandwidth capacity](TOP-009-20260912-bandwidth-capacity/README.md) | Failed stage 2: shape modes fit 248x better but final geometry/holdout worsen. Stage 4 exhausts K=9 and reaches 11.849 mm, still worse than the start and 74,159x above the known truth objective. Independent review qualifies the original local-minimum and data-sufficiency claims |
| [TOP-008 feasible finite differences](TOP-008-20260912-feasible-fd/README.md) | 24 inversions on the same frozen scenes: measuring the feasible side of a refused probe frees the pinned component from 8.000 mm to 22.737 mm, returns 10/12 runs against 9/12 and takes `split` to 0.000023 mm at a quarter of the solves — with the pass count unchanged at 5/12 |
| [TOP-007 videos](TOP-007-20260911-refined-feasibility/videos.md) | Every guarded scene as an inversion video, with the default-arm before/after pair on the two scenes the guard rescued |
| [TOP-007 refined-feasibility report](TOP-007-20260911-refined-feasibility/README.md) | 24 inversions on the same frozen scenes: the guarded arm aborts nothing and returns 9/12 runs against the default's 7/12, with identical states wherever both completed and 5/12 passing in both |
| [TOP-006 broad-scene report](TOP-006-20260911-scenes-v1/README.md) | 24 attempted inversions across twelve frozen scenes; both policies pass 5/12. Distant ellipse/star fails, with all exceptions/timeouts and visible last states retained |
| [TOP-005 report](TOP-005-20260911/README.md) | Selective refinement: twenty split replays and five full-controller cases pass all declared quality and aggregate-cost gates |
| [TOP-001 report](TOP-001-20260911-comparison/report.md) | 60 paired A/B/C split replays; raw top-two policy not adopted |
| [Expanded shortlist](TOP-001E-20260911/metrics.json) | 20 exploratory three-candidate replays; Cartesian split recovery stabilizes, radial cost increases |
| [Five-case qualification](TOP-001E-controller-20260911/qualification.json) | Ten full Cartesian inversions; E fails the death training gate and aggregate cost gate |
| [Failed historical qualification](TOP-001-20260911-replay-01/README.md) | Radial historical candidate set does not reproduce at B0; Cartesian does |
| [Fresh B0 references](TOP-001-20260911-B0-qualification/README.md) | Unmodified `345038a`, two full split inversions with source verification |
| [Accounting audit](TOP-001-accounting-audit-20260911/verification.json) | Independent observation matches all 1,109 reported BIE frequency solves |

Every new replay includes portable JSON observations, original candidate trials,
trajectory, event lineage, rejection classes and work by stage. Source and
launcher hashes identify the measured code. Failed qualifications stay with the
comparison. The [track handoff](../../../docs/iterations/topology/README.md)
carries the next action.
