# SPD-004 — a pipeline change delivers additional full-inverse speedups

2026-09-16. **Execution COMPLETE.** The user authorized the architecture
investigation with “investigate go”; [dispatch plan](../iteration_03/03_plan.md).
Owner/reviewer: Codex `/root`, self-review; no independent review claimed.

The first architectural change removes mandatory continuation when a
training-only check finds the handoff already adequate. **All ten fresh full
workers pass the original recovery checks.** Both death/split repetitions skip
continuation; merge fails the readiness screen and completes the unchanged
fallback. Performance-contract verdict: **PASS**.

| Full case | Fast baseline | Readiness pipeline | Speedup | Repetitions per arm |
|---|---:|---:|---:|---:|
| death | 236.26 s | 46.12 s | 5.12x | 2 |
| split | 222.32 s | 33.10 s | 6.72x | 2 |
| merge | 406.34 s | 403.52 s | 1.01x | 1 |

Death and split rows use median worker times from two interleaved pairs each.
Merge is one complete pair; its relative runtime change is -0.69%.
Treat that small difference as effectively unchanged runtime, not an established
fallback speedup. The screen still adds eight physical systems.
Times include startup, original-start topology, screening, any continuation,
and independent endpoint checks. Baseline is the already accelerated analytic
CPU pipeline, not historical FD. No GPU change is involved.

Maximum paired difference in 4096-point sampled boundaries: `0.000e+00 m`;
maximum coefficient difference: `0.000e+00 m`. All topology event,
geometry, training, independent evaluation and numerical gates pass. Actual
physical and directional work reconciles, and source/input integrity passes.

[Full measured report](../../../../results/validation/speedup/SPD-004-20260916-pipeline-readiness/README.md) · [paired CSV](../../../../results/validation/speedup/SPD-004-20260916-pipeline-readiness/comparison.csv) · [verification](../../../../results/validation/speedup/SPD-004-20260916-pipeline-readiness/verification.json).

## What the big-picture investigation found

The pipeline was imposing continuation exposure after some cases had already
reached adequate reconstruction quality. A full-training readiness decision
removes that whole optimizer phase on those cases. It preserves independent
endpoint assessment and explicitly leaves stationarity/stage exposure unmeasured.
The gate uses residual <=1e-5 at every training frequency on both grids, plus
the original numerical tolerances; evaluation data and truth never select it.

The saved twelve-scene audit separates different architectural problems:

| Situation | Cases | Next decision |
|---|---|---|
| Adequate handoffs | repeated-birth, death, split, far-two-circles | Stop before mandatory fitting |
| Conservative gate retains an adequate handoff | mixed | Keep fallback; later study task/noise-aware stopping |
| Real shape/frequency refinement needed | merge, central-ellipse-star | Preserve continuation; investigate adaptive capacity |
| Continuation still fails recovery | far-two-stars | Diagnose search/information choices |
| Finer-grid handoff refused | far-ellipse-star, empty-ellipse-star | Bring final numerical feasibility into topology search |
| Topology wall limit reached | enclosing-ellipse-star, far-three-shapes | Investigate topology growth and effort allocation |

[Detailed audit and provenance](../../../../results/validation/speedup/SPD-004-20260916-pipeline-readiness/architecture_audit.md).

## Qualification, scope and next priority

26 focused tests pass; four saved-handoff physics checks use 32 systems and
agree with archived predictions to 5.244e-15. Full-case work counts reconcile.
The timed controls cover three scenes, not the entire suite; the data are
noiseless and the conservative gate has not been qualified for noisy data.
Host-wide process isolation is unverified in the sandbox. All arms are
sequential with single-thread BLAS; individual timings remain available.

The implementation is experimental, with no production-default promotion.
After early completion, topology is the dominant remaining cost on the
measured easy cases. Prioritize earlier final-grid feasibility and adaptive
topology/shape/data decisions for harder scenes, and reprofile before a GPU
port. SPD-003 exact reuse remains an unexecuted compatible optimization.
