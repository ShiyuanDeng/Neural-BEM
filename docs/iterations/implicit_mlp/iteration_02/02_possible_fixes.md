# Iteration 02 — possible fixes before consulting ChatGPT

Prepared from the September 8 suite and prior bounded diagnostics. These are
Codex's candidate actions for consultation, not a received ChatGPT guide or
an agreed implementation. The [results report](01_results_and_diagnosis.md)
contains the complete measurements.

## Evidence that constrains the options

Circle reaches 60 updates with 1.069 mm boundary error despite accurate placement.
Star stops after 47 updates at 37.368 mm error; its fitted amplitude collapses
from about 0.120 to 0.021 against the 0.25 target. Its final refinement change
is 0.00998257 mm, close to the 0.010 mm limit, and both deepest search directions
fail that check. Ellipse exits before saving a bundle or traceback.

The exact-target fit is much better than the inverse: about 0.284 mm for circle
and 1.191 mm for star. Earlier physical/modal studies find the original star
band locally informative; multistatic readout improves conditioning without
proving full neural sufficiency. Circle and star consume about 128 minutes of
recorded inverse time, so each new long run needs a discriminating purpose.

## Ranked candidate actions

| Priority | Candidate | Evidence and cheapest useful check | What would justify a fix |
|---|---|---|---|
| 1 | Capture and validate ellipse initialization before inversion | The old archived initial weights fail the new geometry at 3.212 mm distance and 0.0740 mm refinement change; the failed run's fresh weights and traceback are missing | Reproduce and save the actual startup failure, then demonstrate a topology-valid, resolved initialization under unchanged tolerances |
| 2 | Audit the final star's conversion and search locally | All 30 terminal candidates fail; 29 fail before data evaluation; the accepted state is near the refinement-change limit | Frozen-weight tests separate audit sampling/branch sensitivity from actual raw/converted discrepancy and find a meaningful admissible movement |
| 3 | Profile candidate evaluation before increasing resolution | Circle needs 423 and star 420 attempted evaluations | Measured extraction, audit, conversion and BEM timings identify a costly repeated operation that can be reduced without changing acceptance results |
| 4 | Isolate multistatic acquisition in the neural driver | Target modal condition improves about 73.6 → 10.4; indexed forward/adjoint diagnostics already exist | Validated independent observation indexing, residual scaling and neural pullback; a bounded actual-network test before a full wrong-start comparison |
| 5 | Diagnose neural update directions and regularization | Star loses lobe amplitude while loss falls; circle keeps noncircular error despite good placement | Measure the boundary modes induced by weight updates and data/Eikonal alignment; determine whether the problem is direction, basin or weakly constrained modes |
| 6 | Consider continuation or scaled neural GN/TSVD/IRGN | They may help a nonlinear basin or poorly conditioned update, but neither is isolated by the current suite | Prior diagnostics justify a specific formulation, scaling and comparison budget |

For the star conversion audit, vary production conversion and independent audit
resolution separately. Raising a gate or allowing ever smaller movements is
not evidence of repaired lobes. The 0.1 mm meaningful-movement floor is a
reporting convention, not an acceptance threshold to silently change.

For multistatic or frequency changes, keep data normalization explicit. More
entries can change the response norm and effective regularization balance.
The original suite's evaluation frequencies are historical holdouts, not a
training-selection score. The prior diagnostic study uses a different 3 GHz
holdout and should not be compared numerically as though it were the same set.

## Options to defer without new evidence

- Another unchanged full inverse or a simple increase in the update budget.
- A larger SIREN justified only by failed recovery.
- Another blanket pretraining redesign: prior alternatives produced extra contours.
- Relaxed conversion tolerances or a switch to explicit curve-owned updates.
- Higher frequency presented as necessary merely because the star has five lobes.

## Questions ChatGPT's implementation guide must resolve

Which bounded checks distinguish the causes, in what order, and at what cost?
Which concrete outcome warrants an implementation change or a long inverse?
How will unchanged physics, geometry ownership and acceptance be verified?
Which single factor will the next expensive comparison vary?

The local [prior controls report](evidence/01_prior_controls_and_observability.md)
and [ellipse audit](evidence/02_ellipse_initialization_audit.md) supply the full
written context. Record the returned guide in `03_implementation_guides/` and
its review in `04_discussion/`; decisions are consolidated in `05_final_review.md`.
