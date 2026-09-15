# Scientific decision and falsifiable hypotheses

## Verdict

**Idea 2 merits a bounded diagnostic. Idea 3 merits a carefully specified later diagnostic, not substantial implementation now.** Analytic differentiation is a competent baseline requirement, not a discovery attributable to either mechanism.

Kress already uses trigonometric approximation and special integration of the singular part. High-order Nyström methods have direct dielectric-transmission precedent [S1]. Therefore, “spectral instead of nodal” and “no uniform sampling” are not sufficient scientific contributions.

For unitary Q, the full coordinate transformation Q* A Q preserves singular values. It does not improve the 2-norm condition number of the same matrix. Truncating, compressing, rescaling, or changing the discretization is a separate intervention.

## Two distinct hypotheses inside idea 2

**H2-FIELD:** at a sufficiently accurate integration resolution, the primal fields and the tested shape-sensitive fields can be represented with substantially fewer Fourier coefficients than nodes. A reduced solve then has fewer unknowns.

Falsification of this prototype: useful field reduction disappears at matched forward/sensitivity accuracy on nontrivial scenes, or a cheaper reduced-node Kress solve achieves the same result.

**H2-OPERATOR:** even when many field modes are needed, the nontrivial operator blocks or their correctly separated pieces have economical mode coupling. This may support a future structured assembly/application method.

Falsification of the tested compression: the declared patterns need most coefficients, lose derivative accuracy, or only look sparse because the identity dominates. Failure does not rule out other singularity-aware factorizations that have not been tested.

Fourier–Galerkin operator splitting and sparse coefficient approximations have precedent for Helmholtz Dirichlet problems [S2]; structured spectral singular-integral methods also exist on other domains/bases [S3]. Those sources motivate these hypotheses, not a guarantee for a coupled multi-interface Müller system.

## Why idea 3 is deferred

Geometry-to-operator and geometry-to-solution holomorphy has theoretical support [S4]. It does not supply a useful Taylor radius or a cheap solve for the updated matrix. Successful low-rank BIE updates for spatially local boundary changes exploit locality [S5]; globally supported Fourier changes do not automatically inherit it.

A one-parameter update can have full matrix rank. For example,

    A(a) = diag(1+a, 1+2a, ..., 1+n*a)

has a full-rank change for any nonzero change in a. Parameter dimension, update rank and update amplitude are different quantities.

Moreover, differentiating d(c) = C(c) A(c)^(-1) B(c) gives the same first-order data prediction as differentiating the separate operators. An operator Taylor surrogate must earn its extra cost by extending the useful prediction region or amortizing repeated work. It does not win merely by reproducing that derivative. Adaptive reduced-model optimization already addresses model validation and enrichment [S6].

## Non-FD derivative policy

The target architecture is not FD-based. Use the actual analytic discrete operator derivatives where supported. A reusable LU/tangent solve is a standard control. FD or Taylor tests may verify a derivative but must not become the production derivative mechanism by default.

Keep these quantities separate:

- directional field derivative / JVP;
- full residual Jacobian used by LM;
- scalar loss gradient from an adjoint;
- operator derivative used in a geometry expansion.

A loss adjoint does not by itself provide the current optimizer's full Jacobian. This diagnostic does not choose a new optimizer and must not mix optimizer changes into the comparison.

## What a positive result would establish

At most: evidence that a particular reduction or compression is worth a next prototype, on the tested physical model and regime. A speed claim requires setup-inclusive, accuracy-matched timing. An inverse-use claim additionally requires sensitivity qualification. A publication-level novelty claim requires a separate comparison with spectral BIE and reduced-order-model literature.

The physical information, acquisition, geometry family and topology policy are held fixed. No representation change creates new measurements or resolves nonuniqueness by itself. Improved recovery from a different frequency schedule must not be credited to a different solver.

## What would constitute a rabbit hole

Stop the current line rather than repeatedly adding filters, bespoke preconditioners, adaptive bases, tolerance changes or extra scene selection to rescue an unsuccessful diagnostic. In particular, do not count as success:

- a full Fourier coordinate change;
- fewer unknowns but unresolved derivative fields;
- a reduced matrix whose full dense parent is omitted from timing or memory;
- a comparison only against an unnecessarily fine Kress grid or an FD-heavy inverse;
- results confined to a circle or an easy low-frequency case;
- changed gauge, source model, material model or acceptance tolerances.

Negative evidence is useful. Report the tested mechanism and its limits precisely instead of inventing a successor automatically.
