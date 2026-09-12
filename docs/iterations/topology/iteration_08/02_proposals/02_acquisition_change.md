# TOP-012 — richer acquisition, and what it costs the benchmark

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION. **Requires a user
  decision**, because every route below changes the frozen v1 data contract.
- **Execution status:** NOT STARTED
- **Owner:** unassigned. **Reviewer:** unassigned.
- **Baseline:** `3c2fd13`.

## Why it is back on the table

The literature verdict ranked multi-frequency continuation **4** and deferred
it, correctly at the time: nothing then showed the acquisition was short of
anything. Four cycles later the picture is different. A state inside the frozen
**0.003** data tolerance at **8.7878e-05** sits **11.849 mm** from the truth with
worst holdout error **1.4154** — and four separate optimizer and representation
repairs improved the objective without moving the geometry. That pattern is what
an information shortage looks like.

It is **not yet proof of one.** [TOP-011](01_sensitivity_and_conditioning.md)
measures how much boundary movement actually hides inside the tolerance, and it
is the cheaper question. **This proposal should not run before that one**, which
would otherwise buy data to fix a problem not yet shown to be about data.

## The constraint that makes this the user's decision

Frozen v1 trains on **24 paired source/receiver observations at 0.5 GHz** and
reserves **1.5 and 2.5 GHz** for evaluation only. Every route below changes what
v1 means, and v1 is immutable by its own contract: a changed scene, acquisition,
mode schedule, tolerance or budget is a **separately named comparison**, never an
overwrite. So this creates a **v2**, and the v1 evidence stays exactly as it is.

## Three routes, with what each costs

**A. More spatial diversity at 0.5 GHz.** Add source/receiver pairs at the
existing training frequency. **This does not touch the frequency holdout at
all** — 1.5 and 2.5 GHz remain untouched and still function as the
evaluation-only set, so the holdout keeps its meaning and the existing holdout
numbers stay comparable. It is the cheapest route and the only one that leaves
the evaluation contract intact. It tests whether the shortage is angular
coverage rather than bandwidth.

**B. More frequencies, with a fresh holdout.** Train on additional frequencies
and reserve a **new, never-fitted** set for evaluation. This is what the
literature actually supports for escaping flat objectives — frequency
continuation, in the Borges–Greengard sense — but it **destroys the current
holdout**: once 1.5 GHz is fitted, no result at 1.5 GHz is held out any more,
and every recorded holdout number in TOP-006 through TOP-010 becomes
incomparable. A new evaluation set has to be generated and then left alone.

**C. Both.** Most informative, most expensive, and it confounds the two effects
unless run as separate arms — which is the same objection the verdict raised
against combining rank 1 and rank 2, and it applies here too.

**Recommendation: A first.** It answers a real question, costs the least, and is
the only route that preserves the evaluation contract. B follows only if A shows
angular coverage is not the shortage.

## Question

Does the reconstruction improve when the acquisition is enriched, on scenes
whose geometry the current acquisition demonstrably fails to pin down?

## Falsifiable hypothesis

If the decoupling is an information shortage, richer data shrinks the boundary
displacement permitted inside the data tolerance and improves matched error on
the failing scenes. If geometry stays wrong with substantially more data, the
limit is not acquisition, and the objective, the representation or the gate
definitions come back into question.

## Controls

Identical scenes, truths, materials, resolutions, budgets, gates and controller
policy. **Acquisition is the only difference**, and the enriched arm is named
separately rather than replacing anything. Oracle generation uses the same
checked finer discretisation as v1, and its convergence is re-checked rather than
assumed. The v1 bundles are not touched, re-run or re-scored.

## What this proposal deliberately does not do

It does not loosen the 0.003 data tolerance to make the gate agree with the
geometry, and it does not re-tune any gate. If TOP-011 shows large displacement
inside that tolerance, the honest response is to say what the tolerance
certifies — not to move it until the numbers flatter the result.

## Budget, to be declared before execution

New oracle generation for whichever route is chosen, plus a full twelve-scene
comparison against the matching v1 arm. Both must be declared with explicit
solve and wall-clock caps before any run, and a fresh output directory.

## Decision criteria

Improvement is measured **per gate, on all twelve scenes**, against the same
policy on v1 data. A pass-count change is the headline; boundary error, IoU,
training and held-out error are reported separately, and the enriched arm must
also report what it cost in solves. No result here transfers back to v1.

## Artifacts

Fresh benchmark version `config/topology_scenes_v2.json` with its own frozen
specification, plus `results/validation/topology/TOP-012-<run-id>/`. The v1
specification and every v1 bundle remain byte-identical.
