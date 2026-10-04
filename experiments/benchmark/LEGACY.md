# Legacy scene sets: reproduce evidence only, never start new work here

Since 2026-10-04 the only scene set for new experiments is [TG-002](README.md). The sets
below are retired. They stay **where they are** because campaign seals hash their exact
paths: `atlas_cases.py` and `policy_cases.py` alone are pinned by about 100 manifests.
`results/.../SC-050/run.py` lives inside its own sealed result folder. Moving or editing
these files would make the recorded campaigns unverifiable. They are frozen; read them, do
not extend them.

**Why they are retired:**
- The far-start sets (SC-049/SC-050, the CI-001 `far__`/`modal__` panels and everything
  derived from them) start 220–267 mm from the target. They only recover with the exhaustive
  SC-050 disk grid search. From those starts, 0/6 recovered without it in SC-050, against 6/6
  with it. Results on them measure the grid search, not the node-free method.
- The near-start sets duplicate shapes that TG-002 now carries with one common start and
  frozen placements.

| Legacy set | Scenes | Where defined | Status |
|---|---|---|---|
| SC-022 atlas | `wrong_circle`, `circle_to_star`, `circle_to_c` | `experiments/shape_continuation/atlas_cases.py` | Shapes moved into TG-002 (`circle`, `star`, `c_shape`) |
| SC-025 held-out | `kite`, `peanut`, `hook` | `experiments/shape_continuation/policy_cases.py` | Shapes moved into TG-002 |
| SC-044 fresh | `asymmetric_lobes`, `deep_c` (+ noise seeds) | SC-044 result folder | Retired (covered by `asymmetric`, `c_shape`) |
| SC-047/048 coupled | two-object separations | SC-047/048 result folders | Retired (outside the single-curve method) |
| SC-049/SC-050 far | `development_c`, `opposite_c`, `shifted_rotated_c`, `shifted_star`, `new_asymmetric`, `new_thin_c`, `noisy_asymmetric` | `results/validation/shape_continuation/SC-050-localization-robustness/run.py` | Retired: far starts need the grid search; `opposite_c` duplicates `development_c` data |
| MA-002…MA-006 contrast inputs | the far scenes at contrasts 2, 4, 13.3 | `experiments/modal_atlas/*` | Retired (far starts) |
| CI-001 all-36 regression | core/fresh/far/modal panels | `experiments/cleaned_interface/benchmark.py` (`descriptors`) | Frozen regression record. Its fit/score helpers are still reused by TG-002, unchanged |
| FM-001…FM-005, RB-001, TR-001…003 | `modal__c13.3__development_c` and related | `experiments/cleaned_interface/fm00*.py`, `experiments/relaxed_bie/`, `experiments/theory_radius/` | Completed campaigns on legacy cases. Do not continue them on legacy cases; port the question to TG-002 |
| TG-001 | far-start `aphex_twin`, `cog`, `cross`, `heart`, `s_curve` | `experiments/cleaned_interface/legacy/tg001_target_gallery.py` | Superseded the same day by TG-002 (no fits run) |

The CI-001 `benchmark.py` name predates TG-002 and refers to the 36-case regression set,
not to this benchmark. Older topology, IBIM, SDF and SPD drivers (root `run_*.py`,
`experiments/top0*`, `spd*`) predate the cleaned interface entirely.

To reproduce a legacy result, use that campaign's own README and recorded source snapshot.
