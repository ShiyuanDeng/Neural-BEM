# Sampling and frequency-path controls

This isolated experiment follows ranked tasks 5–6 in the October 2 exploratory
document. It reuses the existing topology derivative, scene loader, endpoint
gates, SC coupled Fourier geometry, normal updates, and LM fitter. It changes
no production defaults. Results, including unsuccessful initializations,
numerical stops and resource limits, live in `results/exploratory_continuation`.

## Contracts discovered before implementation

The frozen twelve-scene specification has **one training frequency, 0.5 GHz**.
Its 1.5 and 2.5 GHz measurements are held out. The acquisition consists of
24 paired transmitter/receiver observations per frequency. It does not contain
the 576 entries of a 24-by-24 multistatic matrix.

These facts impose two restrictions:

1. The diagonal sampling map from a complex 24-by-24 matrix to its 24 paired
   entries has a kernel of dimension 552. Its missing off-diagonal entries
   cannot be reconstructed by reshaping or zero-filling the observed vector.
   Ordinary LSM therefore has no eligible frozen-data arm here. The code
   explicitly reports `UNSUPPORTED_PAIRED_ACQUISITION` for all twelve scenes.
   A separate full-ring, full-matrix dielectric-disk control exercises LSM.
2. A frequency path on a singleton training-frequency set has only one index.
   Ascending continuation and SCIF's first-hit path both reduce to `[0]`.
   An informative frequency-path comparison requires additional training
   observations. This experiment declares an extended acquisition at
   0.25, 0.375, 0.5, 0.75 and 1 GHz, and keeps both original holdout frequencies
   outside fitting and path selection. The archived 0.5 GHz data are reused
   exactly after a source/units/material agreement check. Added observations
   are generated at 256 nodes and checked at 128 nodes.

## Relationship to existing SC and MA

The maintained cumulative inverse is `experiments/cleaned_interface`; the
SC/MA reconciliation is in `docs/pipelines/shape_frequency_continuation.md`.
SC already supports frequency revisits, separate state/update bands, point
sources, and coupled fixed-count components. MA-005 adds damped observations,
localization and a measured-frontier tail. Those results use different cases
and measurement contracts and are not comparable pass counts for this suite.

Here `sc_fixed_band` is a deliberately small **SC backend control**: ascending
frequencies with M=5. It is not a reproduction or evaluation of the complete
cleaned cumulative policy, SC-050, or MA-005 DF. The RLA and SCIF arms share
that same fitter and geometry machinery, so the experiment isolates the
frequency path and normal-update band rule. Every arm has fixed topology from
the same data-only initializer; none is allowed the target component count.

## Algorithms and primary sources

The empty-domain initializer calls the repository's existing
`evaluate_current_domain_topological_derivative(None, ...)`. For the outgoing
Green function `G=i H0^(1)(kr)/4`, an infinitesimal equal-density dielectric
disk has response per area `(ki²-ke²) u_inc(z) G(receiver,z)`. For
`J=||prediction-data||²/2`, its derivative is the real inner product with the
residual. The implementation also preserves the existing objective's frequency
weights and column scales. Negative derivative regions are thresholded at
60% of their maximum improvement; connected components produce area-equivalent
circles with fixed radius bounds. This follows the topological sensitivity
approach in [Carpio, Pena and Rapún, 2025, §§3–4](https://arxiv.org/html/2501.15327v1).
A shrinking-disk test verifies sign, source strength and area scaling directly
against the transmission solver. Image thresholds are heuristics, not a
certificate of object count or boundary accuracy.

LSM solves `N g_z ≈ phi_z` using the SVD and Tikhonov regularization, with
indicator `1/||g_z||`. The numerical control selects each parameter to make
`||N g_z-phi_z||/||phi_z||=0.01` and records unattainable discrepancies.
This is a **right-hand-side discrepancy target**, not an estimate of noise in
the measured operator. Quadrature weights are explicit. See
[Garnier, Haddar and Montanelli, 2023](https://arxiv.org/abs/2210.15560) for
near-field sampling, SVD regularization and discrepancy selection. The present
control is an adaptation to penetrable TM data; it does not establish the
theoretical guarantees of their sound-soft formulation.

The RLA controls ascend through the frequencies and use
`M=max(1,ceil(c k R_init))`, for c=0.5, 1 and 1.5. `R_init` is the largest seed
radius, without truth information. Curve storage remains K=24 and does not
shrink when M falls. Recursive frequency warm starts and band limitation follow
the boundary-inversion structure already implemented from
[Borges, Rachh and Greengard, 2023](https://arxiv.org/abs/2210.11607).

SCIF uses the actual rule in
[Askham, Borges, Hoskins and Rachh, arXiv v1, §3](https://arxiv.org/pdf/2308.00559):
start at index zero; step up with probability p, otherwise move to
`max(0,index-1)`; stop at the first arrival at the highest index. Thus a downward
draw at zero repeats zero. Here p=0.603 and seeds 0–7 are fixed across all
scenes. The operational path cap is 32 visits; capped paths are incomplete,
never patched with an ascending suffix. Each visit allows two LM updates and
each path has a 160-unit work cap. This is a bounded adaptation to penetrable
transmission; the source studies sound-soft obstacles and longer optimizations.
Best-of-eight selection uses only the five-frequency training residual, and
all eight runs are charged to its work and wall totals.

## Running

Use the repository Python environment with NumPy, SciPy, pytest and scikit-image.
The recorded run used `/home/drdeng/miniconda3/envs/EMNerf/bin/python`.

```bash
export PYTHONPATH=solvers:.
python -m pytest -q experiments/exploratory_continuation/test_controls.py
python -m experiments.exploratory_continuation.run initializers
python -m experiments.exploratory_continuation.lsm_control
python -m experiments.exploratory_continuation.campaign controller --workers 2 --timeout 120
python -m experiments.exploratory_continuation.campaign controller_guarded --workers 2 --timeout 180
python -m experiments.exploratory_continuation.campaign controller_full --workers 4 --timeout 600
python -m experiments.exploratory_continuation.run prepare-frequencies
python -m experiments.exploratory_continuation.campaign continuation --workers 2 --timeout 150
python -m experiments.exploratory_continuation.retry_caps
python -m experiments.exploratory_continuation.resolution_diagnostic
python -m experiments.exploratory_continuation.report
```

The first two controller pilots preserve all twelve scenes, archived observations and endpoint
gates, but use a smaller shared budget: two cycles, six fixed
iterations, two candidate refinement iterations, and twelve candidates per
type. Therefore they are a matched **bounded pilot**, not a rerun of the
original frozen-budget campaign. A failed controller can consume work before
its final ledger is returned; missing counters are flagged, and known counts
are lower bounds. Process wall time is retained for those failures. Shared CPU
load means elapsed times are descriptive and not controlled speed comparisons.

The `controller_full` campaign subsequently runs both initialization arms with
the **original frozen numerical budgets**: ten cycles, 22 fixed iterations,
three candidate refinement iterations and 48 candidates per type. Both arms
use existing policy H, which guards feasibility at the refined resolution and
uses feasible finite-difference directions. Its 600-second per-job cap is the
original benchmark's declared cap. Last accepted-state and work checkpoints
are saved throughout. Original A-policy failures and the bounded H pilot are
retained separately; guarded full-budget results are the primary initializer
comparison.

The initial SCIF 160-unit pilot and its complete 96-path denominator are retained.
The supplemental 512-unit analysis replays the 16 purely work-capped paths and
explicitly reuses the other 80 deterministic endpoints, with input hashes and
a check of unchanged core source hashes. It reports both the effective cost
of the 96 paths and the actual original-plus-replay cost. The seven numerical
merge-scene failures are separately replayed at N64/128, 128/256 and, where
necessary, 256/512. These resolution diagnostics are not substituted into the
primary comparison. `path_completion_audit.json` documents a corrected
reporting bug: attempting the final frequency visit does not count as a
completed optimization path when that visit hard-stops.
