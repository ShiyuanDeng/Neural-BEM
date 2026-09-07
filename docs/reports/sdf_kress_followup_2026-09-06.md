> Historical record, classified 2026-09-07. Behavior and planned work below
> refer to the original date. Current pipeline names are
> [Implicit MLP + Method B](../pipelines/implicit_mlp.md) and
> [Explicit Radial Fourier](../pipelines/explicit_radial_fourier.md). See the
> [architecture](../current_architecture.md) and [results catalogue](../../results/README.md).

# SDF/Kress follow-up: derivatives, distance information, and inverse controls

Date: 2026-09-06. This follows the completed
[A/B/C batch](sdf_kress_first_batch_2026-09-05.md) and the user's subsequent
instruction to continue until a design decision is needed. The original
[guide](../legacy/codex_sdf_kress_priorities_2026-09-05.md) and historical evidence are
unchanged. All additions are explicit-import experiments; production solver,
optimizer, extraction, representation and topology defaults are preserved.

## Verdict and the decision now needed

The explicit curve remains the useful authoritative reconstruction state.
There is still **no demonstrated essential role for metric SDF values in the
current inverse**. A already measured unchanged canonical reconstruction
without per-step SDF work; H1 finds no clear distance-specific conversion win;
F's frozen neural metric loses to the tested explicit controls. These are
bounded results, not a theorem that implicit representations or learned
priors can never help. Initialization and independently audited export remain
legitimate optional representation roles.

E is a positive numerical result: a verified derivative of the actual Kress
objective. D turns that foundation into useful local shape/material recovery,
but also exposes starting-basin failures and strong local radius/material
coupling. Those are the next practical issues; retaining an SDF would not
resolve them by itself.

| Proposed direction | Needs a true SDF? | Present recommendation |
|---|---|---|
| One interior permittivity | No | Bounded fixed/joint recovery now implemented; improve robustness to starts next |
| Distinct materials on separate objects | No | First use explicit fixed-count loops and independently validate unequal-material cylinders |
| 3-D | No | Choose the physical problem first; full Maxwell is not a coordinate extension of scalar TMz |
| Neural update/prior | No distance requirement | The tested frozen metric has no advantage; learned/adaptive features would be a different hypothesis |
| H1 metric tangency | Yes, for its distance radii | No distinct measured benefit here; do not promote it |
| Close quadrature / component proposals | No / optional implicit representation | Separate projects; retain clearance gates and explicit-loop controls |

My recommended next branch is **robust explicit shape/material inversion**:
predeclare low-frequency continuation and/or bounded multistart selection
using training data, retain untouched acquisitions, then extend fixed-count
separated objects to unequal materials. The alternative is a research branch
that gives a learned prior or neural representation genuine ownership of
proposed geometry and tests its transfer against explicit controls. That
changes the scientific objective and representation contract; it should be a
user decision, not another automatic extension merely to preserve an SDF.
Topology changes, close-target quadrature, learned-prior datasets, nested
region semantics and 3-D have not been implemented in this follow-up.

## E — differentiate the actual solved Kress problem

The new [`gpr_bem_kress.shape_derivative`](../../solvers/gpr_bem_kress/shape_derivative.py)
implements analytic first-order jets of the existing single-interface
discretization. It includes the actual truncated near power-log series,
direct Hankel/Bessel expressions, analytic diagonals, native-period speed
normalization, outward normals, source arc weights, incident Dirichlet and
Neumann traces, receiver matrix and direct incident term. It does not use
finite differences to implement the derivative or change the forward code.

`KressDirection` declares a coherent real path through native-grid position
and first-derivative jets, optionally second/third jets, interior/exterior
positive lossless relative permittivity, and complex source strengths. The
current cancelled operator does not use second/third direction jets; those
arrays are still checked when supplied. Node correspondence, period,
frequency, acquisition, topology and near/direct branch are fixed for one
linearization. Branch margins and primal reassembly differences are reported.
Unsupported moving acquisition, conductivity, magnetic material, component
births, multi-interface derivatives, refitting and remeshing are not silently
approximated.

For the stored production system `AU=B` and receiver map `C`,
`linearize_kress_forward` computes `dU=A^-1(dB-dA U)` and
`dz=dC U+C dU+dD`. `build_paired_objective_adjoint` supports scattered or total
fields, arbitrary paired selections including duplicates, and a fixed real
matrix acting on `[Re(z-y).ravel(); Im(z-y).ravel()]`. It solves conjugate
adjoints once per frequency, then contracts each declared direction without a
tangent solve. Both complex residual components and source phases are retained.

The result is a **discrete directional covector**, not a uniquely determined
normal-gradient density. A coefficient basis and mass/Riesz map must be
declared before converting it into normal motion. Multiplying the returned
coefficient derivative by arc weights again is wrong. No regularizer is
implicitly included.

### Measured validation

The fresh [final sweep](../../results/validation/kress_shape_derivative/refined-audits-20260906/summary.md)
passed all **96/96** case/node/direction records and its separate
independent-reference/physical-refinement gate in **77.77 s**. It covers a
circle, rotated ellipse, five-lobe star and matched-material circle at
N32/64/128, two frequencies, multiple complex sources, repeated paired
measurements, eight geometry/material directions and five central-FD steps.
Every finite difference calls the unchanged production forward on the
perturbed continuous curve. Objective checks cover both scattered and total
observables with fixed weighting and nonzero immutable residuals.

The largest best-step fixed-node FD mixed-error ratio was 0.0265, against a
pass threshold of 1; this ratio is error divided by the declared
absolute-plus-relative tolerance, **not a 2.65% field error**. Maximum
adjoint/JVP objective discrepancy was `1.60e-14`. Finest-grid nonzero-contrast
independent derivative relative error was at most `1.65e-8` for the checked
directions. The independent oracles are fixed-mode cylinder Mie differences,
separately refined Nyström differences, and the exact same-set parameter-shift
identity. The star's computed phase derivative decays to `3.57e-14` relative
to the incident-inclusive field scale (the larger scattered/incident norm);
it was not forced to vanish at finite N.

A separate analytic matched-material cylinder sensitivity
[`cylinder_sensitivity_reference.py`](../../solvers/sdf_inverse/cylinder_sensitivity_reference.py)
uses Bessel recurrences and a Wronskian identity, not the Kress derivative.
At equal materials, the physical scattered field vanishes but a
material-contrast direction does not; finite-N representation leakage is
still measured. Interior/exterior material derivatives agree with that
oracle at `1.88e-15` / `6.81e-15` relative. Common material directions cancel.

The first [development sweep](../../results/legacy/development/kress_shape_derivative/bounded-20260906/summary.md)
is preserved: 15 pure-shape matched-material checks failed because the test
scaled its absolute tolerance by the vanishing scattered field. The corrected
audit uses the incident-field scale for receiver observables, with a focused
regression. A noisy phase-reference FD was also replaced by the exact
same-set identity, while retaining the actual finite-N Kress derivative.
No derivative implementation was modified to make these audit corrections
pass. The final artifact records the measured source hashes; a subsequent
CLI-only change makes multi-resolution physical-gate failure return a nonzero
exit code as well as recording failure. Future manifests additionally hash
the periodic-weight and SDF-to-boundary helper packages. Neither follow-up
changes measured numerical behavior; stored measurements were not rewritten.

This is a verified foundation for the bounded tests, not yet a scalable
arbitrary-nodal reverse pass: each coefficient contraction still assembles its
directional operators, and dense solves remain. Existing production inverse
drivers retain their numerical Jacobians.

## H1 — do metric distance values earn a distinct role?

The new [`distance_tangency`](../../solvers/sdf_to_ordered_boundary/distance_tangency.py)
fits ordered Fourier curves to queried contacts and optional tangent jets.
It assumes continuous value/gradient access and an already discovered loop;
it is not a sparse-distance reconstruction algorithm or a reproduction of
Reach For the Arcs. All off-surface arms share frozen queries and a declared
positive-label ordering; the original Method-B baseline uses the shared
frontend zero-set points. The original Method B, off-surface
zero-projection plus Method B, and distance-free projected/tangent fits are
controls. Spectral penalty is zero in every new arm.

Distance contacts are checked against the queried zero set, sign, normal
orientation, genuine refined nearest contacts, fidelity, topology and speed.
Rejected attempts keep their raw candidate, reason, work counts and valid
baseline fallback. Fallback validity does not mean accuracy qualification.
Neither target geometry nor physical observations determine fitter acceptance.

The [full evidence and accounting](../../results/validation/distance_tangency/first-batch-20260906/README.md)
cover 75 arms in **86.15 s**, with 54 accepted and 21 explicit fallbacks.
Cases are exact circle/ellipse distances, same-zero deliberately nonmetric
distortions, and the frozen approximate neural star from B. K1/4/8 and
N64/128/256 are independent sweeps. Geometry, fields, conditioning and
refinement must all meet fixed gates.

There is **no >10% matched-error selected-work win attributable to distance
values**. On the exact ellipse, distance+tangent achieves 0.204 micrometres
set error and `1.73e-5` field error at K1/N64; the distance-free
projected+tangent control also qualifies at 0.308 micrometres / `2.51e-5`.
Their measured selected-work difference is only 2.7% in one timing trial.
Both benefit from parameter labels/tangents, not exclusively distance values.
The already available circle Method B is cheaper and roundoff-accurate.

Exact distance contacts save some continuous-interface queries relative to
the existing iterative projection/recheck protocol, but this small saving
did not produce the predeclared work advantage. It is not a lower bound on
distance-free conversion cost. “Selected work” means conversion plus one
chosen-N forward; the artifact separately counts the whole experiment and
its qualification/search costs.

The distortion preserves the zero set and unit gradient on the interface,
yet its off-surface contact error is approximately 0.180 mm. Every metric
arm is correctly rejected. The frozen neural contact residual reaches
1.161 mm; no neural arm qualifies in the bounded ladder. Eikonal behavior
on the interface alone does not validate off-surface metric radii.

The immutable-metrics
[decision supplement](../../results/validation/distance_tangency/first-batch-20260906/decision_supplement.json)
corrects a reporting bug: minimum usable bandwidth must compare minimum
qualifying K, not the K of a marginally faster timed row. There is no circle
bandwidth win. Original measured metrics remain unchanged and a regression
protects that distinction. H1 stays experimental; its present evidence does
not justify making accurate off-surface distances mandatory in reconstruction.

## F — a frozen neural update metric, not a trained SDF inverse

[`neural_metric.py`](../../solvers/sdf_inverse/neural_metric.py) uses E's discrete
coefficient covector on the authoritative radial chart. With `H` the map from
coefficients to normal motion, `W=diag(ds)`, `M=H^T W H`, and
`B=-partial_theta(phi)/|grad(phi)|`, the projected neural map is
`T=M^-1 H^T W B`. Its covariance acts on the coefficient covector; there is
no second arc-weight multiplication and no invented normal density.

The experiment freezes the metric at the initial exact circle. The network's
zero output head makes hidden-weight derivatives zero there: only **65 of
5,441** parameter columns are active. This is a frozen random-feature
tangent metric, not trained deep-network adaptation. Once the curve moves,
the unchanged field is not queried as if its zero set were the new curve.
No weights are trained, no representation is extracted, and no off-surface
distances are used during reconstruction.

Controls are mass-whitened identity and one explicit Sobolev smoother of
angular length 0.35; three neural seeds use the same initialization and
observations. Active metrics are projected using their own mass submatrix,
trace-normalized and mixed with the same `1e-3` isotropic floor. All arms use
E, zero regularization, actual current-geometry normal step limits of 2 mm,
true-objective Armijo acceptance and the same metric-independent stationarity
norm. This is not a comparison against the existing damped Gauss–Newton
inverse or a tuned set of explicit optimizers.

The predeclared budget is five accepted K3/N64 updates at 0.5 GHz, then ten
K5/N128 updates at 0.5+1.5 GHz, capped at 160 total frequency-level forward
calls per arm. Each frequency stage has its own fixed objective; objective
jumps across stages are not interpreted as descent. Model/metric setup,
gradient/operator work, forward calls and final qualification are counted
separately. In accepted history rows, `gradient_norm` describes the pre-step
geometry, while coefficients/loss describe the accepted post-step state; it
must not be read as a final-state stationarity diagnostic. Independent Mie
circle and refined Nyström star data are frozen
before any optimization; shifted acquisitions at 2 GHz are inspected only
after every arm is frozen. Final field resolution is checked independently
at N128/256/512, with a `1e-6` finest-pair self-refinement gate.

Even a win over the chosen moderate smoother would not establish a
neural-specific advantage: neural eigenvalue anisotropy can be much stronger.
A claim about distinctive neural coupling would need a spectral-matched
explicit control. The finite K5 chart and frozen initial features also cannot
test learned priors, non-star expressivity, topology, or end-to-end neural
zero-set optimization.

### Measured comparison

The [ten-arm run](../../results/inverse/radial_fourier/neural_metric/comparison-20260906/summary.md)
finished in **360.63 s**, with every final training/held-out numerical
resolution check passing. The finest training/held-out field self-differences
are at most `3.1e-14` / `4.1e-13`; the remaining errors are not unresolved BEM
quadrature. Independent circle Mie64/72 data agree, and the star Nyström
training/held-out reference refinements are `2.77e-11` / `1.19e-10`.

There is **no neural-metric win** in this bounded comparison. Circle identity
and Sobolev reach their declared training-loss threshold at relative field
errors 0.00391 / 0.00685, with correspondence RMS geometry errors 0.064 /
0.114 mm. Their held-out errors are still 0.0401 / 0.0753: the training stop
is not a claim of accurate generalization. All three neural seeds exhaust
15 accepted steps, at training errors 0.0675–0.1297, held-out errors
0.5765–1.528 and geometry RMS 1.043–2.292 mm.

Every star arm exhausts its update budget, so none is a fully converged star
reconstruction. Identity/Sobolev reach training errors 0.278 / 0.308 and
held-out errors 0.604 / 0.539, versus neural training 0.461–0.558 and held-out
0.790–0.887. All star arms use exactly 28 frequency-level forward calls;
circle counts differ (40 identity, 30 Sobolev, 28 per neural seed), despite
shared caps. Setup and gradient costs are included in reconstruction times.
This is not a matched-final-accuracy speed comparison.

The initial neural metric condition numbers are 439–943, versus 4.06 for
the moderate smoother and 1 for identity. Projection of the neural normal
map into the eleven-control chart leaves 15.6–16.6% weighted residual.
These are measured limitations of this initial random-feature coupling, not
an experiment in learned/adaptive features. No settings, seeds, budgets or
held-out choices were retuned after the results. Keep the module opt-in;
there is no evidence here to replace the explicit controls with it.

## D — one unknown interior permittivity

[`material_inverse.py`](../../solvers/sdf_inverse/material_inverse.py) adds an
explicit, bounded experiment with one positive lossless interior `epsr` and
known exterior/source calibration. Every changed candidate rebuilds its
material and the full Kress prediction, including interior wavenumber and
analytic diagonals. The one-entry cache includes the complete shape/material,
scene, numerical configuration, observation and frozen normalization identity.
Mutation and invalid parameter-index aliases are rejected.

The joint chart has five geometric controls (mean radius, two center
coordinates, radial cosine/sine mode two) and one material control. Physical
scales are `[.01,.01,.01,.005,.005,2]`; fixed bounds keep all radial curves
positive and simple, with `epsr` in `[1.2,12]`. This K2 circle-target control
does not claim K5-star, multiple-material or general-shape recovery. The
scaled real residual Jacobian uses E's analytic shape/material JVPs and
bounded trust-region least squares. Immutable Mie observations and their
normalization never follow the candidate.

Eight predeclared arms cover fixed-circle clean material starts 2/5/9, one
noisy fixed-circle start, and two joint shape/material starts with clean and
seeded 1% complex-noisy data. The truth is `epsr_in=3`, `epsr_out=6`, radius
50 mm, center `(0.5,0.5)` m. Training uses 12 pairs at 0.5/1.5 GHz, while
half-step-shifted acquisitions remain held out. Each arm has at most 40
optimizer residual evaluations; actual frequency-level forward calls and
analytic derivative work are separately counted. N64 optimization is audited
at N64/128/256. Fixed-mode Mie/FD sensitivities, material and refined set
errors, Jacobian singular values and column correlations accompany fields.

TRF's success flag, independently checked scaled projected stationarity and
physical recovery are different results. Small steps, a budget exit, a local
stationary point or a tiny field residual alone are not a global recovery or
identifiability claim. Noise tests use clean held-out fields for their
recovery gate. No conductivity, per-component unequal materials, region graph
or 3-D physics is introduced.

### Measured recovery and failed starts

The [eight-arm material batch](../../results/inverse/radial_fourier/shape_material/material_inverse/bounded-20260906/README.md)
finished in **73.55 s**. Five arms pass the predeclared physical-recovery gates.
Fixed-geometry clean starts at `epsr=2` and 5 recover 3 within `2.1e-11`;
the noisy fixed start 5 recovers `3.000807`, with clean held-out field error
`6.11e-4`. The joint low-permittivity start recovers the clean material within
`1.37e-10` and the set within `1.75e-12` m; with 1% complex noise it recovers
`3.000048`, with 0.0649 mm symmetric set error and `0.00349` clean held-out
field error.

All three high-permittivity starts fail and remain saved. Fixed-circle start 9
ends at `epsr=10.1433`, with held-out field error 1.247. TRF stops on its
relative-cost criterion, but the independently checked projected gradient is
`1.01e-5`, above the `1e-7` stationarity gate, and recovery fails. Both joint
start 2 arms exhaust 40 residual evaluations at the radius upper bound and one
shape-mode lower bound, with `epsr` near 4.119/4.124 and held-out errors near
0.85. They are neither stationary nor recovered. No extra restarts or
post-result tuning were added to turn these into successes.

The material/radius columns of the scaled, weighted real Jacobian have
correlation approximately **-0.960** near the successful joint solution;
its full local condition number is approximately 8.8. This establishes local
compensation in the declared coordinates, not global non-identifiability.
The successful noisy arm still fits under its frozen gates. Starting-basin
robustness is a different issue from local derivative correctness.

Independent material JVPs agree with Mie differences to at most `1.88e-8`
relative across the tested epsr 2/3/9; all predeclared sensitivity gates pass.
All candidate final-field refinement differences are at most `4.31e-13`,
including failed starts: accurately solving the forward problem does not
make a wrong inverse result correct. Observations and source hashes are
unchanged. Total recorded work includes 478 frequency-level forward calls,
1,320 analytic direction evaluations and separately measured oracle,
sensitivity and qualification costs. These are local homogeneous full-space
circle tests, not general material identification or physical GPR validation.

## Final verification and handoff

The final combined regression selection passed **514 tests**, with 276
existing warnings, in **123.98 s**. It includes the inverse, ordered geometry,
SDF-to-boundary, Kress, multi-component seam/oracle and all four relevant
comparison-driver contracts; it is not a claim that every repository test or
historical benchmark was rerun. The earlier 482-test result overlaps this
final selection and must not be added to it. All four final experiment NPZ
archives loaded with pickle disabled: **1,244 finite numeric arrays**, no
object arrays. `git diff --check` passed.

Current experimental API/reporting fixes include invalid unsigned paired-index
overflow, scale-aware primal/zero-contrast derivative checks, frozen
material-normalization cache identity, attempted-work accounting, strict
failure/stationarity distinctions and minimum-usable-bandwidth reporting.
Failed scientific experiments remain failed; fixes were not used to relabel
them as successful recoveries. Existing defaults and historical bundles are
unchanged, and no commit was made.

## Reproduction

Run from the repository root with the recorded EMNerf environment and a
**fresh** output directory:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_kress_shape_derivative_validation.py --output-dir results/kress_shape_derivative/NEW_RUN

env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_distance_tangency_comparison.py --output results/distance_tangency/NEW_RUN

env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_neural_metric_comparison.py --output-dir results/neural_metric/NEW_RUN

env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_material_inverse_comparison.py --output results/material_inverse/NEW_RUN
```

Strict JSON/CSV and non-pickled numeric geometry/field arrays record physical
configuration, immutable observations, source/code hashes, reference identity,
resolutions, failures, work and timings. Timed experiments run without other
project benchmarks competing for CPU. Single-run timings are descriptive,
not a hardware-independent speed claim.
