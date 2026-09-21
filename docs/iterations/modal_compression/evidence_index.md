# Compression evidence index

Organized 2026-09-21. **The research line is closed.** This is a navigation and
ownership map, not a new experiment or a replacement for the original records.
Start with the [closure decision](CLOSEOUT.md) for the current interpretation.

## Ownership and preservation

| Location | Responsibility |
|---|---|
| `docs/iterations/modal_compression/` | Current compression synthesis, literature audit, MC-001 and closure |
| `docs/iterations/laurent/` | Original LAU plans/results and the broader coefficient-space, scattering-matrix and information experiments |
| `docs/iterations/boundary_bie/` | Original projected-modal diagnostic and pre-Laurent exploration |
| `experiments/` | Implementations in their existing packages; no renaming of imports or experiment IDs |
| `results/validation/` and `results/experiments/` | Original numerical evidence, configs, provenance, figures and reproduction commands |

Organize by links, not by moving or copying the same work into a second track.
An old experiment retains its ID and its plan-to-result history. Original
measurements stay with their bundles; later corrections are linked overlays.
Read LAU-001 with LAU-001-R1, and the September 18 claims with the September 21
audit. A newer README does not silently invalidate or rewrite a raw result.

## Experiments directly concerning compression

| Study | Question and interpretation | Original record / data | Implementation |
|---|---|---|---|
| BIE-002 | Fourier projection of nodal Müller systems; reduced unknowns/masks, physical checks and matched cost. Projected implementation slower; not a test of a direct sparse assembler | [Closeout](../../../results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02/README.md) | [Package](../../../experiments/bie002_modal_diagnostic) |
| LAU-001 | Initial modal remainder/derivative screen. Preserve its original result, but interpret qualification through R1 | [Laurent iteration 02](../laurent/iteration_02/01_results.md), [bundle](../../../results/validation/laurent/LAU-001-20260917-modal-derivative-compression/README.md) | [laurent_compression](../../../experiments/laurent_compression/README.md) |
| LAU-001-R1 | Independent derivative/reference repair, fixed-count refinement and asymmetric controls. Corrects the initial compression interpretation | [Laurent iteration 03](../laurent/iteration_03/01_results.md), [bundle](../../../results/validation/laurent/LAU-001-R1-20260917-151900-qualified/README.md) | [laurent_compression](../../../experiments/laurent_compression/README.md) |
| LAU-002 | Published scalar Fourier masks and their transmission adaptation; conditional slot savings, no implemented runtime gain | [Laurent iteration 04](../laurent/iteration_04/01_results.md), [bundle](../../../results/validation/laurent/LAU-002-20260917-closeout/README.md) | [laurent_literature](../../../experiments/laurent_literature/README.md) |
| LAU-003 | Sensitivity-preserving trace subspaces. Compact anchor success did not imply frozen off-anchor/acquisition reuse | [Laurent iteration 05](../laurent/iteration_05/01_results.md), [bundle](../../../results/validation/laurent/LAU-003-20260917-closeout/README.md) | [laurent_tangent_rom](../../../experiments/laurent_tangent_rom/README.md) |
| LAU-004 | Protected spans and guarded reuse. Delivered accuracy with frequent rebuilds; no compact nonanchor reuse | [Laurent iteration 06](../laurent/iteration_06/01_results.md), [bundle](../../../results/validation/laurent/LAU-004-20260917-closeout/README.md) | [laurent_adaptive_rom](../../../experiments/laurent_adaptive_rom/README.md) |
| September 18 Fourier–Galerkin studies | Direct hybrid assembly, modal decay, refinement, derivative bands and frequency/shape reuse. Exploratory results with audited qualification/provenance limits; no retrospective MC or LAU number | [Bundle](../../../results/experiments/laurent_fgm_20260918/README.md), [later audit](iteration_01/02_proposals/01_outsider_evidence_review.md) | [laurent_fgm](../../../experiments/laurent_fgm/README.md) |
| MC-001 | Arbitrary-entry forward/derivative inspection and fresh solves at qualified cutoffs. All references passed; common-mask continuation gate failed; no Stage B | [Modal iteration 02](iteration_02/01_results.md), [bundle](../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/README.md), [gallery](../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/gallery.html) | [modal_entry_screen](../../../experiments/modal_entry_screen/README.md) |

The scientific comparison of these outcomes is in the
[outsider review](iteration_01/02_proposals/01_outsider_evidence_review.md),
not duplicated in this index. Its [saved-data audit](iteration_01/02_proposals/audit_saved_artifacts.json)
records numerical read-back and historical provenance mismatches.

## The mixed September 18 package

Keep this package and bundle together: multiple mechanisms share the assembler.
Their results should not all be counted as evidence for modal-entry compression.

| Saved subfolder | Mechanism | How to read it |
|---|---|---|
| [decay](../../../results/experiments/laurent_fgm_20260918/decay), [refinement](../../../results/experiments/laurent_fgm_20260918/refinement), [penalty](../../../results/experiments/laurent_fgm_20260918/penalty) | Operator-entry decay, band selection, fixed-kernel refinement and directional penalty | Direct compression evidence; use the audit's qualification, direction-norm and theorem-transfer corrections |
| [broadband](../../../results/experiments/laurent_fgm_20260918/broadband), [affine](../../../results/experiments/laurent_fgm_20260918/affine), [transfer](../../../results/experiments/laurent_fgm_20260918/transfer) | Frequency-family rank, interpolation, reduced solution spaces and preconditioner reuse | Different targets from entry sparsity; broadband/transfer geometry derivatives also change frequency in the archived implementation |
| [multiobject](../../../results/experiments/laurent_fgm_20260918/multiobject), [scaling](../../../results/experiments/laurent_fgm_20260918/scaling) | Local scattering responses, selective rebuilding and object-count scaling | Related Laurent reuse work; favorable response-reuse timing does not demonstrate sparse Müller assembly or a current inverse speedup |

## Related work that remains Laurent-owned

- [Native coefficient pipeline](../../../experiments/modal_muller_research/README.md)
  and [Boundary–BIE exploration](../boundary_bie/iteration_05/01_exploration.md):
  shared geometry, assembly, acquisition and derivative machinery. Its hash-pinned
  code stays in place.
- [Coupled modes and acquisition](../boundary_bie/iteration_05/02_coupled_modes_and_measurements.md),
  [scattering library](../boundary_bie/iteration_05/03_scattering_library.md),
  [deformable scattering](../boundary_bie/iteration_05/04_deformable_scattering.md):
  response compression and reuse are distinct from deleting operator entries.
- [LAU-005](../laurent/iteration_07/01_results.md): calibration uncertainty and
  neighbour-assisted identifiability. It closed the Laurent cycle, but is not
  another negative modal-compression experiment.
- [Speed-up track](../speedup/README.md): whole-inverse profiles and acceleration
  decisions stay there; this archive cites relevant evidence without assuming
  compression is a runtime priority.

## Reports and their interpretation

| Original PDF | Role and reading companion |
|---|---|
| [Research Directions for Modal Boundary-Integral Inverse Scattering](<../laurent/Research Directions for Modal Boundary-Integral Inverse Scattering.pdf>) | Earlier Laurent research directions; read against the executed LAU records |
| [Explicit-Boundary BIE/FWI: literature review and roadmap](<../laurent/Explicit-Boundary BIE_FWI for Scattering_ Literature Review, Novelty Assessment, and Research Roadma.pdf>) | Broad motivation for the September 18 package; read with the later saved-evidence audit |
| [Theoretical Foundations of Geometry-Spectrum–Adaptive Modal Müller Compression](<Theoretical Foundations of Geometry-Spectrum–Adaptive Modal Müller Compression.pdf>) | New 34-page theoretical report; [reference map](iteration_01/02_proposals/03_reference_map.md) separates established results, proposed theorems and empirical claims |

Each PDF has one original location. The brief earlier duplicate in the modal
folder was replaced by the user; the audit identifies the current report by
SHA-256. A theoretical proposal is not a record of an executed test.

## Notation across the two tracks

| Symbol | Meaning |
|---|---|
| `kD` | Exterior wavenumber times object diameter, `2*pi*D/wavelength`; physical electrical size |
| `K_gamma` | Largest absolute Laurent index describing the geometry |
| `K_u`, or `K` in MC-001 figures | Boundary-solution Fourier cutoff; `2*K+1` coefficients per trace, two traces in the scalar Müller system |
| `N` | Boundary nodes in nodal controls; check each historical source for whether its quoted dimension counts nodes, coefficients per trace or total unknowns |

Geometry degree, trace cutoff and electrical size must not be used
interchangeably. The [Laurent symbol table](../laurent/README.md#resolution-symbols--keep-these-distinct)
also explains the coefficient workspace and scattering-matrix angular order.
