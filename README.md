# Neural SDF BEM AD

Research code for 2-D dielectric transmission, boundary-element forward
modeling, and inverse geometry reconstruction.

**Start with [`solvers/bem_inverse`](solvers/bem_inverse/README.md) for the
maintained cleaned SC/MA inverse.** It provides the problem/observation API,
continuation policy, solver services, geometry updates, and numerical audits.
Campaign catalogs, truth-based scoring, and dated studies live separately in
`experiments/` and `results/`.

## Run and validate

From the repository root, use the existing EMNerf environment:

```bash
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
CI_PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python

# Check the package boundary and the cleaned numerical/campaign contracts.
"$CI_PY" -m pytest pytest/bem_inverse experiments/cleaned_interface -q

# Inspect the existing campaign without launching fits.
"$CI_PY" -m experiments.cleaned_interface inventory
"$CI_PY" -m experiments.cleaned_interface plan --cases modal__c4__development_c
```

The [campaign guide](experiments/cleaned_interface/README.md) documents input
preparation, source seals, CPU/CUDA selection, and fresh output directories.
The default numerical policy and solver selection are unchanged by package
isolation. Historical import paths continue to work.

## Where to work

| Location | Role |
|---|---|
| [`solvers/bem_inverse/`](solvers/bem_inverse/README.md) | Maintained cleaned inverse implementation and public API |
| [`solvers/gpr_bem_kress/`](solvers/gpr_bem_kress/README.md), [`solvers/ordered_boundary/`](solvers/ordered_boundary/README.md) | Reusable physics and ordered-boundary geometry used by the inverse |
| [`experiments/cleaned_interface/`](experiments/cleaned_interface/README.md) | Campaigns, qualification, historical regressions, and compatibility imports |
| [`experiments/shape_continuation/`](experiments/shape_continuation/README.md), `experiments/modal_atlas/` | Research drivers; extracted shared numerics forward to `bem_inverse` |
| [`pytest/`](pytest/README.md) | Package and solver regression tests |
| [`solvers/`](solvers/README.md) | Other inverse implementations and independent reference solvers |
| [`docs/`](docs/README.md) | Pipeline guides, dated reports, and research history |
| [`results/`](results/README.md) | Recorded evidence, inputs, source snapshots, and failures |

For cleaned-interface code changes, search `solvers/bem_inverse` first. Search
historical evidence explicitly when needed, for example:

```bash
rg 'make_backend' solvers/bem_inverse experiments/cleaned_interface pytest/bem_inverse
rg 'discrepancy' docs/iterations/cleaned_interfaces
```

## Numerical scope and evidence

The cleaned CI-001 campaign recorded **28/36 configurations passing its frozen
contract and 34/36 recovered**. Seven noisy cases fail the residual gate after
discrepancy stopping; matched runtime retention was not established.
[Campaign report](docs/iterations/cleaned_interfaces/iteration_03/01_results.md).
Extraction does not change those results or promote experimental methods.

`nodal_kress` remains the default. `modal_muller` requires explicit registration;
geometry selection is separate. The modal method is boundary-collocation-free,
but the complete inverse still uses quadrature and sampled checks. See the
[campaign guide](experiments/cleaned_interface/README.md) for capabilities and
limits, including opt-in full-matrix observations and geometry variants.

Other research paths remain available: [implicit MLP](docs/pipelines/implicit_mlp.md),
[Cartesian Fourier/topology](docs/pipelines/explicit_cartesian_fourier.md),
[radial Fourier](docs/pipelines/explicit_radial_fourier.md), and
[shape/frequency continuation](docs/pipelines/shape_frequency_continuation.md).
Their claims and defaults are documented in their own guides.

The previous long [repository overview](docs/legacy/repository_overview_2026-10-03.md)
and [research dashboard](docs/legacy/dashboard_2026-10-03.md) are preserved as
historical snapshots. Reference solvers, experimental code, and recorded
results remain in place.
