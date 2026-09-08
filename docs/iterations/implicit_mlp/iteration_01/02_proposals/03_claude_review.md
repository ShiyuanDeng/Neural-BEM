# Additional review comments

Recorded in commit `7f9e7d6`, co-authored by Claude. Preserved as a dated
discussion; the iteration final review records the conclusions after testing.


A second pass over the same two commits, the
[checkpoint audit](../../../../../results/validation/implicit_mlp_adjoint/review-20260908/README.md)
and the historical bundles. These comments follow the guide's phases and add to
the [Codex companion review](02_codex_review.md) rather than restating it.

## On the termination correction

**Concur, and it supersedes a published claim.** Finding 4 of the
[rerun bundle](../../../../../results/validation/implicit_mlp_adjoint/rerun-20260907/README.md)
asserted that the bandwidth-96 star reached a real line-search stop with the
guard no longer binding. The probe shows the refinement-change condition
rejecting the backtrack-8 candidate at `1.15825e-5 m` against a `1e-5 m` limit,
while backtracks 9, 10 and 12 satisfy every production condition. That finding
has been corrected in place and now points here.

**Add a magnitude caveat before running the deeper search.** The accepted
fallback steps are small: backtrack 9 moves no weight by more than
`1.953125e-6` and lowers the loss from `0.3461879920809253` to
`0.3460535595880327`, a decrease of `1.344e-4`, or `0.039%`. A naive
constant-rate extrapolation puts a useful loss reduction at order `10^3` such
steps. `--max-backtracks` already exists with default 8, so raising it is a
one-flag experiment; the expected outcome is that a clean stop becomes a slow
crawl. Run it to close the termination question, and declare an accepted-step
size floor so the result is not read as recovery. It cannot explain the
`36.386 mm` shape error, and the report should say so before the run rather
than after.

## On acquisition: the ring is quasi-monostatic

**The largest unexamined lever is not the pair count.** Both documents treat
angular acquisition as eight versus 12 pairs. The stronger fact is structural:
`PairedForwardProblem` states that source row `i` is observed only at receiver
row `i` (`solvers/sdf_inverse/forward.py:118`), and `_ring_scan` places each
receiver `0.06 m` from its source at `0.3 m` standoff, a separation of about
`0.2 rad`. Every measurement is therefore near-backscatter, and each BEM solve
already produces the field at every receiver before that field is discarded.

A multistatic readout of the same eight sources gives 64 complex measurements
per frequency, or 128 real data directions, against the 16 available now, at
close to the present solve cost. This speaks directly to the dimension bound
raised in section 1A: 21 real modal columns cannot be resolved by 16 real
directions at one frequency, and no frequency ablation removes that ceiling.

The Kress side already carries the general case — `shape_derivative.py:518`
allocates a full `(receivers, sources)` cotangent — so the restriction lives in
the problem and loss layer, not in the solver. This is a real change to a
validated contract and is not free, but it should be a declared Phase-2 arm
rather than an unexamined constant.

## On ordering: two cheap controls belong before Phase 1

**Run the matched pair-count control first.** The historical five-parameter
star at 12 pairs took `74.00 s` in Kress. Repeating it at `--num-pairs 8`, with
everything else held, is the cheapest experiment in either document and decides
whether frequency is worth ablating at all. Both documents schedule it inside
Phase 2, behind a modal Jacobian study. If the lobes still recover at eight
pairs, the acquisition hypothesis is closed and P1 through P4 answer a settled
question.

**Add a start-at-truth control.** Neither document has one. Initialize the
SIREN at the exact-target fit that the driver already builds for the
representation floor, then run the production inverse unchanged. If it walks
away from the target, the limit is optimization and conditioning; if it stays,
the landscape near the solution is sound and the difficulty is the basin
reached from the wrong initial star. This distinguishes hypotheses that local
Jacobians cannot: a well-conditioned physical Jacobian at the target is
consistent with both outcomes. Cost is one short inverse run.

## On holdout reservation

**Endorse the collision catch and apply it to the whole plan.** Reserve the
evaluation set against the union of every planned training stage, not per
phase. The guide's Phase-2 holdout `{0.25, 1.0, 3.0}` collides with the
Phase-4 stage at 1.0 GHz; `{0.25, 3.0}` is disjoint from the whole proposed
path `{0.5, 1.0, 1.5, 2.0, 2.5}`.

Check 3.0 GHz before adopting it. `DEFAULT_STAR_ORACLE_NODES = 512` was chosen
for a band ending at 2.5 GHz. The `observation_oracle_self_convergence` gate at
`1e-8` fails loudly rather than silently, so the risk is a wasted ablation, not
a wrong number; a short standalone oracle check is cheaper than discovering it
mid-sweep.

## On Phase 5

**Agree that the minimum-norm step is metric-dependent; also reschedule the
diagnostic.** With eight pairs and two frequencies the residual is 32 real
numbers, so `J J^T` is `32 x 32` and the full weight Jacobian costs 32 adjoint
solves. The diagnostic this review asks for before building an optimizer is
therefore hours of work, not a rewrite, and does not need to wait behind four
phases.

State the ceiling plainly in the Phase-1 report: at most `2 * pairs *
frequencies` weight-space directions are constrained by the data, which is 32
today, against 8,577 weights. That is arithmetic about the measurement
dimension, not a claim about SIREN or Adam, and it holds for every optimizer.
It is also the second argument for the multistatic arm above, which raises the
ceiling by eight.

## Suggested ordering

| Order | Experiment | Approximate cost | What it decides |
|---|---|---|---|
| 1 | Five-parameter star at eight pairs, 0.5/1.5 GHz | about 75 s | Whether angular acquisition alone explains the historical control's success |
| 2 | Deeper backtracking from the frozen checkpoint, with a declared step floor | short | Closes the termination question separately from the shape error |
| 3 | Start-at-truth MLP inverse | one short run | Separates conditioning from basin |
| 4 | Scaled neural Jacobian spectrum at the initial star | hours | Measures the constrained-direction ceiling directly |
| 5 | Phase 1B, then 1A if still warranted | as scoped | Physical then modal observability |

Frequency ablation, continuation and a new optimizer stay conditional on these.
The disagreement with the guide is about sequence and cost, not about method:
its discipline, ownership model and refusal to treat falling training loss as
success should all be kept.
