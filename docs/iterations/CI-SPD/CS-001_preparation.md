# CS-001 preparation — fitting awaiting specific ID approval

Historical pre-run record. The later user instruction removed separate ID
confirmation and authorized execution; see [completed CS-001 results](CS-001_results.md).

2026-10-05. **Prepared, no inverse fits run.** The general user request
authorizes implementation and preparation. AGENTS.md additionally requires
explicit approval of the experiment ID before fitting; CS-001 was presented
in an asynchronous approval question and has not yet received a response.

The [preregistered plan](CS-001_plan.md) fixes eight TG-002 cases, paired
fresh-interpreter control/revised runs, the four-phase schedule, increasing
M/K levels, and unchanged recovery/numerical gates. Implementation is opt-in
as `bem_inverse.continuation_policy.ShapeFrequencyPolicy`. Default
`CumulativePolicy` behavior is preserved. Stage-local exact similarity
initialization uses three metre coordinates; all independent start/endpoint
audits retain the selected ordinary spectral update. The initial start audit
retains the ordinary warm-up's M=1; a numerical stop in the M=0 restricted
fit also receives an M=1 spectral endpoint audit.

## Bounded validation

- 475 tests passed across `pytest/bem_inverse`, `experiments/cleaned_interface`,
  `experiments/shape_continuation`, and the frozen TG-002 benchmark tests;
  15 existing library/runtime warnings. Final log: `validation.log`.
- Focused tests exercise exact prefix preservation, all-frequency shape stages,
  increasing M/K validation, accepted-state inheritance, stage-local update
  dispatch, and spectral audits on both completed and failed initialization.
- CPU and CUDA central differences checked all three similarity derivative
  columns at the prescribed circle, lowest damped frequency, contrasts
  0.5/4/13.3 and TG-002's 0.05 m length unit. All six checks passed; maximum
  relative column error **1.5624568485426515e-9**, against the 1e-5 gate.
- Sealed TG-002 inputs, final source hashes, source archive, qualification,
  and concrete control/revised executable plans verify.

The first broader validation found a new operation-field name colliding
with an existing legacy experimental subclass. The field was renamed to
`fit_geometry_update`, preserving compatibility. Original failed-test log
`validation_v1.log` and source/qualification snapshot `preparation_v1/`
remain in the evidence directory; final preparation is in `preparation/`.
This was a software qualification failure, not a measured inverse result.

Evidence: `results/validation/cleaned_interfaces/CS-001/`.
After specific approval, execute:

```bash
PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.benchmark.cs001 \
  run --approved-id CS-001
```

The driver additionally requires a truthful `authorization.json` recording
CS-001 approval. That record is currently unauthorized. No case, recovery,
speed, or end-to-end strategy validation is claimed before the paired runs.
