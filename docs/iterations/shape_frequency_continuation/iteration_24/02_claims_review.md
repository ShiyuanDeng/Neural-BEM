# Reviewer constraints on the strategy claims

2026-09-26. Written during SC-042/043/044, before their complete outcomes.
This is an owner assessment; no independent reviewer has been assigned.

The current experiments must establish a useful decision rule, not merely a
plausible explanation of selected trajectories. Simple alternatives receive
the same allowance; diagnostic work and failed paths remain visible.

## Prior work that directly limits novelty

[Borges–Greengard (2014 preprint / 2015 publication), §3.1](https://arxiv.org/html/1408.5436v1#S3.SS1)
already combines band-limited normal perturbations, damping for valid curves,
and filtering of the updated boundary followed by arclength resampling. The
filter has a smooth spectral roll-off, with parameters reported in the
examples. Therefore normal-update restriction, state filtering and their
combination are established ingredients. Our hard Cartesian cutoff is not
an exact implementation of that baseline; success against an unfiltered
control would not establish superiority over their method.

[Borges–Rachh–Greengard (2022), §2.1](https://arxiv.org/html/2210.11607v1#S2.SS1)
uses separate normal perturbations and arclength Fourier states, increases
complexity with frequency, and restricts admissible curvature-spectrum
energy. This is especially close prior work for the penetrable-object
problem. Our acquisition and numerical formulation differ, but those
differences do not make band-limited continuation or curvature control new.

[The temporal domain derivative in inverse acoustic obstacle scattering
(2025), §5.1](https://link.springer.com/article/10.1007/s00211-025-01481-8)
also explicitly uses an integrated squared-curvature penalty in a
Gauss–Newton reconstruction. It addresses a different formulation; it is
evidence against a broad claim that curvature regularization itself is new,
not an interchangeable experimental comparator.

[Askham–Borges–Hoskins–Rachh (2023)](https://arxiv.org/abs/2308.00559)
already studies cavity failures and random walks in frequency for sound-soft
obstacles. Its authors report partial robustness gains and persistent hard
cases. Thus nonmonotone continuation and cavity sensitivity are also prior
art; a future frequency policy needs a closer comparison than a monotone
schedule alone. The physics differs from this penetrable-object campaign.

A focused update search on 2026-09-26 also checked the primary record of
[Tsang et al. (December 2025)](https://arxiv.org/abs/2512.10123), which combines
a differentiable forward model with learned inverse-medium reconstruction
and increasing-frequency refinement. It is broader context if the project
returns to neural geometry, rather than a matched comparator for the present
classical boundary policy. This search is not an exhaustive priority review.

## What the present work can honestly claim

| Proposed claim | Current defensible scope | Evidence still required |
|---|---|---|
| Low normal-update bandwidth does not cap accumulated state complexity | Mechanism and measured failure in this implementation; multiplication by the normal and nonlinear refitting explain why | Do not claim first discovery; isolate cleanup, recurrent filtering and tangent-space changes |
| Differentiate the actual projected update | Qualified implementation consistency, supported by full-construction finite differences | A general mathematical novelty claim needs more than the chain rule and numerical agreement |
| Physical-metric action prediction | Coordinate-invariant constrained least squares, a standard mathematical building block applied here | Prospective choices must outperform fixed and stagnation controls after paying for qualification |
| High-band content is unrecoverable | Unsupported from a truncated atlas or a small residual alone | Acquisition-specific, noise-scaled sensitivity and stability tests; separate uncomputed modes from measured null directions |
| A small data residual proves the right shape | Unsupported; geometry, numerical validity and data fit measure different properties | Last-returned-state geometry on known truths, independent noise draws, and eventually model mismatch |
| A general robust continuation method | Not established by development suffixes | Complete reconstructions on fixed fresh cases, noise, comparable failures, costs, and stronger established baselines |

SC-042 asks whether a simple repair explains the apparent strategy benefit.
SC-043 asks whether the diagnostic earns its overhead against two cheap
policies. SC-044 asks whether state treatments transfer to a full pipeline
on two fixed new shapes with paired noise. A negative result narrows the
claim; it does not license retrospectively changing a threshold or removing
a difficult target.

The most useful next iteration depends on which obstruction survives. If
cheap schedules tie the diagnostic, improve or drop the decision rule. If
numerical resolution fails while shape error falls, isolate discretization
adaptation from geometry regularization. If noisy reconstructions reach the
discrepancy while geometry remains poor, investigate stability and data
coverage before extending the noiseless fitting ladder. None of those
outcomes alone establishes an information-theoretic limit.

Post-fit feature clarification during SC-043: the star's 5.1136 mm truth
minimum radius is at a concave valley; its convex tips have radius 10.4167
mm. Earlier text used the global minimum as evidence of blunt tips. That
inference is not justified by the statistic. The numerical values are
unchanged, and the current regularity reports localize all five tips
separately. Local feature preservation must be tested at matched features,
not inferred from a global curvature extremum at an unspecified location.

## Final outcome addendum

The campaign is complete. SC-042 supports one-off repair on development
starts; recurrent restrictions add little there. SC-044 shows selective
stabilization on one noisy C trajectory, with residual local artifacts.
SC-043 completes all 18 paths and audits but fails its controller gate:
RMS geometric-mean ratios 1.11301 versus fixed and 1.00512 versus stagnation.
Its kite error is 88%/68% worse, and all 36 low/high radius constraints are
inactive. The qualified diagnostic has not earned decision superiority.

Retain the mechanism findings and simple regularization baselines. The
next diagnostic hypothesis must concern accepted finite progress and total
cost, with untouched full-pipeline/noise evaluation. The current results do
not establish adaptive frequency selection or an observability limit.
[Complete policy results and integrated reviewer decision](../iteration_26/01_results.md).
