# BIE-002 contract review — 2026-09-15

Owner/reviewer: Codex / self-review; no independent reviewer claimed.

The user instructed execution of the new ZIP, going as far as possible, and
granted all permissions except branch creation. This explicit session instruction
supersedes the packet's proposed-status/named-phrase hold for this bounded BIE-002
contract. It does not expand the scientific scope. Stay on the existing branch.
The user also identified concurrent topology work: all numerical additions are
isolated under `experiments/bie002_modal_diagnostic`; shared source is read-only,
hashed before/after and checked during execution. No topology files or shared
indexes are edited. No commit/push is implied by the ZIP.

| Recommendation | Disposition |
|---|---|
| Full unitary control, separate trace scaling, reduced equations | Accept |
| Refined reference and reduced-node Kress comparator | Accept |
| Analytic single-interface operator derivatives | Accept; wrap existing `_directional_operators`, reuse LU equally in both arms |
| Multi-interface derivatives / BIE-004 | Defer; live implementation only supports `KressTMzForwardResult` |
| Fixed operator bands and oracle profiles of A-I | Accept; ellipse/star only for fixed bands, dense cross-block accounting in profiles |
| Direct coefficient assembly / production integration / idea 3 | Defer |
| Earlier broad two-track handoff | Superseded for this diagnostic; preserve history |
| BIE-001 desk-study selection | Superseded by this review and BIE-002 contract; never numerically executed |

## Live API map

`system.py` and `multicomponent.py` assemble the direct unsquared
`[[I-DeltaK, DeltaV],[-DeltaT,I+DeltaKp]]`. Unknown order is all components'
Dirichlet nodes, then all components' Neumann nodes. Incident traces form B;
the exposed receiver operator is C=[D,-S] with quadrature already applied.
Predictions transpose C U into source/receiver order and select paired indices.
The experiment builds the same objects with existing factories; no kernel copies.
Single-interface base result records supply the existing directional-operator
routine, which recomputes primal kernels and checks them against stored A/B/C.
Those calls count both as derivative calls and primal reassemblies. Its public
JVP adds `np.linalg.solve`; the experiment calls the existing operator seam to
measure actual LU reuse without that avoidable factorization. This private API
dependency is explicit and pinned, not a production API extension.

## Focused reading

[Boubendir–Domínguez–Turc](https://arxiv.org/abs/1404.1331) supports a strong
trigonometric Nyström transmission baseline. The abstract of
[Jiang–Wang–Yu](https://link.springer.com/article/10.1007/s11075-021-01082-0)
motivates convolution/compact splitting for Dirichlet equations;
[Slevinsky–Olver](https://arxiv.org/abs/1507.00596) motivates separating known
singular actions in coefficient space. These are mechanism precedents, not
certificates for this coupled Müller projection. Only abstracts/metadata were
checked; no claim of reproducing their algorithms or numerical studies.
