# Phase A: matched five-parameter star controls

Commit: `838bedf4eb37beb3c01ae770958e6c92f2abdf04`. The source hashes and working-tree state at launch are in `provenance.json`.

Both arms use the existing analytic wrong star, target and materials from `run_sdf_inverse_comparison.py`. Paired readout observes receiver row i only for source row i; there are respectively 12/12 and 8/8 sources/receivers on a 0.30 m ring with the existing Tx/Rx offset. Independent Nystrom observations use 512 nodes. Training is {0.5,1.5} GHz. The common holdout is {3.0} GHz only: 0.25 GHz is excluded because the planned frequency audit probes it. Each arm verifies 512/1024-node oracle self-convergence at 3 GHz against 1e-8 before proceeding.

Both use the historical analytic-control Method-B settings unchanged: 128 Kress nodes, Fourier bandwidth 48, 257 x 257 extraction grid, 128 projected samples, arc-length dense resolution 2048, validation resolution 1024. These are the analytic-control settings, distinct from the neural bandwidth-96 study. Maximum boundary error below is the existing maximum **node-to-exact-target** distance; it is a sampled one-direction metric, not a continuous Hausdorff certificate.

The optimizer is the existing bounded central-FD damped Gauss-Newton implementation, with the same 14-update maximum, 6 damping trials, 8 backtracks, steps and stopping tolerances in both arms. No optimizer implementation or tolerance is changed. Its post-repair truthful `no_decreasing_step` stopping label can differ from the historical falsely converged small-rejected-step label. Recovery and optimizer termination are reported separately.

| Acquisition | Train rel. L2 | Holdout rel. L2 | Max boundary (mm) | Amplitude error | Rotation error (rad) | Accepted / rejected | Inverse forwards | Inverse seconds | Stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| paired-12 | 5.881e-06 | 2.064e-04 | 0.03869 | 5.427e-06 | 1.352e-07 | 10 / 0 | 121 | 75.53 | no_decreasing_step |
| paired-8 | 5.433e-06 | 1.978e-04 | 0.03870 | 5.825e-06 | 5.296e-07 | 13 / 0 | 154 | 95.81 | no_decreasing_step |

`trajectory.csv` in each arm reports every accepted iterate, physical errors, training/holdout performance, cumulative accepted/rejected trials, forward evaluations and elapsed inverse wall time. `trials.csv` records every evaluated line-search candidate and rejection reason. Finite-difference probes and restoration cache hits are not mislabeled as rejected trials. Holdout is evaluated only in a separate pass after training finishes; its forwards and wall time are reported separately. Skipped proposals below the existing relative-step floor do not execute a forward and are not included in evaluated trial counts. Rejection counts by reason: {"paired-12": {}, "paired-8": {}}.

Recovery gates retain the historical geometry/holdout allowances (center 0.5 mm, radius and node boundary error 1 mm, amplitude/rotation 0.02, holdout relative L2 1e-3), plus train relative L2 1e-3. Outcomes: {"paired-12": true, "paired-8": true}.

Eight paired views recover the star inside its five-parameter family at 0.5/1.5 GHz. Reducing 12 to 8 pairs does not explain the neural failure by itself. Physical and general-boundary modal observability remain necessary before claiming sufficiency for the neural inverse.

This does not establish sufficiency for arbitrary neural boundaries, explain the neural basin, or select the acquisition for a full neural run. The 3 GHz holdout is never used for tuning, line search or frequency/acquisition selection. Timings are single-run engineering measurements. `matched_trajectories.png` shows amplitude, phase and boundary error through the two accepted trajectories.

Reproduce with the exact command in `commands.txt` from the repository root.

Validation: **15 focused tests passed**, including an independent regression that checks instrumentation preserves the optimization path and forward/cache counts while separating actual rejected trials from FD probes and accepted-state restoration. Artifact consistency, matched settings, holdout reservation, and `git diff --check` also passed. To rerun into this existing bundle, append `--overwrite`; alternatively choose a fresh `--output-dir`.
