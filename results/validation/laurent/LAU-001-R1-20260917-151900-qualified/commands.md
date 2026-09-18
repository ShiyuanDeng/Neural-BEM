# Reproduction

From the repository root with the recorded source state:

```bash
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLCONFIGDIR=/tmp/laurent-review-mpl
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m pytest -q experiments/laurent_compression experiments/modal_muller_research -p no:cacheprovider
$PY -m experiments.laurent_compression.run_screen --output <fresh-directory> --stage campaign
$PY -m experiments.laurent_compression.audit_bundle <fresh-directory>
```

The delivered campaign used
`results/validation/laurent/LAU-001-R1-20260917-151900-qualified`.
Do not reuse that output path: existing directories are rejected.

The pilot `LAU-001-R1-20260917-pilot-01` ran before the refined-illumination
extension. The intermediate campaign `LAU-001-R1-20260917-151700-campaign`
contains the same numerical experiment before explicit comparison IDs were
added to the artifact schema. Both are preserved as intermediate evidence;
this qualified bundle is the authoritative rerun and read-back audit.
