# BIE-002 — frozen modal/structure diagnostic

- Approval: **APPROVED** by the user's 2026-09-15 ZIP execution instruction and
  explicit permission override, as recorded in the [review](02_proposals/03_current_checkout_review.md).
- Execution: **COMPLETE**, 2026-09-15. See the [result bundle](../../../../results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02/README.md).
- Owner: Codex. Reviewer: self-review; no independent reviewer assigned.
- Scope: experiment-local only; shared numerical source, topology work, gauge,
  optimizer, materials and production defaults remain read-only.
- Governing mathematics/budgets: [packet contract](02_proposals/02_modal_reuse_diagnostic_pack/02_BIE002_MODAL_DIAGNOSTIC.md)
  and [validation rules](02_proposals/02_modal_reuse_diagnostic_pack/04_VALIDATION_COST_AND_STOP_RULES.md).

## Frozen choices (before numerical results)

Five continuous geometries: circle `(0.5,0.5), r=.05`; ellipse and 5-lobed star
from TOP-018's `central-ellipse-star` scene specification; saved TOP-018 COMMON
two-star state; saved TOP-017 engineering resolution `F_rejected` state (the
previously difficult, subsequently 256/512-qualified two-star state). Geometry
is known input to this diagnostic, not an inverse estimate. Preserve saved
Cartesian coefficients verbatim. Analytic fixtures retain native parameter t;
no refit/re-gauge occurs. Their geometric bandwidths are 1, 1, and 6.

Use 0.5 and 1.25 GHz, existing topology development frequencies. Copy materials,
24 paired transmitters/receivers, constants and 1e-6 source strength from TOP-018.
Neither frequency is claimed as untouched evaluation data. Use paired scattered
fields, real-stacked and normalized by the fixed finest-reference response norm;
also save absolute complex errors and full receiver-matrix errors. The incident
paired response norm fixes S_y independently of candidate choice. Ell is the
base curve/union bounding-box diagonal sampled at 2048 native parameter points,
fixed for all arms, resolutions, perturbations and frequencies.

Single-interface ladder: 64/128/256 nodes; 128 is the projection integration
grid, 256 reference, qualified by 128/256 discrepancy. Multi-interface ladder:
64/128/256/512 nodes per component; projection at 256, reference at 512,
qualified by 256/512 discrepancy. No further refinement. Retain the largest odd
mode count <= each of .25N, .5N, .75N; full includes one Nyquist representative.

Directions: circle x-translation; ellipse/star x-translation and Cartesian
cos(5t) in x / sin(5t) in y. Each has unit RMS physical boundary displacement;
all native jets are coherent. These are fixed Cartesian coefficient paths,
not topology-controller retractions. Two Taylor probes on noncircular high
frequency cases use the mode-5 direction at amplitudes 1e-4, 5e-5, 2.5e-5,
1.25e-5 metres, fixed P/S. At most 30 reference/ladder directional assemblies;
reserve 6 for a three-pair cold timing comparison of the first qualified
noncircular high-frequency reduced candidate (one mode-5 JVP per arm).

Fixed centered-mode bands: widths 4/8/16/32 on ellipse and star, both
frequencies, all four signed trace blocks of A-I. No wrapping. Identity exact.
Oracle profiles on every base case: smallest retained entry counts leaving
relative Frobenius tails <=1e-2, 1e-4, 1e-6, reported per signed self/cross block.
Fixed pattern derivatives use the identical frozen mask. Also record action
errors on the solved fields and all primal transmitter trace tails.

Primary thresholds: full-mode 1e-10; reference data discrepancy 2e-7;
candidate data 1e-6; derivative reference discrepancy 2e-5; candidate JVP 1e-4;
lifted residual 1e-6. Fixed source floors are 1e-12*S_y (and /ell for JVP).
Promotion thresholds and stopping rules are unchanged from the packet.

120 system assemblies (conservatively includes derivative primal reassembly),
36 derivative calls, 300 LU factorizations, 600 batched solves, 1800 numerical
seconds, 8 GiB RSS; planned array storage below 4 GiB. Reserve before each
operation, ledger attempts/failures/reuse, one single-thread numerical worker.
Report coarse peak RSS and conservative array estimates; do not claim exact
allocation tracing. One wiring-repair round maximum. Stop on imported numerical
source drift. Three paired repeats have the same prior warm-up for both arms;
if no candidate passes, skip finalist timing and explain why.

## Deliverables / stop

Fresh `results/validation/boundary_bie/BIE-002-*` bundle with frozen manifest,
work ledger, accuracy/timing/tail/structure/Taylor tables, tests and commands.
Close H2-FIELD and H2-OPERATOR separately. Open iteration 02 only after results.
Choose exactly one next decision; do not execute a successor, inverse, BIE-004
or geometry-reuse study. BIE-001 is superseded, not numerically executed.


## Execution closeout — 2026-09-15

All ten scene/frequency cases completed within the frozen budget: 85 assemblies
(including 36 analytic primal reassemblies), 36 directional calls, 116
factorizations, 224 solve batches, 24.53 numerical seconds, 0.776 GiB peak RSS.
Four algebra tests pass; all full-mode and reference checks pass. The supplied
pre-execution plan is preserved byte-for-byte as `frozen_plan.md` in the bundle.
Two environment-metadata startup failures preceded any numerical work; the
continuation records them and conservatively charges two seconds. No physical
wiring repair, tolerance change, extra scene or scientific retuning occurred.

H2-FIELD: **NO_USEFUL_SIMPLE_COMPRESSION**. H2-OPERATOR:
**ORACLE_STRUCTURE_ONLY; fixed-band promotion failed**. Multi-interface
sensitivities remain explicitly unqualified. Three paired timings favor the
cheapest qualified nodal baseline. Results open
[iteration 02](../iteration_02/01_results.md). The single decision is to stop/defer
this simple projected-field and centered-band prototype and retain tuned nodal
Kress. No successor is executed or released.
