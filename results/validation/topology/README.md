# Topology research evidence

| Bundle | Role and outcome |
|---|---|
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
