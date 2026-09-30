# Modal Chebyshev versus maintained cleaned-interface Kress

2026-09-30. A matched comparison of the independent Chebyshev review prototype and the actual `NodalKress` service at repository HEAD `1723dbee`. **The modal path computes fields and shape Jacobians on the tested fixtures, but is not a complete, registered cleaned-interface backend. Latest CUDA Kress remains faster for these forward workloads and reaches a lower observed error floor.**

## What was compared

- CPU: Intel Core Ultra 9 285K. GPU: NVIDIA RTX 5090 (32 GB). Python 3.9.25, NumPy 2.0.2, SciPy 1.13.1, PyTorch 2.8.0+cu128; double precision.
- Kress: maintained `experiments.cleaned_interface.physics.NodalKress`, `acceleration=spd016`, `geometry=both`, explicit CUDA with four frequency workers. Receipts verify real CUDA / damped CUDA and no fallback. CPU Kress uses one frequency worker.
- Modal: unchanged independent `chebyshev-review-20260930/replay.py:NativePhysics`, one CPU frequency worker; BLAS uses one thread for every method. This compares implementations currently available, not hypothetical equally optimized GPU implementations.
- All fixtures use contrast 13.3 and the same 24 paired point-source observations. The small C has geometry band K=24 and update band M=24; the saved DF endpoint has K=192, M=67. Damping means multiplication of the real wavenumber by `1+0.25i`.
- Modal coefficient window B=128 / 160 for the small / large C; radial degree 100, log degree 260, assumed log lower endpoint beta=0.05. Source/receiver angular order 64 and series length 48. Profile tokens 512/1024 map to Ku=64/96 on the small C and Ku=96/128 on the endpoint; they are not modal node counts.
- Three sequential repetitions, with method order rotated/reversed; CUDA synchronization at timing boundaries. Tables report medians; raw JSON records every observation and min/max ranges. The timings include complete matrix assembly, factorization, incident fields and receiver evaluation.
- **New geometry forward** includes modal geometry preparation and every required frequency-specific source expansion. **Same geometry forward** retains modal geometry/source expansions; both methods rebuild and factor their matrices. **Jacobian** reuses forward factors. Imports, CUDA startup and one-time damped ray-table construction are excluded.
- SC geometry-update preparation is excluded equally from both physics timings: about 0.107 s for K=24/M=24 and 2.276 s for K=192/M=67 in the single-frequency run. Thus these are not full LM iteration or inverse-campaign speed ratios.

## Precision

Errors below are relative Euclidean field errors and relative Frobenius Jacobian errors against independently evaluated **2048-node CPU Kress**. These measure agreement with a refined numerical reference, not certified error against an exact solution. Kress 512 and 1024 already agree at roughly roundoff on these smooth fixtures.

| Fixture | Method | Field error | Jacobian error | Worst Jacobian column |
|---|---|---:|---:|---:|
| C, real 2.5 GHz | Kress CUDA, N=512 | 2.73e-14 | 7.35e-14 | 1.3e-13 |
| C, real 2.5 GHz | Modal CPU, Ku=64 | 1.37e-08 | 9.11e-08 | 8.13e-07 |
| C, real 2.5 GHz | Kress CUDA, N=1024 | 2.6e-14 | 7.23e-14 | 8.83e-14 |
| C, real 2.5 GHz | Modal CPU, Ku=96 | 1.57e-12 | 4.51e-12 | 8.79e-12 |
| C, damped 1 GHz | Kress CUDA, N=512 | 1.41e-15 | 2.07e-15 | 9.95e-14 |
| C, damped 1 GHz | Modal CPU, Ku=64 | 1.19e-13 | 1.35e-13 | 2.09e-12 |
| C, damped 1 GHz | Kress CUDA, N=1024 | 1.05e-15 | 1.76e-15 | 6.14e-14 |
| C, damped 1 GHz | Modal CPU, Ku=96 | 1.2e-13 | 1.36e-13 | 2.08e-12 |
| Large C endpoint, real 2.5 GHz | Kress CUDA, N=512 | 1.88e-14 | 6.17e-14 | 8.67e-13 |
| Large C endpoint, real 2.5 GHz | Modal CPU, Ku=96 | 1.57e-10 | 8.72e-08 | 1.34e-05 |
| Large C endpoint, real 2.5 GHz | Kress CUDA, N=1024 | 1.93e-14 | 5.99e-14 | 4.52e-13 |
| Large C endpoint, real 2.5 GHz | Modal CPU, Ku=128 | 1.76e-12 | 5.16e-12 | 1.35e-10 |

Higher Ku is necessary for high precision. For example, the endpoint improves from roughly 1.6e-10 field / 8.7e-8 Jacobian error at Ku=96 to 1.8e-12 / 5.2e-12 at Ku=128. The fast profile is therefore not the same accuracy as the refined profile. These fixture comparisons meet the current field and Jacobian-column refinement thresholds; that is not a full cleaned-interface audit.

The earlier independent review also found a roughly 7.2e-9 damped field-error floor at 2.5 GHz on the saved C, unchanged by increasing Ku from 64 to 96. The successful 1 GHz damped check here does not establish uniform accuracy for larger complex wavenumbers. See the [mathematical and numerical review](../../../../docs/iterations/cleaned_interfaces/node_free_modal_muller_review.md).

## Single-frequency runtime

All entries are seconds. The CPU control is included to separate the modal algorithm from the advantage of the maintained GPU implementation.

| Fixture | Method | New geometry forward | Same geometry forward | Jacobian | New forward + Jacobian |
|---|---|---:|---:|---:|---:|
| C, real 2.5 GHz | Kress CUDA, N=512 | 0.029740 | 0.029187 | 0.014660 | 0.044490 |
| C, real 2.5 GHz | Kress CPU, N=512 | 0.711712 | 0.710097 | 0.013490 | 0.725080 |
| C, real 2.5 GHz | Modal CPU, Ku=64 | 0.837512 | 0.090258 | 0.001930 | 0.839483 |
| C, real 2.5 GHz | Kress CUDA, N=1024 | 0.103798 | 0.102911 | 0.032734 | 0.138285 |
| C, real 2.5 GHz | Modal CPU, Ku=96 | 0.851491 | 0.098382 | 0.002276 | 0.853747 |
| C, real 2.5 GHz | Kress CPU, N=1024 | 2.986716 | 3.000825 | 0.041046 | 3.029408 |
| C, damped 1 GHz | Kress CUDA, N=512 | 0.040871 | 0.036338 | 0.016011 | 0.056925 |
| C, damped 1 GHz | Kress CPU, N=512 | 0.836114 | 0.839011 | 0.014561 | 0.850675 |
| C, damped 1 GHz | Modal CPU, Ku=64 | 0.811143 | 0.089169 | 0.002076 | 0.813325 |
| C, damped 1 GHz | Kress CUDA, N=1024 | 0.127725 | 0.125391 | 0.034087 | 0.161807 |
| C, damped 1 GHz | Modal CPU, Ku=96 | 0.814827 | 0.095258 | 0.002452 | 0.817308 |
| C, damped 1 GHz | Kress CPU, N=1024 | 3.484487 | 3.490972 | 0.042804 | 3.527291 |
| Large C endpoint, real 2.5 GHz | Kress CUDA, N=512 | 0.034885 | 0.029490 | 0.021094 | 0.056498 |
| Large C endpoint, real 2.5 GHz | Kress CPU, N=512 | 0.710927 | 0.708293 | 0.018893 | 0.730795 |
| Large C endpoint, real 2.5 GHz | Modal CPU, Ku=96 | 7.831396 | 0.225971 | 0.003823 | 7.835271 |
| Large C endpoint, real 2.5 GHz | Kress CUDA, N=1024 | 0.104257 | 0.102168 | 0.045909 | 0.150166 |
| Large C endpoint, real 2.5 GHz | Modal CPU, Ku=128 | 7.833264 | 0.232373 | 0.004306 | 7.837544 |
| Large C endpoint, real 2.5 GHz | Kress CPU, N=1024 | 2.988197 | 2.979855 | 0.054474 | 3.042980 |

## Full 19-frequency forward workload

Saved DF endpoint, all 19 real frequencies from 0.25 to 2.5 GHz. Geometry preparation is paid once per batch and source expansions once per frequency. The precision reference is CPU Kress N=1024 across the entire catalog; the highest-frequency endpoint also has the independent N=2048 check above.

| Method | New geometry forward (s) | Same geometry forward (s) | Jacobian (s) | New forward + Jacobian (s) | Worst frequency field error | Aggregate Jacobian error |
|---|---:|---:|---:|---:|---:|---:|
| Kress CUDA, N=512 | 0.495134 | 0.470200 | 0.207811 | 0.702945 | 1.12e-13 | 7.65e-14 |
| Kress CPU, N=512 | 13.586622 | 13.562964 | 0.379684 | 13.965765 | 6.7e-14 | 6.7e-14 |
| Modal CPU, Ku=96 | 46.824028 | 4.268973 | 0.069002 | 46.894423 | 1.57e-10 | 2.96e-08 |
| Kress CUDA, N=1024 | 1.758232 | 1.742562 | 0.512124 | 2.270355 | 5.22e-14 | 4.34e-14 |
| Modal CPU, Ku=128 | 46.796873 | 4.398688 | 0.078153 | 46.875724 | 1.97e-12 | 2.81e-12 |

Because N=512 already reaches the reference error floor here, it is the useful Kress baseline. Comparing only against N=1024 would charge Kress for refinement that does not improve these fields appreciably. The smaller modal Jacobian cost does not offset its forward setup and assembly cost in these workloads.

## Is it a complete replacement?

| Capability | Maintained cleaned-interface Kress | Independent modal prototype |
|---|---|---|
| Boundary to receiver fields | Implemented for the CI single-curve, equal-density contract | Demonstrated on selected fixtures |
| Shape Jacobian | Implemented through the backend contract | Demonstrated; two complete finite-trial directional checks and three archived LM stages reproduced |
| Real / damped frequencies | Implemented; SPD-016 damped envelope and failure/fallback rules | Selected real and damped cases verified; cancellation and source-series limits remain |
| Resolution and error control | Production/refined node profiles plus runner audit | Fixed experimental Ku/B/degrees; no general adaptive selection or valid geometry-bound certificate |
| Localization and observable frontier | Backend methods implemented | Missing from this service |
| Input validation, diagnostics and failure handling | Backend validation, residuals, device/failure receipts | Partial; no equivalent full service contract |
| Registration and full CI runs | Registered; full 36-case inverse campaign executed | Not registered; three stage replays, no full 36-case native campaign |

The existing Kress campaign has its own inverse-policy retention failures; its completion does not mean all inverse cases passed. Conversely, localization/frontier are integration requirements of the cleaned interface, not missing terms in the modal forward equations.

The modal source/receiver expansion additionally requires all points outside its coefficient bounding circle. Its fixed beta=0.05 is an assumption for these fixtures. The proposed finite-window Parseval test cannot certify that bound or curve simplicity. Increasing Ku alone cannot cure coefficient-window, radial/log degree or source-series error.

**Use maintained nodal Kress as the current production backend. The Chebyshev modal implementation is a promising, independently checked research forward/Jacobian solver; accuracy on these fixtures is comparable at roughly 11–12 digits when refined, but neither completeness nor a speed advantage over latest CUDA Kress has been established.**

## Reproduce and inspect

Run from the repository root with CUDA access; run the parts sequentially:

```bash
env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/cleaned_interfaces/modal-versus-cleaned-kress-20260930/benchmark.py single
env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/cleaned_interfaces/modal-versus-cleaned-kress-20260930/benchmark.py catalog
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/cleaned_interfaces/modal-versus-cleaned-kress-20260930/summarize.py
```

[single.json](single.json) and [catalog.json](catalog.json) contain per-repetition timings, accuracy, execution receipts, reference specifications, environment and SHA-256 source hashes. [summary.json](summary.json) records ratios to CUDA Kress N=512. The summarizer verifies completion, three repetitions per group and source hashes. Production solver and optimizer sources are unchanged.
