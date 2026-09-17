# SPD-008 recorded execution

Working directory: `/home/drdeng/Neural_SDF_BEM_AD`, existing branch
`feature/ordered-boundary-nystrom`. Numerical interpreter:
`/home/drdeng/miniconda3/envs/EMNerf/bin/python`.

Each phase used `PYTHONPATH=solvers` and `OMP_NUM_THREADS=1`,
`OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`.
The final regression subprocess argv is recorded exactly in [tests.json](tests.json).
All sixteen full-worker subprocess argv lists and environments are recorded in
[campaign/timings.json](campaign/timings.json).

After the runner repair, the numerical qualification/campaign/report chain used
these module commands, in order, advancing only on a zero return code:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python -u -m experiments.spd008_geometry.run qualify --bundle results/validation/speedup/SPD-008-20260917-geometry
/home/drdeng/miniconda3/envs/EMNerf/bin/python -u -m experiments.spd008_geometry.run campaign --bundle results/validation/speedup/SPD-008-20260917-geometry
/home/drdeng/miniconda3/envs/EMNerf/bin/python -u -m experiments.spd008_geometry.run report --bundle results/validation/speedup/SPD-008-20260917-geometry
```

Output was redirected to `qualification.log`, `campaign.log`, and `report.log`.
The preserved earlier attempt used the corresponding frozen driver under
`*_attempt_01/sources/`; its pre-dispatch failure and prior diagnostic costs are
retained and counted. Existing numerical output directories cannot be reused.

The file-only final audit, with zero new physical solves, is reproducible using:

```bash
python results/validation/speedup/SPD-008-20260917-geometry/audit.py
git diff --check
```

The final audit stdout is archived in `audit.log`. The separate file-only
`monitor.py` sampled saved progress every 55 seconds and exited at completion.
See [timing_context.json](timing_context.json) for the independently observed
LAU-001 workload and the resulting shared-host timing qualification.
