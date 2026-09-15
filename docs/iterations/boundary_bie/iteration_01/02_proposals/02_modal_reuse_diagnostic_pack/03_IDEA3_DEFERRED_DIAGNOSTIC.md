# Idea 3 — deferred local operator-reuse diagnostic

**Status:** DEFERRED; not authorized by BIE-002.  
**Experiment ID:** unassigned; select an unused BIE ID only when a separate contract is reviewed.  
**Execution:** NOT STARTED.

This is not a second implementation track hidden in the modal contract. A negative modal result does not mathematically invalidate reuse; sequencing is to avoid simultaneous solver changes, not because reuse requires modal success.

## Decision to support

Does an operator-level approximation extend the useful prediction region or lower repeated-evaluation cost beyond simpler alternatives, at matched accuracy?

Two separable mechanisms could matter: cheaper evaluation of changing operators, and cheaper solution of the resulting systems. Measure which one is actually available. Local shape analyticity [S4] supports investigating approximation; it supplies neither an update rank nor an amortized speed guarantee. Spatially local fast BIE updates [S5] are relevant comparators, not guarantees for global Fourier deformations.

## Prerequisites

Use already validated single-interface analytic operator directions and existing saved fixed-topology geometry changes. Start in nodal coordinates. No modal implementation is required. Do not first build a full new multi-interface derivative library or high-order Taylor library.

Keep native parameter correspondence, topology, material, frequency, sources, receiver positions and scales fixed. A split/merge, new component, frequency change, node redistribution or gauge-branch change invalidates that local model unless explicitly accounted for. This diagnostic does not transport models across such events.

## Models to compare on identical geometry steps

Let the base state solve A0 U0=B0 and Y0=C0 U0. For a displacement Delta c, define DA, DB, DC along that full displacement.

**E — exact fresh evaluation:** assemble A1, B1, C1 at c0+Delta c, factor A1 and compute Y1. This supplies the reference and the end-to-end cost.

**T — ordinary tangent-data prediction:**

    A0 dot_U = DB - DA U0
    Y_T = Y0 + DC U0 + C0 dot_U.

Charge derivative construction and the tangent solve. Where a full Jacobian is already available, show that different amortization scenario explicitly instead of pretending its setup is free.

**O — first-order operator surrogate:**

    A_tilde = A0 + DA
    B_tilde = B0 + DB
    C_tilde = C0 + DC
    Y_O = C_tilde solve(A_tilde, B_tilde).

The new matrix generally needs a new factorization. Count it. O and T agree to first order. O retains some nonlinear dependence through matrix inversion, but omitted operator second derivatives generally leave second-order error in the geometry displacement. Do not label O second-order accurate merely because it solves a new matrix.

**P — exact new matrix with old-factorization preconditioning, only if already available cheaply:** assemble the exact new operators and use the base LU as a preconditioner in a residual-controlled iterative solve. This does not save new kernel assembly. Count iterations, matrix-vector applications, all RHS work and fallback factorizations. Do not build a new Krylov framework solely to complete this optional arm.

No explicit matrix inverses. No Woodbury formula until the update's numerical low rank and its construction cost have actually been demonstrated.

## Suggested bounded design for the later contract

Use one supported noncircular single interface at two qualified frequencies, three admissible directions, and four physical displacement amplitudes, for example 1e-4, 1e-3, 1e-2 and 5e-2 times a fixed scene length. Freeze the choices beforehand and retain infeasible steps as such. Saved real optimizer displacement directions are preferable when available; do not use truth to choose a favorable direction.

The later contract should cap exact assemblies, derivative assemblies, reduced/updated solves, memory and elapsed execution separately. A suggested ceiling is 48 exact frequency-system assemblies and 24 analytic directional assemblies, with no inverse run. These numbers are proposed resource limits, not a forecast or present authorization.

Compare error versus physical displacement for T and O. Compute the per-case break-even reuse count

    m_break_even = ceil(T_setup / (T_exact - T_online)),

only when T_exact>T_online. Include validation and rebuild costs in T_online, or show them separately and state the qualification. Check whether the actual available sequence has that many admissible nearby evaluations; a hypothetical infinite reuse limit is not a practical speed result.

Small forward-system residual against A_tilde certifies only the surrogate solve. Assess its prediction against exact A1/B1/C1 and, for final accuracy claims, the refined reference. Formal certified error bounds would be a later contribution, not something this small test provides.

## Continue / stop

A worthwhile successor requires a useful, repeatable accuracy region plus a credible setup-inclusive saving against both E and T, or a distinct proven advantage of P. A locally successful single-state example is not enough to integrate a new controller.

If O merely matches T at greater cost, needs almost every step revalidated/rebuilt, or only works for negligible displacements, stop this first-order approach. Do not automatically escalate to higher orders, reduced bases, new trust regions or a new inverse algorithm. Record one specific follow-on question only when the measurements support it.
