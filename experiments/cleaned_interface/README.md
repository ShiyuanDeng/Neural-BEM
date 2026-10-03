# Cleaned inverse campaigns (CI-001)

The maintained numerical API now lives in
[`solvers/bem_inverse`](../../solvers/bem_inverse/README.md). This directory
owns campaign commands, qualification, scoring, historical regression fixtures,
and compatibility imports. Edit runtime implementations in `bem_inverse`;
the old module paths forward to the same implementations. Existing command
lines remain valid. Pre-extraction source seals require their recorded sources;
use a fresh output directory for a campaign on the extracted code.

FM-001 adds opt-in full source-by-receiver observations for `nodal_kress`.
The runner flattens these in source-major order for fitting and audits;
localization still reads only the damped paired diagonal. Ordinary paired
calls and the default policy retain their behavior. `full_matrix.RelaxedStage`
selects a positive `relaxed_tau` for a stage (`None` retains ordinary loss).
FM-002 supplies the complete relaxed-loss gradient, including shape-dependent
receiver weights and penalty normalization, by eliminating the auxiliary field
and differentiating the resulting objective. The frozen-weight data Jacobian
is retained only as a curvature approximation. Trial and refined evaluations
recompute the exact loss; final audits always use ordinary real-data loss.
`full_matrix.RealRelaxedPrefix` is the fixed opt-in FRr schedule. Additional
adjoint RHS batches reuse existing CPU/CUDA LU factors and count against the
unchanged work budgets. Full-matrix frontier norms use all measured entries.

The preregistered campaign driver is `python -m experiments.cleaned_interface.fm001`:
`seal`, `controls`, `catalogs`, `paths`, `arm --arm F`, `arm --arm FRr`, and
`report`, in that order after Phase-0 replay. Run from the repository root
with `PYTHONPATH=.:solvers`, single-threaded BLAS, and the archived `EMNerf`
environment. It refuses changed source/input seals, unqualified catalogs,
incomplete run overwrites, and unpassed arm gates. Each arm stops at its
second loss of a previously recovered case. See the
[frozen FM-001 plan](../../docs/iterations/cleaned_interfaces/iteration_18/03_plan.md).

The corrected three-case, four-arm comparison driver is
`python -m experiments.cleaned_interface.fm002`. Invoke `seal`, `qualify`,
`run`, then `report`. It independently varies early damping and relaxation while all
arms keep damped paired localization. The new campaign has its own source
archive and input seal. FM-001 must be reproduced from its archived sources;
the corrected gradient does not rewrite that experiment. See the
[FM-002 plan](../../docs/iterations/cleaned_interfaces/iteration_19/03_plan.md).

FM-002 completed all 12 fixed runs: both damped arms recovered 3/3 selected
cases, and both real-prefix arms recovered 1/3. Corrected relaxation added
no recoveries. The [results and limits](../../docs/iterations/cleaned_interfaces/iteration_19/01_results.md)
record the numerical stops, costs, 477 passing tests and unchanged ordinary
controls. The ordinary damped default remains selected.

Current relaxed-BIE research now belongs to the
[standalone track](../../docs/iterations/relaxed_bie/README.md). Its
[updated assessment](../../docs/iterations/relaxed_bie/iteration_01/01_results.md)
qualifies the original closure recommendation, and
[RB-001](../../docs/iterations/relaxed_bie/iteration_02/01_results.md) records
the approved resolution-recovery follow-up. FM-001/FM-002 commands and sealed
artifacts retain their existing paths.

One maintained, truth-free SC/MA continuation runner. **The CI-001 campaign
passes 28 of 36 configurations under the frozen contract**, and recovery is 34/36,
the same as the archived strategies. Seven noisy cases fail the residual gate after the
discrepancy stop, and one noiseless case falls short on residuals. See the
[campaign results](../../docs/iterations/cleaned_interfaces/iteration_03/01_results.md).
Runtime retention is not established.

**Meaning of “node free.”** The defensible claim is **boundary-collocation-free
Fourier–Galerkin physics with spline-free, quadrature-based geometry** when the
spectral geometry update is explicitly selected. The complete inverse is not
sample-free: normal moves, arclength quadrature, metrics, interval proposals,
frontier diagnostics and the inconclusive-validity fallback use samples.
Nonlinear FFT operations have quadrature/aliasing error; they are not exact
coefficient convolutions. The validity inequalities hold in exact arithmetic,
but the current FFT rounding allowance is heuristic, not interval-verified.
See the [NF-001 review and experiments](../../docs/iterations/cleaned_interfaces/iteration_17/01_results.md).

## Run the 36 configurations

From the repository root, using the existing EMNerf environment:

```bash
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
CI_PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python

"$CI_PY" -m experiments.cleaned_interface inventory
"$CI_PY" -m experiments.cleaned_interface plan --cases modal__c4__development_c
"$CI_PY" -m experiments.cleaned_interface prepare
"$CI_PY" -m experiments.cleaned_interface spd-pairs --device auto
"$CI_PY" -m experiments.cleaned_interface augment --device auto --allow-new-damped-data
"$CI_PY" -m experiments.cleaned_interface run --solver nodal_kress --device auto --frequency-threads 4 --workers 1
"$CI_PY" -m experiments.cleaned_interface report
```

The output defaults to `results/validation/cleaned_interfaces/CI-001`.
Use `--output PATH` consistently for another campaign. Preparation only freezes
sources, input references, comparison tolerances and the policy; it does not
fit or synthesize observations. `spd-pairs` runs the two original SPD-016 D
pairs through the extracted interfaces, checks their accepted states and
decisions against each other and the archived reference, and measures the
original 20% saving gate. Inspect its `passed` result before the larger run.
These are four bounded attempts, separate from the 36 configurations.

`augment` generates and qualifies the **16 missing complex-frequency catalogs**
at 1024/2048 nodes. This changes their observation contract explicitly. All
original real observations and noise draws remain byte-for-byte unchanged;
noisy damped samples use a separately recorded independent Gaussian draw.
The 20 existing damped catalogs are reused. Augmentation checkpoints each
catalog, then seals hashes; fitting refuses an incomplete augmentation.
Generation is serial, with independent frequencies threaded.

`run` always starts each case from its prescribed original circle. It never
starts from a saved reconstruction. All 36 configurations, including the two
known contrast-13.3 C failures, are retained in `comparison.json` and
`comparison.csv`. `--cases ID ...` selects a subset for diagnosis, without
changing the algorithm. `--workers 1` is the conservative default; process
workers use spawn so CUDA is not inherited through fork. Stage progress is
printed, and accepted states and decisions are saved as the run proceeds.

Completed results can be resumed with the same command and settings. An
incomplete case directory is preserved and refused rather than overwritten.
Use another campaign directory for a rerun. A changed frozen source or input
also requires a new campaign.

## Public interface

```python
from bem_inverse import Problem, Observation, Execution, fit

result = fit(
    problem,  # original curve, real/damped observations, acquisition, contrast, units
    solver="nodal_kress",
    execution=Execution(device="auto", frequency_threads=4, acceleration="spd016"),
    output="path/to/one-run",
)
```

`Problem` has no scene ID, target, benchmark path or historical strategy.
Only the benchmark layer loads targets, for explicit observation generation
and scoring after fitting and numerical audit return.

The solver contract is in [physics.py](../../solvers/bem_inverse/physics.py). Predictions carry an
opaque handle; the optimizer passes that handle back for derivatives through
the **complete projected geometry trial**. The selected service also owns
localization qualification, its exact-disk landscape service, frontier
diagnostics, resolution profiles/refinement and numerical audit evaluations.
The runner never reads traces, matrices, factors or modal coefficients.
Register a qualified implementation with `register_backend(name, factory)`;
then the same `solver=name` selection covers the whole run.

`modal_muller` is the coefficient-space alternative (next section). Until `register()`
is called, `make_backend('modal_muller')` still raises a capability error
**before fitting**. There is no silent nodal replacement.

Solver selection is independent of `device=cpu|auto|cuda`, frequency threads
and geometry execution. `cpu` is explicit CPU execution. `auto` records CPU
fallbacks for unavailable CUDA, arguments outside the SPD-016 ray table, and
device out-of-memory. Explicit `cuda` fails for these unsupported conditions
instead of changing the requested execution. Device solve OOM can reuse host
LU under `auto`; the receipt records those fallbacks too. `acceleration=reference`
retains the current real-frequency CUDA/thread/cache path and uses reference
damped CPU/Mie evaluation. It is the matched execution control, not the old
serial CPU baseline. Pair it with `device=auto` or `cpu`.

## Modal Müller service

[modal_muller.py](../../solvers/bem_inverse/modal_muller.py) implements the same contract as
`NodalKress` with the Chebyshev Müller discretization: Fourier–Galerkin
traces `|m| <= K_trace` and no boundary collocation nodes in the operator. It is the clean
rewrite of the prototype that the
[independent review](../../docs/iterations/cleaned_interfaces/node_free_modal_muller_review.md)
checked. Registration remains explicit. Existing source seals must still match their recorded code:

```python
from bem_inverse.modal_muller import register
register()
result = fit(problem, solver='modal_muller', execution=Execution(device='auto', frequency_threads=4))
```

Physics and geometry are separate selections. The call above preserves the
legacy spline geometry. Select certified spectral geometry directly with
`fit(..., geometry_update='certified_spectral')`, or use the modal CLI:

```bash
"$CI_PY" -m experiments.cleaned_interface.modal_muller run --solver modal_muller \
  --geometry-update certified_spectral --output NEW_PREPARED_CAMPAIGN
```

Available geometry selections are `spline`, `spectral` (NU-003),
`certified_spectral` (NU-006 preparation plus NU-007 certificates on CUDA),
and `analytic_spectral` (NF-001 experimental
analytic quadrature tangent). Omission retains the existing runner/wrapper
choice. Explicit selection is recorded in campaign identity, plans, decisions,
configuration and results; changing it requires a fresh campaign. It cannot be
combined with a representation-specific `geometry_adapter`. The analytic path
runs on the CPU and retains the same sampled finite trial and validity tiers.

`device` has the same meaning as for Kress. `cpu` is the unchanged reference
path. `auto` runs geometry preparation and assembly on CUDA through
[modal_cuda.py](../../solvers/bem_inverse/modal_cuda.py), and falls back to the CPU after device
out-of-memory with a recorded reason. `cuda` fails instead of falling back.
Scalar Bessel/Hankel values, Graf waves, LU, fields and the Jacobian always
run on the CPU, so handles hold no device memory.

From the command line, use the same subcommands through the modal entry point,
with a new prepared campaign directory:

```bash
"$CI_PY" -m experiments.cleaned_interface.modal_muller run --solver modal_muller --output NEW_CAMPAIGN ...
```

| Stage | Code | Depends on k | Retained |
|---|---|---|---|
| geometry | `modal_geometry.ModalGeometry` (CUDA: `modal_cuda.DeviceModalGeometry`): Δ, R, W, \|W\|², normal products; certified log\|W\|²; Chebyshev T_n(R) and regular-wave arrays | no | per curve, window and device, LRU of 4 |
| waves | `modal_operator.point_kernels`: regular waves once per k, Graf source/receiver coefficients (CPU) | yes | receiver RHS in the handle |
| assembly | `modal_operator.muller_matrix` (CUDA: `modal_cuda.muller_matrix`): six radial functions → V, K, T (Maue), K′ = K transposed | yes | T_n arrays extended lazily |
| factorization / fields | dense LU, traces, paired receiver data | yes | LU in the handle |
| jacobian | `modal_operator.hadamard`: 2π(k_i²−k_e²) Σ_m w_m (u ũ)_{−m}, with w = Re(V conj N) from SC-035 coefficient velocities | yes | none |

Each stage is timed separately in `receipt()['stage_seconds']`. On the
19-frequency K=192 catalog with four frequency threads, a new geometry costs:

| Execution | Production | Refined |
|---|---:|---:|
| Modal CUDA | 0.26 s | 0.34 s |
| CUDA Kress (N=512 / N=1024) | 0.44 s | 1.73 s |
| Modal CPU | 2.1 s | 3.3 s |

For comparison, the review prototype took 46.6 s at production. For a single
cold frequency, CUDA Kress remains faster (0.03 s against 0.09 s at K=192).

**Resolution.** Tokens are `8*K_trace`. The factor only satisfies the shared
`FitStage` guard `nodes > 2*K_geometry`.

- Production uses `K_trace = max(64, 32*(ceil(K_geometry/64)+1))`: 64 for the
  damped prefix, 128 at K_geometry = 192.
- Refinement adds 32.
- The coefficient window is `K_trace + 64`, so LM acceptance and audits refine
  the trace cutoff and the window together.

The profile was raised by one step after
[CI-001-modal](../../results/validation/cleaned_interfaces/CI-001-modal-review/README.md).
There, the earlier production level (96 at K_geometry 192) was off by up to
9e-8 at contrast 13.3 and 2.5 GHz from M49 upward. That is within 2× of LM's
1e-7 production/refined tolerance. 128 gives ≤ 3.8e-10, and 160 gives
≤ 1.1e-12.

**Error control.** Each approximation has an explicit rule. When a rule fails,
the service raises `ValueError`, and LM records it as a numerical refusal.

- log|W|² is a Chebyshev series on `[beta, Lambda]`. Lambda is the coefficient
  triangle bound. beta must be certified by the complete coefficient residual
  `r = ||1 - |W|² v||_1 < 1`, which gives `|W|² >= (1-r)/||v||_1`. This replaces
  the prototype's assumed `beta = 0.05` and the finite-Parseval test that the
  review disproved. In exact arithmetic a crossing or touching curve cannot
  pass this inequality. Numerical receipts mark `arithmetic_verified=false`:
  the floating-point allowance is not a proved enclosure. Failure is
  inconclusive and does not establish a crossing (simple near-cusp curves can
  exhaust the degree/window budget too).
  Clockwise curves are refused from the coefficient signed-area formula.
- The radial degree is where every later Chebyshev coefficient falls below
  1e-15 of the coefficient sum.
- The Graf order uses the rigorous |J_l| bound (DLMF 10.14.4), with |H_l|
  from a scaled forward recurrence and a recurrence-based geometric tail. It
  has no fixed cap below 1024 orders.
- Row l of the regular waves is divided by `(k rho/2)^l/l!`, and H_l(kd) is
  multiplied by it. Orders of 250 and more therefore neither underflow nor
  overflow. SciPy's `hankel1` itself loses accuracy near its range limit
  (1e-5 at order 120, x = 1.3).
- Sources and receivers must lie outside the coefficient bounding circle.
- The regular-wave series is refused when its cancellation `eps*I0(|k| rho)`
  exceeds 1e-9.

**Limits.** The service supports one equal-density curve and paired point
sources only. Damped fields keep a roughly 6e-9 floor at 2.5 GHz, but the
policy damps only up to 1.25 GHz, where agreement is 1e-13. CUDA agrees with
the CPU path to the method's own floor (≤ 2.7e-12 on real fields); against
2048-node Kress, its error stays within 2× of the CPU's. Evidence:
[CPU service](../../results/validation/cleaned_interfaces/modal-muller-service-20260930/README.md) and
[CUDA execution](../../results/validation/cleaned_interfaces/modal-muller-cuda-20261001/README.md).
The [all-36 campaign](../../results/validation/cleaned_interfaces/CI-001-modal-review/README.md)
found two limits:

- Graf refusal near the acquisition;
- a coarse production profile at contrast 13.3.

Both were fixed afterwards
([fix bundle](../../results/validation/cleaned_interfaces/modal-muller-fixes-20261001/README.md)).

## Coefficient normal update (NU-001)

[n_update.py](../../solvers/bem_inverse/n_update.py) is an alternative geometry update with the same
step coordinates as `ProjectedUpdate`. It moves the Laurent coefficients
directly:

```text
z_new = z + P_K[sum_q a_q (phi_q N + psi_q z')] / (sigma_0 L_unit),   N = sum_j j z_j w^j
```

- φ_q are the θ-harmonics 1, cos mθ, sin mθ; σ₀ = L/2π.
- ψ = 0 in arm A. Arm B (`tangential=True`) adds the band-limited
  Hou–Lowengrub–Shelley tangential term, which holds the speed profile to first
  order.
- The trial is affine in a, so the shape directions are exact coefficient
  arrays. There are no splines, no finite differences and no
  reparameterization; the speed ratio is monitored, not restored.
- Validity is tiered: exact signed area; an optional incremental |W|²
  certificate; a Bernstein bound on min|z′|²; then the baseline sampled test.

It is not wired into `fit`. [n_update_audit.py](n_update_audit.py) substitutes
it for one run without touching CI-001 frozen sources, and also holds the
pre-run control and the drift report:

```bash
python -m experiments.cleaned_interface.n_update_audit control --output DIR
python -m experiments.cleaned_interface.n_update_audit prepare --arm A --output CAMPAIGN
python -m experiments.cleaned_interface.n_update_audit run --output CAMPAIGN --cases core__kite
python -m experiments.cleaned_interface.n_update_audit drift --campaigns CI-001 NU-001-A NU-001-B --output DIR
```

Plan and decision rules: [iteration 08](../../docs/iterations/cleaned_interfaces/iteration_08/03_plan.md).

[n_reparam.py](n_reparam.py) is the spectral arclength reparameterization
(proposal eq. 9: quadrature on a uniform grid, no splines or inversion) with
an exact shape-distance audit; tests in `test_n_reparam.py`. It is not wired
into `fit`. `python -m experiments.cleaned_interface.n_reparam` reproduces the
NU-002 replay ([iteration 10](../../docs/iterations/cleaned_interfaces/iteration_10/01_results.md)).

[nu003.py](nu003.py) is `SpectralProjectedUpdate`: the CI-001 trial map with the
spline resampler replaced by the eq. 9 quadrature (no splines). It also provides
the NU-003 pre-check, campaign substitution and drift/identity report; tests in
`test_nu003.py`. Results: [iteration 11](../../docs/iterations/cleaned_interfaces/iteration_11/01_results.md).

[nu004.py](nu004.py) runs the NU-003 map with `solver='modal_muller'` (arm MS)
and a modal + spline control (arm MN), and writes the drift/identity report.
Results: [iteration 12](../../docs/iterations/cleaned_interfaces/iteration_12/01_results.md).

[nu005.py](nu005.py) is `CertifiedSpectralUpdate`: the NU-003 map whose three
sampled validity tests (moved curve, coarse and fine, and candidate) are each preceded by
coefficient certificates (exact area, then Lemma 3–4 increment, then the full |W|² certificate,
with the unchanged sampled test as fallback). It also provides the NU-005 pre-check
and campaign; tests in `test_nu005.py`. The drift and decision audit is
[nu005_drift.py](nu005_drift.py). Results:
[iteration 13](../../docs/iterations/cleaned_interfaces/iteration_13/01_results.md).

[nu006.py](nu006.py) is `BatchedCertifiedUpdate`: the NU-005 update whose `prepare`
evaluates all 2(2M+1)+2 projections in one torch float64 call (CUDA when available;
it falls back to the sequential CPU path after device out-of-memory). It is
decision-identical to NU-005 and cuts geometry preparation from 150 s to 3.9 s on the six core
cases; tests in `test_nu006.py`. Results:
[iteration 14](../../docs/iterations/cleaned_interfaces/iteration_14/01_results.md).

[nu007a.py](nu007a.py) completes GPU certificate qualification under the
disclosed threshold-scaled comparison gate. All 864 offline comparisons and
18 complete CPU/GPU pairs pass, retaining archived NU-006 paths and results.
Across six core cases, the sum of per-case median runtimes falls from 247.2 s
to 149.6 s, and certificate work from 103.5 s to 7.5 s. Explicit
`certified_spectral` selection now uses `DeviceCertifiedUpdate` on CUDA and
retains `BatchedCertifiedUpdate` on CPU; the spline/nodal defaults remain.
The original failed NU-007 evidence is preserved. See the
[qualification and integration report](../../results/validation/cleaned_interfaces/NU-007a-20261003/README.md).

## Executable policy

[policy.py](../../solvers/bem_inverse/policy.py) is the single definition of `cumulative_sc_ma/1.0.0`.
The CLI plan, `plan.md`, `plan.json`, and resolved `decisions.json` come from
its operation objects. Static fits list actual frequencies/wavenumbers,
damping, weights, bands, accuracy profile, optimizer settings, budgets,
stopping rules and transitions. Adaptive frontier stages show their formula,
inputs, threshold and possible bands before running, then their measured
value and resolved stages during execution.

The noiseless path preserves the archived MA-004/005 semantics:

1. Audit the original circle on the full real catalog.
2. Localize using the first three damped frequencies, exact Mie grid and
   coordinate refinement; qualify with the selected backend.
3. Damped 0.25 GHz warm-up, then four damped prefix stages with
   `M=floor(3*max(real(k_exterior)))` and `K_geometry=2*M+2`.
4. Explicit real-frequency stage-four handoff.
5. Full real-catalog releases `M=11,15,19,25,31,37`, `K_geometry=192`.
   Before M25, crop coefficients to 64 and zero-pad to 192, without a refit.
6. Measure the paired-Jacobian 1% frontier at the highest real frequency;
   append `43,49,...,91` while below the frontier and the next band is <=95.
   This preserves the original arithmetic progression, including its ceiling.
7. Independently audit the returned curve after every exit, then score outside
   the inverse. Hard stops and numerical refusals remain explicit outcomes.

Declared noise invokes the same rule on every configuration: inverse-variance
whitening, SC-044's `1.1² * expected_noise_loss` discrepancy threshold,
recurrent coefficient cleanup before full-catalog releases, and no further
release/tail once the full real catalog reaches that discrepancy. This is a
**policy change relative to DF**, proposed to retain earlier noise handling;
its reconstruction benefit is not established by the interface tests.
There are no scene-specific historical fallbacks or truth-based decisions.

M is the shape-update band; K_geometry is Cartesian storage; K_trace is a
backend-internal physics cutoff. Nodal/coefficient workspace resolution is a
separate backend profile. The LM compatibility structure still names its two
opaque resolution tokens `nodes` and `refined_nodes`; only the nodal service
interprets them as node counts.

The fit cap is 13,412 SPD units and 1,800 seconds, including localization and
frontier diagnostics. Audits each have a separate 300-second limit. Caps are
checked before complete batches; a running numerical call may finish after
the wall limit. Preserve both the original optimizer ledger and the service's
actual attempted/completed/failed calls, including speculative frequency work.

## Compare evidence

The frozen comparison contract reports every configuration separately:
recovery, boundary RMS, Hausdorff upper bound, all-frequency residuals,
numerical audit, stopping outcome, work and runtime. Geometry retention uses
an additive `max(0.02 mm, 5% of reference)` allowance; residual retention uses
`max(1e-6, 5% of each reference residual)`. These are predeclared engineering
gates, not equivalence claims between different algorithms. Same-backend
extraction and SPD controls have separate, tighter tolerances. The two known
failures retain their actual errors and are compared too.

The report includes exact historical source/input hashes and complete
predecessor references. Historical suffix costs are identified. Missing
full-path costs remain unknown; overlapping cumulative records are not added
twice. Archived host timings cannot establish a runtime pass.

For a runtime claim, run three independent full-path reference/candidate pairs
with identical hardware, device, threads, workers, policy and observations.
Use `--acceleration reference` for the current real-CUDA/thread/cache baseline
and `--acceleration spd016` for the candidate. Reuse exact augmented input
bytes in each prepared campaign:

```bash
"$CI_PY" -m experiments.cleaned_interface augment --output NEW_OUTPUT \
  --reuse-from results/validation/cleaned_interfaces/CI-001 --allow-new-damped-data
"$CI_PY" -m experiments.cleaned_interface compare-execution \
  --references REF1 REF2 REF3 --candidates RUN1 RUN2 RUN3 --matched-host-load
```

The last flag attests comparable external host load; hardware, software,
thread settings, source/input hashes, observations, accepted decisions and
work are checked. Every case must retain quality and have a median runtime
ratio <=1.20. The report marks requirement 1 satisfied only after both the
all-36 numerical and matched runtime gates pass. The two-pair SPD speedup
alone cannot qualify the full DF path or all 36 configurations.

## Implementation and checks

| Responsibility | Maintained code |
|---|---|
| Inputs without truth | `problem.py` |
| Policy, plans, adaptive rules | `policy.py` |
| Complete projected update and exact cleanup | `geometry.py` (extracted SC-035/042) |
| Optimizer | shared `shape_continuation/lm_backend.py`, explicit service hook |
| Backend and work diagnostics | `physics.py` |
| Modal Müller backend | `modal_muller.py` (service), `modal_geometry.py`, `modal_operator.py`, `modal_cuda.py`; tests in `test_modal_muller.py` |
| Localization | `localization.py`, `mie_grid.py` |
| Damped CUDA assembly | `damped_cuda.py`, explicit radial-kernel argument in Kress |
| Interpretation, checkpoints, audits | `runner.py` |
| Frozen inputs, generation, scoring, comparisons | `benchmark.py`, `qualification.py` |

There are no result-folder Python imports or process-global solver/contrast
patches in the maintained path. Archived scripts and evidence remain in place.
The SPD-016 field-table extension is intentionally not selected. See
[implementation evidence](../../results/validation/cleaned_interfaces/CI-001-implementation/README.md)
for the focused checks, and the
[campaign review](../../results/validation/cleaned_interfaces/CI-001-campaign-review/README.md)
for the all-36 regressions and build re-verification.
