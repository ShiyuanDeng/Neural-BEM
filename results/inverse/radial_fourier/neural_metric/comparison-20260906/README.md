# Interpretation and replay notes

This predeclared comparison is negative evidence for the tested **frozen initial neural-feature metric**: all three seeds reconstruct both cases less accurately than the explicit identity and moderate Sobolev controls within the declared budgets. It is not a test of trained/adaptive neural metrics or direct optimization of an extracted neural zero set. No settings were changed and no benchmark was rerun after inspecting the outcomes.

See [summary.md](summary.md) for the full results, [metrics.json](metrics.json) for configuration, work, stopping and qualification details, [trajectories.csv](trajectories.csv) for accepted trajectories, and [arrays.npz](arrays.npz) for numeric observations, acquisition and metric arrays. This supplement was added after the measured run; those measured files were not edited.

## What completed, and what did not

The workflow completed in 360.63 seconds. Both explicit circle arms met the declared normalized loss tolerance of `1e-4`: identity after 15 accepted updates, Sobolev after 13. Their refined training relative errors were approximately 0.00391 and 0.00685. The three neural circle arms exhausted the 15-update allowance with relative errors 0.0675–0.1297.

All five star arms exhausted the 15-update allowance; **there is no fully converged star reconstruction here**. Identity/Sobolev training relative errors were approximately 0.278/0.308, compared with 0.461–0.558 for the neural seeds. These are bounded-progress comparisons, not final attainable errors.

Actual work is not identical on the circle: identity used 40 frequency-specific forward calls, Sobolev 30, and each neural seed 28. Every star arm used 28. The common cap was 160 calls total per run, not 160 per frequency, and no arm exhausted it. Adjoint, directional-assembly, setup and qualification costs are recorded separately. Timing is descriptive, not an equal-work speedup claim.

All ten arms passed the predeclared `1e-6` final training/held-out self-refinement tests. This establishes numerical resolution of their reported predictions, not successful reconstruction: an inaccurate shape can have a well-resolved forward solution. Held-out errors did not select any setting. Losses before and after the frequency-stage switch are different objectives.

## What the neural metric actually contributed

The geometric-circle initialization has 5,441 parameters, but its zero output head leaves only 65 active parameter-Jacobian columns. The model was queried only to construct the initial metric; it was neither trained nor queried during reconstruction. All accepted states remained explicit gauge-fixed K5 radial Fourier curves, with the same true Kress objective and derivative contract.

The normalized mass-whitened neural metric condition numbers were about 439–943, compared with 4.06 for the declared Sobolev control and 1 for identity. Projecting the initial neural normal map into the shared 11-dimensional chart left 15.6–16.6% arc-weighted relative projection residual. That is a linear chart-projection diagnostic, not measured nonlinear weight-to-extracted-curve transfer error.

Consequently, this experiment neither establishes an advantage for signed-distance values nor excludes a useful learned metric. The tested moderate Sobolev control is not spectrally matched to the neural metrics; a neural-specific coupling claim would require that additional control. The fixed star-shaped chart cannot test topology changes or unrestricted neural expressivity.

In trajectory records, `gradient_norm` is the **pre-step** current-geometry mass-dual covector norm, while that row's coefficients and loss are **post-step**. It must not be read as a final-state stationarity measurement. Successful stopping in this run used the loss criterion; budget exits were not labeled convergence.

## Replay and post-run source audit

Observation arrays were made read-only in memory and saved, together with training/held-out acquisition arrays, before reconstruction. Completed-arm checkpoints include initial/final and accepted-step coefficients. Numeric initial normal bases, arc weights, mass matrices, neural feature covariances and active coefficient/whitened metric matrices are saved in `arrays.npz`. Seeds, model architecture, physical constants, stage schedules, limits, tolerances and the invocation are recorded in `metrics.json`. No object-pickle loading is needed for these arrays.

At **2026-09-06 00:31:03 UTC**, after completion, all **60** source paths listed in the measured manifest's `provenance.source_sha256` were rehashed against the current workspace. **All 60 matched; no missing or changed paths were found.** This was a post-run audit, not a continuous during-run hash check. The manifest explicitly limits inverse-module hashing to the used modules; unrelated concurrent inverse experiments are outside that hash scope. The invocation and provenance support replay, but bitwise equality across different numerical-library/hardware environments is not promised.
