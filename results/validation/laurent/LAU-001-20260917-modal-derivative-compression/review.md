# Review — SELF-REVIEW ONLY

No independent reviewer was assigned to LAU-001. This is the owner's own
assessment against the plan's six review questions. It is not a substitute for
independent review, and the verdict should be read with that discount.

**Was this genuinely adaptive/derivative-aware, rather than BIE-002's band
experiment repeated?** Yes. The compressed object is the independently
constructed node-free operator, not a projection of a Nyström matrix; the
protected part is a verified analytic log-symbol split, not the identity alone;
and the decisive comparison (`FORWARD` versus `DERIVATIVE_AWARE`) is a rule
BIE-002 never tested. BIE-002's band is retained as the negative control and
reproduces its original negative result.

**Were `q`, Fourier normalisation, RHS, receivers, signs and geometry
dependencies handled consistently?** For the native path, yes, and it is checked
rather than asserted: the split reconstructs the assembled operator to `1e-16`,
the three assemblers agree to `1e-14`, the data derivative matches the qualified
Jacobian to `1e-12`, and a tangential reparameterisation leaves receiver data
stationary to `1e-6`. The projected-Nyström control uses a unitary DFT rather
than the plan's physical-coefficient convention; that is consistent internally
and documented in `audit.md`, but it means the two operators are compared only
through convention-independent quantities.

**Did derivatives differentiate the same frozen-mask model, and was the
continuous reciprocal check labelled separately?** The first: yes, and an early
bug that held `b` and `C` fixed inside the finite difference was found and fixed
before the campaign -- it is why 44/48 tangent checks now pass instead of 0/48.
The second: **no** -- the reciprocal/Hadamard arm was not run at all. That is a
gap against the plan, recorded in the README's limitations rather than papered
over.

**Were noncircular, held-out and refined cases qualified without changing gates
after results?** Gates were frozen in `metrics.GATES` before execution and were
not touched. Two reporting changes were made after the pilot -- separating
training from held-out derivative error, and raising the doubled-cutoff guard so
the star's refinement check could run -- neither of which relaxed a threshold.
`k_out*a_ref = 10` was declared `UNQUALIFIED` rather than reported as a
compression failure, and the star's failure at its own cutoff is reported as a
failure rather than replaced by the doubled-cutoff result.

**Was the protected singular part actually verified, and were all costs
counted?** The split is exact and reconstruction-checked per block. Costs are
counted and the conclusion is negative: coupling retention produced **no**
measured saving, because the mask needs all dense entries and all training
derivatives first and the solve stays dense. That is stated as the blocking
finding, not hidden behind an "online" number.

**Does any speed claim survive comparison with the nodal reciprocal/compiled
baseline?** No speed claim is made. The only measured speedup (`COEFFICIENT_WINDOW`,
1.5-2.3x assembly) is a different mechanism, was measured with one repeat rather
than the plan's three-repeat alternating protocol, and is not compared against
nodal Kress at all.

**Weakest points of this bundle, in order.** (1) Self-review only. (2) The
reciprocal derivative arm is missing. (3) The projected-Nyström control was
verified but never compressed, so nothing here says whether these rules transfer
to it. (4) Timings are indicative only. (5) Four training directions, one anchor
per fixture, no noise -- and the circle result shows directly that a mask trained
on four directions is not validated for a fifth.
