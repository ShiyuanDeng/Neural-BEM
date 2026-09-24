# SC-028 active-band diagnostic — declared before dispatch

The original P=48 preflight failed and remains failed. This diagnostic asks
whether the discrepancy is present in the bands used by the proposed
inverse. It does not dispatch recovery or relax the original gate.

At the same six SC-025 endpoints and the same 1.5/2.5 GHz frequencies,
recompute N=512/1024 Jacobians. Report relative errors for M=9,11,13,15,17,19
and 48, the worst full-atlas column and its relative sensitivity, and the
whole-matrix relative discrepancy. No changes to geometry or normalization.
Budget: 48 solve/reciprocal units, ten minutes, six single-thread workers.
Owner: Codex. Authorized within the user's requested analysis and testing.

This separates numerical errors in the actual update space from
relative errors in high-order atlas columns. A successor plan, written
before recovery, is required if the scope of qualification changes.
