# BIE-002 — diagnose modal field and operator structure

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION.
- **Execution status:** NOT STARTED.
- **Question:** does either field reduction or nontrivial operator structure justify one follow-on prototype?
- **Hypotheses:** H2-FIELD and H2-OPERATOR in [01](01_SCIENTIFIC_DECISION.md).
- **Baseline:** current local Kress/Müller forward at a qualified resolution, plus a tuned reduced-node Kress control; B0 is historical provenance, not a requirement to downgrade current source.
- **Intervention:** experiment-local Fourier transformations, truncation and declared coefficient-structure measurements. No production formulation change.
- **Controls:** identical geometry, parameterization, frequency, materials, acquisition, sources, indexing, normalization, gauge and reference data.
- **Scope:** new scripts/tests under `experiments/bie002_modal_diagnostic/`; a fresh result bundle; narrowly scoped document updates. Shared numerical modules are read-only.
- **Metrics / budget:** [04](04_VALIDATION_COST_AND_STOP_RULES.md), frozen before numerical execution.
- **Decision:** propose one justified successor, or close with a negative/inconclusive result. No automatic adoption.
- **Owner / reviewer:** unassigned / unassigned.

## A. Reconcile source before numerical work

Read the live files and the governance rules listed in [05](05_REPOSITORY_HANDOFF.md). Record the commit, dirty paths, numerical file hashes and dependency versions. Check for already completed equivalent diagnostics; reuse validated artifacts rather than rerunning them.

Map the actual unknown ordering, component ordering, source/receiver ordering, and the exact stored A, B, C. Verify signs against production code; do not reconstruct a remembered Müller convention. Use the direct unsquared system. Do not form normal equations or impose Hermitian symmetry.

Instrument through experiment-local wrappers. Existing timings may be reused, but distinguish assembly, factorization, triangular solves and receiver evaluation. If access to an essential operator would require modifying a shared solver API, stop that part and write the specific interface proposal. Do not quietly expand scope.

## B. Mathematical seam and dimensions

At one frequency and fixed topology, use

    A(c) U(c) = B(c),        Y(c) = C(c) U(c).

c is the real geometry coefficient vector. If component l has N_l nodes, the full complex system dimension is n = 2*sum_l N_l. U has n rows and one column per transmitter. B has the same shape. C maps traces to receiver fields. Y here precedes production transpose, acquisition selection and residual transformation; those operations remain unchanged.

The two trace blocks are Dirichlet values u_D and outward-normal derivatives u_N. Confirm the implementation's ordering. Distinguish geometry bandwidth K_gamma, retained field modes K_u, quadrature resolution N_l, and admissible geometry direction count q.

### Fixed dimensional scaling for fair diagnostics

Raw trace blocks have different physical units. Choose and record one positive characteristic length ell per scene from the base geometry, and hold it fixed across frequencies, resolutions, perturbations and comparison arms. For example, the base scene's bounding-box diagonal is an adequate declared scaling convention, not a claim about the optimal norm.

With S multiplying every Neumann trace/equation row by ell and leaving Dirichlet rows unchanged, define

    U_s = S U
    A_s = S A S^(-1),       B_s = S B,       C_s = C S^(-1).

Implement the diagonal operations, not an explicit inverse. This scaling is shared by nodal and modal diagnostics, so it cannot be credited to modal coordinates. Do not call its Euclidean condition number the natural Sobolev operator condition number. Report physical trace errors separately with arc-length weights.

S is fixed in each derivative calculation. If a different geometry-dependent scaling is introduced later, its derivatives must be included; that change is not part of this experiment.

## C. Full-mode coordinate control

For each component use its existing native uniform parameter nodes, not newly chosen arc-length nodes. On a 2*pi-periodic parameter grid t_j, the Fourier synthesis entries are

    P[j,m] = exp(i*m*t_j) / sqrt(N_l).

For another period use the corresponding dimensionless phase. Assemble the block synthesis matrix according to the actual component/trace layout. The all-mode matrix Q is square and unitary.

On an even grid, use each of the N_l discrete modes once, including exactly one Nyquist representative. Smaller symmetric sets -M,...,M exclude the Nyquist until the full-mode control. Field coefficients are complex; DO NOT impose real-geometry conjugate symmetry on them.

Check

    Q* Q = I
    A_hat = Q* A_s Q
    B_hat = Q* B_s
    C_hat = C_s Q
    U_s = Q solve(A_hat, B_hat).

The star denotes conjugate transpose. Test recovery of U, Y and the full-system residual. Full-mode spectral/conditioning equality can be checked on one small fixture; do not perform large SVDs throughout the campaign.

**A already contains source quadrature weights. Do not apply them again.** This is an orthogonal projection of an existing discrete system in parameter-grid coordinates, not a claim to have constructed a continuous arc-length Galerkin method. A true change of testing measure requires additional analysis.

A failed full-mode check is a wiring failure, not evidence about compressibility. Repair at most the bounded allowance in [04](04_VALIDATION_COST_AND_STOP_RULES.md), then stop if unresolved.

## D. Field-reduction diagnostic

Take selected columns P of Q, so P*P = I and P has r<n columns. Compute

    A_r = P* A_s P
    B_r = P* B_s
    C_r = C_s P
    A_r Z = B_r
    Y_r = C_r Z.

The lifted state is S^(-1) P Z. The initial prototype may build the full Kress matrices and project them. That is deliberately a diagnostic: it has NOT removed full assembly or its peak-memory cost.

Use at most four predeclared retained fractions per component, approximately 1/4, 1/2, 3/4 and full, rounded to legal mode counts. Use the same fraction for both traces in the first diagnostic; do not adapt each block after inspecting failures. The full-mode case is the control, not a candidate improvement.

Record primal Fourier tails for both traces and every transmitter. Measure predicted-data error and the lifted residual

    R_full = A_s P Z - B_s,

not merely the small reduced residual. A low tail is screening evidence, not a proof that the reduced solve is stable. Spectral tail plots alone do not qualify a method.

### The indispensable competing baseline

At the same continuous geometry, run Kress on a predeclared smaller even-node ladder and identify the cheapest accuracy-qualified nodal candidate. This is separate from the sufficiently refined reference. Mode truncation is not credited with a gain that a node-count reduction already provides.

Use the same source batch in all arms. Base RHS count, node count and field mode count are not interchangeable complexity measures.

## E. Differentiate the reduced problem, not a projected answer

Use supported analytic derivatives of the actual discrete maps. For a real geometry direction v, write dots for the derivative along c(alpha)=c0+alpha*v, including the derivative of the implemented retraction where relevant.

At fixed P and fixed S:

    dot_A_r = P* dot_A_s P
    dot_B_r = P* dot_B_s
    dot_C_r = dot_C_s P

    A_r dot_Z = dot_B_r - dot_A_r Z
    dot_Y_r = dot_C_r Z + C_r dot_Z.

For the nodal control:

    A_s dot_U_s = dot_B_s - dot_A_s U_s
    dot_Y = dot_C_s U_s + C_s dot_U_s.

These are analytic tangent calculations. Factor each base matrix once and reuse its factors for supported RHS batches in both arms. Include all derivative-assembly costs. Do not silently compare a cached modal solve against a repeatedly factorized nodal solve.

**Projecting the full nodal derivative and calling it the reduced solver's derivative is incorrect.** Z and dot_Z must come from the reduced equations above.

Use the existing analytic single-interface routine if its current support matches the case. It may be wrapped, not rewritten, within this experiment. If its JVP routine bundles an unavoidable extra factorization, record that wrapper cost separately and compare equally instrumented arms; do not describe an unavailable cached implementation as measured.

Coherent geometry jets include gamma and its native parameter derivatives. Freeze P, node correspondence, component identities, gauge basis, scaling and kernel branches during local derivative tests. Differentiate the composed geometry/retraction, not a different raw-coefficient path. Never assume an accepted re-gauge is differentiable across a branch change.

Use at most three deterministic, admissible directions per single-interface case: a translation, an available higher-band shape mode, and a seeded mixed direction. Include directions that are not easy symmetry controls. Normalize and record physical boundary displacement so sensitivity comparisons have the same units.

Multi-component forward tests are mandatory for scope assessment, but **do not invent multi-component sensitivities by differentiating isolated objects**. If a compatible analytic multi-interface derivative already exists at the local checkout, verify and use it within the budget. Otherwise label that part `FORWARD_ONLY / SENSITIVITY_UNQUALIFIED`; extending it is a separately approved BIE-004 task, not a hidden dependency to implement now.

FD may be used only in a declared validation probe. No FD inversion, full FD Jacobian campaign, or new FD-based backend is part of BIE-002. Taylor-remainder checks using the analytic derivative are preferred where practical.

## F. Operator-structure diagnostic, distinct from field reduction

Transform the nontrivial scaled operator H_s=A_s-I, preserving all cross-interface blocks and the exact identity. Inspect the signed block contributions consistent with production; separately summarize the four trace interactions and self/cross-component interactions.

Measure energy/entry retention versus declared thresholds, not just a heatmap. For each block, a sorted-magnitude retention profile is an **oracle compression bound**: finding it required the complete matrix. It does not demonstrate a predictable sparse assembly algorithm.

On at most two preselected noncircular cases, also test one fixed centered-mode band pattern with widths from {4,8,16,32}, clipped to the grid. Use ordinary integer mode differences rather than silently wrapping them. Keep cross-component blocks dense in this simple pattern unless a different cross pattern was declared before running. Report that limitation and its actual storage contribution.

Keep the identity exact. Report both retained nonidentity entries and the storage of the whole system. A nearly diagonal identity-dominated matrix is not evidence that its physically relevant correction is easy to compress.

For the tested fixed-pattern operator, compute solved-data and lifted residual errors. When analytic derivatives are available, freeze the pattern and apply the same linear masking operation to the derivative of H_s; differentiate the resulting approximate system. Do not silently let a magnitude threshold change its support during derivative evaluation.

If simple patterns fail but the oracle profiles suggest structure, report `ORACLE_STRUCTURE_ONLY`, with construction cost included. A direct coefficient-assembly or singular-kernel factorization remains a separate successor. Do not begin porting an entire literature solver inside this diagnostic.

## G. Required output

One fresh bundle must contain the frozen manifest, machine-readable accuracy/timing/work tables, failed and skipped cases, source provenance, reproducible commands, focused tests, and a short verdict separating H2-FIELD from H2-OPERATOR. Use the schema and stop rules in [04](04_VALIDATION_COST_AND_STOP_RULES.md).

Close with exactly one recommendation: a named next prototype justified by the evidence; a specific missing diagnostic; or stop/defer. Do not implement the recommendation during closeout.
