# Faster inverse policies: earlier stage exits

## Questions

1. Can a simple progress rule shorten the hook c13.3 fit while preserving recovery?
2. How can it avoid stopping a temporary slow patch before useful shape change?
3. Do small late increments come from damping/backtracking, or from the current update space?

**Status:** discussion superseded by the [approved PS-002 plan](../03_plan.md).
On 2026-10-26 the user chose the literal 5% / two-iteration rule in every stage
and authorized one immediate hook fit. Historical recommendations remain below.

## Starting point

The user suspects long nearly flat stage tails and damping/backtracking that
make increments too small. Their initial candidate is a stage exit when loss
decreases by less than 5% over the last two iterations.

The baseline is [GU-002](../../../../../results/validation/cleaned_interfaces/GU-002/README.md):
hook c13.3, modal Muller with GPU slider preparation, no localization, and the
default `CumulativePolicy` v1.0.0. It recovered in 30.3 s, 125 accepted iterations
and 2,978 work units. The CPU-preparation slider follows the same accepted path.

K means stored geometry band, M normal update band, Ku physics trace cutoff,
and F the active frequency set. At M11, M15 and M19, K=192, Ku=128 and all 19
real frequencies stay fixed. Only the update band changes between those stages.

## What the saved histories say

These are arithmetic checks of saved losses, not new inverse fits. For the
table, interpret the proposal as the combined relative decrease across two
accepted iterations of the same stage, tested first after iteration 2.

| Slider stage | First trigger / saved accepted iterations | Loss at trigger | Saved final loss | Later decrease |
|---|---:|---:|---:|---:|
| Warm-up | 4 / 11 | 0.0362294 | 0.0362260 | 0.0093% |
| D1 | 3 / 7 | 0.00960325 | 0.00960283 | 0.0044% |
| D2 | 5 / 8 | 0.00912418 | 0.00912417 | less than 0.001% |
| D3 | **6 / 19** | **0.00570957** | **0.000656038** | **88.51%** |
| D4 | 4 / 8 | 0.000203244 | 0.000203238 | 0.0030% |
| Real D4 | 6 / 16 | 0.00836297 | 0.00834435 | 0.2227% |
| M11 | 7 / 22 | 0.0392098 | 0.0358026 | 8.69% |
| M15 | 4 / 18 | 0.0241021 | 0.0240192 | 0.3439% |

M19 and subsequent stages do not trigger this rule on the saved histories.
M19 removes 99.7% of its entry loss in four accepted iterations.

D3 is the counterexample to treating every flat segment as wasted work. Its
large improvement comes at iterations 12-14, after the proposed exit at 6.
Advancing early might still recover through later stages, but these records
cannot answer that: later stages would start from a different curve.

Sources: [slider stage records](../../../../../results/validation/cleaned_interfaces/GU-002/slider/runs/hook__c13.3),
especially `stage_3_damped.json`, `release_M11.json` and `release_M15.json`.
Saved cutoffs cannot be added up as a predicted iteration saving or speedup.

## Separate the two suspected mechanisms

The default currently has **no progress-based stage exit**. It uses strict
convergence tolerances, unsuccessful-search termination, stage iteration caps
and work limits. Calling this a strict stall rule would conflate two controls.

Every accepted M11 and M15 trial uses backtrack 0. Their LM damping decreases
throughout, ending near 1.05e-14 and 1.29e-12. Repeated halving or increasing
damping therefore does not explain these particular long tails.

D3 does use a halved proposal at iterations 1 and 5-11; the full trials have
higher loss. Its gradient grows during the slow patch. Removing backtracking
could accept harmful moves and is a separate question from leaving a stage.

Tiny proposals are skipped before trial construction and recording. Terminal
retries that construct no curve are therefore not fully represented by the
trial list. They do not call the forward solver.

Code: [C9-C12 loop](../../../../../solvers/bem_inverse/fit_stage.py),
[progress conditions](../../../../../solvers/bem_inverse/checks.py),
[policy](../../../../../solvers/bem_inverse/policy.py).
The existing progress condition is only enabled under the optional agreement
damping path. A stopping-only comparison must not silently enable that path.

## Proposed terminology

Keep the existing glossary distinction between an iteration, trial curve and
accepted curve. Here the progress window counts iterations that accepted a
curve; rejected trial curves do not advance that window.

Proposed **stage progress exit**: end the current stage because recent relative
loss decrease is small, retaining its current accepted curve for the next stage.
It is not convergence of the entire fit, or a failed physics solve.

Record that term in `GLOSSARY.md` once its meaning is agreed. The numerical
threshold and window belong in this proposal and the eventual policy, not in
the glossary. These choices are reversible; no ADR is needed at this point.

## First interview round: decisions still open

1. **Isolate stage stopping.** Recommendation: change only stage progress
   exits first. Keep geometry, K/M/Ku/F sequence, LM damping, backtracking,
   physics checks and recovery requirements unchanged.
2. **Where to apply it.** Recommendation: first apply the proposed rule only
   to full-real-catalog stages, M11 onward. Keep the earlier stages unchanged
   for this first candidate because D3 has a delayed improvement.
3. **Exact rule and action.** Recommendation: after at least two accepted
   iterations in the current stage, compare current loss with loss two
   accepted iterations earlier. If their combined relative decrease is below
   5%, advance to the next stage with the current accepted curve. Reset the
   window at every stage; never compare losses across stage boundaries.

Resolved by the user: implement the rule in every stage, rather than restricting
it to full-catalog stages. Keep other controls unchanged and run one GPU slider
hook c13.3 fit now. See the approved plan for the precise scope.

## Design branches to settle next

- If the full-catalog-only rule is chosen: decide the bounded hook comparison
  and what evidence would justify widening its stage or scene coverage.
- If all stages are chosen: explicitly accept the D3 trajectory change or
  choose a simple condition that protects its temporary slow patch.
- If damping/backtracking also changes: keep its effect distinguishable from
  stage exits, with a concrete hypothesis supported by the saved trial records.

Use measured fit time and physics work together with unchanged TG-002 recovery
requirements. Accepted iteration count alone is not the speed criterion.
