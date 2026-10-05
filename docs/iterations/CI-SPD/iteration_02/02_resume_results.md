# ON-002 resumed adapter qualification

User authorization: `go on ON-002`. The resume receipt preserves the original
baseline, interruption, renewed deadlines and existing launch branch.
GP-001 is not launched. The strict ON-002 field gate still blocks fitting.

The pinned BiCGSTAB uses an absolute 1e-30 floor on squared scalar division
 denominators. Physical pixel testing areas and the frozen 1e-6 source
strength make its iterates scale dependent. On the independent 12/10 control,
removing only the common testing area gave true residual 0.02940 after 200
iterations; additionally normalizing the RHS gave 6.67e-5 at the same cap.
Both failures are retained. Exact FFT assembly agreed with dense projection
at 1e-12. This control remains unqualified at its cap.

The implemented repair removes the testing area from both sides, and
normalizes each forward/adjoint RHS to unit norm before the pinned solve,
restoring the physical solution afterward. Kernel and receiver cell-area
factors, paired readout, contrast chain rule, solver, caps and tolerances are
unchanged. GauGal remains read-only.

**Focused regression: 7 passed.** A smaller independent 8/4 dense assembly
checks operator layout, physical scaling, iterative/direct agreement and the
complete occupancy derivative for contrasts 0.5, 4 and 13.3. This establishes
algebraic correctness on that control; it does not qualify the registered grids.
The original four disk/kernel/mask controls also pass. The earlier three
failed regression attempts and the scale diagnostic are retained in validation.

Registered-grid qualification is pending. No inverse, hybrid, gallery of
recoveries or matched timing comparison is released yet.

## Registered 128/112 single-precision screen

The repaired batch completed all 12 configurations in 10.954s.
True solves qualified 0/12; field gates qualified
0/12; occupancy derivatives qualified 0/12.
All native prediction/reference/occupancy arrays are preserved and checked.
Source hashes stayed unchanged. The 200-iteration cap is retained.

The true-residual failures release the single pre-registered complex128/float64
fallback. This changes only arithmetic precision, with its cost recorded.
No second precision change, extra iteration cap or alternative solver is allowed
in this adapter phase. Inversion and timing parity remain blocked.

## resume128_double

Completed 12 checks in 34.063s; true solves qualified 0/12, field gates 0/12, FD controls 0/12. Source hashes stayed unchanged; native arrays and log were verified and saved.

| Contrast | Catalog | GHz | True residual | Field discrepancy | Field gate | FD gate |
|---|---|---:|---:|---:|---|---|
| 0.5 | real | 0.25 | 3.77e-06 | 0.000361 | False | False |
| 0.5 | real | 2.5 | 0.000201 | 0.0586 | False | False |
| 0.5 | damped | 0.25 | 7.49e-06 | 0.000404 | False | False |
| 0.5 | damped | 2.5 | 0.000114 | 0.0488 | False | False |
| 4 | real | 0.25 | 4.82e-06 | 0.00121 | False | False |
| 4 | real | 2.5 | 0.256 | 0.947 | False | False |
| 4 | damped | 0.25 | 1.41e-05 | 0.000842 | False | False |
| 4 | damped | 2.5 | 0.000435 | 0.145 | False | False |
| 13.3 | real | 0.25 | 7.16e-05 | 0.00463 | False | False |
| 13.3 | real | 2.5 | 0.0253 | 1.72 | False | False |
| 13.3 | damped | 0.25 | 4.86e-05 | 0.00334 | False | False |
| 13.3 | damped | 2.5 | 0.000489 | 0.243 | False | False |

Field discrepancies from unqualified solves cannot measure the physical grid error reliably.

The single precision fallback is exhausted. Even the weakest low-frequency
control misses 1e-6 at the 200-iteration cap in double precision. One registered
256/224 low-frequency c0.5 real control will now check whether the required
initial finer grid removes this failure. If it fails, stop at that mandatory
control: the conjunctive adapter gate cannot pass, so no additional cases or
512 escalation can release fitting under the remaining single-repair contract.
