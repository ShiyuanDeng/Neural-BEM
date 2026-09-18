# Laurent track: start here

**Opened 2026-09-17 by user direction.** The Laurent/coefficient work was built
as an exploratory notebook inside Boundary–BIE iteration 05 and as two isolated
application experiments. It is now large enough to own a cycle structure. This
handoff organises what exists and what it has established; the shared folder
convention, approval rule, experiment-contract template and collaboration rules
stay in the [iterations README](../README.md).

**Nothing was moved to open this track.** Iteration 05's four exploration
records stay in `boundary_bie/`, the application reports stay under
`results/experiments/`, and the code stays under `experiments/`. This track
cites them as starting evidence, exactly as Boundary–BIE cites the
Cartesian-Fourier history.

## Research question

> **What does a node-free Laurent/Fourier coefficient representation of
> geometry, boundary traces and scattering give the inverse that a nodal
> discretisation does not — and what does it cost?**

The track is organised around that question, not around promoting the Laurent
solver. **Replacing Kress is not the goal.** The recorded evidence is explicit
that the node-free path is currently *slower* than an accuracy-matched nodal
Kress forward, and that the demonstrated speedups come from mechanisms
(reciprocal derivatives, trace elimination into a scattering matrix) that
transfer to the nodal compiler. What is distinctive about the Laurent path is
**structure**: exact singular splitting, analytic derivatives in coefficient
space, exact symmetry selection rules, and a geometry description with no
quadrature grid at all.

## What "the Laurent pipeline" is

Eight layers, built 2026-09-16, all under `experiments/`. Production solver
defaults were never changed by any of it.

| # | Layer | Owns | Implementation |
|---|---|---|---|
| L1 | **Geometry and the log certificate** | `z(θ) = c₀ + s·Σ z_j e^{ijθ}`; the divided difference `W = (z(w)−z(v))/(w−v)`; right-half-plane certificate and the projected log-series recurrence | `coefficient_operator.CoefficientGeometry` |
| L2 | **Node-free Müller assembly** | `A = [[I−ΔK, ΔV],[−ΔT, I+ΔK′]]` built from coefficient convolutions. `log R = log(4sin²(θ−φ)/2) + 2Re log W`, so the singular part is an **exact** contraction against `L_ℓ = −1/\|ℓ\|`. `T` uses the Maue identity applied before truncation | `CoefficientGeometry.assemble`, `kernel_matrix`, `kernel_matrix_reference` (independent algebra check), `ModalMomentFamily` (compile geometry once, reuse across frequencies) |
| L3 | **Acquisition without nodes** | Sources, receivers and disconnected-component interaction from cylindrical-wave expansions and Graf's addition formula. Boundary integrals are Fourier-coefficient selections | `coefficient_fields` (`RegularWaves`, `cross_matrix`, `solve`), `coefficient_derivative.FixedAcquisition`, `ShapeFields` |
| L4 | **Shape derivatives** | Three distinct paths, kept separate on purpose: the **operator** derivative `D_v A` of the finite modal system; the **reciprocal/Hadamard** continuous identity `δY_rs = (k_i²−k_o²)∫ u_s u_r (δx·n) ds` evaluated with truncated traces; and a **matrix-free** trace/coefficient action | `coefficient_derivative.ShapeOperator.derivative`, `NativeShapeForward.hadamard_jacobian`, `coupled_inverse.TraceJacobian` |
| L5 | **Fixed-topology inverses** | Bounded least squares over a radial Fourier chart, frequency continuation, noise regularisation, residual-driven addition of shape harmonics, extra-frequency acquisition design | `inverse.py`, `coupled_inverse.py` |
| L6 | **Scattering-matrix compilation** | Eliminate the boundary traces once into `T = P A⁻¹ B`; solve `(I − TU)β = Ta`, `Y = Cβ`. Rotation is the phase `e^{i(n−m)α}`. Pose derivatives are exact derivatives of that finite system | `scattering_library.py`, `pose_inverse.py` |
| L7 | **Deformable scattering matrices** | `dT/dx_j` for Laurent coefficient directions at fixed cylindrical normalisation; joint shape+pose inversion; checked local-`T` models with fresh-recompilation acceptance | `deformable_scattering.py`, `deformation_inverse.py` |
| L8 | **Applications of the compiled path** | Calibration-aware acquisition design; neighbour-assisted shape sensing under joint shape/material/gain uncertainty | `experiments/laurent_calibration/`, `experiments/laurent_neighbour/` |

Verified on 2026-09-17 in this checkout: **`pytest -q experiments/modal_muller_research` → 30 passed in 8.56 s.**
The package's own [README](../../../experiments/modal_muller_research/README.md)
owns the module map, the stable-versus-driver surface, and the rule that its
files are **hash-pinned by 11 recorded bundles** and must be extended rather
than reorganised.

### Resolution symbols — keep these distinct

| Symbol | Meaning | Code name | Typical qualified value |
|---|---|---|---|
| `K_γ` | geometry Laurent half-degree | `LaurentGeometry.coefficients` keys | 1 (circle) … 6 (5-lobed star) |
| `K_u` | boundary-**trace** half-bandwidth | the `cutoff` argument | 16–40 |
| `M` | coefficients per trace, `M = 2K_u+1` | — | 33–81 |
| `B` | coefficient half-bandwidth of the polynomial workspace | `bandwidth` | 32–96 |
| `p` | cylindrical/angular order of the scattering matrix | `order` | 12–14 |
| `terms` | retained Bessel power-series length | `terms` | 28 (48 at high frequency) |
| `N` | nodal Kress nodes per component (control only) | `nodes` | 32/64 production, 256/384 oracle |

**Naming trap.** Iteration-05 prose writes `M=24` for the code's `cutoff=24`,
which is 49 coefficients per trace. New records use `K_u=24, M=49`. Do not
rename the existing API to fix the prose.

## Progress ledger — what is actually established

Each row is a recorded measurement with its scope. None of it is a production
promotion; no Laurent code is on any default path.

| Capability | Established | Evidence |
|---|---|---|
| Node-free forward matches refined nodal Kress | Data error `3.0e-15`–`6.1e-15` on circle/ellipse/star/two-component at 0.5 and 1.25 GHz; oracle 256/512 agreement `≤9.8e-15` | [`native/accuracy.csv`](../../../results/experiments/modal_muller_20260916/native/accuracy.csv) |
| Trace-cutoff convergence is geometry-dependent | Circle/ellipse converge by `K_u=16`; the star needs `K_u=40` for the same data error and still leaves residual `3.9e-8` | [`native/convergence.csv`](../../../results/experiments/modal_muller_20260916/native/convergence.csv) |
| The coefficient window `B` is a real, unquantified error axis | `B: 64→96` moves the star matrix by `5.4e-13`; `96→128` by `2.1e-16`. The log-series bound is explicitly declared `'coefficient L2, projected recurrence; excludes window error'` | same; `coefficient_operator.py:199` |
| Operator derivative `D_v A` is analytic and cheap | Native reciprocal vs refined nodal operator derivative: `1.4e-5` (`K_u=16,B=24`) → `1.6e-9` (`24,40`) → `3.6e-13` (`32,64`) | [iteration 05](../boundary_bie/iteration_05/01_exploration.md) |
| Reciprocal derivative is the dominant practical win — **and it is not Laurent-specific** | Nodal reciprocal inverse is **18.8–19.0×** faster than the nodal operator-derivative control; the native modal inverse is only 1.4–1.7× faster than it | [iteration 05](../boundary_bie/iteration_05/01_exploration.md) |
| Coupled multi-object recovery with residual-driven mode selection | Two objects, 1% noise: combined RMS `1.759 → 0.030 mm`, held-out field `1.969% → 0.182%`, after one selected harmonic, one designed frequency and one more harmonic | [iteration 05 §2](../boundary_bie/iteration_05/02_coupled_modes_and_measurements.md) |
| Matrix-free Jacobian actions scale better | 192×192 acquisition, 82 shape parameters: payload `48.37 → 0.75 MB` (**64.6×**), actions 2.7–3.0× faster, agreement `6e-16`. At 24×24 the explicit matrix still wins | same |
| Trace elimination into `T` is the real speedup | Four objects, 1% noise pose inverse: `0.155 s` including compilation vs `1.538 s` nodal reciprocal rebuild (**10×**), `0.078 s` with reuse (**20×**) | [iteration 05 §3](../boundary_bie/iteration_05/03_scattering_library.md) |
| Exact symmetry selection rules appear without masking | Circle `m=n`; ellipse `m−n` even; three-lobed `m−n ≡ 0 mod 3`; forbidden-entry Frobenius norm `0`, `2.1e-17`, `5.0e-17` | same |
| `dT/dx` in Laurent coordinates, and its fingerprints | Reciprocal vs differentiated compiler `7.0e-15`; centered recompilation `7e-11`–`2e-10`. A circle's `δr = ε cos kθ` opens exactly the `\|m−n\| = k` bands | [iteration 05 §4](../boundary_bie/iteration_05/04_deformable_scattering.md) |
| Joint shape+pose inversion, 24 unknowns | All 54 inverses converge; four objects 1% noise: boundary RMS `0.1438 mm`, held-out field `0.3196%`; local-model discrepancy falls `1.40e-2 → 1.60e-13` over four accepted updates | same |
| The compiled path supports real information experiments | Calibration-aware design does **not** beat well-spread uniform multioffset (negative); an uncertain neighbour **does** improve target-harmonic recovery `0.654 → 0.118 mm` | [calibration](../../../results/experiments/laurent_calibration_20260916/report.md), [neighbour](../../../results/experiments/laurent_neighbour_20260916/report.md) |
| Published Fourier compression construction reproduced | JWY2021 scalar mask: 0.687% entries at 2,047 unknowns, analytic-density error 1.63e-11. Adapted transmission masks pass six of eight cases with fewer represented forward slots; both higher-frequency stars fail. Exact table reproduction and runtime gains remain open | [LAU-002 closeout](../../../results/validation/laurent/LAU-002-20260917-closeout/README.md) |

### Measured cost position — read this before proposing a speed claim

Single component, 0.5/1.25 GHz, one CPU thread, from
[`native/timings.csv`](../../../results/experiments/modal_muller_20260916/native/timings.csv):

| Forward, circle | Median seconds | One-time setup |
|---|---:|---:|
| Nodal Kress, 32 nodes | **0.0039** | 0 |
| Compiled `ModalMomentFamily` | 0.0072 | 0.908 s |
| Native `assemble` per call | 0.0624 | 0.0015 s |

The native assembler is roughly **16× slower per forward** than the nodal
control it matches to `6e-15`, and the compiled variant is ~1.9× slower with a
0.9 s compile that must be repeated whenever the inverse changes the shape.
Iteration 05 records the same conclusion from the other end: *"Native forward
assembly still dominates."* Any Laurent speed claim is measured against the
current qualified nodal reciprocal/compiled path, never against the retired
nodal operator-derivative baseline.

## Standing limits of the whole pipeline

These apply to every layer and must be restated in any successor plan.

- **Materials.** Lossless, equal (unit relative) permeability, scalar TMz,
  single interface per component. The reciprocal identity requires equal
  permeability; material inversion is untested on this path.
- **Geometry admissibility.** The log quotient needs `Re(W/z₁) > 0`. Some
  distorted saved shapes fail that certificate or converge slowly. The series
  bound controls the projected coefficient recurrence in L2 and **does not**
  certify the finite coefficient window.
- **Frequency ceiling.** The Bessel power series cancels at high argument:
  good at 2.5 GHz (`9.1e-13`), broken at 5 GHz with 28 terms (`0.254`),
  recovered only to `2.6e-8` at 48 terms, still poor at 8 GHz
  ([`native/stress.csv`](../../../results/experiments/modal_muller_20260916/native/stress.csv)).
  Every inverse recorded so far used 0.5–2.5 GHz.
- **Topology.** Disjoint bounding circles, external sources/receivers, known
  component count and identity, locally constrained initial guesses. No
  topology change, no object detection, no close contact.
- **Charts.** The inverses use a radial chart that removes tangential gauge
  freedom; the underlying forward accepts general Laurent geometry. Do not
  describe the tested inverse as unrestricted Cartesian Laurent recovery.
- **Statistical scope.** Small fixture counts, one or five noise seeds, one or
  two initialisations. These are feasibility and screening results.

## Cycle history

| Iteration | Cycle | State |
|---|---|---|
| — | Pre-track exploration (filed in Boundary–BIE iteration 05, 2026-09-16) | Four exploration records; 30 tests pass; no production promotion |
| 01 | **Does the modal operator's remainder compress while preserving geometry derivatives?** | **LAU-001 COMPLETE** (2026-09-17). Original `STRUCTURE_ONLY` result; the “every gate” and refinement interpretation are corrected by LAU-001-R1. [Original bundle](../../../results/validation/laurent/LAU-001-20260917-modal-derivative-compression/README.md) |
| 02 | Independent review and validation repair | **LAU-001-R1 APPROVED and COMPLETE**. [Contract](iteration_02/03_plan.md). Independent derivatives, objective gating, flux scaling, fixed-count refinement, asymmetric and held-out checks |
| 03 | What survives the corrected screen? | [Results](iteration_03/01_results.md): ellipse passes at fixed 30%; both stars fail fixed 30%/50% budgets. The refined star pass uses more entries than the smaller dense remainder. Coefficient-window qualification survives; no speed or promotion claim |
| 04 | Published construction and numerical transmission transfer | **LAU-002 COMPLETE**. [Results](iteration_04/01_results.md): scalar convergence verified, printed-table discrepancies preserved; adapted masks reduce represented entries on six of eight transmission cases. No runtime or production claim |
| 05 | Innovation: sensitivity-preserving trace reduction | **LAU-003 COMPLETE**. [Results](iteration_05/01_results.md): 48/194 unknowns preserve anchor derivatives; compact frozen reuse fails. 120/194 tangent model survives small offsets but fails new illumination. No inverse/speed claim |
| 06 | Protected spans and guarded reuse | **LAU-004 COMPLETE**. [Results](iteration_06/01_results.md): rank 80→56 / 120→112; 42/42 delivered physical passes with 24 rebuilds. No compact nonanchor reuse, inverse or speed claim |

## Reading order

1. This handoff.
2. The four iteration-05 exploration records in order:
   [native inverse](../boundary_bie/iteration_05/01_exploration.md) →
   [coupled modes and measurement design](../boundary_bie/iteration_05/02_coupled_modes_and_measurements.md) →
   [scattering library](../boundary_bie/iteration_05/03_scattering_library.md) →
   [deformable scattering](../boundary_bie/iteration_05/04_deformable_scattering.md).
3. Mechanism sources, in this order:
   `experiments/modal_muller_research/coefficient_operator.py` (assembly and the
   exact log split), then `coefficient_derivative.py` (analytic `D_v A`), then
   `scattering_library.py` (trace elimination).
4. [BIE-002 closeout](../../../results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02/README.md)
   — the *projected-Nyström* modal diagnostic that stopped, and the reusable
   fixtures, gates and negative controls it leaves behind.
5. Iteration 01: the [received brief](iteration_01/02_proposals/01_modal_derivative_compression_tests.md),
   the [review](iteration_01/02_proposals/02_review.md), then the
   [plan](iteration_01/03_plan.md).

## Current state

The user directed a shift to our innovations on 2026-09-17 and authorized
proceeding. **LAU-003 is APPROVED** under that instruction; its bounded contract
records the scope. Exact paper-table parity is no longer the active objective.

| Item | Value |
|---|---|
| Active iteration | [06: protected spans and guarded delivery](iteration_06/01_results.md) |
| Stage | **LAU-004 COMPLETE; 2026-09-18 priority review recommends parking generic compression**. [Review](iteration_06/02_proposals/01_outsider_priority_review.md); user direction pending |
| Approved experiment IDs | **`LAU-001`, `LAU-001-R1`, `LAU-002`, `LAU-003`, `LAU-004`**. LAU-004 authorized by the user’s “go” after LAU-003; [contract](iteration_05/03_plan.md). LAU-003 authorized by the user’s instruction to proceed with our innovations; [contract](iteration_04/03_plan.md). LAU-002 authorized by the user's instruction to catch up with the literature, 2026-09-17; [contract](iteration_03/03_plan.md). Repair authorized by “just keep fixin and testin” after the outsider review, 2026-09-17 |
| Execution status | `COMPLETE` for LAU-004 pilot; campaign not released (compact nonanchor reuse target failed). Prior experiments complete |
| Next expected action | Consider the [outsider priority review](iteration_06/02_proposals/01_outsider_priority_review.md): preserve compression tools, prioritize a direct inverse-information question, and reopen compression only with a cost/quality case |
| Owner / reviewer | Codex implemented and validated LAU-004; independent reviewer unassigned. Earlier repair history remains in its own records |
| Branch | `feature/ordered-boundary-nystrom` in the existing checkout; no branch or worktree creation |
| Shared interfaces | None touched. `solvers/` and `modal_muller_research/` stayed read-only; experiments live in [`laurent_compression/`](../../../experiments/laurent_compression/README.md), [`laurent_literature/`](../../../experiments/laurent_literature/README.md), [`laurent_tangent_rom/`](../../../experiments/laurent_tangent_rom/README.md) and [`laurent_adaptive_rom/`](../../../experiments/laurent_adaptive_rom/README.md) |

The 2026-09-16 open-exploration authorisation recorded in the
[Boundary–BIE handoff](../boundary_bie/README.md) covered that exploration. It
is **not** a standing authorisation for a numbered experiment on this track.
The 2026-09-17 repair instruction separately authorized LAU-001-R1's bounded
corrections and reruns; it did not request a sparse assembler or default change.
The subsequent instruction to catch up with literature separately authorized
LAU-002's reproduction and bounded transmission transfer; its completed scope
does not establish a fast assembler or justify a production default change.

## Reproduce the current pipeline

```bash
cd /home/drdeng/Neural_SDF_BEM_AD
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:. MPLCONFIGDIR=/tmp/laurent-mpl
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q experiments/modal_muller_research
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.modal_muller_research.run_native
```

Evidence bundles: [`results/experiments/modal_muller_20260916/`](../../../results/experiments/modal_muller_20260916),
[`laurent_calibration_20260916/`](../../../results/experiments/laurent_calibration_20260916),
[`laurent_neighbour_20260916/`](../../../results/experiments/laurent_neighbour_20260916).
