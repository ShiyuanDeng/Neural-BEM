# Review of the modal derivative-compression brief

**Reviewer:** Claude (not the brief's author). **Date:** 2026-09-17.
**Subject:** [`01_modal_derivative_compression_tests.md`](01_modal_derivative_compression_tests.md).
**Diagnostics run for this review:** none numerical. Source reading and one
existing-suite confirmation (`pytest -q experiments/modal_muller_research` →
30 passed, 8.56 s). No configuration, solver or experiment file was changed.

## Verdict

**Accept the scientific contract; amend the target, the derivative mechanism,
the frequency ladder and the placement.** The brief is careful, its gates are
usable as written, and its negative-control discipline is right. It was written
against the *projected-Nyström* modal object that BIE-002 tested. This track
owns something the brief treats as hypothetical: an independently constructed,
node-free Laurent Fourier–Galerkin Müller assembler with an **exact analytic
singular split** and an **analytic operator derivative** already in the tree.
That changes what the cheapest decisive measurement is, and it makes one of the
brief's contingencies (`SPLIT_UNAVAILABLE`) probably unnecessary.

The consolidated contract is [`03_plan.md`](../03_plan.md).

## Resolutions

Each material recommendation, resolved once.

| # | Brief's recommendation | Resolution |
|---|---|---|
| R1 | File at `boundary_bie/iteration_05/02_proposals/01_…` | **Reject — user direction.** Filed in a new `laurent` track at `docs/iterations/laurent/iteration_01/02_proposals/01_…`. Iteration 05's records are not moved or renumbered |
| R2 | Working label `MDC-SCREEN`, reconcile with the ID register | **Accept with amendment.** The ID is **`LAU-001`** |
| R3 | Check whether the 16 September open-exploration authorisation still applies | **Resolved: it does not extend here.** It authorised the iteration-05 exploration. `LAU-001` is `PROPOSED — NOT APPROVED FOR EXECUTION`; only the user passes gate 4 |
| R4 | Out of scope: "a new Laurent assembler" | **Accept, and note it is moot.** One exists and is qualified. The screen imports it read-only |
| R5 | Make `A_M^proj = E A_N^q P` the diagnostic object | **Accept as a control; retarget the primary object.** See §1 |
| R6 | Expect `SPLIT_UNAVAILABLE` for `VERIFIED_SINGULAR_SPLIT` | **Resolved: the verified split is available.** See §2 |
| R7 | Build directional references by centered finite differences of independently assembled geometries | **Accept as the *check*; reject as the *mechanism*.** See §3 |
| R8 | Sweep electrical sizes `k_out·a_ref ∈ {2, 5, 10}` | **Accept 2 and 5; make 10 conditional.** See §4 |
| R9 | Arms `FULL / BAND / FORWARD / DERIVATIVE_AWARE`, fractions 0.10–1.00 | **Accept verbatim**, plus two added arms (§5) that the brief could not have specified |
| R10 | Blockwise score with Frobenius normalisation and declared floors; forward-only ablation | **Accept verbatim.** It stays the baseline adaptive rule |
| R11 | Algebra unit test `R(η) = η·H` at `η = 0` | **Accept verbatim** as a required test |
| R12 | Numerical gates in §10 (receiver `1e-6`, derivative `1e-3`/target `1e-4`, lifted residual `1e-6`, retention `≤0.30`, refinement stability) and the cancellation-aware absolute allowance | **Accept verbatim, unchanged.** Not renegotiable after results |
| R13 | Budget: 45 min, 8 GiB, ≤500 assemblies, ≤1200 factorisations, ≤2500 RHS batches | **Accept as hard ceilings.** Expected consumption is well under, because §3 removes the FD sweeps the brief budgeted for |
| R14 | Artifacts under `results/validation/boundary_bie/<id>-…` | **Amend** to `results/validation/laurent/LAU-001-<timestamp>-modal-derivative-compression/` |
| R15 | Package at `experiments/modal_derivative_compression/` | **Amend** to `experiments/laurent_compression/`, matching `laurent_calibration/` and `laurent_neighbour/` |
| R16 | Benchmark against the current nodal reciprocal/compiled path, not the old operator-derivative arm | **Accept, and sharpen.** The honest starting point is that the native assembler is ~16× slower per forward than the 32-node nodal control it matches to `6e-15`. Recorded in the [handoff](../../README.md#measured-cost-position--read-this-before-proposing-a-speed-claim) |
| R17 | Verdict vocabulary (four labels) | **Accept, plus one.** See §6 |
| R18 | Conditional later work (hybrid `V`, then `K/K′`, then regularised `T`, then a matched inverse) | **Defer unchanged.** Not part of `LAU-001` |
| R19 | "Do not rely on the older dashboard's statement that no modal prototype exists" | **Confirmed.** The dashboard is stale on Boundary–BIE's stage too; this review does not rewrite it beyond adding the new track row |

## 1. Retarget the primary object: test the operator we actually have

The brief is right that `A_M^proj = E A_N^q P` "is a diagnostic/control" and must
not be called an independently constructed continuous Fourier–Galerkin operator.
On this track that operator is not hypothetical:
`CoefficientGeometry.assemble` (`coefficient_operator.py:238`) builds
`A = [[I−K, V], [−T, I+K′]]` directly from Laurent coefficients, with **zero
boundary nodes and zero point-pair kernel calls** (both are asserted in its
returned metadata).

So the primary compression target is the **native** `A_M`, and `A_M^proj` is
retained as the equivalence control — which is also exactly the object BIE-002
tested and stopped. Keeping both is what separates "BIE-002 repeated" from a
new result. The nodal→modal transform the brief specifies in §4.2 already
exists as `modal.ModalSystem.from_nodal`: it applies the flux similarity
`S_q = diag(I, diag J)` via `state_scale` (`modal.py:36`), projects with a
**unitary** DFT (`norm='ortho'`), and already reports the lifted residual
`‖A·lift(x) − b‖/‖b‖` (`modal.py:81`). Reuse it; do not re-derive it. The
adapter must record which Fourier normalisation is in force and convert RHS,
receivers and derivatives consistently — the brief's warning applies precisely
because the two available conventions differ.

## 2. The verified singular split exists; use it

The brief's §4.3 anticipates having only `IDENTITY_ONLY` and records
`SPLIT_UNAVAILABLE` as the likely outcome. In this assembler every block is

```text
block[m,n] = 2π ( smooth[m,−n]  +  Σ_ℓ L_ℓ · P[m−ℓ, ℓ−n] ),   L_ℓ = −1/|ℓ|, L_0 = 0
```

(`kernel_matrix`, `coefficient_operator.py:87–107`), which is the brief's own
`ℓ̂_h = −1/|h|` symbol. `kernel_matrix_reference` (`:72`) is retained in the
source as an independent literal contraction — the reconstruction check the
brief asks for, already written. So both labels are available:

| Label | Protected `S_M` | Remainder `R_M` |
|---|---|---|
| `IDENTITY_ONLY` | the `I` blocks and the Maue term `−mn·V` (`:254`) | everything else |
| `VERIFIED_SINGULAR_SPLIT` | the above **plus** the exact log-symbol convolution of every block | the smooth polynomial lookup `2π·smooth[m,−n]` |

This satisfies the brief's prohibition on collapsing the singular part to a
universal diagonal: `L` is convolved against the **geometry-dependent** array
`P`, and its derivative is nonzero by construction (`ShapeOperator.derivative`
differentiates both the `P` factor and `log_quotient`).

**Consequence the brief could not anticipate.** With the split written this way,
the support of each part is *predictable*, not empirical. If the effective
coefficient half-bandwidth is `β`, then the log-symbol part is nonzero only
where `|m−n| ≤ 2β` (a centered band) and the smooth part only where
`|m| ≤ β` and `|n| ≤ β` (a centered box). `β` is set by the Laurent degree and
the number of Bessel terms that survive the weight floor, and is capped by the
declared `B`. This is a falsifiable structural hypothesis costing a handful of
assemblies to test, and it can **stop** the whole mask campaign — which is
exactly what implementation principle §5 asks a screening stage to be able to
do. The plan makes it gate **G1b**, before any mask sweep.

It also relocates where compression would actually pay. Zeroing entries of an
assembled dense `A_M` does not reduce dense LU cost, as the brief says. Reducing
`B` and `terms` *does* reduce assembly cost, because `dense_product` is an
FFT over the full `(2B+1)²` workspace per Bessel term per block family. The
recorded sensitivity is already instrumented: `B: 64→96` moves the star matrix
by `5.4e-13`, `96→128` by `2.1e-16`, and the source comments state outright that
the log-series bound *"excludes window error"* (`coefficient_operator.py:199`).

## 3. Analytic derivatives are the mechanism; finite differences are the check

The brief budgets centered differences of independently assembled perturbed
geometries as the way to obtain `D_v R` for every training direction. On this
track `D_v A` is analytic: `ShapeOperator.derivative`
(`coefficient_derivative.py:102`) returns the block derivative in the same
coordinates, reusing `2 Re(δW/W)` so that extra directions cost contractions
rather than reassemblies. It is qualified against the refined nodal operator
derivative at `1.4e-5 → 1.6e-9 → 3.6e-13` as `(K_u, B)` refine.

So: analytic `D_v A` builds the directional references and the derivative-aware
scores; centered differences at `h ∈ {1e-3, 5e-4, 2.5e-4}` remain **required**
at one anchor per fixture as the plateau/roundoff check, plus the refined-`N`
check. Every other rule in the brief's §7 is kept verbatim, including the
decisive one: the mask is frozen at the anchor and the *same* `𝒮` is used for
`Ã` and `D_v Ã = D_v S + Π_𝒮 D_v R`. Re-thresholding at `η ± hv` tests a
different, piecewise-defined algorithm and is out of scope.

The reciprocal/Hadamard derivative stays a **separately labelled** arm, as the
brief requires. The repository already draws this distinction explicitly
(`jacobian_kind='operator'` versus `'hadamard'`), and iteration 05 states it in
the same terms: the continuous identity evaluated with truncated traces is not
the derivative of the finite modal system.

## 4. The frequency ladder has a hard physical ceiling here

With exterior `ε_r = 6` and an anchor `a_ref = 36 mm`, the brief's sizes map to

| `k_out·a_ref` | `f` | `k_in·a_ref` | Status |
|---:|---:|---:|---|
| 2 | 1.08 GHz | 1.41 | Safe. Brackets the 0.5/1.25 GHz points all prior inverses used |
| 5 | 2.71 GHz | 3.54 | Plausible. Just above the verified 2.5 GHz point (`9.1e-13`), needs its own Bessel-term check |
| 10 | 5.41 GHz | 7.07 | **At risk.** At 5 GHz the series gives `0.254` relative error with 28 terms and only `2.6e-8` with 48 |

(`native/stress.csv`.) Sizes 2 and 5 are primary. Size 10 runs only if a Bessel
term/precision qualification passes at the declared gate; otherwise it is
recorded **`UNQUALIFIED`**, never as a compression failure. This is the brief's
own rule about oracle qualification, applied to a limit it did not know about.

## 5. Two added arms

Both are cheap, both are Laurent-specific, and without them the screen is a
re-run of BIE-002 on a different matrix.

- **`ANALYTIC_SUPPORT`** — the predicted exact support from `(K_γ, effective
  Bessel order, B, K_u)` of §2, with no magnitude thresholding at all. If it
  meets the gates, `DERIVATIVE_AWARE` has to beat *this*, not `BAND`, to be
  worth anything.
- **`COEFFICIENT_WINDOW`** — reduce `B` and `terms` and reassemble, measuring
  error **and assembly seconds**. This is the only arm in the design that
  changes real work, and it is the direct answer to the brief's second question
  in §11 ("can obtaining and using those couplings beat the current qualified
  implementation?").

## 6. One added verdict

The brief's four labels do not cover a likely outcome: the structure is real
and predictable, but no *learned* mask improves on the analytic prediction.
Reporting that as `GO_HYBRID_FEASIBILITY` would overstate it, and as
`STOP_TESTED_COMPRESSION` would erase a positive result. Added:

**`ANALYTIC_STRUCTURE_SUFFICIENT`** — the predicted support meets receiver,
derivative, residual and refinement gates on both noncircular fixtures, and
neither `FORWARD` nor `DERIVATIVE_AWARE` improves on it at matched retention.
The recommendation is then a declared bandwidth/term budget rule inside the
existing assembler, **not** a mask-learning mechanism and **not** an authorised
hybrid-assembler prototype.

## Risks the plan must carry, not resolve

1. **The star's own trace convergence is the weak link, not compression.** At
   `K_u = 24` the star's data error is `1.5e-9` and its residual `1.1e-4` —
   already outside the brief's `1e-6` residual gate before any mask is applied.
   Either qualify the star at `K_u = 40` (where residual is `3.9e-8`) or record
   it `UNQUALIFIED` at the lower cutoff. Do not reduce `M` until it is too small
   and then blame the retention rule; the brief says this and it bites here.
2. ~~**Three assemblers must be shown to agree first.**~~ `assemble` builds `K′`
   from `target_dot` (`:250`) while `ModalMomentFamily` (`:320`) and
   `ShapeOperator` (`coefficient_derivative.py:94`) use `k[::-1,::-1].T`.
   **Amendment, 2026-09-17:** resolved before approval by a read-only check that
   wrote no artifacts — circle/ellipse/star at 0.5 and 1.25 GHz, `K_u=24`,
   `B=64`, `terms=28`, relative Frobenius difference `≤8.5e-15` (moment family)
   and `≤1.1e-16` (shape operator). `CoefficientGeometry.assemble` is the
   reference. The G0 blocker is struck and becomes a regression test.
3. **`A_M^proj` and native `A_M` are different matrices**, not two views of one.
   A retention rule that works for one is not thereby established for the other.
   Report them separately throughout.
4. **A positive structure result is not a faster assembler.** Preparation cost —
   dense entries, analytic directional derivatives, mask discovery, protected-part
   construction — is counted in full, and any sparse-assembly benefit is labelled
   unimplemented.

## What this adds beyond BIE-002 — in one paragraph

BIE-002 projected an assembled Nyström matrix into Fourier coordinates, tested
fixed centered bands, and stopped: no noncircular band met the joint gates, and
its oracle profiles (`5.72%` ellipse, `16.77%` star) were bounds on a full
matrix, not tested algorithms. `LAU-001` changes three things at once. The
matrix is the **independently constructed** node-free operator rather than a
projection of a nodal one. The protected part is a **verified analytic singular
split** rather than the identity alone, which is the decomposition the source
report's hypothesis is actually about. And the retention question is asked with
**analytic geometry derivatives** available, so derivative-aware selection can be
tested at its intended cost instead of through a finite-difference budget. If
the answer is still negative, it is a negative about the desingularised modal
representation itself — which BIE-002 could not deliver.
