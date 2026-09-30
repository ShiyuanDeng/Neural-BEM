# Iteration 07 — MA-006: the operator atlas exposes trace-cutoff feedback

2026-09-29. Owner: Codex. Independent reviewer: unassigned.
**Execution status: COMPLETE.** [Frozen contract](../iteration_06/03_plan.md),
[evidence and complete table](../../../../results/validation/modal_atlas/MA-006/README.md),
[read-back audit](../../../../results/validation/modal_atlas/MA-006/readback_audit.json).

**The atlas now retains modal Müller matrices, both trace unknowns, acquisition
maps and selected operator derivatives.** The first cutoff screen finds a
concrete difference between projecting resolved traces and actually solving a
smaller system. Nine of ten cells qualify. Among those nine, the smallest
sufficient tested cutoff increases in one cell for the data/Jacobian criterion,
and in three cells for the local-update criterion.

This executes the missing numerical part of the original vision's §§5.1 and 8.
It does not establish a coefficient-native inverse or deploy a K_u controller.

## Measurement

The baseline is a resolved nodal Müller/Kress system transformed into a modal
system using the existing flux similarity and unitary DFT. The trace coordinate
is the stored curve parameter t. Shape directions are normalized-arclength
normal harmonics through P=12, represented by fixed Cartesian velocities.
The same parameterization, acquisition, material and reference matrix are held
fixed across the three arms:

- **Projection:** zero omitted coefficients of the resolved forward and
  reciprocal solutions, without re-solving.
- **Reduced solve:** solve the retained principal submatrix with retained RHS.
- **Schur:** eliminate omitted modes exactly, including the RHS correction,
  then reconstruct their traces. This is an expensive algebraic control.

Every cell stores a full 1024 × 1024 complex operator (N=512), checked against
N=1024 for data and shape derivatives. The cutoff ladder is
8, 12, 16, 24, 32, 48, 64, 96, 128, 192. A sufficient cutoff must pass there
and at every larger tested ladder entry; it is not an exact minimum.

The local-update diagnostic uses one fixed 1% synthetic linear residual and a
fixed ridge. It is a numerical-fidelity diagnostic, not a reconstructed shape,
an actual MA-004 optimizer step, or a noise model.

| High-contrast cell, 2.5 GHz | Projection: data/J | Reduced: data/J | Projection: local update | Reduced: local update |
|---|---:|---:|---:|---:|
| Star truth, c=13.3 | 48 | 64 | 48 | 64 |
| C truth, c=13.3 | 48 | 48 | 48 | 64 |
| MA-004 D star endpoint, c=13.3 | 64 | 64 | 64 | 96 |

Data/J requires both relative errors <=1e-3. The local-update gate additionally
requires gradient and ridge-step errors <=1e-2. The other six qualified cells
(three circles, two low-contrast star cells and the low-contrast C) have no
projection/reduced cutoff difference on this ladder. Their sufficient
data/J cutoffs range from 8 to 24; the high-frequency low-contrast star requires
32 for its local-update criterion in both arms.

![Cutoff comparison](../../../../results/validation/modal_atlas/MA-006/cutoff_errors.png)

### The clearest separation: high-contrast star at K_u=48

| Quantity | Projection | Reduced solve |
|---|---:|---:|
| Relative data error | 2.41e-9 | 8.66e-4 |
| Relative Hadamard Jacobian error | 1.07e-4 | 1.50e-3 |
| Relative gradient error | 8.87e-5 | 3.70e-2 |
| Relative ridge-step error | 5.16e-5 | 2.22e-1 |

At K_u=64, the reduced Jacobian error falls to 3.84e-7 and the step error to
9.55e-5. The reduced system then has 258 complex unknowns, versus the reference
system's 1024. That dimension reduction is not an end-to-end speedup claim:
this experiment still assembles and transforms the full operator.

The C truth illustrates a separate point. At K_u=48 the reduced data and
Jacobian already pass the 1e-3 gate, but the step differs by 9.55%. At the star
endpoint K_u=64 gives data/J errors of 1.16e-4/2.21e-4 yet a 2.92% step error.
Accuracy relative to the field is not automatically accuracy relative to a
small residual and its local update.

### The matrix-level explanation

For the same full reference system, the difference in retained solutions is

    x_L(reduced) - x_L(reference) = A_LL^{-1} A_LH x_H(reference).

This identity is checked at every cutoff; its worst normalized discrepancy is
6.89e-14 over all ten cells. The high-contrast star's retained feedback is
8.66e-4 relative at K_u=48. The Schur-corrected system recovers the reference:
over qualified cells, maximum data/Jacobian errors are 4.65e-14/4.09e-14.

Thus the gap in these comparisons comes from omitted-mode feedback in the
same discretization, rather than a changed acquisition or different numerical
assembler. The feedback diagnostic currently uses the full reference x_H. It
explains the error retrospectively; it is **not yet a cheap prospective error
estimator** for choosing K_u without a resolved solve.

The operator records show the expected strong diagonal structure of the circle,
fivefold coupling pattern of the star, and broader coupling of the C in the
declared coordinate. These are descriptive observations. The per-block figures
normalize each displayed block separately and do not compare absolute physical
importance across blocks.

![Operator blocks](../../../../results/validation/modal_atlas/MA-006/operator_blocks.png)

Selected dA/dB/dR records cover constant and cosine-6 shape directions.
They are centered-difference estimates with step refinement, not analytic
derivatives. Very faint extra bands in derivative plots can be finite-difference
or roundoff residue and should not be interpreted as resolved physical couplings.
The full-matrix derivative path includes incident and readout derivatives.
Across qualified cells it agrees with the actual-velocity Hadamard derivative
to <=1.54e-6 relative. At small cutoffs the derivative of the reduced discrete
model and the Hadamard expression on reduced traces differ substantially;
both are retained separately in the evidence.

### One qualification failure, preserved

The MA-004 D C endpoint at c=13.3 fails the fixed direction-window gate:
projection of the intended normal harmonic velocities into the declared
Cartesian window differs by 2.17e-4, above 1e-4. Its field/Jacobian grid errors
are only 4.57e-9/1.36e-8, and its selected derivative comparisons pass.
Its matrix records remain useful for the actual projected directions, but the
contract excludes it from cutoff recommendations. This does **not** identify
the cause of its earlier inverse failure. No gate was relaxed or window widened.

## What is now recorded

Ten complex NPZ snapshots total 452.8 MiB. Each contains A (all four blocks),
B (source and reciprocal RHS), R (receiver readout), Dirichlet and flux trace
coefficients, selected dA/dB/dR, geometry, physical normal velocities, DFT
ordering/scaling, and cutoff-level data/Jacobians/gradients/steps. The JSON layer
adds trace tails, block couplings, retained conditioning, Schur/feedback
measurements, qualification and sufficient-cutoff results. The data can support
new analyses without regenerating these BIE solves.

The matrix assembly and basis transformation are a hybrid projected-Nyström
control imported from the Laurent library. No coefficient-workspace B_work is
used, and no native Laurent coefficient assembly has been qualified on these
snapshots. MA-001 used arclength trace spectra; its empirical cutoff law cannot
be compared numerically with these native-parameter cutoffs without aligning
the trace coordinates.

## Validation and decision

Five tests pass: two existing circle controls and three new independent
algebra/finite-difference/cutoff-selection checks. All 300 saved arm/cutoff
records pass read-back recomputation of errors and cutoff choices. Source and
input hashes match. For the nine qualified cells, grid discrepancies are
<=2.50e-14 in data and <=5.36e-14 in J. The campaign used 100 nodal assemblies,
20 nodal factorizations and 300 reduced/Schur factorizations in 130.9 seconds on
an Intel Core Ultra 9 285K, one CPU worker and one BLAS thread. Hardware load was
not controlled; these are descriptive timings. Detailed RHS-accounting limits
are disclosed in the evidence README.

**Decision:** retain the operator layer as part of the atlas. This screen
demonstrates that its retained/omitted coupling can matter to a useful trace
cutoff, especially when the desired quantity is an update rather than a field.
Trace projection is a starting diagnostic, not a solver-cutoff certificate.

No automatic successor is launched. The remaining implementation question is
whether an affordable estimator of data/J/update error can select K_u without
assembling or solving the full reference. Before deploying that, qualify the
actual active update bands (including M=37–85), more residual directions,
noise, and an appropriate native or hybrid assembler. This experiment measures
neither inverse recovery benefit nor cost savings from an adaptive K_u policy.
