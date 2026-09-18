# Move from entry counts to a model that preserves inverse information

User-directed innovation phase, 2026-09-17. The literature baseline is sufficient
for the next decision; exact paper tables are no longer the active objective.

The higher-frequency stars have qualified full operators but no passing sparse
mask. This localizes the immediate problem to discarded couplings. Test whether
we can reduce the solution space instead, keeping dense coupling inside it.
Laurent coordinates already give analytic shape tangents, so we can construct a
basis around what the inverse must differentiate, not just its current fields.

Three matched arms separate forward interpolation, explicit tangent enrichment,
and receiver-adjoint closure. For A U=b and A* Z=C*, a basis containing U and Z
reproduces the output and its first parameter derivative at the anchor (assuming
an invertible projected system). This is ordinary projection algebra: it does
not prove accuracy after the shape moves. Frozen-rank offset tests decide that.

Sensitivity interpolation itself is established: see [Benner, Gugercin and
Werner, Structure-Preserving Interpolation for Model Reduction of Parametric
Bilinear Systems](https://www.sciencedirect.com/science/article/pii/S0005109821003198),
which extends parameter-sensitivity matching to structured bilinear systems.
[Doelz and Henriquez](https://arxiv.org/abs/2305.19853) also connect parametric
boundary-integral shape holomorphy to reduced modelling and shape inversion.
These precedents rule out claiming generic shape ROM or derivative interpolation
as our invention. The experimentally testable contribution here is preserving
physical inverse sensitivities in the node-free transmission pipeline, including
untrained coefficient directions and a demonstrable local reuse radius.

The [bounded LAU-003 contract](../03_plan.md) owns implementation and gates.
Fast coefficient assembly, actual inverse speed and new theory remain future
work; a passing anchor alone will not be presented as a successful inverse.
