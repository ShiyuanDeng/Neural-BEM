# Repository freeze — 2026-10-05

> Historical snapshot: this report records the read-only audit of October 5, 2026.
> It was saved to the repository on October 6 at the user's request. Statements
> about HEAD, dirty files, checks not rerun, and repository preservation refer to
> the audit, before this report was saved and the workspace committed. Links point
> to repository paths; use the recorded source revisions and experiment archives
> when later changes alter those paths.
>
> **Fact-checked 2026-10-06.** A second, independent pass re-derived the report's
> claims from source code, saved result files and Git (not from summary documents).
> Corrections are applied inline and listed in [Appendix A](#appendix-a--fact-check-log-2026-10-06).
> Since the audit, the dirty tree it describes was committed unchanged (plus a one-line
> stale test assertion) as **`71087669`**. That commit is now the reproducible reference
> for the frozen state.

**The maintained research pipeline is now an explicit Cartesian Fourier boundary inverse solver using modal Müller physics.** Neural SDF inversion, topology changes, modal compression, and several alternative continuation schemes have substantial histories, but they are not all part of that pipeline.

The strongest completed current-benchmark result is **26 recoveries out of 30 TG-002 cases**. That result belongs to recorded experiment versions. It does **not** establish that the exact audited working tree—containing newer kernel changes and uncommitted policy work—has completed the same campaign.

The audit made no repository changes, ran no inverse experiments, and reran no numerical tests. It inspected source, Git history, documents, and saved evidence; independently checked stored classifications and selected hashes; and confirmed that the repository contents remained unchanged.

## 0.1 Exact checkout

| Item | Frozen state |
|---|---|
| Repository | `/home/drdeng/Neural_SDF_BEM_AD` |
| Initial snapshot | **2026-10-05 22:30:03 UTC**, 23:30:03 BST |
| Current branch | **`feature/shape-frequency-continuation`** |
| HEAD | **`3d3ed16aff94ddde425a47b9517e55a726f24658`** |
| Commit date | **2026-10-05 22:11:47 +01:00** |
| HEAD subject | `profile(modal): separate Chebyshev construction and forward assembly costs` |
| Configured upstream | `origin/feature/shape-frequency-continuation` |
| Locally recorded upstream relationship | Same commit; no ahead/behind difference |
| Working tree | **12 modified tracked files; 8 untracked files; no staged changes** |
| Worktrees | One: this checkout |
| Remote verification | No fetch or live remote comparison performed |
| Post-freeze reference commit | **`710876696a0eb2bf616e8dede89f55135aed7559`** (2026-10-06 01:51 BST, pushed): the audited dirty tree, this report, and a one-line test-assertion fix |

**Branch discrepancy:** the supplied preferences name `feature/ordered-boundary-nystrom`, but the actual checkout is `feature/shape-frequency-continuation`. The audit preserved the actual checkout.

The locally visible branch tips are:

| Branch/ref | Tip | Interpretation |
|---|---|---|
| `feature/shape-frequency-continuation` | `3d3ed16a` | Current development |
| `origin/feature/shape-frequency-continuation` | `3d3ed16a` | Locally recorded upstream |
| `feature/ordered-boundary-nystrom` | `d5bce837` | Older modal-compression closeout |
| `origin/feature/ordered-boundary-nystrom` | `d5bce837` | Also the locally recorded `origin/HEAD` |
| `origin/claude/magical-meitner-11naoj` | `0c203e33` | Additional locally visible remote-tracking history |

The current branch is **446 commits beyond** the ordered-boundary branch's ancestor tip. There are **558 commits reachable through locally available refs**, including stash history. A September 1 stash titled `local one-off QBX baseline helper` and the tag `qbx-kdiff-closeout-2026-09-01` also remain.

### Modified and untracked files

```text
Modified tracked files:
  docs/iterations/CI-SPD/CONTINUATION_SCHEDULE.md
  experiments/benchmark/__main__.py
  experiments/benchmark/campaign.py
  pytest/bem_inverse/test_pipelines.py
  solvers/bem_inverse/certified.py
  solvers/bem_inverse/continuation/lm_backend.py
  solvers/bem_inverse/continuation_policy.py
  solvers/bem_inverse/geometry_selection.py
  solvers/bem_inverse/physics.py
  solvers/bem_inverse/pipelines.py
  solvers/bem_inverse/policy.py
  solvers/bem_inverse/runner.py

Untracked files:
  docs/iterations/CI-SPD/CONTINUATION_VARIANTS.md
  experiments/benchmark/policy_screen.py
  experiments/benchmark/runtime_report.py
  experiments/benchmark/test_policies_archive.py
  pytest/bem_inverse/test_entry_reuse.py
  pytest/bem_inverse/test_policies.py
  pytest/bem_inverse/test_validity_order.py
  solvers/bem_inverse/policies.py
```

These changes matter scientifically: they include policy selection, geometry-validity ordering, stage-entry reuse, compact geometry storage, and a modal resolution response. **HEAD alone is therefore not a complete representation of the executable workspace at the freeze.** In particular, the modified benchmark CLI imports the untracked policy registry.

### Recent commits

All dates below are October 5, 2026, BST.

| Time | Commit | Recorded change |
|---|---|---|
| 22:11 | `3d3ed16a` | AC-002 forward-cost profile |
| 21:40 | `009bf5b2` | Analytic radial Chebyshev coefficients |
| 16:29 | `9c7a98c8` | GauGal TV repair; data/shape mismatch retained |
| 15:51 | `7b5bd696` | GS-001 native-TV stall recorded |
| 15:46 | `bbf1c438` | CS-001: four retained recoveries and C-shape regression |
| 15:20 | `cbb81ebc` | CS-001 similarity initialization prepared |
| 14:58 | `601eaba6` | Continuation schedule/runtime documentation |
| 14:42 | `411d80f1` | GGB-005 single-frequency translation/radius experiment |
| 14:28 | `7ed9c31f` | GGB-004 translation/radius experiment |
| 14:10 | `47db3b3d` | GGB-003 translation comparison |
| 14:00 | `a2fe0e07` | GGB-003 preparation |
| 13:41 | `d8b11020` | DP-001: 26 recoveries retained; 1.134× median speedup |

## 0.2 Repository and evidence map

| Area | Actual role |
|---|---|
| [solvers/bem_inverse](../../solvers/bem_inverse/README.md) | Maintained cleaned inverse implementation |
| `solvers/periodic_kress`, `ordered_boundary`, `gpr_bem_kress` | Ordered-boundary/nodal physics and supporting machinery |
| `solvers/sdf_inverse`, `sdf_to_ordered_boundary`, `sdf_bem_multicomponent` | Neural/SDF and multicomponent historical pipelines |
| `solvers/gpr_bem_mod`, `gpr_bem_qbx`, `gpr_bem_kdiff`, `gpr_bem_ndiff`, reference packages | Earlier formulations and preserved controls |
| [experiments/benchmark](../../experiments/benchmark/README.md) | TG-002, the current benchmark entry point |
| `experiments/cleaned_interface`, `shape_continuation`, `modal_atlas` | Earlier campaigns and diagnostics |
| `experiments/top018`–`top025`, `spd*`, `bie*` | Topology, runtime, and derivative experiments |
| `experiments/modal_muller_research`, `laurent_*`, `modal_entry_screen` | Isolated modal/Laurent/compression research |
| `experiments/theory_radius`, `relaxed_bie`, `atlas` | Continuation theory and optimization diagnostics |
| `experiments/fresnel`, `polarization`, `time_domain`, `halfspace`, `ibim3d`, `algoim` | Separate extensions and feasibility work |
| `docs/iterations` | Dated plans, proposals, reviews, results and decisions |
| `results/validation` | Main numerical evidence archive |
| `results/legacy`, `results/experiments` | Earlier solver evidence and isolated research |
| `results/exploration-*`, `fresnel`, `time_domain`, etc. | Extension-specific evidence |
| `pytest` and experiment-local tests | Validation implementations |
| Root `run_*.py`, notebooks and ZIP handoffs | Historical drivers and handoffs; not a reliable selector of the current method |
| `bembel`, `bempp-cl`, `gprMax`, `ngbem`, `scuff-em` | Vendored/reference software, not evidence that those methods drive the maintained inverse |

The inventory found **1,603 Markdown files** under the main documentation, experiment, solver and result trees. The results tree contains roughly **59,000 files including ignored/generated material**. This is a repository-wide census followed by focused semantic inspection of the active pipeline and research tracks; it is not a claim that every binary array or figure was independently reanalysed.

### Major theory, review and vision documents

These documents have different evidential roles:

| Document | Role in the history |
|---|---|
| [Original deep-research report](../reference/deep-research-report.md) | Neural-SDF-to-ordered-boundary vision; Methods A/B/C |
| [Fully modal Müller atlas vision](fully_modal_muller_atlas_research_vision.md) | Modal structure and adaptive-inverse proposals |
| [Laurent research track](../iterations/laurent/README.md) | Literature reviews, modal operators, local responses, ROMs and calibration |
| [Modal-compression track](../iterations/modal_compression/README.md) | Includes the 34-page geometry-spectrum compression theory PDF |
| [Shape/frequency continuation track](../iterations/shape_frequency_continuation/README.md) | Includes the atlas-driven continuation literature review and SC plans |
| [Node-free Müller summary PDF](../iterations/cleaned_interfaces/node_free_modal_muller_summary.pdf) | Chebyshev/logarithm proposal containing claims later challenged |
| [Independent node-free review](../iterations/cleaned_interfaces/node_free_modal_muller_review.md) | Reproduction, counterexamples and scope corrections |
| [October 3 theory directions](../theory_directions_cartesian_fourier_2026-10-03.md) | Explicit-boundary theory proposals; mostly not implemented |
| [October 3 inverse review](inverse_review_2026-10-03.md) | Code/evidence reconciliation |
| [CI-SPD track](../iterations/CI-SPD/README.md) | Latest runtime, continuation, GauGal and radial-coefficient work |

A document's existence, including an “agreed plan,” was not treated as execution evidence.

## 0.3 Integrity checks performed during the audit

At **22:39:24 UTC**, the final content census matched the initial census:

```text
Tracked + non-ignored untracked regular files: 56,335

SHA-256 of the sorted path → file-SHA-256 mapping:
9db28a1fc5be29ed7318fa5243c09ba88ea58f3be59872c004be4e43f90143d8
```

HEAD and Git status also matched. This fingerprint excludes ignored files and Git metadata; it is an integrity observation, not a backup.

For TG-002:

- **131 sealed input files** matched their recorded hashes.
- The frozen source archive matched its manifest hash.
- The manifest records no input-qualification failures.
- Manifest SHA-256: `34375b59a40ed8e945904b246d3022bdeeeacb2291fced1bafc16f6861be7b00`.

Evidence: [TG-002 manifest](../../results/validation/cleaned_interfaces/TG-002/manifest.json).

# Part 1 — The actual current pipeline

## 1.1 Which entry point selects it?

There is **no single repository-wide default** independent of the entry point.

| Entry point | Actual selection |
|---|---|
| Benchmark CLI, ordinary invocation | `modal_muller` + `certified_spectral` + `CumulativePolicy` (defaults: 1,800 s fit, 300 s audit) + localization `none`; behaves like `modal_fixed` (hard stop on an unresolved trial) |
| Benchmark `--pipeline modal_fixed` | Same physics/update pairing; unresolved numerical trials cause a hard stop |
| Bare `bem_inverse.runner.fit(...)` | Legacy defaults: `nodal_kress` and spline-based projected update |
| Benchmark `--policy ...` | Working-tree policy registry selects a complete recipe and benchmark contract |
| Old root drivers / topology drivers | Their own older pipelines; not interchangeable with the maintained benchmark |

This is traced through [benchmark CLI](../../experiments/benchmark/__main__.py), [campaign dispatch](../../experiments/benchmark/campaign.py), [runner](../../solvers/bem_inverse/runner.py), and [pipeline definitions](../../solvers/bem_inverse/pipelines.py).

The current modal service explicitly requires:

- one `FourierCurve`;
- positive known contrast;
- equal-density homogeneous transmission physics;
- paired point-source acquisition.

It does not select neural weights, topology changes, material estimation, layered media, or a full multistatic acquisition. See [backend validation](../../solvers/bem_inverse/modal_muller.py).

## 1.2 Information flow

```text
Frozen observations + known contrast + initial Fourier curve
                              │
                              ▼
c = {c_j}, z(θ) = Σ c_j exp(ijθ)
                              │
                              ▼
ModalGeometry(c)
  normal-density coefficients N = -i z′
  squared-distance coefficients R
  divided difference W
  log|W|² and Chebyshev geometry arrays
                              │
                  exterior/interior k, k_i
                              ▼
Dense Fourier–Galerkin Müller matrix A(c,k)
                              │
             incident Dirichlet/flux coefficients b
                              ▼
A x = b,  x = [û_D, q̂], q = |z′| ∂ₙu
                              │
                  receiver representation
                              ▼
paired scattered fields F(c,k)
                              │
               observed data and normalization
                              ▼
real stacked residual r and loss ½‖r‖²
                              │
      reciprocal traces + complete-trial geometry velocities
                              ▼
Jacobian J = ∂r/∂a
                              │
             damped Gauss–Newton / LM system
                              ▼
normal-update coefficients a
                              │
          clipping, halving and geometry construction
                              ▼
c_trial = c + P_Kg[ R_arc(z + h_a n) − R_arc(z) ]
                              │
      geometry checks + production/refined field checks
                   + reliable decrease test
                              ▼
accept c_new, or reject/stop
                              │
            next iteration / next policy stage
                              ▼
all-frequency endpoint audit
                              │
                benchmark-only truth scoring
```

Here `R_arc` denotes arclength reparameterization, **not** the squared-distance coefficient object.

## 1.3 Objects, implementation and validation

| Step | Mathematical object and representation | Inputs → outputs | Source/functions | Used by ordinary benchmark? | Validation boundary |
|---|---|---|---|---|---|
| Geometry state | $z(\theta)=\sum_{j=-K_g}^{K_g}c_j e^{ij\theta}$, complex Cartesian coefficients | Coefficients → curve, derivatives, sampled geometry | [FourierCurve](../../solvers/bem_inverse/continuation/geometry.py) | Yes | Shape/geometry tests; sampled validity alone is not a global certificate |
| Geometry coefficient objects | Normal density $N=-iz'$, $R=\lvert z(\theta)-z(\phi)\rvert^2$, divided difference $W$, coefficient multipliers | Curve + workspace → frequency-independent coefficient arrays | [ModalGeometry](../../solvers/bem_inverse/modal_geometry.py) | Yes | Coefficient/nodal comparisons and log-bound tests; finite workspace and arithmetic remain relevant |
| Smooth radial kernels | Six regularized Helmholtz/material-difference functions in Chebyshev coefficients | $k_o,k_i$, radial interval → radial coefficient arrays | [radial_coefficients](../../solvers/bem_inverse/modal_operator.py) | Yes; AC-001 implementation | 24 scalar cases and four forward comparisons recorded; no fresh full inverse campaign |
| Singular/operator assembly | Exact Fourier logarithm symbol plus smooth coefficient contractions; dense block matrix | Geometry + radial arrays + trace cutoff → $A$ | [kernel_matrix / muller_matrix](../../solvers/bem_inverse/modal_operator.py) | Yes | Modal/nodal, Mie, field and derivative checks; not a sparse/compressed production operator |
| Incident traces | Scaled Graf expansions; Dirichlet and flux coefficients | Geometry + external point sources → right-hand sides | [point_kernels](../../solvers/bem_inverse/modal_operator.py) | Yes | Scaled-Graf corrections and regression evidence; bounding-circle/order restrictions apply |
| Boundary solve | $Ax=b$, $x=[\hat u_D,\hat q]$, $q=\lvert z'\rvert\partial_nu$ | Dense matrix/RHS → modal traces and retained LU | [ModalMuller._evaluate](../../solvers/bem_inverse/modal_muller.py) | Yes | Algebraic residual recorded; this alone does not certify discretization accuracy |
| Receiver field | Boundary representation contracted with receiver coefficients | Traces + receivers → paired complex scattered fields | Same `_evaluate`; `point_kernels` | Yes | Production/refined and independent reference comparisons in tests |
| Objective | Normalized complex residual stacked into a real vector; $\frac12r^Tr$ | Predictions, data, weights → residual/loss | [normalize / Objective](../../solvers/bem_inverse/continuation/lm_backend.py) | Yes | Objective/derivative tests; declared-noise weighting differs from noiseless TG-002 |
| Geometry tangent | Cartesian coefficient velocities of the complete projected trial | Current curve + update basis → `space.derivatives` | [BatchedCertifiedUpdate.prepare](../../solvers/bem_inverse/batched.py) (on CUDA, its subclass `DeviceCertifiedUpdate`) | Yes | Default uses centered finite differences of geometry construction, not forward-solve finite differences |
| Physics sensitivity | Reciprocal Hadamard contraction with $w_i=\Re(V_i\overline N)$ | Forward/reciprocal traces + geometry velocities → complex field Jacobian | [derivative / _contract](../../solvers/bem_inverse/modal_muller.py), [hadamard](../../solvers/bem_inverse/modal_operator.py) | Yes | Refined-column comparisons and complete-trial directional FD checks |
| LM update | $(J^TJ+\lambda D)a=-J^Tr$ | Residual/Jacobian → proposed real normal coefficients | [fit_stage](../../solvers/bem_inverse/continuation/lm_backend.py) | Yes | Optimizer tests and campaign histories; damping depends on selected policy |
| Geometry update | Centered arclength projection of a normal displacement | $c,a$ → trial coefficients | [spectral_project](../../solvers/bem_inverse/spectral.py), [CertifiedSpectralUpdate.trial](../../solvers/bem_inverse/certified.py) | Yes | Coarse/fine projection checks, certificate attempts, sampled fallback and domain checks |
| Acceptance | Geometry admissibility, resolution and reliable decrease | Trial/base at two resolutions → accept, reject or stop | [acceptance / resolution_check](../../solvers/bem_inverse/continuation/lm_backend.py) | Yes | Explicit numerical gate; “audit passed” is separate from target recovery |
| Continuation | Frequency, damping and update/storage-band schedule | Previous endpoint + policy → next stage | [CumulativePolicy](../../solvers/bem_inverse/policy.py) | Yes | Multiple historical and TG-002 campaigns; variants have different evidence |
| Endpoint audit | All-real-frequency field, Jacobian-column and complete-trial FD checks | Returned curve → numerical qualification | [runner.audit](../../solvers/bem_inverse/runner.py) | Yes, including failed exits | Normally refinement of selected backend; not always an independent discretization |
| Recovery scoring | Geometry error plus data fit plus audit | Endpoint + truth → recovery classification | [campaign.run_case](../../experiments/benchmark/campaign.py) | After fitting only | Truth scoring belongs to experiment code, not solver decisions |

### Three bandwidths must remain distinct

| Symbol | Meaning | Example |
|---|---|---|
| $M$ | Normal-update harmonic cutoff; $2M+1$ real update variables | $M=11,15,19,\ldots$ |
| $K_g$ | Stored Cartesian geometry cutoff | Early stages use small bands; established full-catalog stages use 192 |
| $K_t$ | Trace cutoff for each boundary unknown | Often 64/96 or 128/160 production/refined |
| $B$ | Coefficient workspace | Normally $K_t+64$ |

For the current modal profile,

$$
K_t=\max\left(64,\;32\left(\left\lceil K_g/64\right\rceil+1\right)\right),
$$

with refined cutoff $K_t+32$.

Thus:

- $K_g\le64$: ordinarily $K_t=64/96$;
- $K_g=192$: ordinarily $K_t=128/160$;
- matrix dimension is $2(2K_t+1)$;
- the generic “resolution” integer is **a token $8K_t$**, not a boundary-node count.

This coupling is important for interpreting CS-001: reducing stored geometry also reduced the trace resolution. See [resolution_profile](../../solvers/bem_inverse/modal_muller.py).

## 1.4 What the Müller construction actually contains

The current matrix is assembled as

$$
A=
\begin{bmatrix}
I-\Delta K & \Delta V\\
-\Delta T & I+\Delta K'
\end{bmatrix}.
$$

The logarithmic singularity is handled through its known Fourier coefficients, with nonzero modes proportional to $-1/|\ell|$. The hypersingular contribution uses the Maue form before modal truncation.

The current implementation uses:

- coefficient geometry;
- Chebyshev expansions for the smooth radial terms;
- analytic radial coefficient construction introduced by AC-001;
- coefficient contractions into a **dense** modal system;
- scaled Graf expansions for point-source and receiver traces.

It does **not** use the historical proposed compressed modal mask, broadband ROM, multi-object response solver, or a matrix-free inverse by default.

The geometry cache reuses exactly matching curve coefficients, workspace and device. It does not establish that a matrix or factorization can be reused after changing the shape.

### CPU/GPU scope

For the modal service, coefficient geometry and assembly can run on CUDA. The displayed implementation still uses SciPy LU factorization/solves, with point-wave and Jacobian work on the CPU. Consequently, “GPU inverse” does not mean that every operation executes on the GPU.

`device=auto` selects CUDA when available. Explicit CUDA requests and automatic fallback have different semantics; an explicit unavailable CUDA request is an error.

## 1.5 What “Jacobian” means here

The active physics derivative is a reciprocal shape derivative. Schematically,

$$
\frac{\partial F_r}{\partial a_i}
=
2\pi(k_i^2-k_o^2)
\sum_m (w_i)_m
\bigl(u_s\,\widetilde u_r\bigr)_{-m}.
$$

However, its geometry velocities are generated through the complete update construction.

For the default `certified_spectral` preparation, the code evaluates the geometric projection at zero and at positive/negative perturbations of each coordinate, normally with a **$10^{-7}\,\mathrm m$** step, then forms centered differences.

Therefore:

- it is **not** finite-differencing every forward solve to build the Jacobian;
- it is **not** automatic differentiation through the entire discrete program;
- it is **not** an exactly differentiated default geometry map in floating-point arithmetic;
- the separate `analytic_spectral` option does not describe the ordinary default.

This distinction matters when reading older references to “AD,” “exact velocities,” or “node-free derivatives.”

## 1.6 Geometry restriction and acceptance

The default trial has the form

$$
z_{\mathrm{trial}}
=
z+P_{K_g}\left[\mathcal R(z+h_a n)-\mathcal R(z)\right].
$$

The centered difference between reparameterized curves makes the zero update an identity. The implementation evaluates arclength quadrature on sampled grids; spectral storage does not eliminate all sampling.

The acceptance path includes:

1. step clipping and possible halving;
2. displaced/final-curve validity checks;
3. coarse/fine geometry-projection comparison;
4. production and refined physics evaluations;
5. resolution tolerances;
6. a decrease test that accounts for disagreement between resolutions.

The established `modal_fixed` path stops on an unresolved numerical trial. The `modal_response` variant (dirty tree at the freeze, committed in `71087669`) promotes an unresolved trial once to $K_t=128/160$ and rejects unresolved trials there instead of stopping. It is not a qualified replacement.

### “Certified” has a bounded meaning

The current log-modulus machinery uses a coefficient residual argument, including the **full, untruncated residual convolution**, to bound positivity. That is stronger than the invalid finite-section/Parseval arguments in the September PDF.

Nevertheless:

- sampled values help construct the candidate interval;
- floating-point allowance is not an interval-arithmetic proof;
- geometry checking can fall back to sampled checks;
- arclength projection and complete-trial validation still use samples;
- coefficient windows and series limits can cause refusals.

The current solver is not established as an entirely sample-free, formally certified inverse algorithm.

## 1.7 The ordinary continuation schedule

For TG-002, the default policy executes this sequence. Bands below were checked against the executed `plan.json` of recorded DP-001 runs.

| Phase | Actual action |
|---|---|
| Initial audit | Qualify the prescribed start |
| Localization operation | Benchmark `none` adapter keeps the centered start |
| Warm-up | Damped 0.25 GHz, $M=1$, $K_g=4$ |
| Frequency ladder | Cumulative damped prefixes ending at 0.5, 0.75, 1.0 and 1.25 GHz; $M=3,5,7,9$ with $K_g=2M+2=8,12,16,20$ ($M=\lfloor3\max\Re k\rfloor$); $K_t=64/96$ |
| Return to measured objective | Same four frequencies, undamped, $M=9$, $K_g=20$ |
| Full-catalog release | All 19 real frequencies, $M=11,15,19$, $K_g=192$, $K_t=128/160$ |
| Cleanup | Once, before $M=25$ (noiseless data): crop stored geometry to band 64 and pad back; no arclength refit |
| Fixed releases | $M=25,31,37$ |
| Observable frontier | Measure paired-Jacobian information at the highest real frequency |
| Conditional tail | Add bands in steps of six from 37: candidates $M=43,49,\ldots,91$ |
| Final audit | Run on every exit, including numerical failure |

The ordinary path does **not** run an $M=95$ stage: with step 6 from 37 and ceiling 95, the tail stops at 91.

Other important distinctions:

- Default policy damping is the scheduled rule. DP-001 feedback damping is an option.
- Default `required_accuracy` is unset. ON-001's accuracy exit is an option.
- TG-002 is noiseless; noise whitening/discrepancy rules exist but are not thereby validated by TG-002.
- `CumulativePolicy` defaults to 1,800 fit seconds and 300 audit seconds; the ordinary CLI, PC-001 and PC-002 ran under these. The registry's `BENCHMARK_CONTRACT` (120 fit seconds, 30-second audit allowances, 13,412 work units) is **not new**: ON-001, DP-001, RG-001 and CS-001 ran under it (their recorded plans show `fit_seconds=120`). The 26/30 count was obtained under both budgets. A recipe comparison must still state its contract.

## 1.8 Numerical audit versus recovery

The endpoint audit checks all 19 real frequencies using:

- field refinement tolerances of $10^{-5}$ at frequencies up to 0.5 GHz and $10^{-7}$ above;
- normalized Jacobian-column agreement at $10^{-3}$;
- a seeded complete-trial directional finite-difference check at $10^{-3}$.

For ordinary modal runs, this is principally a comparison between resolutions of the **same modal backend**. Independent nodal comparisons occur in separate qualification work; they should not be silently attributed to every endpoint audit.

TG-002 recovery additionally requires:

$$
\mathrm{RMS}\le1\,\mathrm{mm},\qquad
\mathrm{Hausdorff\ upper}\le2\,\mathrm{mm},
$$

and every frequency's relative data residual no larger than

$$
\max(0.003,3\,\mathrm{noise}).
$$

**A numerically qualified wrong boundary is still a failed recovery.**

# Part 2 — What has actually been demonstrated in the current research state?

The status terms below are cumulative, not mutually exclusive:

- **Proposed:** a document or plan exists.
- **Implemented:** source exists and performs the mechanism.
- **Executed:** saved outputs/logs establish a run.
- **Quantitatively tested:** explicit metrics were recorded.
- **Validated:** a specified check passed within its stated scope.
- **Failed:** a specified criterion failed.
- **Superseded:** replaced by a later implementation or contract.
- **Abandoned/retired:** an explicit decision ended its active use.
- **Unresolved:** evidence is incomplete, conflicting, or insufficient.

## 2.1 Current benchmark evidence

TG-002 comprises ten shapes × contrasts 0.5, 4 and 13.3, one centered 65 mm circle start, 24 paired measurements per frequency, and 19 frequencies from 0.25 to 2.5 GHz. Real and damped synthetic catalogs are available. The targets are displaced 22–38 mm from the start center.

The input truth was generated with the CPU nodal reference and qualified through N1024/N2048 comparisons. See [benchmark definition](../../experiments/benchmark/README.md).

| Experiment | Observed result | What it establishes | What it does not establish |
|---|---|---|---|
| **PC-001 M1** | Modal: **26/30**, median total ≈31.39 s | Full recorded modal benchmark result | Exact present-workspace retention |
| **PC-001 N1** | Fixed nodal recipe: **26/30**, median ≈156.68 s | Same recovery count in that campaign | An isolated 5× discretization advantage; recipes/costs differ |
| **PC-001 N0** | **12/12 completed**, then user stopped | Successful partial evidence | A completed 30-case baseline |
| **PC-002** | Fairer nodal+spline comparison: **26/30**, median total ≈100.58 s | A stronger nodal comparator; independent fine-reference audit evidence | Fully matched timing against all earlier modal runs |
| **ON-001 B/E** | **26/30 in both**; median paired successful-output speedup **1.546×** | Accuracy-based early exit retained these recoveries | New recovery or a universal speedup |
| **DP-001 E/F** | **26/30 in both**; all 26 shared successes faster; median **1.134×** | Recorded feedback/reuse recipe retained recovery | Attribution of the gain to one mechanism alone |
| **RG-001** | **26/30 in both**, no new recovery; accepted paths of the 26 retained bitwise; Aphex c4 RMS 1.685→0.664 mm, but its endpoint audit, Hausdorff and field gates failed | Decision-gate relaxation was executed and tested | Resolution-gate changes solving the four failures |
| **CS-001** | Eight-case screen: control **5/8**, revised **4/8** | Four retained recoveries, one regression; shared-success median **1.499×** faster | A successfully promoted new continuation schedule |

Evidence: [PC-001 report](../../results/validation/cleaned_interfaces/PC-001/report.md), [PC-002 summary](../../results/validation/cleaned_interfaces/PC-002/NS/summary.json), [ON-001 results](../iterations/cleaned_interfaces/iteration_31/01_results.md), [DP-001 comparison](../../results/validation/cleaned_interfaces/DP-001/final_comparison.json), [RG-001 report](../../results/validation/cleaned_interfaces/RG-001/report.json), [CS-001 report](../../results/validation/cleaned_interfaces/CS-001/report.json).

The recovery rule was recomputed from every saved `result.json` with stored metrics under PC-001, ON-001, DP-001, CS-001 and RG-001, using its audit flag, RMS, Hausdorff upper bound and per-frequency residual limits. All **334** results (PC-001 72, ON-001 106, DP-001 60, CS-001 16, RG-001 80) agree with their recorded classifications. (The first draft reported 268, from a narrower file selection.) This checked classification consistency. It did not recompute geometry distances or rerun endpoint physics.

**The same four cases fail in every 30-case campaign:** `aphex_twin` at all three contrasts and `hook__c13.3`. This holds for PC-001 M1 (modal) and N1 (nodal Kress), PC-002 (nodal + spline), ON-001 B/E, DP-001 E/F and RG-001. The failures are therefore not specific to the modal discretization or to the spectral geometry update.

### The four failures in DP-001 F

| Case | RMS, mm | Hausdorff upper, mm | Maximum relative residual | Endpoint audit |
|---|---:|---:|---:|---|
| `aphex_twin__c0.5` | 4.475 | 11.964 | 1.310 | Pass |
| `aphex_twin__c4` | 1.685 | 5.146 | 0.760 | Pass |
| `aphex_twin__c13.3` | 2.570 | 10.657 | 1.370 | Fail |
| `hook__c13.3` | 8.653 | 25.140 | 1.629 | Pass |

These are failed recoveries, including three numerically qualified endpoints. All four DP-001 F runs ended with `NUMERICAL_FAILURE` (“candidate leaves the frozen numerical-resolution regime”). Removing that stop has not rescued them. In PC-001 N1, the nodal resolution response promoted all four to N1024/2048, and they still failed with trial wall limits or accuracy-limited trials. RG-001's extended diagnostics gave them 900 s fit budgets; none recovered, and none passed its endpoint audit. This does not prove data nonuniqueness, stationary local minima, or impossibility of recovery.

### Why CS-001 is a failed promotion

CS-001 implemented a genuine alternative:

- exact translation/scale initialization preserving circular shape;
- the existing frequency ladder;
- four compact full-frequency shape stages;
- a configured final full release.

But the C-shape, contrast-13.3 control recovery was lost. The revised run stopped at $M=15,K_g=32$ before taking the next step, with a candidate field discrepancy about $1.128\times10^{-7}$, just above the $10^{-7}$ gate.

Its endpoint geometry was relatively close—RMS ≈0.251 mm and Hausdorff upper ≈0.655 mm—but its maximum data residual was approximately **25.9%**. It therefore failed the actual recovery criterion despite passing its endpoint numerical audit.

None of the screened runs entered the advertised final $M=95$ release. Smaller geometry storage also selected smaller trace systems, so this is not a clean isolation of “better continuation.” Evidence: [CS-001 results](../iterations/CI-SPD/CS-001_results.md).

## 2.2 Newest committed work: kernel validation, not a new recovery campaign

| Work | Status and concrete evidence | Limit |
|---|---|---|
| **AC-001 analytic radial coefficients** | Implemented in the active operator; 24/24 scalar cases and 4/4 highest-frequency matrix/field comparisons passed | No full inverse rerun after this change |
| **AC-001 regression suite** | Saved XML records **628 passed, 46 skipped**, plus five separately passing CUDA tests. It contains test cases from the then-untracked `test_policies.py`, `test_entry_reuse.py` and `test_validity_order.py`, so it ran on a tree that already held the policy work | Historical test execution, not tests rerun in the audit or a complete seal of the dirty tree |
| **AC-001 numerical accuracy** | Maximum reported normalized scalar coefficient discrepancy ≈$6.37\times10^{-13}$; high-precision value discrepancy ≈$2.18\times10^{-13}$; worst final forward matrix comparison ≈$9.07\times10^{-9}$ | Norm-scaled metrics are not uniform absolute-error guarantees for every regime |
| **AC-001 performance** | Analytic scalar construction median ≈1.00 ms versus ≈0.354 ms for the DCT reference | Removing radial sampling did not make this scalar substep faster |
| **AC-002 profile** | Twelve forward evaluations; three fresh/reused pairs on each device; field equivalence and accounting assertions passed | One geometry/frequency configuration, not inverse throughput |

AC-002's representative timings were about **48.35/11.98 ms** for fresh/reused CUDA geometry and **382.18/67.10 ms** on CPU. Those figures must not be presented as 19-frequency or complete-inverse timings.

The AC-001 archive preserves failed intermediate implementations, including small-argument cancellation and damped C-shape matrix-gate failures before the extended-precision construction. The final passing result supersedes those implementations; the failures remain useful evidence.

Sources: [AC-001 evidence](../../results/validation/cleaned_interfaces/AC-001/README.md), [final suite XML](../../results/validation/cleaned_interfaces/AC-001/final-suite.xml), [AC-002 profile](../../results/validation/cleaned_interfaces/AC-002/profile.json).

## 2.3 Policy registry (uncommitted at the freeze, committed in `71087669`): implementation is ahead of evidence

The new registry contains these recipes:

| Recipe | Research status supported by evidence |
|---|---|
| `baseline` | Established algorithm lineage; registry/wiring was uncommitted at the freeze and has no campaign of its own as a registry entry |
| `accuracy_exit` | ON-001 idea quantitatively qualified |
| `feedback` | DP-001 idea quantitatively qualified |
| `decision_gate` | Executed experimental variant; no new recovery |
| `four_phase` | Implemented and executed; CS-001 promotion criterion failed |
| `reach_clip` | Executed screen; rejected |
| `working_frequencies` | Executed screen; rejected |
| `validity_first` | Implemented candidate; acceptance-equivalence claim needs its exact evidence scope retained |
| `entry_reuse` | Implemented candidate |
| `exact_fast` | Combined candidate |
| `compact_release` | Implemented candidate |
| `resolution_response` | Implemented opt-in modal promotion/rejection behavior; unqualified campaign |
| `adaptive_resolution` | Combined compact-storage/resolution candidate; unqualified campaign |

The registry references **`docs/iterations/CI-SPD/PS-001_plan.md`**, but that file is absent. No completed PS-001 result directory was found.

Saved AC-001 test XML includes tests with names corresponding to some pending policy/reuse/validity work. Therefore “never tested at all” would be too strong. What is missing is evidence linking a complete campaign to the **exact current versions and combinations**.

Source: [working-tree policy registry](../../solvers/bem_inverse/policies.py).

# Part 3 — Reconstructed idea history

The following ledger covers the research tracks visible in the repository. A successful diagnostic or suffix continuation is not promoted here into a fresh, general inverse result.

## 3.1 From implicit geometry to explicit boundaries

| Idea/track | What was implemented and executed | Outcome and present status |
|---|---|---|
| **Compressed IBIM / MOD / QBX / kernel-difference variants** | Multiple forward formulations and comparisons; QBX checks on ideal ordered geometries and compressed-cloud cases | Quantitatively tested. Cloud tuning was closed because geometry robustness/cost advantages were not established. Preserved reference history, superseded for the maintained inverse |
| **Ordered-boundary Nyström/Kress** | Ordered curves, singular quadrature and independent controls | Implemented and validated within tested regimes; became the dependable forward/derivative foundation and remains the reference |
| **SDF-to-boundary Methods A/B/C** | Geometry extraction and conversion machinery; Method B smooth Cartesian Fourier contour plus arclength processing | Conversion implementation exists. Its geometry/derivative checks do not establish successful neural inversion |
| **Known-family parameter inverses** | Low-dimensional circle, ellipse and five-lobe controls | Successful bounded controls; known shape families, not free neural geometry |
| **Neural SDF + implicit BEM adjoint + Method-B pullback** | Real neural-weight optimization and branch-local derivatives | Implemented, executed, gradients tested. Recovery failed in the principal recorded neural runs |
| **Neural iteration-3 repair plan** | Detailed proposals and diagnostic reviews | Proposed/agreed historical plan, not executed as a completed new inverse campaign; neural track paused |
| **Radial explicit Fourier inverse** | Explicit shape optimization and later MLP export | Successful shape controls; exporting a fitted boundary to an MLP is not evidence that neural-weight optimization recovered it |
| **Cartesian Fourier representation/gauge** | Non-radial explicit curves, gauge studies and inverse controls | Implemented and tested; this representation lineage survives in the current solver |
| **Joint explicit shape/material estimation** | Small parameterized shape plus material experiments | Eight-arm and fifteen-workflow studies showed strong start dependence; multistart helped the small tested cohort. Not general unknown-material neural inversion |
| **Frozen neural metric on explicit shape directions** | Diagnostics of a neural-induced metric on explicit modes | Diagnostic implementation; not renewed successful neural training |

The neural evidence is especially important. In the long paired/multistatic comparison, both arms terminated without a decreasing admissible neural step. Recorded raw RMS errors were approximately **14.10 mm** and **9.51 mm**; the multistatic arm's lobe amplitude collapsed to about **1.53 mm** against **12.5 mm** truth.

Later reviews cleared the leading “wrong Kress gradient” and “wrong Method-B reverse” explanations on the audited states, apart from identified late branch noise. That leaves optimization/representation/admissibility issues unresolved; it does not validate neural recovery.

Sources: [QBX closeout](../legacy/qbx_closure.md), [known-family controls](../legacy/known_shape_family_controls.md), [implicit-MLP history](../iterations/implicit_mlp/README.md), [radial history](../iterations/radial_fourier_topology/README.md), [Cartesian history](../iterations/cartesian_fourier/README.md), [shape/material pipeline](../pipelines/explicit_radial_shape_material.md).

## 3.2 Topology and event-driven inversion

| Idea/track | Execution evidence | Outcome |
|---|---|---|
| **Explicit birth/death/split/merge machinery** | Event implementations, parity controls and multicomponent inverse runs | Real implemented functionality in the historical topology pipeline |
| **TOP-001–008: candidate allocation and feasibility** | Candidate budgets, refinement checks and feasible finite differences | Some cost/feasibility improvements qualified; not universal topology recovery |
| **TOP-009: capacity gate** | Diagnostic gate tested | Failed its intended criterion |
| **TOP-010: stationarity/restart interpretation** | Further descent measured | Lower loss did not establish geometry recovery; “stopped” was not equivalent to stationary |
| **TOP-011/012** | Tolerance/acquisition investigations | Bounded diagnostic evidence |
| **TOP-013/014/015** | Plans/deferred branches | Deferred or superseded; no completed result should be inferred from numbering |
| **TOP-016–019: staged continuation and qualified pairs** | Saved-state comparisons, two-star and merge tests | Strong local successes, sometimes at higher work cost; suffix evidence is not a fresh-start guarantee |
| **TOP-020/022** | Fresh two-star/direct attempts | Failed recovery |
| **TOP-021** | Conditional follow-up | Not dispatched |
| **TOP-023** | Damping/terminal-model diagnostic | First-step/model improvement qualified; no completed inverse claim |
| **TOP-024** | Bounded damping pair | Neither arm recovered |
| **TOP-025** | Twelve-scene campaign, later compiled campaign | Older campaign **7/12**; later compiled scorecard **8/12** |
| **Field-defined events** | Corridor, contour, opacity and split-seed investigations | Mostly failed or model-blocked diagnostics; no production topology improvement established |

### Material conflict: 7/12 versus 8/12

The topology landing pages emphasize **7/12**, but the later saved compiled scorecard records **8/12**, with all twelve scenes attempted and source revision:

```text
5cb15550a5a146700169de178128914692122473
```

The audit checked both sets of scorecard rows. The later result includes recovery of `far-two-stars`. Its remaining failures are `far-ellipse-star`, `empty-ellipse-star`, `enclosing-ellipse-star`, and `far-three-shapes`.

The later campaign changed implementation and execution/budget settings. The improvement cannot be attributed solely to compilation. Its scorecard also explicitly says `production_promotion: false`.

Sources: [topology history](../iterations/topology/README.md), [older scorecard](../../results/validation/topology/TOP-025-20260915-210356-all-scenes-current/scorecard.json), [later compiled scorecard](../../results/validation/topology/TOP-025-compiled-20260917-115641/scorecard.json), [runtime history](../iterations/speedup/full_inverse_runtime_history.md), [field-defined-event history](../iterations/field_defined_events/README.md).

**Current relevance:** topology machinery is historical/separate. The maintained modal benchmark accepts one boundary and does not invoke these event searches.

## 3.3 Derivatives, reciprocal solves and runtime work

| Idea/track | Recorded result | Disposition |
|---|---|---|
| **BIE-001** | Replaced before its intended run | Superseded by BIE-002 |
| **BIE-002 projected modal diagnostic** | Full-mode reference checks passed; simple useful compression failed; projected approach was ≈3.44× slower | Diagnostic success, compression failure |
| **BIE-004 analytic derivatives** | 1,008 operator checks passed; bounded derivative speedup ≈1.87× | Qualified component; later integrated through runtime work |
| **BIE-006 first-order operator reuse** | Most tested tangent approximations worsened; no useful accepted-path range | Tested and stopped |
| **BIE-003/005** | Deferred plans | Not completed evidence |
| **SPD-001/002** | Analytic Jacobian and whole-inverse comparisons | Qualified bounded speedups; promoted implementation lineage |
| **SPD-004 readiness checks** | Event-specific early-skipping gains | Qualified for tested events, not all event types |
| **SPD-005 reciprocal derivatives** | Multiworker inverse comparisons retained recoveries | Integrated speed improvement |
| **SPD-006/007 compiled scattering** | Sixteen comparisons and default promotion | Implemented/qualified in historical pipeline |
| **SPD-008 exact geometry reuse** | Sixteen comparisons retained paths | Qualified exact-reuse optimization |
| **SPD-010–013** | Frequency threading, CUDA and multiworker work | Implemented and tested under recorded hardware/settings |
| **SPD-014/015** | Geometry pruning/integration | Bounded gains; some evidence starts from saved suffixes |
| **SPD-016 damped integration** | Damped-grid/assembly and bounded inverse comparisons | Transferred into cleaned-interface lineage |
| **SPD-003/009** | Original plans without their own completed campaigns | Do not infer execution from later related implementations |

Sources: [BIE history](../iterations/boundary_bie/README.md), [runtime history](../iterations/speedup/full_inverse_runtime_history.md).

These changes establish real engineering progress. Multiplying their separately reported speedups would be invalid: they use different baselines, cases, phases and overlapping work.

## 3.4 Laurent/modal operators, compression and reduced models

| Idea/track | What happened | Status |
|---|---|---|
| **Native Laurent coefficient Müller solver** | Geometry/logarithm algebra, operator assembly, Graf fields, derivatives and bounded inverses were implemented | Executed and locally validated; historical monomial radial implementation had high-frequency/high-contrast cancellation limits |
| **Local scattering response $T=PA^{-1}B$** | Single-object response, coupled-object equations, pose/shape derivatives and neighbor interactions | Real research implementation and validation; not the current single-boundary inverse |
| **LAU-001 masks/structure** | Corrected gates overturned overly positive early interpretation; noncircle masks failed useful retention targets | Structure observed; useful general compression not established |
| **LAU-002 literature reproduction** | Scalar compression reproduced at high resolution; transmission transfer only partially passed | Literature-regime result, not fast inverse |
| **LAU-003 tangent/frozen ROM** | Only 48/194 anchor derivative checks qualified; frozen transfer/new-illumination tests failed | Negative ROM evidence |
| **LAU-004 protected subspaces** | 42/42 delivered checks after rebuilds; 24 rebuilds needed | Accuracy protected through fallback/rebuilding; no demonstrated useful compression/speed campaign |
| **LAU-005 calibration** | Coupled calibration grids, cross-validation and nonlinear solves executed | Bounded successful calibration work; track explicitly closed |
| **September 18 Fourier–Galerkin study** | Closed-form smooth amplitudes, decay, masks, multi-object response, broadband ROM and transfer experiments | Extensive executed research, with limitations below |
| **MC-001 entry screen** | 12 references qualified; no noncircle 50%-retention mask passed the common forward/derivative gate | Stage B withheld; track explicitly closed |

The September 18 study deserves separation from a mere proposal:

- Its hybrid FFT/Galerkin assembler avoided the older monomial-series ceiling on tested circles, including $kD=60$.
- Geometry analyticity and modal decay were measured, but the useful gradient band grew with electrical size.
- Required retention was roughly **38–63%** in the reported sweep; no improving asymptotic compression payoff was demonstrated.
- The proposed gradient-band rule was corrected from a maximum to an **additive** penalty.
- Multi-object local responses and selective rebuilds agreed with monolithic controls in qualified separation regimes.
- Broadband operator snapshots had rank around 11 at $10^{-6}$, while solution/derivative needs were much larger.
- Held-out affine reconstruction was executed, but required 81–161 training assemblies for stricter targets.
- Preconditioner transfer improved iteration counts locally, yet the dense implementation still assembled the true operator. This was **not** a demonstrated inverse runtime saving.
- Very close-object comparisons with an unconverged reference were explicitly inconclusive.

Sources: [native modal research](../../experiments/modal_muller_research/README.md), [Laurent history](../iterations/laurent/README.md), [September 18 executed study](../../results/experiments/laurent_fgm_20260918/README.md), [MC-001 raw summary](../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/summary.json).

**Current relevance:** coefficient assembly and reciprocal ideas survived; compressed masks, ROMs and multi-object coupling did not become the maintained benchmark algorithm.

## 3.5 Shape/frequency continuation and modal atlases

| Track | Evidence-backed interpretation |
|---|---|
| **SC-001–014: paper/glider reproduction** | Continuation, derivatives and glider experiments ran. A constrained harmonic/trust-region variant recovered the tested glider, but full reproduction of the paper's plotted results across contrasts was not established |
| **SC-015–019: atlas, horizons and adaptive control** | Atlas diagnostics were implemented; controller qualification was incomplete/negative. Diagnostic usefulness did not establish an adaptive policy |
| **SC-020–026: cleaned hybrid and consolidation** | Qualified bounded implementations and trajectory studies; broad atlas-derived band rules remained unreliable |
| **SC-027** | Proposed, not executed |
| **SC-028/029: rough/active-band atlas** | Broad preflight failed; narrowed active-band study ran. Low-band protection had evidence, higher-frequency generality remained unresolved |
| **SC-030–034: optimizer metrics and baseline repair** | Earlier comparison baseline was malformed and later corrected. Hanke/curvature alternatives did not pass intended adoption gates; proposed filtering was not completed |
| **SC-035: state bandwidth and complete-trial derivative** | Important adopted change: lower early storage bands plus derivative of the actual update construction; improved several shapes but worsened star performance |
| **SC-036/037** | Ray-step and wider-storage alternatives tested; mixed outcomes, failed aggregate adoption criteria |
| **SC-038: full-frequency shape release** | Added $M=11,15,19$ releases materially improved tested C/kite endpoints; became part of cumulative lineage |
| **SC-039/040** | Large saved-trajectory/atlas dataset and replay validation; 867 accepted states across 34 trajectories in one dataset |
| **SC-041–043: forecast/adaptive atlas** | Some local release predictions useful; prospective controller failed superiority against fixed/stagnation comparators despite passing numerical audits |
| **SC-042/044: cleanup/noise** | Saved-suffix artifact cleanup tested; fresh/noisy results mixed, often tied. Not a general robust-denoising result |
| **SC-045/046** | Charged-work/audit limits prevented qualification; later interpretation must preserve those failures |
| **SC-047: coupled nonstar shapes** | Local physics/derivatives qualified; object-selection transfer failed false-birth checks |
| **SC-048: global-motion enrichment** | Tested, failed intended transfer gates |
| **SC-049/050: far starts and Mie initialization** | Far-start failure and historical grid-localization successes recorded |
| **SC-051: frequency-only control** | Frequency-only full bands ($M=K=255$ from the first frequency) recovered **0/36** single-object configurations versus 34/36 for the preselected established strategies, with worse RMS in all 41 compared cases; supports the tested need for joint shape release, not a universal theorem |

Far starts and SC-050 grid initialization are now **explicitly retired for new experiments**. They remain because historical seals and evidence reference them. Their existence in code or old success tables does not make them current recommendations.

The old **34/36** continuation headline is also not a clean result of one uniform present-day pipeline; it combines historical development/transfer evidence.

Two different “34/36” figures appear in the repository. Do not merge them:

- **SC-051's 34/36** counts per-case *preselected* established strategies, not one fixed pipeline.
- **CI-001's 34/36** counts geometric recovery. Only **28/36** passed the full frozen contract; seven noisy cases failed the residual gate (§3.6).

Source: [SC history and result index](../iterations/shape_frequency_continuation/README.md), [legacy benchmark policy](../../experiments/benchmark/LEGACY.md).

### Modal-atlas line

| Track | What is supported |
|---|---|
| **MA-001 / reproduction** | Wave-pair identity and circle/BIE checks; trace-frontier diagnostics. One sharp-kite state failed numerical qualification and was excluded |
| **Resonance interpretation** | High-contrast circle mechanism partly supported; the proposed contrast-0.5 resonance explanation was not supported |
| **MA-002/003** | Frozen high-contrast and band-only interventions failed to resolve the relevant basins |
| **MA-004** | Damped localization/prefix repaired 2 of the 4 MA-002 failures and kept all 8 earlier recoveries. Gate G1 required 3 repairs, so it failed and transfer was withheld |
| **MA-005** | Damping plus shape-frontier release gave strong bounded transfer/fresh results; original hard C-shape case remained unsolved |
| **MA-006** | Operator atlas executed; 9/10 cells qualified. Relative to projection, reduced solves needed a larger tested cutoff in 1/9 data/Jacobian cells and 3/9 local-update cells; exact Schur elimination restored the reference. It is a projected-Nyström control ($P=12$): no deployed adaptive cutoff and no inverse speed-up |

These studies helped form the cumulative policy. They did not produce a validated automatic modal-compression or adaptive-resolution controller.

Source: [modal-atlas history](../iterations/modal_atlas/README.md).

## 3.6 Cleaned inverse, spectral updates and node-free claims

| Track | Concrete outcome | Status |
|---|---|---|
| **CI-001 cleaned nodal campaign** | Old 36-case campaign: 28/36 passed all recovery gates; geometric closeness alone reached a different, higher count | Completed; do not substitute geometry-only 34/36 for full recovery |
| **Initial modal CI-001 campaign** | 19/36 initially recovered | Executed failure relative to intended retention |
| **Scaled Graf/finer-profile repairs** | Affected-case reruns improved results; seven of nine affected cases matched expectations | Bounded repair evidence; not a new complete all-36 campaign |
| **NU-001 coefficient-normal update** | Low retention and drift | Tested and rejected |
| **NU-002 reset experiments** | Representation/reset diagnostics | No complete inverse success claim |
| **NU-003 spline-free centered update** | Six of six retained; slower in that comparison | Qualified geometry alternative |
| **NU-004 modal + spectral** | Six of six retained; roughly 2× bounded nodal comparison | Qualified subset |
| **NU-005 geometric certificates** | 1,131 checks without fallback in the recorded set; six cases retained; additional cost | Bounded qualification, not universal certificate coverage |
| **NU-006 batched GPU preparation** | Preparation ≈150→3.9 s; whole comparison ≈390→242 s; six retained | Adopted speed improvement |
| **NU-007 GPU certificate** | Decisions matched, but the specified relative-bound gate failed | Failed original criterion |
| **NU-007a revised qualification** | Threshold-scaled qualification passed; bounded wall-time improvement | Separate later accepted result |
| **NF-001 review / analytic tangent option** | Sampling/derivative claims reviewed; analytic discrete geometry tangent made selectable | Does not change the ordinary default to fully analytic geometry differentiation |
| **GC-001 spline/spectral replay** | 279 proposed moves; 278 reference-qualified, one unresolved; agreement across qualified decisions | Geometry-only result, no inverse or physics calls |

GC-001 showed that output-grid aliasing was a dominant discrepancy source in its replay, and that GPU batched spectral preparation could be substantially faster. It did **not** test a GPU spline implementation or prove that every geometry certificate can be skipped.

Sources: [cleaned-interface history](../iterations/cleaned_interfaces/README.md), [CI-001 summary](../../results/validation/cleaned_interfaces/CI-001-campaign-review/summary.json), [modal repair summary](../../results/validation/cleaned_interfaces/modal-muller-fixes-20261001/rerun_summary.json), [GC-001 evidence](../../results/validation/cleaned_interfaces/GC-001/README.md).

## 3.7 Relaxed BIE, acquisition changes and initialization censuses

| Track | Execution and outcome | Interpretation |
|---|---|---|
| **FM-001 full matrix / relaxed BIE** | Full-matrix C-shape recovery where a paired run failed; initial relaxed gradient was incomplete | Acquisition finding is local; initial gradient results cannot be treated as a fair relaxed-method test |
| **FM-002 gradient repair** | Full reduced-loss gradient included missing terms and passed checks; recovery counts unchanged with/without relaxation in the tested arms | Corrected implementation; no added recovery benefit demonstrated |
| **RB-001 nodal resolution response** | Four archived tails had removable resolution stops; both budget settings still recovered 0/4 | Numerical obstruction removed in those tails, recovery not solved |
| **FM-003 initialization census** | 512 starts and endpoint follow-ups; a selected paired C-shape contrast-13.3 endpoint recovered | Evidence against “paired data makes this target impossible”; retrospective search evidence |
| **FM-004 selected endpoints** | 4/11 recovered | Bounded, selection-dependent transfer |
| **FM-005 resolution promotion** | 7/11 recovered; four earlier recoveries retained | Further bounded success; not a blind fresh benchmark |
| **FM-006** | Proposed follow-up | No completed campaign evidence found |

Sources: [FM-002](../../results/validation/cleaned_interfaces/FM-002/summary.json), [FM-003](../../results/validation/cleaned_interfaces/FM-003/phase4/summary.json), [FM-004](../../results/validation/cleaned_interfaces/FM-004/summary.json), [FM-005](../../results/validation/cleaned_interfaces/FM-005/summary.json).

## 3.8 Cross-domain and external-data exploration

These were actual implementations or experiments, but are separate from current TG-002 recovery claims.

| Direction | Recorded work | Scope limit |
|---|---|---|
| **Sensitivity/null-space atlas** | Hundreds of spectra and finite-path comparisons | Linear near-null structure did not establish global nonuniqueness; some finite changes badly violated the local model |
| **Fresnel experimental data** | Real-data fits and incident-field calibration | Restricted shapes and acquisition mismatch; not current all-shape validation |
| **TE / passive-loss physics** | Forward and derivative checks, loss atlas | Qualified local extension; current default remains the stated scalar equal-density model |
| **LSM/full-matrix initialization** | Additional full-matrix data and controller jobs | Same 5/12 outcome in the compared jobs; uses additional observations, not the paired-information contract |
| **Alternative frequency schedules** | RLA/SCIF/fixed-band studies | Some recovery differences, but not a fair replacement comparison against the maintained cumulative method |
| **Time-domain comparison** | 512-frequency reconstruction and FDTD comparisons; reported sub-percent forward error | Forward cross-validation, not a time-domain inverse |
| **Sommerfeld half-space** | Single buried-object forward implementation | Not a qualified layered-media inverse |
| **3-D scalar IBIM sphere** | Sphere forward controls with significant dense-memory cost | Not arbitrary-surface Maxwell inversion |
| **Algoim/neural implicit quadrature** | SIREN geometry quadrature and continuum derivative checks | Not differentiation through the entire adaptive algorithm, nor successful neural inverse recovery |
| **Streamed endpoint audit** | Bit-identical comparison with a substantial memory reduction in the tested setup | Real integrated engineering result |
| **Stopping-floor exploration** | Continued descent measured; work stopped after scope change | No final recovery or stationarity conclusion |
| **Support certificates / passivity / operator ROM** | Isolated September exploration and tests | Conditional finite-model certificates and mixed/negative ROM evidence; not global continuum guarantees |

Sources: [October 2 exploration report](exploration_2026-10-02.md), [September exploration](../iterations/boundary_bie/iteration_05/01_exploration.md), and the corresponding experiment/result directories listed in the freeze.

## 3.9 Theory-radius and continuation guarantees

| Idea | Evidence | Status |
|---|---|---|
| **T1 / TR-001 empirical local radius** | Forty numerically qualified rows and 936 extra probes. None of the 911 resolved probes violated the tangential-cone condition (maximum ratio 0.32 against 1/2). The 22 apparent violations were all among the 25 unresolved probes and are numerical-floor effects; eight weakest singular values were also unresolved. For the contrast-13.3 C, damping enlarged the empirical radius about 41× (0.0088→0.36 mm) | Executed empirical study supporting a nonlinearity explanation of the damping benefit near truth; not a certified Lipschitz radius or convergence theorem |
| **T2 / TR-002 certified handoff rule** | 24 handoffs; 17 outside the stated applicability conditions; none of seven applicable cases passed the desired inequality | Failed useful certification criterion |
| **TR-003 branch/homotopy work** | Later numerical branch qualifications exist; earlier completion/adapter validation failed | Mixed evidence; failed completion guard must remain visible |
| **Complex-frequency damping** | Implemented and used | Real geometry with complex $k$ |
| **S2 complexified geometry continuation** | Proposed | Not implemented by merely storing $x+iy$ Fourier coordinates |
| **Carleman convexification, monotonicity, optimal transport, inverse Born, stronger Bayesian guarantees** | Theory directions in documents | No corresponding maintained inverse implementation or completed validation found |
| **Neural PL*/ReLU uniqueness framing** | Considered then identified as mismatched to the explicit-boundary problem | Not a current established theoretical foundation |

Sources: [theory directions](../theory_directions_cartesian_fourier_2026-10-03.md), [theory-radius history](../iterations/theory_radius/README.md).

Literature-priority and novelty statements in these documents were not independently verified against external literature in this repository audit.

## 3.10 GauGal comparison and recent alternative solvers

| Track | Actual evidence | Status |
|---|---|---|
| **GGB-001 comparison** | Three eligible cylinder examples, different acquisition/noise/parameterization contracts; very fast GauGal runs compared with an unsuccessful slow BEM example | Executed comparison, not general method parity |
| **GGB-002** | Single-/four-frequency BEM alternatives failed recovery; four-frequency run encountered numerical failure | Negative bounded result; not proof that frequencies cannot help |
| **GGB-003 translation + shape** | Arm-to-arm comparison, not one run improving: the translation arm T ended 1.40 mm from the true centre, versus 458.58 mm for baseline arm B. Both arms ended in `NUMERICAL_FAILURE`. T's residuals stayed at 13.5–16.2% against a 5.5% noise target, and T took 297.7 s versus 4.4 s | Localization success, failed full recovery |
| **GGB-004 translation + radius** | 43 updates, ≈3.70 s; center error ≈0.20 mm; pixel metric looked exact | Fitted 0.75/1.0/1.25 GHz residuals (5.6–6.6%) missed the ≈5.5% noise targets; circle-only result |
| **GGB-005 single-frequency translation + radius** | 30 updates, ≈1.32 s; centre error ≈0.10 mm; fitted 0.5 GHz residual 5.20% met its 5.50% noise target | 0.75–1.25 GHz holdouts (5.6–6.6%) missed theirs; not general shape recovery |
| **ON-002 GauGal adapter** | Rescaling/double-precision/resumed qualifications; 0/25 required solve gates | `ADAPTER_INCOMPLETE`; inverse/hybrid/all-30 work unrun |
| **GS-001 native TV** | Twelve updates; ≈30.2% residual; stall | Executed failure preserved |
| **GS-001 repaired TV** | 202 updates to wall cap; ≈0.461% single-frequency residual, IoU ≈0.331, sampled RMS ≈28.1 mm | Data fit improved, geometry recovery failed; still above TG-002's 0.3% data threshold |
| **ON-003 Ewald route** | Circle/splitting/diagonal qualification grids failed required accuracy | Accuracy/resource-limited; full fields/derivatives/inverse unrun |
| **EW-001 follow-up** | Smaller splitting parameters still failed; contraction-cost bound unfavorable | Tested and closed |
| **GN-001 lean LM** | Proposal to remove checks/work | Not implemented as the current default |
| **GPU spline port** | Proposed comparison | No executed GPU-spline inverse evidence |
| **GP-001 hybrid** | Proposed | No completed campaign evidence |

Sources: [GGB-002](../../results/validation/cleaned_interfaces/GGB-002/report.md), [GGB-003](../../results/validation/cleaned_interfaces/GGB-003/report.md), [GGB-004](../../results/validation/cleaned_interfaces/GGB-004/report.md), [GGB-005](../../results/validation/cleaned_interfaces/GGB-005/report.md), [ON-002 evidence](../../results/validation/cleaned_interfaces/ON-002/resume128_double/summary.json), [GS-001 results](../iterations/CI-SPD/GS-001_results.md), [ON-003](../../results/validation/cleaned_interfaces/ON-003/summary.json), [EW-001](../../results/validation/cleaned_interfaces/EW-001/summary.json).

# Part 4 — Conflicts and claims that need qualification

| Tempting statement | Evidence-backed correction |
|---|---|
| “The project is currently a neural SDF inverse.” | The maintained benchmark optimizes explicit Fourier boundaries. Neural inversion is a separate paused lineage with failed principal recovery runs |
| “The repo is on ordered-boundary-nystrom.” | Actual checkout is shape-frequency-continuation, 446 commits beyond that branch tip |
| “HEAD reproduces the current workspace.” | At the freeze it did not: twenty modified/untracked paths included executable policy changes. Since 2026-10-06 they are committed in `71087669` |
| “The current code has recovered 26/30.” | Recorded earlier campaign versions did. New kernel work (AC-001) and the policy variants lack a matching complete campaign on `71087669` |
| “The four failures are a modal-discretization artefact.” | The identical four cases fail with nodal Kress too (PC-001 N1, including promotion to N1024/2048, and PC-002 nodal + spline) |
| “Topology recovered 7/12.” | True of the older scorecard; a later compiled scorecard records 8/12 under changed settings |
| “Node-free means the inverse has no sampling.” | Operator construction is coefficient-based, but geometry projection, validity preparation/fallback and FD qualification use sampling |
| “The geometry certificate in the September PDF proves correctness.” | Independent counterexamples refuted the proposed finite-section/RMS certificates. Current code uses a different, stronger residual construction with stated numerical limits |
| “The Jacobian is exactly AD through the solver.” | Default physics uses a reciprocal shape formula; default complete-trial geometry velocities use centered differences |
| “Modal compression was validated.” | Modal structure and some literature-regime results were validated; useful common field/derivative compression failed the MC-001 entry gate |
| “The adaptive atlas was successful.” | Diagnostic atlases were useful; prospective adaptive control failed its superiority criteria |
| “A small residual means the shape was recovered.” | GS-001 is a direct counterexample. TG-002 correctly requires geometry and numerical gates too |
| “Passing the endpoint audit means successful inversion.” | Three DP-001 failures passed numerical audit |
| “Four-phase continuation was adopted successfully.” | CS-001 lost one control recovery; its final full-release stage was never reached in the screen |
| “Modal resolution response does not exist.” | True at HEAD `3d3ed16a` (the `pipelines.py` docstring and error said so); stale relative to the dirty tree. `modal_response` is implemented and committed in `71087669`, but remains unqualified |
| “PS-001 is a registered/completed screen.” | The registry refers to a missing plan; no completed screen evidence was found |
| “The modal method is five times faster than nodal.” | Some historical totals have that ratio, but PC-002 shows why recipe, audit, geometry and execution settings must be matched |
| “Analytic radial coefficients made the method faster.” | They removed radial sampling; the measured scalar construction was slower, and no whole-inverse speed gain was demonstrated |
| “The four failures are local minima or nonidentifiable.” | Their recorded numerical stops and data/geometry failures do not establish either conclusion |

The strongest mathematical-document conflict is documented in the [independent node-free review](../iterations/cleaned_interfaces/node_free_modal_muller_review.md): a finite compressed positivity test can pass despite a self-intersecting curve, and an RMS/Parseval check does not provide a uniform geometric bound. Those are substantive counterexamples, not stylistic disagreements.

# Part 5 — Statements supported for the supervisor meeting

The following wording stays within the evidence:

> We have a maintained two-dimensional, known-material, single-boundary inverse solver using explicit Cartesian Fourier geometry and modal Müller boundary-integral physics. It uses reciprocal shape sensitivities, a normal/spectral geometry update, and staged shape-frequency continuation with numerical acceptance and endpoint checks.

> On the frozen noiseless TG-002 benchmark—ten shapes at three contrasts, one centered start, 24 paired measurements at 19 frequencies—the recorded modal campaigns recover 26 of 30 cases. Accuracy-based stopping and a later feedback/reuse recipe retained those recoveries and reduced measured runtime under their recorded contracts. The same four cases (the Aphex Twin shape at all three contrasts and the hook at contrast 13.3) fail in every 30-case campaign, with both modal and nodal physics.

> We have extensive forward, derivative and geometry validation, including independent nodal controls. The newest analytic radial-coefficient implementation passed component and regression tests, but has not yet been shown to retain the complete benchmark on the current code.

> Several major ideas were investigated and did not meet their intended goals: the principal neural-SDF inverse runs, useful modal compression for the inverse, broad atlas-driven control, the latest four-phase continuation promotion, and current GauGal-adapter parity. Other successful diagnostics—topology suffixes, multi-object response reuse, localization, and low-rank operator snapshots—have narrower scope than a general inverse result.

The evidence does **not** currently support a global convergence guarantee, general noisy-data robustness, arbitrary topology recovery, end-to-end sample-free certification, or validated superiority over GauGal.

# Part 6 — Existing unresolved directions recorded in project material

These are existing open items, not new research proposals, and no work on them was performed in the audit.

| Existing item | Frozen status |
|---|---|
| Modal resolution response / RP-001 lineage | Implemented as `modal_response` (dirty tree at the freeze, committed in `71087669`); campaign qualification absent |
| PS-001 policy comparison | Screen code exists; referenced preregistration is missing; no completed results |
| Exact stage-entry reuse and validity-order changes | Implemented with test-related evidence; exact current combined campaign behavior unresolved |
| Blind transfer of selected initialization/resolution successes | FM-006-style follow-up remains distinct from retrospective FM-003–005 selections |
| GauGal adapter/hybrid comparison | ON-002 qualification incomplete; GS-001 does not establish parity or shape recovery |
| GPU spline comparison | Proposal remains unexecuted |
| Formal continuation/certificate claims | Empirical radius work exists; useful global or handoff guarantees remain unestablished |
| Neural iteration-3 recovery repair | Historical paused plan; no completed execution |
| Multi-object response and broadband preconditioner deployment | Research implementations exist; maintained-inverse integration and end-to-end benefit remain unestablished |

**Repository preservation during the October 5 audit:** no scientific code, documents, results, branches, worktrees or Git history were changed. No cleanup, commit, push, experiment, or numerical test run was performed during that audit.

# Save and commit validation — 2026-10-06

The user subsequently requested that this report be saved, followed by committing
and pushing the workspace. The October 5 snapshot above remains historical.

Pre-commit validation covered `pytest/bem_inverse`, `experiments/benchmark`,
`experiments/cleaned_interface`, `experiments/shape_continuation`,
`pytest/gpr_bem_kress`, and `pytest/ordered_boundary`. The initial run recorded
**748 passed and one failed in 223.87 seconds**. The only failure was a stale
expected error-message regex in
`test_benchmark.py::test_run_refuses_mixed_method_selection`: the implementation
correctly raised `ValueError`, with the new policy-aware wording.

Only that expected message was updated. Both affected benchmark test files were
rerun: **31 passed in 0.97 seconds**. The initial failure and follow-up output are
preserved in the [validation transcript](research_freeze_2026-10-05_validation.txt).
All 89 evidence links in the audit resolved before saving this receipt, and
`git diff --check` passed. Source hashes confirmed that saving and validating the
report introduced no scientific implementation changes. The pre-existing policy
work is preserved in the requested commit; its campaign-qualification limitations
remain as recorded above. No new benchmark campaign was run.

# Appendix A — Fact-check log (2026-10-06)

A second pass re-derived the claims above from primary sources: source code (identical at `71087669` to the audited dirty tree for all scientific files), saved `result.json`/`plan.json`/XML records, and Git. Iteration result documents served only where no raw record exists. Landing pages and summaries were not treated as evidence. Corrections are applied in place above.

## Corrections

| Section | First draft | Corrected to | Primary evidence |
|---|---|---|---|
| §1.7 | The 120 s / 30 s benchmark contract was described as *new* | It is the contract ON-001, DP-001, RG-001 and CS-001 ran under. PC-001/PC-002 used the 1,800 s / 300 s defaults. The 26/30 count holds under both | `fit_seconds` in each campaign's `plan.json`; `BENCHMARK_CONTRACT` comment in `policies.py` |
| §1.7 | Ladder bands “approximately 3, 5, 7, 9”; tail “up to the configured ceiling” | Exact $M$, $K_g$ and $K_t$ per stage; tail candidates 43–91, never 95 | DP-001 `plan.json`; `CumulativePolicy.operations/tail` |
| §2.1 | “268 saved recovery classifications” | 334 results, all consistent | All `result.json` with metrics under PC-001, ON-001, DP-001, CS-001, RG-001 |
| §3.5 MA-004 | “failed two of four adoption gates” | Repaired 2 of 4 failures; G1 needed 3, so G1 failed; 8 earlier recoveries kept | `modal_atlas/iteration_05/01_results.md` |
| §3.5 MA-006 | “reduced solves failed most requirements” | 9/10 cells qualified; a larger cutoff was needed in only 1/9 and 3/9 cells | `modal_atlas/iteration_07/01_results.md` |
| §3.9 TR-001 | “some tangential-cone violations” | No resolved probe violated the condition; apparent violations were unresolved numerical-floor probes | `theory_radius/iteration_02/01_results.md` |
| §3.10 GGB-003 | “Center error fell ≈458.6→1.4 mm” (reads as one run improving) | Endpoints of two different arms (B 458.58 mm, T 1.40 mm); both ended in `NUMERICAL_FAILURE` | `GGB-003/report.md` |
| §3.10 GGB-004/005 | Residual outcomes stated qualitatively | Residual versus noise target per frequency | `CI-SPD/GGB-004_results.md`, `GGB-005_results.md` |

## Additions

- The identical four-case failure set across every 30-case campaign, modal and nodal (§2.1, Part 4, Part 5).
- Nodal promotion to N1024/2048 (PC-001 N1) and 900 s budgets (RG-001 extended) did not rescue those four (§2.1).
- The AC-001 suite already collected the then-untracked policy test modules (§2.2).
- The two distinct “34/36” figures, and SC-051's 0/36 frequency-only result (§3.5).
- The post-freeze reference commit `71087669`, with stale “dirty tree / uncommitted” wording updated where it describes the present (header, §0.1, §2.3, Parts 4–6).

## Verified as written (selection)

- **Part 0:** branch, HEAD and date; the 12 modified + 8 untracked files; branch tips; 446/558 commit counts; tag and stash; TG-002 manifest SHA-256; Markdown/result census counts.
- **Part 1:** every cited function at its cited location; CLI and `runner.fit` defaults; modal input requirements; Müller block structure with Maue form; six radial functions; the $K_t$ formula and $B=K_t+64$, matching recorded plans; SciPy LU and CPU Graf/Jacobian work; `device=auto` semantics; Jacobian factor $2\pi(k_i^2-k_o^2)$; $10^{-7}$ m centered geometry differences; audit tolerances (field $10^{-5}/10^{-7}$, Jacobian $10^{-3}$, FD $10^{-3}$, seed 42001); recovery gates.
- **Part 2:**
  - PC-001: M1 26/30, 31.39 s; N1 26/30, 156.68 s; N0 stopped by the user at 12/12.
  - PC-002 26/30, 100.58 s; ON-001 1.546×; DP-001 1.134× with all 26 faster; RG-001 26/30.
  - CS-001: 5/8 vs 4/8; C-shape stop at M15/K32 at $1.1278\times10^{-7}$; RMS 0.251 mm, Hausdorff 0.655 mm, residual 25.9%; no case reached M95.
  - DP-001 F failure table.
  - AC-001: 24/24 and 4/4; 628 passed, 46 skipped, plus 5 CUDA; error metrics; 1.00 vs 0.354 ms; no inverse rerun.
  - AC-002 timings; registry contents; absent PS-001 plan and results.
- **Part 3, checked against result records:**
  - Neural: RMS 14.10/9.51 mm; lobe 1.53 vs 12.5 mm.
  - Topology: TOP-025 7/12 vs 8/12 (rows, source revision, failures, `production_promotion: false`); TOP-009/020/021/022/024 dispositions.
  - BIE: BIE-001/002/004/006 (3.44×, 1,008 checks, 1.87×).
  - Laurent and compression: LAU-003/004 (48/194; 42/42 with 24 rebuilds); September 18 study (kD = 60 Mie check, retention 0.38–0.63, additive penalty, rank 11, 81/161 assemblies); MC-001.
  - Continuation and atlases: SC-038/039/043/047–050; MA-001 kite exclusion and resonance finding; MA-005.
  - Cleaned interface: CI-001 28/36 (34/36 geometric); modal 19/36; 7/9 repairs; NU-001–NU-007a; GC-001 278/279.
  - Relaxed BIE and initialization: FM-002–FM-006; RB-001 0/4.
  - Theory radius: TR-001/002 counts.
  - GauGal and alternatives: GGB-004/005; ON-002 0/25; ON-003; EW-001; GS-001 (12 → 202 updates, 30.2% → 0.461%, IoU 0.331, RMS 28.1 mm).
  - Exploration: LSM 5/12; streamed audit bitwise identical.

## Not independently re-verified

- The census fingerprint `9db28a1f…` (its serialization was not recorded; file counts are consistent).
- Individual rows for SC-001–037, TOP-001–008/011–019/023, SPD-001–016 beyond the runtime-history table, LAU-001/002/005, and the §3.8 exploration rows other than LSM and streamed audit.
- Document-level theory claims in §3.9, and every literature-priority or novelty statement.
