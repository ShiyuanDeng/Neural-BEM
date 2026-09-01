# Rebuilding the adjoint/inverse for `gpr_bem_mod`

*Planning only — nothing built yet. Written 2026-08-27, before starting, so the
reasoning is on record. Follows the same convention as
`docs/validation_change_log.md`'s "Plan: kernel-differenced quadrature on the
real (compressed) boundary" entry.*

---

## 0. Scope

This plan covers bringing `solvers/gpr_bem_mod/ibim_tmz_adjoint.py` and
`solvers/gpr_bem_mod/ibim_inverse.py` forward to match the Müller +
`analytic_extrapolated` forward operator that `ibim_tmz_system.py` /
`ibim_tmz_forward.py` already implement (`docs/validation_change_log.md`,
"Muller formulation and analytic normal-derivative kernels").

**`gpr_bem_kdiff` is explicitly out of scope.** It has no `ibim_tmz_adjoint.py`
or `ibim_inverse.py` at all, and per `docs/ibim_error_mitigation_literature_codex.md`
§0, building an adjoint against a forward operator that is itself still
missing a load-bearing correction (the off-diagonal log-singular term for
`T` — see `docs/validation_change_log.md`, "`gpr_bem_qbx` built and measured")
is the exact trap that section warns against. If `kdiff` is later finalized,
this plan should be re-run against it, not extended to cover it now.

This is "forward finalized" in the sense Phase H of the codex requires:
Müller formulation chosen, circle validation automatic, `analytic_extrapolated`
kernels the measured winner, direct solve the default. It is *not* finalized
in the stronger sense of §0's checklist — `MULLER_OFFSET_SCALE` is a tuned,
discretisation-dependent constant (not derived), and 8 GHz still fails even
on a perfect circle. Building the adjoint anyway is a judgement call, not a
strict reading of §0; see §12 for why it's made here.

---

## 1. Why this is needed, precisely

The naive framing — "the adjoint differentiates the old operator" — undersells
the actual failure mode and makes it sound like it would fail loudly. It
won't. Read `prepare_ibim_adjoint_context` (`ibim_tmz_adjoint.py:207-251`): it
calls `_prepare_ibim_forward_receiver_rows` → `solve_ibim_tmz_total_field_batch`
(`ibim_tmz_system.py:251`) with `formulation` and `normal_derivative_scheme`
left as `None`, which resolve to the current defaults — `"muller"` and
`"analytic_extrapolated"` (`ibim_tmz_system.py:82,100`;
`ibim_tmz_forward.py:346`). **So the forward value inside the adjoint context
is already correct, current-formulation Müller.** The loss and residual
computed from it (`ibim_tmz_adjoint.py:242`) are right.

What's stale is everything downstream of that: `ibim_adjoint_context_from_receiver_dual`
and the directional-derivative machinery it calls
(`_ibim_system_action_point_directional_derivative`,
`_single_layer_boundary_trace_single_sample_directional`, etc.,
`ibim_tmz_adjoint.py:1026-2167`) hand-differentiate the **old** system
construction — first-kind sum, finite-difference normal-derivative traces —
because that logic was written before the formulation existed and was never
touched by the Müller change (which only touched `ibim_tmz_system.py` and
`ibim_tmz_forward.py`'s *forward* functions, per the 2026-08-24 change-log
entry's file list).

The consequence: **a gradient check that only compares loss values, or eyeballs
that reconstructed shapes look plausible, will not catch this.** Only a
directional finite-difference check on the gradient itself will —
which is exactly what `test/test_ibim_tmz_adjoint.py::...frozen_geometry_finite_difference`
already does, and it already fails: `0.233 < 0.0002` assertion
(`docs/validation_change_log.md`, "Issue 8"). That test is the canary; it
should stay red until this plan's Phase 4 is done, and should be the first
thing re-run after every phase below.

---

## 2. Non-goals

- Do not touch `gpr_bem_ref` or `gpr_bem_kdiff`.
- Do not touch `SirenSDF2D`, learning rates, loss weighting, or any inverse
  hyperparameter — that's Phase H territory in the codex, downstream of this.
- Do not re-open the `MULLER_OFFSET_SCALE` tuning question as part of this
  work. If the adjoint needs a different offset than the forward (unlikely,
  but a compressed boundary's local spacing does move under a shape update),
  treat that as a new, separately-logged finding, not scope creep here.
- Do not attempt to fix 8 GHz or the square-corner case as part of this. The
  circle is the only validation target for Phase 4-6 below.
- Do not add a `formulation="difference"` code path to the adjoint. `ref` is
  frozen and does not need one; building it here doubles the surface area for
  no measured benefit.

---

## 3. Current architecture map

For orientation before Phase 0. All line numbers as of this writing, `gpr_bem_mod`.

| File | Lines | Role today |
|---|---:|---|
| `ibim_geometry.py` | 477 | Untouched by this work. Produces `ImplicitBoundaryBand2D` / `ImplicitBoundarySamples2D`, including `curvature` and `jacobian = 1 - signed_offset * curvature` (`:207-208`) — **already implemented**, contrary to what the pre-split derivation doc in `docs/ibim_shape_derivative.md` claims (see §4). |
| `ibim_tmz_forward.py` | 1044 | Forward-only. `normal_derivative_scheme` dispatch (`:349-370`), analytic kernels (`:371-473`), matrix builders (`:724-844`). No directional/shape-derivative version of any of these exists yet. |
| `ibim_tmz_system.py` | 511 | `build_ibim_tmz_frequency_system` (`:112-214`) does the Müller combination — see the sign-convention comment at `:155-171`, which is the derivation this plan's Phase 2 must mirror for the dual. `solve_ibim_tmz_total_field_batch` (`:251`) is what the adjoint's forward pass already calls correctly. |
| `ibim_tmz_adjoint.py` | 2346 | The file this plan mostly rewrites. Two layers: (a) formulation-agnostic wrapper (misfit, multifrequency loop, B-scan transform, `:157-476`, `:2167-2346`) — reusable; (b) formulation-specific differentiated-solve machinery (`:826-2166`) — stale, per §1. |
| `ibim_inverse.py` | 809 | Calls into (a) and (b) above via the context builders. `_estimate_bscan_shape_gradient_finite_difference` (`:318-412`) already exists and is solver-agnostic — this is the verification tool for Phase 6, not something to build. |
| `run_ibim_circle_inverse_bscan.py` | ~960 | Driver. Already has `--solver` (`:671-676`), resolved via `solver_select.resolve_from_argv()` before `gpr_bem` is even imported (`:24-27`) — the same aliasing mechanism `solvers/README.md` documents. No change needed here beyond what Phase 5 already covers (passing `formulation`/`normal_derivative_scheme` explicitly downstream). |
| `docs/ibim_shape_derivative.md` | 669 | Pre-split derivation, written against a single flat `gpr_bem/` package on a different machine (`/home/haibing/...` paths). Predates Müller. Claims the Jacobian `J_a` term is *not yet implemented* — **this is now false** (`ibim_geometry.py:208`); the doc is stale on at least this point and should not be trusted without re-checking every other claim against current code. |

---

## 4. Phase 0 — re-derive on paper, write a new derivation doc

**Status: done, 2026-08-27.** `docs/ibim_shape_derivative.md` is fully
rewritten against current `gpr_bem_mod` code. It found something this plan's
earlier drafting did not anticipate: the operator isn't assembled as a direct
boundary-to-boundary kernel the way the pre-Müller derivation modeled it.
Every row `i` is evaluated at an *offset probe point* `p_i ± d n_i` against
every column `j`, for all four blocks, not just the diagonal — so a correct
shape derivative has to differentiate through the probe construction itself
(`p_dot_i` and `n_dot_i` both entering, with `n_dot_i` entering *twice* for
`K'`/`T` — once via the probe offset, once via the kernel's own normal
argument). This reframes Phase 1 below: the work isn't "differentiate four
kernels," it's "differentiate one probe-evaluation template, instantiate it
four ways." See `ibim_shape_derivative.md` §3-§6 for the full derivation,
§6.2 for why the Müller combination itself turned out to need no
formulation-specific derivative work (linearity: differentiate each
wavenumber's blocks the same way, then subtract, exactly mirroring how the
forward pass already builds `exterior_family`/`interior_family` separately),
and §11 for the resulting coding order. Also resolved: rebuild-plan §14
open question 3 (does the `analytic_extrapolated` Lagrange extrapolation
commute with the shape derivative) — yes, exactly, because the extrapolation
is a fixed linear functional of the sampled kernel values (§ibim_shape_derivative.md
§3.3).

**Goal:** a from-scratch shape-derivative derivation against the *current*
code, not an update to the old one. Reuse `docs/ibim_shape_derivative.md`
only as a source of which geometric quantities exist (`m_a`, `n_a`, `p_a`,
`J_a`, and their `∂_alpha` counterparts in §3 of that doc look structurally
reusable) — verify each one against `ibim_geometry.py` rather than trusting
the doc's claim about it, given the `J_a` miss above.

New content needed that the old doc does not have at all:

1. **Müller block derivation for the dual.** The old doc derives shape
   derivatives of the first-kind sum system. Needs the equivalent for the
   Müller difference system as actually assembled at `ibim_tmz_system.py:172-198`
   — in particular, get the transpose of the 2x2 block operator (`upper_left`,
   `single_layer`, `hypersingular`, `lower_right`) right, including the sign
   convention noted in the code comment at `:169-171` (`hypersingular_matrix`
   already carries `W = -T`).
2. **Shape derivative of the analytic normal-derivative kernels.** The old
   doc's §3 differentiates geometry (`m_a`, `n_a`, `p_a`, `J_a`) but not the
   *kernel* itself — because at the time everything downstream used a finite
   difference of the potential, which doesn't need its own closed-form
   derivative (the FD stencil IS the derivative, crudely). Now that the
   forward path uses closed-form `∂G/∂n_x` and `∂²G/∂n_x∂n_y`
   (`ibim_tmz_forward.py:371-473`), their shape derivatives need deriving too
   — one more derivative order on top of what `ibim_error_mitigation_literature_codex.md`
   §4b.2 already wrote down.
3. **Which cancellation is the invariant check.** Per the codex's standing
   rule ("do not blindly flip signs... the cancellation is the invariant
   mathematical check"), identify the shape-derivative analogue: probably
   that the derivative of the Müller identity term (`identity ∓ double_layer`
   diagonal) reduces to a known geometric quantity (curvature rate of change)
   independent of the kernel details — worth deriving explicitly as a
   standalone unit-testable identity, not just trusted by inspection.

**Deliverable:** replace `docs/ibim_shape_derivative.md` in place (same
filename — it's already the natural location), dated and with the stale
Chinese pre-split version's specific wrong claims (path, `J_a` status)
corrected or removed. Do not start Phase 1 until this exists in reviewable
form.

**Exit criterion:** a reviewer (human or a second derivation pass) can check
every equation against a named function in `ibim_geometry.py` /
`ibim_tmz_forward.py` / `ibim_tmz_system.py`, the way this plan's §3 does at a
coarser grain.

---

## 5. Phase 1 — shape-derivative kernels in `ibim_tmz_forward.py`

**Status: mostly done, 2026-08-27.** Four new functions added (purely
additive — nothing existing was modified), each verified against central
differences of the already-trusted forward potential functions:
`implicit_single_layer_source_directional_derivative_potential_from_band`,
`implicit_greens_function_mixed_directional_hessian_potential_from_band`,
`implicit_greens_function_pure_target_hessian_potential_from_band`,
`implicit_greens_function_pure_source_hessian_potential_from_band`. See
`docs/ibim_shape_derivative.md` §11a for the full mapping from function to
term, and `pytest/test_ibim_shape_derivative_kernels.py` for the
verification (6/6 passing — two exact regression checks against existing
kernels, four finite-difference checks). **Remaining:** `T`'s own
position-motion terms need a *third*-derivative identity, not yet derived —
see §11a's explicit callout. This is genuinely open work, not something
Phase 3 can silently absorb.

Add the directional derivatives of the four analytic building blocks, mirrored
against Phase 0's derivation:

- `∂/∂p_a [G(p_a, p_b)]` and its normal-derivative analogues, for a boundary
  point `p_a` moving under a shape perturbation (this is *not* the same as
  `∂G/∂n_x` — that's the normal derivative at a fixed point; this is the
  derivative with respect to the point's own position, needed for the shape
  gradient).
- Do this for all four kernels (S, D, K', T-via-`analytic_extrapolated`), so
  the adjoint in Phase 3 never has to fall back to finite-differencing a
  potential the way the *old* adjoint code did (`_one_sided_normal_derivative`,
  `ibim_tmz_adjoint.py:1759`) — that pattern is exactly what
  `ibim_error_mitigation_literature_codex.md` §4b spent an entire section
  arguing against for the forward solve; no reason to reintroduce it here.
- Follow the existing `normal_derivative_scheme` dispatch pattern
  (`ibim_tmz_forward.py:349-370`) so `finite_difference` stays available as a
  fallback/diagnostic scheme for the *shape* derivative too, the same way it
  did for the normal derivative — useful for isolating bugs (compare analytic
  shape-derivative kernel against its own FD at large step, the same kernel-
  correctness test pattern `ibim_error_mitigation_literature_codex.md` §4b.4
  used).

**Test, before wiring into anything:** a standalone kernel-identity check —
compare the new analytic shape-derivative kernel against a central-difference
perturbation of the *existing*, already-trusted forward potential functions
(`implicit_single_layer_potential_from_band` etc.), no solver involved. This
is the cheapest, most isolatable test in the whole plan and should be written
first.

---

## 6. Phase 2 — dual system assembly in `ibim_tmz_system.py`

**Status: done, 2026-08-28**, but simpler than originally planned.
`adjoint_system_matrix(system)` in `ibim_tmz_system.py` returns `A^H` as the
conjugate transpose of the already-assembled dense `system.system_matrix`,
rather than reconstructing it block-by-block. `A` is fully materialized by
the time the forward pass finishes (`xp.concatenate` in
`build_ibim_tmz_frequency_system`), so there is no block-bookkeeping step
left to get wrong — `docs/ibim_shape_derivative.md` §7's block-swap
description is still useful as an explanation of *why* the structure looks
that way, but isn't needed as an implementation step. No separate sanity
check was run against that block description, since the direct transpose
carries no risk the check would be guarding against.

Add a function alongside `build_ibim_tmz_frequency_system`, e.g.
`build_ibim_tmz_adjoint_system`, that assembles the transpose of the Müller
block system for a given `(k_exterior, k_interior)` pair, reusing
`build_implicit_boundary_operator_family` the same way the forward builder
does.

**Sanity check, cheap and mandatory before Phase 3 starts:** at a fixed
boundary and frequency, assemble the forward `system_matrix`
(`ibim_tmz_system.py:192-198`), transpose it numerically, and confirm the new
function's output matches to machine precision. This catches block-ordering
and sign mistakes in five minutes, before they get buried under Phase 3's much
larger surface area. This is the "verify... rather than assuming" instinct
this repo's own history keeps rewarding (§10 of `forward_solver_validation.md`,
the §4b retraction in the codex) — cheap checks that would have caught wrong
attributions early were consistently skipped in favor of reasoning from the
math, and consistently should not have been.

Note `cond(A)` is now ~1e4 (`docs/validation_change_log.md`, Müller
conditioning table), not the ~1e11 the old first-kind system had — the dual
solve itself should be numerically easy; this phase is about getting the
*construction* right, not about conditioning risk.

---

## 7. Phase 3 — rewrite `ibim_tmz_adjoint.py`

**Status: historical first pass, 2026-08-28 — superseded by §7a/§7b.**
`solvers/gpr_bem_mod/ibim_shape_derivative_prototype.py` implements the
**top output row only** of `d/dalpha[A(theta) q]`:
`-Ḋ @ u_dirichlet + Ṡ @ u_neumann`, Müller-combined (each block
differentiated per-wavenumber using Phase 1's kernels, then
exterior-minus-interior, mirroring the forward assembly per
`docs/ibim_shape_derivative.md` §6.2). This is a genuinely separate,
clearly-labeled module — at this first-pass point it was not wired into
`ibim_tmz_adjoint.py`, and its own docstring said so, to avoid a half-finished
piece being mistaken for the real Phase 3 deliverable.

**Explicitly not implemented, by choice, not oversight:**
- The bottom output row (`Ṫ @ u_dirichlet + K̇' @ u_neumann`). `K'` is, per
  `docs/ibim_shape_derivative.md` §11a, fully computable from existing
  Phase 1 primitives and would follow the exact same pattern as `D` below —
  simply not built in this pass. `T` genuinely cannot be built yet; its
  own-point-motion terms need a third derivative of `G` that has not been
  derived (§11a).
- The SDF-specific geometric derivative chain (`docs/ibim_shape_derivative.md`
  §2.3 — `m_dot`, `n_dot` via the tangential projector, `J_dot`, etc.). The
  verification below uses arbitrary point/normal/weight velocity fields, not
  ones derived from an actual `SirenSDF2D` parameter — sufficient to check
  whether the *assembly* is differentiated correctly for *some* smooth
  one-parameter boundary family, but not a check of the geometry chain
  itself, which would need `ibim_geometry.py` involvement.
- `A^H mu = C^H psi` is not solved anywhere here — no adjoint variable, no
  receiver-row derivative (`Ċ`, §8 of the derivation doc), no incident-trace
  derivative (`ḃ`), no actual scalar-loss gradient `dJ/dalpha`. This
  prototype checks one piece of `Ȧq`, not the full adjoint identity.

### Phase 4 verification (the one requested — run once, not iterated on)

Setup: `perfect_circle_boundary_samples`, N=32, radius 0.05 m, center
(0.5, 0.5), real sand/plastic materials from `config.base_config`, 1.5 GHz,
Müller formulation, `analytic_extrapolated` kernels, `use_strict_quadrature=True`
— the actual validated defaults, not a simplified stand-in. Arbitrary
complex `u_dirichlet`/`u_neumann` (not solved from a real incident field —
`Ȧ` doesn't depend on where `q` came from) and arbitrary real
point/normal/weight velocity fields (not renormalized after perturbing
normals — the kernel math never assumes unit normals, confirmed in Phase 1,
so this is a valid one-parameter family for the check even though it isn't a
physically realizable SDF motion).

Method: assemble the real system at `theta`, `theta + eps*velocity`,
`theta - eps*velocity` via the actual, unmodified
`build_ibim_tmz_frequency_system`; central-difference the top-row output
`A[:N,:N] @ u_D + A[:N,N:] @ u_N`; compare against
`top_row_system_action_directional_derivative`'s closed-form output at the
same `theta`. Swept `eps` from `1e-2` to `3e-5`.

Result:

| eps | max abs err | rel err (norm) | err / eps² |
|---:|---:|---:|---:|
| 1.0e-2 | 1.622e-4 | 8.107e-5 | 1.622 |
| 3.0e-3 | 1.460e-5 | 7.296e-6 | 1.622 |
| 1.0e-3 | 1.622e-6 | 8.107e-7 | 1.622 |
| 3.0e-4 | 1.460e-7 | 7.296e-8 | 1.622 |
| 1.0e-4 | 1.620e-8 | 8.099e-9 | 1.620 |
| 3.0e-5 | 1.489e-9 | 7.426e-10 | 1.654 |

`err/eps²` holds constant at ≈1.62 across three decades of `eps` before
flattening into the roundoff floor at `eps≈3e-5` — the textbook signature of
a central difference converging onto a correctly-implemented analytic
derivative (`O(eps²)` truncation error, then floating-point noise once `eps`
gets too small to resolve further). Nothing here needed debugging — the
result matched on the first run at this scope. That is evidence for the top
row specifically (S and D blocks, Müller-combined, both offset sides, all
four term types per block), not for the bottom row, not for the full adjoint
identity, and not for the SDF geometric chain — see the "explicitly not
implemented" list above for exactly what remains before this is Phase 3/4
complete in the sense the rest of this plan means.

---

## 7a. Phase 3 continued, 2026-08-28 — `K'`/`T` completed; scalar diagnostic still off by ~2x

Continuation of the same session. Scope of what was added, all still inside
the same prototype module (`ibim_shape_derivative_prototype.py`), still not
wired into `ibim_tmz_adjoint.py`:

### `T`'s missing third derivative — derived and verified

`docs/ibim_shape_derivative.md` §11b (new) derives
`D_x^p D_y^q G = (-1)^q D_u^{p+q} g(u)` at `u = x-y` (any function of a
single displacement argument), which reduces both of `T`'s previously-missing
terms to one new closed form, `D_u^3 g`, contracted with three vectors:

```
D_u^3 g(a,b,c) = A(r)(a.e)(b.e)(c.e) + B(r)[(a.b)(c.e) + (a.c)(b.e) + (b.c)(a.e)]
A(r) = f''' - 3f''/r + 3f'/r^2,  B(r) = f''/r - f'/r^2
```

Two new functions in `ibim_tmz_forward.py`:
`implicit_greens_function_third_derivative_two_target_one_source_potential_from_band`
(`D_x^2 D_y^1 G`, T's own-motion term) and
`..._one_target_two_source_...` (`D_x^1 D_y^2 G`, T's source-motion term).
Verified two ways before use: (1) the closed form itself against a
triple-nested central difference of `G` via a standalone scipy script —
`O(eps²)` convergence confirmed (`err/eps²` ≈ 470-485 from `eps=1e-2` to
`1e-4`, roundoff dominating below that); (2) both new package functions
against central differences of the existing, already-verified mixed-Hessian
function — `pytest/test_ibim_shape_derivative_kernels.py`, now 8/8 passing.

### `K'` and `T` full block contraction, with the extrapolation stencil

`_adjoint_double_layer_block_action_derivative_one_wavenumber` and
`_hypersingular_block_action_derivative_one_wavenumber` added to the
prototype module, applying the `(3,-3,1)` stencil at `m=1,2,3` per side to
the derivative terms (per §3.3's "extrapolation commutes" result — no new
derivation needed for that part, already settled in Phase 0).
`full_system_action_directional_derivative` now returns **both** rows of
`Ȧq`.

**Verification (full `Ȧq`, both rows, real circle N=24, 1.5 GHz, real
Muller+`analytic_extrapolated` system, `use_strict_quadrature=True`):**

| eps | top max err | top rel err | bot max err | bot rel err | top e/eps² | bot e/eps² |
|---:|---:|---:|---:|---:|---:|---:|
| 1.0e-2 | 1.759e-4 | 8.191e-5 | 1.895e-2 | 1.930e-4 | 1.76 | 189.5 |
| 3.0e-3 | 1.583e-5 | 7.372e-6 | 1.707e-3 | 1.737e-5 | 1.76 | 189.6 |
| 1.0e-3 | 1.759e-6 | 8.191e-7 | 1.896e-4 | 1.930e-6 | 1.76 | 189.6 |
| 3.0e-4 | 1.583e-7 | 7.372e-8 | 1.707e-5 | 1.737e-7 | 1.76 | 189.6 |
| 1.0e-4 | 1.757e-8 | 8.187e-9 | 1.895e-6 | 1.932e-8 | 1.76 | 189.5 |
| 3.0e-5 | 1.623e-9 | 7.402e-10 | 1.738e-7 | 1.771e-9 | 1.80 | 193.1 |

Both rows converge cleanly at `O(eps²)`, relative error ~1e-8 to 1e-9 at the
best-resolved step. **Passed on the first run — including `K'` and `T`, the
3-point extrapolation stencil, and the new third-derivative kernels,
together, all at once.** This is genuinely strong evidence the full `Ȧq`
contraction (all four blocks, Müller-combined) is correct.

### `ḃ`, `Ċ`, the adjoint solve, and the scalar loss gradient — built, and wrong

Added: `incident_trace_directional_derivative` (`ḃ`, standalone — the
incident trace has no BEM quadrature and no offset averaging, re-derived
directly against `ibim_incident_trace_on_boundary`'s actual formula, not
assumed unchanged from the pre-split version), `receiver_row_matrices` /
`receiver_row_action_directional_derivative` (`C`, `Ċq` — receivers are
fixed external points, so only source-side/column terms apply, no offset
averaging), and `full_loss_gradient_directional_derivative`, which solves
the real forward system for `q`, solves `A^H mu = C^H psi` via Phase 2's
`adjoint_system_matrix` (no re-derivation — literally the conjugate
transpose of the real assembled matrix), and combines everything into
`dJ/dalpha = Re[mu^H(ḃ - Ȧq) + psi^H(Ċq)]` for `J = 0.5 Σ|total_receiver -
observed|²`.

**Verification, real circle N=24, real materials, 1.5 GHz, fixed Tx at
(0.2, 0.5) / Rx at (0.8, 0.5), arbitrary fixed `observed` target:**

Sanity check first — `J(theta0)` computed two independent ways (inside the
adjoint function vs. a fully standalone reference loss function) agreed
exactly: `0.00026119801227667...` both paths. So the forward solve and loss
reconstruction are consistent between the two code paths; the disagreement
below is isolated to the gradient.

| eps | FD dJ/dalpha | abs err vs. adjoint | err/eps² |
|---:|---:|---:|---:|
| 1.0e-2 | -9.04812e-5 | 4.519e-5 | 0.452 |
| 3.0e-3 | -9.05680e-5 | 4.528e-5 | 5.03 |
| 1.0e-3 | -9.05757e-5 | 4.529e-5 | 45.3 |
| 3.0e-4 | -9.05765e-5 | 4.529e-5 | 503 |
| 1.0e-4 | -9.05766e-5 | 4.529e-5 | 4529 |
| 3.0e-5 | -9.05766e-5 | 4.529e-5 | 50320 |

Adjoint value: `-4.52883e-5`.

**This is not an unconverged check.** The FD value stabilizes to 5
significant figures from `eps=1e-3` down to `3e-5` (`err/eps²` blowing up
here just means the *absolute* error has stopped shrinking, i.e. the FD has
already converged and the residual gap is a real, constant discrepancy, not
truncation noise going the wrong way). The gap itself is exactly the
signature to pay attention to: `-4.52883e-5 / -9.05766e-5 = 0.500000...` —
the adjoint result is almost exactly **half** the correct value, to 6
significant figures, at every `eps` tested. That precision rules out
coincidence; it's a specific, reproducible factor, not a qualitative "the
adjoint is wrong somewhere."

**Not debugged, per instruction — documented instead.** A clean factor of
~2 in a Wirtinger-calculus gradient is a known, common failure signature:
for a real-valued loss of a complex variable, whether the final combination
formula (`Re[...]`) or the definition of `psi = ∂J/∂conj(y)` itself already
carries a factor of 2 is a convention choice, and different derivations
(including the one `docs/ibim_shape_derivative.md` §9 carried over from the
pre-Muller version, unverified in this pass) make that choice differently.
Mixing two internally-consistent-but-different conventions for `psi` and the
final `Re[...]` step is exactly the kind of thing that produces a constant,
precise factor-of-2 gap rather than a qualitative mismatch. This is a
concrete, specific lead for whoever continues this work — not a diagnosis,
since it wasn't chased down, but a strong candidate that should be checked
*first*, before re-deriving anything else in §9.

### What this session's Phase 3/4 work actually establishes, honestly stated

- **Strong, repeated, verified evidence** that every individual
  shape-derivative *kernel* (S4-S6, S11b of the derivation doc) is correct,
  including the two hardest additions (third derivatives for T, the
  extrapolation stencil for K'/T) — eight kernel-level tests, all passing,
  all against independently-computed finite differences.
- **Strong, verified evidence** that the *block assembly* (Müller
  combination, both offset sides, all term types, for all four blocks) is
  correct — the full `Ȧq` check, both rows, clean `O(eps²)` convergence,
  first try.
- **Superseded by the production bridge below:** the scalar diagnostic in
  `ibim_shape_derivative_prototype.py` still has the factor-of-2 convention
  issue recorded above and should remain diagnostic-only. The exported
  leading-order adjoint path no longer depends on that scalar helper.
- Still unbuilt at this checkpoint: the SDF-specific geometric derivative chain
  (`ibim_geometry.py`) and Phase 6's circle-convergence run. The production
  bridge verifies frozen normals/weights point motion; it does not claim the
  full SDF parameter derivative chain is complete.

## 7b. Production bridge, 2026-08-28 — frozen-geometry point adjoint green

Verification pass after reviewing Claude's build found the exported
`ibim_tmz_adjoint.py` path still differentiated the old first-kind
exterior-plus-interior action. The canary
`test_ibim_leading_order_point_directional_gradient_matches_frozen_geometry_finite_difference`
failed with relative error `0.208502194` against the `2e-4` gate. A local
diagnostic using the same forward context showed:

| path | directional derivative |
|---|---:|
| production before fix | -0.3725456309 |
| central finite difference | -0.1640434369 |
| verified Muller `Ȧq` contraction only | -0.1640435729 |

That isolated the mismatch to `Ȧq`, not to the receiver rows, incident trace,
or adjoint solve. The fix is deliberately narrow: `ibim_tmz_adjoint.py` now
uses `full_system_action_directional_derivative_from_wavenumbers` for the
default `formulation="muller"` / `normal_derivative_scheme="analytic_extrapolated"`
case, passing the forward solve's already-resolved wavenumbers and
`offset_distance`. Normals and weights remain frozen, matching the public
`ibim_leading_order_point_directional_gradient` contract. A sparse
single-sample fast path keeps `ibim_leading_order_normal_shape_gradient`
practical; it matches the dense verified contraction to roughly `1e-11` max
absolute error on representative circle samples.

Post-fix verification:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/pytest pytest/artefacts/test_ibim_tmz_adjoint.py --solver=mod -q
# 12 passed, 11 warnings in 37.52s

/home/drdeng/miniconda3/envs/EMNerf/bin/pytest pytest/test_ibim_shape_derivative_kernels.py --solver=mod -q
# 8 passed in 0.02s
```

This completed the exported frozen-geometry point-directional adjoint check
for the default `gpr_bem_mod` forward operator at this checkpoint. The
multi-frequency/B-scan and inverse-wiring checks were added next; see §7c.

## 7c. Production bridge continued, 2026-08-28 — density and composed objectives

The next verification pass found a separate contract bug in the normal
shape-gradient output. `ibim_leading_order_normal_shape_gradient` and its
multi-frequency/B-scan aggregators were returning one-node directional
derivatives, but `ibim_shape_gradient_surrogate_loss` treats its input as a
shape-gradient density and multiplies by quadrature. That double-weighted the
boundary contribution in the SDF surrogate.

Fix: the public normal-gradient functions now divide the per-node directional
derivative by the active quadrature weight before returning it. The
finite-difference fallback in `ibim_inverse.py` was updated to the same
contract, so both analytic and fallback paths return density. A direct
analytic-circle surrogate canary now checks that the radius parameter's
autograd gradient matches the all-node normal point-directional derivative.

The adjoint context builders and `IBIMInverseConfig` now also expose
`formulation` and `normal_derivative_scheme` explicitly, defaulting to the
production pair (`"muller"`, `"analytic_extrapolated"`). This pins the
inverse/adjoint path to the validated forward operator unless a caller
deliberately overrides it.

New composed-objective checks:

- Multi-frequency frozen-geometry finite difference: passed at the original
  `2e-4` gate.
- B-scan frozen-geometry finite difference: passed at the same gate using
  `5e-9` displacement. A larger `2e-5` displacement is dominated by curvature
  of the time-domain objective; a diagnostic confirmed the B-scan dual
  matches the direct frequency-response linearization while the objective
  finite difference converges only at much smaller steps.
- Fallback-density unit check: verifies sparse B-scan finite differences are
  divided by quadrature before entering the surrogate.
- Small analytic-circle inverse smoke: target radius `0.05`, initialized at
  `0.054`; four CPU steps reduced B-scan loss from
  `1.6874685715e10` to `1.6821096125e10` and radius parameter from
  `0.0540000014` to `0.0539919995`. This is a direction/smoke check, not a
  full convergence benchmark.

Post-update verification:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/pytest pytest/artefacts/test_ibim_tmz_adjoint.py --solver=mod -q
# 15 passed, 14 warnings in 52.15s

/home/drdeng/miniconda3/envs/EMNerf/bin/pytest pytest/artefacts/test_ibim_inverse.py --solver=mod -q
# 6 passed, 10 warnings in 2.03s

/home/drdeng/miniconda3/envs/EMNerf/bin/pytest pytest/test_ibim_shape_derivative_kernels.py --solver=mod -q
# 8 passed in 0.01s

/home/drdeng/miniconda3/envs/EMNerf/bin/pytest pytest/artefacts/test_ibim_tmz_forward.py --solver=mod -q
# 9 passed, 1 skipped, 4 warnings in 16.03s

/home/drdeng/miniconda3/envs/EMNerf/bin/pytest pytest/artefacts/test_ibim_tmz_system.py --solver=mod -q
# 5 passed, 1 skipped, 5 warnings in 7.34s
```

Still not claimed: the full SDF-derived `p_dot`/`n_dot`/`w_dot` chain through
the pre-compression band/compression identity is not built. The production
inverse path uses the frozen compressed-sample density surrogate, which is the
same leading-order coupling strategy the tests above verify. A saved,
multi-step circle convergence benchmark is also still pending.

Remaining/refinement checklist. Work in the same order the file's existing
structure suggests (point-directional → boundary-normal → leading-order),
replacing any still-used formulation-specific stale branch with one built on
Phases 1-2:

1. `_ibim_system_action_point_directional_derivative` (`:1026`) and its
   single-sample sibling (`:2000`) — **done for the default
   Müller/`analytic_extrapolated` frozen-geometry path in §7b**; non-default
   diagnostic branches still use the older implementation.
2. `_single_layer_boundary_trace_single_sample_directional` /
   `_double_layer_boundary_trace_single_sample_directional` /
   `_single_layer_normal_derivative_trace_single_sample_directional` /
   `_double_layer_normal_derivative_trace_single_sample_directional`
   (`:1161-1363`) and their point-directional counterparts (`:1766-2000`) —
   replace the finite-difference-based derivative evaluation with Phase 1's
   analytic shape-derivative kernels.
3. `_ibim_incident_trace_*_directional_derivative` (`:984`, `:1470`, `:2089`)
   — check whether these need any change at all; the incident field doesn't
   depend on the formulation, only the *boundary operator* does. Likely
   untouched, but confirm rather than assume.
4. `_ibim_receiver_action_*_directional_derivative` (`:1124`, `:1525`, `:2134`)
   — the receiver representation formula; check against Phase 0's derivation
   for whether it changes under Müller (the receiver evaluation is a Green's
   representation using the *solved* densities, which does depend on which
   formulation solved for them).
5. Leave the wrapper layer alone unless a signature needs to change to thread
   through a new parameter: `complex_l2_data_misfit` (`:157`),
   `build_ibim_receiver_operator_rows` (`:169`), `prepare_ibim_adjoint_context`
   (`:207`, `formulation`/`normal_derivative_scheme` now added and threaded
   down in §7c), `prepare_ibim_multifrequency_adjoint_context` (`:298`),
   `prepare_ibim_bscan_adjoint_context` (`:370`), the misfit and gradient
   surrogate functions (`:476-737`), and the B-scan transform dual
   (`:2298-2346`).

**Do not treat step 5's "leave alone" as a free pass** — audit each one for
implicit formulation assumptions before deciding it's truly untouched.

---

## 8. Phase 4 — verification

This is not a follow-up step, it's the deliverable that makes Phase 3 trustworthy.

**Status update, 2026-08-28:** the exported production path now has
single-frequency, multi-frequency, B-scan, normal-density, and surrogate
finite-difference canaries in `pytest/artefacts/test_ibim_tmz_adjoint.py`,
all passing for `--solver=mod` (§7c). The original broader acceptance target
below remains the bar for a full validation campaign: the current tests do
not yet sweep the exact 0.5/1.5/2.5 GHz validation set or multiple arbitrary
perturbation directions.

1. **Bring `test_ibim_tmz_adjoint.py::...frozen_geometry_finite_difference`
   green**, targeting `gpr_bem_mod` specifically (add a `--solver`-parametrised
   version or a `mod`-specific twin, mirroring how `test_circle_comparison.py`
   handles ref/mod/kdiff side by side) — at the *original* tolerance
   (`2e-4`), not a loosened one. If it can't reach that, that's a finding to
   report, not a threshold to relax without justification (the FD-roundoff
   argument that justified loosening the *old* test doesn't automatically
   transfer here — check the new FD step-size sensitivity fresh).
2. **Step-size sweep on the finite-difference check**, the same discipline
   `docs/validation_change_log.md`'s stand-off sweep used elsewhere in this
   project — confirm the FD estimate itself has converged before trusting a
   mismatch as a real gradient bug rather than FD truncation/roundoff noise.
3. **Multi-frequency and B-scan-level checks**, not just single-frequency
   point-directional — `prepare_ibim_multifrequency_adjoint_context` and
   `prepare_ibim_bscan_adjoint_context` have their own composition logic
   (frequency weighting, inverse transform) that a single-frequency check
   cannot exercise.
4. **Multiple boundary points and multiple perturbation directions**, not
   just one — a bug isolated to (say) tangential vs. normal perturbation
   components is exactly the kind of thing a single test case hides.

**Acceptance:** analytic circle, fixed geometry (not yet coupled to
`SirenSDF2D`), gradient check passes at a tolerance comparable to the old
test's original `2e-4`, across at least 0.5/1.5/2.5 GHz (the same three
frequencies the forward validation already treats as the clean, gate-worthy
band) and multiple boundary sample points.

---

## 9. Phase 5 — wire into `ibim_inverse.py` and the run script

Should be close to mechanical **if** Phase 3 kept the context-builder call
signatures stable (module-level function names and return types), since
`ibim_inverse.py` consumes them through those, not through internals.

**Status update, 2026-08-28:** the inverse path now consumes shape-gradient
density consistently. The analytic B-scan normal-gradient path and the sparse
finite-difference fallback both return density, and `IBIMInverseConfig`
threads `formulation` / `normal_derivative_scheme` into the B-scan adjoint
context. `run_ibim_circle_inverse_bscan.py` still needs no solver-selection
change; use `--solver=mod`.

- Done in §7c: update whatever calls into `prepare_ibim_*_adjoint_context` to pass
  `formulation="muller"` / `normal_derivative_scheme="analytic_extrapolated"`
  explicitly rather than relying on defaults, given §7 step 5's point about
  silent default drift.
- Done in §7c: `_estimate_bscan_shape_gradient_finite_difference`
  (`ibim_inverse.py`) was corrected to return density and covered by a fake
  objective unit test; a tiny analytic-circle smoke also exercised the wired
  inverse loop.
- Still true: `run_ibim_circle_inverse_bscan.py` already has `--solver`; no change needed
  there. Just remember to pass it explicitly (`--solver=mod`) once this plan
  lands, rather than relying on `solver_select`'s default, which stays `ref`.

---

## 10. Phase 6 — circle-first end-to-end validation

Per the codex's Phase H ordering: run the inverse loop against the analytic
circle target with a known ground truth **before** touching `SirenSDF2D` at
all. Concretely:

**Status update, 2026-08-28:** a tiny analytic-circle CPU smoke passed in the
right direction (loss and radius error both decreased over four steps; see
§7c). This is not a replacement for the saved convergence run below.

1. Initialize from a deliberately wrong circle (wrong radius and/or center),
   run the loop, confirm it converges to the true circle.
2. Save results to disk — per `forward_solver_validation.md` §8.2/§3, "the
   inverse pipeline has no saved results" was true even for the *old* broken
   adjoint; don't repeat that gap here. Store loss curves, gradient norms,
   and boundary geometry per iteration.
3. Only after this passes, move to `SirenSDF2D` — and only as a distinctly
   separate, later piece of work, not part of this plan's exit criteria.

---

## 11. Test plan summary

| Test | New or existing | Gate |
|---|---|---|
| Kernel-identity check, shape-derivative kernel vs. FD of existing potential | New (Phase 1) | Exact |
| Dual system = transpose of forward system, fixed geometry | New (Phase 2) | Machine precision |
| `test_ibim_tmz_adjoint.py` frozen-geometry FD check, `mod`-targeted | Existing test, new target | `< 2e-4` (unrelaxed) |
| FD step-size convergence sweep | New (Phase 4) | Monotone convergence before trusting the point above |
| Multi-frequency / B-scan adjoint check | Added in §7c | `<2e-4` on current canaries |
| `_estimate_bscan_shape_gradient_finite_difference` density contract | Added in §7c | Exact fake-objective density check |
| Circle-target inverse convergence | Smoke only in §7c; full run pending | Converges to true radius/center within a documented tolerance |

---

## 12. Risks, and why do this now anyway given §0's caveat

Patterns this project's own history says to expect, so Phase 4 shouldn't be
skipped or rushed on the assumption "the derivation looked right":

- **A plausible-sounding mechanism turning out to be wrong** happened twice
  already on the forward side (`forward_solver_validation.md` §10; the §4b
  finite-difference retraction in the codex). No reason to expect the adjoint
  derivation is exempt — this is the core argument for Phase 4 being
  non-negotiable and for the kernel-level check in Phase 1 being written
  *before* anything is wired together.
- **Sign/transpose errors are silent** by construction — a wrong-signed
  gradient does not crash, it just steers optimization the wrong way, slowly
  enough to look like slow convergence rather than a bug. This is why Phase
  2's five-minute transpose check and Phase 4's FD check are both mandatory
  rather than "nice to have."
- **`MULLER_OFFSET_SCALE` is discretisation-dependent** (§7 caveat, and
  `docs/validation_change_log.md`'s 2026-08-25 entry). The adjoint construction
  doesn't need to re-derive this constant, but it does need to use whatever
  offset the *forward* solve inside the same context actually used — check
  that `prepare_ibim_adjoint_context` and friends thread `offset_distance`
  consistently between the forward call and any new dual-construction call,
  rather than each independently resolving `None` to a default that could
  drift out of sync.

Doing this now, despite §0's stronger checklist not being fully satisfied
(tuned offset constant, open 8 GHz question): those two open items are
forward-solver accuracy questions that don't block *deriving a correct
adjoint for whatever forward operator currently exists*. The adjoint should
differentiate the actual, current forward operator — a correct gradient for
an imperfect (but currently-frozen-in-practice) forward operator is still
useful and is a prerequisite for ever running the inverse loop at all. The
one thing genuinely worth waiting for would be if the forward *formulation*
itself were expected to change again soon (e.g. if `kdiff` is finalized and
replaces `mod`) — it is not currently on that trajectory; `kdiff` is still
failing on non-circular shapes with no near-term fix identified.

---

## 13. Effort estimate

| Phase | Relative size |
|---|---:|
| 0 — derivation | Medium; blocking, highest-leverage if done carefully |
| 1 — forward-file kernels | Small-medium, well-isolated, cheaply testable |
| 2 — dual system | Small, cheaply self-checking |
| 3 — adjoint rewrite | **Large** — most of the file's 2346 lines are formulation-specific |
| 4 — verification | Medium, but not optional, and likely to surface Phase 0/3 mistakes (expect at least one iteration back) |
| 5 — wiring | Small, mechanical if Phase 3 kept signatures stable |
| 6 — circle validation | Small execution, but is the actual proof this all worked |

Matches the earlier estimate given in conversation: multi-week for one
person, dominated by Phase 3, with Phase 4 realistically forcing at least one
loop back into Phase 0 or 3 given this project's track record of the first
derivation attempt missing something (§12).

---

## 14. Open questions to resolve before starting Phase 1

1. Does the Phase 0 derivation confirm the old doc's `J_a` geometric-derivative
   chain (§3 of `docs/ibim_shape_derivative.md`) is otherwise reusable, or
   does it need re-deriving from scratch given the Jacobian-status miss
   already found?
2. Should `offset_distance` for the dual system in Phase 2 always be forced
   equal to the forward solve's resolved offset (passed explicitly), or does
   the dual construction have its own principled offset in the literature
   this project already surveyed (`ibim_error_mitigation_literature_codex.md`)?
   Leaning toward "always equal, passed explicitly" per §12, but worth a
   one-line decision recorded before Phase 2 starts, not discovered midway.
3. ~~Does `analytic_extrapolated`'s Lagrange extrapolation to `t=0` commute
   with taking a shape derivative?~~ **Resolved in Phase 0.** Yes, exactly —
   see `ibim_shape_derivative.md` §3.3. The extrapolation is a fixed linear
   functional (weights `(3,-3,1)` don't depend on `alpha`), so
   `∂/∂p [extrapolate(f(d), f(2d), f(3d))] = extrapolate(∂f/∂p(d), ...)`
   without qualification.
