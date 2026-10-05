# Agreed inverse continuation schedule

2026-10-05. Status: **agreed design, documented for implementation**.
This records the user's four-phase schedule and correction:
**"frequency ladder stays as it is now."** This documentation change does
not change the executable policy or launch an experiment.

## Schedule

| Phase | Data | Updates and bandwidth |
|---|---|---|
| 1. Position and size | Lowest frequency used for initialization | Exact translation and uniform scaling only. Starting from a circle, fit its centre x, centre y and radius; preserve its circular shape. |
| 2. Existing frequency ladder | Existing cumulative four-frequency ladder | Preserve its current frequency sequence, damping transitions, and **current M/K progression**. |
| 3. Additional shape ladder | All configured fitting frequencies at every stage | **Four additional stages** that continue increasing M and K from the frequency ladder's endpoint. The frequency set stays fixed throughout these four stages. |
| 4. Full release | All configured fitting frequencies | Release the full configured, validated M/K bandwidth, retaining the validity, numerical-accuracy and stopping checks. |

Carry the accepted boundary forward between phases. Phase 3 continues from
the M/K reached by phase 2; it does not restart the shape-order ladder.
The four new stages release shape detail, rather than introduce four more
physical frequencies. "All frequencies" means the complete fitting catalog
for the run: four in the case-8 panel, potentially more in the maintained
benchmark policy.

The earlier assistant suggestion to hold phase 2 at M=3 was rejected.
Its associated illustrative M=5/7/11/15 ladder is not an agreed set of
post-prefix levels. Preserve the user's existing frequency ladder instead.

## What is preserved in the existing frequency ladder

The current implementation is
[`CumulativePolicy.operations`](../../../solvers/bem_inverse/policy.py).
Its default prefix is cumulative 0.5, 0.75, 1.0 and 1.25 GHz. Each prefix
stage computes:

```text
M = floor(3 * max(real(k_exterior)))
K_geometry = 2*M + 2
```

Here the wavenumbers are those in the actual configured observations and
their package units. Preserve this computation; do not replace it with
fixed low-M stages or transplant case-8 M values into another unit system.
The maintained policy uses the damped prefix and then an explicit return
to the corresponding real-frequency objective. Preserve that existing
transition as part of the frequency-ladder behavior. This decision does
not enable grid-search localization; the maintained benchmark default
remains `--localization none`.

The existing policy's earlier warm-up and later release/fixed/frontier
operations are implementation context, not additional phases to append
automatically to the agreed four-phase design. Their exact integration
with the new restricted initialization and four-stage shape ladder must
be made explicit in the implementation plan.

## M, geometry K, and physics resolution

- **M:** normal shape-update Fourier band.
- **K_geometry:** Cartesian Fourier band storing the boundary. This is
  the K that grows with M in the shape ladder.
- **K_trace:** internal field-solver modal cutoff. The case-8 production
  and refined checks used 64 and 96. These are two numerical accuracies
  at the same physical frequency, separate from the shape coefficients.

"Full release" means full configured bandwidth, not removal of step
bounds, geometry validity or numerical-accuracy checks. Preserve the
noise-based stopping rules: an accepted full-catalog endpoint that meets
the required discrepancy and audits can finish without traversing every
remaining release stage. Reaching a target on a frequency subset permits
continuation to the next data stage; it does not establish full-catalog
success. Work limits and numerical failures remain distinct from convergence.

## Evidence and implementation details still to set

[GGB-004](GGB-004_results.md) showed that a separate translation-and-radius
stage avoids the protrusions seen with interleaved shape updates: its
four-frequency circle fit settled in 3.70 s. [GGB-005](GGB-005_results.md)
reached the 0.5 GHz fitted noise target in 1.32 s, with 0.103 mm centre error
and an exact match on the original pixel grid. Both stopped before ordinary
shape continuation. These runs support the restricted initial stage on
case 8; they do not validate the complete proposed schedule or other scenes.

The exact four added M/K levels, per-stage budgets, and final configured
maximum have not been selected in this discussion. They must continue
upward from the actual existing ladder endpoint. Specify their increasing
geometry-storage K levels explicitly; the current prefix uses K=2*M+2,
whereas the current later releases use fixed storage, so neither rule is
silently selected here for the new ladder. The lowest-frequency data choice
and treatment of the current warm-up must also be specified for the
target catalog; the case-8 evidence used real 0.5 GHz, while the maintained
policy has a 0.25 GHz damped warm-up. Record those concrete settings in the
implementation/experiment plan before running a validation campaign.
