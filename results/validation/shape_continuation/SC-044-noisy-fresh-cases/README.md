# SC-044 — full reconstructions on two fixed fresh shapes with noise

**RUNNING, 2026-09-26.** Data and all six prefixes qualified; suffixes running.
[Frozen contract](plan.md), [source/input hashes](manifest.json),
[available outcome table](TABLES.md), [fixed target outlines](targets.svg).

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

The current host is executing this sequence; do not duplicate it while
active. Existing run directories are preserved rather than overwritten.
Report figures can be rebuilt without solves using
`results/validation/shape_continuation/strategy_campaign_figures.py`.
