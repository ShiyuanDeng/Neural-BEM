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

Results: pending in results/validation/cleaned_interfaces/PC-002/NS.
