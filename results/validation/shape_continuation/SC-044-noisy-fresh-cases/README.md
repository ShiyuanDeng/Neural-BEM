# SC-044 — full reconstructions on two fixed fresh shapes with noise

**COMPLETE, 2026-09-26: all six prefixes and 18 suffix paths returned.**
[Frozen contract](plan.md), [source/input hashes](manifest.json),
[available outcome table](TABLES.md), [fixed target outlines](targets.svg).

Stage-boundary cleanup and the permanent cap have essentially tied RMS
geometry. Their six-dataset geometric-mean ratios against none are 0.87318
and 0.87250; common-work ratios are 0.90889 and 0.90839. The original frozen
transfer gates remain false because two audits timed out. Those endpoints
now pass separate SC-045 qualifications; original flags are unchanged.

The lobed shape is a meaningful tie under all three data profiles. On the
deeper C, the unchanged first-noise path hits its field refinement gate at
M19, before reaching discrepancy. Both treatments avoid that stop and reach
about 0.158 mm RMS. At the common 380-unit suffix allowance, boundary cleanup
already improves RMS from 0.3535 to 0.2010 mm. It reaches 0.1580 with 456
units. This is a benefit beyond extra work, but it is one failure avoided on
one draw of one target.

Local geometry adds a separate distinction. For the clean C, none/boundary/
cap Hausdorff estimates are 0.4820/0.3846/0.3877 mm; under the second noise
draw they are 0.7030/0.6263/0.5765 mm. RMS differs by less than 1% in those
comparisons. Spurious curvature remains: the clean unfiltered minimum radius
is 0.835 mm and cleanup gives 2.268 mm, versus a true minimum of 9.645 mm.
State restrictions mitigate this artifact without eliminating it.

[Final geometry](geometry.pdf), [clean-C artifact detail](cavity_feature.pdf),
[post-fit feature measurements](../strategy_feature_errors.json) and the
[closeout](../../../../docs/iterations/shape_frequency_continuation/iteration_25/01_results.md)
provide the full interpretation. All 107 saved-evidence checks pass. Unique
fitting work is 10,924 units, original prefix/suffix audits 2,169, and data
generation 76: **13,169 measured units**, excluding separately recorded
SC-045/046 follow-ups.

The two targets were fixed before observations or inverse fits: an asymmetric
lobed outline and a deeper C-shaped domain. Each has clean observations and
two paired draws of 1% relative complex-RMS Gaussian noise. The 2048-node
data passed comparison with 1024 nodes: maximum relative discrepancies
5.91e-15 and 8.79e-15 respectively, below the 1e-8 gate. Data generation
cost 76 frequency fields. All observations and noise standard deviations
are committed JSON and sealed in the manifest.

Each dataset starts from the same circle and follows a common four-stage
prefix. Qualified prefixes feed three state strategies: unchanged,
stage-boundary cleanup and a permanent K64 cap. Each complete path is
charged its prefix even though the common prefix is computed once. Failed
prefixes block their suffixes and stay in the denominator. Noise stopping
uses the declared variance and a 1.1-squared discrepancy factor; truth never
chooses the iterate, cutoff or stopping time.

All six prefix paths completed their schedules and passed their field,
Jacobian and full-trial derivative audits. Their unique fitting work is
1,766 units. Prefix audits use each prefix's final four-frequency objective;
the suffix and its endpoint audit use all 19 frequencies.

The lobed clean/cap and noise-seed-0/boundary endpoint audits timed out during
severe host memory pressure. Their original failures remain; separate
[SC-045 qualifications](../SC-045-timeout-qualification/README.md) reuse the
exact returned shapes and unchanged audit settings, with additional cost.

This is two distinct target shapes with repeated noise draws, not six
independent targets. The same two seeds are used for both shapes, so their
standardized noise patterns are shared across targets as well as methods;
frequency-dependent amplitudes follow each target's signal norm. The
observations share the governing model with the
inverse. The study tests transfer to new shapes and measurement noise;
material, calibration and experimental model mismatch remain untested.

From the repository root, sequentially:

```bash
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-044-noisy-fresh-cases/run.py generate --workers 2
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-044-noisy-fresh-cases/run.py prefix --workers 2
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-044-noisy-fresh-cases/run.py suffix --workers 2
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-044-noisy-fresh-cases/analyse.py
```

This sequence has terminated. Existing run directories are preserved
rather than overwritten; do not duplicate completed paths.
Report figures can be rebuilt without solves using
`results/validation/shape_continuation/strategy_campaign_figures.py`.
