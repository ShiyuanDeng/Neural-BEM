# ON-002 resumed results — adapter incomplete

**Decision: ADAPTER_INCOMPLETE.** The authorized `go on ON-002` resumption
finished its allowed scale/precision repair, but no registered-grid system
reached the 1e-6 true residual at the fixed 200-iteration BiCGSTAB cap.
The strict ON-002 stop rule closes the adapter and blocks fitting. This is
an incomplete comparison, not evidence that either inverse method is better.

The final 256/224 control was the prescribed start circle, contrast 0.5,
0.25 GHz real frequency, in complex128. Its true residual was **7.0456e-6**.
Its raw sharp-disk field discrepancy was 1.1318e-4, but the solve failure
prevents qualification or a reliable grid-error conclusion. Its system and
sensor adjoint errors were 6.44e-16 and 5.16e-16, with exactly zero off-pair
readout. The occupancy gradient was correctly refused.

## Repair and independent checks

The pinned external BiCGSTAB clamps squared complex-division denominators at
1e-30. Metre-scale Galerkin testing areas and the frozen 1e-6 source strength
activate that absolute floor. The adapter now divides its equations and RHS
by the common physical testing area, normalizes each forward/adjoint RHS to
unit 2-norm inside the pinned solve, then restores the physical solution.
The exact equations, physical pixel kernel, receiver cell area, paired mask
and signed contrast chain rule are preserved. No GauGal source was edited.

A 12/10 dense control verified FFT assembly at 1e-12, but failed the solve
cap: testing-area normalization alone yielded residual 0.02940; unit-RHS
normalization improved it to 6.67e-5. Those failed checks are retained.
**Seven regression tests pass**, including independent dense operator,
direct-solve and complete-gradient controls at all three contrasts on an
8/4 system, plus the original disk, kernel and paired-mask controls. This
small-system result does not qualify the registered resolutions.

## Registered-grid evidence

| Batch | Pixels / centres | Precision | Checks | Solve / field / FD gates | Diagnostic seconds |
|---|---|---|---:|---|---:|
| resume128_float | 128 / 112 | complex64 | 12 | 0 / 0 / 0 | 10.954 |
| resume128_double | 128 / 112 | complex128 | 12 | 0 / 0 / 0 | 34.063 |
| resume256_double_weak_control | 256 / 224 | complex128 | 1 | 0 / 0 / 0 | 17.610 |

The two 128-grid batches each covered contrasts 0.5/4/13.3 at 0.25 and
2.5 GHz, real and damped. The single complex128 fallback was used after
single-precision true-residual failures. Double precision still qualified
0/12 solves. The mandatory weak 256-grid control then failed, exhausting
the declared adapter repair. The remaining 256 controls and 512 escalation
were not released. Algebraic and paired-sensor adjoints passed all 25 resumed
checks; full-grid occupancy derivatives remained blocked by failed forward
solves. Remaining causes at the registered cap are unresolved; this report
does not claim precision alone, physical discretization alone, or a layout
error explains them.

The original 128-grid batch remains immutable: 0/12 solves qualified,
residuals 0.91–1.00. Its previously local native arrays are now committed too.
No observation was regenerated, target geometry selected a setting, or
reference implementation changed. B remains pinned to launch `6f2c1408` in
its unchanged source archive; it was not rerun under unqualified G physics.

## Scope, validation and receipts

B/G fitting, hybrid H, all-30 comparison, recovery gallery and timing repeats
are **unrun because the adapter gate failed**. No speed ratio or recovery
winner is published. Proposed GP-001 remains unrun; it is a separate contract.
This run stayed on the recorded existing `feature/shape-frequency-continuation`
launch branch while RG-001 used the checkout. No branch/worktree was created.
Compute/source/Git locks separated numerical batches and publications; active
RG-001 changes were preserved.

Every resumed batch completed, verified unchanged numerical/external source
hashes, and saved checked native predictions, independent Mie references,
occupancy/coefficient arrays, solver statistics, adjoints, refusals and logs.
Final TG-002 seal verification passed all 30 cases. The focused tests pass,
source snapshots and baseline archive match their hashes, and whitespace
validation passes. The original interruption and diagnostic failures stay
in the evidence rather than being overwritten.

- [Plan and resume registration](../iteration_01/03_plan.md)
- [Original interrupted record](01_results.md)
- [Machine-readable closeout](../../../../results/validation/cleaned_interfaces/ON-002/closeout.json)
- [Resumed 128 single-precision receipts](../../../../results/validation/cleaned_interfaces/ON-002/resume128_float/summary.json)
- [Resumed 128 double-precision receipts](../../../../results/validation/cleaned_interfaces/ON-002/resume128_double/summary.json)
- [Final 256 weak control](../../../../results/validation/cleaned_interfaces/ON-002/resume256_double_weak_control/summary.json)
- [Validation and failed diagnostics](../../../../results/validation/cleaned_interfaces/ON-002/validation/)

Closed 2026-10-05T10:19:29.506081+00:00; resumed wall time including queueing/reporting
through this receipt: 947.817s, plus 554s charged from the first launch.
The three registered-grid diagnostic batches took 62.628s;
these are adapter costs, not inverse comparison timings.
