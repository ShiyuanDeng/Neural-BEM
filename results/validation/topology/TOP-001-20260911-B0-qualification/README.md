# Fresh B0 split references — 2026-09-11

These two full inversions ran **unmodified commit `345038a`**, extracted with
`git archive` into `/tmp/topology-B0-20260911`. All archived Python files were
compared byte-for-byte with that commit. [Source verification and commands](source_verification.json).

| Chart | Accepted cut | Final relative L2 | Sampled Hausdorff |
|---|---|---:|---:|
| [Radial](radial/split/metrics.json) | 32-mm corridor, π/4, zero offset, circular seeds | 6.7758124e-7 | 23.297878 nm |
| [Cartesian](cartesian/split/metrics.json) | 32-mm corridor, −π/4, zero offset, K9 contour fits | 6.8733797e-6 | 175.210848 µm |

Both use cap 48, fixed 64/128 nodes, the original 24-pair 0.5-GHz acquisition
and original full-profile controller budgets. The source verification also
compares the candidate generator, workspace, objective, contour fitter and
optimizer configuration ASTs against TOP-001: all five are unchanged.

The earlier radial bundle used cap 12 and selected a different candidate; it
does not reproduce at B0. That [failed historical qualification](../TOP-001-20260911-replay-01/README.md)
is preserved. The Cartesian run reproduces the September 10 audit. The
[qualification amendment](../../../../docs/iterations/topology/iteration_01/04_execution_amendment.md)
records why these new pinned references are used for the comparison.

The original B0 driver has no solve counters and no source manifest. The
separate verification file supplies source provenance; no solve counts are
invented for these runs. The two single-thread baseline processes overlapped;
wall times are not a controlled comparison. Array outputs follow the existing
Git-ignore policy; the subsequent replays include portable JSON observations.

Portable observations were exported from the qualified replay and verified
array-for-array against each original NPZ. In a fresh checkout, run
`python results/validation/topology/TOP-001-20260911-B0-qualification/restore_observations.py`
to restore the ignored NPZ inputs. Container bytes may differ; numerical arrays
are preserved exactly. Then run the replay driver with this directory as
`--reference-root` and a fresh output directory.
