# Repository handoff and non-destructive integration

## Inspected context

Repository: `ShiyuanDeng/Neural-BEM`  
Branch: `feature/ordered-boundary-nystrom`  
Package date: 2026-09-15

The current branch HEAD was not pinned by this packet. Individual document blobs are recorded in `manifest.json`; local agents must capture their actual checkout commit and file hashes before work. Repository state may advance after this package is prepared.

The fetched track handoff still identifies Boundary–BIE iteration 01 as proposal/review stage, no approved experiment IDs, and BIE-002 as a reserved prototype contract. This packet supplies a proposed narrow contract, not a retrospective claim of approval or execution.

The shared iteration rules are newer than the track handoff's old separate-branch wording. The shared rule says use the existing `/home/drdeng/Neural_SDF_BEM_AD` checkout on `feature/ordered-boundary-nystrom`; new branches/worktrees require separate explicit approval. Follow that newer shared rule.

## Read before coding

Repository-relative paths; inspect current definitions rather than relying on historical line numbers:

    AGENTS.md (where present, and applicable ancestor/nested instructions)
    docs/iterations/README.md
    docs/iterations/implementation_principles.md
    docs/README.md
    docs/current_architecture.md
    docs/iterations/boundary_bie/README.md
    docs/iterations/boundary_bie/iteration_01/02_proposals/01_boundary_bie_research_brief.md
    docs/pipelines/explicit_cartesian_fourier.md
    solvers/gpr_bem_kress/README.md
    solvers/gpr_bem_kress/system.py
    solvers/gpr_bem_kress/operators.py
    solvers/gpr_bem_kress/forward.py
    solvers/gpr_bem_kress/multicomponent.py
    solvers/gpr_bem_kress/shape_derivative.py
    solvers/sdf_inverse/curve_updates.py
    solvers/sdf_inverse/radial_topology.py

Use current result-catalogue links to locate saved geometries. TOP-018's qualified two-star bundle is one existing source, not a mandate to replay its inverse. The older architecture's 64/128-node statement must not override actual saved manifests that use 256/512.

Historical source inspection found `KressDirection`, `linearize_kress_forward`, and analytic directional operators in `shape_derivative.py`, with single-interface restrictions. It also found a separate `np.linalg.solve` inside each JVP. These are navigation hints, not a guarantee that today's implementation is unchanged. Inspect current behavior, support and counters before making performance claims.

## Allowed numerical code area after named approval

Prefer a new self-contained module:

    experiments/bie002_modal_diagnostic/
      README.md
      run_diagnostic.py
      modal_projection.py
      metrics.py
      test_modal_projection.py

These are suggested new filenames, not claims that executable entry points already exist. Keep the module small. It may import existing solver/geometry functions, assemble experimental projections, collect results and test algebra. Do not duplicate the singular kernel implementation.

Shared production numerical code is read-only under this contract. Instrument with wrappers. A required shared-API change is an explicit blocker/proposal, not permission to refactor. Do not change the Kress weights, branch cutoffs, diagonal formulas, materials, source/receiver map, topology policy, Fourier gauge, optimizer or defaults.

Allowed documentation changes after review/approval: the named review, the agreed iteration-01 plan, and concise status/link updates in the track handoff. After closeout, open the next results cycle. Leave other tracks and historical evidence untouched.

## Work protection

Before editing, inspect working-tree status and identify user/other-agent changes. Never reset, clean, stash, overwrite, or rebase them. Do not auto-commit or push merely because this packet is being executed. Use one implementation writer; no parallel agents changing the shared checkout. A reviewer may inspect read-only.

If the checkout or schema has changed, make the smallest necessary compatibility adjustment within the experimental module, record it, and retain the mathematical contract. If a concurrent writer is active or a change would exceed scope, leave a precise blocked report rather than proceed unsafely.

## Artifacts and reproducibility

Use a fresh unique directory such as

    results/validation/boundary_bie/BIE-002-<date>-modal-diagnostic-<run-id>/

Respect the repository's binary-artifact policy. Do not imply excluded arrays/figures will exist in a fresh checkout. Save numeric summary data, coefficients/provenance and regeneration commands sufficient to audit conclusions. Keep failed arms and exhausted budgets visible.

At completion, report source files changed, tests actually run, artifacts, performance/accuracy qualification and the single recommended next decision. Do not launch that successor.
