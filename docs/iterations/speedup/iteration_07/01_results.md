# SPD-007 — promote compiled + reciprocal + readiness to the default

Authorized directly by the user's “yes” on 2026-09-17, following the explanation
that SPD-006 was integrated but still opt-in. Work uses the existing
`feature/ordered-boundary-nystrom` branch. No new branch or worktree.

**COMPLETE / DEFAULT PROMOTED.** Both fresh full workers recover and preserve
the previously qualified endpoints exactly.

## Resulting behavior

The normal full inverse now selects **compiled + guarded reciprocal derivatives
+ training-only readiness**, with no runtime flag required. An existing
`SDF_INVERSE_RUNTIME` setting or explicit Python context still takes precedence.

| Path | Default behavior |
|---|---|
| Cartesian fit, multiple components, at least 256 nodes | Compiled scattering with convergence checks and full Kress fallback |
| Single component or unavailable compiled representation, at least 128 nodes | Full Kress with reciprocal shape derivatives |
| Coarse Cartesian fit below 128 nodes | Existing operator shape derivatives |
| Radial coefficients | Existing finite differences |
| TOP-025 full-pipeline handoff | Check all four training frequencies at 256/512 nodes before continuation |
| Ready handoff | Skip fitting; still score independent evaluation frequencies and original geometry/numerical gates |
| Unready handoff | Run the existing four-stage schedule, optimizer and constraint policy |

Readiness uses the exact SPD-004/SPD-006 gate: relative fit error at both
resolutions <=1e-5, and per-frequency production/refined discrepancy
<=[1e-5, 1e-7, 1e-7, 1e-7]. Truth geometry and evaluation frequencies never
enter the routing decision. A ready result records `STATIONARITY_NOT_MEASURED`;
skipping the schedule does not claim optimizer stationarity or full exposure.
Standalone fixed-topology fits do not run the full-pipeline readiness check.

`--inverse-runtime fast`, `reciprocal`, and `reference` remain explicit comparison
profiles and run the full continuation schedule. `fast` selects the previous
operator derivative; `reciprocal` uses full Kress reciprocal fitting; `reference`
selects FD/reference CPU. Equivalent environment and Python selections remain
available. Explicit forward execution contexts retain precedence.

## Integration details

- `sdf_inverse.runtime` defaults to `compiled` and records
  `continuation_readiness=True` in runtime metadata.
- The pure readiness gate lives in `sdf_inverse.readiness`. The full workflow
  lives in `experiments.top025.readiness`; the older SPD wrappers reuse it.
- `experiments.top025.run.run_continuation` routes by the selected profile.
  `run_scheduled_continuation` retains the original schedule without a second
  readiness check. The gate is charged exactly once.
- Spawned campaign workers read their runtime from the frozen contract,
  including when a Python context selected it before thread-pool dispatch.
- Work summaries retain physical systems, operator directions, reciprocal
  batches, compiled batches and per-frequency failures separately. The
  readiness screen has its validated separate 8-unit/300-second budget; the
  fit retains 8012 units/7200 seconds. New campaign contracts account for the
  screening overhead explicitly; existing outer timeouts remain hard limits.
- Normal reporting replays the readiness decision from saved training arrays,
  checks independent endpoint scores, and recognizes a qualified early exit.
  Video provenance includes the final capacity-adjusted handoff even when
  there are no continuation stages.

## Validation

**249 tests passed, one unavailable-CUDA test skipped** in 65.89 seconds.
Coverage includes default CLI/Python/subprocess selection, explicit comparison
profiles, actual compiled continuation, coarse/single-object/angular/geometric
fallbacks, training/evaluation separation, original topology/optimizer guards,
failure accounting, saved prediction replay and video endpoint provenance.

**Both fresh default-CLI workers pass**, starting from the original states and
observations:

| Scene | Full CLI time | Route | Accepted steps | Difference from SPD-006 final coefficients |
|---|---:|---|---|---:|
| Death | 46.274 s | Readiness skip + independent endpoint checks | No continuation | 0 |
| Merge | 173.317 s — 2m53s | Readiness fails; reciprocal full schedule | [16, 1, 2, 3] | 0 |

Topology events also match. Both workers charge exactly eight readiness solves;
merge records 46 reciprocal batches. These scenes exercise the skip and
single-component fallback; the actual default multi-object compiled fit is
covered by the real-continuation regression test. The two-worker validation
took 219.61 seconds sequentially with one BLAS thread per worker.

Their source snapshots, input hashes, exact commands and logs are in
[SPD-007 evidence](../../../../results/validation/speedup/SPD-007-20260917-default-promotion/).
These workers use neither `--inverse-runtime` nor `SDF_INVERSE_RUNTIME` and do
not monkeypatch the normal continuation entry point. The final seal verifies
312 files, all 219 current/frozen source hashes, and the four consumed SPD-006
reference-file hashes. [Machine-readable validation](../../../../results/validation/speedup/SPD-007-20260917-default-promotion/validation.json)
records `PASS`.

This is default-dispatch and quality validation, not a new matched speedup
measurement or an all-twelve-scene campaign. The timing evidence remains
[SPD-006](../iteration_06/01_results.md): 17m29s for central ellipse/star and
21m32s for two stars, 4.5%/5.6% less time than reciprocal + readiness in those
matched runs. All earlier sealed artifacts remain unchanged.

The next performance target remains geometry-validation reuse and the separate
true-analytic constraint-policy comparison, as described in the
[geometry follow-up](../iteration_05/02_proposals/02_geometry_cost_followup.md).
