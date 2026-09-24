# SC-030: SPD-008 and the clean hybrid

**COMPLETE:** 36 fresh-process workers, six cases × three arms × two sequential
repetitions. Every result, including six numerical/derivative hard stops, is
retained. The cache reduces aggregate hybrid inversion time by
**12.62%** (11.28–14.60% by case),
with identical scientific trajectories and work in every cached/off pair.

The fixed hybrid ladder has lower final boundary RMS error on all six common
starts. SPD completes C, kite and hook with large errors, and stops on circle,
star and peanut. The hybrid still leaves approximately 3-mm RMS error on
C, kite and peanut. Schedule completion is not a recovery certificate; shorter
time to a poor endpoint or early stop is not a recovery speed advantage.

## Results and interpretation

- [Research closeout and decision](../../../../docs/iterations/shape_frequency_continuation/iteration_13/01_results.md)
- [Complete comparison table](comparison_table.md): all 18 case/arm pairs, inverse-time medians and ranges, errors and work
- [Per-worker measurements](case_results.csv), [per-stage outcomes](stage_results.csv), [work categories](work_categories.csv), [cache counters](cache_results.csv)
- [Machine-readable summary](summary.json) and [final verification](verification.json)
- [Closeout validation](closeout_validation.json): report, document links and reconciled totals
- [Boundary reconstructions](boundaries.png) ([vector PDF](boundaries.pdf)) and [cost/error comparison](cost_quality.png) ([vector PDF](cost_quality.pdf))

This is SPD-008 execution of native fixed-topology continuation from the common
bad circle, not the complete SPD topology/readiness pipeline. All arms share
data, the physical starting boundary, frequency schedule, 512/1024 nodes,
iteration/work/time limits and post-run scoring. Their native geometry,
feasibility guards and update construction differ as declared in the contract.
The hybrid transfers exact geometry reuse and retains its existing kernels;
SPD uses its compiled/real-Bessel/certified configuration.

## Verification and provenance

- [Frozen approved contract](approved_plan.md)
- [Source/input/environment manifest](manifest.json), with the complete measured source archive in `sources/`
- [Pre-dispatch tests](pre_dispatch_tests.log): 76 passed
- [Numerical/cache qualification](qualification/result.json): PASS, 52 units, 58.34 s
- [Actual saved-start and initial-loss audit](actual_start_audit.json)
- [Supplemental inherited-input audit](inherited_configuration_audit.json), recorded during the campaign against commit `bc443cc`
- [Implementation review](implementation_review.md): owner review; independent reviewer unassigned
- [Campaign and exact worker commands](campaign.json), [historical first-pass checkpoint](first_pass.md)
- [Final artifact checksums](artifact_manifest.sha256)

Final verification checks all 36 configurations and worker exits; immutable
sources/inputs/plan; all 240 original SPD-008 source files; cache memory bounds;
accepted-step numerical checks; 12 exact cached/off pairs; 18 exact repetition
pairs; and 24 hybrid endpoint/work replays of SC-029. All endpoint scoring
completed. The SPD circle endpoint fails the post-run all-training-frequency
resolution audit in both repetitions; the other endpoints pass. This does not
contradict the checks on the active frequency prefix at each accepted step.

The campaign used 12,534 inverse units and 972 post-run field
solves in 3.69 hours. Worker records separate setup, inverse, evaluation,
and outer process timing. The Intel Core Ultra 9 285K host was shared and
unpinned; all workers ran sequentially with one BLAS thread and rotated/reversed
arm order. Two repetitions provide ranges, not confidence intervals.

## Rebuild the report without solving

From the repository root:

```bash
OPENBLAS_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python results/validation/shape_continuation/SC-030-spd008-comparison/summarize.py
```

This reads saved artifacts, checks the frozen contract and rebuilds tables,
verification and figures. It does not run either inverse. To check the complete
closed bundle, run `sha256sum --quiet -c artifact_manifest.sha256` from this
directory before regenerating figures (PDF creation metadata may change on
regeneration).

The numerical driver uses `prepare`, `qualify`, then `campaign` with the same
fresh output directory, the EMNerf interpreter, `PYTHONPATH=solvers:.` and
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`. The preserved
[campaign commands](campaign.json) specify the exact measured workers. Existing
bundles must not be overwritten. No successor, relaxed guard or retry was run.
