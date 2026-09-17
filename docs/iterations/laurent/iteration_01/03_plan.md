# Iteration 01 plan — LAU-001, derivative-preserving compression of the native Laurent Müller operator

Consolidates the [received brief](02_proposals/01_modal_derivative_compression_tests.md)
and [its review](02_proposals/02_review.md). Where the two differ, the review's
resolutions (R1–R19) govern; everything else is the brief, unchanged.

---

## LAU-001 — does the native Laurent operator's desingularised remainder compress without destroying geometry derivatives?

- **Approval status:** `APPROVED` — by the user on 2026-09-17, in this session,
  with "go", immediately after being told `LAU-001` was still unapproved. Scope
  and budget are this plan as written, with the amendments recorded below.
- **Execution status:** `COMPLETE` — 2026-09-17. Verdict **`STRUCTURE_ONLY`**.
  Artifacts: [`results/validation/laurent/LAU-001-20260917-modal-derivative-compression/`](../../../../results/validation/laurent/LAU-001-20260917-modal-derivative-compression/README.md).
  Results open [iteration 02](../iteration_02/01_results.md).
- **Owner:** Claude. **Reviewer:** `unassigned` (self-review only unless one is
  assigned before closeout).
- **Question.** At a qualified trace resolution, does a modest set of retained
  couplings of the **node-free Laurent Müller operator** — after removing its
  exact identity and log-symbol contributions — preserve the full transmission
  solution, the receiver predictions, and the derivative of the actual
  approximate forward model, on noncircular geometries?
- **Falsifiable hypothesis.** Protecting the verified singular part and
  selecting couplings from forward **and** directional-derivative information
  meets all four numerical gates at ≤30% remainder retention on both
  noncircular fixtures. It is wrong if retention above ~50% is needed at
  moderate electrical size, if derivatives fail while fields pass, or if
  retention rises sharply when the trace dimension doubles.
- **Baseline.** [B0 — 2026-09-10](../../../baselines/B0_2026-09-10.md), commit
  `345038a`; current branch `feature/ordered-boundary-nystrom`. Numerical
  references: the qualified nodal Kress oracle at `N = 256/384`, and the
  current nodal reciprocal/compiled path for every cost comparison. The retired
  nodal operator-derivative arm is a historical control only.
- **Intervention.** Change only **which couplings of a fixed modal operator are
  retained** (arms `FULL/BAND/FORWARD/DERIVATIVE_AWARE/ANALYTIC_SUPPORT`), and,
  in the one separately labelled arm `COEFFICIENT_WINDOW`, the declared
  coefficient budget `(B, terms)`. Geometry, trace bandwidth, physical
  frequency, materials, acquisition, observations and solver tolerances are
  fixed within every paired comparison.
- **Controls.** Independently refined nodal Kress; the uncompressed native
  operator at identical `K_u`; the projected-Nyström operator `A_M^proj` at the
  identical `K_u` (BIE-002's object, retained as the equivalence control); the
  full-mode square DFT coordinate change; forward-only masks; BIE-002's centered
  band; and the existing reciprocal/Hadamard derivative where it qualifies.
- **Scope and shared interfaces.** New code lives only in
  `experiments/laurent_compression/`. `solvers/` and
  `experiments/modal_muller_research/` are **read-only imports**; no runtime
  patching of private implementations. No production default changes. No
  topology, MLP, material inversion, new physical model, replacement singular
  quadrature, new assembler, geometry–frequency surrogate, reduced basis or
  optimizer change.
- **Compute budget and stopping rules.** §7 below. Hard ceilings: 45 min
  numerical wall time, 8 GiB peak RSS, ≤500 full physical assemblies,
  ≤1200 factorisations, ≤2500 RHS batches. Stop early on broken equivalence,
  inconsistent derivatives, source drift or instability.
- **Artifacts.** §8 below, in a fresh directory under
  `results/validation/laurent/`.
- **Decision criteria.** The five verdicts in §6.

---

## 1. What is being compressed, precisely

Every nonidentity block of the native operator is built by `kernel_matrix`
(`experiments/modal_muller_research/coefficient_operator.py:87`) as

```text
block[m,n] = 2π ( smooth[m,−n]  +  Σ_ℓ L_ℓ · P[m−ℓ, ℓ−n] ),   L_ℓ = −1/|ℓ|,  L_0 = 0
```

so the decomposition `A_M = S_M + R_M`, `Ã_M = S_M + Π_𝒮 R_M` is available in
two explicitly labelled forms:

| Label | Protected `S_M` | Remainder `R_M` (the candidate pool) |
|---|---|---|
| `IDENTITY_ONLY` | the exact `I` blocks only | log-symbol convolution **and** smooth lookup, every block |
| `VERIFIED_SINGULAR_SPLIT` | the `I` blocks **plus** the exact log-symbol convolution of every block | the smooth polynomial lookup `2π·smooth[m,−n]` |

**Amendment, 2026-09-17 (execution).** An earlier draft put the Maue term
`−m·n·V` in `IDENTITY_ONLY`'s protected part. It is not an independent additive
term — it is a mode-index reweighting of `V`, which also appears unweighted in
the `(1,2)` block. Protecting one occurrence while compressing the other would
make the two inconsistent. The Maue term therefore inherits `V`'s own split:
`−m·n·V_log` goes with the log part, `−m·n·V_smooth` with the smooth part.

`𝒮` carries **block labels** as well as `(m,n)`; it retains interactions, not
trace unknowns. `M = 2K_u+1` is held fixed across all masks in a paired test.
Exact identity terms are excluded from the candidate pool but counted in total
storage and work. Hermitian symmetry is **not** assumed and conjugate-symmetric
masks are not enforced.

Both labels run. A failure of `IDENTITY_ONLY` does not disprove compression
after a genuinely different split; a success obtained by protecting a large
dense `S_M` is not a saving unless its cost is counted.

## 2. Implementation

An isolated package; prefer reuse over duplication in every module.

```text
experiments/laurent_compression/
    __init__.py
    adapters.py       read-only wrappers over the existing solvers
    structure.py      predicted vs measured support (gate G1b)
    masks.py          the six retention rules
    metrics.py        errors, residuals, retention and the cost ledger
    run_screen.py     pilot / campaign stages, dry-run estimate, checkpoints
    test_algebra.py
    test_derivatives.py
```

**`adapters.py`** — the only module that touches existing code.

| Function | Wraps | Contract |
|---|---|---|
| `native_blocks(geometry, ko, ki, K_u, B, terms)` | `CoefficientGeometry`, `kernel_matrix` | Returns `identity`, `log_part`, `smooth_part` per block by linearity of `kernel_matrix` (call it once with zero smooth array, once with zero `P` array). **Asserts** the three sum to `CoefficientGeometry.assemble` bit-for-bit up to declared roundoff |
| `native_derivative(prepared, direction, …)` | `prepare_direction`, `ShapeOperator.derivative` | Analytic `D_v A`, split identically. `D_v I = 0` is exact |
| `native_acquisition(…)` | `FixedAcquisition`, `ShapeFields.maps` | `b`, `C`, and `D_v b`, `D_v C` in native coefficients |
| `projected_blocks(curves, frequency, acquisition, K_u)` | `probe.assemble`, `modal.ModalSystem.from_nodal` | The `A_M^proj` control. Records the DFT normalisation in force (`norm='ortho'`, unitary) and converts RHS/receivers/derivatives consistently. Reuses `ModalSystem.solve`'s lifted-residual definition |
| `nodal_reference(curves, frequency, acquisition, N)` | existing Kress builders | The refined oracle at `N = 256/384` |

Do not multiply an assembled Nyström matrix by a second quadrature-weight
matrix; do not apply `S_q` twice if the solver already carries `q`.

**Import rule.** `adapters.py` is the *only* module in this package that may
import `modal_muller_research`, and it imports **library modules only**
(`coefficient_operator`, `coefficient_fields`, `coefficient_derivative`,
`modal`). It must not import `run_*`, `plot_*` or `probe`. Three existing
outside packages already depend on `run_native.nodal` and `probe.assemble`;
that accidental interface is recorded in
[the package README](../../../../experiments/modal_muller_research/README.md)
and this experiment does not add a fourth. `experiments/modal_muller_research/`
is **read-only and hash-pinned**: 11 recorded bundles hash its files as their
measured source state, so nothing there is renamed, moved, reformatted or
deduplicated by this experiment.

**`structure.py`** — `effective_bessel_order(ko, ki, scale, terms, floor)`
returns the smallest `p*` whose series weight falls below the declared floor;
`predicted_support(K_γ, p*, B, K_u)` returns the hypothesised exact support
(log band `|m−n| ≤ 2β`, smooth box `|m|,|n| ≤ β`, with `β = min(B, K_γ·p*)`);
`measured_support(blocks, floor)` returns the observed one. Both are reported
per block, per fixture, per frequency.

**`masks.py`** — six rules, deterministic ties, per-block allocation (never a
flattened matrix where the largest-unit block wins):

| Arm | Rule | Role |
|---|---|---|
| `FULL` | no coupling truncation | same-`M` accuracy control |
| `BAND` | BIE-002's centered band at its recorded widths | negative/control arm; reuse widths, do not search |
| `FORWARD` | magnitude retention from `R` only | is derivative information needed? |
| `DERIVATIVE_AWARE` | one common mask scored from `R` and training `D_v R` | main candidate |
| `ANALYTIC_SUPPORT` | the predicted support of `structure.py`; no thresholding | the Laurent-specific arm the others must beat |
| `COEFFICIENT_WINDOW` | reduce `(B, terms)` and reassemble | the only arm that changes real assembly work |

The derivative-aware score is the brief's, unchanged:

```text
s_mn^(b) = max{ |R_mn^(b)| / s_R^(b) ,  max_{v ∈ V_train} |(D_v R^(b))_mn| / s_{D,v}^(b) }
```

with block Frobenius norms and declared reference-noise-based floors, physically
normalised directions, and the same retained fraction in each nontrivial block
before ranking. `FORWARD` is the ablation with identical normalisation,
accounting and tie-breaking. Any additional protected rows or couplings are
recorded and their union charged.

An `ORACLE / TEST-INFORMED` post-processing profile may be computed without new
forward assemblies. It is labelled as headroom and **never** reported as a
deployed candidate.

## 3. Staged gates

Each gate has a deliverable and a stop condition. A gate that cannot pass within
budget is recorded `UNQUALIFIED` or `INCONCLUSIVE`, never converted into a
compression result.

### G0 — freeze and audit (no numerical experiment)

1. Read `AGENTS.md`, [the iteration workflow](../../README.md),
   [implementation principles](../../implementation_principles.md), the
   [track handoff](../README.md) and the BIE-002 closeout.
2. Record commit, dirty status and diff, imported numerical source hashes,
   environment, thread settings, concurrent work.
3. Write `audit.md` mapping every reused API and its **exact** scaling
   convention: block layout `[[I−K, V],[−T, I+K′]]`; mode ordering `−K_u…K_u`;
   trace state `(û_D, q̂)` with `q = |z′| ∂ₙu`; the `2π` factor inside
   `kernel_matrix`; the flux similarity and unitary DFT in `modal.py`; the
   `operator` versus `hadamard` derivative contracts.
4. ~~**Blocking check:** the three assemblers must be shown to agree.~~
   **Resolved 2026-09-17, before approval, by a read-only check that wrote no
   artifacts.** `CoefficientGeometry.assemble` builds `K′` from `target_dot`
   while `ModalMomentFamily` and `ShapeOperator` use `k[::-1,::-1].T`; on
   circle/ellipse/star at 0.5 and 1.25 GHz with `K_u=24, B=64, terms=28` the
   relative Frobenius differences are `≤8.5e-15` (moment family) and `≤1.1e-16`
   (shape operator). **`CoefficientGeometry.assemble` is the reference.** Carry
   this forward as a regression test in `test_algebra.py`, not as a gate.
5. Freeze `config.json`: fixtures, frequencies, `K_u`, `B`, `terms`, `N`,
   directions, masks, floors, gates, budget, seeds, output directory.

**Stop if** the frozen config's only novelty is repeating BIE-002's bands.

### G1 — qualify the oracle and the uncompressed modal control

**Case matrix.** Fixed-material, equal-permeability, single-interface full-space
TMz. Exterior `ε_r = 6`, interior `ε_r = 3`, unit relative permeability,
lossless — the recorded native benchmark values.

| Geometry | Source | Purpose |
|---|---|---|
| Circle | `LaurentGeometry.circle` | analytic sanity, mode indexing and sign checks. Never sufficient for a positive verdict |
| Ellipse | `LaurentGeometry.ellipse`, coefficients frozen from BIE-002 | first noncircular case |
| 5-lobed star | `LaurentGeometry.star` (Laurent modes `{−4, 1, 6}`) | mixed positive/negative Laurent modes; the hard case |

Prefer these existing fixtures over a conveniently easy new one. Validate the
actual curve, seam, orientation, simplicity, positive minimum `J` and the log
certificate before use. One BIE-002 saved two-component fixture may be added
**only** if it admits a Laurent chart and passes the certificate; otherwise
record `FIXTURE_UNAVAILABLE`.

**Frequencies** (review §4): `k_out·a_ref = 2` (≈1.08 GHz) and `5` (≈2.71 GHz)
are primary; `10` (≈5.41 GHz) runs only after a Bessel term/precision
qualification, else `UNQUALIFIED`. `a_ref` is the equivalent-area radius of the
anchor geometry; record Hz and both media's electrical sizes. Physical
frequencies are **held fixed** during shape perturbation.

**Acquisition.** The existing 24 paired source/receiver set, frozen coordinates
and strengths, all RHS at a frequency through one factorisation. Separate
validation illuminations are declared and never used to choose masks.

**Refinement.** `K_u ∈ {24, 48}`; `B ∈ {48, 96}` (the doubling check the source
comments demand); `terms ∈ {28, 48}`; nodal oracle `N ∈ {256, 384}`; projected
control from `N ∈ {128, 256}` with `N > 2K_u` always.

**Required passes before any mask is tested:**

| Check | Gate |
|---|---|
| `E P = I`, identity projection, mode ordering, complete RHS/receiver conversion | exact to roundoff |
| Square full-DFT control vs nodal receivers | `≤1e-10` relative |
| Circle analytic solution reproduced | declared tolerance |
| Refined nodal receiver reference | `≤1e-8`; data directional derivatives `≤1e-5` |
| Uncompressed native control vs refined nodal | receivers `≤1e-7`; lifted scaled full-system residual `≤1e-7`; data directional derivative `≤1e-4` |
| Projected-Nyström control, same `K_u` | the same three, reported separately |
| Matrix convergence at fixed `K_u` under refining `N` and `B` | reported, not assumed |

**Known risk (review §"Risks" 1).** At `K_u = 24` the star's recorded residual
is `1.1e-4`. Either qualify the star at `K_u = 40` or record it `UNQUALIFIED`
at the lower cutoff. Do not shrink `M` until it fails and then blame the mask.

### G1b — is the retained structure analytic? *(the stop-gate)*

Using only G1's already-assembled matrices, compare `predicted_support` with
`measured_support` per block, per fixture, per frequency, at declared floors,
for both split labels. Report the magnitude decay of each part separately:
the log-symbol part is expected to decay like `1/|m−n|` inside its band, the
smooth part away from the centre of the box.

| Outcome | Consequence |
|---|---|
| Prediction holds at the declared floor | `ANALYTIC_SUPPORT` becomes the reference rule. `FORWARD` and `DERIVATIVE_AWARE` run only at fractions bracketing its retention. Full sweep **cancelled** |
| Prediction fails or is far looser than the measured support | Run the brief's full mask sweep as written in G3 |

This gate costs no new assemblies and can remove most of the campaign. That is
its purpose (implementation principles §5).

### G2 — trustworthy geometry derivatives

**Directions.** At each noncircular anchor, four linearly independent training
directions spanning low and high admissible Fourier modes and both real
coordinate types, plus **two held-out** directions, at least one involving an
admissible harmonic outside the training span. Save all coefficients and the
singular values of the coordinate matrix. Normalise each `v` so a unit step
gives RMS boundary displacement `a_ref`; record the normal component (a nearly
tangential direction is not a sensitivity test).

Differentiate with respect to independent **real** coordinates from the real and
imaginary parts of the Cartesian Laurent coefficients. Do not impose
`c₋ₚ = conj(cₚ)`, do not change the chart, and do not apply a gauge or
retraction inside a derivative probe.

**Mechanism vs check (review §3).** Analytic `D_v A`, `D_v b`, `D_v C` build
every reference and score. Centered differences of independently assembled
perturbed geometries at `h ∈ {1e-3, 5e-4, 2.5e-4}` are **required** at one
anchor per fixture, with a stable plateau and an independently refined-`N`
check. No arbitrarily tiny step, no single-step match, no complex-step
differentiation through `abs`, normals or conjugations. An inadmissible probe is
labelled unqualified; never substituted by a zero derivative.

**Differentiate the model that is solved.** Build `𝒮` at the anchor, freeze it,
then use the same `𝒮` for both:

```text
D_v Ã = D_v S + Π_𝒮 D_v R
A D_v x = D_v b − (D_v A) x
D_v Y = (D_v C) x + C D_v x + D_v Y_direct
```

Re-thresholding at `η ± hv` is a different algorithm and is out of scope.
With fixed observations and fixed weighting `W`,
`L = ½‖r‖²`, `D_v L = Re{r* W D_v Y}`; the adjoint form
`A*λ = C*W*r` is equivalent and either may be used. Multiple RHS and
frequencies sum real contributions; frequencies are never mixed in a solve.
Regularisation is absent from the core diagnostic.

**Truth.** One nearby but distinct synthetic truth per fixture from refined
Kress, observations frozen before any derivative test. The anchor is **not** the
minimiser. A small unmodelled shape harmonic is included where feasible. No
noise in this screen.

**Two required, separately reported checks:**

1. **Discrete correctness** — compressed tangent/adjoint vs finite differences
   of the *same frozen-mask compressed objective*.
2. **Physical accuracy** — that compressed derivative vs the qualified
   uncompressed/refined Kress derivative.

The reciprocal/Hadamard derivative evaluated on compressed traces is a **third,
separately labelled** arm. The continuous identity is not automatically the
derivative of a finite masked matrix; both errors are reported.

### G3 — compare retention rules at fixed trace dimension

Separate masks per physical frequency; masks and hashes stored. Nominal retained
fractions **0.10, 0.20, 0.30, 0.50, 1.00**; a band reports its actual fraction.
Both split labels. For every retained matrix, **solve the actual transmission
system** and evaluate data and derivatives — heatmaps, Frobenius tails and
random-vector action errors are not acceptance tests.

`COEFFICIENT_WINDOW` runs here as the separately labelled work-reducing arm:
sweep `(B, terms)` downward from the qualified setting, reassemble, and record
error **and measured assembly seconds** against the G1 reference.

### G4 — held-out checks and resolution robustness

With the mask unchanged:

- Both held-out geometry directions and the validation illuminations. A
  threshold chosen after seeing these is not held out.
- Trace dimension approximately doubled (`K_u → 2K_u`) at an independently
  qualified `N`; rebuild the anchor mask from training information at the new
  dimension and retest held-outs. Report retained fraction **and** absolute
  retained count at both resolutions.
- At the star and the intermediate electrical size, apply the fixed anchor mask
  at two unseen offsets of RMS displacement `0.005·a_ref` and `0.01·a_ref`,
  reassembling exact `S, R` there. This is local mask robustness, **not** an
  operator surrogate or a reusable inverse step.
- Check normal geometry admissibility and the log certificate at every offset;
  separate invalid geometry from numerical failure.
- Report the worst case and each frequency separately; no pooled error.

A mask from four directions is not validated for arbitrary geometry
derivatives. State exactly which independent directions and harmonics were
covered.

## 4. Metrics recorded at every paired point

**Structure.** Per-block and total retained fraction; identity/protected-part
representation; stored values and indices; derivative-support union; coefficient
and mode ordering; predicted-versus-measured support; optional band profiles.

**Accuracy.** Operator-action error on reproducible random vectors, forward
solution vectors and adjoint-relevant vectors; data error per frequency/RHS;
data directional-derivative error; objective directional derivative; modal and
lifted full-system residuals; condition number in the declared scaling.

**Derivative attribution** — reported separately, never merged into one number:
finite-difference plateau, reference refinement error, uncompressed modal error,
compression-only error, total compressed-to-reference error.

**Cost.** Native assembly, projection, split extraction, analytic directional
derivatives, mask discovery, protected-part construction and application,
remainder storage and application, factorisation, RHS solves, receiver
evaluation, derivative contractions, validation, peak memory. Every
factorisation and RHS batch, plus RHS **columns**. Finite-difference primal
reassemblies count as work. Fixed block/unknown scaling throughout a paired
comparison; canonical `q` removes the Dirichlet/Neumann unit mismatch and any
further equilibration is documented.

### Numerical gates — frozen, not renegotiable after results

| Quantity | Gate |
|---|---|
| Receiver error vs qualified refined Kress | `≤1e-6` relative on each non-negligible frequency/RHS group |
| Data directional-derivative error | `≤1e-3` relative, target `1e-4`; every non-negligible held-out direction |
| Objective directional-derivative error | `≤1e-3` relative, target `1e-4`, with the allowance below |
| Lifted residual in the qualified fixed-scaled full nodal system | `≤1e-6`; the uncompressed modal residual also reported |
| Research retention target | `≤≈0.30` of candidate remainder couplings, derivative-support union included |
| Refinement stability | still qualified at approximately doubled trace dimension; retained fraction must not rapidly approach one |

For a near-zero objective derivative, save the absolute error and use

```text
|g̃_v − g_v| ≤ 1e-3·|g_v| + 1e-6·s_v,     s_v = ‖r_ref‖₂ · ‖W D_v Y_ref‖₂
```

reporting which term controlled the decision and the sign where significant.
An analogous absolute scale is declared for near-zero fields and data
derivatives **before** any mask is inspected. Reference uncertainty, allowed
approximation and any later noise budget stay distinct.

## 5. Cost interpretation

Conventional dense factorisation is acceptable for the diagnostic: it isolates
approximation quality, and zeroing entries does not reduce dense LU complexity.
Two questions are measured **separately**:

1. Does the representation preserve the required quantities with fewer couplings?
2. Can obtaining and using those couplings beat the current qualified
   implementation?

Building all dense entries and all directional derivatives before selecting a
mask answers (1) only. Its preparation cost is included in full and any
sparse-assembly benefit is labelled **unimplemented**. A dense protected part is
counted; a coefficient-represented one reports measured storage, convolution
bandwidth and action time. The retained fraction of the remainder is never
quoted as the total algorithmic reduction.

Benchmarks run against accuracy-matched **current nodal Kress with its qualified
reciprocal/compiled derivative path**, starting from the recorded position that
the native assembler is ≈16× slower per forward than the 32-node nodal control
it matches to `6e-15`. One worker, single-thread BLAS/OpenMP, fixed warm-up,
three paired repeats in alternating order, ranges reported, JIT cold and
amortised recorded. A sequential run is not called isolated unless host-wide
isolation was checked. **No speed criterion is required for a positive structure
result**, and a speed claim requires measured end-to-end savings at matched
field and derivative quality, mask discovery and validation included.

## 6. Verdicts

| Verdict | Meaning |
|---|---|
| `GO_HYBRID_FEASIBILITY` | Adaptive common masks meet receiver, derivative, residual and refinement gates on **both** noncircular fixtures at moderate electrical size with ≈≤30% remainder retention. States which split was used. Authorises a recommendation for a separately scoped hybrid prototype — not a speed or inverse-method claim |
| `ANALYTIC_STRUCTURE_SUFFICIENT` | The predicted support meets all gates and neither `FORWARD` nor `DERIVATIVE_AWARE` improves on it at matched retention. Recommends a declared `(B, terms)` budget rule inside the existing assembler; **not** a mask-learning mechanism and **not** a hybrid prototype |
| `STRUCTURE_ONLY` | Oracle/training masks look promising but held-outs, protected-part cost, mask-discovery cost or full-system residuals prevent a practical conclusion. States the one missing mechanism |
| `STOP_TESTED_COMPRESSION` | More than roughly half the candidate interactions are needed at relevant electrical size, derivatives destroy the saving, or retention deteriorates sharply with refinement. Preserve the negative result and its scope |
| `INCONCLUSIVE_REFERENCE_OR_BUDGET` | Reference, derivative, trace, decomposition or compute qualification failed. Missing evidence is not converted into a no-go or a success |

`FORWARD` and `DERIVATIVE_AWARE` are compared directly. If forward-only
selection meets all derivative gates at the same or lower cost, the report says
the tested cases do **not** demonstrate an advantage from derivative-aware
selection.

## 7. Budget and accounting

Hard ceilings, checked before each batch whose maximum cost is known:
**45 min** numerical wall time, **8 GiB** peak RSS, **≤500** full physical
assemblies (FD primal rebuilds included), **≤1200** factorisations,
**≤2500** RHS batches. Source-audit and implementation time are separate and may
never be used to hide numerical runs.

Planned consumption, for reservation before dispatch:

| Stage | Assemblies | Notes |
|---|---:|---|
| G1 references and controls | ≈66 | 48 native across `(K_u, B, terms)`, 12 nodal oracle, 6 projected |
| G1b | 0 | reuses G1 matrices |
| G2 finite-difference plateau | ≈144 | one anchor per fixture, 6 directions × 3 steps × 2 signs, plus one refined-`N` repeat |
| G3 `COEFFICIENT_WINDOW` | ≈24 | masks themselves need no new assembly |
| G4 doubled `K_u` and local offsets | ≈18 | |
| **Total** | **≈252 / 500** | expected wall time well inside the ceiling; measure, do not assume |

On a cap: checkpoint and issue `INCONCLUSIVE_REFERENCE_OR_BUDGET`. Never
silently extend a ladder, relax a gate, replace a fixture or open a successor.

## 8. Artifacts

Fresh directory, never overwritten:

```text
results/validation/laurent/LAU-001-<timestamp>-modal-derivative-compression/
    README.md                 decision, decisive evidence, limitations, next decision
    manifest.json             source hashes, environment, geometry, acquisition, seeds
    config.json               frozen tolerances, directions, masks, grids, budgets
    audit.md                  API/scaling/sign map, three-assembler agreement, difference from BIE-002
    reference_convergence.csv N, K_u, B, terms, oracle and trace qualification
    structure.csv             predicted vs measured support per block (G1b)
    fd_convergence.csv        steps, refinements, tangent and objective checks
    compression.csv           all arms, all masks, all failures; no best-only reporting
    heldout.csv               unused directions/illuminations and local-offset checks
    timings.csv               full ledger, controlled repeats, preparation included
    summary.json              machine-readable per-case gates and overall verdict
    commands.md               exact commands actually executed
    review.md                 independent review, or explicit 'self-review only'
```

Save masks, direction coefficients and enough numeric arrays to reproduce the
checks, following the repository's tracked-binary policy. A small number of
plots: blockwise forward and derivative magnitudes, error versus retention,
retention versus trace resolution. Label every axis with modes, units and block
identity. Keep failures and invalid probes visible.

## 9. Commands (interface to implement — none of these exist yet)

```bash
cd /home/drdeng/Neural_SDF_BEM_AD
git status --short && git branch --show-current && git rev-parse HEAD
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python

$PY -m pytest -q experiments/laurent_compression/test_algebra.py \
               experiments/laurent_compression/test_derivatives.py

$PY -m experiments.laurent_compression.run_screen \
    --config <frozen-config.json> --stage pilot --dry-run
$PY -m experiments.laurent_compression.run_screen \
    --config <frozen-config.json> --stage pilot --output <fresh-pilot-dir>
$PY -m experiments.laurent_compression.run_screen \
    --config <same-frozen-config.json> --stage campaign \
    --resume <pilot-manifest> --output <fresh-campaign-dir>
```

The runner prints resolved parameters, exposes a dry-run work estimate,
checkpoints safely, refuses incompatible resumes, and checks imported source
hashes **before and after** numerical work. On drift it stops and keeps prior
results tagged with their original snapshot rather than blending them.

**Pilot first:** circle algebra and analytic checks, then ellipse and star at
`k_out·a_ref = 2`. Establish reference and derivative validity before any
three-size sweep. Reuse matrices across all masks and both trace cutoffs.

## 10. Required tests

`test_algebra.py`

- `E P = I`, identity projection, mode ordering, RHS/receiver round trip.
- Split reconstruction: `identity + log_part + smooth_part` equals
  `CoefficientGeometry.assemble` for every block and both split labels.
- `kernel_matrix` versus the retained `kernel_matrix_reference` contraction.
- Three-assembler agreement (`assemble`, `ModalMomentFamily`, `ShapeOperator`),
  carried forward from the G0 check at its measured tolerances.
- **Entrywise `D_v A` versus centered finite differences, per block.** This
  check exists nowhere in the repository today: `A` has a blockwise dense-oracle
  test, but every existing derivative test validates the *data* Jacobian
  `D_v Y`, in which a per-block error can partially cancel. `LAU-001` masks
  `D_v R` entry by entry, so it must establish the derivative at that
  granularity before any mask is scored.
- Mask accounting: per-block fractions, derivative-support union, deterministic
  ties, protected-row charging.
- **`R(η) = η·H` at `η = 0`** — the forward remainder vanishes but its
  derivative does not. `DERIVATIVE_AWARE` must not silently discard all
  sensitivity.

`test_derivatives.py`

- Analytic `D_v A`, `D_v b`, `D_v C` versus centered finite differences with a
  plateau.
- Frozen-mask tangent and adjoint versus finite differences of the **same**
  frozen-mask objective.
- Adjoint identity including weighting and scaling.
- Parameter-shift / tangential-null control on **receiver data** only (not on
  `D_v A`): reparameterisation can change matrix entries while leaving physical
  data unchanged to first order.

## 11. Independent review must answer

- Was this genuinely adaptive/derivative-aware, rather than BIE-002's band
  experiment repeated on a different matrix?
- Were `q`, Fourier normalisation, RHS, receivers, signs and every geometry
  dependence handled consistently across the native, projected and nodal paths?
- Did derivatives differentiate the same frozen-mask model, and was the
  continuous reciprocal check labelled separately?
- Were noncircular, held-out and refined-resolution cases qualified without any
  gate changing after results?
- Was the protected singular part actually the verified split, or only the
  identity — and were all costs counted?
- Does any speed claim survive comparison with the current nodal
  reciprocal/compiled baseline?

End the report with **one** recommendation: a separately scoped hybrid
prototype, a declared coefficient-budget rule, stopping the tested rule, or one
precisely named unresolved diagnostic. Not another unconstrained menu, and no
automatic successor.

## 12. Deferred — document, do not execute here

The brief's §14 staged path (a true hybrid Fourier–Galerkin `V`, then `K/K′`,
then regularised `T`, then the full Müller system, then a matched inverse),
frequency–geometry surrogates and reduced bases all remain later decisions. The
existing Laurent work is preserved; this plan neither erases it nor treats it as
an unbuilt dependency.

---

**Approval.** `LAU-001` is `PROPOSED — NOT APPROVED FOR EXECUTION`. Until the
user approves this ID by name, an agent may read, review, propose and write
documents, and may **not** create `experiments/laurent_compression/`, change any
numerical code or configuration, or launch a run — not even a small one, and not
as "just checking". Branch or worktree creation needs separate explicit
approval, per `AGENTS.md`.
