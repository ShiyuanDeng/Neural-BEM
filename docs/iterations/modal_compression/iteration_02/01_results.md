# MC-001: real modal structure, but no compact common mask on noncircles

2026-09-21. **Execution status: COMPLETE (Stage A). Stage B: NOT STARTED;
the conditional release gate failed.** The user asked for direct matrix and
derivative visualizations, with continuation only if this first test went well.
This record opens iteration 02 from the [approved iteration-01 plan](../iteration_01/03_plan.md).

**Finding:** the simple entry screen was useful. It exposes a strong distinction
between sparsity of the forward matrix, sparsity of each derivative, and the
cost of one pattern that preserves the forward model and all tested discrete
derivatives. The circle passes. None of the nine noncircular cases passes the
declared 50% common-pattern gate. This is a negative for that construction at
these tolerances, not a rejection of modal compression in general.

## Evidence and visualizations

- [Complete local gallery](../../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/gallery.html), with 18 PNG/SVG figures.
- [Compact forward/derivative comparison](../../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/figures/05_forward_vs_derivative_kd10.png), all four shapes at kD=10.
- [Forward matrices](../../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/figures/01_forward_heatmaps.png): all four blocks of `A-I`, preserving the identity separately.
- [Derivative matrices](../../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/figures/02_derivative_heatmaps.png): the p=6 cosine direction; the gallery also shows all six directions per case.
- [Retained-entry curves](../../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/figures/03_retained_entries.png): arbitrary sorted entries, per-block Frobenius tails, individual derivatives and the union.
- [Actual re-solve errors](../../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/figures/04_resolve_errors.png): field, discrete derivative and physical Hadamard derivative versus represented fraction.
- [Configuration](../../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/config.json), [decision and work](../../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/summary.json), [read-back audit](../../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/readback.json), [implementation](../../../../experiments/modal_entry_screen/README.md).

Each case directory contains `case.json` with every passing/failing mask and
control, and `arrays.npz` with the selected full matrices, all seven analytic
directions including the tangential diagnostic, acquisition and masks. Original
Laurent sources and results are unchanged.

## What was tested

Four unit-diameter finite Laurent geometries (circle, ellipse, asymmetric star,
crescent), three electrical sizes kD=2,10,30, equal-permeability transmission
with `ki/ko=1/sqrt(2)`, and 12 sources × 12 receivers. The state is `(u,q=J*u_N)`.
Physical wavenumbers and acquisition remain fixed during every shape derivative.

Six pure-normal directions use `delta z=(-i*z')*cos(p*t)` or sine for p=1,3,6,
normalized to unit RMS displacement. On a noncircle their normal speed includes
`J(t)`; calling these pure normal-speed harmonics would be inaccurate.

Analytic derivatives of the Hankel/log amplitudes, incident traces and receiver
map were checked against centered full reassembly at three step sizes.
Independent nodal Kress fields and reciprocal derivatives were refined at
384/512 nodes. Modal assembly was independently refined at 512/1024 grid points.
Candidate trace cutoffs were the first passing values on the frozen ladder
16,24,32,40,48,64,80,96. These are **smallest on this ladder**, not proven globally
minimal dimensions. No candidate was enlarged to improve its retained fraction.

For each of six tail tolerances from 1e-2 to 1e-8, two masks were tried:
forward entries alone, and their union with all six derivative supports.
Each block's entries were freely selected by magnitude; no diagonal band was
assumed. Each candidate was solved again. The discrete derivative used the same
frozen mask on `dA`, plus the full acquisition derivatives `db,dC`.
The continuous reciprocal/Hadamard formula on its traces was a separate arm.

## The first-stage decision

The table gives the **smallest represented fraction observed on the predeclared
tail ladder that meets both accuracy gates**, using the common mask. The field
gate is 1e-6 relative error and every tested physical data derivative must be
within 1e-3. These values therefore show the storage cost of accuracy, before
applying the additional 50% release requirement.

| Shape | kD=2 | kD=10 | kD=30 stress test |
|---|---:|---:|---:|
| Circle control | 17.8% | 20.1% | 14.4% |
| Ellipse | 51.1% | 79.0% | 90.4% |
| Asymmetric star | 72.7% | 92.7% | 89.0% |
| Crescent | 61.2% | 87.2% | 86.4% |

The corresponding `(cutoff K, full matrix slots)` at kD=2/10/30 are:

| Shape | kD=2 | kD=10 | kD=30 |
|---|---|---|---|
| Circle | (16, 4356) | (16, 4356) | (24, 9604) |
| Ellipse | (16, 4356) | (16, 4356) | (24, 9604) |
| Asymmetric star | (24, 9604) | (32, 16900) | (48, 37636) |
| Crescent | (16, 4356) | (24, 9604) | (40, 26244) |

The identity is counted separately, conservatively including any diagonal slots
also in the remainder mask. Hence dense masks may exceed 100% in the plots.
These are shared support positions, not measured sparse-factor storage, total
bytes for all derivative matrices, or runtime savings.

Stage B required at least two noncircles to pass at **both** kD=2 and 10.
Zero do. The ellipse kD=2 result narrowly misses 50%; that is not a deep
mathematical obstruction. Its kD=10 result and the other shapes make the overall
gate failure substantially broader than that rounding-level near miss.

## What the direct entry inspection reveals

1. **Symmetry can hide first-order couplings.** The circle's forward blocks
   are diagonal while the p=6 derivative occupies shifted diagonals. An entry
   can be zero at the anchor yet have a nonzero derivative. At kD=10 the
   forward-only mask uses 4.5% of represented slots and gives field error
   2.62e-15, but worst discrete derivative error 4.91. A zero forward entry is
   not permission to zero its derivative. The ellipse's checkerboard pattern
   also warns against assuming the same zero pattern under arbitrary motion.

2. **Individually sparse derivatives need not share a sparse pattern.** At
   ellipse kD=10 and per-block tail 1e-6, the remainder retains 41.7% of entries,
   individual derivatives retain 45.0–49.6%, but the common pattern plus identity
   reaches 101.0%. Separate sparsity and common sparsity are different findings.

3. **The difficult shapes have much less entrywise sparsity at strict matrix
   accuracy.** At kD=10 and tail 1e-6, the star forward remainder retains 93.8%
   and its individual derivatives 98.8–99.3%. The crescent retains 95.6% and
   96.4–99.9%, respectively. Its low Laurent geometry degree does not make the
   modal operator sparse at the minimally qualified trace resolution.

4. **Matrix tails and measured-output error are different targets.** The
   crescent kD=2 common mask at 61.2% has field error 4.26e-8 and derivative
   error 1.59e-4, despite a 1e-2 block-tail allowance. Requiring 1e-6 matrix
   error would retain almost everything. Conversely, on the star kD=2 a
   49.9% forward mask has field error 1.11e-6: almost, but outside, the declared
   gate. Neither raw darkness nor a single norm substitutes for re-solving.

## The surviving alternative is visible, but not qualified for reuse

On the ellipse at kD=10, a forward-only mask representing **30.2%** of slots
gives field error **1.14e-8**. Differentiating its masked system gives worst
relative derivative error **2.16**, while applying the physical Hadamard formula
to its compressed traces gives **1.29e-5**. At kD=2 a 15.0% forward mask has
field error 6.64e-9 and Hadamard error 9.64e-4, just inside the sensitivity gate.
The crescent kD=2 supports this physical route at 43.5%, with field error
6.60e-7 and Hadamard error 1.64e-4 (see the exact saved row).

This reproduces the qualitative Laurent separation on noncircular shapes.
It suggests preserving forward/adjoint traces may be more economical than
preserving every discrete operator derivative. It does not establish a broadly
compact method: the crescent kD=10 requires 71.4% for this route among tested
masks, and the star kD=10 requires 58.9%. Nor is a Hadamard estimate necessarily
the derivative of the approximate objective used by an optimizer.

The planned nearby-motion, held-out direction/illumination and local
Gauss–Newton checks therefore **did not run**. These anchor results must not
be described as successful mask reuse or inverse optimization.

## Outsider checks on this experiment itself

- **The 50% requirement is our screening choice.** A 20–40% slot saving may
  still be useful in a suitable workload. It needs an economic comparison;
  it does not become worthless because this release gate failed.
- **The common mask is a design constraint, not a theorem.** Separate masks
  for operator derivatives or an action-based Jacobian could avoid its union
  cost, although then the computed Jacobian need not exactly differentiate
  the masked forward. The consistency question must be tested explicitly.
- **Largest-entry masks are Frobenius-optimal per block, not output-optimal.**
  Only six shared tail settings were re-solved. No lower bound on the best
  physically weighted or block-specific pattern follows from this screen.
- **Coordinates and norms remain choices.** All cases use the same Laurent
  parameter coordinate and weighted-flux state. Per-block normalization removes
  arbitrary cross-block scale comparisons; it does not test Sobolev mode
  scaling or reparameterization. Dense patterns in this basis are not evidence
  that every basis is dense.
- **Directional and acquisition coverage is limited.** Six normalized
  directions, one contrast, three frequencies and one source/receiver ring
  do not characterize all inverse problems. No asymptotic rate is inferred.
- **Small dense systems already exist here.** Sparse overhead, fill-in,
  mask construction and geometry refresh could consume apparent savings.
  Full dense construction was used throughout this diagnostic, so no speed
  advantage has been demonstrated.
- **Accuracy is output-specific.** For example, the accurate common mask on
  crescent kD=30 has scaled full residual 8.06e-5. Passing receiver/JVP gates
  does not establish a uniformly accurate full-state solver.

## Validation and work

All 12 reference qualifications passed. Worst independent nodal refinement
errors were 2.67e-14 for fields and 1.06e-13 for physical derivatives.
Worst selected-cutoff matrix-grid and derivative-grid discrepancies were
2.06e-14 and 1.60e-14; projected Kress-to-modal block discrepancy was at most
4.88e-14. The worst final-step matrix FD discrepancy was 6.31e-7, with the
multi-step values saved for inspection. This FD number is a truncation/check
error, not a claim that analytic derivative entries smaller than it are noise.

The analytic/grid comparison resolves the 1e-8 tail screen well in aggregate
block norms; it does not independently certify every tiny entry. Relative data
derivative errors use a floor of 1e-8 times the largest directional norm in
each case; all six reference norms exceed that floor in every case, so it
does not mask a failed weak direction. Tangential results are diagnostic only.

Seven meaningful core tests passed. Read-back rebuilt all 144 masks/solves
from saved arrays and reproduced the errors and release decision. Numerical
source hashes had no drift. The main run took 210.7 seconds, with 288 charged
assemblies (including analytic directional assemblies), 265 factorizations
and 0.857 GiB peak RSS. Plotting/read-back are outside this main-run timing.
The main figures were visually inspected; all 18 have PNG and SVG versions.

## Next decision for discussion

Do not launch a sparse implementation from these results. First choose the
benefit worth pursuing and its error target. My preferred next diagnostic is
the **physical-derivative route at fixed forward storage**, using the ellipse
as a positive control and the asymmetric star/crescent as hard controls, then
checking off-anchor consistency and actual trial-objective reduction. That
would directly test the most interesting separation above.

Alternatively, if the intended benefit is rigorous operator compression,
compare block-specific/Sobolev-scaled retention before adding a complicated
adaptive rule. If only forward memory matters, assess the observed moderate
savings against actual storage/factorization costs. These are discussion
options, not dispatched successors. The user's conditional instruction stops
execution here.
