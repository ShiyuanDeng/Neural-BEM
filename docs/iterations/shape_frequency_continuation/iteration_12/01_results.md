# Iteration 12 — testing the atlas strategies (SC-029)

2026-09-24. Owner: Codex. Independent reviewer: unassigned.
**Execution: IN PROGRESS.** The twelve four-stage paths have completed;
the twenty-four frozen suffix comparisons are next.

The [plan](../iteration_11/03_plan.md) follows the independently audited
SC-026 atlas and preserves SC-028's failed P=48 preflight. SC-029 is
qualified only for the inverse's actual update bands, M<=19, at the
unchanged N=512/1024 and 1e-6 derivative-refinement tolerance.

## First milestone

All six baseline curves reproduce SC-025 bitwise with identical work.
All twelve four-stage arms finish normally. The
[prefix report](../../../../results/validation/shape_continuation/SC-029-atlas-strategies/PREFIX_RESULTS.md)
shows that M=2 in stage 1 improves C (3.20 to 0.35 mm RMS) and peanut
(2.94 to 0.13 mm), but worsens kite (2.98 to 5.54 mm) and hook
(0.53 to 4.99 mm). It fails the frozen worst-case guardrail and cannot
be recommended as a universal replacement for the original ladder.

The two suffixes will separate higher-frequency data from additional
iterations and wider update bands, using identical saved prefix states.
Those results are pending. All six cases remain development data.

## Atlas interpretation

The [supplemental sensitivity analysis](../../../../results/validation/shape_continuation/SC-026-independent-audit/README.md)
uses the actual four/nine training-frequency sets and keeps only high
normal-ray coverage and low misalignment. It preserves the motivation for
the frequency test on the 57 near-converged states, while retaining the
limits of a truth-assisted projection under assumed normalized-component
noise. It does not choose an optimizer update or establish recoverability.
