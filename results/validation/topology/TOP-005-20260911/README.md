# TOP-005: selective candidate refinement — PASS on declared qualification

The controller can now retain its raw shortlist and also refine the best
candidate in the lowest optimization dimension, **only when the raw leader has
more directions**. This reaches the missed simple split seed while preserving
the original three-step optimizer budget. Enable it with
`--include-simplest-candidate`; the existing default remains unchanged.

**All 27 declared runs completed:** two default replay checks, twenty selective
split replays and five full Cartesian controller cases. All quality and summed
work gates pass. [Machine-readable qualification](qualification.json),
[artifact verification](verification.json), [execution log](execution.log),
[contract](../../../../docs/iterations/topology/iteration_02/03_plan.md).

## Main result

| Ten split replays per chart | Baseline A | Selective F |
|---|---:|---:|
| Cartesian worst sampled Hausdorff | 175.210848 µm | **30.803117 nm** |
| Cartesian worst 1.5/2.5-GHz holdout relative L2 | 9.684310e-3 | **3.336687e-6** |
| Cartesian total BIE frequency solves | 6,567 | **3,787 (42.3% fewer)** |
| Radial total BIE frequency solves | 2,641 | **2,641; all ten trajectories exactly unchanged** |

The unperturbed Cartesian replay changes from **175.21 µm / 1,109 solves**
to **25.91 nm / 553 solves**. All ten Cartesian reconstructions remain below
31 nm. Seven of nine perturbed runs select the same construction as the
unperturbed F case, compared with four of nine for A. Different construction
labels can still produce accurate, effectively identical circles.

[Comparison figure](comparison.svg).

## Five full-controller cases

Both arms start from each original initial state. Geometry, training and
evaluation-only holdout thresholds are the ones declared before these runs.

| Case | A BIE solves | F BIE solves | Quality gates | Exact A trajectory? |
|---|---:|---:|---|---|
| repeated-birth | 759 | 835 | PASS | yes |
| death | 811 | 907 | PASS | yes |
| split | 1,172 | 616 | PASS | no; geometry improves |
| merge | 553 | 581 | PASS | yes |
| mixed | 1,360 | 1,384 | PASS | yes |
| **Total** | **4,655** | **4,323 (7.1% fewer)** | **all pass** | |

F does **not** make every case cheaper. Extra probes in losing event groups
increase work on the four unchanged trajectories. The split savings exceed
those costs in this suite. Thus the hoped-for absence of birth/death overhead
was not achieved, even though the predeclared quality and aggregate-cost gates
pass. The policy remains opt-in; a cheaper screening rule needs a new test.

[Baseline split video](media/baseline/inversion.mp4) ·
[Selective split video](media/selective/inversion.mp4). These render saved
accepted trajectories; no physics was rerun for the videos.

## Implementation and checks

`TopologyControllerConfig.include_simplest_candidate` defaults to `False`.
`_refinement_shortlist` retains the ordinary raw top-k and adds at most one
candidate. Minimum-dimension ties use raw loss. An already simple raw leader
gets no extra candidate. Cartesian dimension is the gauge tangent dimension,
so extra coefficient storage that introduces no new direction does not trigger
extra refinement. The accepted candidate is still selected by the original
production/refined physical objectives.

- **533 inverse tests pass** ([log](tests.log)). New tests cover the third-ranked
  simple candidate, no extra work for a simple leader, tied dimensions,
  duplicate prevention, and Cartesian storage versus accessible dimension.
- Default A replays reproduce both pinned B0 reference events and final errors.
- All twenty F split inputs pair exactly with A. All saved split/controller
  trajectories are monotone and every accepted event passes both resolution
  margins. No split or controller rejection remains unclassified; see the
  [controller rejection counts](controller/rejection_counts.json). All split geometry and
  holdout comparisons pass independently of the controller gates.
- Source hashes match the executed files. Starting commit is `746c9fb` plus the
  recorded TOP-005 working tree; source identity lives in each manifest.
  The physical solver, objective, construction and gauge algorithms are unchanged.
- Costs include completed objective-frequency solves and TD solves, exclude
  final qualification/oracle work, and are not weighted by matrix dimension.
  The independent TOP-001 observer validated the ledger against actual solves.
  Up to six single-thread experimental jobs ran concurrently; wall time is
  not a controlled comparison. Both plots and the selective final frame were
  visually checked; the videos have valid 14.2/10.2-second streams.

## Reproduce

Use the repository root and the tested Python environment:

```bash
export PYTHONPATH=solvers OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
TOPOLOGY_PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
TOPOLOGY_STAMP=$(date -u +%Y%m%dT%H%M%S%N)

# Restore ignored reference arrays from verified, tracked JSON after a clone.
"$TOPOLOGY_PY" results/validation/topology/TOP-001-20260911-B0-qualification/restore_observations.py

# Full selective experiment, with a fresh result directory.
"$TOPOLOGY_PY" run_selective_topology_experiment.py --workers 6 \
  --output "results/validation/topology/TOP-005-${TOPOLOGY_STAMP}"

# Normal controller use of the qualified opt-in policy.
"$TOPOLOGY_PY" run_fourier_topology_controller.py --chart cartesian --profile full \
  --include-simplest-candidate --skip-video \
  --output "results/validation/topology/selective-controller-${TOPOLOGY_STAMP}"
```

This is a bounded noiseless, separated, same-material synthetic qualification.
It includes an ellipse merge control, but the difficult split target is still
two circles. Generalization to noncircular split children and the value of
screening unused extra probes remain open. No neural, noisy, nested-hole,
multi-material or 3-D result is claimed. Independent reviewer: unassigned.
