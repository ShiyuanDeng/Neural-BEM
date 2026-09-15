# BIE-004 review — coupled analytic shape derivatives

2026-09-15. Owner: Codex. Reviewer: owner self-review; no independent reviewer
claimed. The user explicitly asked BIE and topology to proceed concurrently and
then instructed this agent to keep working on BIE, following the proposed
BIE-004 scope. That instruction authorizes this bounded implementation and
validation. It supersedes the earlier successor hold for BIE-004, while the
branch/worktree prohibition remains in force.

## Question and decisions

Can the existing analytic single-interface machinery produce accurate, cheaper
**full residual Jacobians** for the coupled multi-object problem at fixed
topology? A scalar loss adjoint or a few correct directional derivatives alone
do not answer that question.

| Decision | Disposition |
|---|---|
| Preserve Kress/Müller formulation, acquisition, materials and gauge | Accept |
| Reuse existing `_Jet`, `_difference_matrices` and special-function derivatives | Accept; pin these private dependencies |
| Differentiate all directed cross-object blocks, normals and source weights | Accept; essential coupling, not isolated-object differentiation |
| Reuse one primal LU across tangent right-hand sides | Accept; count factorization separately from solves |
| Compare the same geometry paths as the current gauge-aware FD Jacobian | Accept; verify retraction identity on the fixed linear subspace |
| Multi-material, magnetic/lossy media, topology-event derivatives | Defer |
| Change production solver API or optimizer | Defer; isolated experiment first |
| Revive modal compression or geometry/operator Taylor reuse | Defer |
| Claim recovery improvement from derivative agreement or speed | Reject |

## Interface map and change boundary

`multicomponent.py` assembles self exterior-minus-interior blocks and directed
exterior-only cross blocks into `[[I-dK,dV],[-dT,I+dKp]]`. The global state
orders all Dirichlet component nodes before all Neumann component nodes.
`shape_derivative.py` already differentiates self kernels, branch choices and
Kress diagonals. The extension will use that implementation unchanged and add
the analytic jets of the smooth cross kernels, then incident B and receiver C.

`MultiRadialFourierState.gauge_tangent_basis()` supplies the optimizer's actual
directions; `incremented(...).polar_angle_gauge_fixed()` supplies its FD path.
The gauge-fixed Cartesian set is a linear coefficient subspace. We must measure
that the saved states and perturbed directions stay on it before treating its
retraction derivative as identity. No derivative of a general off-subspace or
branch-changing re-gauge is claimed.

New numerical files belong only under `experiments/bie004_multi_derivative/`.
Shared source is read-only and checked by hashes before/after stages. Topology
may write its own files concurrently. BIE benchmarks run as one single-thread
worker and record external numerical processes; concurrent timing is marked
inconclusive or deferred rather than credited as a speed result.

The [plan](../03_plan.md) owns frozen fixtures, gates and budgets. The first
checks cover uneven component node counts/native periods, collective versus
relative translations, moving either component, and a noncircular shape mode.
Only then compare all 34 gauge-coordinate columns on saved two-star states.
