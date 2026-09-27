# SC-047: coupled continuation and topology diagnostic gate

2026-09-27. Owner: Codex; no independent reviewer assigned. User authorized
autonomous follow-through after Claude's final `34355f99` handoff. Existing
branch only. SC-047 does not promote production defaults.

Question: can the qualified single-object continuation core take coupled,
object-specific steps on general Cartesian curves, and do selective updates
improve geometric recovery at counted cost? Topology remains diagnostic-only.

Claude's parts 5–6 are complete, including their early stops and negative
strategy findings. No supported atlas superiority is assumed. His suggestion
to settle noisy single-object behaviour is retained as a limitation; this
bounded foundation screen follows the supplied multi-object roadmap, with
noise included in the strategy and topology controls.

## API map and implementation

- `forward.py`: dispatch OrderedBoundary2D to the existing multi-component
  Müller assembly, receivers and incident traces. Reuse the same factorization,
  Hadamard contraction and paired-data selection; preserve single-object code.
- New `multi_object.py`: immutable collection of FourierCurve objects with
  stable IDs; independent per-object update spaces composed from an injected
  existing update implementation; block physical metrics and conditional atlas.
- Reuse `lm_backend.fit_stage`, `Objective`, `Ledger` and acceptance gates.
  The driver injects SC-035's existing complete centred projected update.
  No legacy polar gauge, new optimizer, or new forward discretization.
- Focused regression tests precede numerical edits: one-component equivalence,
  permutation, two-component finite differences, paired-only output, invalid
  geometry, freezing an object, conditional projection identity.

## Frozen sequence and ceilings

1. Qualification: paired inherited ring acquisition and material contrast;
   independent multi-cylinder reference for two circles; circles and an
   ellipse/C pair at N=128/256/512 per component as needed. At frequencies
   0.25/0.5/1.0/1.5 GHz, require forward refinement/reference relative error
   <=1e-6; perturb objects separately and together at 2e-6, 1e-6, 5e-7 m,
   requiring at least two successive complete-trial derivative errors <=1e-3.
   Single-object and permutation differences <=1e-11. Preserve all errors.
   Ceiling: 1,000 frequency solves and 20 minutes.
2. Only if qualified: fixed-count ellipse/C scenes, centre separations
   0.14/0.20 m, same known contrast; K=32, M=3 then 5, N=256/512.
   Correct count and approximate locations, perturbed shapes; label this a
   local recovery screen, not discovery from circles. Frequencies fixed at
   0.25/0.5/1.0/1.5 GHz throughout; equal frequency weights, inherited paired
   data. Refined N=512 observations. Clean and 1% complex Gaussian noise,
   seed 4701 (per-frequency relative normalization, no whitening claim).
   Compare joint LM, round-robin object LM, and object selection nominated
   by conditional residual/shape information. Nomination uses all Jacobians
   and charges them. Accepted finite progress uses the same LM/refined gates.
   Maximum 12 one-iteration dispatches, 400 solve units and 20 minutes per
   arm including diagnostics; 16 units reserved for endpoint qualification.
   All arms share M=3 for six dispatches then M=5 for six. Only object
   selection differs. No threshold tuning after seeing outcomes.
   Also measure target alone, known neighbour, unknown neighbour at identical
   physical scaling. Report absolute spectra and conditional information loss.
   Success requires worst-object RMS <=0.9 of both controls on all four scenes
   at no greater work, and neither object >1.05 of the better control.
   Otherwise no strategy superiority; count each arm's actual finite progress.
3. After forward/derivative qualification: separately budgeted diagnostic
   insertion response from coupled incident/reciprocal fields, checked against
   finite disks at radii 0.004/0.002/0.001/0.0005 package units (5 cm/unit).
   Equal permeability/finite dielectric contrast only. Validate sign and
   response per area at separated exterior points; relative response error
   <=2% on the two smallest probes and improvement under radius refinement.
   Four cases: wrong boundary/correct count, missing object, extra object,
   correct geometry plus 1% noise. Compare before/after equal-budget shape
   refinement, log finite birth and whole-component deletion counterfactuals.
   Ceiling: 600 frequency solves and 20 minutes. Actual objective derivative,
   no per-frequency image rescaling; count off-boundary work and RHS columns.
   This screen cannot authorize topology actions: require qualified finite
   predictive value without systematic correct-count false births first.

Before dispatch save exact settings, inputs, source hashes and commands.
Record all numerical stops, refused candidates and work, including audits.
Truth is used only to generate observations and score saved endpoints.
Report per-object RMS/Hausdorff, worst object, region error, clearance and
curvature. Valid endpoints and diagnostics are prerequisites, not novelty.
No new branch/worktree, topology action or production policy promotion.
