# Implementation Guide: Periodic SDF Boundary → Kress-Discretized Müller Blocks

## Purpose and authority

This guide is the next implementation companion to:

- `From Neural SDFs to Kress-Ready Smooth Closed Boundaries`;
- `neural_sdf_to_kress_implementation_guide.md`;
- `sdf_boundary_parameterization_implementation.md`; and
- the isolated Kress-proxy `summary.md`.

Those files establish and validate the geometry side:

\[
F_\theta
\longrightarrow
\gamma(t)
\longrightarrow
\texttt{PeriodicCurve2D}.
\]

The isolated Kress proxy additionally verifies the universal scalar logarithmic product rule on frozen curves. It does **not** yet verify any Helmholtz operator, Müller difference, operator diagonal, block matrix, solve, or receiver field.

The purpose of this phase is therefore:

\[
\boxed{
\texttt{PeriodicCurve2D}
\longrightarrow
\{\Delta V,\Delta K,\Delta K',\Delta T\}
\longrightarrow
A_{\mathrm{M\ddot uller}}
}
\]

while reusing the repository's existing:

- Helmholtz Green-function and derivative kernels;
- operator builders;
- kernel-difference (`kdiff`) machinery;
- incident-field and receiver-evaluation routines;
- analytic circular-cylinder reference;
- trusted Nyström/reference utilities; and
- convention and material definitions.

This is intentionally **not** a file-by-file patch prescription. Codex should inspect the repository and choose the smallest clean integration seam. Existing implementations are authoritative where they already encode the project's physics and sign conventions.

---

# 1. End-to-end pipeline

The complete intended forward path is

\[
F_\theta
\longrightarrow
\gamma(t)
\longrightarrow
\texttt{PeriodicCurve2D}(N)
\longrightarrow
\text{Müller difference operators}
\longrightarrow
A\,q=b
\longrightarrow
\text{boundary traces}
\longrightarrow
\text{receiver field}.
\]

More explicitly:

```text
neural SDF / implicit field
        │
        ▼
PeriodicParameterization2D = continuous γ(t)
        │ discretize once at uniform even N
        ▼
PeriodicCurve2D
  t_j, points, d1, d2, speed,
  outward normals, curvature, ds weights
        │
        ▼
geometry adapter for existing operator builders
        │
        ├── exterior medium operators
        └── interior medium operators
                  │
                  ▼
      cancellation-safe Müller differences
          ΔV, ΔK, ΔK′, ΔT (or ΔW)
                  │
                  ▼
       Kress/Nyström discretized blocks
                  │
                  ▼
          2N × 2N Müller matrix
                  │
                  ▼
       solve for u_D and u_N traces
                  │
                  ▼
      evaluate scattered field at receivers
```

Once `PeriodicCurve2D` has been created, the operator layer should not receive the SDF, marching polygon, projection history, Fourier optimizer, or extraction notebook.

For initial operator development, begin with an **analytic circle parameterization** rather than an extracted SDF curve. This isolates operator and quadrature errors. After the operator implementation converges on exact geometry, repeat with the accepted Method-B Fourier boundary.

---

# 2. Scope of this phase

Implement now:

1. A thin adapter from `PeriodicCurve2D` to the existing operator-builder geometry input.
2. A convention audit that records exactly what the current kernels and operators mean.
3. Exterior and interior operator construction on the same periodic node set.
4. Cancellation-safe Müller difference blocks.
5. Kress treatment of the logarithmically singular self interaction.
6. Assembly of the four visible Müller matrix blocks.
7. Direct solution of the unsquared system.
8. Boundary-trace and receiver-field validation on one smooth component.
9. Block-level, system-level, and physical convergence artifacts.

Do not implement in this phase:

- a new SDF extractor or new parameterization method;
- end-to-end differentiation through extraction or the solve;
- a replacement set of Helmholtz kernels when suitable builders already exist;
- near-touching multiple-component special quadrature;
- close evaluation for receivers arbitrarily near the boundary;
- a production multi-material region graph;
- FMM acceleration;
- a new QBX implementation; or
- inverse/adjoint integration.

The first target is a **single smooth penetrable component in a homogeneous exterior**, using the current free-space two-dimensional TMz/scalar Helmholtz conventions.

---

# 3. Freeze the convention package before coding

Most Müller implementation failures are sign, normal, jump, or physical-scaling failures rather than quadrature failures. Codex should first locate the existing definitions and write a small convention record or developer note containing:

- fundamental solution convention, for example whether the code uses
  \[
  G_k(x,y)=\frac{i}{4}H_0^{(1)}(k|x-y|)
  \]
  or its negative/conjugate counterpart;
- time-harmonic convention;
- orientation of the boundary normal;
- whether the obstacle curve is stored counterclockwise;
- the exact definitions of `V/S`, `K/D`, `Kp/Dp`, and `T/W`;
- whether `T` and `W` differ by a minus sign in repository vocabulary;
- whether `K` uses the source normal and `Kp` the target normal;
- whether any operator builder already includes a trace jump term;
- the ordering and physical meaning of the unknowns;
- whether `u_N` is an ordinary normal derivative or a scaled flux;
- material coefficients multiplying the operators in TMz; and
- the signs of the incident Dirichlet and Neumann traces on the right-hand side.

Do not repair or modernize conventions while integrating Kress. Preserve one internally consistent package and prove it with tests.

## 3.1 Current-project target form

Under the project convention used in the earlier derivations—outward normal from the inclusion, unknowns

\[
q=\begin{bmatrix}u_D\\u_N\end{bmatrix},
\]

and the shorthand

\[
\Delta X=X_{\mathrm{out}}-X_{\mathrm{in}},
\]

the intended matrix has been written as

\[
\boxed{
A=
\begin{bmatrix}
I-\Delta K & \Delta V\\
\Delta T & I+\Delta K'
\end{bmatrix}
}
\]

with

\[
Aq=
\begin{bmatrix}
\gamma_D u^{\mathrm{inc}}\\
\gamma_N u^{\mathrm{inc}}
\end{bmatrix}.
\]

Equivalently,

\[
A_{11}=I+K_{\mathrm{in}}-K_{\mathrm{out}},
\qquad
A_{12}=V_{\mathrm{out}}-V_{\mathrm{in}},
\]

\[
A_{21}=T_{\mathrm{out}}-T_{\mathrm{in}},
\qquad
A_{22}=I+K'_{\mathrm{out}}-K'_{\mathrm{in}}.
\]

This is a **target to verify**, not a command to overwrite the repository's established operator signs. If the code defines `W=-T`, uses the opposite Green function, stores a scaled Neumann trace, or absorbs jumps into an operator builder, the concrete assembly must be translated accordingly. The analytic circle, zero-contrast, and jump tests decide correctness.

## 3.2 Keep jump terms separate from principal operators

The operator builder should make it possible to distinguish:

- the principal/on-surface integral operator `K` or `Kp`; and
- the \(\pm\tfrac12 I\) trace jump.

The full identity terms in the Müller matrix arise when the appropriate interior and exterior trace equations are combined. They must be added **exactly once**. Do not allow a builder to hide a jump while the final assembler adds it again.

---

# 4. Geometry input contract

The solver-facing geometry is the frozen

```python
PeriodicCurve2D
```

created by

```python
parameterization.discretize(N, require_even=True)
```

at

\[
t_j=\frac{2\pi j}{N},\qquad j=0,\ldots,N-1.
\]

It already provides the information needed by the operator layer:

- `points[j] = γ(t_j)`;
- `first_derivatives[j] = γ'(t_j)`;
- `second_derivatives[j] = γ''(t_j)`;
- `speed[j] = |γ'(t_j)|`;
- `outward_normal[j]`;
- `curvature[j]`; and
- `arc_length_weights[j] = (2π/N)|γ'(t_j)|`.

## 4.1 Adapter requirements

The adapter should:

- preserve node order and phase;
- preserve the endpoint-free periodic grid;
- preserve the single outward normal convention for both media;
- use the curve's derivatives and normals, not neural-SDF Hessians;
- expose `t`, `dt`, speed, and derivatives when a Kress split needs them;
- pass ordinary `ds` weights only if the receiving builder expects them; and
- never duplicate the endpoint.

The existing operator builders may expect only `{points, normals, weights}`. That is acceptable for far/off-diagonal evaluation. The Kress self treatment may additionally need `t`, `dt`, `speed`, `d1`, `d2`, or curvature. Codex should extend or wrap the narrowest relevant interface rather than create a second geometry hierarchy.

## 4.2 Weight ownership must be explicit

For a parameterized integral,

\[
\int_0^{2\pi} K(t,s)\,\varphi(s)\,|\gamma'(s)|\,ds,
\]

the source Jacobian must appear exactly once.

Before comparing matrices, determine whether each existing builder returns:

1. a bare physical kernel;
2. a parameterized kernel already multiplied by \(|\gamma'(s)|\); or
3. a fully quadrature-weighted matrix already multiplied by `dt * speed[j]`.

The unknown vectors should contain nodal trace values, not preweighted trace values, unless the entire existing solver consistently uses a weighted unknown convention. Do not accidentally multiply by `arc_length_weights` twice.

---

# 5. Operator layer and Müller differences

Use the repository's operator vocabulary, but keep the following mathematical roles visible in diagnostics:

| Operator | Typical role | Normal dependence | Müller-difference behaviour near the diagonal |
|---|---|---|---|
| \(V_k\) / \(S_k\) | Neumann density to Dirichlet trace | none | leading universal log cancels in \(V_o-V_i\); finite but not necessarily analytic |
| \(K_k\) / \(D_k\) | Dirichlet density to Dirichlet trace | source normal \(n_y\) | finite difference; may retain weak log-type nonanalytic terms |
| \(K'_k\) / \(D'_k\) | Neumann density to Neumann trace | target normal \(n_x\) | finite difference; may retain weak log-type nonanalytic terms |
| \(T_k\) / \(W_k\) | Dirichlet density to Neumann trace | both target and source normals | individual kernels are hypersingular; the Müller combination is only logarithmically singular |

The exact signs depend on the convention audit.

## 5.1 Form the physical Müller combination, not merely a textual subtraction

For the current nonmagnetic scalar/TMz case, the combination may be the simple difference `out - in`. If the formulation uses material prefactors, define instead the actual physical combination appearing in the transmission equations, for example

\[
\Delta_{\mathrm{phys}}T=c_oT_o-c_iT_i.
\]

The leading hypersingularity must cancel in the true Müller combination. If it does not, either:

- the wrong physical scaling was used;
- one normal/sign convention is inconsistent; or
- the implemented formulation is not the intended Müller system.

## 5.2 Construct cancellation before discretization where it matters

The most important rule is:

\[
\boxed{
\text{do not build two huge hypersingular matrices and subtract them near }i=j.
}
\]

Use the existing `kdiff` machinery as the primary source for cancellation-safe evaluation. The preferred architecture is that the operator layer can evaluate the **combined difference kernel** directly.

A practical split is:

- far from the diagonal: ordinary existing Hankel/operator formulas are acceptable, provided they agree with `kdiff`;
- near the diagonal: use the existing cancellation-safe difference or local series;
- on the diagonal: use the analytic/removable limit required by the chosen Kress split or regularized operator form.

For the hypersingular difference, a useful local diagnostic under one common convention is

\[
T_{k_o}(x,y)-T_{k_i}(x,y)
=
-\frac{k_o^2-k_i^2}{4\pi}\log|x-y|+O(1),
\]

with the sign reversed if the repository's `T/W` convention is reversed. Treat this as a unit-test target after translating conventions, not as a replacement implementation formula.

## 5.3 Permit operator-equivalent regularization

Do not force one internal route for the hypersingular block. Codex may reuse whichever established repository path is best supported:

- direct cancellation-safe `T_out - T_in` kernel;
- a Maue-type or tangential-derivative regularization;
- an existing `W/T` difference builder; or
- another algebraically equivalent regularized form.

The required outcome is the same discrete Müller block, demonstrated by block-action and full-solution convergence tests.

---

# 6. Kress discretization seam

The scalar proxy has already validated the universal periodic logarithm on the new geometry. The next step is to make each operator difference expose its **operator-specific smooth coefficient and remainder**.

For a difference kernel written in the normalization used by the existing Kress utility,

\[
K_\Delta(t,s)
=
A_\Delta(t,s)L(t-s)+B_\Delta(t,s),
\]

where, for example,

\[
L(t-s)=\frac12\log\!\left(4\sin^2\frac{t-s}{2}\right),
\]

Kress gives an action of the schematic form

\[
(K_\Delta\varphi)(t_i)
\approx
\sum_j
\left[
R_{i-j}A_{\Delta,ij}
+
\Delta t\,B_{\Delta,ij}
\right]\varphi_j.
\]

This formula assumes that the source Jacobian has already been included consistently in `A` and `B`. If the operator split returns a bare physical kernel, multiply both parts by \(|\gamma'(t_j)|\) exactly once.

## 6.1 Reuse the tested scalar rule

Do not reimplement a second set of logarithmic weights inside every operator. Reuse the same periodic weight generator and normalization that passed the manufactured scalar-circle test.

Each operator-specific builder should supply, directly or through an adapter:

- the smooth log coefficient `A_delta(t_i, t_j)`;
- the smooth remainder `B_delta(t_i, t_j)`;
- the diagonal limit of the remainder;
- any required geometry factors; and
- metadata describing whether source Jacobians are included.

## 6.2 Priority order

A sensible development order is:

1. **`ΔT` / `ΔW`:** mandatory Kress treatment because a logarithmic singularity remains after Müller cancellation.
2. **`ΔV`, `ΔK`, `ΔKp`:** make their finite diagonal limits correct, then add full log splitting where needed to recover spectral/high-order convergence.

The other three differences can be pointwise finite while still containing terms such as \(r^m\log r\). A diagonal replacement alone may converge but can lose spectral convergence. The final high-order implementation should therefore be judged by block-action convergence, not by whether every matrix entry is finite.

## 6.3 No pointwise diagonal evaluation

At `i == j`, do not call a singular Hankel derivative and then patch `nan`. The diagonal entry must come from the analytic split, a cancellation-safe limit, or an operator-equivalent regularization.

---

# 7. Suggested implementation milestones

## Milestone 0 — preserve existing evidence

Before connecting any operator code, keep these tests passing unchanged:

- SDF-to-parameterized-boundary tests;
- `PeriodicParameterization2D` / `PeriodicCurve2D` tests;
- frozen-curve Kress scalar proxy; and
- existing operator/kdiff tests.

## Milestone 1 — geometry-to-existing-builder bridge

Feed an exact `PeriodicCurve2D` circle into the existing operator builders with the smallest possible adapter.

Purpose:

- verify geometry units, ordering, normal orientation, and weight ownership;
- compare off-diagonal entries/actions against the current trusted builder;
- prove that the new geometry can replace the old irregular boundary node source without changing physics.

This bridge is a debugging control, not the final Kress Müller implementation.

## Milestone 2 — visible difference blocks

Produce a result that retains all four operator differences separately:

```text
ΔV
ΔK
ΔKp
ΔT or ΔW
```

Do not return only the final `A`. Retaining the blocks makes it possible to locate sign, diagonal, cancellation, and convergence failures.

At this stage, validate cancellation and far/near overlap independently of the linear solve.

## Milestone 3 — Kress-correct self blocks

Connect the tested periodic logarithmic weights to the operator-specific split. Start with the hypersingular difference and then complete the other nonanalytic difference kernels as required by convergence evidence.

For one component, every block is a self block. In a later multi-component implementation, Kress is used on each same-component diagonal block; well-separated cross-component blocks use ordinary smooth quadrature.

## Milestone 4 — Müller matrix and direct solve

Assemble the four blocks under the frozen convention package. Preserve the current unknown ordering and solve

\[
Aq=b
\]

directly or with the repository's ordinary linear solver.

Do **not** form a normal equation or square the operator, such as

\[
A^2q=Ab.
\]

Store the ordinary residual

\[
\frac{\|Aq-b\|}{\|b\|}
\]

but do not treat it as the principal accuracy metric.

Support multiple incident sources as multiple right-hand sides if the current solver already does so.

## Milestone 5 — exterior receiver evaluation

Use the existing exterior representation/evaluation path with the solved traces. For receivers safely separated from the boundary, ordinary high-order source quadrature should be sufficient.

Do not interpret on-surface Kress correction as a general close-evaluation method. Receivers close to the boundary and nearly touching components remain a separate QBX/singularity-swapping/adaptive-quadrature problem.

---

# 8. Recommended result object

Adapt names to the repository, but return enough structure to audit the solve:

```python
@dataclass(frozen=True)
class MullerBlockResult:
    geometry: PeriodicCurve2D
    exterior_wavenumber: complex
    interior_wavenumber: complex
    delta_V: Array
    delta_K: Array
    delta_Kp: Array
    delta_T: Array
    A11: Array
    A12: Array
    A21: Array
    A22: Array
    system_matrix: Array
    rhs: Array | None
    solution: Array | None
    diagnostics: Mapping[str, Any]
    conventions: Mapping[str, Any]
```

Useful diagnostics include:

- geometry identifier/hash and `N`;
- medium parameters and physical operator prefactors;
- normal orientation;
- Green-function and `T/W` convention;
- Kress logarithm normalization;
- whether Jacobians and `dt` are already included;
- diagonal strategy for each block;
- near/far switch used by `kdiff`, if any;
- finite-value checks;
- per-block norms;
- direct-vs-kdiff overlap errors;
- condition estimate;
- solve residual; and
- runtime by block.

Do not mutate the immutable geometry object with operator diagnostics.

---

# 9. Validation ladder

Validation must separate:

\[
E_{\mathrm{geometry}},\qquad
E_{\mathrm{kernel}},\qquad
E_{\mathrm{quadrature}},\qquad
E_{\mathrm{system}},\qquad
E_{\mathrm{physical}}.
\]

A Kress rule can converge to machine precision on the wrong fitted geometry. Conversely, a correct geometry does not prove the operator signs or diagonals.

## 9.1 Geometry-seam tests

For every solve:

- even endpoint-free uniform `t` grid;
- positive speed;
- counterclockwise orientation under the chosen obstacle convention;
- outward normals consistent with the exact circle;
- positive `ds` weights;
- `sum(ds_weights)` agrees with perimeter; and
- no refitting when `N` changes in an operator convergence study.

## 9.2 Kernel-difference tests

For each difference block:

1. Compare direct exterior-minus-interior evaluation with the cancellation-safe `kdiff` result at well-separated pairs.
2. Sweep separation toward the diagonal.
3. Verify that the near-series and ordinary formulas agree in an overlap region.
4. Verify finite, stable diagonal limits.
5. For `ΔT`, explicitly test loss of significance in naive subtraction and confirm that the cancellation-safe path avoids it.
6. Test complex/lossy wavenumbers as well as real wavenumbers.

These tests should run before matrix assembly.

## 9.3 Zero-contrast test

Set the interior medium equal to the exterior medium.

Then the physical Müller differences should vanish, leaving only the identity structure appropriate to the convention. The solved total boundary traces should reproduce the incident traces, and the scattered receiver field should vanish to numerical tolerance.

This single test simultaneously catches many errors in:

- difference order;
- jump signs;
- physical prefactors;
- receiver representation; and
- incident RHS construction.

## 9.4 Circular Fourier-mode block tests

On an exact circle, use periodic Fourier densities

\[
\varphi_m(t)=e^{imt}
\]

or real sine/cosine equivalents.

For each of `ΔV`, `ΔK`, `ΔKp`, and `ΔT`:

- apply the discrete block to several low and moderate modes;
- compare against analytic Fourier–Bessel eigenvalues where already available, or the repository's trusted Nyström/reference implementation;
- measure block-action error under `N → 2N → 4N`.

This is the strongest way to validate each entire matrix row without first solving a coupled problem.

## 9.5 Manufactured transmission test

Use a solution with known interior and exterior traces, then test:

- each operator equation separately;
- Dirichlet transmission residual;
- Neumann/flux transmission residual;
- recovered `u_D` and `u_N`; and
- receiver or far-field error.

Do not report only `||Aq-b||`.

## 9.6 Existing circular-cylinder physical reference

Reuse the verified line-source penetrable-cylinder Fourier–Bessel solution. Sweep:

- several frequencies;
- contrast, including zero contrast;
- lossless and lossy media; and
- `N` on one frozen exact circle.

Record separately:

- absolute receiver-field error;
- relative receiver-field error;
- boundary-trace error;
- transmission residuals; and
- matrix condition estimate.

Retain absolute error because frequencies with a near-null true scattered field can make relative error look artificially large.

## 9.7 Noncircular convergence

After the exact-circle tests pass:

1. use an exact smooth Fourier/star parameterization to test the operator independently of SDF conversion;
2. use the accepted Method-B SDF-derived Fourier curve;
3. freeze that curve and vary only `N`;
4. then vary the geometry bandwidth `K` separately.

This preserves the distinction:

```text
vary N at fixed γ  -> quadrature/operator resolution
vary K at fixed SDF -> geometry representation resolution
```

## 9.8 Cross-checks against existing solvers

Use the existing implementations as independent controls where appropriate:

- `nystrom_ref` or analytic circle data as the primary oracle;
- current `kdiff` block/action results away from the diagonal;
- the offset-based solver as a lower-order historical control;
- existing QBX results as a near/on-surface cross-check, not as proof of Müller-specific signs.

Do not make agreement among two code paths that share the same kernel routine the only validation evidence.

---

# 10. Metrics to place in the main table

Keep the principal result table narrow. For each geometry, frequency, `N`, and implementation variant, report:

| Category | Metric |
|---|---|
| Identity | geometry ID, exact/SDF-derived, method, `K`, `N`, frequency, contrast |
| Status | success/failure and reason |
| Kernel | worst direct-vs-kdiff overlap error; near-diagonal stability flag |
| Block accuracy | max or relative action error for `ΔV`, `ΔK`, `ΔKp`, `ΔT` against reference |
| System | `cond(A)` estimate and relative linear residual |
| Boundary physics | Dirichlet and Neumann transmission residuals |
| Trace accuracy | relative errors in `u_D` and `u_N`, where reference exists |
| Physical accuracy | absolute and relative receiver/far-field error |
| Convergence | adjacent `N`-doubling ratios on the frozen curve |
| Cost | block-build time, solve time, receiver-evaluation time, memory |

Secondary diagnostics can remain in JSON/NPZ artifacts:

- individual block norms;
- diagonal values;
- Kress coefficient/remainder tails;
- spectral density tails;
- geometry metrics copied from the frozen curve bundle; and
- per-source errors.

No scalar aggregate score should choose the implementation.

---

# 11. Acceptance logic

A candidate Müller implementation is not accepted merely because it returns a finite solution.

Minimum qualitative gates:

1. all geometry invariants pass;
2. every block is finite without post-hoc `nan` replacement;
3. near/far and series/direct kernel formulas overlap consistently;
4. zero contrast produces negligible scattering;
5. circle Fourier-mode block actions converge to the independent reference;
6. the full circular-cylinder solution converges under `N` refinement;
7. boundary transmission residuals converge;
8. no operator or identity term is counted twice;
9. the direct unsquared system is solved; and
10. the result is at least as accurate as the existing trusted reference/control at comparable resolution.

Do not encode one universal `N`, one universal condition-number threshold, or one universal frequency-independent tolerance. Store the convergence evidence and use scale-aware tolerances already customary in the repository.

---

# 12. Multiple components: design now, defer difficult quadrature

The current SDF Phase-1 converter rejects multiple components before fitting, although the low-level contour front end can detect them. The Müller API should nevertheless avoid assuming that one component is the only possible future case.

The eventual representation is

\[
\Gamma=\bigcup_{\ell=1}^{M}\Gamma_\ell,
\qquad
\gamma_\ell:S^1\to\Gamma_\ell.
\]

For a future block matrix:

- each same-component block receives Kress self treatment;
- well-separated cross-component blocks are smooth and can use ordinary high-order quadrature;
- nearly touching cross-component blocks require separate close-evaluation machinery;
- component orientation and region/material ownership must be explicit; and
- disconnected curves must never be concatenated into one fake periodic parameterization.

Do not implement the near-touching case in this phase, but keep component indexing and geometry metadata extensible.

---

# 13. Common failure modes to prevent

Codex should explicitly guard against the following:

- passing raw marching points instead of `PeriodicCurve2D`;
- recomputing normals from the SDF inside the operator code;
- flipping the normal for the interior medium rather than using one global boundary normal and correct jump relations;
- summing interior and exterior hypersingular blocks when Müller requires the cancelling combination;
- subtracting two individually hypersingular floating-point values near the diagonal;
- treating a finite diagonal replacement as proof of spectral convergence;
- applying both `arc_length_weights` and a Jacobian already included in the Kress split;
- adding \(\pm\tfrac12 I\) jumps in both the operator builder and final assembler;
- transposing `K` to obtain `Kp` without checking target/source-normal and weight conventions;
- solving squared/normal equations;
- judging accuracy only by the algebraic residual;
- conflating geometry-bandwidth refinement with quadrature-node refinement;
- using relative receiver error alone at physical near-nulls; and
- assuming on-surface Kress correction resolves a different nearby branch or near-boundary receiver.

---

# 14. Recommended Codex execution order

1. Read the four companion documents and inspect the existing operator, kdiff, reference, and solver code.
2. Write down the convention package and identify the current trusted matrix assembly.
3. Add an adapter from an exact-circle `PeriodicCurve2D` to the existing operator inputs.
4. Reproduce existing far/off-diagonal operator actions without changing kernels.
5. Expose exterior, interior, and difference blocks separately.
6. Add cancellation/overlap tests, especially for `ΔT`.
7. Reuse the tested scalar Kress weight implementation for an operator-specific `A log + B` split.
8. Validate `ΔT` first, then complete the other difference blocks as required for high-order convergence.
9. Assemble the four Müller blocks with jumps/identities added exactly once.
10. Solve the unsquared system on the exact circle.
11. Pass zero-contrast, Fourier-mode, manufactured-transmission, and circular-cylinder tests.
12. Repeat on an exact noncircular Fourier curve.
13. Repeat on the accepted Method-B SDF-derived curve, freezing `γ` while sweeping `N`.
14. Only after this evidence is stable, connect the new path to the broader forward driver behind an explicit opt-in solver selection.

---

# 15. Concise Codex task statement

```text
Implement the next isolated phase of the SDF-to-BIE pipeline:

PeriodicParameterization2D
    -> discretize at uniform even N
PeriodicCurve2D
    -> existing Helmholtz operator/kdiff machinery
cancellation-safe Müller difference blocks
    -> Kress-discretized 2N x 2N Müller system
    -> direct solve and receiver evaluation.

Treat the repository's existing Green function, operator definitions,
material scaling, incident fields, receiver evaluator, kdiff routines,
and analytic/reference solvers as authoritative. Do not create a new
parallel Helmholtz implementation unless a missing primitive is proved.

First freeze and document the sign/normal/jump convention. Under the
current project shorthand the target system is

    [ I - (K_out-K_in)      V_out-V_in       ] [u_D]
    [ T_out-T_in            I+(Kp_out-Kp_in) ] [u_N]

against the incident Dirichlet and Neumann traces, but translate this
through the actual repository definitions of T/W, flux scaling, jumps,
and Green-function sign. Verify rather than assume.

Use PeriodicCurve2D as the sole geometry seam. Do not pass the SDF,
marching polygon, or fitting state into the BIE layer. Preserve uniform
endpoint-free t_j, outward normals, curve derivatives, and source
Jacobians. Audit weight ownership so dt*|gamma'| appears exactly once.

Construct the physical exterior/interior Müller combination before
near-diagonal discretization, especially for the hypersingular block.
Reuse the existing kdiff/series path to expose cancellation. Never form
two individually hypersingular diagonal values and subtract them.

Reuse the scalar Kress logarithmic weights already validated by the
frozen-curve proxy. Make each operator difference provide the smooth
coefficient and smooth remainder, including analytic/removable diagonal
limits. Start with Delta-T/Delta-W, then complete Delta-V, Delta-K and
Delta-Kp according to convergence evidence.

Return and persist all four difference blocks and all four final matrix
blocks separately, not only the assembled A. Solve A q = b directly; do
not square A.

Validate in this order:
1. geometry/normal/weight invariants;
2. direct-vs-kdiff far and overlap tests;
3. zero contrast;
4. exact-circle Fourier-mode actions for each block;
5. manufactured transmission conditions;
6. the existing analytic penetrable-cylinder line-source solution;
7. exact noncircular Fourier geometry;
8. accepted Method-B SDF geometry with frozen-gamma N doubling.

Report block-action error, boundary transmission residuals, trace error,
absolute and relative receiver error, condition estimate, ordinary solve
residual, convergence ratios, and runtime separately. Agreement or a
small linear residual alone is not acceptance.

Keep the first implementation single-component. Make the interfaces
component-aware for later extension: Kress on each self block, ordinary
quadrature on well-separated cross blocks, and separate close-evaluation
machinery for near-touching components.
```
