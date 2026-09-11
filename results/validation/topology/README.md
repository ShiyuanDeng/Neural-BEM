# Topology research evidence

| Bundle | Role and outcome |
|---|---|
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
