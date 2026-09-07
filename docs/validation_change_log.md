# Validation Change Log

> **Status: append-only experimental history.** For present behavior see
> [`current_architecture.md`](current_architecture.md); for active work see
> [`ordered_boundary_nystrom_plan.md`](ordered_boundary_nystrom_plan.md).
> The compressed-cloud QBX/kdiff investigation closed on 2026-09-01; its
> evidence and qualifications are in [`qbx_closure.md`](qbx_closure.md).
> Earlier “current” interpretations and “next steps” below are chronological
> history, not current instructions.

2026-08-21

## Scope

This records the small validation pass made after the forward-solver review. The
repo root `.git` directory is empty, so this file is the durable local record of
the changes.

## Files changed

- `test/test_ibim_tmz_theory_validation.py`
  - Added an executable theory regression for the 2D TMz forward solver.
  - The reference is the separation-of-variables Fourier-Bessel series for a
    penetrable circular cylinder driven by the same line-source Green function
    used by the code, `0.25j * H_0^(1)(k r)`.
  - The reference self-checks zero contrast and transmission continuity before
    using the series as a numerical oracle.
  - The IBIM scattered field is checked at 0.5, 1.5, and 2.5 GHz on the canonical
    circle boundary. Observed relative L2 errors during development were roughly
    0.102, 0.228, and 0.159.

- `test/test_ibim_tmz_adjoint.py`
  - Replaced one brittle central-difference assertion with the exact directional
    derivative through `bscan_from_frequency_response`.
  - The old finite-difference check used `step = 1e-8` and failed from roundoff
    at about `2.31e-6` relative error against a `1e-6` tolerance.
  - The new check compares the adjoint dual against the direct transform
    derivative and passes at `1e-12`.

## Validation run

Command:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q test
```

Result:

```text
56 passed, 2 skipped, 32 warnings in 165.32s
```

The two skips are CuPy-dependent GPU consistency checks. CuPy is not installed in
the active `EMNerf` environment. The warnings are the intentional
`compress_implicit_boundary_band` warnings that report when requested
`merge_distance` is reduced before operators size their trace offsets.

## Current interpretation

The forward solver works for the canonical circular inclusion in the sense that
it reproduces the exact penetrable-cylinder scattered field to about 10-25% in
the main operating band with the current compressed-boundary/offset assembly.
That validates the physics path and catches order-one regressions such as the
old trace-offset mistake.

The same test also makes the limitation explicit: the present assembly is not a
high-accuracy singular quadrature. The residual error is consistent with the
offset-based trace approximation and irregular compressed boundary samples
described in `docs/legacy/forward_solver_validation.md`.

## Follow-up implementation pass

2026-08-21

### Files changed

- `gpr_bem/cylinder_reference.py`
  - Moved the exact 2D TMz penetrable circular-cylinder line-source reference out
    of the test file into a shared module.
  - Exposes incident, scattered, total-field, and frequency-response helpers.

- `gpr_bem/validation.py`
  - Added reusable frequency-response and B-scan error metrics.
  - Reports absolute, pure relative, mixed relative, broadband, and gated errors
    so physical scattering nulls do not dominate interpretation by themselves.

- `gpr_bem/ibim_tmz_system.py`
  - Added `solve_strategy={"direct", "squared"}` to the forward solve APIs.
  - Changed the default state solve to direct `A q = b`.
  - Kept the old `A^2 q = A b` route as `solve_strategy="squared"` for
    diagnostics and reproducibility.
  - Forward results now record `solve_strategy` and
    `linear_system_relative_residual`.

- `run_ibim_rectangular_scan_forward.py`
  - Added `--solve-strategy`, `--skip-validation`, and
    `--skip-solve-diagnostics`.
  - The default run now writes:
    - exact circular-cylinder total/scattered frequency responses,
    - approximate scattered response with the analytic incident field removed,
    - exact total/scattered B-scans,
    - frequency and B-scan validation metrics,
    - metadata JSON,
    - validation JSON,
    - validation Markdown summary,
    - validation PNG comparing exact, IBIM, residual, and frequency error.

- `test/test_ibim_tmz_system.py`
  - Added a direct-vs-squared solve regression.
  - The direct solve must produce a smaller state residual while staying close to
    the old squared route on a physical RHS.

- `test/test_ibim_tmz_theory_validation.py`
  - Updated the theory regression to use the shared cylinder reference module.

### Validation run

Command:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q test
```

Result:

```text
58 passed, 2 skipped, 34 warnings in 210.72s
```

The two skips are still the CuPy-dependent GPU checks. The warnings are the
intentional `compress_implicit_boundary_band` warnings.

### Regenerated forward artifacts

Command:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python run_ibim_rectangular_scan_forward.py --device cpu --output-dir results/rectangular_loop_forward
```

Generated:

- `results/rectangular_loop_forward/rectangular_loop_forward_data.npz`
- `results/rectangular_loop_forward/rectangular_loop_forward_metadata.json`
- `results/rectangular_loop_forward/rectangular_loop_forward_validation.json`
- `results/rectangular_loop_forward/rectangular_loop_forward_validation.md`
- `results/rectangular_loop_forward/rectangular_loop_forward_validation.png`
- refreshed overview, stack, and trajectory PNGs

Key saved validation numbers from the full rectangular-loop run:

| metric | value |
|---|---:|
| scattered broadband relative error | 0.696145 |
| total B-scan relative error, all samples | 0.0259846 |
| total B-scan relative error, t >= 2 ns | 0.564599 |
| scattered B-scan relative error, t >= 2 ns | 0.696116 |

Selected scattered-field frequency errors:

| f (GHz) | rel error |
|---:|---:|
| 0.504687 | 0.0998889 |
| 1.50406 | 0.244445 |
| 2.00375 | 3.39807 |
| 2.50344 | 0.153756 |
| 4.0025 | 1.06712 |
| 8.0 | 2.29568 |

Direct-vs-squared diagnostics on selected frequencies show direct state residuals
around `1e-15` versus squared-route residuals around `1e-8`, with receiver
differences around `1e-9`. This supports using direct `A q = b` as the default
until a real Calderon-style derivation justifies an operator product solve.

### Current interpretation after follow-up

The repo now has executable theory validation and run-time validation artifacts,
not just plots. The direct state solve fixes the unnecessary conditioning damage
from the old `A^2 q = A b` route, but it does not fix the dominant discretization
error. The late/scattered B-scan remains far less accurate than the full B-scan
appearance suggests, because the full record is dominated by the analytic direct
wave. The remaining error still points at the finite-offset trace and singular
quadrature problem described in `docs/legacy/forward_solver_validation.md` and
`docs/legacy/ibim_error_mitigation_literature_codex.md`.

---

## Muller formulation and analytic normal-derivative kernels

2026-08-24. All changes are in `solvers/gpr_bem_mod/`; `solvers/gpr_bem_ref/` is
untouched and remains the control.

### Files changed

- `gpr_bem_mod/ibim_tmz_forward.py`
  - Added `implicit_single_layer_normal_derivative_potential_from_band` and
    `implicit_double_layer_normal_derivative_potential_from_band`, which evaluate
    `dG/dn_x` and `d^2G/dn_x dn_y` from their analytic kernels. `H_2` is formed by the
    recurrence `H_2 = (2/z) H_1 - H_0`, so the backend still only needs orders 0 and 1.
  - Added `normal_derivative_scheme` to the two normal-derivative trace functions, the
    `K'`/`W` matrix builders and the operator-family builder:
    - `finite_difference` - the historical path, unchanged;
    - `analytic` - analytic kernel evaluated at the stand-off `+-d`;
    - `analytic_extrapolated` (default) - analytic kernel at `d, 2d, 3d` per side,
      Lagrange-extrapolated to `t = 0` with weights `(3, -3, 1)`.
  - Exposed `default_trace_offset_distance`.

- `gpr_bem_mod/ibim_tmz_system.py`
  - Added `formulation={"muller", "difference"}`, defaulting to `muller`.
  - `difference` reproduces the historical system exactly: the exterior and interior
    Calderon equations subtracted, which cancels the `+-1/2` identity terms and leaves
    every block a sum of the two wavenumbers. First kind.
  - `muller` adds them instead: the identity survives on the diagonal and every block
    becomes an exterior-minus-interior difference. Second kind. Because
    `build_implicit_hypersingular_boundary_matrix` returns `W = -T`, all four blocks
    take the same orientation. The right-hand side `(u_inc, q_inc)` and the receiver
    representation are unchanged.
  - Added `MULLER_OFFSET_SCALE = 0.1375` (i.e. `d = 0.275 x merge_distance`), applied
    when `offset_distance is None` and the formulation is Muller. The value was tuned
    after the fact; see the valley refinement below.
  - `formulation` and `normal_derivative_scheme` are recorded on the system object and
    threaded through `solve_ibim_tmz_total_field_batch` and
    `solve_ibim_tmz_frequency_response`.

### Measured: scattered-field relative L2 against the Fourier-Bessel series

Analytic circle, 257^2 grid, 272 boundary samples, 12 bistatic pairs, strict
quadrature, float64. Stand-off at the historical default `d = 2 x merge_distance`:

| case | 0.5 GHz | 1.5 GHz | 2.5 GHz | cond(A) @ 2.5 GHz |
|---|---:|---:|---:|---:|
| ref, difference + finite difference | 0.1016 | 0.2283 | 0.1589 | 1.510e+11 |
| mod, difference + finite difference | 0.1016 | 0.2283 | 0.1589 | 1.510e+11 |
| mod, difference + analytic | 0.3292 | 0.3685 | 0.5993 | 1.393e+11 |
| mod, difference + analytic extrapolated | 0.6475 | 0.3300 | 0.3994 | 3.342e+11 |
| mod, Muller + finite difference | 0.0087 | 0.4635 | 1.7558 | 2.350e+04 |
| mod, Muller + analytic extrapolated | 0.0016 | 0.0935 | 0.3595 | 1.686e+04 |

The finite-difference row of `mod` reproduces `ref` to the printed digits, which is the
plumbing check.

**Conditioning.** `cond(A)` falls from `1.5e11` to `1.7e4`, seven orders of magnitude.
That is the structural confirmation that the Muller derivation is right: a second-kind
condition number does not appear by accident, and it settles open question 3 of
`docs/legacy/forward_solver_validation.md`.

**Analytic kernels alone do not help.** Under the first-kind formulation they are
worse than the finite difference at all three frequencies. The prediction in §4b that
variant (B) might lose was correct: the finite difference extrapolates to `t = 0` and
so partly compensates the stand-off consistency error.

The rows above compare schemes at a stand-off tuned for neither, so they do not
attribute the win. See the attribution table below, which does.

### Measured: the stand-off sweep, and the constraint that disappeared

Muller + analytic extrapolated, varying the stand-off:

| d / merge_distance | 0.5 GHz | 1.5 GHz | 2.5 GHz |
|---:|---:|---:|---:|
| 0.031 | 0.00260 | 0.01855 | 0.13289 |
| 0.063 | 0.00166 | 0.01230 | 0.08790 |
| 0.125 | 0.00076 | 0.00645 | 0.04413 |
| **0.250** | **0.00011** | **0.00276** | **0.00736** |
| 0.500 | 0.00020 | 0.00440 | 0.02400 |
| 1.000 | 0.00030 | 0.02010 | 0.08060 |
| 2.000 | 0.00160 | 0.09350 | 0.35950 |
| 4.000 | 0.00710 | 0.51090 | 2.17180 |

This is the measurement §4b said would be the most valuable output, and it answers the
question it posed -- but not the way §4b guessed. Under the old formulation the
accuracy valley sat at `d = 2 md` and error exploded below `1 md`, which
`docs/legacy/forward_solver_validation.md` §6.1 attributed to near-singular quadrature and §4b
attributed to the finite differencing dividing quadrature noise by `d`.

**Both explanations are wrong, and the measurement below refutes §4b's.**

*How the refutation was reached.* The §4b hypothesis was specific and therefore
falsifiable: if the small-`d` blow-up is caused by the stencil dividing quadrature noise
by `2d`, then it must be a property of **the differencing**, and a scheme that performs
no differencing cannot exhibit it. The analytic kernels are exactly that control -- they
evaluate `dG/dn_x` and `d^2G/dn_x dn_y` in closed form and never subtract two nearly
equal potentials. So the hypothesis predicts the three schemes should separate sharply
as `d` shrinks, with the finite difference diverging and the analytic rows staying flat.

Adding the `difference` formulation to the sweep was originally only meant as a
control for the Muller change. It turned out to be the decisive measurement, because
the three schemes do **not** separate. They agree to three significant figures at every
small `d`: 2.442 / 2.442 / 2.441 at `d = 0.125 md`. A mechanism that acts only on the
finite difference cannot produce an error that the analytic kernels reproduce to three
digits. Whatever causes the blow-up is therefore common to all three, and the only
thing they share is the operator combination they are assembled into.

The confirming half is the Muller column: under the second-kind system the finite
difference is well behaved down to `0.125 md` and its error keeps falling as `d`
shrinks. So the differencing does not blow up at small `d` per se -- it blows up at
small `d` *in a first-kind system*, exactly as the analytic kernels do. The `8 eps / d`
noise argument in §4b is arithmetically correct and simply never becomes the binding
term; it costs a factor 1.4 - 2.4 at matched optima, not an order of magnitude.

The mechanism is the standard one and should have been predicted from §4.1 rather than
measured: the first-kind system has no identity term, so its spectrum is unbounded and
the discrete operator inherits the conditioning of the continuous one. Shrinking `d`
sharpens the near-singular kernels and pushes `cond(A)` up further with nothing to
regularise it. Muller's surviving `I` on the diagonal is what bounds the spectrum, which
is the same fact that shows up as `cond(A)` falling from 1.5e11 to 1.7e4.

*The methodological lesson*, which is the same one `docs/legacy/forward_solver_validation.md` §10
records: the plausible-sounding mechanism was wrong again, and it was wrong in the same
direction -- an alarming-looking local numerical detail (a noisy stencil) was blamed for
an error that actually came from a structural choice one level up. §4b was written from
code reading, and code reading is what produced the wrong attribution. The control that
settled it cost one extra column in a sweep that was already being run.

The data:

| difference formulation, 2.5 GHz | d = 0.125 md | 0.25 md | 0.5 md | 2 md |
|---|---:|---:|---:|---:|
| finite difference | 2.442 | 2.404 | 2.182 | 0.159 |
| analytic | 2.442 | 2.403 | 2.271 | 0.599 |
| analytic extrapolated | 2.441 | 2.398 | 2.345 | 0.399 |

Switching to Muller removes the lower bound for **every** scheme, differencing included.

### Attribution: which change earned the win

Muller, each derivative scheme swept to *its own* optimal stand-off:

| scheme | best d / md | 0.5 GHz | 1.5 GHz | 2.5 GHz |
|---|---:|---:|---:|---:|
| finite difference | 0.125 | 0.00026 | 0.00406 | 0.01549 |
| analytic | 0.0625 | 0.00033 | 0.00382 | 0.02522 |
| **analytic extrapolated** | **0.275** | **0.00010** | **0.00261** | **0.00547** |

Refining the stand-off for the winning scheme (geometric mean over the three
frequencies, so no single band dominates the choice):

| d / md | 0.5 GHz | 1.5 GHz | 2.5 GHz | geo-mean |
|---:|---:|---:|---:|---:|
| 0.200 | 0.00025 | 0.00351 | 0.01723 | 0.00247 |
| 0.250 | 0.00011 | 0.00276 | 0.00736 | 0.00129 |
| **0.275** | **0.00010** | **0.00261** | **0.00547** | **0.00112** |
| 0.300 | 0.00012 | 0.00255 | 0.00636 | 0.00124 |
| 0.350 | 0.00016 | 0.00266 | 0.01100 | 0.00167 |

The valley is shallow between 0.25 and 0.30 md, so this is not a knife edge, but it is
tuned on one geometry at one discretisation and should be re-swept if either changes.

- **Muller is essentially the whole result.** With the derivative blocks left as the
  original finite difference and only the stand-off retuned, the error is already
  0.00026 / 0.00406 / 0.01549 -- a 390x / 56x / 10x improvement over `ref`.
- **The analytic extrapolated kernels add a further 1.4x - 2.4x** on top of that, at
  matched optima. Real and worth keeping, but secondary. The earlier "5x at 1.5 and
  2.5 GHz" figure was an artifact of comparing at `d = 2 md`, a stand-off tuned for
  neither scheme; it should not be quoted.
- **Plain analytic (variant B) is the worst of the three at 2.5 GHz**, worse than the
  finite difference it replaced. The extrapolation to `t = 0` is doing the work, not
  the analytic kernel by itself. Variant (B) is retained only as a diagnostic.
- Analytic extrapolated also reaches its optimum at a **larger** stand-off (0.25 md vs
  0.125 md), i.e. further from the near-singular region, which is a robustness
  advantage independent of the error figure.

### Selected configuration

`gpr_bem_mod` now defaults to **Muller + analytic_extrapolated at 0.275 x
merge_distance** (`MULLER_OFFSET_SCALE = 0.1375`), the best cell measured. Against the
`ref` baseline:

| f (GHz) | ref | mod default | improvement |
|---:|---:|---:|---:|
| 0.5 | 0.1016 | 0.00010 | **1020x** |
| 1.5 | 0.2283 | 0.00261 | **87x** |
| 2.5 | 0.1589 | 0.00547 | **29x** |

Roughly 10x / 56x / 390x of that is Muller; the kernels supply the remaining 1.4 - 2.4x.

`MULLER_OFFSET_SCALE` is tuned for `analytic_extrapolated`. The optimum is
scheme-dependent -- `finite_difference` bottoms out near 0.125 md and `analytic` near
0.0625 md -- so a caller overriding `normal_derivative_scheme` should override
`offset_distance` too.

The 10-15% error floor that `docs/legacy/forward_solver_validation.md` §2 called structural, and
§7 estimated would need ~8000 nodes to reach 1% at 2.5 GHz, is now below 1% at the
same 272 nodes.

### Consequences for the open issues

- Issue 1 is resolved, and with a much larger accuracy win than the ~60% confidence in
  §12.2 anticipated.
- Issue 4b is resolved, and its real value was the stand-off sweep rather than the
  direct accuracy delta, as predicted.
- **Issue 2 needs re-scoping.** The `O(kd)` stand-off argument was measured on the
  first-kind system with finite-difference derivative blocks. A full literature-style
  volume IBIM redesign is a much weaker proposition against a 0.7% baseline than
  against a 16% one. The nearer-term target is now compressed-boundary
  kernel-differenced quadrature on the boundary cloud already produced by the tubular
  sampling/compression step.
- Issue 6 (8 GHz) has not been retested and remains open.

### Test status

Updated 2026-08-25, after the shared tests were brought forward.

```text
python -m pytest pytest/ --solver=mod   ->  1 failed, 59 passed, 2 skipped
python -m pytest pytest/ --solver=ref   ->  0 failed, 60 passed, 2 skipped
```

Two of the three failures recorded on 2026-08-24 are resolved by test changes, not by
solver changes:

**1. `test_solver_comparison.py` — rewritten (resolved).** The old
`test_solvers_agree_on_scattered_field` asserted the two solvers agree, which stopped
being true by design. It is replaced by the per-solver metric table `solvers/README.md`
describes: `test_solver_comparison_table` prints N, stand-off, formulation, derivative
scheme, per-frequency relative error, per-frequency `cond(A)`, residual and timing for
both packages, and gates only on gross breakage;
`test_modified_solver_improves_circle_scattering_accuracy` asserts the `mod` defaults
are what they should be and that `mod` beats `ref` at every frequency. Measured:

| solver | N | offset | form | scheme | 0.5 GHz | 1.5 GHz | 2.5 GHz | cond @ 2.5 |
|---|---:|---:|---|---|---:|---:|---:|---:|
| ref | 168 | 0.00469 | difference | finite difference | 0.0915 | 0.6284 | 0.1958 | 6.06e+12 |
| mod | 168 | 0.00064 | muller | analytic extrapolated | 0.0003 | 0.0036 | 0.0342 | 1.80e+04 |

**3. `test_ibim_tmz_theory_validation.py` line 134 — made formulation-aware
(resolved).** The stale `offset_distance == 2.0 * merge_distance` assertion now
branches on `forward.system.formulation`: `difference` keeps the historical
`2.0 x merge_distance`, `muller` asserts `0.275 x merge_distance` and that the
derivative scheme is `analytic_extrapolated`. Both solvers pass.

**2. `test_ibim_tmz_adjoint.py::...frozen_geometry_finite_difference` (`mod` only) —
still failing, and should stay that way.**

```text
assert relative_error < 2.0e-4
E   assert 0.23341600170883026 < 0.0002
```

This is issue 8 arriving exactly where §12.2 and Phase H said it would.
`ibim_tmz_adjoint.py` carries its own assembly, which still hard-codes the first-kind
operator sum and the finite-difference normal-derivative blocks. It therefore
differentiates the *old* forward operator, and its dual no longer matches the *new*
one. The gradient is not wrong for the operator it was built for; it is now
differentiating a different operator than the one being solved. Nothing in the inverse
pipeline should be run against `mod` until the adjoint is brought forward, and that is
a 2346-line file that Phase H deliberately schedules last.

### Measured 2026-08-25: `MULLER_OFFSET_SCALE` is discretisation-dependent

The comparison test runs a coarser case than the one the constant was tuned on -- 168
samples on a 161^2 grid over a 6R box, against 272 samples on a 257^2 grid. Re-sweeping
the stand-off there:

| d / md | 0.5 GHz | 1.5 GHz | 2.5 GHz | geo-mean |
|---:|---:|---:|---:|---:|
| 0.1375 | 0.00073 | 0.00601 | 0.02223 | 0.00460 |
| **0.200** | **0.00018** | **0.00302** | **0.01337** | **0.00192** |
| 0.275 (default) | 0.00032 | 0.00355 | 0.03416 | 0.00340 |
| 0.350 | 0.00039 | 0.00573 | 0.04977 | 0.00482 |
| 0.500 | 0.00017 | 0.01476 | 0.07954 | 0.00589 |

The optimum moves from 0.275 md to about 0.200 md, and the default costs 2.6x at
2.5 GHz on this case. That is why the `mod` improvement over `ref` at 2.5 GHz reads as
5.7x in the comparison table but 29x in the theory test: part of the difference is a
genuinely harder discretisation, and part is simply an off-optimum stand-off.

Neither value dominates -- 0.200 is 2.2x worse than 0.275 on the 272-sample case, and
0.275 is 1.8x worse than 0.200 here -- so the constant was left at 0.1375, tuned for
the finer case that the theory regression uses. The honest reading is that
`MULLER_OFFSET_SCALE` is a tuned constant, not a derived one, and `merge_distance`
alone is not the right scaling variable. Expressed in mean node spacing `h` the two
optima sit at 0.30h and 0.25h, noticeably closer than 0.275 vs 0.200 suggests, which
points at `h` as the better normaliser -- but two points is not a scaling law. Deriving
the optimum properly is part of issue 2, not a patch to this constant.

---

## Nystrom reference solver

2026-08-25

Built the standalone explicit-boundary reference solver. Full results and the
convergence study are in `docs/nystrom_reference_study.md`; this is the change
record.

### Files added

- `solvers/nystrom_ref/nystrom_tmz.py`, `solvers/nystrom_ref/__init__.py`
  - Smooth curve parameterizations (circle, ellipse, star), uniform-`t` nodes,
    outward normals and speeds from the analytic tangent.
  - The four Muller difference kernels, formed **symbolically** rather than by
    subtracting two assembled operators.
  - Kress/Kussmaul-Martensen log quadrature, applied uniformly to all four
    blocks; diagonal entries by a Richardson limit in the parameter.
  - Dense assembly, direct solve, exterior representation at receivers.
  - Forward only. No SDF, no adjoint, no inverse, not differentiable.

- `pytest/test_nystrom_reference.py` — 11 tests, 14 s.

Placed as a **sibling** of `gpr_bem_ref` / `gpr_bem_mod` rather than inside
`gpr_bem_mod` as originally planned. An oracle that imports the machinery it
judges shares its bugs, and the shared `pytest/` suite resolves the bare name
`gpr_bem` to one package at a time, so a reference inside `gpr_bem_mod` would
disappear under `--solver=ref`. It shares only the problem definition: config
constants, the `Material` wavenumber convention, and the `0.25j * H_0^(1)(k r)`
normalisation.

### The finding that changed the plan

The plan budgeted a two-phase quadrature effort and rated high-order
hypersingular quadrature as the medium-confidence risk. It is not needed at all.

For TMz with non-magnetic media both traces are continuous, so the Muller blocks
are pure exterior-minus-interior differences with no material weighting. Taking
those differences analytically cancels the leading singularity of every block,
because in each case the leading term is k-independent: `ln r` in `dS`, `1/r` in
`dD` and `dK'`, `1/r^2` in `dT`. What survives is **bounded** in three blocks and
**`O(ln r)`** in the hypersingular one. A single log rule covers the whole
system: no Maue/Gunter regularisation, no finite-part integrals. This is variant
(D) of `docs/legacy/ibim_error_mitigation_literature_codex.md` §4b.4, scoped there and never
built.

The plan's Phase 2 had the ranking backwards -- it expected `S`, `D`, `K'` to
need corrections "especially", with the hypersingular difference as the merely
weakly singular one. After the difference is taken it is the reverse.

### Measured

Circle against the Fourier-Bessel series, 12 bistatic pairs, float64:

| f (GHz) | N | pts/lam | rel err | cond(A) |
|---:|---:|---:|---:|---:|
| 0.5 | 128 | 99.7 | 6.58e-13 | 1.19e+02 |
| 1.5 | 128 | 33.2 | 8.27e-12 | 4.39e+03 |
| 2.5 | 128 | 19.9 | 5.45e-11 | 1.21e+04 |
| 8.0 | 128 | 6.2 | 3.15e-08 | 5.06e+05 |

Converged at N = 128 everywhere in the band; refining is `O(1/N)`, not spectral,
because the residual error is dominated by the `eps = 1e-3` diagonal limit and a
diagonal entry carries weight `h = 2 pi / N`. That floor is `~1e-11` absolute.

Identities: zero contrast 2.35e-17; ellipse-with-`a=b` and star-with-`amp=0`
both reproduce the circle oracle at 4.66e-12; reciprocity on the star 1.29e-11;
`D_e u_inc - S_e q_inc` outside the scatterer at machine precision at every
frequency. That last one is the convention check, and it is the reason the sign
work landed first time -- it fails loudly on a flipped normal or a wrong jump
relation, which is exactly what a convergence study cannot see.

### Consequences for the open issues

- **Issue 6 (8 GHz) is localised.** Nystrom reaches 3.15e-08 at 6.2 points per
  wavelength with `cond(A) = 5.06e+05`, and Muller is resonance-free for
  transmission problems, so there are no spurious interior resonances. Whatever
  fails at 8 GHz is in the IBIM discretisation, not in the integral equation.
- **Issue 5 confirmed.** No anomaly at 2.0 GHz (1.9e-10, in line with its
  neighbours). The spike is a metric artifact of a physical null, as argued.
- **Issue 7 is done for smooth shapes.** Ellipse and star self-converge and the
  degenerate cases match the oracle, so non-circular validation now exists.
  SIREN-parameterised shapes are still out of reach -- these are analytic
  parameterizations, not level sets.
- **Issue 2 is still not decided, and the obvious comparison will not decide
  it.** "Nystrom beats IBIM by five orders of magnitude" was close to a foregone
  conclusion: spectral quadrature on an exact parameterization against a
  low-order stand-off approximation. The question that matters is how much of
  the IBIM's residual error is bad quadrature versus bad node distribution,
  since its nodes come from a compressed level-set band with irregular spacing
  and better singular quadrature cannot fix irregularity. The cheap version is
  to jitter the uniform-`t` nodes here to match the IBIM's spacing statistics
  and measure what survives. Not done.

### Test status

```text
python -m pytest pytest/test_nystrom_reference.py   ->  11 passed in 14.29s
```

Solver-independent: the file imports `nystrom_ref` and `gpr_bem_ref` by their
real names and never touches the bare `gpr_bem` alias, so it behaves identically
under `--solver=ref` and `--solver=mod`.

---

## gprMax cross-check

2026-08-25

Added a third, independently-implemented row to the comparison test: gprMax
(FDTD), alongside the two BEM packages. Full design and results are in
`docs/gprmax_reference_study.md`; this is the change record.

### Why a third method

`gpr_bem_ref` shares code lineage with `mod`. The Nystrom reference
(previous section) shares the Muller formulation with `mod` on purpose. Both
would reproduce a formulation-level bug in `mod` rather than catching it.
gprMax shares no code, no Green's function, and no boundary-integral
machinery with either -- it is the only check in this project that can tell
the difference between "the physics is right" and "two implementations of
the same method agree with each other".

### Files added

- `solvers/gprmax_ref/build_scene.py`, `run_case.py`, `cache_io.py`,
  `cache/*.json` -- see `docs/gprmax_reference_study.md` for the split
  between the (gprMax-env-only) runner and the (dependency-free) cache
  reader.
- `pytest/test_solver_comparison.py` -- extended with `_gprmax_metrics()`,
  a `gprmax` row in the printed table, and `test_gprmax_cross_check`, all
  driven from the cache and all skipping cleanly on a cache miss.

### The environment split forced the cache design, not just motivated it

gprMax needs a compiled Cython extension not built in the repo's own `gprMax/`
checkout; the working build lives in a separate `gprMax` conda environment
(Python 3.11) that the `EMNerf` test environment cannot import. There is no
code path by which the test suite could run gprMax itself even if it wanted
to -- so the cache in `solvers/gprmax_ref/cache/` is load-bearing, not a
speed optimisation. `cache_io.py` is pure stdlib + numpy and is the only part
of `gprmax_ref` the test ever imports.

### Design choice: calibrate against a background-only run

Rather than deriving gprMax's Hertzian-dipole current normalisation and
mesh-dispersion phase error analytically, two FDTD runs are made per case --
with and without the target -- and the background run's DFT is compared
against the closed-form incident field `0.25j H0^(1)(k |Tx-Rx|)` at each
frequency to get a per-frequency complex calibration factor, applied to the
target-minus-background signal. This cancels every FDTD-specific unknown
(source scaling, cell-size effects, direct-path dispersion) since both runs
share the source, domain, cell size, and path length, leaving only the
discretisation error the check is meant to measure.

### Design choice: one run for the whole ring

The 24-pair ring scan in `test_solver_comparison.py` is one representative
Tx/Rx pair rotated around a rotationally symmetric target, so every pair
gives the identical scattered field -- confirmed against the Mie series to
`7e-17`, not assumed. One gprMax run stands in for the whole comparison.

### Measured

Cell size 1 mm (29 cells/wavelength in sand at the dispersion-limiting
frequency, gprMax's own estimate of -0.10% phase-velocity error), Ricker
pulse at 1.5 GHz center, 15 ns window, ~8.7 s solve time per variant:

| f (GHz) | gprMax rel. error vs Mie | mod rel. error vs Mie |
|---:|---:|---:|
| 0.5 | 1.03% | 0.03% |
| 1.5 | 2.32% | 0.36% |
| 2.5 | 1.90% | 3.42% |

gprMax sits between `ref` (9-63%) and `mod` at 0.5 and 1.5 GHz; at 2.5 GHz
`mod`'s own error has grown to a similar order as gprMax's floor, so the two
are not meaningfully distinguishable there -- both are under 4%.

### What this adds to the picture

An independent, non-BIE method reproduces the Mie series to 1-2% on the same
case where the Muller reformulation delivered a 10-1020x accuracy gain over
`ref`. That is evidence the gain reflects real physics rather than a
self-consistent bug shared between `mod`, the Mie series, and Nystrom -- the
one thing the other two checks in this project cannot provide, since both
already assume the same formulation `mod` uses.

### Test status

```text
python -m pytest pytest/test_solver_comparison.py -s -q   ->  3 passed in 2.21s (cache hit)
```

Cache-miss path verified by temporarily moving the cache directory aside:
the gprMax table row disappears and `test_gprmax_cross_check` skips with a
message pointing at `run_case.py`, rather than failing the suite.

---

## Perfect circle sampling toggle

2026-08-25

### Purpose

A reusable version of the isolation experiment from `docs/legacy/forward_solver_validation.md`
§7 and the "not done" jitter proposal in `nystrom_reference_study.md`: swap the
real compressed IBIM boundary for exact uniform-arclength circle nodes, at the
same N, and see how much `gpr_bem_mod`'s error moves. Everything downstream
(offset rule, formulation, kernels) is left untouched.

### Files changed

- `solvers/gpr_bem_ref/ibim_geometry.py`, `solvers/gpr_bem_mod/ibim_geometry.py`
  (kept identical, as before) -- added `perfect_circle_boundary_samples()`.
  Places points at exact angles on the circle, exact outward normals, and the
  exact trapezoidal quadrature weight (spectrally accurate for a smooth
  periodic integrand). Returns a real `ImplicitBoundarySamples2D`, so it is a
  drop-in for anywhere a compressed boundary is accepted -- it never touches
  the Cartesian grid / Newton-projection / bin-merge pipeline at all.
  `merge_distance` is set to the resulting node spacing so offset formulas
  that scale off it behave the same as they do for a real boundary.
- Both `__init__.py` files -- exported the new function.
- `conftest.py` -- added `--perfect-sampling` (boolean, default off), next to
  the existing `--solver` option.
- `pytest/test_solver_comparison.py` -- `_run_solver` now takes
  `perfect_sampling`; when set, it builds the real compressed boundary only to
  read off its N, then replaces it with `perfect_circle_boundary_samples` at
  that N. The per-frequency `MAX_RELATIVE_ERROR` gate in
  `test_solver_comparison_table` and the `mod_error < ref_error` assertion in
  `test_modified_solver_improves_circle_scattering_accuracy` are skipped under
  the toggle (they were tuned against the real irregular boundary); the table
  still prints either way, labelled by sampling mode.

### Measured

Ring-scan case (`GRID = 161x161`, 6R box, N=168 both ways):

| solver | sampling | 0.5 GHz | 1.5 GHz | 2.5 GHz | cond(A) @ 2.5 |
|---|---|---:|---:|---:|---:|
| gpr_bem_ref | ibim | 0.0915 | 0.6284 | 0.1958 | 6.06e+12 |
| gpr_bem_ref | perfect | 0.0615 | 0.4320 | 0.1772 | 8.22e+07 |
| gpr_bem_mod | ibim | 0.0003 | 0.0036 | 0.0342 | 1.80e+04 |
| gpr_bem_mod | perfect | 0.0005 | 0.0025 | 0.0294 | 1.22e+04 |

```text
python -m pytest pytest/test_circle_comparison.py -s -q                     -> 3 passed
python -m pytest pytest/test_circle_comparison.py -s -q --perfect-sampling  -> 3 passed
```

(`test_solver_comparison.py` was renamed to `test_circle_comparison.py` later
the same day -- see below.)

### Reading, without digging into why

For `mod`, perfect sampling is close to a wash at this N: 1.4x better at
1.5 GHz, 1.2x better at 2.5 GHz, slightly *worse* at 0.5 GHz. It does not
reproduce the large gains the offset/formulation/kernel work already
delivered. For `ref`, it is a consistent but modest 1.1-1.5x, and `cond(A)`
drops by five orders of magnitude -- noted, not explained here.

This agrees in direction with the existing §7 isolation experiment (perfect
nodes help more at low frequency, less at the operating band) but not in
magnitude (that experiment saw up to 16x at 0.5 GHz on different N/grid/box
values) -- consistent with `MULLER_OFFSET_SCALE` already being documented as
discretisation-dependent for this exact ring-scan case, above. Not
re-swept here.

---

## Square target, and a shape-agnostic gprMax reference

2026-08-25

### Purpose

First non-circular target: a square, roughly the circle's size (same
characteristic length, not area-matched), same center. No closed-form
(Mie/Fourier-Bessel) oracle exists for a square cross-section, so this needed
a different validation strategy than the circle case, not just a new SDF.

### Files changed

- `solvers/gpr_bem_ref/neural_sdf.py`, `solvers/gpr_bem_mod/neural_sdf.py`
  (kept identical) -- added `rectangle_signed_distance()`, the exact Euclidean
  SDF of an axis-aligned rectangle (`length(max(d,0)) + min(max(d.x,d.y),0)`,
  not the `max(|x|-hw,|y|-hh)` approximation, which is only exact along the
  edges, not at the corners). A square is the equal-half-extents case. Exported
  from both `__init__.py`s. `build_implicit_boundary_band` needed no changes
  at all -- it already takes an arbitrary `sdf_fn`.
- `solvers/gprmax_ref/build_scene.py`, `cache_io.py`, `run_case.py` --
  generalised from a circle-only `target_radius` to `target_shape` +
  `target_size` (radius for a circle, half-side for a square).
  `build_geometry` snaps a square's half-side to a whole number of cells, so
  the `#box` target sits exactly on cell faces -- zero staircasing, the entire
  reason to reach for a square as an independent oracle (the circle's own
  floor was dominated by staircasing, `docs/gprmax_reference_study.md`).
  `run_case.run()` now builds its cache-key params via `cache_io.build_params`
  instead of a second, separately-maintained inline dict (the two had to stay
  in sync by hand before; that hazard is gone). This is a breaking change to
  the cache key schema, so the existing circle cache entry was regenerated
  under the new schema (identical physics, new hash) and the orphaned old-schema
  file removed.
- `pytest/test_solver_comparison.py` renamed to `pytest/test_circle_comparison.py`.
  `_gprmax_metrics`'s `build_params` call updated to the new
  `target_shape`/`target_size` signature. `test_solver_comparison_table` and
  `test_gprmax_cross_check` renamed to `test_circle_comparison_table` /
  `test_circle_gprmax_cross_check` for parallelism with the new file.
- `pytest/test_square_comparison.py` (new) -- same two-solver-plus-gprMax
  structure, but: no `relative_error` computed inline (no oracle); gprMax
  comparison uses only the ring scan's index-0 pair, since a square only has
  4-fold symmetry, not the circle's full rotational symmetry, so gprMax's one
  simulated pair does not stand in for the other 23 the way it does for the
  circle; and a `test_square_self_convergence` (N=161^2 -> 241^2) that needs
  no gprMax cache at all, checking `gpr_bem_mod`'s answer does not swing
  wildly under refinement -- the thing a square's corners (an SDF gradient
  discontinuity the circle never exercises) could plausibly break.
- `conftest.py`, `pytest/README.md`, `solvers/README.md`,
  `docs/gprmax_reference_study.md` -- filename/signature references updated.
  `docs/validation_change_log.md` -- this entry, and the file-name fix in the
  perfect-sampling entry above.
- Cache regenerated: `solvers/gprmax_ref/cache/58001057a5e8e4dd.json` (circle,
  new schema, identical scattered-field values to the old entry) and
  `32c8781ec4a0b804.json` (square, new). The old-schema circle entry
  (`2c3d5ec68165387c.json`) was deleted -- unreachable under the new key
  schema and regenerable via `run_case.py` if ever needed.

### Measured

Square, half-side 0.05 m, same center as the circle case, N=168 both solvers
(161x161 grid, same as the circle comparison):

| solver | 0.5 GHz | 1.5 GHz | 2.5 GHz |
|---|---:|---:|---:|
| gpr_bem_ref vs gprMax (index-0 pair) | 0.2718 | 0.2964 | 0.5346 |
| gpr_bem_mod vs gprMax (index-0 pair) | 0.0203 | 0.0635 | 0.0195 |

`gpr_bem_mod` self-convergence (N=168 -> 256, no gprMax involved):

| f (GHz) | relative change |
|---:|---:|
| 0.5 | 0.0115 |
| 1.5 | 0.0364 |
| 2.5 | 0.0792 |

```text
python -m pytest pytest/test_circle_comparison.py -s -q  ->  3 passed
python -m pytest pytest/test_square_comparison.py -s -q  ->  3 passed
```

### Reading, without digging into why

No pathological corner pile-up on the first attempt -- `mod` lands on the
same N=168 as the circle case at the same grid resolution, and both the
gprMax comparison and self-convergence pass comfortably inside their (loose,
first-cut) thresholds. `mod`'s error against gprMax (2.0% / 6.4% / 2.0%) is
the same order as the circle case's Mie-series error (0.03% / 0.36% / 3.4%)
but consistently worse, which is expected: `MULLER_OFFSET_SCALE` and the
whole offset/kernel tuning chain were swept on the circle only. Not re-swept
here. Self-convergence increasing with frequency (1.2% -> 3.6% -> 7.9%) is the
physically expected direction -- finer boundary features (i.e., the corners)
matter more as the wavelength shrinks -- not investigated further.

## Square target results, explained, and an analytical-oracle plan

2026-08-26

Read-only: no code changed. Follows up on the "not investigated further"
close of the previous entry. Full detail, including the ka/resonance/
condition-number tables and the T-matrix feasibility estimate, is in
`docs/legacy/square_target_oracle_options.md`; this is the pointer.

`gpr_bem_ref` being bad on both shapes traces to the same known first-kind
BIE + finite-difference normal-derivative issue, not a square-specific
failure mode. `gpr_bem_mod`'s square error being worse than its circle error
is expected -- `MULLER_OFFSET_SCALE` and the kernel scheme were tuned on the
circle only. The one genuine anomaly, `mod` vs gprMax peaking at 1.5 GHz
while `mod`'s own oracle-free self-convergence rises monotonically, was
narrowed down (interior-resonance proximity and gprMax numerical dispersion
both checked and ruled out as the cause) but not resolved -- the working
hypothesis is that it lives in gprMax's own square-case error, not `mod`'s,
and the two cannot be told apart without a tighter oracle.

No closed-form (Mie-style) solution exists for a square, confirmed again.
The best candidate for a *tighter-than-gprMax* independent check is a
T-matrix / Extended Boundary Condition Method oracle (global multipole
expansion, exact-boundary surface integral, its own convergence study
required before trusting it, feasible truncation order estimated at ~20 for
this case's `ka` range) built as a new sibling solver
`solvers/tmatrix_ref/`, following the `nystrom_ref` precedent. It would also
remove the current index-0-pair-only limitation of the gprMax check, since a
T-matrix evaluates any Tx/Rx pair cheaply once built. A quasi-static
conformal-mapping check was considered and set aside -- this case's `ka`
(1.28-6.42) is not in the quasi-static regime, so it would not usefully
constrain any of the three test frequencies. FEM was considered and
deprioritized as largely redundant with gprMax's own role. Not built here --
next step is a literature search (Phase 0 in the plan doc) before writing
any T-matrix code.

## Smooth non-circular target comparisons: ellipse and star

2026-08-26

### Purpose

Use the already-qualified standalone Nystrom solver as a precision baseline for
two smooth non-circular shapes from `docs/nystrom_reference_study.md`: an
ellipse with semi-axes 0.07 m / 0.035 m, and a star
`r(t) = 0.05 * (1 + 0.25 cos(5t))`. This exercises the IBIM forward path on
non-circular smooth geometry without relying on gprMax as the high-accuracy
oracle.

### Files changed

- `config/ellipse_config.py`, `config/star_config.py` -- shape-specific config
  files parallel to `circle_config.py` / `square_config.py`.
- `pytest/test_ellipse_comparison.py`, `pytest/test_star_comparison.py` -- new
  ref/mod/gprMax comparison tables. BEM error columns compare the full 24-pair
  ring against Nystrom N=512; gprMax is included only on the index-0 pair, by
  the existing one-pair FDTD design.
- `solvers/gprmax_ref/build_scene.py`, `run_case.py`, `cache_io.py` -- gprMax
  support for `target_shape=ellipse` and `target_shape=star`. Circle/square
  cache keys stay backward-compatible; optional `target_parameters` only enter
  the key for parameterized shapes. Ellipse/star are voxelized into row-wise
  `#box` spans, so their FDTD rows include staircasing error.
- `pytest/README.md`, `docs/gprmax_reference_study.md` -- references updated.
- Cache generated: `solvers/gprmax_ref/cache/b9574b81fbe6e086.json` (ellipse)
  and `b2014082026cfc76.json` (star).

### Measured

Ellipse, Nystrom N=512 baseline, BEM grid 161x161, BEM N=120:

| solver | 0.5 GHz | 1.5 GHz | 2.5 GHz | 4.0 GHz | 6.0 GHz | 8.0 GHz |
|---|---:|---:|---:|---:|---:|---:|
| gpr_bem_ref vs Nystrom | 0.4262 | 2.3559 | 1.9877 | 1.8715 | 3.2928 | 6.5110 |
| gpr_bem_mod vs Nystrom | 0.0032 | 0.0146 | 0.0529 | 0.1907 | 0.6525 | 0.9050 |
| gprMax vs Nystrom, index-0 only | 0.0084 | 0.0186 | 0.0218 | 0.1027 | 0.4426 | 16.7509 |

Star, Nystrom N=512 baseline, BEM grid 161x161, BEM N=164:

| solver | 0.5 GHz | 1.5 GHz | 2.5 GHz | 4.0 GHz | 6.0 GHz | 8.0 GHz |
|---|---:|---:|---:|---:|---:|---:|
| gpr_bem_ref vs Nystrom | 0.2897 | 1.9912 | 17.5728 | 9.9270 | 7.2737 | 11.8861 |
| gpr_bem_mod vs Nystrom | 0.0041 | 0.0087 | 0.0358 | 0.0762 | 0.2760 | 0.7484 |
| gprMax vs Nystrom, index-0 only | 0.0036 | 0.0136 | 0.0898 | 0.0831 | 0.5063 | 9.4427 |

```text
python -m pytest pytest/test_ellipse_comparison.py -s -q  ->  3 passed in 9.35s
python -m pytest pytest/test_star_comparison.py -s -q     ->  3 passed in 11.25s
python -m pytest pytest/test_circle_comparison.py -s -q   ->  3 passed in 4.45s
python -m pytest pytest/test_square_comparison.py -s -q   ->  3 passed in 9.80s
```

### Reading, without digging into why

This extends the same forward-solver picture seen on circle/square. On smooth
non-circular geometry, `gpr_bem_mod` is much closer to the qualified oracle
than the frozen first-kind `gpr_bem_ref` at every printed frequency. The low
three frequencies are clean enough to gate. The 4/6/8 GHz columns remain
diagnostic only: IBIM error grows with frequency, and gprMax is not a
high-frequency precision oracle under the checked-in 1 mm / 1.5 GHz Ricker
setup.

## Kernel-differenced quadrature, hosted on IBIM's own boundary object

2026-08-26

### Purpose

Issue 2 in `docs/legacy/ibim_error_mitigation_literature_codex.md` -- the finite
trace offset (`E ~ O(kd)`) -- is the current forward solver's structural
accuracy ceiling. `nystrom_ref` already proved the fix (difference the
exterior/interior kernels analytically before any quadrature, so every Muller
block is bounded except the hypersingular one, which is only logarithmic) on
an explicit parameterized curve, reaching ~1e-9 to 1e-10. Open question: can
that same trick be hosted against `ImplicitBoundarySamples2D` -- the
`points`/`normals`/`quadrature_weights` object IBIM's own pipeline actually
produces -- rather than an explicit curve, as a first step before tackling the
harder problem of doing it on an irregular, SDF-derived narrow-band boundary?

### Files changed

- `solvers/kernel_diff_ref/kernel_diff_tmz.py` (new) -- kernel-differenced
  Muller solve, adapted from `solvers/nystrom_ref/nystrom_tmz.py` (copied and
  restructured, not imported, so the two stay independent -- one is being
  validated, the other is the oracle validating it). Circle-only and
  perfect-sampling-only: it takes discrete `points`/`normals`/`weights` for
  everything except the diagonal self-term, which still needs the *known*
  circle parameterization sampled off-node (Kress' log-correction and the
  Richardson diagonal limit both need that). Checks its input actually is
  equidistant-angle circle nodes rather than assuming it. This is the one
  piece that would need replacing (with an Izzo/Runborg/Tsai-style corrected
  quadrature) to generalize beyond a perfect circle -- see the module
  docstring and Phase E in the literature codex.
- `solvers/kernel_diff_ref/__init__.py` (new).
- `pytest/test_circle_comparison.py` -- added a fourth row, `kernel_diff*`
  (`_kernel_diff_metrics`), always built from
  `gpr_bem_mod.perfect_circle_boundary_samples` at the same N as the
  `gpr_bem_mod` row, regardless of `--perfect-sampling`. New test
  `test_circle_kernel_diff_perfect_sampling`. Module docstring, `--perfect-
  sampling` explanation line, and `_display_discretization` updated.
- `pytest/README.md`, `solvers/README.md` -- references added, including a
  new "Other solver packages under here" table in `solvers/README.md`
  covering `nystrom_ref`/`kernel_diff_ref`/`gprmax_ref` together (previously
  undocumented as a group).

### Validation

Before wiring into the test file: `solve_transmission_on_circle`, fed the
same node positions as `nystrom_ref.build_curve(circle_parameterization(...),
168)`, reproduces `nystrom_ref.solve_transmission`'s scattered field bit-for-
bit (`reldiff = 0.0` at every checked frequency, 0.5-8 GHz) -- confirms the
adaptation is a faithful port, not a re-derivation with a different answer.

### Measured

`kernel_diff*` vs Mie, N=168 (same N as `gpr_bem_mod`), on
`gpr_bem_mod.perfect_circle_boundary_samples`:

| f (GHz) | kernel_diff err | `gpr_bem_mod` err (compressed IBIM boundary) |
|---:|---:|---:|
| 0.5 | 5.8e-13 | 3.2e-04 |
| 1.5 | 6.6e-12 | 3.6e-03 |
| 2.5 | 4.5e-11 | 3.4e-02 |
| 4.0 | 3.1e-11 | 3.0e-02 |
| 6.0 | 3.8e-09 | 1.6e-01 |
| 8.0 | 2.8e-08 | 1.8e+00 |

```text
python -m pytest pytest/test_circle_comparison.py -s -q                    ->  4 passed in 4.04s
python -m pytest pytest/test_circle_comparison.py --perfect-sampling -s -q ->  4 passed
```

### Reading, without digging into why

At the same N the production solver uses, removing the finite trace offset
takes the circle case from a percent-level, frequency-growing error (and
outright breakdown at 8 GHz, 180% relative error) to 8-13 significant digits
at every tested frequency including 8 GHz, with no re-tuning of any constant.
This is not evidence that `gpr_bem_mod`'s irregular narrow-band boundary is
fine as-is -- `kernel_diff*` runs on a perfect boundary specifically to keep
that variable out of the picture -- but it is direct, quantitative confirmation
that the trace-offset mechanism identified as Issue 2 is real, is large, and
is not conflated with node irregularity: same formulation, same N, same
frequencies, only the trace evaluation changed. The 8 GHz numbers in
particular reframe "8 GHz non-convergence" (Issue 6): on a circle, at this N,
it is not a resolution problem or an unexplained anomaly -- it is the same
`O(kd)` mechanism as every other frequency, just large enough there to look
categorically different. Whether that holds on non-circular or irregularly-
sampled boundaries is exactly the open question Issue 2's next step (a
corrected quadrature that works from discrete compressed-boundary data, no known
parameterization) would settle.

## Plan: kernel-differenced quadrature on the real (compressed) boundary

2026-08-26

Planning only -- nothing built yet, recorded before starting so the reasoning
that led here (including a discarded first idea) isn't lost.

Terminology note: this plan is not literature-accurate volume IBIM. The
tubular/narrow-band sampling remains only a boundary-extraction step; the
solver operates on the projected/compressed `ImplicitBoundarySamples2D` cloud,
using the same points as collocation, quadrature, and trace-evaluation points.
A Kublik/Chen-Tsai/Izzo-style lifted-volume quadrature remains a possible
fallback, not the current implementation target.

### Decision: a third solver package, `solvers/gpr_bem_kdiff/`

Forked from `gpr_bem_mod`, keeping `ibim_geometry.py`, `neural_sdf.py`,
`waveforms.py`, `cylinder_reference.py`, materials, and `__init__.py`
byte-identical -- same convention that already separates `ref`/`mod`: only
the formulation-specific files change (`ibim_tmz_forward.py`,
`ibim_tmz_system.py`). Geometry/SDF machinery is untouched by any of this;
only the operator assembly and trace treatment change.

### What changes from `gpr_bem_mod`'s assembly

`gpr_bem_mod` builds each of S/D/K'/T twice (once per wavenumber, via
`build_implicit_boundary_operator_family`), each time approximating the trace
by averaging potentials evaluated at `boundary_points +- offset*normals`, and
only subtracts exterior-minus-interior *after* both are separately assembled
(`ibim_tmz_system.py:172-178`). `gpr_bem_kdiff` instead differences the
exterior/interior kernels analytically first (`nystrom_ref`'s construction,
already validated), and evaluates the result directly at the boundary nodes
-- no `+-offset`, no probe points, both wavenumbers combined in one pass.

### The point of this entry: how the boundary is obtained, corrected from an
### earlier plan in this same conversation

First proposal (superseded): generalize `kernel_diff_ref`'s diagonal
self-term (currently: sample the *known analytic circle formula* off-node,
via Richardson extrapolation) using per-node curvature and an osculating-
circle local approximation, plus a reconstructed global arc-length ordering
(nearest-neighbor walk or centroid-angle sort) to extend Kress' log-weight
matrix to irregularly-spaced nodes.

**Dropped, in favor of something simpler that uses only data already
stored**, for two reasons: (1) `ImplicitBoundarySamples2D` does not even
carry a `curvature` field through `compress_implicit_boundary_band` --
reaching for it would mean modifying the compression step, new machinery for
no clear benefit; (2) the global reordering was solving a more general
problem than this one needs. Kress' circulant log-weights assume a global
equidistant parameterization because *that* method needs one; a correction
that instead asks "which other nodes are geometrically near node i" needs no
global structure, ordinary Euclidean nearest-neighbor lookup on the already-
stored `points` array answers it directly.

**Current plan.** One set of boundary points -- `gpr_bem_mod`'s real,
already-computed `build_implicit_boundary_band` -> `compress_implicit_
boundary_band` output, not `perfect_circle_boundary_samples` -- serves as the
collocation nodes, the quadrature nodes, and the trace-evaluation points, all
at once. Off-diagonal entries: the differenced kernel evaluated directly
between the two given nodes, exactly as `kernel_diff_ref` already does for
the perfect circle -- no change needed there. Diagonal entries (node i
against itself, `r=0`, unavoidably special: the differenced kernel is
analytically finite there but individually-infinite Hankel terms cannot be
subtracted in floating point at literal `r=0`) get a local Richardson-style
limit built from node i's own nearest *already-stored* neighbor(s) --
`argsort` on Euclidean distance, no continuum parameterization assumed or
required anywhere.

### This supersedes the earlier volume-IBIM reading of Phase E

An earlier version of `docs/legacy/ibim_error_mitigation_literature_codex.md` implied
that Issue 2 should move next to a lifted-volume narrow-band formulation
rather than the compressed cloud. That instruction has now been replaced. The
active plan works directly from the compressed cloud because the tubular
samples are serving only as boundary-recovery data at this stage.

The reason for the re-scope is the `kernel_diff_ref` result: once S/D/K' are
bounded by kernel-differencing (~1e-8 to 1e-13 vs the Mie series at 0.5-8 GHz
on the perfect circle, with no volumetric/lifted-singularity treatment), the
only block that still needs a singular-quadrature correction is T. The current
hypothesis is that this correction may be tractable directly on the compressed
cloud via local nearest-neighbor structure. The true volume narrow-band route
is still useful background and a fallback, but it is not the active
implementation target.

### Validation plan

Ellipse and star first (`nystrom_ref` still gives an exact yardstick there,
and `test_ellipse_comparison.py`/`test_star_comparison.py` already exist to
host the comparison) -- before the square, whose corners are the case most
likely to break a nearest-neighbor-based local correction. Nothing here is
measured yet; this entry exists so the reasoning is on record before
building starts.

## `gpr_bem_kdiff` v1 built and measured: the diagonal-only plan is not enough

2026-08-26

### What was built

`solvers/gpr_bem_kdiff/`, forked from `gpr_bem_mod` per the plan above.
Geometry/SDF/materials/waveforms/cylinder-reference files copied verbatim
(byte-identical). New `ibim_tmz_forward.py`: kernel-differenced Muller blocks
evaluated directly on `points`/`normals`/`quadrature_weights` from
`compress_implicit_boundary_band`'s real output, no `offset_distance`
anywhere. Off-diagonal entries: plain quadrature, the raw differenced kernel
times the target node's weight -- no log-singularity correction there (the
v1 scope decided two entries up). Diagonal entries: local osculating-circle
fit per node (curvature estimated from the turning of the already-trusted
normal field between the two nearest already-stored neighbours, one on each
side of the local tangent -- no new stored fields, no global ordering), fed
through the same Richardson-extrapolated diagonal-limit construction
`kernel_diff_ref` already validated, with a new `_kress_log_self_weight`
that computes only the needed self term in O(N) rather than building the
full O(N^2) circulant matrix (needed because the effective local node count
can run into the thousands on a near-straight boundary segment -- an early
version without this crashed with a 149 GiB allocation attempt on the real
compressed circle boundary). New `ibim_tmz_system.py`: combined-wavenumber
assembly (both `k_exterior`/`k_interior` differenced before assembly, not
subtracted after), direct solve only, no GPU backend, no adjoint/inverse
(out of scope, see the package docstring). `ibim_tmz_adjoint.py` and
`ibim_inverse.py` are not forked.

### Diagnostic: is the diagonal treatment itself right?

Compared `_diagonal_terms`'s output against `kernel_diff_ref`'s exact
diagonal (`_diagonal_limits` + `_kress_log_weights`, fed the true global
circle) on the *same* perfect-circle boundary, N=168, 1.5 GHz. The estimated
local radius matched the true radius to 5.8e-5 relative error (from the
finite-difference curvature estimate). S and T (hyper) diagonal values
matched to ~5e-5 relative error, consistent with that input precision --
**the local-osculating-circle machinery itself works**. D and K' (adjoint)
diagonal values did not match well in relative terms, but both the measured
and reference values are individually tiny (~1e-9 vs ~6e-13) for this
specific circle/frequency combination, and this did not show up as a
material contributor to the full-system error below -- not chased further
here.

### Measured: full solve, perfect circle and real compressed circle, N=168

| f (GHz) | perfect circle | real compressed circle | `gpr_bem_mod` (real boundary, for reference) |
|---:|---:|---:|---:|
| 0.5 | 1.9e-4 | 2.6e-4 | 3.2e-4 |
| 1.5 | 1.5e-3 | 3.1e-3 | 3.6e-3 |
| 2.5 | 7.7e-3 | 1.3e-2 | 3.4e-2 |
| 8.0 | 3.1e-1 | 1.7e+0 | (mod also breaks down here) |

### Isolating the cause: off-diagonal log-correction is not optional

Patched `kernel_diff_ref` (the already-validated, full-Kress-correction
implementation) to zero its off-diagonal Kress weights, keeping only the
self (diagonal) term -- i.e., reproducing `gpr_bem_kdiff` v1's scope inside
the already-trusted code, to isolate whether the missing piece explains the
gap. Result on the perfect circle: 15.6% / 209% / 584% / 361% at
0.5/1.5/2.5/8.0 GHz -- **worse** than `gpr_bem_kdiff`'s actual numbers above,
because dropping only the log term (keeping the smooth remainder) is a worse
approximation than using the plain undecomposed kernel the way
`gpr_bem_kdiff` actually does off-diagonal. Either way, both tests confirm
the same conclusion: correcting only the diagonal, while leaving T's
near-diagonal-but-not-at-it log behaviour uncorrected, is not sufficient to
recover `kernel_diff_ref`'s ~1e-8 to 1e-13 result. That correction is
necessary, not an optional refinement -- contrary to the hope stated in the
"Historical near-term target" section of Phase E.

### Reading, without digging into why yet

Two real, separable pieces of progress and one clear next question. Progress:
(1) the combined-wavenumber, no-offset assembly architecture works end to end
against a real `ImplicitBoundarySamples2D` boundary, not just a perfect one;
(2) the local-osculating-circle diagonal treatment is itself accurate (S/T
diagonal values track the input curvature-estimate precision, not a larger
independent error). Open question: the off-diagonal near-neighbour
log-singular correction for T, the piece explicitly deferred when this was
scoped two entries up, turns out to be load-bearing rather than a nice-to-
have -- `gpr_bem_kdiff` v1 lands roughly at `gpr_bem_mod`'s current accuracy
(same order of magnitude, not clearly better) rather than near
`kernel_diff_ref`'s perfect-circle result, and is worse at 8 GHz. Building
that correction for an irregularly-spaced cloud (no global ordering assumed)
is the next real piece of work, not yet started.

## `gpr_bem_kdiff` wired into the pytest comparison files

2026-08-26

### Files changed

- `pytest/test_circle_comparison.py` -- new `gpr_bem_kdiff` row (`_kdiff_metrics`),
  gated loosely at 0.5/1.5/2.5 GHz only (`KDIFF_MAX_RELATIVE_ERROR`), full
  0.5-8 GHz sweep printed by `test_circle_kdiff_real_boundary`. Respects
  `--perfect-sampling` the same way ref/mod do.
- `pytest/test_ellipse_comparison.py`, `pytest/test_star_comparison.py` --
  same row (`_kdiff_metrics`, no perfect-sampling mode for a non-circular
  shape), printed only by `test_ellipse_kdiff_real_boundary` /
  `test_star_kdiff_real_boundary`, no gate yet -- first measurement on these
  shapes, see below for why a gate would be premature.
- All three: `_display_discretization` gained a `kdiff_local -> "kdiff2"` case.

One incidental debugging note: an early full-suite run appeared to hang for
25+ minutes at ~1100% CPU. Killed and re-ran in isolation -- resolved
cleanly in under 10s each. Root cause was a stale background pytest process
left over from earlier in the session contending for the same cores, not a
bug in this code; flagging only because it looked alarming at the time.

### Measured: `gpr_bem_kdiff` vs the existing oracle, real compressed boundary

| shape | oracle | N | 0.5 GHz | 1.5 GHz | 2.5 GHz | 4.0 GHz | 6.0 GHz | 8.0 GHz |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| circle | Mie | 168 | 2.6e-4 | 3.1e-3 | 1.3e-2 | 2.2e-2 | 9.5e-2 | 1.7e+0 |
| ellipse | Nystrom | 120 | 4.3e-3 | 3.8e-2 | 5.7e-2 | 1.4e-1 | 5.6e-1 | 6.0e-1 |
| star | Nystrom | 164 | 1.1e-2 | 2.0e-2 | 7.3e-2 | 1.4e-1 | 2.6e-1 | 7.6e-1 |

Same row, `gpr_bem_mod` for comparison (same boundary, same N per shape):

| shape | 0.5 GHz | 1.5 GHz | 2.5 GHz | 4.0 GHz | 6.0 GHz | 8.0 GHz |
|---|---:|---:|---:|---:|---:|---:|
| circle | 3.2e-4 | 3.6e-3 | 3.4e-2 | 3.0e-2 | 1.6e-1 | 1.8e+0 |
| ellipse | 3.2e-3 | 1.5e-2 | 5.3e-2 | 1.9e-1 | 6.5e-1 | 9.0e-1 |
| star | 4.1e-3 | 8.7e-3 | 3.6e-2 | 7.6e-2 | 2.8e-1 | 7.5e-1 |

### Reading: the missing off-diagonal correction matters more as curvature varies more

On the circle, `gpr_bem_kdiff` is at or slightly better than `gpr_bem_mod`
at every frequency except 8 GHz, where the two are comparable. On the
ellipse and star, `gpr_bem_kdiff` is consistently *worse* than `gpr_bem_mod`
at low-to-mid frequency (roughly 2-3x at 0.5-1.5 GHz), converging toward
comparable or occasionally better at the high-error frequencies. The circle
has constant curvature everywhere; the ellipse's varies smoothly; the star
(5 lobes, amplitude 0.25) varies the most. That ordering matches the error
ordering exactly, which is consistent with (not proof of, but consistent
with) the already-identified cause: the off-diagonal near-neighbour
log-singular correction for the hypersingular block is still missing, and a
local diagonal-only fix has less to compensate for on a constant-curvature
shape than a rapidly-varying one. No gate was added on ellipse/star for this
reason -- the numbers are informative, not yet a claim of correctness worth
enforcing.

Nothing here changes the conclusion from the previous entry: the off-diagonal
correction is the next real piece of work.

### Square, added too: the anticipated corner failure, confirmed

`pytest/test_square_comparison.py` got the same row (`_kdiff_metrics`,
`test_square_kdiff_real_boundary`, index-0 pair vs gprMax, printed only, no
gate -- `_format_table` also needed a `None`-safe offset column, same fix
`test_circle_comparison.py` already had). Result: **12.30 / 4.21 / 3.27 /
24.03 / 14.16 / 8.62** relative error at 0.5-8 GHz -- catastrophically worse
than `gpr_bem_mod`'s 0.02-1.26 on the same case. This is exactly the failure
this session's own validation plan named in advance ("square last, because
corners are the most likely place for a nearest-neighbor-based local
correction to break," logged two entries up). A true corner is an SDF-
gradient discontinuity, not merely high curvature the way the star's lobes
are -- curvature is undefined there, so the local-osculating-circle diagonal
fit produces meaningless values for nodes near it, and that corrupts the
whole linear solve, not just those nodes' own rows. Confirms, doesn't just
suggest, that the local-curvature diagonal treatment needs explicit corner
handling (or the boundary needs to avoid placing a node's local fit across a
corner) before this generalizes past smooth shapes -- consistent with, and
now measured evidence for, why the codex places corner-safety inside the
"future/fallback: true volume IBIM" escape hatch rather than assuming the
compressed-cloud route covers it.

## `gpr_bem_qbx` built and measured: QBX near-diagonal band, forked from `gpr_bem_kdiff`

2026-08-27

### Motivation

`docs/legacy/ibim_error_mitigation_literature_codex.md` Section 1.3 named Quadrature
by Expansion (Klockner, Barnett, Greengard, O'Neil, 2013) as "a serious
alternative to the current stand-off method," but explicitly deferred it
until a validated high-order reference existed -- `nystrom_ref` now fills
that role. Separately, `gpr_bem_kdiff`'s own module docstring flags an
unaddressed gap: the off-diagonal-but-*nearby* log-singular behaviour of the
hypersingular block T has no correction, only the exact diagonal does. Both
point at the same experiment: does QBX, applied to that specific near-
diagonal band, close the gap between `gpr_bem_kdiff` and `gpr_bem_mod` on
curved (ellipse/star) targets that the previous two entries measured?

### Files added

A fourth solver package, `solvers/gpr_bem_qbx/`, forked from `gpr_bem_kdiff`
(same convention as every fork in this directory -- geometry/SDF files
byte-identical, only the formulation files diverge). Only
`ibim_tmz_forward.py` changed relative to `gpr_bem_kdiff`, plus one new file:

- `qbx_kernels.py` (now archived as `scratchpad/qbx_legacy_near_band.py`) --
  the historical QBX construction. Graf's addition theorem gives a
  local cylindrical-harmonic expansion of the kernel about an off-curve
  expansion center, truncated at a finite order; the single-layer block is
  that expansion directly, the other three come from differentiating it once
  on the source side (folded into the coefficients) and once on the target
  side (analytic, since the expansion is smooth wherever it's evaluated) --
  rather than deriving four separate addition-theorem identities by hand.
  Evaluating from both sides of the curve and averaging recovers the
  principal-value boundary operator via the Plemelj jump relations, the same
  "evaluate from both sides" idea `gpr_bem_mod`'s finite-offset trace uses,
  except QBX evaluates a convergent local expansion instead of approximating
  the trace by the physical field value, so it does not carry `gpr_bem_mod`'s
  structural `O(kd)` stand-off error.
- `ibim_tmz_forward.py` -- unchanged except `build_kdiff_operator_blocks` now
  calls `apply_qbx_band_correction` after filling the plain differenced-kernel
  matrix and the (unchanged) diagonal, to overwrite a band of near-diagonal
  entries with QBX rows.

### Design note, measured not assumed: the obvious radius guess is backwards

First attempt sized the expansion radius `r` at a few times the local node
spacing `h` (the "the coefficient sum needs several nodes to see" reasoning)
and tried to fold the exact diagonal into the same QBX evaluation. Both were
wrong, and both were caught by direct measurement rather than by inspection:

- **Exact diagonal**: evaluating QBX with the source node coincident with the
  target (the literal diagonal entry) puts the two points at *exactly* equal
  distance from the expansion center -- precisely the boundary of Graf's
  addition theorem's convergence, not strictly inside it. Measured result: the
  double-layer and adjoint blocks collapse to numerical noise (~1e-14) at zero
  separation instead of the true, generically nonzero, curvature-dependent
  limit -- not a convergence problem fixable by more terms, a genuine
  degeneracy. No radius fixes this, so the diagonal keeps `gpr_bem_kdiff`'s
  legacy `_diagonal_terms` unchanged. Its underlying limit machinery was
  validated on an exact circle; the fitted per-node approximation on irregular
  noncircular/corner geometry remains a separate limitation. QBX is only ever
  applied to genuinely distinct neighbour nodes.
- **Radius vs. spacing**: for a fixed source at arc-distance `s` from the
  target, `|y-c|/|x-c| - 1 ~ s^2 / (2 r^2)` -- so *increasing* `r` at fixed
  `s` pushes the nearest neighbour's distance ratio *closer* to 1 (slower
  series convergence), not further from it. At `r ~ 3h` the nearest neighbour
  sits at distance-ratio ~1.06 and does not converge even at 40 expansion
  terms (~1 correct digit). At `r ~ 0.5h` (smaller than the spacing) the same
  neighbour sits at ratio ~2.2 and converges to 6+ digits by order 20,
  matching the closed-form `_difference_kernels` result on the tested
  well-separated pair to the same precision. Shipped defaults:
  `radius_spacing_factor=0.5`, `radius_curvature_factor=0.2` (upper bound
  from local radius of curvature, unchanged reasoning from `gpr_bem_kdiff`'s
  own radius clipping), `expansion_order=20`, `band_factor=8`.

### Validation: QBX rows reproduce the closed-form kernel

Before wiring into the solve, checked `_qbx_diff_row` against
`_difference_kernels` directly on a unit circle, well-separated pair
(46 degrees apart), increasing expansion order: relative error 4.4e-1 at
order 2, 7.6e-4 at order 8, 2.4e-6 at order 12, down to 1e-13 at order 20,
across all four blocks (S, D, K', T). This is strong evidence the Graf-
theorem coefficient and target-side derivative formulas (independently
re-derived here, not copied from `_difference_kernels`) have the right signs
and prefactors.

### Measured: `gpr_bem_qbx` vs `gpr_bem_kdiff` vs `gpr_bem_mod`, same boundary/N

Same ring-scan case as the previous two entries, oracle Mie series (circle)
or `nystrom_ref` (ellipse/star):

| shape | N | solver | 0.5 GHz | 1.5 GHz | 2.5 GHz | 4.0 GHz | 6.0 GHz | 8.0 GHz |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| circle | 168 | `gpr_bem_mod` | 3.2e-4 | 3.6e-3 | 3.4e-2 | 3.0e-2 | 1.6e-1 | 1.8e+0 |
| circle | 168 | `gpr_bem_kdiff` | 2.6e-4 | 3.1e-3 | 1.3e-2 | 2.2e-2 | 9.5e-2 | 1.7e+0 |
| circle | 168 | `gpr_bem_qbx` | 2.6e-4 | 3.1e-3 | 1.3e-2 | 2.2e-2 | 9.5e-2 | 1.7e+0 |
| ellipse | 120 | `gpr_bem_mod` | 3.2e-3 | 1.5e-2 | 5.3e-2 | 1.9e-1 | 6.5e-1 | 9.1e-1 |
| ellipse | 120 | `gpr_bem_kdiff` | 4.3e-3 | 3.8e-2 | 5.7e-2 | 1.4e-1 | 5.6e-1 | 6.0e-1 |
| ellipse | 120 | `gpr_bem_qbx` | 4.3e-3 | 3.8e-2 | 5.7e-2 | 1.4e-1 | 5.6e-1 | 6.0e-1 |
| star | 164 | `gpr_bem_mod` | 4.1e-3 | 8.7e-3 | 3.6e-2 | 7.6e-2 | 2.8e-1 | 7.5e-1 |
| star | 164 | `gpr_bem_kdiff` | 1.1e-2 | 2.0e-2 | 7.3e-2 | 1.4e-1 | 2.6e-1 | 7.6e-1 |
| star | 164 | `gpr_bem_qbx` | 1.1e-2 | 2.0e-2 | 7.3e-2 | 1.4e-1 | 2.6e-1 | 7.6e-1 |

`gpr_bem_qbx` is numerically indistinguishable from `gpr_bem_kdiff` at every
frequency on all three shapes, including the star (curvature up to ~190,
where the missing correction was expected to matter most). Direct inspection
of the assembled matrices (star boundary, 4 GHz) confirms the band
correction genuinely executes -- 3 to 11 neighbours corrected per node,
band entries actually overwritten -- but the QBX-corrected values differ
from the plain-quadrature values they replaced by only ~1e-8 to 1e-11
relative (max over all four blocks), against matrix entries of order
1e-3 to 1e1.

### Reading: a genuine negative result, not a wiring failure

The hypothesis that motivated this build -- that `gpr_bem_kdiff`'s missing
off-diagonal-but-nearby log-singular correction for T explains its gap
against `gpr_bem_mod` on ellipse/star -- is not supported by this
measurement. The tested row algebra matches one separated circle pair and the
near-band path genuinely executes. Same-node QBX converges back to the same
pointwise distinct-node kernels and leaves the solve unchanged. This rules out
pointwise evaluation error in those replaced entries as the dominant cause at
the tested resolutions. It does **not** establish the accuracy of the
underlying near-singular quadrature or isolate the local diagonal as the
remaining cause. Those questions required the later operator-level and
source/target probes recorded below. The square/corner case was not tested in
this particular near-band experiment.

## Revised QBX diagonal/T-operator probe: bounded diagonals help locally, T-QBX needs source oversampling

2026-08-31

### Motivation

The previous `gpr_bem_qbx` experiment applied QBX only to a near-diagonal band
of distinct source/target pairs and deliberately left the exact diagonal
unchanged. That did not move the solve. The revised hypothesis splits the
four Muller difference blocks by their actual diagonal behaviour:

- `S_diff`, `D_diff`, and `Kp_diff` have finite Muller-differenced pointwise
  self limits. These can legitimately be tested as `w_i * QBX_self_limit`.
- `T_diff` retains a residual logarithmic singularity. A finite physical
  `T_diff(x_i, x_i)` should not be manufactured. The correct target is the
  integrated operator action `(T_diff mu)(x_i)`.

The scratchpad driver built for this is:

```bash
/home/drdeng/miniconda3/envs/up2you/bin/python scratchpad/qbx_diagonal_probe.py
```

The default system `python` does not have `torch`, so the `up2you` environment
was used for all runs.

### Files changed

- `scratchpad/qbx_diagonal_probe.py`
  - Builds the same circle/ellipse/star geometries used by the comparison
    tests: circle `N=168`, ellipse `N=120`, star `N=164`.
  - Uses the same 0.5/1.5/2.5 GHz frequencies, material constants, ring
    source/receiver layout, and Mie/Nystrom references as the existing tests.
  - Prints side-by-side solve rows for `gpr_bem_mod`, `gpr_bem_kdiff`, current
    `gpr_bem_qbx`, and scratchpad-only diagnostic variants.
  - Probes one-source QBX self series for `S_diff`, `D_diff`, `Kp_diff`, and
    `T_diff`.
  - Compares bounded pointwise diagonals against parameterized `nystrom_ref`
    finite limits.
  - Builds full-row operator-level QBX matrices for the `T` block, including
    the self source in the coefficient quadrature.
  - Adds a parameterized diagnostic solve where oversampled source densities
    are obtained by Fourier interpolation.
- `scratchpad/qbx_diagonal_probe_self_series.csv`
  - Generated detailed self-series records for the default three-shape,
    three-frequency run.

No production solver package was changed.

### Diagnostic variants

`EXP_BOUNDED_DIAG_QBX`

- Forks the `gpr_bem_kdiff` assembly inside the scratchpad driver only.
- Leaves every off-diagonal direct differenced-kernel entry unchanged.
- Replaces only the `S_diff`, `D_diff`, and `Kp_diff` diagonal entries with
  weighted QBX self limits.
- Keeps the old osculating-circle `T` diagonal.

`EXP_T_OPERATOR_QBX`

- Keeps old `S_diff`, `D_diff`, and `Kp_diff` diagonals.
- Replaces the whole `T` row by full-row operator-level QBX over all source
  nodes, including `j == i`.
- The resulting `T_qbx[i,i]` is treated only as an algebraic quadrature
  contribution, not as a physical pointwise kernel value.

`EXP_ALL_DIAG_FIX`

- Combines bounded `S/D/Kp` QBX self diagonals with full-row `T` operator QBX.

### Bounded self-series and diagonal comparison

The one-source self probes match the revised mathematical expectation:

- `S_diff` gives a stable finite value, though the conservative plateau flag
  is strict enough that higher frequency/radius combinations sometimes print
  `no` at `1e-5` to `1e-4` relative tail span.
- `D_diff` and `Kp_diff` are near zero in these symmetric sampled locations;
  absolute spans are at machine scale, while relative spans can look large
  because the denominator is also machine scale.
- `T_diff` shows the expected non-plateau drift. The script prints it for
  visibility but never treats it as a finite pointwise diagonal.

The direct unweighted diagonal comparison against parameterized `nystrom_ref`
shows that the QBX bounded diagonals are much closer to the finite pointwise
reference than the osculating construction for `S_diff`. Representative
0.5 GHz values:

| shape/location | block | abs osc-ref | abs qbx-ref |
|---|---|---:|---:|
| circle/east | `S_diff` | 1.5e-4 | 2.8e-8 |
| ellipse/major tip | `S_diff` | 2.7e-4 | 8.3e-8 |
| ellipse/intermediate | `S_diff` | 3.1e-4 | 2.5e-8 |
| star/lobe tip | `S_diff` | 2.3e-4 | 6.2e-8 |
| star/valley | `S_diff` | 2.0e-3 | 2.2e-8 |

For `D_diff` and `Kp_diff`, the tested reference values are often near zero,
so relative errors are not meaningful. Absolute QBX errors are also near the
reference magnitude, while osculating absolute errors are typically larger.

### Solve result: bounded diagonals alone are not the main mechanism

Default full scratchpad solve, same real compressed boundaries and same
Mie/Nystrom references:

| shape | solver | 0.5 GHz | 1.5 GHz | 2.5 GHz |
|---|---|---:|---:|---:|
| circle | `gpr_bem_kdiff` | 2.6157e-4 | 3.0594e-3 | 1.2799e-2 |
| circle | `EXP_BOUNDED_DIAG_QBX` | 2.4213e-4 | 2.9015e-3 | 1.2365e-2 |
| ellipse | `gpr_bem_kdiff` | 4.3220e-3 | 3.7559e-2 | 5.7334e-2 |
| ellipse | `EXP_BOUNDED_DIAG_QBX` | 4.2628e-3 | 3.7101e-2 | 5.7088e-2 |
| star | `gpr_bem_kdiff` | 1.0854e-2 | 1.9658e-2 | 7.3288e-2 |
| star | `EXP_BOUNDED_DIAG_QBX` | 8.0292e-3 | 1.2013e-2 | 7.4883e-2 |

This is useful but not decisive:

- Circle improves slightly, which is acceptable but not a large control shift.
- Ellipse barely moves.
- Star improves at 0.5 and 1.5 GHz, but slightly worsens at 2.5 GHz.

Conclusion: replacing only the bounded `S/D/Kp` osculating diagonals does not
explain the remaining curved-shape gap.

### Same-source full-row `T_QBX` fails the circle control

The first full-row `T_QBX` assembly used the existing `N` source nodes directly.
This is the most literal dense-matrix replacement, but it is not accurate
enough:

| circle 0.5 GHz | relative scattered-field error |
|---|---:|
| `gpr_bem_kdiff` | 2.6157e-4 |
| `EXP_BOUNDED_DIAG_QBX` | 2.4213e-4 |
| `EXP_T_OPERATOR_QBX` | 6.6877e-3 |
| `EXP_ALL_DIAG_FIX` | 6.6974e-3 |

This is a hard circle-control failure. It should not be interpreted as a
physical conclusion about the diagonal hypothesis. It means the same-source
`T_QBX` discretization is underresolved.

The operator-action probe confirms the same point on a parameterized circle at
the same nominal `N=168`:

| T action, circle 0.5 GHz | max relative action error |
|---|---:|
| old same-N `T` | 6.807e-3 |
| same-source `T_QBX`, `rho/h=0.5`, `P=20` | 1.438e-1 |

### Source oversampling fixes the T operator

The full-row `T_QBX` coefficient kernels are nonsingular because the expansion
center is off the curve, but they are sharply varying near the source point
closest to the center. Source oversampling is therefore not optional for this
operator-level construction.

Circle action probe, 0.5 GHz:

| rho/h | P | source factor | max T-QBX action error |
|---:|---:|---:|---:|
| 1.0 | 16 | 1x | 9.026e-2 |
| 1.0 | 16 | 4x | 1.562e-3 |
| 1.0 | 16 | 8x | 1.846e-9 |
| 1.0 | 24 | 8x | 1.879e-6 |
| 1.0 | 32 | 8x | 1.363e-4 |

This shows the expected useful window: source oversampling lowers the
coefficient quadrature error, but simply increasing `P` eventually makes the
result worse.

At `rho/h=1.0`, `P=16`, `8x` source oversampling, this ideal ordered
analytic-curve T-action probe is excellent on the tested shapes over
0.5--2.5 GHz:

| shape | 0.5 GHz | 1.5 GHz | 2.5 GHz |
|---|---:|---:|---:|
| circle | 1.846e-9 | 3.005e-10 | 4.376e-10 |
| ellipse | 1.106e-9 | 1.018e-9 | 1.276e-9 |
| star | 1.488e-7 | 8.520e-8 | 1.233e-7 |

### Parameterized diagnostic solve with oversampled T-QBX

To test whether the operator-level `T_QBX` is viable when source quadrature is
handled properly, the scratchpad driver adds a parameterized solve:

- `S/D/Kp` come from `nystrom_ref` at the nominal same `N`.
- `T` is replaced by full-row QBX evaluated on an 8x oversampled source curve.
- The unknown Neumann density is prolonged from nominal nodes to oversampled
  source nodes by global Fourier interpolation.

This is diagnostic-only because it relies on global parameter ordering.

Results at `rho/h=1.0`, `P=16`, `8x` source:

| shape | N | 0.5 GHz | 1.5 GHz | 2.5 GHz | max residual | max cond |
|---|---:|---:|---:|---:|---:|---:|
| circle | 168 | 5.2186e-11 | 3.9167e-10 | 2.0953e-9 | 3.6e-15 | 1.21e4 |
| ellipse | 120 | 2.7968e-10 | 2.4210e-9 | 4.3124e-9 | 3.9e-15 | 1.39e4 |
| star | 164 | 5.5506e-9 | 4.8362e-8 | 2.2117e-7 | 1.1e-14 | 2.40e4 |

A 1x source control on the same parameterized circle is much worse:

| circle 0.5 GHz | source factor | error |
|---|---:|---:|
| parameterized `T_QBX` solve | 1x | 2.5999e-3 |
| parameterized `T_QBX` solve | 8x | 5.2186e-11 |

Within this structured circle control, the 1x-to-8x change isolates coefficient
quadrature rather than the target-side derivative formula or Müller signs. It
does not pin the production compressed-cloud forward gap to source quadrature.

### Current reading

The revised diagnosis is now sharper:

1. `S/D/Kp` bounded QBX self diagonals are numerically sensible and improve
   direct diagonal comparisons, especially for `S_diff`.
2. Those bounded diagonals alone do not explain the remaining curved-shape
   forward error.
3. `T` must be treated as an operator, not as a finite pointwise diagonal.
4. At the tested node counts/radius/order, operator-level `T_QBX` is accurate
   only after coefficient-quadrature oversampling.
5. A same-`N` dense matrix replacement for `T` is a dead end. It fails the
   circle negative control.
6. A parameterized, globally ordered smooth-curve solve with Fourier density
   prolongation strongly validates the mathematical `T_QBX` construction over
   the tested 0.5--2.5 GHz range.
7. The Graf/T derivative convention is not the immediate blocker. The later
   probes below test whether source geometry/transfer alone can bridge this
   result to the compressed targets.

### Historical next steps (now superseded)

These source-side follow-ups were the next experiments at this point in the
chronology. They were superseded by the five-shape full-row results and the
decision in [`qbx_closure.md`](qbx_closure.md); do not continue them as the
current forward-solver plan.

Do not move the current same-source `EXP_T_OPERATOR_QBX` into production.

The next productive path is to build a separate diagnostic for the real
compressed IBIM boundary that supplies oversampled source nodes and density
prolongation:

1. For smooth single-component validation shapes, recover a local/global
   ordering of the compressed boundary only for diagnosis, not as final
   production architecture.
2. Build oversampled source points/normals/weights by interpolating the
   compressed geometry, or by resampling the known analytic level set for
   circle/ellipse/star while keeping the target nodes fixed.
3. Build an interpolation/prolongation matrix from target unknowns to
   oversampled source densities.
4. Re-run `EXP_T_OPERATOR_QBX` on the real compressed target nodes with the
   oversampled source quadrature.
5. If that passes the circle and improves ellipse/star, then design the
   production version:
   - `S/D/Kp`: direct off-diagonals plus converged finite QBX self diagonals.
   - `T`: direct far interactions plus local operator-level QBX on an
     oversampled source neighbourhood.
6. Only after that validation, remove the osculating-circle Richardson and
   Kress self-weight machinery. Curvature/spacing should remain only as QBX
   radius-safety inputs.

If no reliable density prolongation can be built for the unordered compressed
IBIM boundary, then the fatal conclusion is architectural: accurate
operator-level `T_QBX` requires more boundary structure than the current
compressed point cloud exposes.

## Raw SDF-band source oversampling for operator-level T-QBX

Date: 2026-08-31

This follow-up keeps the experiment reversible: only
`scratchpad/qbx_diagonal_probe.py` was extended.  No production solver code was
changed.

### What was added

The scratchpad now has two opt-in probes:

- `--ibim-source-t-action`
- `--ibim-source-t-solve`

Both keep the compressed IBIM boundary as the target grid, but replace the
operator-level `T_QBX` source quadrature by raw SDF-band samples from a finer
Cartesian grid.

The source grid factor `f` is implemented as:

```text
grid_shape_f = f * (grid_shape - 1) + 1
```

So the physical grid spacing shrinks by `f`.  With the default
`build_implicit_boundary_band` settings, the cosine delta and retained band
half-widths also remain fixed in fine-grid cell units, so the number of raw
band samples grows approximately by `f`, not by `f^2`.

For each source grid:

- call the existing `build_implicit_boundary_band`;
- use `band.projected_points` as source points;
- use `band.normals` as source normals;
- use `band.quadrature_weights` as source weights;
- optionally reproject source points/normals once more to the SDF zero set with
  `--ibim-reproject-sources`.

For target points:

- the default uses the existing compressed points/normals;
- `--ibim-reproject-targets` reprojects those compressed points back to the SDF
  zero set and refreshes normals.

For a matrix solve, the Neumann density still lives on the compressed target
grid.  The diagnostic therefore builds a local inverse-distance prolongation
matrix `P_idw` and assembles:

```text
T_QBX = T_rect(raw_sources -> compressed_targets) @ P_idw
```

This is intentionally crude.  It is a diagnostic for whether source
oversampling alone is sufficient, not a final density interpolation scheme.

### Raw-source counts

At the existing `161 x 161` base grid:

| shape | factor | raw band samples | compressed samples | measure |
|---|---:|---:|---:|---:|
| circle | 1 | 856 | 168 | 3.141277e-1 |
| circle | 2 | 1668 | 336 | 3.141664e-1 |
| circle | 4 | 3364 | 336 | 3.141541e-1 |
| circle | 8 | 6712 | 664 | 3.141583e-1 |
| ellipse | 1 | 838 | 120 | 3.391145e-1 |
| ellipse | 2 | 1694 | 256 | 3.390847e-1 |
| ellipse | 4 | 3350 | 256 | 3.391021e-1 |
| ellipse | 8 | 6734 | 496 | 3.390934e-1 |
| star | 1 | 670 | 164 | 4.147764e-1 |
| star | 2 | 1342 | 176 | 4.149577e-1 |
| star | 4 | 2678 | 350 | 4.149428e-1 |
| star | 8 | 5398 | 688 | 4.147308e-1 |

### Projection/clearance issue

Using compressed targets and raw projected sources directly produced bad QBX
clearance.  The clearest failure was the star:

| shape | max `|phi(target)|` | factor 4 min clearance |
|---|---:|---:|
| circle | 1.12e-5 | 0.984 |
| ellipse | 4.55e-5 | 0.926 |
| star | 4.39e-4 | 0.639 |

The compressed samples are weighted averages of projected band points, so they
are not guaranteed to remain on the SDF zero set.  This matters for QBX because
the expansion disk is built from the target point and normal, while the source
quadrature lies on the projected source curve.

Reprojecting target and source points improved the geometry:

| shape | max `|phi(target)|` after reproject | factor 4 min clearance |
|---|---:|---:|
| circle | 6.25e-17 | 1.000 |
| ellipse | 1.56e-8 | 1.000 |
| star | 4.41e-6 | 0.997 |

The remaining `bad` counts are mostly equality/tolerance-level points on the
QBX boundary, plus a small residual star clearance issue.

### Operator-action results

At 0.5 GHz, `P=16`, `rho/h=0.5`, using the existing compressed target grid:

Without reprojecting target/source geometry:

| shape | source factor | old T action | qbx analytic density | qbx IDW density |
|---|---:|---:|---:|---:|
| circle | 1 | 2.271e-2 | 4.177e-2 | 4.168e-2 |
| circle | 2 | 2.271e-2 | 1.615e-2 | 1.596e-2 |
| circle | 4 | 2.271e-2 | 4.314e-3 | 4.275e-3 |
| circle | 8 | 2.271e-2 | 5.402e-4 | 1.920e-3 |
| ellipse | 4 | 1.475e-2 | 1.406e-2 | 1.396e-2 |
| star | 4 | 4.826e-2 | 1.780e-1 | 1.781e-1 |

With both target and source reprojected:

| shape | source factor | old T action | qbx analytic density | qbx IDW density |
|---|---:|---:|---:|---:|
| circle | 8 | 2.234e-2 | 3.154e-4 | 1.940e-3 |
| ellipse | 4 | 1.006e-2 | 2.199e-3 | 2.499e-3 |
| ellipse | 8 | 1.006e-2 | 6.546e-4 | 2.556e-3 |
| star | 4 | 9.653e-3 | 4.445e-3 | 4.474e-3 |
| star | 8 | 9.653e-3 | 3.893e-3 | 3.854e-3 |

This is the useful split:

- analytic source densities show that raw SDF-band source quadrature can make
  operator-level `T_QBX` substantially better;
- IDW density prolongation already limits ellipse at factor 8;
- invalid or marginal QBX clearance can completely mask the expected
  improvement, especially on the star before reprojecting.

### Forward solve with raw-source T-QBX and IDW prolongation

At 0.5 GHz, `P=16`, `rho/h=0.5`, reprojecting both targets and sources:

| shape | source factor | solve error | max residual | max condition |
|---|---:|---:|---:|---:|
| circle | 4 | 2.2044e-4 | 5.0e-16 | 1.24e2 |
| circle | 8 | 1.9594e-4 | 4.8e-16 | 1.24e2 |
| ellipse | 4 | 5.7300e-3 | 4.5e-16 | 9.41e1 |
| ellipse | 8 | 5.7247e-3 | 4.4e-16 | 9.40e1 |
| star | 4 | 7.0832e-3 | 4.6e-16 | 7.28e1 |
| star | 8 | 7.6924e-3 | 4.5e-16 | 7.27e1 |

Compared with the earlier 0.5 GHz compressed-boundary solve errors:

| shape | kdiff | bounded S/D/Kp QBX | raw-source T-QBX solve |
|---|---:|---:|---:|
| circle | 2.6157e-4 | 2.4213e-4 | 1.9594e-4 |
| ellipse | 4.3220e-3 | 4.2628e-3 | 5.7247e-3 |
| star | 1.0854e-2 | 8.0292e-3 | 7.0832e-3 |

The circle control passes, and star improves.  Ellipse worsens in the solve
despite a strong analytic-density action improvement.  Since the ellipse
action with analytic source density improves from `2.199e-3` to `6.546e-4`
when going from 4x to 8x, but the IDW/solve result does not improve, the
current bottleneck is density prolongation/target-source consistency, not raw
source count.

### Current interpretation

The simple SDF-band oversampling strategy is good enough to test the main
operator-level `T_QBX` hypothesis, but only after two details are respected:

1. compressed targets and raw sources must be brought onto the same SDF zero
   set, or QBX clearance can be invalid;
2. the density prolongation from compressed targets to oversampled sources must
   be better than local Euclidean IDW.

The cheated parameterized experiment supplied both automatically: exact
geometry and Fourier density prolongation.  This raw SDF-band experiment
replaces the geometry part reasonably well after re-projection, but not the
density prolongation part.

### Historical next step (completed by the following probe)

This proposed ordered-transfer diagnostic was carried out in the “Perfect
boundary knowledge” entry below. It did not remove the ellipse/star floor.

The next diagnostic should replace IDW with a tangential/ordered interpolation
for smooth single-component compressed boundaries:

- recover local or global boundary order for circle/ellipse/star diagnostics;
- build an arclength-like coordinate on the compressed targets;
- interpolate density to raw projected source samples in that coordinate;
- rerun the raw-source `T_QBX` solve.

If that fixes ellipse while preserving the circle and star improvements, then
the production problem is specifically: expose enough boundary structure to
prolong densities accurately.  If it does not, the next suspects are remaining
QBX clearance on the star and the mismatch between reprojected target geometry
and the old direct `S/D/Kp`/receiver quadrature.

## gprMax reference switched to genuinely single-frequency (`contsine`) runs, for a fair timing comparison against QBX

Date: 2026-09-01

### Motivation

Discussion of the operator-level `T_QBX` forward-solve timing above (ideal
8x-oversampled solve: 6.9-39.2 s per shape/frequency, depending on
oversampling factor -- see the "ideal source oversampling" section) raised the
question of whether that is competitive with the FDTD reference this project
also uses. The only gprMax timing on record at that point
(`docs/gprmax_reference_study.md`, ~8.7 s/variant) was for a *broadband*
Ricker-pulse run that happened to cover the frequency being compared, not a
solve of that one frequency -- not a fair basis for the comparison.

### What changed

`solvers/gprmax_ref/` gained a `--frequency-mode harmonic` (now the default),
driving gprMax's built-in `contsine` continuous-sine-wave source at exactly
the target frequency instead of a broadband Ricker pulse read off by DFT. Full
mechanism, the transit/settle/ramp/extraction time budget, a cross-platform
cache-key rounding fix, and per-shape measured cell sizes are documented in
`docs/gprmax_reference_study.md`'s 2026-09-01 update; only the parts relevant
to the QBX timing comparison are repeated here.

### Validation

Circle's harmonic-mode error against the Mie series reproduces the old
broadband-Ricker numbers at every frequency (0.5-8 GHz, within ~1% relative of
each other at every point) -- the harmonic method is measuring the same
physics, not a cheaper but biased substitute. See
`docs/gprmax_reference_study.md` for the full comparison table.

### Measured: gprMax (harmonic, one frequency at a time) vs BEM forward solves

`pytest/results/aggregate_metrics.md` now opens with a "Wall-Clock Comparison"
table, regenerated by `pytest/test_aggregate_comparison_results.py`, with one
column per shape and one row per solver. That generated file, rather than a
copied table here, is the canonical source for the measured values because
BEM timings vary from run to run. It labels coverage explicitly: all six
frequencies and the full 24-pair ring for BEM, but one representative pair per
frequency for the cached gprMax row.

### Reading, against the QBX numbers above -- and the pair-count catch

The "Wall-Clock Comparison" table's `gprmax (1 pair)` row is **not** a 24-pair number.
gprMax's cache holds only one representative Tx/Rx pair per frequency (exact
by rotational symmetry for the circle, index-0 by convention for the other
shapes -- see `docs/gprmax_reference_study.md`); 124.83 s for circle is that
one pair, summed over the six cached frequencies (so roughly 21 s per
frequency for one pair -- matches the per-frequency numbers `run_case.py`
printed at generation time, e.g. circle 0.5 GHz was 35.45 s, 8 GHz was
24.64 s). The BEM rows in the same table already solve the full 24-pair ring
per frequency, because a BEM
factorization handles every Tx/Rx pair as an extra right-hand-side column
almost for free.

For a nonsymmetric shape, a different Tx/Rx pair requires a different gprMax
simulation, so matching the BEM rows' 24-pair coverage would require more work
than the cached one-pair row. That full workload was not measured. The circle
is an important exception: rotational symmetry makes its one cached pair
representative of the whole ring, so multiplying the circle timing by 24 is
not a fair equal-work normalization. The earlier `24 * 35.45 s` extrapolation
and resulting “QBX is roughly 20x faster” statement are therefore withdrawn.
The aggregate report retains only raw measured totals with coverage labels; it
does not establish an equal-work gprMax/QBX speed ratio. The QBX closeout
instead compares QBX with `mod` and `kdiff`, whose BEM workloads are identical;
see [`qbx_closure.md`](qbx_closure.md).

## "Perfect boundary knowledge" prolongation probe: does ordering fix ellipse?

Date: 2026-09-01

### Motivation

The previous entry ("Raw SDF-band source oversampling for operator-level
`T_QBX`") isolated two separate things needed for the raw-source `T_QBX`
diagnostic to work: (1) target/source geometry both on the SDF zero set, and
(2) a density prolongation from compressed targets to oversampled sources
better than local Euclidean IDW. With reprojection fixed, circle and star
improved with source oversampling but ellipse got *worse* (5.73e-3 @4x,
5.72e-3 @8x, vs the `gpr_bem_kdiff` baseline 4.32e-3). The stated next step
was: replace IDW with an ordered/smooth density prolongation, keeping
everything else the same, and see whether that alone fixes ellipse.

### What was added

`scratchpad/qbx_diagonal_probe.py` gained a second, opt-in "condition B" mode
for the existing `--ibim-source-t-solve` probe: `--ibim-perfect-prolongation`.
It keeps the real compressed IBIM boundary as the unknown/target grid (same
`S/D/Kp` blocks, same target reprojection, same solve/evaluation code as
condition A), but replaces exactly the source construction and density
prolongation:

- **Parameter recovery**: each (reprojected) compressed target point's curve
  parameter `t` is recovered analytically, reusing the closed-form inversions
  already in the script (`_point_parameter`/`_point_parameters` --
  `arctan2` for circle/star, the semi-axis-scaled `arctan2` for the ellipse).
  Since targets are reprojected onto the SDF zero set first, these points sit
  exactly on the analytic curve, so this closed-form inversion *is* the
  closest-point parameter, not merely a proxy for it.
- **Sources**: built directly from `nystrom_ref`'s
  `circle_parameterization`/`ellipse_parameterization`/`star_parameterization`
  via `build_curve`, uniform in `t`, at `source_factor * num_target` nodes
  (new helper `_analytic_oversampled_source_samples`). These points/normals
  are exact by construction -- no SDF band sampling, no reprojection, no
  possible geometric error.
- **Prolongation**: a new `_periodic_spline_prolongation_matrix` builds a
  periodic cubic spline through the target samples sorted by their recovered
  `t` (with a wrap-around knot to close the period) and evaluates it at the
  source `t` values. Because cubic-spline interpolation is linear in the
  sample values for fixed knots/query points, the whole map is produced as
  one matrix (by spline-interpolating a permutation/one-hot matrix instead of
  looping columns), so it drops into the same
  `_qbx_operator_t_matrix_with_source_prolongation` assembly condition A
  already used.

No production solver code was touched; both conditions live only in the
scratchpad script.

### Measured: 0.5 GHz, `P=16`, `rho/h=0.5`, both target and (for condition A)
### source reprojection onto the SDF zero set

Baselines rerun to confirm current values (not just taken from the log):

| shape | gpr_bem_mod | gpr_bem_kdiff |
|---|---:|---:|
| circle | 3.2409e-04 | 2.6157e-04 |
| ellipse | 3.1849e-03 | 4.3220e-03 |
| star | 4.1089e-03 | 1.0854e-02 |

Condition A (IDW prolongation, "no parameterisation knowledge") and condition
B (analytic parameterization + periodic-spline prolongation, "perfect
boundary knowledge"), relative scattered-field error vs Mie (circle) or
`nystrom_ref` N=512 (ellipse/star):

| shape | cond | 1x | 2x | 4x | 8x |
|---|---|---:|---:|---:|---:|
| circle | A (IDW) | 4.6139e-04 | 4.9080e-04 | 2.2044e-04 | 1.9594e-04 |
| circle | B (perfect) | 8.3239e-04 | 4.3238e-04 | 3.1486e-04 | 2.6977e-04 |
| ellipse | A (IDW) | 6.5904e-03 | 5.8334e-03 | 5.7300e-03 | 5.7247e-03 |
| ellipse | B (perfect) | 5.7154e-03 | 5.3440e-03 | 5.3627e-03 | 5.3529e-03 |
| star | A (IDW) | 6.5767e-03 | 6.3190e-03 | 7.0832e-03 | 7.6924e-03 |
| star | B (perfect) | 7.8519e-03 | 7.1531e-03 | 7.2674e-03 | 7.2695e-03 |

The 4x/8x condition-A entries reproduce the previous log's numbers exactly
(circle 2.2044e-4/1.9594e-4, ellipse 5.7300e-3/5.7247e-3, star
7.0832e-3/7.6924e-3); 1x/2x are new data points, run for the first time here.
No gross clearance violation was reported: `clear=1.000` for most runs and
`0.996-0.997` for star at higher condition-A factors. Equality/tolerance-level
`bad` pairs remain, however, so strict QBX admissibility was not established.

### Reading: the density-prolongation hypothesis is only partly confirmed

- **Circle**: condition B converges cleanly and monotonically with source
  count (8.32e-4 -> 4.32e-4 -> 3.15e-4 -> 2.70e-4), unlike condition A, which
  has a non-monotonic blip at 2x (4.61e-4 -> 4.91e-4) before improving. That
  monotonic trend is itself useful evidence that the analytic source geometry
  and spline prolongation are behaving as intended. But condition B's
  absolute error is *worse* than condition A at every matched factor, and at
  8x it lands close to but still slightly above the `gpr_bem_kdiff` baseline
  (2.70e-4 vs 2.62e-4) rather than clearly beating it the way condition A did
  (1.96e-4).
- **Ellipse**: condition B is a real but modest improvement over condition A
  (~5.35e-3 vs ~5.73-5.83e-3, roughly 7-9% lower), but it does **not** fix
  ellipse. Error is flat from 2x onward and never approaches, let alone beats,
  the `gpr_bem_kdiff` baseline (4.32e-3). Both conditions plateau at a level
  worse than the plain kdiff solve.
- **Star**: condition B (7.85e-3 -> 7.15e-3 -> 7.27e-3 -> 7.27e-3) plateaus in
  the same range as condition A's better values (6.32-7.08e-3), with no clear
  win either way, and neither condition shows monotonic improvement with
  oversampling past 2x.

**Answer to the motivating question: no**, replacing IDW with an
ordered/smooth prolongation over an exact analytic source curve does not, by
itself, fix ellipse while preserving the circle/star gains from condition A.
It only slightly narrows ellipse's gap and leaves the qualitative picture
unchanged: ellipse and star both plateau well before the geometric-oversampling
benefit seen on the circle. Condition B removes analytic source-geometry error
and replaces the original IDW map with one periodic-spline transfer. It
therefore rules out raw source count or that original IDW construction as the
whole explanation, not density transfer in general. The remaining floor may
come from the fixed compressed-target geometry/weights, unchanged direct
`S/D/Kp` blocks, QBX T evaluation, residual transfer error, or an interaction
among them. This experiment does not uniquely isolate a target-side cause.

### Historical next steps (superseded by closeout)

These were possible target-side isolation experiments, not production tasks.
The decision in [`qbx_closure.md`](qbx_closure.md) stops further tuning on the
compressed cloud and moves the forward path to ordered-boundary Kress/Nyström.

- Rerun this probe with target reprojection but a *finer* target grid (larger
  `N`) to see whether the ellipse/star plateaus fall when the compressed
  target discretization itself is refined, isolating whether the floor is a
  target-side or `T`-operator-side effect.
- Directly compare condition B's own `T`-operator action error (not just the
  full forward-solve error) against the reference `T_diff`, the way the
  earlier `_run_ibim_source_t_action_probe` did for condition A, to see
  whether the operator itself is still the bottleneck for ellipse/star once
  prolongation is no longer a suspect.
- Consider whether the periodic cubic spline (C2, but not exactly matching
  the truncated-Fourier prolongation used by the fully parameterized
  diagnostic) is itself under-resolving the higher-curvature-variation
  regions of the ellipse/star target sampling, and try a Fourier-based
  prolongation on the analytically recovered (but non-uniformly spaced)
  target parameters as a direct comparison.

## Shared T-assembly isolation and archived full-row QBX experiment

Date: 2026-09-01

The kdiff solve now has one explicit numerical variation point.  Its existing
direct S/D/K' matrices are assembled once in
`gpr_bem_kdiff.build_kdiff_operator_blocks`; a `TAssembler` supplies only
`dT = T_exterior - T_interior`, and `ibim_tmz_system` remains solely
responsible for placing `-dT` in the Muller system's lower-left quadrant.
Calling the solve without `t_assembly`, or with `LegacyLocalT()`, reproduces
the previous kdiff assembly exactly.

`gpr_bem_qbx` is no longer a duplicated solver package.  It exports
`FullRowQBX` plus explicit source configurations and is passed to the public
`gpr_bem_kdiff` solve:

- `SameNodeSources`: the plain no-oversampling full-row control, with identity
  density prolongation;
- `ParameterizedFourierSources`: analytic periodic source geometry with a
  configurable source factor and Fourier-collocation density prolongation;
- `ComponentParameterizedFourierSources`: the same construction applied
  independently to each disconnected curve;
- `RawSDFBandSources`: configurable Cartesian grid refinement, raw IBIM-band
  source quadrature, optional source reprojection, and IDW prolongation.

All assemble the same operator form,
`T = T_rect(compressed targets, oversampled sources) @ P`, in source chunks.
They do not move the compressed targets and cannot modify S/D/K'.  The old
near-band QBX solver copy was removed; its results remain recorded above and
reproducible from Git history.  The scratchpad retains the low-level QBX row
diagnostics but no longer presents that obsolete solver as a live comparison
row.

Focused contract validation checks:

- implicit default kdiff and explicit `LegacyLocalT()` are exactly equal;
- parameterized and raw-band full-row QBX leave S/D/K' byte-identical;
- only the Muller system's lower-left quadrant changes with T strategy;
- both prolongations reproduce a constant density to roundoff;
- the recorded parameterized 8x/order-16 circle diagnostic gives a maximum
  T-action error of `3.94e-9` over constant and first/second sine/cosine modes
  at N=64 against the independent `nystrom_ref` Kress matrix. The current
  executable regression is weaker: N=32, one cosine mode, and `<1e-6`.

Raw SDF-band QBX remains experimental. Invalid clearance now raises by default;
archived comparisons must opt in with `allow_invalid_clearance=True`, which
does not make their results admissible. The mixed ellipse/star results in the
preceding entries still apply; this refactor makes those experiments isolated
and reproducible but does not promote IDW prolongation as a validated default.

### Five-shape comparison rows and aggregate export

With the explicit `--include-qbx-archive` flag, the circle, ellipse, star,
square, and two-circle comparison pipelines add three QBX rows: same-node
`gpr_bem_qbx`, `qbx_fourier8`, and `qbx_sdfraw8`. The two-circle Fourier row
uses independent component prolongations. The default comparison path omits
them. The flagged aggregate exporter writes all three rows, their scattered
fields, timings, and complete per-frequency `t_assembly` reports.

The `8` labels have deliberately different meanings. Fourier uses exactly
`M=8N`; raw SDF uses an 8x-refined Cartesian grid and retains the complete
narrow band, giving actual source ratios of roughly 33x--80x in this run.
All solves and residuals are finite, but the diagnostics also expose why the
rows remain experimental: oversampled source sets have nonzero invalid QBX
clearance counts, and nonuniform Fourier collocation is poorly conditioned on
the ellipse (`1.78e6`) and star (`3.09e4`). These measurements are retained,
not interpreted as evidence of convergent QBX.

## QBX/kdiff production-direction closeout

Date: 2026-09-01

The five-shape comparison, ideal ordered-geometry controls, source-transfer
probes, clearance reports, and timings have now been consolidated in
[`docs/qbx_closure.md`](qbx_closure.md).

The result is deliberately narrower than “QBX does not work.” QBX T is highly
accurate on ordered, coherently parameterized smooth curves. On the real
compressed target cloud, however, same-node QBX is underresolved and every
oversampled stored row has invalid clearance. Accuracy is mixed rather than
uniformly worse, but no realization gives a robust, admissible improvement,
and the measured five-shape totals are about 30x, 54x, and 289x the kdiff time
for same-node, Fourier-source, and raw-SDF-source QBX respectively.

Therefore:

- `gpr_bem_kdiff` is frozen as a fast compressed-cloud experimental baseline;
- full-row QBX is retained only behind the isolated `TAssembler` seam;
- no further radius/order/IDW tuning is planned on the compressed cloud;
- `gpr_bem_mod` remains the operational inverse/adjoint-capable baseline; and
- forward-accuracy work moves to ordered SDF contour extraction followed by a
  coherent, component-wise Kress/Nyström discretization of all Müller blocks.

## Solver-neutral ordered smooth-boundary foundation

Date: 2026-09-02

### Hypothesis

Exact smooth geometry should be represented once, independently of MOD,
kdiff, Kress, QBX, or future SDF extraction. A forward solver should consume a
continuous component evaluator and component-aware samples rather than infer
order, normals, curvature, or density-transfer coordinates from the compressed
IBIM cloud.

### Change

Added `solvers/ordered_boundary/`, a NumPy-only package containing:

- `PeriodicCurve2D`, with stable component ID, arbitrary off-node periodic
  evaluation of `x/x'/x''` and optional `x'''`, explicit reversal and phase
  shift, and quadrature-independent uniform sampling;
- immutable `PeriodicCurveSamples2D`, deriving speed, tangent, CCW outward
  normal, curvature, and `h|x'|` arc-length weights from the evaluator;
- `OrderedBoundary2D` and `OrderedBoundarySamples2D`, retaining component-local
  grids alongside flattened arrays, slices, offsets, node owners, and local
  indices;
- exact circle, rotated ellipse, rotated radial-star, and real Fourier-series
  producers; and
- scale-aware reports for closure/derivative consistency, regularity,
  orientation, sampled self-intersection, component intersection, containment,
  and clearance, with JSON-safe provenance and phase diagnostics.

The package owns no SDF extraction, Torch code, material semantics, singular
quadrature, Kress pair weights, Maue regularisation, or MOD `merge_distance`.
Odd node counts are valid geometry; a future Kress consumer can request an
even count explicitly.

### Validation

```text
/home/drdeng/miniconda3/envs/EMNerf/bin/pytest \
  pytest/ordered_boundary/test_ordered_periodic_curve.py \
  pytest/ordered_boundary/test_ordered_boundary.py -q
-> 22 passed in 1.09 s
```

The tests cover analytic geometry and independent oracle agreement,
non-arclength parametrization, Fourier input ownership, optional third
derivatives, rigid rotation, odd/even restriction separation, immutable
derived fields, multicomponent flattening, strict JSON serialization,
clearance/nesting/intersection policies, a smooth lemniscate, a double-covered
circle, a zero-speed cusp, open/nonperiodic input, and a static ban on imports
from solver/oracle packages.

### Decision

Accept this as the common explicit-boundary starting point. Keep future SDF
projection/fitting as a producer of `PeriodicCurve2D`, and keep every
forward-method quadrature/regularisation in a solver adapter. No production
forward path or default changes in this entry.

## Ordered-boundary node ownership correction

Date: 2026-09-02

### Issue

The first API used `PeriodicCurve2D` for a continuous evaluator and appended
`Samples2D` to the actual node geometry. That was backwards for its intended
role parallel to `ImplicitBoundarySamples2D`: the BIE starting point must be
unambiguously node-owned and serializable.

### Change

- `PeriodicCurve2D` now owns one immutable uniform periodic node grid: the
  parameters, positions, first/second/optional-third derivatives, and derived
  speed, tangent, outward normal, curvature, and ordinary arc-length weights.
- `OrderedBoundary2D` now owns and flattens those node components directly. It
  has no `.sample()` method and no hidden evaluator.
- Off-node evaluation and resolution changes moved to explicitly separate
  `PeriodicParameterization2D` and `OrderedBoundaryParameterization2D`
  producers. Their transition to BIE nodes is named `.discretize(...)`.
- The generic `quadrature_weights` name became `arc_length_weights` so it
  cannot be mistaken for Kress target-source product weights.
- Continuous geometry diagnostics are correspondingly named
  `validate_periodic_parameterization` and
  `validate_ordered_parameterization`.

This is an API clarification only. It does not add an SDF extractor, Kress
weights, a hypersingular regularization, or a forward-solver connection.

### Validation

The 23 ordered-geometry tests now assert that `PeriodicCurve2D` and
`OrderedBoundary2D` are explicit node types, have no evaluator/evaluation
method, own read-only node arrays, and preserve component-local and flattened
indexing. The focused compatibility run, including the independent Nyström
oracle and existing IBIM geometry tests, passes 44 tests; its four warnings are
the pre-existing intentional IBIM merge-distance warnings.

## Frozen SDF boundaries: isolated scalar Kress proxy

Date: 2026-09-02

### Hypothesis

The coefficient-owning curves returned by the isolated SDF comparison should
support the logarithmic Kress split on uniform even node grids without being
refitted as the node count changes. Fourier Methods B and accepted C should
show spectral product-rule convergence. Method A should remain usable but
eventually expose the algebraic convergence implied by a globally C2,
piecewise-cubic curve.

This test must keep geometry error separate from quadrature error. A product
rule can converge to high accuracy on an under-resolved approximation of the
zero set.

### Change

Added [`scratchpad/sdf_boundary_kress_proxy.py`](../scratchpad/sdf_boundary_kress_proxy.py),
an explicitly non-production scalar diagnostic. It evaluates

\[
\int_0^{2\pi}\log|\gamma(t)-\gamma(s)|\rho(s)|\gamma'(s)|\,ds
\]

with the standard periodic logarithmic product weights. It uses the required
factor one half for the canonical `log(4 sin^2((t-s)/2))` weights and the
removable diagonal value `log|gamma'(t)|`.

The manufactured choice makes `rho(s)|gamma'(s)|` a non-bandlimited Poisson
kernel with `a=0.75` and phase `0.37`. The canonical logarithmic convolution is
known analytically. On non-circular curves, the reference evaluates the smooth
geometric `q` remainder with composite Gauss-Legendre orders 24 and 40; the two
orders must agree before the reference is accepted. Thus the reference does
not reuse a finer instance of the Kress rule being tested.

The benchmark records two errors rather than collapsing them. The **smooth
remainder error** measures the geometry-dependent `q` term and is the useful
A/B/C representation comparison. The **full manufactured-action error** adds
the analytically known canonical convolution and remains the end-to-end scalar
identity check. Reporting both is necessary because the canonical term can
dominate the full error and conceal a curve-dependent remainder trend.

The frozen-curve sweep reconstructs native `spline_knots` /
`spline_coefficients` or Fourier cosine/sine coefficients from the existing
full-study artifacts. It verifies exact reconstruction, then discretizes the
same continuous curve at N=32 through 2048. It neither reruns marching squares
nor refits at a new N. Selected C rows are successful refinements; fallback C
rows are not repeated because their saved coefficients are bit-identical to B.

Added [`pytest/sdf_to_ordered_boundary/test_sdf_boundary_kress_proxy.py`](../pytest/sdf_to_ordered_boundary/test_sdf_boundary_kress_proxy.py)
for independent circle sine/cosine identities including the special Nyquist
term, the non-bandlimited analytic circle control, the independent smooth-
remainder reference, spline asymptotics, even-N rejection, and a static ban on
imports from solver implementations.

No `solvers/` package, solver selector, forward/adjoint/inverse entry point, or
current architecture behavior changed.

### Validation

Fast executable checks:

```bash
PYTHONPATH=solvers OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
MKL_NUM_THREADS=1 \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  pytest/sdf_to_ordered_boundary/test_sdf_boundary_kress_proxy.py
```

The checked compact coefficient inputs make the frozen coefficient benchmark
self-contained. `--artifact-root` supplies the tracked study manifest and
metrics; `--curve-root` supplies the checked authoritative arrays selected for
this diagnostic:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  scratchpad/sdf_boundary_kress_proxy.py \
  --artifact-root results/sdf_boundary_parameterization/study-20260902 \
  --curve-root results/sdf_boundary_parameterization/\
kress-scalar-proxy-20260902/frozen_curves \
  --output-dir results/sdf_boundary_parameterization/\
kress-scalar-proxy-REPRO \
  --timing-repeats 9
```

The canonical skimmed error/runtime table and complete JSON/CSV records are in
[`results/sdf_boundary_parameterization/kress-scalar-proxy-20260902/summary.md`](../results/sdf_boundary_parameterization/kress-scalar-proxy-20260902/summary.md).

The generated summary is the authoritative readable error/runtime table. It
shows smooth-remainder and full-action errors side by side and labels values
that are limited by reference agreement instead of presenting them as precise
roundoff measurements. It also records the outcome of the declared,
configured gates and the agreement of the two composite-Gauss reference
orders.

Runtime columns have deliberately narrow meanings. A proxy-action timing is
one dense `N x N` matrix formation and application on the recorded CPU/thread
configuration. It is neither an FFT application time nor a four-block BIE
assembly or solve. A converter timing is copied from the earlier A/B/C study
and includes that row's shared marching-squares, contour-validation,
resampling, and Newton-projection front end. Because that shared front-end cost
is charged independently to every row, converter times must not be summed
across methods.

Geometry fidelity and product-rule convergence remain separate. A frozen
Fourier curve may integrate its own smooth remainder to the reference floor
while still approximating the original zero set poorly; the geometry residual
columns must therefore be read alongside the remainder-error columns.

### Decision

Subject to the generated summary's configured gates, retain **Method B with
adaptively increased bandwidth** as the preferred parameterization candidate.
The scalar test asks whether accepted C demonstrates a remainder-convergence
advantage commensurate with its extra conversion work; it does not infer that
advantage from the geometry plot or from the shared canonical convolution.
Method A remains the finite-smoothness control rather than the preferred
high-order Kress curve.

This does not complete Phase 3 of the ordered-boundary plan: no Müller kernel
block, singular diagonal formula, linear system, scattered field, or solver
integration was tested here.

2026-09-02

## Test and evidence organization

The test suite was grouped by the implementation or validation boundary it
exercises. Selector-backed IBIM tests now live in `pytest/gpr_bem_shared/`;
MOD- and kdiff-specific checks in `pytest/gpr_bem_mod/` and
`pytest/gpr_bem_kdiff/`; independent oracles in `pytest/gprmax_ref/` and
`pytest/nystrom_ref/`; geometry contracts in `pytest/ordered_boundary/` and
`pytest/sdf_to_ordered_boundary/`; and physical solver comparisons in
`pytest/solver_comparisons/`. The archived QBX comparison helper is under
`pytest/solver_comparisons/archived_qbx/`.

Evidence was removed from the test tree. The SDF smoke run, full study, and
manufactured scalar Kress proxy are now the three dated bundles under
`results/sdf_boundary_parameterization/`. Their SDF residuals, speed,
curvature, topology checks, and scalar action errors are geometry/quadrature-
readiness measurements, not BIE/PDE solver errors. The dated five-shape bundle
with actual field/solver errors and archived QBX rows is now
`results/solver_comparisons/legacy/qbx-closeout-20260901/`. Historical QBX
scratch drivers are under `scratchpad/legacy/qbx/`.

Older historical entries may retain the paths that existed when those
experiments were run; the immediately preceding active Kress entry was updated
to use the current reproduction paths. For current reproduction, use the
organized locations above and the commands in `pytest/README.md`; no numerical
result or solver pipeline changed. Two tests that exercise APIs present only
in the maintained MOD implementation (`test_ibim_tmz_adjoint.py` and
`test_ibim_inverse.py`) now import `gpr_bem_mod` explicitly. They are no longer
misleadingly collected as selector-shared tests under `--solver=ref`; the
genuinely shared tests remain dual-run under `pytest/gpr_bem_shared/`.

Validation after relocation collected 248 tests from `pytest/`. The
non-comparison package run passed 224 tests with two optional-backend skips;
the relocated `pytest/solver_comparisons/` run passed all 22 tests; and the
shared suite against `--solver=mod` passed 41 tests with the same two optional
skips. The warnings were the existing merge-distance and Matplotlib/PyParsing
warnings, not collection or import failures.

## Isolated `PeriodicCurve2D` Kress/Müller forward candidate

Date: 2026-09-02

### Hypothesis

One frozen smooth `PeriodicCurve2D` should be a sufficient and clean geometry
seam for cancellation-safe Müller differences. A coherent all-block periodic
Kress discretization should recover analytic circle block actions, boundary
traces, and receiver fields and should converge on exact noncircular and
SDF-derived Fourier curves without importing extraction or fitting state into
the solver.

### Change

Added the direct-import-only `solvers/gpr_bem_mod/ordered_nystrom/` candidate.
Its adapter accepts one even, endpoint-free, counterclockwise, simple
`PeriodicCurve2D`; preserves its points, node order, outward normals, and
ordinary `ds` weights; and maps only the parameter coordinate to canonical
`[0,2 pi)`. A content hash records geometry identity.

The numerical layer forms `Delta V`, `Delta K`, `Delta Kp`, and `Delta T` as
combined exterior-minus-interior kernels. It uses a cancellation-safe
power-log near series, direct Hankel differences away from the diagonal,
closed diagonal remainders, and one shared full-log periodic weight generator
in `solvers/periodic_kress/`. Each completed block owns the source Jacobian and
parameter step exactly once. Target-row chunking bounds temporary storage
while retaining the four dense matrices.

Under the audited repository convention, the directly solved system is

```text
[ I-DeltaK    DeltaV   ] [u_D] = [u_inc,D]
[ -DeltaT   I+DeltaKp ] [u_N]   [u_inc,N]
```

The lower-left sign is equivalent to the maintained package's `+DeltaW`
because that vocabulary defines `W=-T`. The forward result retains total
traces, separated exterior single/double potentials, the full
source-by-receiver field, linear residuals, overlap diagnostics, and separated
timings. The high-level material route is explicitly lossless and nonmagnetic;
conductive inputs are rejected until the repository phasor/conductivity sign
is reconciled. The low-level complex-wavenumber API remains available for
numerical kernel tests.

No selector, normal forward driver, adjoint, inverse, SDF converter, or
`gpr_bem_mod.__init__` export was changed. Architecture, convention derivation,
diagonal formulas, API, limitations, and the integration verdict are recorded
in the implementation record now located at
[`gpr_bem_kress_implementation.md`](gpr_bem_kress_implementation.md).

### Validation

The solver-owned regression command was:

```bash
PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  pytest/ordered_nystrom
```

It passed 38 tests. Coverage includes isolation, geometry/weight ownership,
canonical Kress modes including Nyquist, near/direct overlap, small-separation
stability, analytic Fourier-Bessel actions of all four circle blocks, exact
matrix signs and jumps, manufactured modal recovery, zero contrast, circle
Mie traces/receiver fields through 8 GHz, receiver-clearance guards, and
explicit magnetic/lossy rejection.

The checked exact-curve evidence was generated with:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_ordered_nystrom_validation.py \
  --preset quick --timing-repeats 3 --run-id quick-20260902
```

It produced 27 rows for exact circle, rotated ellipse, and smooth five-lobed
star at `N={64,128,256}` and `{0.5,2.5,8}` GHz. All nine configured largest-`N`
smoke checks pass. At `N=256`, the worst mixed receiver error is `1.22e-8`, the
worst total-trace error is `1.11e-8`, and the largest ordinary system residual
is below `4e-14`. The difficult star/8-GHz receiver error decreases from
`5.55e-1` at `N=64` to `8.89e-5` at `N=128` and `1.22e-8` at `N=256`; a small
algebraic residual alone would not have exposed the first two under-resolved
solutions. Exact retained storage for four blocks plus the system is 8 MiB at
`N=256`. The slowest median candidate cell, including the separately timed raw
condition estimate, is 327 ms; the complete run took 16.04 s.

The separate frozen-geometry command used the checked finest-input Method-B
circle `K=4` and ellipse/star `K=32` coefficient bundles, `N={128,256}`, and an
independent `nystrom_ref` oracle at `N=512`. It passed all nine configured
largest-`N` checks. The worst `N=256` receiver and trace discrepancies are
`4.79e-9` and `3.56e-9`; the slowest median candidate cell is 322 ms and the
complete three-repeat run took 18.00 s.

The readable tables, complete CSV/JSON records, commands, input provenance,
environment, and current source/artifact hashes are indexed at
[`results/ordered_boundary_nystrom/README.md`](../results/ordered_boundary_nystrom/README.md).
No dense matrix, solution, trace, or receiver array is stored there. The raw
condition number mixes Dirichlet and Neumann units and is diagnostic only.

### Decision

Keep one shared downstream solver accepting `PeriodicCurve2D`; do not fork a
solver for parameterization Methods A, B, and C. Those remain upstream curve
producers and should be compared by freezing each `gamma` before varying the
Nyström node count. Method B with adaptive bandwidth remains the preferred
upstream candidate because Method C has not demonstrated an operator benefit
that offsets its nonlinear cost and fallback behavior.

The new solver is accepted only as an isolated experimental candidate. It is
not Phase-4-complete and is not ready for selector or inverse integration.
Remaining gates include all six frequencies, reference-oracle
self-convergence, separate exterior/interior transmission residuals,
noncircular block/reciprocity checks, solver-level geometry-bandwidth sweeps,
lossy-physics reconciliation, and equal-work comparisons against the current
operational baseline.

2026-09-02

## Promote the ordered implementation to a peer package boundary

### Hypothesis

The Kress/Nyström implementation is a parallel forward solver, not a MOD
assembly option. Moving it to a sibling package and making its receiver map
explicit should remove accidental MOD/Torch coupling while retaining the
complete forward state required for a later adjoint.

### Change

Moved the live implementation from the nested experimental location to
`solvers/gpr_bem_kress/` and renamed its public records and entry points around
the solver identity: `KressSolveConfig`, `KressTMzFrequencySystem`,
`KressTMzForwardResult`, `KressTMzMultiFrequencyForwardResult`,
`build_kress_tmz_frequency_system`, `solve_kress_tmz_total_field_batch`, and
`solve_kress_tmz_frequency_response`.

The peer owns a small package-local `Material` value rather than importing
`gpr_bem_mod` for class identity. Its geometry input remains exactly one
immutable `PeriodicCurve2D`; SDF extraction, Method-B fitting, scan
orchestration, and neural coupling remain outside the solver package.

Added `ExteriorReceiverOperator`, which stores the fully weighted
single-/double-layer rows and the actual state map

```text
C = [D, -S],        q = [u_D, u_N]^T,        u_sc = C q.
```

The forward result retains that operator together with the literal unsquared
system `A`, right-hand side, state, and traces. This records—but does not yet
implement—the future discrete-adjoint boundary
`A^H lambda = C^H psi`. The eventual shape derivative must differentiate the
accepted weighted Kress assembly and must distinguish a nodal directional
derivative from an unweighted shape-gradient density so arc-length weights are
not applied twice.

The package remains absent from `solver_select` and all operational MOD
forward/adjoint/inverse drivers. Tests now live under the matching
`pytest/gpr_bem_kress/` directory. Historical entries and stored manifests
above retain the paths and hashes that existed when their measurements were
made.

### Validation

The peer-package regression command was:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest \
  pytest/gpr_bem_kress -q
```

It passed all 41 tests in 0.40 s. The suite includes the prior block, system,
trace, and Mie-field checks plus isolation/API and explicit receiver-operator
checks. This verifies the package move and forward algebra; it is not an
adjoint gradient check.

The new comparison contract uses the same callable SDF for independent MOD
compression and Method-B-to-`PeriodicCurve2D` Kress extraction on circle,
ellipse, and star. Kress' full source-by-receiver matrix is reduced explicitly
to the 24 paired diagonal entries for comparison. Existing gprMax caches cover
only pair index 0, so they provide one-pair relative error at each frequency
and must not be presented as full-ring coverage. Quantitative results and
commands for that comparison are intentionally deferred to a separate entry
after its targeted tests settle.

### Decision

Accept `gpr_bem_kress` as the clean experimental peer-package boundary and
remove the nested MOD ownership. Keep it direct-import only and forward-only.
Do not begin inverse wiring merely because `C^H` is now available: the
system/incident/receiver shape derivatives and finite-difference adjoint gates
remain mandatory.

2026-09-02

## Add same-SDF receiver-field acceptance for the Kress peer

### Hypothesis

If the package boundary is correct, the Kress solver should run beside MOD on
the existing smooth ACC scenes, beginning from the identical implicit-field
callable and being judged by the same receiver-field oracle rather than by
geometry proxies or linear residual alone.

### Change

Added a shared comparison adapter under `pytest/solver_comparisons/`. Circle,
ellipse, and star now branch one `161 x 161` Torch field into independent MOD
compression and Method-B (`M=256`, `K=48`) extraction, followed by a Kress
curve with `N=128`. The Kress full source/receiver matrix is reduced explicitly
to the paired diagonal. Tables now label 24-pair L2 and one-pair gprMax coverage
separately, record preprocessing/forward/end-to-end time, and never rank those
unlike coverages together. The aggregate exporter also stores the ordered
curve artifact beside the MOD cloud for each supported smooth case.

The machine-readable schema now separates `error_pair_count` from the actual
receiver workload (`num_sources`, `num_receivers`, internal matrix shape,
reported field shape, and selection). Each scene JSON records its target,
bounds, grid, materials, constants, full Tx/Rx coordinates, oracle, and Kress
component/config identity. Cache validation compares Tx/Rx offsets relative to
the target because gprMax translates the same homogeneous scene into a compact
FDTD domain; comparing unrelated absolute origins would reject a valid cache.

For future adjoint replay, forward snapshots now retain typed solve/assembly
configs and material values. ACC pairing remains outside the general receiver
operator and is specified as `y=P(Cq+u_inc)`: a future context must apply
`P^H` before `C^H`. A pair vector passed directly to `apply_adjoint` means one
RHS and would be the wrong layout. The shape-adjoint plan also now requires a
coupled curve-jet direction and defers multicomponent gradient tests until a
multicomponent Kress forward solver exists.

### Validation

The three receiver gates and two cache-coordinate contract tests passed in
30.72 s. Across 0.5/1.5/2.5/4/6/8 GHz,
Kress full-ring error ranges from `3.56e-11` to `1.17e-8` on the circle,
`1.38e-12` to `2.48e-8` on the ellipse, and `5.19e-6` to `7.49e-3` on the star.
It beats MOD at every measured cell. A separate table run passed all three
cases in 30.69 s. The final audited aggregate exporter passed in 42.52 s
(43.93 s process wall time) and measured Kress six-frequency forward sweeps of
0.29--0.37 s plus 0.58--0.68 s of boundary preprocessing. The full tables,
exact command, scope qualifications, and MOD, Kress, and gprMax pair-0 values
are frozen in
[`results/solver_comparisons/kress-peer-20260902/summary.md`](../results/solver_comparisons/kress-peer-20260902/summary.md).

The final reporting audit made those gates and workloads executable rather
than implicit: Kress must remain below its declared threshold and beat MOD at
all six frequencies, kdiff is identified as a direct 24-pair receiver
contraction instead of a `24 x 24` materialization, and unavailable JSON
metrics serialize as strict `null` rather than non-standard `NaN`. Cached
gprMax wall time covers two executions per frequency (target and matched
background), or 12 executions for the six-frequency table.

After the final package/config/cache-contract changes, the complete
MOD-selected suite passed `254 passed, 2 skipped` in 179.31 s. The frozen-ref
shared suite separately passed `41 passed, 2 skipped` in 14.65 s, and the
direct Kress package suite passed all 41 tests in 0.34 s (1.57 s process wall
time). The reported warnings were existing adaptive-compression notices and
Matplotlib/Pyparsing
deprecations.

### Decision

Prefer Kress for further smooth single-component forward work. This is a
forward acceptance result, not promotion into the selector or inverse loop.
The star frequency trend still requires bandwidth/node refinement evidence,
and a Kress adjoint still requires derivatives of the actual weighted
geometry, system, incident field, and receiver map plus a finite-difference
gradient check. Existing gprMax caches remain an independent pair-0 physics
cross-check, not a full-ring precision oracle and not literally the Torch-SDF
branch.

2026-09-02

## Add an audited solver-neutral wrong-SDF inverse

### Hypothesis

The accepted Kress forward peer should not be rebuilt to answer the first
inverse question. If both forward solvers consume the same ordered boundary
and the optimizer treats each as the same black box, a deliberately wrong,
low-dimensional SDF should converge against independent analytic data. The
result should expose forward-discretization bias rather than confounding it
with different geometry extraction, truth generation, objectives, or
optimizers.

### Audit

The existing neural B-scan inverse was MOD-only and was not a reliable
MOD/Kress comparison surface. Four concrete defects were found:

- `run_ibim_circle_inverse_bscan.py` passed an unsupported
  `min_boundary_samples` keyword to `run_ibim_bscan_inverse`;
- a CUDA Torch device selected the CuPy BEM backend without first establishing
  that CuPy was importable;
- a broad `except Exception` silently replaced any leading-order adjoint
  failure with a sparse boundary finite difference; and
- its smoke fixture used one frequency, whose trapezoidal integration weight
  is zero, so the nominal B-scan loss and adjoint dual were degenerate.

A short random-SIREN warm start also did not provide a safe comparison input:
it produced multiple zero contours rather than the one regular closed
component required by Kress. In addition, a full numerical Jacobian over a
large network would require at least two complete forward evaluations per
parameter. The comparison was therefore scoped to a wrong three-parameter
circle SDF, leaving scalable neural differentiation as a separate milestone.

### Change

Added `solvers/sdf_inverse/` with four explicit seams:

- a negative-inside `CircleSDF2D` and bounded Torch parameter controller;
- common `TorchImplicitField2D` extraction, single-component validation,
  Method-B Fourier fitting, arc-length redistribution, and even-node
  `PeriodicCurve2D` construction;
- paired forward dispatch that passes the curve directly to Kress or copies
  exactly its points, normals, and arc weights into a MOD
  `ImplicitBoundarySamples2D`; and
- a normalized complex scattered-field objective with a bounded central-FD
  Jacobian, damped Gauss--Newton/Levenberg--Marquardt updates, backtracking,
  evaluation caching, and accepted-iterate records.

Kress evaluates its native full source-by-receiver matrices and the adapter
selects their paired diagonal. MOD uses strict quadrature, direct Müller,
analytic-extrapolated normal derivatives, NumPy, and complex128. Neither
branch silently changes formulation or backend. The SDF-to-curve seam remains
outside autograd, so the parameter finite differences include contour
extraction, fitting, and remeshing.

Added `run_sdf_inverse_comparison.py`. Its truth is the analytic
penetrable-cylinder Mie series from `gpr_bem_ref`, not either forward solver.
The default case starts at center `(0.48, 0.52) m`, radius `0.065 m`, targets
`(0.50, 0.50) m`, radius `0.050 m`, fits 12 paired observations at
0.25/0.5 GHz, and reserves 1/1.5/2.5 GHz for holdout. Both solvers receive the
same 64-node Method-B curve, `129 x 129` extraction grid, and six-iteration
inverse cap. The geometry box was widened to
`((0.30, 0.30), (0.70, 0.70)) m`, which contains every permitted
center/radius trial with at least `0.01 m` clearance. A
second control evaluates each solver on the shared fitted boundary from the
exact target SDF, isolating forward error from recovered-parameter error.

The marching-squares front end was also hardened for contours that pass
exactly through grid nodes. Consecutive near-duplicate vertices emitted around
an exact grid zero are removed before polygon validation. Non-adjacent
duplicates remain untouched and are rejected, preserving the guard against
genuine self-touching or degenerate geometry.

Artifact writes now default to a UTC-timestamped directory. An explicitly
named nonempty output directory is refused unless `--overwrite` is supplied;
that option removes only this driver's known artifact names. Acceptance now
also requires each optimizer to reach a declared convergence condition. The
recorded maximum system residual covers every uncached finite-difference and
line-search forward, including rejected trials, plus the initial, final, and
true-target-boundary controls.

The legacy MOD inverse was repaired rather than silently superseded. The
unsupported keyword was removed; backend resolution requires both Torch CUDA
and importable CuPy; `shape_gradient_fallback` defaults to `error` and permits
the sparse finite difference only when explicitly set to
`finite_difference`; and each iteration records the method used. The smoke
fixture now uses two frequencies and requires a finite nonzero loss and dual.

### Validation

The checked inverse was reproduced with:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py \
  --output-dir results/inverse_solver_comparison/wrong-circle-mie-20260902 \
  --overwrite
```

Both branches used 42 forward evaluations. MOD reduced training relative L2
from `9.737e-1` to `2.713e-3`, a `1.226e5x` loss drop, and recovered the center
to below `0.0001 mm` with `0.0568 mm` radius error. Its inverse holdout relative
L2 was `7.0438e-2`; on the true-target fitted boundary its holdout error was
`7.3024e-2`. It met the relative-step tolerance after five accepted updates
in about `7.5 s`.

Kress reduced training relative L2 from `9.741e-1` to `8.648e-11`, a
`1.294e20x` loss drop, and recovered center and radius to below the displayed
precision (`8.008e-10 mm` radius error). Its inverse holdout relative L2 was
`3.810e-10`; on the identical true-target fitted boundary it was `8.195e-14`.
It met the loss tolerance after five accepted updates in about `4.5 s`.

Accepted losses were monotone, both parameter-error gates passed, maximum
linear-system relative residuals were below `1e-10`, each solver passed the
declared `0.15` holdout ceiling, Kress passed its `1e-6` accuracy gate, and
Kress beat MOD on both recovered and true-target boundaries. Both optimizer-
convergence gates passed, and the MOD/Kress initial- and true-target-boundary
parity deltas were exactly zero. All gates passed.
For the same 42 inverse evaluations, the measured end-to-end MOD/Kress wall
ratio was `1.67x`; this includes repeated geometry extraction and fitting and
is not an isolated BIE assembly benchmark.
The complete configuration, provenance, trajectories, responses, geometry,
plot, and exact values are checked under
[`results/inverse_solver_comparison/wrong-circle-mie-20260902/`](../results/inverse_solver_comparison/wrong-circle-mie-20260902/).

The new module suite was run with:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  pytest/sdf_inverse
```

It passed all 7 cases in 3.71 s. Together with the nine MOD legacy-inverse
tests, the current tree contains 16 focused inverse cases. The complete
first-party suite was then run as:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest \
  pytest/ -q
```

It passed `264 passed, 2 skipped` with 300 warnings in 172.09 s (173.57 s
process wall time). The two skips are the expected CuPy-dependent checks. A
repository-root-wide discovery is not the first-party suite: it also collects
vendored optional projects whose dependencies are not installed, so those
unrelated collection errors are not reported as inverse failures.

### Decision

Accept the shared ordered-boundary parameter-FD path as the working inverse
comparison baseline. Kress materially outperforms MOD on this smooth circle,
including a control where the geometry is identical, and should be the
preferred forward backend for the next smooth single-component inverse work.

This is not selector promotion and not a Kress adjoint. `gpr_bem_kress`
remains direct-import, forward-only, CPU/NumPy, lossless/nonmagnetic, and
single-component. A random SIREN first needs a topology-valid initialization;
a scalable inverse then needs derivatives of the actual weighted Kress
blocks, incident field, receiver map, points, normals, speeds, source
Jacobians, and diagonal split, accepted against this numerical baseline.

2026-09-02

## Extend the inverse to non-circular and neural implicit initializations

### Hypothesis

The solver-neutral seam should depend on a regular zero contour, not on exact
signed-distance values or a circular initial family. A rotated non-distance
ellipse and a bounded random-feature neural implicit should therefore converge
to the same analytic target. A completely unconstrained random network should
instead fail explicitly if it does not supply one valid closed component.

### Change

Added two low-dimensional Torch models and controller builders:

- `EllipseLevelSet2D` returns the dimensionless quadratic
  `(x'/a)^2 + (y'/b)^2 - 1`, with trainable center and semi-axes and a fixed
  rotation; and
- `RadialRandomFeatureImplicit2D` uses fixed seeded tanh direction features
  with trainable center, base radius, and four output weights. Its bounded
  radial envelope guarantees one positive star-shaped contour throughout all
  finite-difference and line-search trials.

`run_sdf_inverse_comparison.py --initial-model` now selects `circle`,
`ellipse`, or `random_features`; `--loss-tolerance` exposes the recorded
optimizer stop threshold. Model state, fixed random features, raw bounds, and
initial physical parameters are persisted. Generic geometry diagnostics now
include `|F| / ||grad F||`, because raw `|F|` changes under harmless implicit-
field rescaling and is not a comparable non-SDF geometry error.

The acceptance set adds final circle-boundary error plus explicit
non-circular/non-distance initialization gates. Tests cover controller
round-trips, deterministic random features, both new models through MOD and
Kress, and a seeded unconstrained MLP that is rejected during contour
validation before a forward solve.

### Validation

The rotated ellipse run used semi-axes `0.072/0.038 m`, rotation `0.4 rad`, and
passed all `25/25` gates. MOD reduced training relative L2 from `9.272e-1` to
`2.713e-3`, with `7.044e-2` holdout error and `5.684e-5 m` maximum circle
error. Kress reduced it from `9.283e-1` to `7.115e-10`, with `3.225e-9`
holdout error and `3.412e-11 m` maximum circle error.

The seeded random-feature neural implicit had `0.00751 m` initial radial span
and passed all `25/25` gates. MOD reduced training relative L2 from `9.298e-1`
to `2.713e-3`, with `7.044e-2` holdout error and `5.684e-5 m` maximum circle
error. Kress reduced it from `9.298e-1` to `3.696e-10`, with `3.645e-9`
holdout error and `5.003e-11 m` maximum circle error. Both branches used 190
forward evaluations; the end-to-end times were `31.67 s` for MOD and `17.45 s`
for Kress.

The combined focused inverse command passed `24 passed` in 25.36 s:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  pytest/sdf_inverse/test_solver_neutral_inverse.py \
  pytest/gpr_bem_mod/test_ibim_inverse.py
```

The complete current first-party suite then passed `272 passed, 2 skipped`
with 300 warnings in 193.15 s (194.92 s process wall time):

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest pytest/ -q
```

Both skips were the expected CuPy-unavailable checks; there were no failures.

All three checked bundles, commands, metrics, and limitations are indexed at
[`results/inverse_solver_comparison/README.md`](../results/inverse_solver_comparison/README.md).

### Decision

Accept both non-SDF cases as inverse-pipeline evidence. The zero-contour
contract is now demonstrated independently of signed-distance magnitude and
of a circular initial parameterization. The random-feature case remains a
topology-constrained small neural model, not evidence that arbitrary SIREN
initialization or full-network finite differences are safe or scalable.


2026-09-03

## Lobed star target with independent Nystrom observations

### Motivation

Every checked inverse case recovered a circle, so the pipeline had never been
asked to recover a shape parameter that a circle does not have. The circle
also hid a question the geometry seam cannot answer for itself: how much of
the achievable accuracy belongs to the forward solver and how much to the
arc-length Fourier representation, which is exact for a circle at bandwidth
one.

### What was added

`--target {circle,star}` selects the analytic target and its observation
oracle. The target owns everything that changes with the shape -- truth
generation, the exact implicit field for the true-boundary control, the exact
point-to-curve distance, the initializations, both frequency bands, the
extraction/fit resolutions, and the shape gates -- so the objective, optimizer,
artifacts, and solver dispatch remain literally the same code. `--target
circle` reproduces the previous behavior; the checked circle bundle re-ran
bit-for-bit identical accepted trajectories after the change.

- `solvers/sdf_inverse/models.py` gained `StarLevelSet2D`, a five-control
  radial star `r(t) = R (1 + a cos(m (t - phi)))` evaluated through a Chebyshev
  recurrence rather than `atan2`, so the field and its point gradient stay
  finite at the extraction grid's center point. `build_star_parameter_controller`
  refuses amplitude bounds containing zero, where the rotation is not
  identifiable, and rotation bounds as wide as the `2 pi / m` symmetry period,
  where one shape has several parameter vectors.
- `solvers/sdf_inverse/targets.py` holds `StarShape`: the parameterization the
  oracle integrates, the Torch field the extraction consumes, and an exact
  point-to-curve distance by bracketed golden-section search. A test asserts
  the parameterization equals `nystrom_ref.star_parameterization` bit for bit.
- `solvers/sdf_inverse/nystrom_oracle.py` wraps `nystrom_ref` as an
  observation source and adds the half-resolution self-convergence check that
  the driver gates on before running any inverse.
- `run_sdf_inverse_contour_video.py` renders an existing bundle's accepted
  contour trajectories for both solvers side by side. It is read-only
  post-processing: no solver import, no recomputed physics, and interpolated
  frames are labelled as such.

### Measurements behind the star configuration

Three choices were measured rather than assumed.

Frequency band. One central finite-difference step in the lobe rotation
changes the field by `1.2e-5` at 0.25 GHz and `1.9e-2` at 1.5 GHz; the lobe
amplitude behaves the same way. The star therefore trains at 0.5/1.5 GHz and
holds out 0.25/1/2.5 GHz. The five-parameter Jacobian of the normalized
residual has condition number `32` on that training pair.

Fourier bandwidth. Truncating the exact star's own arc-length spectrum gives
a maximum boundary error of `9.702e-4 m` at bandwidth 10, `2.035e-4` at 24,
and `2.941e-5` at 48. Method B tracks that floor (`1.144e-3`, `2.466e-4`,
`4.052e-5`). Refining the extraction grid from `129^2` to `385^2` at fixed
bandwidth changed the fitted boundary error by less than one part in a
thousand, and raising the projected-sample count from 64 to 512 changed it as
little. The bandwidth is the limiter, so the star uses bandwidth 48 and 128
nodes. A related finding: Method B's derivative-consistency validation needs
roughly twenty `validation_resolution` samples per retained mode, far above
the `2 * bandwidth + 2` minimum the config enforces; a bandwidth-24 star fit
is rejected at 256 samples and accepted at 512. This is now documented in
`OrderedSDFGeometryConfig`.

Bounds. All 32 corners of the five-dimensional bound box extract to one valid
closed component.

### Validation

The checked run is
[`results/inverse_solver_comparison/wrong-star-nystrom-20260903/`](../results/inverse_solver_comparison/wrong-star-nystrom-20260903/),
recovering `r(t) = 0.05 (1 + 0.25 cos 5t) m` at `(0.50, 0.50) m` from an
initialization wrong in all five controls (`center = (0.48, 0.52) m`,
`mean radius = 0.060 m`, `amplitude = 0.12`, `rotation = 0.25 rad`). All
`30/30` gates passed, including the two new lobe gates and the oracle
self-convergence gate.

| Solver | Train relative L2 | Holdout | True-boundary holdout | Amplitude error | Rotation error | Evaluations | Time |
|---|---:|---:|---:|---:|---:|---:|---:|
| MOD | `1.200 -> 3.021e-3` | `1.266e-2` | `1.260e-2` | `4.916e-4` | `7.842e-5 rad` | 132 | `116.98 s` |
| Kress | `1.196 -> 5.881e-6` | `3.139e-5` | `4.824e-5` | `5.427e-6` | `1.352e-7 rad` | 121 | `74.00 s` |

Both recovered the center to about `3e-9 m`. The observation oracle solved at
512 versus 256 nodes agreed to `2.880e-10` with a `2.1e-14` linear-system
residual.

The focused inverse suite grew from 15 to 24 cases and passed in 37.36 s:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q pytest/sdf_inverse
```

The complete first-party suite passed `281 passed, 2 skipped` with 300
warnings in 216.92 s; both skips were the expected CuPy-unavailable checks.

### Current interpretation

The star moves the accuracy floor from the forward solver to the geometry.
Kress' final training error is on the same geometry-controlled order as its
error on the exact target's fitted boundary, so the shared bandwidth-48
representation is material rather than its own quadrature; the Kress holdout gate is therefore `1e-3` here
against `1e-6` for the circle. MOD remains limited by its own discretisation:
its final holdout error is within half a percent of what it produces on the
exact target's boundary. Both solvers absorbed a small part of the shared
geometry error into their parameters, each ending slightly below its own
true-boundary error, which is why that control is computed at all.

Independence has a stated limit. `nystrom_ref` shares no numerics with either
solver, but it and Kress are separate implementations of the same
Nystrom/Muller formulation, so this comparison would expose a shared
implementation error and not a shared formulation error. MOD's
compressed-cloud discretisation has no such kinship.

### Decision

Accept the star as inverse evidence for lobe depth and phase recovery. It does
not extend the pipeline to topology or lobe-count recovery: the lobe count is
fixed structure, since an integer cannot be recovered by continuous finite
differences. The next milestone is unchanged -- a Kress discrete adjoint whose
directional derivatives are accepted against this low-dimensional baseline.

---

2026-09-03 — alternating full-MLP inverse scaffold

### Change

Added `solvers/sdf_inverse/neural.py`,
`solvers/sdf_inverse/neural_optimization.py`, and
`run_mlp_sdf_inverse_comparison.py`. The accepted implicit state is now able to
be a geometrically initialized residual MLP with all network weights trained.
The missing Kress shape adjoint is not papered over with weight-wise finite
differences: a small smooth normal-mode basis supplies black-box data
directions, and each accepted contour is re-distanced into the MLP with frozen
polygon-distance labels, boundary/offset anchors, exterior samples, and an
Eikonal term. A new forward solve must retain the data decrease or the entire
cycle is rejected. Known contour failures are typed as infeasible geometry so
they can trigger stencil shrinking/backtracking without hiding solver errors.

Eikonal-only inner optimization was rejected. It neither identifies a zero set
nor preserves one, and mutating a model inside the existing cached
finite-difference evaluator would invalidate its numerical Jacobian.

### Focused validation only

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest \
  pytest/sdf_inverse/test_neural_mlp_inverse.py -q
```

Result after hardening: `7 passed in 2.16 s`. The tests cover polygon sign/distance,
finite smooth modal fields at the centre, deterministic random-hidden MLP
initialization, non-circular re-distancing with an Eikonal gate, and one
transactional accepted inverse cycle using a cheap geometry observable. They
also cover terminal convergence between check intervals, Method-B validation
translation, exact-initial early exit, caller-mode restoration, redistance
curve drift, and worst-residual aggregation over modal trials. The existing
raw-unconstrained-MLP rejection check also passed separately.

No real MOD/Kress neural inverse, multi-seed sweep, fine-grid topology audit,
or full first-party suite was run in this change. Those expensive checks and
any accuracy claims are deliberately left for a later calibrated result
bundle; the checked low-dimensional comparisons remain the current evidence.

---

2026-09-03 — modal step regularization after a measured high-mode ripple

### What was wrong

The first real runs of the alternating MLP inverse were rendered as contour
videos, and both circle-target cases visibly converged toward a five-lobed
star. The stored target polyline in those bundles is a true circle (radial
standard deviation `8e-17 m`), so this was the iterate, not the plot. Fitting
radial harmonics to the stored contours:

| case | `k=5` amplitude, initial -> final | mean radius, final |
|---|---:|---:|
| `mlp-circle-to-circle`, Kress | `0.00 mm -> 8.99 mm` | `52.1 mm` |
| `mlp-ellipse-to-circle`, Kress | `0.05 mm -> 12.93 mm` | `48.4 mm` |

The low modes were converging correctly at the same time -- centre `(0.480,
0.520) -> (0.495, 0.505) m`, mean radius `65.0 -> 52.1 mm` -- so the ripple was
riding on an otherwise working inverse. `maximum_mode` was 5, the highest mode
in the basis.

### Cause, measured not assumed

`diag(J^T J)` normalized by its maximum, on the first modal Jacobian:

| `k` | circle target, `ka = 1.67` | star target, `ka = 5.01` |
|---:|---:|---:|
| 0 | `1.000` | `0.965` |
| 1 | `0.986` | `0.168` |
| 2 | `0.898` | `0.504` |
| 3 | `0.384` | `0.267` |
| 4 | `0.090` | `0.251` |
| 5 | `0.011` | `0.403` |
| 6 | -- | `1.000` |
| 7 | -- | `0.978` |

On the circle the `k=5` column carries about 1% of the strongest mode's
sensitivity. Four independent choices then turned that into a growing ripple:
the Levenberg damping decayed by `0.3` per accepted cycle with no floor and
reached about `5e-10` after twelve; Gauss-Newton inverted the small singular
value; an oversized step was brought inside the field-update trust region by
rescaling, which preserves direction and therefore divided away the resolvable
content instead of the ripple (`maximum_modal_field_update_m` read exactly its
`4e-3` cap at every iteration in both cases); and acceptance asked only for
`loss < current_loss`, which a ripple fitting representation error satisfies
indefinitely.

A fifth coupling was separate and made convergence unreachable rather than
wrong: the inner re-distancing stopped at its own `eikonal_rms_tolerance` of
`0.2` while the outer loop refused to call anything above `0.15` converged, so
every run could only end at `maximum_iterations`.

### Change

`solvers/sdf_inverse/neural_optimization.py`

- `minimum_damping` floors the Levenberg damping.
- `curvature_penalty_weight` adds a `k**4` Tikhonov ridge referred to the
  largest diagonal of the normal matrix. At `1e-4` its threshold at `k=5` is
  `0.0625` against a measured diagonal of `0.011`, so it dominates the
  unresolvable mode by about five while sitting at 2% of the `k=3` diagonal
  and 0.2% of the `k=2` diagonal. On the star, where `k=6` and `k=7` are the
  best-determined columns, the same weight is a 13-24% ridge and does not
  block lobe recovery.
- `_bounded_modal_step` enforces the trust region by raising the damping,
  which shortens the step and rotates it toward steepest descent.
  `max_trust_region_solves` bounds that search; the old rescale survives only
  as the fallback, and `max_trust_region_solves=0` reproduces the old
  behaviour exactly.
- `_sufficient_decrease` applies an Armijo test against the step's own
  predicted decrease. The post-redistance check stays a strict decrease:
  re-distancing perturbs the shape by an amount that does not shrink with the
  step length, so an Armijo test there would reject small steps for a reason
  unrelated to the search direction.
- `AlternatingNeuralInverseConfig` now rejects an inner Eikonal tolerance
  above the outer gate.
- `resolvable_maximum_mode(wavenumber, radius)` returns
  `ceil(ka + ka**(1/3))`. It is a reporting heuristic with the shape of the
  Wiscombe multipole truncation, not a theorem.
- `NeuralInverseIteration` records `applied_damping`.

`run_mlp_sdf_inverse_comparison.py` defaults `--maximum-mode` to that estimate,
reports the budget in `metrics.json` under `mode_budget` and in `summary.md`,
and sets the inner Eikonal tolerance to `0.1` -- under the outer gate, but not
far under, because a wrong ellipse or star needs about `6e-2` to fit at all
inside the step budget. An explicitly larger basis is still accepted and is
flagged with `exceeds_resolution`.

### Measured effect

Re-running the four cases with the regularized step, both solvers, and a budget
large enough to let each run end on its own:

| case | solver | max boundary error, before -> after | holdout rel. L2, before -> after |
|---|---|---:|---:|
| circle -> circle | Kress | `1.895e-2 -> 6.335e-4 m` | `1.137 -> 4.253e-2` |
| circle -> circle | MOD | `1.952e-2 -> 6.403e-4 m` | `1.146 -> 8.394e-2` |
| ellipse -> circle | Kress | `2.513e-2 -> 6.050e-3 m` | `1.614 -> 4.940e-1` |
| ellipse -> circle | MOD | `2.602e-2 -> 6.152e-3 m` | `1.641 -> 5.089e-1` |
| star -> star | Kress | `3.009e-2 -> 4.855e-3 m` | `8.432e-1 -> 2.419e-1` |
| star -> star | MOD | `3.016e-2 -> 4.757e-3 m` | `8.541e-1 -> 2.577e-1` |

Three of the four cases now stop on `no_decreasing_redistanced_step` on both
solvers rather than at an iteration cap. `ellipse -> star` still used its whole
budget at 60 and is being re-run at 150; its 60-cap Kress result was
`4.227e-2 -> 8.535e-3 m` boundary error against `4.092e-2 m` before.

The star is the load-bearing check, because `k=5` there is the same column that
had to be suppressed on the circle. Radial harmonics of the recovered contour,
in millimetres, against a target of `50.000` mean radius and `12.500` at `k=5`
with every other harmonic zero: Kress recovers `50.13` and `12.255` with no
spurious harmonic above `0.973`; MOD recovers `50.16` and `12.180` with none
above `1.217`. The prior priced the same column correctly in both regimes
without being told which case it was in.

A negative control is kept at
`results/inverse_solver_comparison/mlp-ellipse-to-circle-mode5-control-20260903/`:
the same case at `--maximum-mode 5`, above its resolution estimate of 3,
reaching the same training error with `1.515e-2 m` (Kress) and `1.853e-2 m`
(MOD) boundary error against `6.050e-3` and `6.152e-3 m` for the capped basis.
The regularization removes the runaway but not the cost of unaffordable basis
freedom, which is why the estimate is the default.

One consequence is worth flagging for the solver comparison. Before this
change, MOD and Kress agreed to three significant digits in every MLP case,
because geometry error near `2e-2 m` dominated both forwards. At a `6e-4 m`
floor they separate again: circle-to-circle training error is `4.017e-4`
(Kress) against `2.718e-3` (MOD).

### Validation run

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest \
  pytest/sdf_inverse/ pytest/sdf_to_ordered_boundary/ -q
```

Result: `117 passed`. Nine tests were added for the new behaviour: the `k**4`
weights and their disabled form, the trust region rotating a step instead of
rescaling it, the trust region leaving an in-region step untouched, the Armijo
test rejecting a negligible fraction of a predicted decrease, the resolution
estimate against `ka`, and the inner/outer Eikonal tolerance ordering. Three
existing tests were updated to satisfy that new ordering invariant.

---

2026-09-03 — canonical-curve MLP inverse and low-to-high continuation

### Failure diagnosis

The completed Kress ellipse-to-star run in
`results/inverse_solver_comparison/mlp-fixed-ellipse-to-star-kress-20260903/`
showed that the regularized MLP loop still had two coupled floors. It accepted
25 updates and stopped at `spectral_tail_growth_limit`; training relative L2
changed only `1.194 -> 1.039`, holdout changed `1.003 -> 1.043`, and maximum
boundary error worsened `42.03 -> 46.67 mm`. The desired radial `k=5`
amplitude remained about `0.47 mm` against `12.5 mm`, while the initial
ellipse's `k=2` content grew.

The forward systems themselves were not the failure: the maximum Kress linear
residual was about `1.5e-14`, and the exact target passed through the same
Kress/Method-B forward seam agreed with the independent observations to about
`4.2e-5` relative error. Runtime attribution instead found `730 s` in the old
inverse-forward wrapper and `217 s` in neural re-distancing out of `948 s`.
A comparable single probe measured about `1.25 s` for dense SDF boundary
extraction and `0.20 s` for Kress, so extraction dominated the nominal
"forward" bucket. Post-redistance contour drift was only `38-120 micrometres`
in absolute terms, but it remained a large and sometimes larger-than-step
fraction late in the trajectory and was fed back into every new Jacobian.

The 0.2 mm radial-tail cap was also not a valid default trust region for this
geometry. Radial Fourier order and normal-displacement order coincide on a
circle, not on an ellipse. A measured admissible ellipse update in the active
normal basis created about `0.224 mm` of radial content above that basis, so
the hard cap could reject ordinary geometric travel rather than only a ripple.

### Change

- `sdf_inverse.forward.predict_paired_curve_response` now dispatches an
  existing `PeriodicCurve2D` directly to MOD or Kress. Modal finite-difference
  probes no longer evaluate the MLP, run marching squares, project a zero set,
  or refit Method B.
- Direct normal-mode updates preserve the canonical node phase and Fourier
  bandwidth. Probe trials receive inexpensive node-polygon/bounds/regular-jet
  checks; a data-decreasing line-search candidate is rebuilt once with dense
  continuous validation before it may be accepted.
- The validated direct curve and its already-computed BEM response are the
  accepted inverse state. All MLP weights are re-distanced to that curve, then
  its extracted zero set is checked for topology, field quality, and geometric
  drift. This is a representation audit only: the extracted curve is not fed
  into the next Jacobian and does not trigger a redundant BEM acceptance solve.
- Multiple frequencies now use cumulative low-to-high continuation by
  default. The `0.5,1.5,2.5 GHz`, `k=5`, 80-iteration calibration uses
  frequency prefixes with budgets `20/20/40` and mode ceilings `1/3/5`.
  Canonical contour, MLP representation, damping, and deterministic sampling
  state carry between stages. `--no-frequency-continuation` retains the joint
  objective for controlled comparisons.
- The Levenberg search still raises damping to rotate an oversized direction,
  but now refines the feasible/infeasible bracket in log damping. It therefore
  uses the least over-damped feasible step instead of the first decade endpoint.
- Radial spectral tail remains in every trajectory and result, but its hard
  growth cap is disabled by default and available only through an explicit
  `--maximum-spectral-tail-growth-mm`. When enabled, continuation refers each
  active mode to the original contour rather than re-baselining every stage.
- Result bundles store canonical and MLP-representation curves and responses
  separately. Timings distinguish direct objective forwards, neural
  re-distancing, and selected-candidate geometry/MLP audits; backend BEM and
  direct curve-update time are also exposed separately, and failed
  re-distancing attempts contribute to explicit attempt/step counters.
- A convergence claim now requires small realized loss and geometry changes,
  a small un-backtracked trust-region model direction, MLP-to-canonical drift
  and boundary-field residual below the geometry tolerance, and an Eikonal
  RMS below its gate. The same representation checks apply to stationary
  line-search exhaustion, not only to accepted updates.

### Focused validation only

No long inverse was run for this change. The final direct curve-forward,
normal-update, continuation-driver, convergence, re-distancing, video, and
non-optimization solver-neutral regression selection passed (`60 passed`, with
the six real inverse cases deliberately deselected). A short real Kress probe
used the saved initial ellipse
and only the first 0.5 GHz objective. With the coarse `k=1` stage and refined
damping, the step used `3.992 mm` of its `4.000 mm` allowance and reduced loss
from `0.70137` to `0.60493`. The former decade endpoint with the wider `k=3`
stage used only `0.487 mm` and reached `0.68885`. This is directional evidence
for the corrected trust/continuation mechanics, not a reconstruction or
convergence claim. The full calibration remains an explicit user-run command.

---

2026-09-03 — completed canonical diagnostic and full-band mode continuation

### Long-run result

The user-completed Kress run in
`results/inverse_solver_comparison/mlp-canonical-ellipse-to-star-kress-20260903/`
did not converge. It accepted 15 updates, and every continuation stage stopped
with `no_acceptable_mlp_distillation`. Full-band loss changed
`2.223592919 -> 2.157108810`, training relative L2
`1.194114882 -> 1.031121445`, holdout relative L2
`1.003360055 -> 0.942955819`, and canonical maximum boundary error
`42.0309 -> 27.8343 mm`. Final MLP-to-canonical maximum drift was
`0.497114 mm`; the corresponding relative response discrepancy was
`0.00406356`.

The canonical/direct-curve split nevertheless fixed the measured forward
bottleneck. Inverse time fell from `948.326 s` in the pre-canonical run to
`288.945 s`. The latter separates into `28.375 s` of direct forwards
(`26.744 s` in Kress and `1.007 s` in curve updates), `174.511 s` in neural
re-distancing, and `85.537 s` in selected-candidate geometry and
representation audits. Boundary extraction is no longer repeated inside
every finite-difference or line-search forward. Re-distancing and auditing,
not the forward BEM solve, now dominate.

### Diagnosis and correction

The cumulative low-frequency first stage optimized an objective that did not
constrain the target lobe. It primarily translated and shrank the ellipse:
mean radius changed `50.982 -> 40.345 mm`. The final `k=5` component had the
wrong phase and its vector error worsened `12.480 -> 14.446 mm`. The improved
boundary maximum and data losses therefore did not indicate the desired lobe
recovery.

- This intermediate change made full-band progressive-mode continuation the
  default: all requested
  training frequencies remain active while modal ceilings grow through
  `k=1/3/5`. `--frequency-continuation` retains the cumulative-frequency
  schedule explicitly, and `--no-continuation` requests one full-band,
  full-mode stage.
- Damping resets at each stage. Unused accepted-update budget from the warm
  stages is carried into the final full-mode stage instead of being lost.
- The maximum representation drift defaults to a `1.5 mm` acceptance safety
  cap. The independent `0.2 mm` geometry-convergence tolerance still gates a
  convergence claim, so loosening acceptance does not redefine convergence.
- Full-validation rejection, failed MLP fitting, representation-extraction
  failure, and representation-drift rejection are reported separately rather
  than all being charged to the infeasible-forward count.

At this point no second long inverse had been run. The completed bundle
above is evidence for the diagnosis and the direct-forward speedup, not for
convergence of the new default schedule.

### Focused validation

The direct-update, curve-forward, convergence-diagnostic, neural inverse,
re-distancing, continuation-driver, video, and non-optimization
solver-neutral selection passes (`80 passed`). This includes an explicit
regression that distinguishes dense curve-validation rejection from an MLP
distillation failure. No full inverse case was started during validation.

---

2026-09-03 — progressive-mode failure and joint full-mode correction

### Long-run result

The user-completed Kress run in
`results/inverse_solver_comparison/mlp-full-band-modes-ellipse-to-star-kress-20260903/`
did not converge. It accepted 74 canonical updates. Training loss changed
`2.223592919 -> 1.268193860` and training relative L2
`1.194115 -> 0.957988`, but holdout relative L2 worsened
`1.003360 -> 1.075114` and canonical maximum boundary error worsened
`42.031 -> 48.442 mm`.

Post-run intrinsic geometry analysis measured `29.206 mm` centre error, mean
radius `44.577 mm`, residual `k=2` amplitude `11.652 mm`, and a `k=5` vector
of `(-3.849, -1.253) mm` with amplitude `4.048 mm`. The five-lobe component
was nearly inverted and its vector error was `16.397 mm`. Dense maximum/RMS
target distance was `49.135/19.457 mm`.

The MLP represented this bad canonical contour faithfully: maximum drift was
`0.243 mm`, its response discrepancy was `0.002329` relative, and all neural
fit, extraction, and representation-drift rejection counts were zero. Stage 1
accepted 20 `k=1` updates. Stage 2 accepted four `k<=3` updates and recorded
37 dense-validation rejections. Stage 3 accepted 50 `k<=5` updates before the
overall `no_decreasing_modal_step` stop.

Total inverse time was `377.523 s`. Direct forwards used `232.739 s`, including
`225.264 s` in Kress; re-distancing used `88.257 s`, and geometry/MLP audits
used `55.849 s`. Boundary extraction remained outside the 1,458 modal forward
attempts. The increased forward share is therefore BEM work from the much
longer trajectory, not regression to extraction inside each probe.

### Diagnosis

Keeping the full frequency band active was insufficient because the modal
basis was still progressive. Twenty-four low-order updates changed the basin
before the target `k=5` direction became available. The falling training loss
therefore hid worse holdout and true geometry.

The older full-basis-from-start run in
`results/inverse_solver_comparison/mlp-ellipse-to-star-nystrom-20260903/`
provides a useful historical contrast. It had recovered `k=5` by
iteration 50; final Kress geometry had `1.626 mm` centre error,
`k=5 = (12.055, -0.558) mm`, and `7.467 mm` dense maximum target distance.
That run predates canonical state ownership, so it is not validation of the
current optimizer. It also used a different acquisition, so it does not
uniquely isolate the schedule; it motivates a matched test of early access to
the full basis.

### Change

- The default is now one joint full-band, full-mode stage.
  `--joint-full-band` is the preferred explicit selector. Progressive-mode
  and cumulative-frequency continuation remain explicit experimental modes.
- `max_backtracks` now counts reductions after the un-backtracked candidate.
  Its new default value of six evaluates the full trial plus six reductions
  through `1/64`. The former five-reduction limit omitted the sixth reduction
  that clears the dense-validation barrier measured in stage 2.
- Failed-step classification retains the best direct canonical candidate. A
  stationary canonical update that the MLP has not represented within the
  convergence gates now stops early as
  `representation_limited_stationary`; it neither claims convergence nor
  consumes the rest of the iteration budget.

No long inverse has been run after this correction. The recommended next run
matches the historical two-frequency, 12-pair, full-`k<=6`, 150-update setup,
but uses the current canonical/audit-only optimizer and explicit
`--joint-full-band` mode.

### Focused validation

The direct-update, curve-forward, convergence-diagnostic, neural inverse,
re-distancing, continuation-driver, contour-video, and non-optimization
solver-neutral selection passes (`95 passed in 28.90 s`). Python compilation
also passes. No full inverse was started during this validation.

---

2026-09-04 — joint-`k<=6` failure and selected-update remeshing

### Long-run result

The user-completed Kress run in
`results/inverse_solver_comparison/mlp-joint-k6-ellipse-to-star-kress-20260903/`
did not converge. Fourteen updates passed the progress-only driver gate before
the optimizer stopped as `representation_limited_stationary`. Training loss
changed `1.423241629 -> 0.542048191`, training relative L2
`1.192384 -> 0.738845`, holdout relative L2
`1.053290 -> 0.935345`, and maximum boundary error
`42.031 -> 35.114 mm`. The data decrease was substantial but the final shape
was still wrong: the canonical stored-curve audit measured
`k=5 = (-0.420, -4.817) mm` against the target `(12.500, 0) mm`, a
`13.788 mm` vector error.

The run requested modes through `k=6`. Its wave-based limit was also six, but
the 12-angle paired scan can identify both real coefficients only through
`k=5`. This explicit over-limit request is recorded in `metrics.json` and
prevents interpreting the run as an accuracy validation.

### Diagnosis

The joint schedule removed progressive-mode staging but exposed a more direct
geometry defect. The first seven accepted normal updates all saturated the
former `4 mm` displacement cap (`3.975--3.998 mm`). Repeated phase-preserving
Fourier updates then collapsed the canonical parameterization: minimum speed
divided by mean speed fell from approximately `1` to `0.003`, maximum absolute
curvature reached approximately `3.03e6 1/m`, and 83 full continuous
validations rejected candidate curves. The apparent stationary modal state
was therefore not evidence of a well-resolved geometric optimum.

The other diagnostics rule out the earlier suspected bottlenecks. All 14
re-distance attempts succeeded, with zero representation-extraction,
representation-drift, or spectral-tail rejection. Final MLP-to-canonical
drift was `0.525 mm` and its response discrepancy was `0.006237`; those values
miss the strict representation convergence gates but do not explain the
canonical parameterization collapse. The maximum inverse linear-system
residual was `8.58e-15`, so BEM algebraic convergence was also intact.

Total inverse time was `96.102 s`. Direct forwards used `48.895 s`, including
`46.369 s` in Kress and `1.618 s` in curve updates; re-distancing used
`26.810 s`, and geometry/MLP audits used `20.132 s`. The run made 472 forward
attempts, nine of them infeasible. Boundary extraction remained outside the
modal finite-difference loop.

### Change

- Finite-difference probes and preliminary line search remain phase-preserving
  and extraction-free. Once a candidate supplies sufficient decrease, the
  same modal update is rebuilt with arc-length redistribution and full
  continuous validation.
- The remeshed curve receives a fresh BEM solve, and its response must pass the
  sufficient-decrease test again. Only that coherent curve/response pair can
  be re-distanced into the MLP and become the next canonical state.
- The default maximum modal displacement is reduced from `4.0` to `2.0 mm`;
  `--maximum-modal-update-mm` exposes the value explicitly. This is a safety
  response to seven consecutive cap-saturating steps, not a calibrated
  convergence claim.
- A full accepted step may reduce damping, but a backtracked accept retains
  the damping that produced its direction. This avoids immediately rebuilding
  the same damping through another reject/escalate cycle.
- Stationary updates with dense continuous-validation rejection now stop as
  `geometry_limited_stationary`. `representation_limited_stationary` is
  reserved for stationary canonical motion without that geometry barrier but
  with unmet MLP convergence gates. Neither is convergence.
- Live progress and every trajectory CSV row now record the accepted
  backtrack count, raw trust-region versus accepted-step predicted relative
  decrease, arc-refit RMS/maximum displacement, and speed ratio before/after
  refitting. A recurrence of the collapse is therefore directly observable.

These corrections target the measured failure while retaining cheap direct
curve probes. They have focused test coverage, but no post-correction long
inverse has yet validated convergence or reconstruction accuracy. The final
direct-update, curve-forward, convergence, neural inverse, re-distancing,
driver, video, and solver-neutral selection passed (`100 passed in 23.38 s`);
Python compilation and the documentation diff check also passed. No new
long-run command is prescribed in this entry.

## 2026-09-05 — Inverse pipeline audit and correctness repairs

### Hypothesis and review scope

The current MLP path may be doing redundant representation work after a
successful canonical-curve update. Review covered the parameter-FD inverse,
alternating neural path, shared extraction, Kress multi-component forwarding,
legacy MOD adjoint evidence, experiment artifacts, and material/3-D scope.
Existing user changes and saved experiment bundles were preserved.

The [dated review](inverse_pipeline_review_2026-09-05.md) records the verdict
and proposed design choices. Its numerical reconstruction/time values come
from the saved 2026-09-04 radial-continuation K5 bundle, not a new long run.
No material inversion, topology optimizer, Kress adjoint, or 3-D extension was
implemented in this audit.

### Repairs

- Retain a surviving one-sided FD probe at an active parameter bound. Do not
  label missing Jacobian columns or arbitrarily small rejected steps as
  convergence. Recognize true declared-bound optima with complete projected
  gradients, preserving raw gradients in iteration records.
- Enforce outward field-gradient direction for the declared negative-inside
  convention in single- and multi-component ordered geometry. Sign-reversed
  fields previously passed CCW canonicalization and represented the wrong
  material region silently.
- When only a canonical initial curve is supplied, extract the current MLP
  representation once instead of assuming zero drift. Explicit audited
  continuation curves retain their existing reuse path.
- Enforce radial curve sampling against its own Cartesian bandwidth K+1.
- Add the exact physical experiment snapshot to new MLP metrics: acquisition
  arrays, complex source strengths, frequencies, materials, physical constants,
  target parameters, and observation-noise policy.

### Validation

New regressions reproduced the failures before repair. The integrated command
after the initial repairs passed `400 passed, 300 warnings in 160.05 s`:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest \
  pytest/sdf_inverse pytest/ordered_boundary pytest/sdf_to_ordered_boundary \
  pytest/gpr_bem_mod pytest/gpr_bem_kress pytest/multicylinder_ref \
  pytest/sdf_bem_multicomponent pytest/nystrom_ref -q --disable-warnings
```

That integrated run preceded the final projected-gradient follow-up. Its
optimizer and bound-stationarity regressions subsequently passed `14 passed
in 0.12 s`; the solver-neutral tests also passed after the stopping change.
The final complete `pytest/sdf_inverse` rerun, using the same environment
above, passed `156 passed in 79.21 s` after the projected-gradient follow-up.
`git diff --check` also passed.
Warnings in the broad run were Matplotlib/pyparsing deprecations and existing
MOD compression diagnostics. The run was scoped to these solver, inverse,
and geometry packages and did not regenerate saved comparison studies.

## 2026-09-05 — SDF/Kress guide first batch (A/B/C)

### Scope and change

Read the complete [priority brief](codex_sdf_kress_priorities_2026-09-05.md)
and implemented its first batch only. The
[implementation/evidence report](sdf_kress_first_batch_2026-09-05.md) owns the
API mapping, measured comparisons and qualifications. D–H remain deferred.
Existing dirty-tree changes and all historical artifacts were preserved.

Added explicit strict/curve-only/final-export policies around the same
canonical optimizer, separate reconstruction and representation outcomes,
smooth continuous-distance targets independent of BEM N, and the bounded
exact-ellipse/ordered-label parameterization experiment. Strict policy,
polygon supervision, production Method B and solver selection defaults remain
unchanged. Export works on a copy and cannot replace a valid canonical state
on failure. Failed optional driver diagnostics retain canonical artifacts;
unavailable metrics are null rather than zero, and unexpected programming
errors are not swallowed.

### Fresh measurements and decision

- A first ran the short deterministic contract test, then the saved star
  configuration without competing project benchmarks. All three policies had
  exactly equal 44-update canonical trajectories and holdout field error
  `1.3393e-8`. Reconstruction times were strict `229.74 s`, curve-only
  `81.61 s`, export-only `81.62 s`; final export took another `8.41 s` and
  failed its 1,200-step fit budget. Strict representation also failed its
  independent final gate. Canonical N128→256 fields agree to `5.89e-14`
  relative. Zero neural calls during curve/export reconstruction were
  instrumented, not inferred. Shared preparation and all other phases are
  separately recorded. These are single-run timings.
- B compared polygon versus continuous-distance labels at identical sample
  coordinates, model initialization and 600-step budgets. Circle extracted
  drift improved `0.233→0.0385 mm`; star `1.605→0.535 mm`. Physical fields
  improved under refinement, but every fit failed the strict training gates,
  the star still exceeded `0.2 mm`, and its global distance RMS worsened
  slightly. Circle truth is independent Mie; the exact-star Kress reference
  is self-refined, not an independent solver. No sampling-change experiment
  is claimed.
- C generated 82 method records and 246 physical-field rows across four
  cases and independent K/N ladders, with seven explicit fallbacks. Ellipse
  ordered-label fitting met the same geometry/field gates at K1/N32 versus
  Method-B K16/N32 without increased condition or node count. It did not
  achieve the declared 10% work-reduction threshold. Star/non-star candidates
  qualified where B did not within the bounded ladder; that is not a
  matched-accuracy speed comparison. The penalty harmed the non-star result.
  Retain opt-in; no default promotion. A separately hashed bandwidth-decision
  supplement reads frozen measurements without rewriting them.

Commands, immutable physical configurations, observation/geometry arrays,
reference convergence, resolutions, source hashes and dirty-tree provenance
live in the fresh bundles linked from the report. Post-measurement driver
failure-path/reporting repairs do not rewrite their source identities.

### Regression validation

All commands used:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  pytest/ordered_boundary pytest/sdf_to_ordered_boundary \
  pytest/gpr_bem_kress pytest/sdf_bem_multicomponent pytest/multicylinder_ref \
  pytest/solver_comparisons/test_parameterization_aware_driver.py
```

Result: `222 passed, 276 warnings in 39.32 s`.

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q --disable-warnings \
  pytest/gpr_bem_mod pytest/nystrom_ref
```

Result: `43 passed, 24 warnings in 71.52 s`.

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q --disable-warnings \
  pytest/sdf_inverse
```

Result: `186 passed in 74.75 s`, including the nine driver instrumentation,
initialization-failure, artifact-preservation and programming-error tests.
These three disjoint selections total 451 passed. Warnings are existing
Matplotlib/pyparsing deprecations and MOD compression diagnostics. The studies
were not regenerated by this regression run. All 100 final A/B/C NPZ archives
(1,144 numeric arrays) loaded without pickle. `git diff --check` passed.

The broad inverse run preceded three final narrow reporting repairs:

- An ambiguous legacy `representation_limited_stationary` reason does not by
  itself imply reconstruction convergence. An explicit internal flag now
  records the verified consecutive accepted-state branch; a rejected tiny
  trial keeps reconstruction nonconverged without altering the old strict
  `converged`/`stop_reason`. The saved star took the verified branch: its
  final stage has five accepted updates and exactly 116 evaluations, with
  no additional failed-step Jacobian after the last row; total stage work is
  `286+461+116=863`. Its measured conclusion is unchanged.
- Failed distance-target refinement before any network query reports
  `representation_evaluated=false`, retaining null representation errors.
- Finite predicted fields can overflow residual normalization. The optional
  export forward audit now catches that `FloatingPointError` as an export
  failure, preserving the model and canonical reconstruction; unexpected
  programming/contract errors still propagate.

The policy and neural-convergence suites passed `33 passed in 0.88 s` after
these repairs, including both actual legacy stopping paths and the finite-input
overflow regression. No numerical optimizer, quadrature, observation or
measured-result file was changed by this final reporting follow-up.

The final combined policy/convergence/driver rerun, under the same environment,
passed `42 passed in 0.91 s`:

```bash
python -m pytest -q --disable-warnings \
  pytest/sdf_inverse/test_distillation_policy.py \
  pytest/sdf_inverse/test_neural_inverse_convergence_diagnostics.py \
  pytest/sdf_inverse/test_representation_ablation_driver.py
```

This overlaps the broad suite; it is not 42 additional independent tests.

## 2026-09-06 — bounded E and H1 follow-up

Authorization: after the completed A/B/C batch, the user asked to continue
until a design decision was needed. Existing defaults and dated measurements
are preserved; these are new explicit-import experiments. Full scope and
qualifications are in [`sdf_kress_followup_2026-09-06.md`](sdf_kress_followup_2026-09-06.md).

**E hypothesis/change:** verify the derivative of the actual discrete Kress
objective before introducing a neural-derived update rule. New analytic jets
differentiate all assembled blocks, incident traces, receiver operators and
material dependence. A conjugate adjoint handles real-stacked fixed weighting
and duplicate paired complex observations. It returns directional covectors,
not invented normal densities. New independent matched-material cylinder
sensitivity supplies a non-FD zero-contrast material oracle.

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_kress_shape_derivative_validation.py \
  --output-dir results/kress_shape_derivative/refined-audits-20260906
```

Result: 96/96 fixed-node records pass; the separate independent-reference and
physical-refinement gate passes. Wall time 77.77 s. The first
`bounded-20260906` artifact remains unchanged, with an explicit explanation
of its inappropriate vanishing-field absolute FD scale and corrected
phase-reference audit. A unit test now guards the zero-contrast error scale.
Unsigned paired-index overflow and tiny-source primal-reassembly checks were
fixed during pre-sweep review. Decision: accept E within its declared
fixed-grid single-interface domain; do not promote the production optimizer
or infer multi-interface/topology derivatives.

**H1 hypothesis/change:** test whether true distance values improve conversion
beyond zero-set projection, ordered labels and tangent information. Five
exact/distorted/frozen-neural cases compare five methods across K1/4/8 and
independently refined N64/128/256. Invalid contacts retain their raw candidate,
query/fitting costs and valid Method-B fallback.

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_distance_tangency_comparison.py \
  --output results/distance_tangency/first-batch-20260906
```

Result: 75 arms, 54 accepted, 21 explicit fallbacks, 86.15 s. No predeclared
>10% matched-error selected-work win; projected/tangent controls also achieve
the low-K exact-ellipse result. Every deliberately distorted metric arm and
every neural metric arm is rejected. A derived bandwidth decision incorrectly
compared fastest-row K instead of minimum qualifying K; a transparent
`decision_supplement.json` and regression correct it without rewriting
measurements. Decision: retain the guards and experimental driver, not a
mandatory metric-distance conversion stage or SDF-specific advantage claim.

After these implementations and reporting corrections, the following
regressions ran with the same thread-limited environment:

```bash
python -m pytest -q --disable-warnings \
  pytest/ordered_boundary pytest/sdf_to_ordered_boundary \
  pytest/gpr_bem_kress pytest/sdf_bem_multicomponent pytest/multicylinder_ref \
  pytest/solver_comparisons/test_parameterization_aware_driver.py \
  pytest/solver_comparisons/test_distance_tangency_driver.py \
  pytest/solver_comparisons/test_kress_shape_derivative_driver.py
python -m pytest -q --disable-warnings pytest/sdf_inverse
```

Results: **265 passed**, 276 existing warnings in 42.38 s; **217 passed** in
61.99 s. These disjoint selections total **482 passed**, before the separate
F/D experiments and their new tests were finalized. No historical comparison
study was regenerated. The final E driver later expanded dependency hashes
and made multi-resolution physical-gate failure set its CLI exit status;
neither changes numerical behavior of the saved passing run.

### F — frozen neural metric comparison, same follow-up

After E passed, a separate explicit-curve optimizer compared identity,
Sobolev angular length 0.35 and frozen initial neural seeds 0/1/2 on circle/star.
The neural metric projects `-partial_theta(phi)/|grad(phi)|` into the declared
radial chart, applies the mass-whitened normalized covariance to E's discrete
covector and never adds a second `ds`. All arms use the same step/budget gates,
zero regularization and true-objective acceptance. Only the 65 output-head
columns of 5,441 MLP parameters are active at the exact initial circle; there
is no training, extraction or model query after metric initialization.

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_neural_metric_comparison.py \
  --output-dir results/neural_metric/comparison-20260906
```

Result: ten arms completed in 360.63 s without changing predeclared settings.
All final numerical-refinement gates pass, but **no neural-metric arm wins**.
Circle identity/Sobolev meet the configured training-loss stop; their held-out
errors remain nonzero. Neural circle arms and all star arms exhaust the
accepted-step budget. Both explicit star controls make better training and
held-out progress than every neural seed at the same 28 frequency-level
forward calls. The full [summary](../results/neural_metric/comparison-20260906/summary.md)
and dated follow-up separate those failures from numerical physics resolution.

Sixteen focused tests passed in 1.36 s before timing. Peer review checked
mass/active-mode projection, exact jets, step and objective consistency,
head-column counts, immutable geometry, stopping semantics and work accounting.
Saved accepted-row gradient norms are pre-step; row losses/coefficients are
post-step. Decision: no default promotion; the result does not test trained
neural priors, direct neural zero-set optimization, topology or stronger
spectral-matched explicit smoothers. No historical artifact was overwritten.

### D — one unknown interior permittivity, same follow-up

The separate bounded experiment rebuilds complete material-dependent Kress
predictions for every candidate and uses E's scaled real residual Jacobian.
Its one-entry cache validates immutable observation, normalization and scene
identities. Six declared joint parameters cover radial-K2 geometry plus one
positive lossless interior permittivity; exterior and source calibration stay
fixed. Independent Mie observations are frozen before candidate evaluation.

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_material_inverse_comparison.py \
  --output results/material_inverse/bounded-20260906
```

Result: eight arms completed in 73.55 s, with five physical recoveries and three
retained high-permittivity-start failures. The clean fixed/joint low starts
recover epsr 3; noisy fixed/joint cases recover 3.000807/3.000048. A fixed start 9
stops on TRF's cost criterion at 10.1433 without passing independent projected
stationarity or physical recovery; both high joint starts exhaust their
40-evaluation budgets at shape bounds, near epsr 4.12, with large held-out
errors. All numerical forward refinements and material-sensitivity gates pass.
Near the successful joint result, scaled radius/material columns correlate
at approximately -0.960; this is a local sensitivity diagnosis, not a global
identifiability proof. No settings or starts were changed after results.

Eleven focused tests passed in 2.82 s before timing. Review corrected a mutable
normalization/cache gap, integer-index aliases, failed-forward work accounting,
Mie-call overcount and geometry-refinement qualification. A mistaken initial
test checked the identity diagonal of the full system; the corrected test
checks the material-dependent analytic S-block diagonal. Immutable data and
all source hashes remained unchanged during the measured run.

Decision: retain the bounded material experiment and explicit failures.
Robustness to starts is the practical next design issue before adding more
material variables. Distinct per-component materials, nested regions,
conductivity, topology proposals and 3-D remain deferred. The complete report
is [`sdf_kress_followup_2026-09-06.md`](sdf_kress_followup_2026-09-06.md).

### Final combined follow-up regression

After all E/H1/F/D code and focused repairs were finalized:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q --disable-warnings \
  pytest/ordered_boundary pytest/sdf_to_ordered_boundary \
  pytest/gpr_bem_kress pytest/sdf_bem_multicomponent pytest/multicylinder_ref \
  pytest/sdf_inverse \
  pytest/solver_comparisons/test_parameterization_aware_driver.py \
  pytest/solver_comparisons/test_distance_tangency_driver.py \
  pytest/solver_comparisons/test_kress_shape_derivative_driver.py \
  pytest/solver_comparisons/test_material_inverse_driver.py
```

Result: **514 passed**, 276 existing warnings in **123.98 s**. The F driver
contracts are in `pytest/sdf_inverse/test_neural_metric.py` and included here.
This final selection overlaps the earlier 482-test run; counts are not added.
All four final E/H1/F/D numeric NPZ bundles loaded with `allow_pickle=False`:
1,244 finite numeric arrays, none with object dtype. `git diff --check`
passed. No historical study was regenerated or old measured bundle edited.
F's post-run audit matched all 60 recorded source hashes; it is explicitly a
post-run comparison, not a claimed during-run hash monitor. No production
default, normal solver selector or git commit changed.

## 2026-09-06 — bounded explicit shape/material robustness

The user approved the practical robustness branch after the E/H1/F/D
follow-up. New explicit-import `sdf_inverse.robust_material_inverse`
orchestrates the existing radial-K2, single-interior-permittivity model with
full-band local fitting, cumulative continuation, or deterministic
contrast-stratified multistart. No SDF or new material region is introduced.
The baseline D module, historical artifacts and production defaults remain
unchanged. Full details and the next design boundary are in
[`material_robustness_2026-09-06.md`](material_robustness_2026-09-06.md).

The frozen 15-workflow comparison uses historical D circle data, noise,
acquisitions and high-material starts verbatim, plus an independently
specified radial-K2 noncircular target with interior `epsr=8.4` (background
6). New observations use separately refined native-curve Nyström kernels.
Two complex-noise cohorts and three fixed-circle controls are included.
Only full-band training scores select the delivered candidate; all 15
selections are sealed before any candidate meets geometry or held-out data.

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_material_robustness_comparison.py \
  --output results/material_robustness/bounded-20260906
```

The shared per-workflow caps are 400 frequency-level forward attempts and
2,400 analytic-direction attempts, including screening/failed/audit work.
Continuation stages receive 40/40 evaluations; full-band controls receive
80; multistart retains two branches. This is not a matched-cost comparison.

Measured physical recovery: **full-band 0/5, continuation 2/5, multistart
5/5**. Continuation succeeds only for the new noncircular target, clean and
noisy. All seven successful recoveries pass the separate `1e-7` scaled
projected-gradient gate; all eight failed recoveries fail that stationarity
gate. Every allocated search completes and none exhausts a global cap.
The noisy multistart circle/noncircle geometry errors are 64.89/51.05 µm;
interior permittivities are 3.0000483/8.4019470 and clean shifted-angle
holdout field errors are 0.003488/0.006427. All selected candidates, including
physical failures, pass forward refinement; the maximum N128→256 field
change is `5.55e-13`.

Elapsed time is **283.71 s**, with 260.81 s workflow, 18.35 s qualification,
1.32 s data preparation and remaining artifact/other overhead. Workflow
work is 1,203 frequency forwards and 5,268 analytic directions; qualification
adds 180 forwards, new independent observations add eight frequency solves,
and historical circle observation regeneration adds zero. All frozen
input/selection hashes match; recorded source changes during the run are
empty. Independent saved-array review verifies the minimum full-band
ranking, objective replay, physical gates, phase sums, caps, and hashes.

After the timed run, a peer-review numerical edge was fixed only in the
new robust wrapper: finite residual entries whose squared norm overflows
cannot become a selected candidate. The already-paid failure remains in
history with null loss and an explicit reason; valid incumbents and exact
costs are preserved. Two toy regressions cover this edge. No finite-path
settings or arithmetic were retuned and the historical measured bundle was
not rerun. Its source hashes intentionally predate this post-run guard; the
only subsequent source-hash difference is `robust_material_inverse.py`.

Final post-guard regression:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q --disable-warnings \
  pytest/ordered_boundary pytest/sdf_to_ordered_boundary \
  pytest/gpr_bem_kress pytest/sdf_bem_multicomponent pytest/multicylinder_ref \
  pytest/sdf_inverse \
  pytest/solver_comparisons/test_parameterization_aware_driver.py \
  pytest/solver_comparisons/test_distance_tangency_driver.py \
  pytest/solver_comparisons/test_kress_shape_derivative_driver.py \
  pytest/solver_comparisons/test_material_inverse_driver.py \
  pytest/solver_comparisons/test_material_robustness_driver.py
```

Result: **561 passed**, 276 existing warnings in **110.59 s**. This
supersedes the overlapping focused 56-test run rather than adding its count.
The fresh 2,303-array NPZ is finite, numeric and non-pickled; all four JSON
files pass strict parsing and `git diff --check` passes.
No production default, solver selector, historical result or git commit was
changed. Keep the robustness workflow opt-in: five synthetic cases and one
noise realization per target do not establish global convergence or
uncertainty. Distinct materials on fixed-count separated explicit loops are
the recommended next physics scope, subject to the user's decision.
