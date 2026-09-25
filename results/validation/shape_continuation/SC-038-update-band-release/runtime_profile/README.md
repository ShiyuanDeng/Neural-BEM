# SC-038 per-update runtime profile

The dominant cost in this replay is **BEM matrix assembly**, especially for
the **finer-grid acceptance evaluation**. Increasing the number of LM
coordinates does not make the small LM solve a material cost here.

## Pipeline

1. Keep the current boundary and its production-grid forward solutions/LU
   factors. At stage startup these fields must first be computed.
2. Prepare the normal-update basis and its geometric projection derivative;
   build the field Jacobian using reciprocal solves with the retained factors.
3. Form the small damped normal equations and solve for the LM displacement.
4. Construct and check a trial boundary; evaluate its fields at all 19
   frequencies on the production grid.
5. If the objective decreases, evaluate on the finer grid and check the
   cross-resolution agreement and acceptance margin. The current boundary's
   finer-grid fields are cached after their first evaluation.
6. Accept the boundary and prepare its Jacobian for the next iteration, or
   try another damping/backtracking candidate. Each additional candidate can
   incur another production field batch; candidates passing that screen also
   incur finer-grid validation.

## Measured example

Replayed the two saved C/M=19 accepted updates at K=192, using all 19
frequencies and 512/1024 production/validation nodes. One worker and one
BLAS/OpenMP thread; ambient machine load was uncontrolled. These are new
profile timings, not the wall times recorded in the original campaign.

The second update reuses the cached finer-grid current-state evaluation:

| Phase | Seconds | Share of update |
|---|---:|---:|
| Finer-grid acceptance fields, 19 frequencies | 59.519 | 80.1% |
| Trial production fields, 19 frequencies | 13.808 | 18.6% |
| Geometry preparation and trial construction | 0.549 | 0.74% |
| Jacobian, including reciprocal solves and contraction | 0.408 | 0.55% |
| 39-by-39 LM linear solve | 0.000041 | <0.001% |
| Other bookkeeping/algebra | 0.008 | 0.01% |
| **Total** | **74.292** | **100%** |

Within the same 74.292 seconds, the kernel timers give another view of the
same work (these percentages must not be added to the phase table):

| Operation | Seconds | Share of update |
|---|---:|---:|
| BEM system assembly, coarse and fine together | 63.616 | 85.6% |
| Dense LU factorization | 8.281 | 11.1% |
| Forward solves, residual checks, and receiver application | 0.821 | 1.10% |
| Reciprocal solve batches and incident trace construction | 0.332 | 0.45% |
| Receiver-operator construction | 0.303 | 0.41% |
| Jacobian contraction with the update directions | 0.071 | 0.096% |

Assembly includes the dense boundary interactions and Kress kernel work.
It is not a measurement isolating individual Hankel/Bessel calls. The
reciprocal solves reuse the forward LU factors; the Jacobian does not perform
one fresh forward factorization per update coordinate.

Startup, through the initial Jacobian, took 17.946 seconds. The first accepted
update took 141.731 seconds, including both current and candidate fine-grid
fields (65.598 and 58.371 seconds). The second took 74.292 seconds because the
current fine-grid fields were already cached. Both steps accepted their first
candidate. Rejected-trial-heavy kite iterations can have a different phase mix;
this profile does not measure the kite's 768/1536 configuration.

## Verification and reproduction

The replay accepted exactly two candidates and reproduced the saved final
coefficients within 1e-12 absolute error. Every original SC-038 source hash
was checked before running, and the source/history hashes were unchanged
afterward. No production code or optimizer decision was changed.

- [Raw measurements and replay verification](result.json)
- [Input/source provenance and thread settings](manifest.json)
- [Instrumented replay script](profile.py)
- [Execution log](run.log)

From the repository root:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python results/validation/shape_continuation/SC-038-update-band-release/runtime_profile/profile.py
```

The script writes only this profile folder and uses process-local timing
wrappers. It overwrites the profile's manifest and result when rerun.
