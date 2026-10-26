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

IS-001 supports keeping LU at Ku64 and Ku128 for these implementations.
The first measured solve-only crossover is Ku512; a roughly 570 ms anchor
needs four equal-cost future targets to repay the fastest method. Those
future targets were not observed. A 1.139 mm accepted step breaks stationary
contraction at real frequency, while GMRES still converges more slowly than LU.

## Are the questions answered?

| Question | Assessment | Remaining limit |
|---|---|---|
| FI: how many frequencies suffice? | None of the six tested counts, 4–14, passes on any curve. | The true minimum and other interpolation families are unknown. |
| FI: worthwhile saving? | No qualified saving for either tested arm. | CPU timings cannot establish CUDA savings; no accurate candidate warranted timing again. |
| FI: does high contrast break it? | Failure also occurs at contrast 4. | Shape and contrast are confounded; a causal contrast effect is not isolated. |
| TA: what causes the refusals? | Different local/nonlocal geometric features are measured. | These are numerical minima, and features do not alone establish certificate-failure causality. |
| TA: does the chart help? | Three matched saved steps improve, but the four fresh fits recover 0/4. | The local advantage does not establish a reliable trajectory. |
| TA: does the simple coefficient bound help? | It is inconclusive at all four accepted bases. | This does not reject sharper bounds or prove invalidity. |
| IS: where does time go? | Current CUDA/CPU components, first-use and cached times are recorded. | Only the highest real/damped frequency, not the full fit. |
| IS: can iterations beat LU now? | No for both tested dense iterative methods at Ku64/128. | This is not a lower bound on all possible iterative implementations. |
| IS: when could they win? | First measured solve-only win at Ku512; four equal-cost reuses repay the best anchor. | Reuse is modeled, not observed over four changing targets. |

## Final supervisor assessment

**Satisfactory as a focused research-progress report; not a demonstrated
solver advance.** The work answers the registered operational decisions,
preserves negative results, and distinguishes local success from recovery.
No implementation blocker remains in the reviewed experiment paths.

The four fresh chart fits recover **0/4**, the same count as NR-001. Hook
reaches M15 rather than stopping in M11 and lowers RMS error from 8.281 to
6.193 mm, still far above the 1 mm requirement. All three aphex RMS errors
worsen. Passing final numerical checks on two early endpoints is not
recovery: their data residuals and shape errors remain large.

A supervisor can reasonably count three concrete contributions:

1. A quantified negative result rules out the tested full-band polynomial
   approximation, without overclaiming that frequency reuse is impossible.
2. Reconstructed failures correct a misleading common-cause explanation.
   The chart changes local acceptance, but four fresh trajectories show
   that this mechanism alone does not solve the recovery problem.
3. Current production profiles and matched-accuracy solves explain why LU
   remains appropriate, and identify the size/reuse conditions for reconsidering it.

A supervisor expecting a new recovery, a production speed-up, or a general
convergence guarantee would **not** have that evidence here. The appropriate
progress claim is stronger diagnosis and better experiment selection.

## Decisions after review

- Keep exact frequency evaluation and LU in the maintained solver.
- Keep the chart experimental. Prioritize understanding the new recorded
  geometry refusals before combining it with a barrier or step rule.
- Treat rational/phase-adjusted frequency surrogates and large-system anchor
  reuse as separate future hypotheses, not already validated improvements.
- Do not run further fits to search for a favorable result. The prescribed
  four-fit continuation is exhausted; the negative answer is itself complete.

The review led to concrete iterations: corrected saved-state provenance,
benchmark-matched Jacobian errors, actual block GMRES, RHS normalization,
finite-band chart checks, safe closure backtracking, an independent chart
implementation review, and the pre-planned full-fit continuation.
The stopping reason is sufficient evidence for these scoped decisions,
not time pressure or a requirement to produce positive results.

