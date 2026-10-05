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
