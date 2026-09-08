# Iteration 01 — final review after matched controls

Retrospective consolidation on 2026-09-08 of the guides, reviews and completed
A–E study. This records the diagnostic cycle's outcome; it does not imply
general neural recovery or execution of deferred experiments.

## Verdict

Retain the targeted repairs. The extra fallback step explains a premature stop
but barely improves the badly recovered star. The five-parameter star recovers
with eight pairs at 0.5/1.5 GHz, and the tested 21-mode two-frequency boundary
Jacobian has full rank. Multistatic readout improves conditioning; higher
frequency adds sensitivity. These are local diagnostics, and full-MLP recovery
remains unresolved.

## Measured outcomes

| Question | Result | Interpretation |
|---|---|---|
| Eight-pair five-parameter recovery? | 13 updates; 0.03870 mm boundary error; train 5.433e-6; 3 GHz holdout 1.978e-4 | Yes within the star family; not neural sufficiency |
| Target-fitted MLP locally usable? | Three updates improve train 0.01073 → 0.00745 and holdout 0.11963 → 0.08926; boundary error 1.191 → 1.290 mm | Short descent neighborhood exists; geometry partly deteriorates |
| Physical lobes absent from original band? | Physical Jacobians rank 5 at the declared thresholds and all tested geometries/acquisitions | Categorical missing-information hypothesis unsupported |
| Tested general modes rank deficient? | Stacked original band ranks 21/21 for modes 0–10 under all acquisitions | No in that local space; higher modes and neural update map remain open |
| Multistatic benefit? | Target modal condition number 73.6 → 10.4; absolute minimum singular value 18.15× larger | Better conditioning and absolute sensitivity; not global recovery |
| Frequency benefit beyond multistatic? | Replacing 0.5/1.5 with 1.5/2.5 GHz raises the target-relative modal minimum 4.83× at both geometries | Supports a separate frequency experiment |

Directions have equal 1 mm RMS normal displacement and declared response
normalization. Multistatic does not improve every target-relative sensitivity:
at the wrong initial star, its original-band normalized minimum is below
paired-8 while absolute sensitivity improves. Inverse comparisons must declare
data scaling and its balance with Eikonal regularization.

## Final decisions

| Topic | Decision |
|---|---|
| Stopping | Preserve both fidelity limits, record rejection reasons and deepen diagnostic backtracking |
| Pretraining | Retain zero star penalty and original circle/ellipse settings |
| Acquisition | Prefer multistatic-8 at 0.5/1.5 GHz for the next isolated neural acquisition change |
| Frequency | Keep a later multistatic 1.5/2.5 GHz arm separate, with two objective terms and a disjoint holdout |
| Continuation | Defer until its basin benefit can be tested against a comparable direct run |
| GN/TSVD/IRGN | Defer a production optimizer; specify neural scaling and regularization if justified |
| Expensive runs | Declare the question and work limit; falling loss alone is not success |

The guide's claim that bandwidth 96 eliminated guard-related termination is
superseded by the checkpoint probe. Five-parameter recovery does not close the
general acquisition question, and a three-step target-fit run does not certify
stability. Stronger claims in earlier discussions remain historical opinions.

## Implementation, validation and work

Implemented capabilities include indexed Kress readout/adjoints, 14-halving
neural defaults, independent rejection reasons, target-fit starts and
post-optimization holdout replay with state restoration. At this stage the
production neural inverse remains paired; no full multistatic neural inverse,
continuation or new optimizer is claimed.

The study reports 184 focused integration tests passing. Fresh finite differences
show second-order convergence in 72 direction/acquisition/frequency groups,
maximum finest-step relative error 1.123e-6. Forward/derivative refinement and
792 spectral-rank checks pass at the sampled settings. The 3 GHz holdout passes
independent 512/1024-node oracle refinement at 2.494e-10.

Five-parameter paired-12/8 controls take 75.53/95.81 seconds; the frozen
backtracking audit takes 235.46 seconds. Physical/modal studies take 1,739.98
seconds for 336 frequency-specific forwards and 1,248 JVPs. The target-fit run's
original 387.22 seconds includes 52.22 seconds of holdout callbacks; the full
report preserves that accounting and its subsequent replay correction. These
are single-run engineering timings.

The [full controls/observability report](evidence/05_controls_and_observability.md)
is included in this folder with configurations, spectra and artifact references.

## Handoff

Open questions concern the wrong-start basin, unprobed boundary directions and
neural update geometry. The following 12-pair repaired wrong-start suite opens
iteration 02. It does not implement the recommended multistatic change and
cannot validate that deferred fix. Its results require a separate consultation.
