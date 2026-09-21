# Outsider review: what the evidence actually says

2026-09-21. Requested scope: organize the Laurent/compression history, challenge
its conclusions against the new theoretical report, and propose next decisions.
Author: Codex. Independent reviewer: unassigned. This is a source and saved-data
audit, not an independently rerun experiment or an adopted execution plan.

**Verdict:** continue investigating a narrower question. Existing evidence
rejects several particular compression constructions and gives no general
inverse speedup. It does not reject useful compression of physical
sensitivities, output-relevant actions, storage or work at an appropriate
accuracy. Conversely, the new theory does not rescue an uneconomic algorithm.

## 1. Five different things have been called modal compression

| Object reduced | Examples here | What success would mean |
|---|---|---|
| Trace dimension | BIE-002 Fourier cutoff; LAU-003/004 POD spans | Fewer unknowns at independently qualified field and sensitivity accuracy |
| Operator entries | LAU-001/002 masks; September 18 bands | Fewer represented/applied entries, including protected terms, with stable output errors |
| Frequency dependence | September 18 affine operator family | Fewer expensive assemblies after paying for training and geometry refresh |
| External response | Local scattering matrices, `T = P A^-1 B` | Reusable response smaller than boundary state; already useful in some fixed-shape/pose tasks |
| Inverse-relevant information/actions | Reciprocal trace products, goal-oriented truncation | Preserve the update or requested output without preserving every state/matrix entry |

These reductions are not interchangeable. An operator family spanned by eleven
dense matrices has parameter rank eleven; an individual operator need not have
matrix rank eleven, and storing the basis costs eleven matrices. A Fourier
coordinate change alone neither discards information nor improves singular
values when it is unitary in the same norm. Compression also does not create
information absent from the measurements.

## 2. Tests already done and the narrow conclusions they support

The linked bundles own full measurements. Test-suite counts in those records
are historical reports; no solver suite was rerun for this review.

| Test | Observed outcome | Interpretation and boundary |
|---|---|---|
| [BIE-002](../../../../../results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02/README.md): projected nodal matrices, five geometries, two frequencies | Circle/ellipse reduce; difficult shapes fail combined gates. Matched ellipse forward and forward+JVP are 3.44x/3.50x slower than tuned nodal controls | A dense projection wrapper is not an efficient solver. Fixed centered bands failed; oracle magnitude profiles still suggested structure beyond those bands |
| [LAU-001-R1](../../../../../results/validation/laurent/LAU-001-R1-20260917-151900-qualified/README.md): repaired independent controls, fixed entry counts, asymmetry, held-outs | Ellipse passes 30% remainder budget; both stars fail fixed 30%/50%. Refined star's 30% pass uses about 19% more entries than the smaller dense remainder | Retention percentages can be misleading. The spectacular derivative-aware advantage on symmetric fixtures is not representative of the asymmetric control |
| [LAU-002](../../../../../results/validation/laurent/LAU-002-20260917-closeout/README.md): scalar literature construction and adapted transmission masks | Scalar: 0.687% positions, density error 1.63e-11 at 2,047 unknowns. Adapted transmission: compact passes in 6/8 cases, about 20–26% forward-slot savings on four noncircular cases; both ka=5 stars fail | Real conditional compression, not a universal negative. No transmission assembly/solve speedup. Protecting the principal logarithmic term was already tried and did not lower the winning count |
| [LAU-003](../../../../../results/validation/laurent/LAU-003-20260917-closeout/README.md): forward, primal/dual and tangent spans | Star anchor derivatives survive in 48/194 dimensions; that basis fails 0.5%-radius offsets. Tangent rank 120 survives those offsets but fails changed illumination | Small rank at one point is insufficient evidence of a reusable reduced inverse |
| [LAU-004](../../../../../results/validation/laurent/LAU-004-20260917-closeout/README.md): protect primal span; guard and rebuild | Matched ranks 80→56 and 120→112. Delivered 42/42 accurate outputs, with 18 reuses and 24 rebuilds. No compact nonanchor reuse | Construction improved. Correctness obtained by rebuilding is not an efficiency gain; the stronger guard was not shown necessary over a simpler residual gate |
| [September 18 decay/refinement/penalty screen](../../../../../results/experiments/laurent_fgm_20260918/README.md) | Noncircles retain 38.3–62.8% of the selected full matrix for aggregate data-Jacobian error ≤1e-6 over kD=2/10/30. Larger deformation indices generally need wider bands | A modest reduction on these tests, with no subquadratic high-frequency scaling demonstrated. It is not a lower bound on all compression methods; qualification limitations below matter |
| Same screen: solution and frequency reduction | Operator snapshot rank 11 near 1e-6; solution ranks 62–88. At rank 80 the worst recorded derivative errors are 7.11e-7, 4.76e-4, 5.78e-3 for ellipse/kite/crescent | Operator interpolation is promising for many fixed-geometry frequency queries; compact global solution POD is poor on this band. These are not ranks of comparable objects, and the derivative convention is confounded |
| Same screen: local responses and preconditioner reuse | Local-response selective rebuild reports up to 49.2x on a 16-object fixture. Affine preconditioners reduce GMRES counts; training uses 81 assemblies | Separate mechanism and favorable reuse task. Neither result establishes modal-entry compression performance in the current complete inverse |

LAU-005 concerns neighbour/calibration identifiability. It helps explain why the
Laurent agenda moved elsewhere, but supplies no additional evidence against
compression. Its 600 recovery fits should not be counted as a compression test.

The power-series high-frequency failure is also separate: the September 18
closed-form Hankel/FFT assembler removes that particular implementation failure.
Circle Mie checks reach kD=60. This is not qualification of every noncircular
geometry, derivative or frequency at that size.

## 3. Corrections from this review

### A. The later results are not as fully qualified as the older repaired campaign

Read-back is reproducible with [audit_saved_artifacts.py](audit_saved_artifacts.py);
its [JSON output](audit_saved_artifacts.json) records exact values and hashes.

1. **Some geometry tests change the frequency too.** In
   `experiments/laurent_fgm/run_broadband.py`, the perturbed solve recomputes
   `ko = kd / diameter(moved)`. `run_transfer.py` does the same. These measure
   a constant-electrical-size path. At fixed material ratio its derivative is
   `D_c Y + (D_c ko) * partial_ko Y`, with the latter derivative including the
   linked interior frequency. Physical inversion normally holds both physical
   wavenumbers fixed while moving the boundary. This affects broadband
   derivative and geometry-transfer interpretations. The decay and penalty
   drivers do hold physical wavenumbers fixed, so do not discard their results
   for this reason.

2. **The 33-mode reference claim is overgeneralized.** At kD=10, the saved
   untruncated receiver errors at 33 coefficients per trace are 2.01e-15
   (ellipse), 1.60e-7 (kite), and 1.55e-6 (crescent). The README's blanket
   machine-precision statement applies only to the ellipse. Over-resolution
   remains a valid concern, but the amount must be established per case and
   per physical quantity, including sensitivities.

3. **“Gradient” is usually a small data-Jacobian norm here.** The decay driver
   compares four finite-difference columns in an aggregate Frobenius norm. It
   does not compute an objective gradient, test every physical direction, or
   bound an optimizer step. Large columns can hide bad relative errors in weak
   columns. Selection uses that one metric, not all four reported errors.
   Eleven of twelve noncircular gradient-selected rows have trace error above
   1e-6; the maximum is 6.31e-5. This is not failure of a declared trace gate,
   because there was none. It prevents treating these rows as equivalent to
   LAU-001-R1's independently lifted-residual qualification.

4. **A claimed inequality is partly built into the search.** `run_penalty.py`
   starts its derivative-band search at `field_band`. Thus its evidence for
   `Q_grad >= Q_field` is imposed by construction. The observed upper bound
   remains empirical. Its direction families are different, non-nested sets;
   their largest Cartesian indices are not normalized physical harmonics.

5. **Reference refinement is incomplete for the derivative screen.**
   `choose_cutoff` stops using receiver agreement and returns the larger member
   of a coarse refinement pair. It is not a minimal qualified trace cutoff.
   Both derivative arms use the same grid and trace cutoff; step consistency
   checks finite-difference error, not independent discretization error.
   The estimate “step difference / 15” needs the central-difference asymptotic
   regime and controlled roundoff; one step ratio does not certify that regime.

6. **Provenance has drift.** Five of seven saved provenance records have at
   least one current mismatch, primarily `curves.py`, sometimes `test_fgm.py`.
   Affine and transfer records match all their listed files. No separate
   `scaling/provenance.json` exists. A mismatch does not prove a result wrong;
   it prevents claiming exact reproduction from today's code without resolving
   the historical source. Saved inputs/results are preserved.

### B. Several interpretations exceed the measurements

- **The FJS theorem was transferred too literally.** Its original problem is
  Laplace on a two-parameter toroidal surface. Its theorem requires a relation
  between band coefficient, analytic width and target regularity. A `q=2`
  test on a 2D Helmholtz Müller system is an adaptation, not a faithful theorem
  test. Nor does that theorem demand a frequency-independent fitted decay
  exponent in these finite windows. See the [reference map](03_reference_map.md).
- **The computed analytic width is not a certificate.** `curves._reach` samples
  radii/angles, finds polynomial roots and performs one local Nelder–Mead
  search. It can miss a closer obstruction. Agreement with an ellipse formula
  validates that example, not a global zero-free-strip bound. Statements that
  it is a rigorous simplicity test or always returns zero at degeneracy are
  unsupported by this implementation.
- **A fit is not a predictive law.** The quoted bandwidth regression uses the
  same handful of shapes/frequencies it explains. There is no held-out-shape
  validation of its constants. The analyticity parameter is also coordinate
  dependent; calling it only a physical geometry descriptor is incomplete.
- **The broad report's kill criterion was not actually established.** It asked
  about effective density and unpredictability under modest shape changes.
  The later README explicitly reports predictable structure, then treats a
  missing asymptotic improvement as the whole kill criterion. Three electrical
  sizes do not establish an asymptotic impossibility. A constant-factor gain
  could be useful, but its cost must be measured.
- **Preconditioning is not free.** Dense true operators are assembled already,
  LU is cheap at these dimensions, and GMRES adds actions and preconditioner
  applications. The helpers also discard GMRES's `info` and solution, so saved
  iteration counts do not independently establish convergence. Any saving
  requires total wall time and verified true residuals for the relevant RHS.
- **Monolithic reuse is possible.** The blanket statement that a monolithic
  factorization cannot offer reuse is false for updating/skeletonization
  methods. The local-response measurement is useful, but its baseline omits
  those competitors. See Ryan–Damle in the reference map.

## 4. What the new report changes, and what it does not

The new [theoretical report](<../../Theoretical Foundations of Geometry-Spectrum–Adaptive Modal Müller Compression.pdf>)
has a much better distinction between established mapping properties, proposed
entrywise bounds, derivative-family hypotheses and economics. Its central
Müller cancellation claim checks against the primary source. It gives reasons
to investigate **different blocks and different error targets**, not grounds
to relabel previous failures as successes.

Three cautions apply even to this better report:

- Sobolev smoothing does not by itself provide usable entrywise constants,
  uniform inverse stability or certified adaptive retention. Its proposed
  theorem still requires proof; its priority assessment is not evidence of
  novelty or publication readiness.
- Weighting `q = J u_N` is already in the native and hybrid code. Exact
  log-amplitude handling and principal-log protection also already exist.
  Recommending those features alone would repeat completed work. The genuinely
  different experiment is a block-specific/output-specific allocation and its
  physical sensitivity consequences.
- A small notation defect is visible on pp. 3–4: the inner product is defined
  linear in its first argument, but matrix entries are written
  `<e_m, B e_n>` and then equated to `2*pi*kappa[m,-n]`. With that inner
  product the latter formula uses `<B e_n, e_m>`; alternatively conjugate the
  first argument in the definition. This does not overturn the smoothing
  argument, but formulas should not be copied into code unchecked.

A further interpretation issue is norm scaling. Flux and Dirichlet coefficients
are not automatically comparable in an unweighted Euclidean norm. In natural
`H^(1/2) x H^(-1/2)` trace scaling, the schematic cross-block orders transform:
the -3 and -1 cross blocks both have effective order -2 after diagonal Fourier
rescaling. This elementary order count is not a new compression theorem. It
means that “one troublesome block dominates” must be tested in a declared,
dimensionally consistent norm, rather than inferred from raw magnitudes.

## 5. A stronger surviving question

**Can we preserve the physical inverse calculation without preserving the
derivative of every discarded matrix entry?**

There is already a striking controlled observation: LAU-001-R1's circle at
ka=2 and 30% retention has discrete masked derivative error **1.46**, while
the continuous Hadamard expression on its compressed traces has error
**7.65e-15**. That does not make the compressed discrete derivative correct.
It proves that these are different approximation targets. The new report's
forward/adjoint-product argument makes this difference a useful research
question instead of merely a validation warning.

An approximate physical gradient need not be the exact gradient of an
approximate objective. To use it in an optimizer, its discrepancy must be
controlled and steps must be checked against the intended objective. In
particular, our least-squares pipeline needs data-Jacobian actions or equivalent
Gauss–Newton information, not just one scalar objective gradient. Tiny gradient
errors in a global norm can still corrupt weakly observed shape directions.

Possible advantages, with honest status:

| Advantage | Current evidence | What would establish practical value |
|---|---|---|
| Certified accuracy/allocation by block, shape and frequency | Sound theoretical motivation; heuristic spectra | Proven or independently validated tail/output estimator with useful tightness and affordable evaluation |
| Less storage or cheaper many-RHS actions | Represented-entry and rank reductions exist | Measured total bytes/actions including protected terms, factors, construction and validation |
| Better noisy inverse behavior | Untested for these compression arms | Equal-data, equal-regularization recovery/held-out comparisons across seeds; compare explicit regularization, since truncation can merely bias the model |
| More useful physical sensitivities per retained entry | Circle counterexample; partial primal/dual results | Noncircular, high-harmonic and off-anchor controls with independent physical derivatives and update acceptance |
| Broadband or repeated-query amortization | Promising operator interpolation at fixed geometry | Honest break-even versus the tuned nodal compiler, including training and every refresh |
| Spectral interpretation and resolution guidance | Symmetry/sideband structure is real | Predictions verified outside the calibration set; no claim that interpretation alone speeds inversion |

**Decision:** pursue a short sensitivity/output-focused falsification test
before either another sparse backend or a long general theorem project.
Treat parametrization and blockwise structure as controlled candidates, not
new explanations that must be true. The [next-tests proposal](02_next_tests.md)
defines the first decision and the conditions for continuing.
