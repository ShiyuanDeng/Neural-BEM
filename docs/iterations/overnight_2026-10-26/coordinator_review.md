# Coordinator review

## Questions

1. Does each implementation test its stated question with the saved states,
   accuracy thresholds and full costs specified in its plan?
2. Do the results support a useful next decision, including a negative answer?
3. What can be reported to a supervisor as established progress, and what
   remains unproved?

## Execution

The user requested three parallel GPT-6.1 agents with high reasoning and
coordinator review, with no time limit. The historical morning deadline does
not limit this execution. All work uses the existing `organised` checkout.

The main studies used saved states without new inverse fits. Production
solver code is unchanged. The positive TA-001 result triggered its planned
conditional four-fit continuation, with an adapter in `experiments/`.

CPU allocations are 0–5 for FI-001, 6–11 for TA-001 and 12–17 for IS-001,
with single-thread BLAS and less than 6 GB per track. IS-001 used CUDA for
production profiles and saved systems, then released it to TA-001.

Each agent owns its experiment and evidence paths. The coordinator commits
completed steps and verifies pushes. Shared-checkout tracked edits initially
blocked two pulls; committing the ready work resolved this without stashing,
discarding work or creating branches.

## Review and corrections

- **Saved inputs:** H3's final carried state is K136/Ku128, not the stale
  plan's K192. Refused NR-001 trial coefficients are saved, permitting direct
  reconstruction checks. Both corrections are explicit in the reports.
- **FI-001 accuracy:** fixed deterministic nodes, unchanged geometry directions,
  held-out fields and normalized frequency-stacked Jacobian columns match
  the intended comparison. Exact-node replays match the production path.
- **FI-001 timing:** CPU timing does not establish CUDA savings. Original
  measurements omit final array packing; this is disclosed and corrected
  for future runs. No rerun was warranted: every approximation fails accuracy.
- **TA-001 geometry:** positive speed before cropping does not prove a valid
  stored curve. The implementation checks the cropped curve and exact
  physics. Closure failures are preserved. First-order checks verify the
  chart's actual finite map, including closure and projection.
- **TA-001 inference:** certificate failure alone proves neither a cusp nor
  a distant touch. Continuous local searches distinguish the observed
  geometries, with their non-rigorous scope disclosed.
- **IS-001 algorithms:** actual rank-aware block Arnoldi supplements global
  GMRES. The report must distinguish these algorithms and include all
  forward and reciprocal right-hand sides.
- **IS-001 scaling:** the source and reciprocal right-hand sides differ by
  roughly six orders of magnitude. Aggregate residual alone concealed field
  error. Per-column normalization corrected it; the original failed accuracy
  evidence remains saved and the tolerance is unchanged.
- **IS-001 costs:** anchor factorization and observed reuse must accompany
  solve timings. First-use and cached-geometry profiles answer different
  questions and must remain separate.

## Assessment so far

FI-001 answers its scoped question decisively: 0/36 tested settings pass.
It does not determine the minimum node count above 14 or reject rational,
phase-adjusted or local-frequency approximations. Failure on peanut c4
shows high contrast is not necessary, but does not isolate contrast effects.

TA-001 establishes a finite-map benefit in 3/4 reconstructed refusals at
matched fractions. It corrects the earlier blanket near-touch explanation.
This is the most constructive local result; recovery requires the separate
continuation evidence and cannot be inferred from lower local losses.

IS-001's completed production-size comparisons support keeping LU at Ku64
and Ku128 for the tested implementation. Its larger-size and anchor-stress
results will determine the range of that conclusion.

## Final supervisor assessment

Pending the remaining crossover and four-fit continuation evidence.
