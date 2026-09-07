# H1: distance-contact/tangent-jet conversion — bounded negative result

No production default changed. This batch does **not** establish a useful independent role for metric SDF values in the current Fourier-to-Kress pipeline. Exact distances give valid contacts, but a distance-free zero-projection/tangent control achieves comparable accuracy and cost. Nonmetric same-zero fields and the frozen neural field fail the distance-contact checks. Keep this experiment opt-in.

The method is a continuous-field/gradient **distance-contact/tangent-jet adaptation**, not a reproduction of [Reach For the Arcs](https://odedstein.com/projects/reach-for-the-arcs/). The published method reconstructs from discrete signed distances using feasible tangency geometry. This experiment does not implement its sphere-union feasibility arcs, sparse-data reconstruction, or Poisson reconstruction. For an exact SDF, `x - phi(x) grad(phi)/|grad(phi)|` is also one Newton zero-projection step; the null result is informative.

## Frozen experiment

Five cases: exact and deliberately distorted distances for a circle and rotated ellipse, plus the frozen `star/smooth_curve` numeric model from `results/smooth_distance_supervision/task-b-circle-star-refined-20260905`. No neural training was repeated. The ellipse's actual Euclidean distance is evaluated by refined closest-point localization, not by treating the ellipse level set as a distance.

Each field supplies one 65×65 marching-squares frontend and 96 projected, ordered samples. Alternating ±3 mm normal offsets plus deterministic small tangential jitter provide common off-surface query points for the four off-surface arms; the original-zero-set baseline uses the shared seed points directly. Exact/distorted cases have the identical mathematical zero set but run their own field-driven frontend, avoiding an oracle-derived seed for the distorted arm.

Five arms, each at Cartesian bandwidth `K=1,4,8`:

- Existing Method B on the shared original zero-set points.
- Existing zero-set projection of the common off-surface points, then Method B.
- Distance contacts with positive ordered labels and Fourier fitting, tangency weight `eta=0`.
- Distance contacts plus tangent-jet fitting, `eta=0.1`.
- Distance-free projected points plus tangent-jet fitting, `eta=0.1`.

Every new arm has spectral penalty **zero**; no regularization-dependent win is claimed. The first label is fixed at zero and positive cyclic gaps preserve correspondence. The optimizer has 80 iterations. `success` means the configured geometry/contact guards pass, not a guarantee of a globally optimal fit; optimizer termination is separately recorded.

Frozen qualification gates: set error ≤0.2 mm, geometric refinement/localization change ≤2 µm, maximum per-frequency field error ≤1e-3, next-N field self-difference ≤1e-5, and system condition ≤1e8. Independent oracle self-difference must be ≤1e-6. BEM nodes are independently swept at `N=64,128,256`; the final N does not qualify by itself without a finer self-check. Contact-zero residual must be ≤10 µm; fitted-contact/nearest-radius tolerances are 0.2 mm. References and physical responses are audited **after** construction and never select samples, coefficients, labels, or an acceptance tolerance.

The scene has 12 paired point-source/receiver acquisitions, 0.5 and 1.5 GHz, relative permittivities 6 exterior / 3 interior, complex source strength, and no added noise. Full physical arrays, constants and materials are in the numeric bundle and metrics.

## Results

75 arms finished in **86.15 s**: 54 accepted and 21 explicit fallbacks. All five zero-reference physical oracles passed; the frozen neural zero reference required N512, with maximum N256→512 difference 6.65e-11. Its independent canonical-star reference also passed. All source/content hashes were stable during the run; all frozen input and neural-state hashes were unchanged afterward.

Selected K1/N64 results (field errors are the maximum across frequencies):

| Case and arm | Set error | Relative field error | Selected pipeline seconds |
|---|---:|---:|---:|
| Exact circle, shared Method B | 8.1e-16 m | 6.57e-14 | 0.168 |
| Exact circle, distance+tangent | 0.00791 µm | 7.19e-7 | 0.248 |
| Exact circle, projected+tangent | 0.00791 µm | 7.19e-7 | 0.250 |
| Exact ellipse, distance contacts only | 0.482 µm | 3.55e-5 | 0.817 |
| Exact ellipse, distance+tangent | 0.204 µm | 1.73e-5 | 0.817 |
| Exact ellipse, projected+tangent | 0.308 µm | 2.51e-5 | 0.839 |
| Distorted ellipse, projected+tangent | 0.619 µm | 3.81e-5 | 1.036 |

There is **no predeclared >10% matched-error work win**. Against the matching distance-free projected+tangent arm, distance+tangent has work ratios 0.993 on the circle and 0.973 on the ellipse. These are single timed trials, not statistically established speedups. Every circle arm qualifies at K1: there is no circle bandwidth reduction. Both Method-B ellipse controls remain unqualified inside this intentionally bounded K≤8 ladder; no matched-work or precise minimum-bandwidth claim against those unqualified controls is possible. The low-K ellipse gain is therefore not evidence that metric SDF values are essential: the distance-free ordered-label/tangent control has it too.

### Invalid metric radii are detected

The deliberate distortion is `phi=d*(1+0.4*tanh(d/0.02))`. It preserves sign, zero set and unit interface gradient, but not distance radii.

| Field | Local off-surface distance RMS error | Maximum normalized contact-zero residual | Outcome |
|---|---:|---:|---|
| Exact circle | 4.39e-17 m | 6.94e-17 m | Metric contacts accepted |
| Exact ellipse | 1.61e-17 m | 1.24e-16 m | Metric contacts accepted |
| Distorted circle | 0.179 mm | 0.180 mm | All metric arms rejected |
| Distorted ellipse | 0.179 mm | 0.180 mm | All metric arms rejected |
| Frozen neural star | 0.471 mm | 1.161 mm | All metric arms rejected |

The exact ellipse evaluator's localization doubling changed the sampled distances by at most 7.03e-17 m. For the neural row, distance error is measured locally against its **frozen extracted zero set**, not the independent canonical training curve; the two errors are not interchangeable.

At neural K8, raw distance+tangent geometry/field errors were 0.556 mm / 2.72e-2. The raw **distance-free** projected+tangent control was better, 0.294 mm / 4.52e-3, but still failed contact-fidelity/closest-contact guards and the frozen qualification gates. Its returned fallback was the valid shared Method B, with 2.342 mm / 0.113 errors relative to the frozen neural zero reference. This is a **topologically valid**, not accuracy-qualified, fallback. Raw candidates and returned fallbacks are saved separately. The neural K4 contact-only candidate had four sampled self-intersections and was not forwarded; its coefficients and invalidity report were retained. No neural arm or baseline qualified inside this ladder.

## Query/work accounting and limitations

Each standalone arm pays its shared frontend, its provisioned original Method-B fallback, its off-surface proposal when used, and all arm-specific field queries and fitting. Rejected attempts retain those costs. Baseline coefficient provision does not require extra field queries. Case-stage counts show each common computation performed once in the actual experiment; hypothetical standalone-arm counts are not incorrectly summed as actual batch work.

For 96 exact-distance query points, contact construction/validation uses 192 value-point and 192 gradient-point queries. The existing ordinary projection uses 288 and 192; adding the projected-tangent control's explicit contact rechecks adds 96 of each. Including the exact-ellipse frontend/proposal, totals are 4,991 values / 670 gradients for distance+tangent versus 5,183 / 766 for projected+tangent. This is a small **interface-query** saving at matched gates, not a fundamental sparse-distance complexity result: the existing projection/recheck protocol repeats some final checks, and continuous gradients are supplied. It did not produce a >10% selected-work benefit. Against the already available original zero-set Method B, the contact arm adds queries and is slower on the circle.

Counts are external continuous-field interface queries, not universal primitive-operation counts. For example, the distorted field's gradient internally evaluates its underlying distance; measured callback time includes that work. The actual shared batch used 27,768 value-point and 6,163 gradient-point queries, plus 384 independent fixture-distance audit evaluations, and 570 Kress physical-audit solves. Reference-oracle costs, geometric/conditioning audits and BEM-refinement solves are separately recorded.

`whole_work_seconds` in derived decisions means **audit-excluded selected pipeline work**: conversion plus one selected N forward. K/N are chosen posthoc from a frozen ladder. It is not total search/benchmark cost; the 86.15 s batch time includes the actual experiment. Repeated benchmarking, sparse distance input without a known loop, higher bandwidths, different sample placement, and topology discovery were not tested. This frontend already finds the zero set, so the experiment cannot establish an information-recovery breakthrough.

The neural zero reference is the saved grid513/K96 extraction, with inherited extraction uncertainty, not an exact analytic surface. Canonical geometry/field errors are also saved and do not control fitting. A PyTorch warning about read-only NumPy views occurred; inspected model forward operations do not mutate inputs and final source/model hashes verified immutability.

## Artifacts, correction, and replay

- `manifest.json`: pre-measurement gates/configuration, command, git state and relevant source/config/brief SHA256 hashes.
- `metrics.json`, `metrics.csv`: immutable measured work, geometry, normals/curvature, spectra, physical errors, validation and fallback records.
- `arrays.npz`: non-pickled geometry coefficients, source/receiver arrays, observations/reference fields, frozen samples, all predicted fields, and raw rejected candidates.
- `decision_supplement.json`: authoritative derived decisions and distance-free controls, with original metrics hash and postprocessing source/command.

**Decision erratum:** original `metrics.json` derived `lower_usable_bandwidth` flags compared the K of the fastest timed row instead of the minimum qualifying K. This falsely suggested a circle bandwidth advantage because K4 was marginally faster than K1 in one Method-B timing. The supplement corrects that reporting-only error; the measured metrics/arrays were not overwritten, and a regression protects the distinction. No matched-error speed-win conclusion changed.

The measured command was:

```sh
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python run_distance_tangency_comparison.py --output results/distance_tangency/first-batch-20260906
```

Use a fresh output path to rerun; existing artifacts are never overwritten. The supplement used the same command with `--summarize-existing` appended, which performs no new fitting/forward solves. Twelve focused regressions passed after the decision correction, including exact/distorted contacts, tangency-objective finite differences, far stationary-branch rejection, crossed order, frozen numeric-model replay, query totals and strict non-pickled artifacts.

**Design decision from this batch:** retain nearest-contact/zero/sign guards, and do not promote metric-distance conversion. If revisiting H1, require a benefit that survives the distance-free ordered-label/tangent control and matched total conversion/forward work. The current evidence favors investigating the explicit curve/derivative path before spending more effort making this approximate neural field's off-surface values act like reliable metric radii.
