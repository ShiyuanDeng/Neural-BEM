# BIE-004 — coupled analytic shape Jacobians

**ANALYTIC_JACOBIAN_QUALIFIED_AND_FASTER**. Execution status: **COMPLETE**.

The experiment differentiates the actual multi-interface Kress system, including
both directions of every cross-object interaction, incident traces, receiver
weights and normals. One base LU is reused for all 34 gauge-coordinate
directions and all 24 source right-hand sides. The existing self-interface
derivative machinery is imported unchanged. Production numerical files and the
topology controller remain unchanged; no inverse was executed.

## Accuracy

| Saved two-star state, 1.25 GHz / 256 nodes per object | Full residual Jacobian relative error | Worst column relative error |
|---|---:|---:|
| common | 1.414e-07 | 3.032e-07 |
| terminal | 1.405e-07 | 4.647e-07 |

Both matrices have 48 real residual rows and 34 production gauge-coordinate
columns. The reference is central FD with coefficient step 1e-5, using the
actual `incremented(...).polar_angle_gauge_fixed()` retraction and fixed
production residual normalization. Full-matrix and worst-column thresholds
are 1e-4. Saved matrices can be re-audited without physical solves.

- Operator comparisons: **1008**, failures:
  **0**. Worst nonzero scaled block relative
  error: **2.568e-06**. Zero-derivative
  blocks use the declared base-scaled roundoff allowance, not an arbitrary
  unit-size absolute tolerance.
- Worst selected JVP error against 1e-5/5e-6 FD:
  **3.990e-07**, threshold 1e-4.
- Worst 256/512 forward discrepancy:
  **6.672e-14**, threshold 2e-7.
- Worst sampled 256/512 analytic sensitivity discrepancy:
  **9.500e-12**, threshold 2e-5.
- The current optimizer's 1e-4 FD step was also measured on selected directions;
  its worst discrepancy against the analytic value is
  **2.617e-05**. This is a separate
  scale-accuracy observation, not an inverse-recovery claim.
- Noncircular mixed-direction Taylor ratios on step halving:
  **4.0006, 4.0003, 4.0001, 4.0001, 4.0001, 4.0000** (expected local
  second-order ratio 4). The displacement of the gauge retraction is recorded
  in [gauge.csv](gauge.csv).

Wiring includes reduction to the existing single-interface analytic routine,
unequal component node counts (24/32) and native periods (2π/3.7), individual
translations, collective translation and a noncircular shape direction. Moving
one object changes cross blocks; translating both leaves A invariant. All
physical checks are charged to the same ledger.

## Full-Jacobian cost

Benchmark status: **COMPLETE**. Timing includes fresh geometry,
retraction, full parent assembly, primal solve, derivative assembly, tangent
solves, receiver evaluation, primal consistency checks and ledger overhead.
The benchmark uses the terminal state, 1.25 GHz, 256 nodes per object, 34
directions and 24 source RHS in both arms. It compares the production FD
mechanism at the finer declared step of 1e-5 against analytic derivatives.

| Method | Paired repetitions | Median [min, max], seconds | LU factorizations per full Jacobian | RHS batches |
|---|---:|---:|---:|---:|
| analytic | 3 | 26.249 [26.214, 26.277] | 1 | 35 |
| fd | 3 | 49.083 [49.023, 49.175] | 69 | 69 |

Measured median speedup: **1.87x**. Timing ranges nonoverlapping: **True**. No detected concurrent repository numerical worker: **True**.

Assembly-equivalent counts conservatively charge one full assembly for every
analytic directional recomputation. Actual recomputed/skipped self and cross
kernel blocks appear in [controls.json](controls.json); unchanged blocks are
reused. Derivative matrices are streamed, not retained for all 34 directions.
Finite differences are used for validation/comparison only.

## Work and reproducibility

Counts across attempts: **703/800** assembly equivalents,
**200/300** analytic directional calls,
**504/600** factorizations,
**703/1000** RHS batches. Numerical wall time:
**595.58/1800 s**. Peak process RSS:
**1.690/8 GiB**. Four algebra tests passed in the
continuation. The first attempt had a malformed negative test: it omitted the
mandatory first-derivative array and therefore raised before the intended
node-grid check. That one test-input correction is preserved in the previous
bundle; it consumed zero physical assemblies and its elapsed time is carried
forward. There was no change to a numerical formula or a scientific threshold.

See [manifest.json](manifest.json), [approved_plan.md](approved_plan.md),
[commands.md](commands.md), [work_ledger.jsonl](work_ledger.jsonl), and
[tests.log](tests.log). Exact experiment sources are preserved in
`measured_sources/`; saved geometry coefficients, observations, acquisition,
source hashes and package versions are in the manifest. The reporting audit
replays the Jacobian errors from the stored matrices and reconciles counters.

The support is fixed topology, shape-only, disjoint lossless nonmagnetic
same-material inclusions, fixed acquisition, and the tested gauge-fixed
Cartesian subspace. Magnetic/lossy media, material/source derivatives,
off-subspace re-gauging, topology-event derivatives and inverse integration are
outside this experiment. Accuracy here is a diagnostic tier, not qualification
for every existing inverse endpoint tolerance.

## Single recommended next action

**Prepare one opt-in integration and matched inverse validation after topology reaches a stable integration point; preserve current defaults.** No successor or inverse is executed by this closeout.
