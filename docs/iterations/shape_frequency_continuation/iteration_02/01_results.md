# Iteration 02 — the paper profile recovers the glider

Opened 2026-09-22, closing [iteration 01](../iteration_01/01_results.md)'s
question. [Track handoff](../README.md).

## What opened this cycle

Iteration 01 asked why the resolved paper-profile inverse stopped accepting
updates, and proposed a step-halving comparison from the stalled checkpoint as
the cheapest discriminating check.

**That comparison was not run, and is now moot.** The user supplied the authors'
[reference implementation](../../../reference/papers/README.md#reference-implementation)
mid-cycle and directed that the paper's algorithm be made to work. Reading the
code answers the question directly, so spending a diagnostic on step halving
would have measured a symptom rather than the cause.

The user's instruction in this session ("we are trying to replicate that paper's
algo first... you try to make it work") is the authority for changing numerical
code and launching runs in this cycle. It supersedes iteration 01's recorded
"no expensive inverse runs" constraint for this scope.

## Cause of the stall

The trust region excluded the update's own highest harmonic. At k=1 the profile
set the curvature band from the manuscript's `⌈ck⌉` with c=2, giving **2**,
while §4's update band `floor(3 max(k,ki))` gives **3**. A Gauss-Newton step
carrying mode-3 content therefore put roughly half the curvature energy above
the band and was refused every time.

Measured on the saved SC-012 starting state, the unfiltered Gauss-Newton step
at k=1 has curvature tail fraction **0.4999 at band 2** and **0.0556 at band 3**.
The band, not the step, was the binding constraint.

The consequence propagated. With every Gauss-Newton proposal refused, the search
fell through to a Gaussian filter strength that reduced the update to nearly a
pure translation, so k=1 spent all 50 iterations on near-translations and handed
the ladder a poor iterate. The later `no_acceptable_step` stops at k=1.75 and 2
were downstream of that, not an independent failure.

## What the reference implementation settled

Four settings the manuscript states loosely, each implemented differently here.
The [audit table](../../../../experiments/shape_continuation/PAPER.md#profile-and-fidelity-audit)
owns them; `src/+rla/update_inverse_iterate.m` and `src/+rla/update_geom.m` are
the routines.

| # | Setting | Was | Now |
|---|---|---|---|
| 1 | Trust-region band | `⌈2k⌉` | `max(20, M)` |
| 2 | Trust-region tolerance | energy `0.1` | energy `0.01`, the square of the code's amplitude `eps_curv=0.1` |
| 3 | Gaussian filter | Cartesian curve coefficients, band `K`, `sigma²` | normal update `h`, band `M`, `sigma` |
| 4 | Steepest descent | raw adjoint `J*r` | Cauchy point `t·J*r` |

The manuscript's prose also reads as though no residual decrease is required
(§2.1: "if only one of the updated curves lies in the trust region, we accept
that step"). The code contradicts this — its filter loop exits only on a
non-increasing residual and reverts otherwise — so the existing strict-decrease
rule was kept and is no longer described as a local safeguard. A switch to test
the prose reading was written and then removed once the code settled it.

## Result

[SC-013](../../../../results/validation/shape_continuation/SC-013-paper-glider-recovery/README.md)
owns the measurements. Both Figure 1 contrasts now complete their ladder and
recover the glider from the unit circle:

| Contrast `ki²/k²` | Ladder | Area error `εΓ` | Residual | Forwards |
|---|---|---:|---:|---:|
| 0.33 | k=1→5 | **0.849%** | 5.87e-4 | 272 |
| 10 | k=1→3 | **0.297%** | 1.23e-5 | 386 |

For reference, the unit-circle start scores 36.1% and SC-012 stalled at 15.7%.
Recovered polar coefficients match the §4.1 glider to four digits at `η`=0.33
and five at `η`=10. `η`=10 is the better reconstruction at every shared
frequency, the ordering Figure 1 reports.

**The published error values are not reproduced.** Digitizing Figure 1's error
panels puts our `εΓ` **2.5x to 26x below the published curve at every
frequency of both contrasts**; our k=5 value at `η`=0.33 is roughly what the
paper reaches at k=10. The algorithm's structure and qualitative behaviour
replicate; its numbers do not, and being better is not replication. The two
leading explanations — an update band much wider than the authors' drivers use,
and a forward/data pair that shares more machinery than theirs — are recorded
with a cheap discriminating check in
[SC-013](../../../../results/validation/shape_continuation/SC-013-paper-glider-recovery/README.md#how-this-compares-to-the-published-figure-1).
Until that check runs, this is an internally consistent fixed-ladder baseline,
not a calibrated reproduction of the paper's.

## Which corrections are load-bearing

Only correction 1 is demonstrated to have ended the stall: a `k ≤ 2` ladder with
correction 1 alone produced a trajectory identical to one with all four. That
check ran in the working directory and was not preserved as a bundle; the
identical-trajectory claim is therefore weaker evidence than SC-013's saved runs.

Corrections 3 and 4 are exercised only by `η`=10, where Gauss-Newton proposals
are usually rejected (245 invalid, 59 over-curved) and 304 of 327 accepted
updates are Cauchy-scaled steepest descent. Correction 4 is load-bearing there
and inert at `η`=0.33. **Correction 3 is never exercised: neither ladder uses a
filter level beyond 0.** It is a repair with no measurement behind it, and the
first run that does engage the filter is its real test.

## Interpretation and next decision

The prerequisite iteration 01 named — "a qualified, straightforward inverse
using Cartesian Fourier geometry, scalar Fourier normal updates and nodal
Müller/Kress" — is now met on §4.1. The track's actual research question,
whether adapting the shape-harmonic band and frequency steps beats the fixed
ladder, has a working baseline to be compared against for the first time.

What this does **not** establish: any frequency above k=5, the paper's harder
§4.2–§4.4 shapes (limited data, cavities, multiple components), noise, unknown
contrast, or any benefit from adaptive continuation. Matching `εΓ` is not a
claim of identical trajectories; the declared differences in the audit stand.

Two candidate next steps, neither proposed as an experiment here:

1. **Extend the ladder** toward the paper's k=10 snapshot at `η`=0.33. Cost
   grows as dense `N³`; a budgeted extension would say whether `εΓ` keeps
   tracking Figure 1 or flattens.
2. **Cost, not just accuracy.** At `η`=10 the first six stages exhaust the
   50-iteration limit rather than converging. The reference drivers loosen
   `eps_upd` to `1e-3`; testing that is a cheap, well-posed question and is a
   more honest starting point for adaptive-policy work than accuracy alone.

Either needs a stated budget and an experiment ID before it runs.
