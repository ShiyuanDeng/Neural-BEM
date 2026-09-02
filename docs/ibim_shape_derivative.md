# IBIM shape-derivative derivation (Müller formulation, `gpr_bem_mod`)

> **Status: active `gpr_bem_mod` mathematical reference.** This derivation
> applies to the compressed-cloud Müller/`analytic_extrapolated` path. It does
> not define the future ordered Kress/Nyström adjoint; that must be derived from
> the accepted new discretization. See
> [`current_architecture.md`](current_architecture.md).

*Phase 0 of `docs/legacy/adjoint_inverse_rebuild_plan.md`, written 2026-08-27
before the corresponding adjoint implementation and retained as its reviewable
derivation.*

---

## 0. Relation to the previous version of this file

This replaces the prior version of `docs/ibim_shape_derivative.md` outright
rather than editing it. That version was written against a pre-split, single
flat `gpr_bem/` package on a different machine (its code links point at
`/home/haibing/PycharmProjects/Neural_SDF_BEM_AD/gpr_bem/...`), predates the
Müller formulation entirely, and its §9.1 explicitly claims the Jacobian
term `J_a` is *not yet implemented* in the quadrature weight. That claim is
now false — `ibim_geometry.py:207-208` already computes
`jacobian = 1.0 - signed_offset * curvature` and folds it into
`strict_quadrature_weights` (`:215`). Per `docs/legacy/adjoint_inverse_rebuild_plan.md`
§4, nothing in the old file should be trusted without re-checking against
current code; this document does that re-check explicitly section by section.

**What carries over largely intact:** §2 below (the geometric derivative
chain — how `m_a`, `n_a`, `p_a`, `kappa_a`, `J_a`, `w_a` move under a shape
parameter) is structurally the same derivation the old file had in its §3. It
didn't depend on which BIE formulation consumes the geometry, so the Müller
change doesn't touch it. It's re-derived here anyway, against verified
current variable names, rather than copied.

**What is new, and is the actual point of this document:** the old file
modeled every boundary operator abstractly as `V_ij = f(r_ij) w_j`, i.e. a
direct kernel evaluation between two boundary points. **That is not what the
code does.** Every operator block (`S`, `D`, `K'`, `T`) is built by evaluating
a potential or its normal derivative at a point *offset from the boundary*,
`p_i ± d n_i`, for **every row `i`, against every column `j`** — not just the
diagonal. Differentiating this correctly requires differentiating the probe
construction `p_i ± d n_i` itself (through both `p_i` and `n_i`), which the
old file's notation has no mechanism for at all. This is §4-§6 below, and is
the primary new content this document adds.

---

## 1. Scope

Covers `gpr_bem_mod` only, at its current state: Müller formulation
(`ibim_tmz_system.py`, `formulation="muller"`, default), `analytic_extrapolated`
normal-derivative kernels (`ibim_tmz_forward.py`,
`DEFAULT_NORMAL_DERIVATIVE_SCHEME`), direct solve
(`solve_strategy="direct"`, default). Does not cover `gpr_bem_kdiff` (no
adjoint planned for it yet, per the rebuild plan's non-goals) or the
compression step's own differentiability (§9, deferred, matching the old
file's §10 and this decision being carried forward unchanged).

---

## 2. Discrete geometry and its parameter derivative

### 2.1 Current quantities (`ibim_geometry.py`, `build_implicit_boundary_band`)

For a fixed background grid point `y_a` (θ-independent — the grid itself
never moves) and current SDF parameters `theta`:

```text
phi_a          = phi_theta(y_a)                          sdf_values
g_a            = grad phi_theta(y_a)                      sdf_gradients
m_a            = ||g_a||                                  grad_norm
n_a            = g_a / m_a                                normals
tau_a          = (phi_a - level) / m_a                     signed_offset
p_a            = y_a - tau_a * n_a                          projected_points
kappa_a        = div(n_a) at y_a (autograd divergence)     curvature      [:202-207]
J_a            = 1 - tau_a * kappa_a                        jacobian       [:208]
delta_a        = regularized_cosine_delta(phi_a)            delta_values
w_a            = delta_a * m_a * cell_area                  quadrature_weights      [:214]
w_a^strict     = w_a * J_a                                   strict_quadrature_weights [:215]
```

`use_strict_quadrature` (threaded through every operator-building function in
`ibim_tmz_forward.py`) selects `w_a` vs. `w_a^strict` as the source weight.
**This must match whatever the forward solve inside the adjoint context
actually used** — `_source_geometry_from_representation`
(`ibim_tmz_forward.py:1001-1018`) picks the attribute by name from that flag,
and `build_single_circle_bscan_benchmark_config` sets it `True`. Any Phase 1/3
code that hard-codes the non-strict weight would introduce a milder version of
exactly the bug this whole plan exists to fix — a value that looks plausible
but differentiates the wrong quantity.

### 2.2 Compression is out of scope for this derivative chain

`compress_implicit_boundary_band` (round → `torch.unique` → `index_add_`
weighted merge, `ibim_geometry.py:251-346`) sits between the band above and
the `ImplicitBoundarySamples2D` the solver actually assembles operators on.
This chain is not smooth in any useful sense (integer binning, a
data-dependent early-exit loop that can change the *number* of retained
samples). Per the old file's §10, and unchanged here: **this derivative
chain is derived on the pre-compression `ImplicitBoundaryBand2D` quantities
above.** Treat compression as a frozen resampling step for now. This is
listed as an explicit open item in §9 rather than silently assumed away.

### 2.3 Parameter derivative chain

Let `alpha` stand for any scalar shape parameter (eventually a component of
`theta`). Write `ẋ := ∂x/∂alpha`. Given:

```text
phi_dot_a = ∂_alpha phi_theta(y_a)
g_dot_a   = ∂_alpha grad phi_theta(y_a)
H_a       = Hess phi_theta(y_a)
H_dot_a   = ∂_alpha Hess phi_theta(y_a)
```

**Gradient norm:**
```text
m_dot_a = n_a^T g_dot_a
```

**Normal.** With tangential projector `P_a = I - n_a n_a^T`:
```text
n_dot_a = P_a g_dot_a / m_a
```
(only the tangential part of `g_dot_a` moves the normal — expected.)

**Offset and projected point:**
```text
tau_dot_a = phi_dot_a / m_a - tau_a * m_dot_a / m_a
p_dot_a   = -tau_dot_a * n_a - tau_a * n_dot_a
```
On the boundary itself (`tau_a = 0`, the common case once the SDF has
converged near the target), this collapses to the familiar leading-order
normal-velocity relation already implemented as
`leading_order_level_set_boundary_update` (`ibim_geometry.py:427-447`):
```text
p_dot_a ≈ -(phi_dot_a / m_a) * n_a          [tau_a = 0 only]
```
Away from the boundary (`tau_a != 0`, which happens for every sample in the
*band* before compression collapses it) both terms matter, and specifically
`n_dot_a` needs the full tangential-projection formula above, not the
leading-order shortcut.

**Curvature.** With `P_dot_a = -(n_dot_a n_a^T + n_a n_dot_a^T)`:
```text
kappa_dot_a = [tr(P_dot_a H_a) + tr(P_a H_dot_a)] / m_a - kappa_a * m_dot_a / m_a
```
This needs `H_dot_a`, i.e. third-derivative information through the SDF
network. Same conclusion as the old file: either allow the higher-order
autograd this requires, or freeze `J_a`/`kappa_a` at their current values for
a first, leading-order-Jacobian implementation and revisit if the strict
Jacobian's contribution turns out to matter (§9 flags this as unresolved,
not assumed negligible).

**Jacobian:**
```text
J_dot_a = -tau_dot_a * kappa_a - tau_a * kappa_dot_a
```

**Quadrature weight**, both variants (the strict one is the one that matters
given §2.1):
```text
w_dot_a        = cell_area * [delta'_a * phi_dot_a * m_a + delta_a * m_dot_a]
w_dot_a^strict = w_dot_a * J_a + w_a * J_dot_a
```

---

## 3. What the forward operator actually assembles

### 3.1 The probe construction

Every operator matrix comes from `implicit_*_trace_from_band` /
`implicit_*_normal_derivative_trace_from_band`
(`ibim_tmz_forward.py:195-294`, `:474-669`). All four share one pattern:
take the boundary's own points/normals as **both** the source set (via
`_source_geometry_from_representation`, weight variant per §2.1) **and** the
basis for the row's evaluation point — `_target_geometry_from_representation`
returns the *same* points/normals array (`:1021-1027`; `ImplicitBoundarySamples2D.points`
is literally the same tensor whether read as source or as target). Then:

```text
x_i^+ = p_i + d * n_i
x_i^- = p_i - d * n_i
```

and the assembled matrix entry for row `i`, column `j` is the **average**
of the kernel evaluated with receiver `x_i^±` against source `p_j`:

```text
Trace_ij = 0.5 * [ Potential(x_i^+, p_j) + Potential(x_i^-, p_j) ]
```

for `S`/`D`, or the analogous normal-derivative potential (with `x_i`'s own
normal `n_i` as the *evaluation-side* normal, see §3.3) for `K'`/`T`. The
critical fact, absent from the old derivation entirely: **this is evaluated
for every `(i, j)` pair, not only the diagonal.** There is no separate
"near-diagonal" or "singular" code path in `gpr_bem_mod` — the global
stand-off `d` is what keeps every entry finite, exactly as
`legacy/forward_solver_validation.md` §6.1 describes. `d` itself is
`_default_trace_offset_distance(band)` (`:991-998`) — for a compressed
`ImplicitBoundarySamples2D`, `2.0 * band.merge_distance` before the
`MULLER_OFFSET_SCALE` rescale applied in `ibim_tmz_system.py:131-132`. `d` is
a single scalar shared by every row and column, not a per-point quantity.

**Consequence for the shape derivative:** row `i`'s evaluation point depends
on `p_i` *and* `n_i` (both already known to move, §2.3), and — in the `K'`/`T`
case — `n_i` also appears a second time as the direction of differentiation
itself. `d` is treated as a fixed scalar for this derivative (see §9 — it is
already the subject of an open, unresolved tuning question per
`docs/validation_change_log.md`, and differentiating through the
`compress_implicit_boundary_band` step that determines it would reopen the
non-smoothness problem §2.2 already sets aside).

### 3.2 Radial kernel functions (verified against `ibim_tmz_forward.py`)

2D Helmholtz free-space Green's function and its derivatives, as actually
coded (`:128`, `:172-177`, `:404-409`, `:460-466`):

```text
G(r)      = (i/4) H_0^(1)(k r)                         single-layer kernel
dG/dn_y   = (i k/4) H_1^(1)(k r) * ((x - y) . n_y) / r  double-layer, source-side normal
dG/dn_x   = -(i k/4) H_1^(1)(k r) * ((x - y) . n_x) / r normal-derivative, receiver-side
d²G/dn_x dn_y = (i/4)[ k H_1^(1)(kr) (n_x . n_y)/r
                        - k^2 H_2^(1)(kr) ((x-y).n_x)((x-y).n_y)/r^2 ]
```
with `H_2` from the recurrence `H_2(z) = (2/z) H_1(z) - H_0(z)`
(`:462`, avoids a third Hankel order in the backend). Sign conventions above
match the code exactly, including that `d²G/dn_x dn_y` is built directly (not
as a further derivative of `dG/dn_y`), which is what §3.3's chain rule must
differentiate.

*Self-correction, same day:* the first version of this section had the
`dG/dn_y` line as `(y - x) . n_y` instead of `(x - y) . n_y` — the opposite
sign of what's actually in the code. Caught before any Phase 1 code was
written by transcribing the formula into a standalone scipy script and
checking it against a central difference of `G` itself, rather than trusting
the hand copy — see `pytest/gpr_bem_mod/test_ibim_shape_derivative_kernels.py` for the
in-repo version of that check. Left here as a concrete instance of exactly
the failure mode §12 of the rebuild plan warns about — a small, easy-to-miss
sign error in a derivation, not caught by re-reading it, only by computing
against it.

### 3.3 The `analytic_extrapolated` scheme

For `K'`/`T`, the normal-derivative *trace* is not the raw kernel above
evaluated once — it is a 3-point Lagrange extrapolation to `t=0` from samples
at `t = d, 2d, 3d` on each side, weights `(3, -3, 1)`
(`_normal_derivative_stencil`, `:360-368`):

```text
K'_ij = 0.5 * [ Sum_m coeff_m * dG/dn_x(x_i^+ = p_i + m*d*n_i, p_j) side=+
              + Sum_m coeff_m * dG/dn_x(x_i^- = p_i - m*d*n_i, p_j) side=- ]
```
same pattern for `T`, using `d²G/dn_x dn_y`. `m ∈ {1,2,3}`, `coeff = (3,-3,1)`.
Because it's a *linear* combination of evaluations at `m*d` (not a
finite difference of potentials), differentiating it is just the same linear
combination applied to the derivative of each term — the extrapolation
commutes with `∂/∂alpha` trivially, since it's linear in the (differentiated)
kernel evaluations and the coefficients `(3,-3,1)` don't depend on `alpha`.
**This resolves open question 3 of `docs/legacy/adjoint_inverse_rebuild_plan.md`
§14**: yes, `∂/∂p [extrapolate(f(d), f(2d), f(3d))] = extrapolate(∂f/∂p(d), ...)`
exactly, because extrapolation here is a fixed linear functional of the
sample values, not a nonlinear function of them. (Had the scheme been
`finite_difference` instead, this would *not* hold as cleanly, since
`_one_sided_normal_derivative`'s stencil divides by `step` in a way that's
still linear in the samples too, actually — so the same conclusion holds
there as well; the genuinely nonlinear case would be something like a
Richardson extrapolation with data-dependent weights, which this code does
not use for this scheme. Worth stating since intuition might expect
extrapolation to be trickier than it is here.)

---

## 4. General template: derivative of one probe-averaged operator entry

Define, for the `+` side (the `-` side is identical with `d → -d`):
```text
x_i(alpha) = p_i(alpha) + d * n_i(alpha)          [d fixed, §3.1]
x_dot_i    = p_dot_i + d * n_dot_i
```
For a generic kernel `Phi(x, y, n_x?, n_y?)` (any of `G`, `dG/dn_y`, `dG/dn_x`,
`d²G/dn_x dn_y`, each possibly using `n_x = n_i` and/or `n_y = n_j`):

```text
d/dalpha [ Phi(x_i, p_j; n_i, n_j) ]
  = ∇_x Phi . x_dot_i
  + ∇_y Phi . p_dot_j
  + ∂Phi/∂n_x . n_dot_i     (only if the kernel uses n_x)
  + ∂Phi/∂n_y . n_dot_j     (only if the kernel uses n_y)
```
and the full entry derivative (`S` as the concrete example, `+` side; average
both sides and multiply by `w_j`/`ẇ_j` as in §5):
```text
d/dalpha [ 0.5*(G(x_i^+,p_j) + G(x_i^-,p_j)) * w_j ]
  = 0.5*[ ∇_x G(x_i^+,p_j).(p_dot_i + d n_dot_i) + ∇_y G(x_i^+,p_j).p_dot_j
        + ∇_x G(x_i^-,p_j).(p_dot_i - d n_dot_i) + ∇_y G(x_i^-,p_j).p_dot_j ] * w_j
  + 0.5*(G(x_i^+,p_j) + G(x_i^-,p_j)) * w_dot_j
```
Note `p_dot_i` couples with the *same* sign on both sides while `n_dot_i`
flips sign with the offset direction — this is the concrete mechanism by
which `x_i^+` and `x_i^-` do **not** produce identical derivative
contributions even though they average to a symmetric-looking trace, and is
exactly the kind of detail a hand-differentiation is likely to get backwards
under time pressure — worth a dedicated unit test in isolation (§8).

`∇_x G`, `∇_y G` are the ordinary (position, not normal) gradients of the
kernel — for `G(r) = (i/4)H_0^(1)(kr)`, `∇_x G = -(ik/4) H_1^(1)(kr) * (x-y)/r`
(the same radial factor already used for `dG/dn_x` in §3.2, just against the
displacement vector directly rather than dotted with a normal — reuse it,
don't rederive it).

---

## 5. Per-block derivative, applying §4

Below, `+`/`-` sides are implicit (apply §4's pattern to each, average, as
the code does); only the per-block kernel and normal-dependence differ.

**`S` (single-layer):** kernel `G(x_i^±, p_j)`, no normal dependence in the
kernel itself. Only the `x_dot_i`/`p_dot_j`/`w_dot_j` terms of §4 apply.

**`D` (double-layer):** kernel `dG/dn_y(x_i^±, p_j; n_j)`. Adds the
`∂Phi/∂n_y . n_dot_j` term — source-normal motion enters here, matching the
old file's observation that `K` (its name for this block) has "one more
leading term than `V`," now precisely located.

**`K'` (adjoint double-layer, `analytic_extrapolated`):** kernel
`dG/dn_x(x_i^±(m), p_j; n_i)` at each stencil multiplier `m`, extrapolated
per §3.3. Adds the `∂Phi/∂n_x . n_dot_i` term (target-normal motion) *and*
`n_dot_i` already entered `x_dot_i` once via the probe offset — **two
separate places `n_dot_i` contributes**, and they must not be conflated into
one term when coding this. The extrapolation linearity (§3.3) means: compute
this whole per-`m` derivative for each of `m=1,2,3` and combine with the same
`(3,-3,1)` weights, no special handling needed for the extrapolation step
itself.

**`T` (hypersingular, via `d²G/dn_x dn_y`, `analytic_extrapolated`, then
negated — `build_implicit_hypersingular_boundary_matrix` returns
`-trace.average_normal_derivative`, `:838`):** kernel depends on both `n_i`
and `n_j`. All four §4 terms apply, plus both normal-motion terms, plus the
extrapolation combination as in `K'`. This is, as both the old file and the
literature codex (`docs/legacy/ibim_error_mitigation_literature_codex.md` §4.3)
already flagged, the heaviest block — not because of extra singularity
structure here (the `analytic_extrapolated` scheme already handles that
part), but because it has the most terms in its own product rule. **Do not
build an explicit `Ṫ` matrix** — accumulate the contraction `mu^H (Ṫ q)`
directly, following the old file's §5.5 implementation recommendation, which
still applies and is if anything more important now that `T`'s per-entry
derivative has more terms than before.

---

## 6. The Müller combination and its derivative

### 6.1 Current assembly (`ibim_tmz_system.py:172-198`, transcribed exactly)

```text
single_layer         = S_ext - S_int
double_layer          = D_ext - D_int
adjoint_double_layer  = K'_ext - K'_int
hypersingular         = T_ext - T_int              (already carries the code's internal
                                                       W = -T sign, see §5)
upper_left  = I - double_layer
lower_right = I + adjoint_double_layer
A = [ upper_left        single_layer  ]
    [ hypersingular      lower_right   ]
```
(block-concatenated per `xp.concatenate` calls at `:192-198`; `I` is the
`num_samples x num_samples` identity, independent of `theta` — `İ = 0`.)

### 6.2 Derivative

Because every block above is a *difference* of an exterior-wavenumber and an
interior-wavenumber version of the **same** geometric operator (both built
from the same `band`/`samples`, differing only in which `k` was passed to
`build_implicit_boundary_operator_family`), and §5's per-entry derivative
formulas do not depend on which wavenumber is plugged into the kernel's
radial factor:

```text
Ṡ = Ṡ_ext - Ṡ_int
Ḋ = Ḋ_ext - Ḋ_int
K̇' = K̇'_ext - K̇'_int
Ṫ = Ṫ_ext - Ṫ_int
İ = 0
Ȧ = [ -Ḋ    Ṡ  ]
    [ Ṫ    K̇'  ]
```
i.e. **compute §5's derivative once per block per wavenumber** (exactly the
same way the forward pass computes `exterior_family` and `interior_family`
separately before subtracting, `ibim_tmz_system.py:136-153`), then subtract,
exactly mirroring the forward construction. This is a direct, low-risk
consequence of linearity — worth stating plainly because it means Phase 3
does **not** need a separate "Müller-aware" derivative formula distinct from
§5; it needs §5 run twice (once per wavenumber) and subtracted, the same
shape the forward code already has.

### 6.3 The invariant check (answering the rebuild plan's Phase 0 item 3)

The Müller construction's defining property is that the identity term
survives on the diagonal while the singular parts of `D`/`K'` cancel between
`ext`/`int` (`ibim_tmz_system.py:164-171` comment). The corresponding
invariant for the *derivative* is: **`İ = 0` exactly**, since `I` is a fixed
matrix with no `theta`-dependence — trivial, but it's the thing to check
first, because if a coded `Ȧ` produces a nonzero contribution from the
identity blocks, that's an unambiguous sign the upper-left/lower-right
`I ∓ (...)` structure was differentiated incorrectly (e.g. differentiating
`I` itself instead of only the block subtracted from/added to it). Recommend
this as the first assertion in Phase 3's unit tests — cheaper than the
kernel-identity check in §8 and catches a different class of mistake (block
bookkeeping, not kernel math).

---

## 7. Dual system for Phase 2

The rebuild plan's Phase 2 needs the transpose of `A` above for the adjoint
solve `A^H mu = C^H psi` (§8 below). Since `A` is the literal block matrix in
§6.1 (`ibim_tmz_system.py:192-198`), its transpose is the ordinary block
transpose:

```text
A^T = [ upper_left^T    hypersingular^T ]
      [ single_layer^T    lower_right^T  ]
```
i.e. swap the off-diagonal blocks *and* transpose each block individually —
`single_layer` moves from top-right to bottom-left (transposed), and
`hypersingular` moves from bottom-left to top-right (transposed);
`upper_left`/`lower_right` stay on the diagonal, each individually
transposed. `A^H` (needed for the actual adjoint equation) is the conjugate
of the above. **The sanity check the rebuild plan's Phase 2 already specifies
— assemble `A` forward, transpose it numerically, compare — should be run
before trusting this block-swap description**, since a swapped-versus-not
off-diagonal mistake here is exactly the "silent sign/transpose error" §12 of
the rebuild plan warns about.

---

## 8. Incident trace and receiver rows

These do not depend on the exterior/interior BIE combination (they're the
right-hand side and the read-out, not the system operator), so this section
is close to a direct carry-over from the old file's §6, re-verified in name
only (function locations differ post-split, math unchanged):

**Incident boundary trace**, `ibim_incident_trace_on_boundary`
(`ibim_tmz_system.py:217`), for source `s` at fixed physical position (source
positions don't move with the shape — only the boundary they're read out at
does):
```text
b_D(i,s) = q_s * G(p_i, s)
b_N(i,s) = q_s * dG/dn_i(p_i, s)
ḃ_D(i,s) = q_s * ∇_x G(p_i,s) . p_dot_i
ḃ_N(i,s) = q_s * [ ∇_x(dG/dn_i)(p_i,s) . p_dot_i + ∇_x G(p_i,s) . n_dot_i ]
```

**Receiver rows**, `build_ibim_receiver_operator_rows`
(`ibim_tmz_adjoint.py:169`) — same functional shape as `S`/`D` above but
evaluated *without* the ± offset averaging (receivers are physically fixed
antenna positions, not boundary probe points), so only the source-side terms
of §4 apply:
```text
Ṡ_r(j) = ∇_y G(r, p_j).p_dot_j * w_j + G(r, p_j) * ẇ_j
Ḋ_r(j) = [ ∂Phi/∂n_y(r,p_j).n_dot_j (position term already in ∇_y) ] * w_j
         + D_r(j) * ẇ_j
```
Direct-incident receiver term `y_inc` doesn't depend on boundary geometry at
all (fixed source/receiver, free-space Green's function): `ẏ_inc = 0`.

---

## 9. Discrete adjoint master formula

Write the forward as
```text
A(theta) q(theta) = b(theta)
y(theta) = y_inc + C(theta) q(theta)
```
For a scalar objective `J(y)` and `psi := ∂J/∂conj(y)`, the adjoint variable
solves
```text
A(theta)^H mu = C(theta)^H psi
```
and, using `ẏ_inc = 0` (§8):
```text
dJ/dalpha = Re[ mu^H (ḃ_alpha - Ȧ_alpha q) + psi^H (Ċ_alpha q) ]
```
Unchanged in structure from the old file's §7 — the master formula doesn't
care which BIE formulation `A` is; what changed is every piece feeding into
it (§5-§8 above). **Update, 2026-08-28:** the scalar diagnostic implementation
in `ibim_shape_derivative_prototype.py` reproduced a real scalar loss's
finite-difference gradient to within a *constant factor of almost exactly 2*
(adjoint value = 0.500000... × the converged FD value, stable to 6
significant figures). That diagnostic helper still carries a likely
`psi`/`Re[...]` convention mismatch and should not be used as production
evidence. A later production verification pass isolated the exported
`ibim_tmz_adjoint.py` failure to a different issue: stale first-kind
exterior-plus-interior differentiation of `Ȧq`. Routing the default
Müller/`analytic_extrapolated` path through the verified `Ȧq` contraction
made the frozen-geometry point-directional finite-difference canary pass.
A follow-up production pass fixed the normal shape-gradient contract: public
normal-gradient functions now return density (`node directional derivative /
quadrature weight`), because `ibim_shape_gradient_surrogate_loss` applies
quadrature exactly once. The current adjoint artefact suite covers
single-frequency, multi-frequency, B-scan, density, and surrogate-radius
checks (`pytest/gpr_bem_mod/test_ibim_tmz_adjoint.py`, 15/15
passing; see `docs/legacy/adjoint_inverse_rebuild_plan.md` §7b-§7c). Map onto code
as:
- `Ȧ_alpha`: §5+§6, contracted against `mu`, not built as an explicit matrix
  (§5's `T`-block recommendation, but applies to all four blocks for the same
  GPU/memory reason).
- `ḃ_alpha`: §8, first half.
- `Ċ_alpha q`: §8, second half, contracted against `psi`.

---

## 10. Open items, carried forward or newly found

1. **Offset `d` is treated as a fixed scalar for this derivative** (§3.1).
   It is, in reality, `MULLER_OFFSET_SCALE * default_trace_offset_distance(...)`,
   and `default_trace_offset_distance` depends on `band.merge_distance`,
   which depends on `compress_implicit_boundary_band`'s data-dependent
   early-exit loop (§2.2) — genuinely not smooth in `theta`. Freezing it is a
   modeling choice, not a derived approximation; if gradient checks (Phase 4
   of the rebuild plan) show a discrepancy that doesn't shrink with the FD
   step, this is one of the first places to look.
2. **Strict Jacobian derivative (`kappa_dot`, `J_dot`) needs third-order SDF
   derivatives** (§2.3). Not yet decided whether to implement in full or
   start with `J_dot` (and `kappa_dot`) frozen at a leading-order value —
   flagged in the rebuild plan's §14 open questions and repeated here rather
   than silently resolved either way.
3. **Compression's non-differentiability** (§2.2) means this whole
   derivation is for the pre-compression band. The rebuild plan's Phase 3-5
   need to decide how the compressed sample set's *identity* (which merged
   bin each surviving point represents) is held fixed during a single
   gradient evaluation — likely fine, since a single forward/adjoint pair
   uses one frozen boundary snapshot. The current production inverse path
   makes that assumption explicit: it feeds a frozen compressed-sample
   shape-gradient density into the SDF surrogate rather than differentiating
   through compression.
4. **`use_strict_quadrature` consistency** (§2.1): confirmed on the source
   side, but Phase 3 must audit that the derivative pipeline's `ẇ` computation
   (§2.3) is requested with the matching strict/non-strict flag every time,
   not just once at the top.

---

## 11a. Phase 1 status, 2026-08-27

Done: four new kernel functions in `ibim_tmz_forward.py`
(`gpr_bem_mod`-only), each verified against central differences of the
*existing, already-trusted* potential functions
(`implicit_single_layer_potential_from_band`,
`implicit_single_layer_normal_derivative_potential_from_band`), plus exact
regression checks against the existing double-layer/hypersingular kernels as
a special case — `pytest/gpr_bem_mod/test_ibim_shape_derivative_kernels.py`, 6/6
passing, `python -m pytest pytest/gpr_bem_mod/test_ibim_shape_derivative_kernels.py
--solver=mod -q`.

| Function | §4/§5 term it computes |
|---|---|
| `implicit_single_layer_source_directional_derivative_potential_from_band` | `∇_y G . v` for a *column*-indexed `v` — the `p_dot_j` term in every block's §4 template, and D's `∂/∂n_y[dG/dn_y] . n_dot_j` (first-derivative only, not a Hessian — see the function's own docstring for why) |
| `implicit_greens_function_mixed_directional_hessian_potential_from_band` | `d²G/dn_x dn_y` for two *explicit* row/column direction fields — generalizes the existing hypersingular kernel (which hard-codes the column side to `band.normals`); covers D's `∇_x[dG/dn_y].x_dot_i` term and K''s `∇_y[dG/dn_x].p_dot_j` term |
| `implicit_greens_function_pure_target_hessian_potential_from_band` | `v_a^T Hess_x(G) v_b`, both row-indexed — K'/T's own-point-motion term, e.g. `(n_i, x_dot_i)` |
| `implicit_greens_function_pure_source_hessian_potential_from_band` | `v_a^T Hess_y(G) v_b`, both column-indexed — D's own-point-motion term, e.g. `(n_j, p_dot_j)` |
| (existing) `implicit_single_layer_normal_derivative_potential_from_band` | `∇_x G . v` for a *row*-indexed `v` — already generic (never assumed `v` was a unit normal), no new function needed |

**Not done, and it's the one still-missing piece for a complete §5:** `T`'s
own `∇_x[d²G/dn_x dn_y].x_dot_i` and `∇_y[d²G/dn_x dn_y].p_dot_j` terms are
**third** derivatives of `G` (T is already a mixed second derivative; its
shape derivative is one order higher again), not covered by any of the four
functions above. The two `pure_*_hessian` functions establish the pattern
(`Hess_{same-side} = -Hess_{mixed}`) but a *third*-derivative identity has
not been derived or verified here. This is real remaining Phase 1 scope, not
an oversight to silently patch around in Phase 3 — flagged explicitly so it
isn't lost.

## 11b. `T`'s third derivative, 2026-08-28

Closes the gap §11a flagged. For any `G(x,y) = g(x-y)` (true here — the
free-space kernel depends only on displacement), the general identity is

```text
D_x^p D_y^q G = (-1)^q * D_u^{p+q} g(u),   u = x - y
```

(since `∂/∂x_k = ∂/∂u_k` and `∂/∂y_k = -∂/∂u_k`). This reproduces every
second-derivative identity already verified in §4 (`Hess_xx = Hess_yy =
D_u^2 g`, `Hess_xy = -D_u^2 g`) as the `p+q=2` case, and extends cleanly to
`p+q=3` for `T`'s two missing terms:

```text
D_x^2 D_y^1 G = -D_u^3 g(u)     [T's own-point-motion term: 2 target-side, 1 source-side]
D_x^1 D_y^2 G = +D_u^3 g(u)     [T's source-point-motion term: 1 target-side, 2 source-side]
```

Both reduce to the *same* third-order tensor `D_u^3 g`, contracted with
three vectors (derived by three successive product-rule differentiations of
`Hess_u(g) = f''(r) ee^T + (f'(r)/r)(I-ee^T)`, `e=u/r`):

```text
D_u^3 g(a,b,c) = A(r)(a.e)(b.e)(c.e) + B(r)[(a.b)(c.e) + (a.c)(b.e) + (b.c)(a.e)]
A(r) = f'''(r) - 3 f''(r)/r + 3 f'(r)/r^2
B(r) = f''(r)/r - f'(r)/r^2
```

with, for `G = (i/4)H_0^(1)(kr)`:

```text
f'(r)   = -(ik/4) H_1^(1)(kr)
f''(r)  = -(ik^2/4) H_0^(1)(kr) + (ik/4r) H_1^(1)(kr)
f'''(r) = (ik^3/4) H_1^(1)(kr) + (ik^2/4r) H_0^(1)(kr) - (ik/2r^2) H_1^(1)(kr)
```

Verified two ways before any code was written: the closed form against a
triple-nested central difference of `G` (standalone scipy script, `O(eps²)`
convergence, `err/eps²` stable at ≈470-485 from `eps=1e-2` to `1e-4`); then
the two package functions built from it
(`implicit_greens_function_third_derivative_two_target_one_source_potential_from_band`,
`..._one_target_two_source_...`) against central differences of the
already-verified mixed-Hessian function —
`pytest/gpr_bem_mod/test_ibim_shape_derivative_kernels.py`, 8/8 passing.

With this, every §5 term for all four blocks (S, D, K', T) is now covered by
a verified closed-form kernel. See
`docs/legacy/adjoint_inverse_rebuild_plan.md` §7a for the full block-assembly
verification this enabled (`Ȧq`, both rows, clean).

## 11. Coding order for Phase 1-3

Matching the rebuild plan's phase breakdown, refined with this document's
findings:

1. Implement §4's general probe-derivative template once, parameterized by
   which kernel/normal-dependence flags apply — §5's four blocks are then
   thin instantiations, not four independent derivations. This is the
   `ibim_tmz_forward.py` work of the rebuild plan's Phase 1.
2. Unit test: kernel-identity check for `∇_x G`, `∇_y G`, `∂(dG/dn_x)/∂n_x`,
   etc. against central differences of the already-trusted forward potential
   functions (`implicit_single_layer_potential_from_band` etc.), **before**
   wiring into any trace-level code — cheapest isolatable test in the whole
   plan, as the rebuild plan's Phase 1 already says.
3. §6.2 (per-wavenumber, then subtract) and §6.3 (identity invariant) —
   `ibim_tmz_system.py`/Phase 2 dual assembly, plus the block-transpose
   sanity check from §7.
4. §5's per-block assembly, contracted rather than materialized (Phase 3) —
   `S`/`D` first (no normal-motion term, simplest instance of §4), then `K'`
   (one normal-motion term plus the two-places-`n_dot_i`-enters trap flagged
   in §5), then `T` last (heaviest).
5. §8 (incident trace, receiver rows) can proceed in parallel with 3-4 — it
   doesn't depend on the Müller-specific work at all.
