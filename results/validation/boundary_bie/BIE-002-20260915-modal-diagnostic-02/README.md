# BIE-002 — simple modal compression does not earn promotion

**COMPLETE. H2-FIELD: NO_USEFUL_SIMPLE_COMPRESSION. H2-OPERATOR:
ORACLE_STRUCTURE_ONLY; fixed-band promotion failed.**

One bounded diagnostic ran five fixed geometries at 0.5 and 1.25 GHz. It changed
no shared numerical code, topology controller, material, gauge, acquisition or
optimizer. The known geometry is an input to this forward diagnostic; no inverse
recovery was attempted. BIE-001 was superseded as a desk-study proposal, never
numerically executed. The user's explicit ZIP execution and permission override
authorized BIE-002. No successor is released.

## Key accuracy results at 1.25 GHz

| Geometry | Modes / nodes per component | Data relative error | Lifted residual | Worst tested JVP error | Gates |
|---|---:|---:|---:|---:|---|
| circle | 31 / 128 | 1.106e-14 | 1.014e-09 | 9.369e-15 | PASS |
| ellipse | 63 / 128 | 6.635e-15 | 2.603e-10 | 1.003e-14 | PASS |
| star | 95 / 128 | 2.054e-07 | 5.088e-04 | 5.234e-06 | FAIL |
| saved_common | 191 / 256 | 2.250e-07 | 4.065e-04 | unqualified | FAIL |
| saved_difficult | 191 / 256 | 1.128e-06 | 9.544e-04 | unqualified | FAIL |

Circle/ellipse rows show the smallest qualified retained set. Failed rows show
the largest tested truncation (approximately 75%). Both two-component rows are
**FORWARD_ONLY / SENSITIVITY_UNQUALIFIED**. Gates: data <=1e-6; lifted full-system
residual <=1e-6; available sampled JVP <=1e-4. Full-mode controls are excluded
from candidate improvement claims. Absolute errors and separate arc-length
weighted Dirichlet/Neumann trace errors are in [accuracy.csv](accuracy.csv).

All **10/10** physical data references qualified; worst refinement discrepancy
**1.301e-11**, against 2e-7.
All **10/10** full-mode controls passed; worst data equivalence error
**1.911e-14**, against 1e-10. The small circle
singular-value check agrees to 2.03e-15 (scaled condition number 4.204); this
confirms a coordinate change does not improve the same matrix's conditioning.
Available analytic derivative references qualified with worst discrepancy
**1.637e-13**, against 2e-5.
Noncircular mode-5 Taylor remainder ratios are 3.997–4.000 on step halving,
consistent with second order for both the nodal and actual reduced equations.
This checks sampled JVPs, not a full Jacobian or inverse readiness.

The star at half dimension fails both data (1.82e-5) and shape-direction
sensitivity (2.31e-4) at high frequency. At 75% dimension its data error is small,
but the lifted residual remains 5.09e-4, over 500 times the permitted threshold.
Similar residual failures persist in the saved two-star cases. A small receiver
error alone would therefore have given a misleading success label.

## Matched cost result

Three paired cold repeats on the qualified high-frequency ellipse compare
63 modes per trace assembled from 128 nodes against 64-node nodal Kress.
Each arm uses the same 24 source RHS and reuses its LU for the shape-mode JVP.

| Measured cost | Nodal Kress median [range], ms | Dense projected modal median [range], ms | Modal / nodal |
|---|---:|---:|---:|
| Forward, including setup | 14.14 [13.95, 14.24] | 48.69 [48.19, 48.92] | 3.44x slower |
| Forward + one analytic JVP, including setup | 50.36 [50.31, 50.88] | 176.13 [175.73, 179.30] | 3.50x slower |

The modal parent matrix, projection and validation-base wrapper are included.
Both comparisons have nonoverlapping observed ranges. Timings are small, local
single-worker measurements, not a broad hardware benchmark. Single-thread BLAS
environment was fixed; optional runtime threadpool inspection was unavailable.
The modal JVP wrapper additionally needs a full base validation state; that
measured cost is exposed separately in [timings.csv](timings.csv).
The cheaper nodal control already reduces the ellipse to nearly the same unknown
count (128 nodal unknowns versus 126 modal unknowns). On both star frequencies,
64-node nodal Kress qualifies; the saved two-component controls qualify at 128
nodes per component. There is no measured cost argument to promote H2-FIELD.

## Operator structure

Fixed widths 4/8/16/32 retain 6.91%, 12.84%, 24.12%, and 44.34% of nonidentity
coefficient positions. At low frequency only the ellipse's width-16 pattern
meets the >=4x storage reduction and accuracy gates. At high frequency width 16
fails its residual gate (1.38e-6); width 32 passes but provides only 2.26x value
storage reduction. No star band passes the combined gates at either frequency.
Thus the required success across noncircular tests is absent.

Sorted-magnitude oracle profiles at relative block Frobenius tail 1e-6 retain:

| Geometry, 1.25 GHz | Oracle retention, all blocks | Self oracle with cross blocks kept dense |
|---|---:|---:|
| ellipse | 5.72% | 5.72% |
| star | 16.77% | 16.77% |
| saved_common | 38.23% | 76.07% |
| saved_difficult | 47.70% | 81.32% |

These are full-matrix oracle bounds, not tested adaptive sparse algorithms.
The 5.72% ellipse and 16.77% star profiles suggest structure beyond the tested
bands, but do not establish predictable assembly, solved accuracy or derivative
accuracy after oracle truncation. Cross blocks materially limit the saved-scene
savings. Signed -DeltaK/+DeltaV/-DeltaT/+DeltaKp interactions are separated in
[structure.csv](structure.csv); the identity is excluded exactly.

## Work, verification and limitations

- Counts: **85/120** full assemblies, including **36** derivative
  primal reassemblies; **36/36** analytic directional calls;
  **116/300** LU factorizations; **224/600** RHS batches.
- Numerical wall time: **24.53/1800 s**, including test
  subprocess and two conservatively charged startup seconds. Peak RSS:
  **0.776 GiB / 8 GiB**. The live-array estimate
  also includes dense parents, transformed temporaries, LU and derivative arrays.
- Four algebra tests pass. Physical controls, all 36 analytic operator primal
  reassembly checks, reference convergence and Taylor probes are recorded in the
  work ledger. Reporting audit reconciles all operation reservations/completions.
- Two metadata startup failures preceded numerical execution: missing optional
  `threadpoolctl`, then NumPy's removed `get_info`. They are preserved in
  [startup bundle](../BIE-002-20260915-modal-diagnostic-01/README.md); no physical
  or algebra wiring failure occurred and no scientific arm was retuned.
- Imported numerical source hashes match before/after execution. Topology work
  continued in its own files; this experiment did not edit them. No branches,
  worktrees, commits or pushes were created by this diagnostic.
- This tier does not qualify 1e-8 inverse endpoints, multi-interface derivatives,
  other field bases, or singularity-aware spectral methods. Analytic fixtures
  use declared Cartesian coefficient directions, with no re-gauge/retraction.
- Arrays/rasters are not required to audit these tables. Frozen coefficients,
  acquisition, materials, scene provenance, source hashes and regeneration
  commands are in [manifest.json](manifest.json) and [commands.md](commands.md).

## Single next decision

**Stop/defer this simple projected-field and centered-band prototype; retain
tuned nodal Kress.** Do not implement a new basis, new sparse pattern,
coefficient-only assembly, multi-interface derivative, inverse campaign or
geometry-reuse successor from this closeout. The result does not refute all
spectral BIE approaches.
