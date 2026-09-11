# Is this a known failure? — literature context for the iteration-05 stall

Companion to the [stall diagnostic](01_stall_diagnostic.md). **Provenance: web
search of September 2026, abstracts and publisher summaries only.** No paper
below was read in full, none was checked against our numbers, and nothing here
is evidence about this code. Treat it as a reading list that says which of our
problems are already named in the literature, and which of them we appear to
have arrived at ourselves.

**Status: this page is not the verdict.** On 2026-09-11 the user held all
implementation until a thorough literature review is done. Nothing below
authorises a fix, and the next agent should extend this into a real review
rather than act on it.

## Short answer

Three of the four suspects are well-documented problems in their own fields.
The fourth — the *interaction* between hard geometric feasibility floors and a
topology-changing BIE inverse driven by finite-difference Jacobians — is the one
I could not find reported, and it is exactly the one that stopped our runs.

## 1. The floor is an *unrelaxable* constraint, and that class is named

Le Digabel and Wild's taxonomy of constraints in simulation-based optimization
([arXiv:1505.07881](https://arxiv.org/abs/1505.07881)) defines a constraint as
**relaxable** if the objective can still be evaluated when it is violated, and
**unrelaxable** otherwise. Our feature-radius floor and the quadrature clearance
floor are both unrelaxable in exactly that sense: the Kress assembly raises
rather than returning a degraded value, so a trial point outside the feasible
set produces no information at all. The taxonomy exists because this class
behaves differently from ordinary nonlinear-programming constraints, and it is
the class that breaks methods which sample around the current iterate — which is
what a central-difference Jacobian does.

So the *setting* is named. What I did not find is a report of our specific
consequence: that refusing a probe and freezing its Jacobian column to zero
silently corrupts every direction that coefficient contributes to, so an
iterate resting on an active unrelaxable constraint loses most of its search
space rather than sliding along the constraint. Work on finite-difference and
model-based methods under convex constraints exists and is the natural place to
look for a remedy
([arXiv:2510.17366](https://arxiv.org/pdf/2510.17366),
[arXiv:2111.05443](https://arxiv.org/pdf/2111.05443),
[arXiv:2205.09627](https://arxiv.org/pdf/2205.09627)),
but I found no statement of the pathology in our form.

## 2. Minimum length scale is standard — imposed differently

Topology optimization has a large literature on minimum length scale, motivated
by precisely the artefacts our floor exists to prevent: thin members, one-node
hinges, mesh-dependent solutions
([Zhou, Lazarov, Wang & Sigmund, CMAME 2015](https://www.sciencedirect.com/science/article/abs/pii/S0045782515001693);
[Guest, Prévost & Belytschko, IJNME 2004](https://www.researchgate.net/publication/227625141_Achieving_minimum_length_scale_in_topology_optimization_using_nodal_design_variable_and_projection_functions);
[member/cavity/separation constraints, arXiv:2003.00263](https://arxiv.org/pdf/2003.00263)).

The relevant difference is **how** the length scale is imposed. That literature
overwhelmingly uses filters, projections and geometric penalty terms — smooth,
relaxable reformulations that let the optimizer approach and leave the limit
continuously. We impose ours as a hard feasibility barrier enforced by the
forward solver. That is why their designs converge *with* a length scale while
ours parks *on* it and stops. A filtered or penalised formulation of the same
floor is a candidate fix with an existing body of practice behind it.

## 3. Merging and nucleation are standard; the neck they leave is the issue

Combining shape derivatives with topological derivatives so that components can
nucleate and merge is established practice
([Burger, Hackl & Ring, JCP 2004](https://www.sciencedirect.com/science/article/abs/pii/S0021999103004868);
[Allaire et al., JCP 2007](https://www.sciencedirect.com/science/article/abs/pii/S0021999107000095)),
and level-set formulations are usually recommended because merging and breaking
happen naturally. Our controller does the explicit-curve equivalent.

What our diagnostic shows is the seam between that machinery and §2: the merge
contour fit of a two-lobed mask is a peanut whose neck was already 0.8 mm above
an 8 mm floor, and refinement drove it onto the floor. I found no paper
reporting that a topology event's *own* output can land on the length-scale
constraint and freeze the optimizer, though it is an obvious consequence of
running §2 and §3 together. Candidate acceptance asking for refinement headroom
is, as far as I can tell, ours to test.

## 4. The single-frequency limit is textbook

Our `merge` scene — 7.9e-05 training residual, 0.554 mm boundary error, 9.4%
error at held-out frequencies — is the classic ill-posedness of single-frequency
inverse obstacle scattering. Recursive linearization and frequency continuation
exist for this reason: a low frequency fixes coarse features only, and higher
frequencies refine them
([Borges, Rachh & Greengard, arXiv:2104.13489](https://arxiv.org/abs/2104.13489);
[multi-frequency 2-D reconstruction, arXiv:1408.5436](https://arxiv.org/pdf/1408.5436);
[Borges, multi-frequency overview](https://math.dartmouth.edu/~fastdirect/workshop/Carlos_Borges.pdf)).
Our benchmark trains at 0.5 GHz alone and holds 1.5/2.5 GHz out, so it measures
this limit by construction. Nothing surprising here — but it does mean a
frequency schedule is the known remedy, and it belongs in a separately named
comparison rather than inside the v1 matrix.

## 5. Representation capacity is a known limit with a known vocabulary

That a circle cannot become a star is our `far-two-stars` failure. The same
literature discusses curve complexity as the bandlimit of curvature under
arclength parameterization, notes that star-shaped radial representations bound
what can be recovered, and that non-star-shaped obstacles need a richer curve
space
([Borges multi-frequency overview](https://math.dartmouth.edu/~fastdirect/workshop/Carlos_Borges.pdf);
[neural warm-start for inverse obstacle scattering](https://www.sciencedirect.com/science/article/abs/pii/S0021999123004369)).
Our chart work already reflects this. What is ours to decide is *when* a
component earns more bandwidth, with no supplied object count or shape family.

## What this changes for the next cycle

- Suspects 1 and 3 are the ones worth an experiment, and the literature suggests
  the shape of the fix rather than the fix itself: reformulate the floor the way
  topology optimization does (filter/penalty, relaxable) and/or make acceptance
  reject a winner with no refinement headroom.
- Suspect 2, the frozen Jacobian column, has a well-studied setting and
  off-the-shelf remedies worth reading properly before we invent one.
- Suspect 4 is known, expected, and deliberately outside v1.
- Any claim that this is novel needs a real literature review, not this page.
  Whoever picks this up should read the §1 and §2 sources in full first.
