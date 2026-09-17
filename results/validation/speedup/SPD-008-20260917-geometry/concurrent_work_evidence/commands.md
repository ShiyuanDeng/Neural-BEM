# Commands actually executed

Repository root `/home/drdeng/Neural_SDF_BEM_AD`, branch
`feature/ordered-boundary-nystrom`, environment
`/home/drdeng/miniconda3/envs/EMNerf/bin/python`.

```bash
cd /home/drdeng/Neural_SDF_BEM_AD
git status --short && git branch --show-current && git rev-parse HEAD

export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python

# G0 read-only three-assembler check (no artifacts written)
# -- carried forward as test_algebra.py::test_three_assemblers_agree

# Package tests
$PY -m pytest -q experiments/laurent_compression/

# Imported suite, unchanged
$PY -m pytest -q experiments/modal_muller_research

# Work estimate
$PY -m experiments.laurent_compression.run_screen \
    --output <scratch>/dry --stage pilot --dry-run

# Pilot (circle + ellipse at k_out*a_ref = 2), written to a scratch directory
$PY -m experiments.laurent_compression.run_screen \
    --output <scratch>/pilot --stage pilot

# Campaign -- this bundle
$PY -m experiments.laurent_compression.run_screen \
    --output results/validation/laurent/LAU-001-20260917-modal-derivative-compression \
    --stage campaign
```

The campaign is deterministic: no random seeds enter the screen. Fixtures,
frequencies, directions, masks, floors, gates and budgets are resolved from
`config.json`, which the runner writes before any numerical work.
