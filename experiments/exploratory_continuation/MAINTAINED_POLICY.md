# Maintained cumulative-policy comparison

**Closed by explicit user scope change.** The full campaign was not completed; no more work is scheduled. The retained contribution is the independently validated cleaned-interface audit memory fix. See the [closure report](../../results/exploratory_continuation/maintained_policy/README.md). The design and commands below document archived attempts.

This supplement addresses the missing task-6 comparison against the maintained
SC/MA strategy. The earlier `sc_fixed_band` control remains a small SC-backend
control and is never relabeled as the maintained strategy.

## What executes

The experiment calls `experiments.cleaned_interface.runner.fit` and obtains its
operations directly from `CumulativePolicy.operations`. It retains the actual
warmup, cumulative frequency prefixes, real-frequency handoff, shape-band
releases, Cartesian cleanup, observable-frontier measurement, adaptive tail,
LM implementation, complete `ProjectedUpdate` derivative, quotas, and independent
initial/final numerical audits. A focused regression compares every fit stage
and optimizer to the maintained policy with the same declared inputs.

The default fitting budget is 13,412 work units and 1,800 seconds. Independent
initial/final audits each have the maintained 300-second allowance. Production
and refined quadrature are N512/1024 per component. The policy uses 44 warmup
iterations and 22 iterations at each later stage; no two-iteration substitute is
used. CPU work counts are retained both in the LM ledger and in the physics
service's actual dispatch receipts. Every requested configuration runs, including
duplicate underlying observations; failed work is not omitted.

## Necessary input adaptations

The frozen default is a **single-object** problem with matched real and
`k(1+0.25i)` observations and a frequency prefix ending at 1.25 GHz. The twelve
topology cases have one to four TD seed components, 24 paired measurements,
and the qualified real catalog 0.25, 0.375, 0.5, 0.75, 1 GHz. Thus an unmodified
default invocation would reject these inputs or replace multiple seeds with one
Mie-localized circle. We make the following explicit adaptations:

1. Each component uses the maintained complete `ProjectedUpdate`. `MultiUpdate`
   composes them and the existing multi-component Müller system couples all
   components in every forward and reciprocal solve. Count stays fixed.
2. The common TD circles replace single-circle Mie localization. Their numerical
   audit still runs before optimization. No truth or heldout observations are
   available to the policy or its initializer.
3. The configurable four-frequency prefix is 0.375, 0.5, 0.75, 1 GHz. The separate
   warmup remains at 0.25 GHz. The 1.5/2.5 GHz observations remain held out.
4. The coupled frontier uses the direct sum of the per-component arclength
   `L2(ds)`-orthonormal normal bases. The common release band is the largest
   harmonic whose paired column norm exceeds 1% of the global paired-column
   maximum. Its solve and reciprocal batch are charged as in the maintained
   single-object frontier.

The runner's optional geometry/localization hooks preserve its default behavior.
The `Problem` contract now accepts an explicit nonnegative `damping_ratio`, with
the original default 0.25 and unchanged strict matching of paired catalogs.
No hidden observation synthesis occurs inside fitting.

## Two information contracts

- **Real cumulative arm:** `damping_ratio=0`, with the damped-catalog position
  explicitly aliased to the same real observations. Mathematically this is the
  zero-damping limit of the same Helmholtz equation and objective. It retains
  cumulative SC operations but makes no claim of MA damping benefit. Its input
  information and TD start match the earlier RLA/SCIF experiments.
- **Damped cumulative arm:** five additional synthetic complex-frequency
  observations at `k(1+0.25i)`, independently qualified at N256/512 with the
  maintained frequency-dependent tolerances. These are **additional data**, not
  quantities inferred from the five real measurements. Their generation cost
  is separately charged. Results cannot establish equal-information superiority
  over real-only RLA/SCIF.

The earlier RLA/SCIF controls used K24, N64/128, Borges updates, two LM iterations
per visit and smaller work caps. Their outcomes may be compared descriptively
under equal real-data/initialization contracts; they do not provide a controlled
compute-, discretization-, or update-matched superiority test. Every report must
show this limitation and the settings, instead of silently treating those arms
as the same experiment.

## Evaluation and retained evidence

The policy has no access to scene truth or heldout data. After it returns, the
original geometry, 0.5 GHz training and 1.5/2.5 GHz holdout gates are evaluated
with at least 512 nodes, sufficient to represent the maintained K192 geometry.
An all-gate qualified pass requires completion of the actual schedule, passing
both independent numerical audits and the original endpoint gates. Time/work
limits and numerical failures remain in the denominator even if a partial
endpoint happens to pass a geometry threshold.

`results/exploratory_continuation/maintained_policy/` preserves full plans,
configuration records, accepted states, rejected trial diagnostics, stage
histories, decision logs, unscored endpoints, audits, work receipts, qualification
arrays and post-fit evaluation. The earlier experiment artifacts are unchanged.

Commands (with the EMNerf Python environment and `PYTHONPATH=solvers:.`):

```bash
python -m pytest experiments/exploratory_continuation/test_maintained_adapter.py experiments/cleaned_interface/test_interface.py -q
python -m experiments.exploratory_continuation.maintained_run campaign --arm real --workers 3
python -m experiments.exploratory_continuation.maintained_run prepare --workers 2
python -m experiments.exploratory_continuation.maintained_run campaign --arm damped --workers 3
```

For maintained-policy provenance and the derivation of the complete projected
trial, see [the maintained pipeline](../../docs/pipelines/shape_frequency_continuation.md),
[the maintained interface](../cleaned_interface/README.md), and
[the experiment's primary-literature record](README.md). This is an explicitly
adapted coupled execution, not a frozen-default reproduction.
