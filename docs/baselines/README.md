# Baselines

A baseline record identifies the **executable comparison reference** for a
planning window: which source state, which drivers and configurations, which
observations and oracles, which existing result bundles, and what those runs
accepted as success.

Recording a baseline does not create a Git tag, copy result bundles, regenerate
observations, or overwrite anything. It identifies and preserves the reference
so later comparisons have something fixed to point at.

| Baseline | Snapshot | Covers |
|---|---|---|
| [B0](B0_2026-09-10.md) | 2026-09-10 source state, recorded 2026-09-11, committed as `345038a` | Explicit radial and Cartesian Fourier inverse with the shared automatic topology controller; the starting point for the [topology](../iterations/topology/README.md) and [boundary–BIE](../iterations/boundary_bie/README.md) tracks |

## Rules

- Record the **full commit hash and branch**, and state plainly whether the
  working tree was dirty. If it was, the baseline is HEAD *plus* the tree.
- Never silently identify the current HEAD with the revision that generated a
  historical result. Record both when they differ.
- Distinguish, in every claim: implemented capability; recorded experimental
  evidence; an independently rerun verification; an interpretation or
  hypothesis; a proposed future direction.
- A recorded test count is not a test run. An existing result bundle is not
  automatically evidence for the current HEAD.
- Where provenance is missing, say so. Absent provenance is a finding, not a
  gap to fill by inference.
