# D: one unknown interior permittivity

The small material extension works from the lower-permittivity starts, including joint radial-shape recovery with 1% complex noise and unseen-angle holdout. It is **not globally reliable from every start**: three predeclared high-permittivity starts failed recovery. Optimizer success, checked stationarity and physical recovery are reported separately. No production inverse/default was changed.

Eight arms completed in 73.55 s. Five passed the frozen physical-recovery gates. All independent material-sensitivity checks passed; observations and relevant source hashes stayed unchanged throughout the run. There were no invalid candidate probes or failed forward solves.

## Frozen setup

The target is an independently evaluated Mie circle: center `(0.5,0.5)` m, radius `0.05` m, interior `epsr=3`, known exterior `epsr=6`, current lossless nonmagnetic TMz physics. This is a fixed-circle / **radial K2** joint control, not a K5-star, multi-material, topology or 3-D inverse.

Twelve source/receiver pairs at 0.5 and 1.5 GHz train the inverse. Twelve disjoint half-step angular acquisitions are held out. Source complex amplitudes and acquisition coordinates are known and frozen. Noisy arms share the same seeded circular complex Gaussian noise, with standard deviation 1% of each frequency's clean pair RMS (seed 4206). A separate held-out noisy dataset uses seed 4216; importantly, noisy-training results are also evaluated against the untouched **clean holdout**.

The six dimensionless optimization coordinates map to `[mean radius, center x, center y, radial cos2, radial sin2, interior epsr]` with scales `[0.01,0.01,0.01,0.005,0.005,2]`. Physical bounds are radius `[0.035,0.075]` m, centers `[0.47,0.53]` m, each mode coefficient `[-0.004,0.004]` m, and interior `epsr=[1.2,12]`. The entire box certifies a positive radial function and therefore a simple regular one-component graph. The continuous radial curve is rebuilt coherently, with no per-candidate refit or rephasing; its Cartesian bandwidth is 3.

Fixed-geometry arms vary only epsr. Joint arms vary all six coordinates, from:

- Start 1: radius 0.057 m, center `(0.494,0.505)` m, modes `(0.002,-0.001)` m, epsr 2.
- Start 2: radius 0.043 m, center `(0.505,0.495)` m, modes `(-0.002,0.001)` m, epsr 9.

Bounded TRF least squares uses the independently tested complete analytic Kress directional derivative, fixed N64, at most 40 residual evaluations, and no regularization. Real and imaginary paired residuals are both retained. Per-frequency weights are fixed from the immutable observed cohort, never recomputed from a candidate. Every changed candidate rebuilds its MaterialSpec, production Material, interior wavenumber and complete Kress operators, including material-dependent analytic self diagonals. The one-entry cache includes full shape/material parameters, acquisition/frequency/calibration/constants, solver/chart configuration, observations and frozen normalization.

## Recovery, including failed starts

Errors use the refined N256 forward; set errors use independently refined closest-curve localization. Stationarity requires scaled projected-gradient infinity norm ≤1e-7. Physical recovery separately requires material error ≤0.1, set error ≤0.2 mm, geometry audit change ≤2 µm, a forward N128→256 difference ≤1e-5, and clean holdout field error ≤1e-4 for clean training or ≤0.02 for noisy training.

| Arm | Recovered epsr | Set error | Clean holdout field error | Checked stationary | Physical recovery |
|---|---:|---:|---:|---|---|
| Fixed clean, start 2 | 3.0000000000 | 0 | 1.17e-14 | Yes | Pass |
| Fixed clean, start 5 | 3.0000000000 | 0 | 1.59e-11 | Yes | Pass |
| Fixed clean, start 9 | 10.143255 | 0 | 1.247 | **No** | **Fail** |
| Fixed noisy, start 5 | 3.000807 | 0 | 6.11e-4 | Yes | Pass |
| Joint clean, start 1 | 2.9999999999 | 1.74e-12 m | 3.55e-11 | Yes | Pass |
| Joint noisy, start 1 | 3.000048 | 64.9 µm | 3.49e-3 | Yes | Pass |
| Joint clean, start 2 | 4.118789 | 41.4 mm | 0.850 | **No** | **Fail** |
| Joint noisy, start 2 | 4.124446 | 41.5 mm | 0.848 | **No** | **Fail** |

The fixed clean start-9 arm triggered TRF's **ftol success flag**, but its projected gradient was 1.01e-5 and it badly missed the data. It is not reported as converged. Both high-epsr joint starts reached the 40-evaluation cap, with radius at the upper bound and cos2 at the lower bound; projected-gradient norms were 3.00e-5 and 6.58e-5. These are failed bounded runs, not certified local minima or evidence that more iterations/restarts could never recover. No retrospective restarts, bound widening or retuning were performed.

The successful noisy joint run had radius error 7.32 µm, center error 11.5 µm and a spurious mode-2 amplitude 46.8 µm. Training error to the noisy observations was 0.947%, while its error to the clean unseen-angle holdout was 0.349%. The near-exact recovered material in this one noise realization is not a general uncertainty guarantee.

## Material/shape ambiguity and derivatives

The **scaled, weighted, real-stacked** six-column Jacobian at the successful clean joint solution had singular values approximately `[1.873,1.152,1.135,0.3695,0.3692,0.2123]`, condition number 8.82, and radius/material column correlation **−0.9599**. The noisy successful solution was similar (condition 8.80; correlation −0.9597). Full matrices, singular values, correlations and declared scales are saved.

Thus the declared local problem has resolved directions, but radius and material sensitivities are strongly correlated. The failed-start endpoints also had finite local Jacobian condition numbers around 8.1: local rank/conditioning is not proof of global identifiability or a guarantee of a useful basin. These diagnostics must not be confused with the BEM system condition numbers.

At fixed-circle epsr values 2, 3 and 9, candidate predictions agreed with independent fixed-mode Mie fields to at worst **1.08e-13** maximum per-frequency relative error. Analytic scaled material JVPs agreed with independently differenced Mie data to at worst **1.87e-8**; Mie FD step refinement changed the derivative by at most **5.62e-8**. Production central-FD errors showed the expected decreasing region over scaled steps `1e-2,1e-3,1e-4,1e-5`; their finest-step discrepancies were 1.12e-9, 8.55e-10 and 2.96e-9. Fixed pre-measurement sensitivity gates are explicit in the manifest and separate from physical-recovery flags.

Independent observations use fixed Mie mode ranges 32 and 64 with a 1e-10 self-agreement gate. Final training/holdout fields are audited at N64/N128/N256 on the same frozen continuous recovered curve. No candidate-generated observations or candidate-dependent residual normalization are used.

## Work, artifacts and replay

Actual counted work: 239 candidate builds, 478 production forward solves, 1,320 analytic directional evaluations/tangent solves, and 38 Mie frequency evaluations. Field solves took 13.51 s, Jacobian work 57.71 s and system-conditioning audits 1.69 s. Oracle/data preparation was 0.0097 s and the independent material-sensitivity audit 0.956 s. These categories overlap intentionally where indicated: sensitivity-audit work is also present in the actual aggregate solve/JVP counts. Per-arm optimization, qualification and total times are separately recorded; no claim of an inverse speedup over another optimizer is made.

- `manifest.json`: pre-measurement configuration/gates, exact physical/acquisition/noise/scaling state, command, git identity and relevant source SHA256 hashes (including `periodic_kress`).
- `metrics.json`, `metrics.csv`: all eight outcomes, separate optimizer/stationarity/recovery flags, failed-start histories, work, sensitivity/refinement and conditioning diagnostics.
- `arrays.npz`: strict non-pickled immutable clean/noisy observations, acquisition arrays, recovered radial states, weighted real Jacobians, analytic/Mie sensitivity vectors, and refined train/holdout predictions.

The data bundle is checkpointed **before** sensitivity or optimization work. Programming/configuration/immutability errors abort; numerical factorization/floating-point failures become explicit failed-arm records, never fabricated zero residuals. This run encountered neither. Existing output directories are never overwritten.

```sh
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python run_material_inverse_comparison.py --output results/material_inverse/bounded-20260906
```

Use a fresh output directory for replay. Eleven focused regressions passed before the batch, covering material/operator/cache rebuilds, exact radial jets, full weighted Jacobian finite differences, normalization/observation immutability, invalid/failed probe accounting, bounded termination distinctions, Mie sensitivity call accounting, disjoint noisy/clean cohorts and strict artifacts.

**Verdict:** one unknown positive lossless interior epsr is a useful, concrete next capability; the same verified explicit-curve derivative supports joint shape/material updates. Keep basin sensitivity visible. More material parameters, conductivity, unknown source calibration, noncircular targets, K5 shapes, extra components and 3-D remain untested here and must not be inferred from these circle controls.
