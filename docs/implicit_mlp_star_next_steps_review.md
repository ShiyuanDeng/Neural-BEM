# Review: remaining implicit-MLP star inverse implementation guide

This companion follows the order of
[the implementation guide](implicit_mlp_star_next_steps_codex.md). It reviews
implementation commit `6496cd367541b404ee396a76acf48c03f383a318` and guide commit
`127ac89999d65dfff4700bdeb11d55b875d9d0cd`, using the recorded reruns and a fresh
[frozen-checkpoint audit](../results/validation/implicit_mlp_adjoint/review-20260908/README.md).

**Verdict:** retain the repairs and conversion-resolution controls. Proceed
with the guide's matched observability and acquisition study after correcting
its termination premise. Keep continuation and neural Gauss–Newton conditional
on the earlier measurements.

## Repository state

**Agree.** Reuse the current geometry, Kress forward/adjoint, controllers,
metrics and artifact conventions. The new probe uses the actual local final
star checkpoint and saved observations; it does not substitute a reconstructed
network or change the production optimizer.

## What is already established; do not re-debug these first

**Agree with the retained repairs; amend claims 4 and 5.** The small-gradient
fallback repair, star pretraining policy and explicit conversion guard remain
justified. The frozen comparisons establish Fourier bandwidth as the dominant
conversion-error lever on those checkpoints. They do not establish that every
subsequent candidate passes the guard at bandwidth 96.

The new audit exactly reproduces the final `star-bw96` training loss,
`0.3461879920809253`. Its total gradient norm is `8.643277626394939`, and the
negative total gradient is also a data-descent direction. Probing the unchanged
fallback gives:

| Trial | Measured outcome | Implication |
|---|---|---|
| Backtrack 8, last allowed | Conversion distance 0.112325 mm passes; refinement change 0.0115825 mm exceeds the 0.010 mm limit | The refinement part of the guard still rejects a terminal fallback candidate |
| Backtrack 9 | All production acceptance checks pass; loss falls to 0.3460535595880327 | An acceptable step exists beyond the configured search budget |
| Backtracks 10 and 12 | Both pass all production acceptance checks | The acceptable step is not confined to one tested magnitude |

Thus the final accepted contour's 0.1061 mm conversion distance does not rule
out a guard-related stop. The guard has two conditions and checks each new
candidate. The previous small-gradient repair also does not guarantee that
eight halvings suffice for every gradient and geometry.

These probes do not replay Adam's historical moments or every rejected trial.
They establish an available acceptable fallback step, not eventual recovery.
The backtrack-9 loss improvement is only about 0.039%; it does not explain the
large remaining shape error.

The longer-run conclusions should remain narrow:

| Run | Train relative L2 | Holdout relative L2 | Maximum node-to-target error | Verdict |
|---|---:|---:|---:|---|
| Circle, bandwidth 20 | 0.001795 | 0.07053 | 1.122 mm | Substantial improvement; recovery gates still fail |
| Star, bandwidth 96 | 0.5966 | 1.078 | 36.386 mm | Recovery remains poor; fitted lobe amplitude and phase worsen |

The circle's training/holdout gap alone does not establish that further
iterations cannot improve holdout.

## Working hypothesis

**Agree with separating representation bandwidth from information bandwidth.**
Treat weak lobe observability as a hypothesis. The guide correctly rejects
`kR = mode number` as a hard cutoff.

The historical five-parameter star already succeeds at 0.5/1.5 GHz with 12
pairs; the new neural run uses eight. Those frequencies are therefore not
categorically incapable of recovering the lobes. Both angular sampling and
frequency deserve matched controls. Weight count alone also does not establish
unrecoverability: network directions can change the field without materially
changing its boundary or measured response.

## Before Phase 1 — terminate only after an audited search

**Add a small prerequisite to the guide.** Log rejection reasons separately:
extraction/topology, conversion distance, refinement change, boundary movement,
data Armijo and regularized Armijo. Check a deeper fallback search from the
saved checkpoint, preserving the conversion and acceptance tolerances.

Separate two questions in the resulting report: why the search stopped, and
why the accepted geometry is still inaccurate. The present probe answers part
of the first; it does not answer the second. This is a bounded termination
audit, not a reason to postpone the observability study for another long inverse.

## Phase 1 — modal and physical-parameter observability audit

### 1A. Boundary-mode Jacobian

**Proceed with normalization and combined-frequency spectra added.** Keep the
normal Fourier modes as diagnostic probes and preserve MLP geometry ownership.
Declare their displacement scale, preferably reporting sensitivities for equal
RMS normal displacement so the constant and oscillatory modes are comparable.

In addition to individual frequencies, vertically stack the real Jacobians
for each proposed training set and report those spectra and correlations.
Single-frequency spectra alone cannot measure complementary information across
frequencies.

With eight paired complex measurements, each frequency contributes at most
16 real data directions. The proposed modes 0 through 10 give 21 real columns,
so a single-frequency modal Jacobian must have a null space. The current two
frequencies supply at most 32 real data directions. Distinguish these dimension
limits from numerical rank loss and from the observability of the particular
amplitude/phase directions of interest.

### 1B. Five-parameter physical Jacobian

**Proceed with declared parameter scales.** Report native-unit derivatives,
but compute comparative conditioning using dimensionless parameter scales or
equal RMS boundary displacement. Centre/radius in metres, relative amplitude
and rotation in radians cannot share an unqualified condition number: changing
metres to millimetres would change it without changing the experiment.

Keep the guide's distinction between arc-length mode 5 and physical star
amplitude/rotation. A local full-rank physical Jacobian is useful evidence of
local identifiability; it does not guarantee convergence from the wrong initial
star or uniqueness in the larger neural shape space.

### 1C. Derivative validation

**Agree.** Use fresh central differences with several magnitudes. Also verify
forward and derivative refinement at the new frequencies and frozen geometries.
`num_nodes >= 2K+2` permits sampling the curve; it is not a convergence
certificate for the BEM operators. This calls for convergence checks, not a
quadrature redesign.

### Phase-1 artifacts

Keep the requested CSVs and plots. Add the declared displacement/parameter
scales, combined-frequency spectra, dimension-imposed rank limits and derivative
convergence windows. Report the result even if mode-5 information is already
strong at 0.5/1.5 GHz.

## Phase 2 — matched five-parameter star controls

**Proceed, adding an angular-acquisition control.** Alongside P0–P4, compare
eight and 12 pairs at the same 0.5/1.5 GHz, initial shape, materials and resolved
forward configuration. This tests the acquisition difference from the
successful historical five-parameter case before prioritizing higher
frequencies over more angles.

Record the actual neural warm-start contour error when comparing it with the
analytic initialization. Matching nominal star parameters does not make a
pretrained neural contour exactly identical to the analytic star.

### Decision after Phase 2

Qualify the proposed causal conclusions:

- Five-parameter failure at higher frequency warrants acquisition and
  initialization/multistart investigation; one optimizer's failure does not
  prove that the acquisition lacks information.
- Failure at the original band and success at a higher band under matched
  conditions supports a frequency explanation for that control.
- Five-parameter success with neural failure narrows the gap to the neural
  representation, optimization or regularization. The five-parameter control
  imposes a strong shape-family prior and uses a different optimizer, so this
  does not uniquely implicate Adam or excess weight count.

Reserve holdout frequencies against the union of all planned training stages.
The guide's Phase-2 holdout includes 1.0 GHz, which Phase 4 later uses to train.

## Phase 3 — matched direct-MLP frequency ablation

**Agree with changing one acquisition factor at a time.** Keep the architecture,
seed, pretraining policy and acceptance contract fixed, and use the corrected
termination diagnostics in every compared run.

Control objective scaling as well as work. The production objective sums
per-frequency normalized squared residuals. Adding a third frequency changes
its balance with a fixed Eikonal term; replacing one frequency in a two-frequency
set does not introduce that particular count change. Declare whether this
balance is preserved or intentionally changed, and avoid attributing the
combined effect solely to new information.

Keep the guide's geometric success criteria. Falling training loss alone is
already known to be insufficient.

## Phase 4 — recursive frequency continuation with the MLP still owning geometry

**Agree as a conditional experiment.** Preserve direct weight updates, transfer
accepted geometry between stages, and reset Adam moments as proposed.

Choose a common evaluation holdout disjoint from every stage: the suggested
path trains at 1.0 GHz, so it cannot retain that frequency as a holdout from
Phase 2. Compare continuation against a direct run with a declared comparable
total work budget; five separate stage budgets should not be mistaken for one
60-update experiment. Record forward evaluations and wall time as well as
accepted updates.

Single-frequency stage losses are different objectives. Report both the
stage-local loss and performance on a fixed declared evaluation set so a
stage transition is not misread as improvement on the same objective. Do not
use holdout performance to select stages or settings.

## Phase 5 — only if the low-dimensional control succeeds but direct-MLP continuation still fails

**Retain the conditional neural Gauss–Newton experiment.** The data-space
damped solve is plausible for the small residual dimension and preserves the
MLP as the optimization variable. Diagnose the scaled neural Jacobian before
building a new optimizer.

The Euclidean minimum-weight-norm step depends on network parameter scaling.
Specify that metric and the regularization objective. Damping the increment
alone is not automatically a prior-centred iteratively regularized
Gauss–Newton method; the guide should distinguish the proposed damped step
from a full IRGN formulation.

Retain actual-candidate extraction, conversion checks, BEM evaluation and
rollback. A successful Gauss–Newton experiment would demonstrate improvement
under its declared conditions; it would not alone prove that historical
failure came specifically from Adam null-space motion.

## What not to change in this study

**Agree with preserving the validated components and ownership model.** Keep
the pretraining repair and guard tolerances. Do not introduce boundary-to-MLP
fitting or enlarge the SIREN without evidence.

The guide explicitly permits reconsideration when new diagnostics contradict
a previous conclusion. The frozen fallback probe supplies that evidence for
the claim that the star's guard and finite-search effects are eliminated.
Distinguish refinement of the guard's independent audit from refinement of
the production conversion at fixed bandwidth; they are different checks.

## Required experiment discipline

Keep the guide's preservation, provenance, independent observations and
holdout rules. Add rejection-reason accounting, declared Jacobian scales,
comparable work budgets and explicit objective scaling. Continue describing
contour distances as sampled numerical checks, not continuous certificates.

## Suggested result structure

Keep the proposed observability bundle and add a compact termination-audit
section or subdirectory. Link this existing review probe rather than rewriting
historical evidence. The top-level decision table should distinguish search
termination, local information and successful nonlinear recovery; its causal
interpretations remain conditional on matched controls.

## Literature motivation for this plan

**Appropriate motivation, not validation of this acquisition.** The cited
[penetrable-object study](https://arxiv.org/abs/2210.11607) examines nonconvex
inverse scattering and recursive linearization. The
[dielectric IRGN paper](https://arxiv.org/abs/2006.10830) treats a three-dimensional
far-field problem, and the [neural implicit paper](https://arxiv.org/abs/2206.02027)
uses IBIM and discusses a generative shape prior. None establishes sufficiency
of this repository's eight-pair acquisition or guarantees full-weight recovery.

## Deliverable

First complete the bounded termination audit, then implement Phase 1 with
scaled and combined-frequency Jacobians. Proceed to the matched Phase-2
controls according to those findings; retain later phases as conditional.

The final report should answer separately: what rejected the proposed steps,
which physical directions the data observes, and which matched experiment
actually improves the recovered geometry.

Review validation: **45 focused inverse/adjoint/repair tests passed**, with
the command and source hashes saved in the
[audit provenance](../results/validation/implicit_mlp_adjoint/review-20260908/provenance.json).
The companion-document edit was checked with `git diff --check`; it changes
no production implementation or experimental results.

---

# Additional review comments

A second pass over the same two commits, the
[checkpoint audit](../results/validation/implicit_mlp_adjoint/review-20260908/README.md)
and the historical bundles. These comments follow the guide's phases and add to
the companion review above rather than restating it.

## On the termination correction

**Concur, and it supersedes a published claim.** Finding 4 of the
[rerun bundle](../results/validation/implicit_mlp_adjoint/rerun-20260907/README.md)
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
