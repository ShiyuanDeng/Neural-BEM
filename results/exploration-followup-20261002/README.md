# Follow-up closure and reusable cleaned-interface work

The user closed the campaign based on the outdated plan and asked to retain
work with demonstrated value for the cleaned interface. All broad scheduling
and long-running continuations were stopped. Scope-change stops are not
numerical failures, final convergence, or completed comparisons.

Work is preserved on the existing `feature/shape-frequency-continuation`
branch. No branch/worktree was created and no merge into another branch was
performed. The initial campaign is recorded at `5ae16efb`; its
[provenance bundle](../exploration-20261002/README.md) remains historical.

The reusable audit fix is isolated in commit **`8e619088`**, containing only
the maintained runner audit change and self-contained cleaned-interface tests.
The later archive commit keeps the experimental adapters and evidence separate.
The isolated five-frequency N512/1024 check reduced peak process RSS from
2,211.1 MiB to 565.3 MiB (74.4%), with identical numerical outputs and 30 work
units. Timings were 31.79 and 32.37 seconds; no speedup is claimed. RSS includes
the interpreter/import baseline, which dominates the streamed run's peak.

## Retained findings

| Work | Result | Consequence |
|---|---|---|
| [Cleaned audit](../exploratory_continuation/maintained_policy/README.md) | Streaming and unchanged-endpoint reuse qualified against the original audit | Retain a separate reusable code fix; preserve numerical tolerances and policy |
| [Fresnel source](../fresnel/source_qualification/README.md) | Incident-only multipoles qualify through 4 GHz under the stated scalar model and improve matched measured-data residuals | Retain source value/gradient/Hessian and shape-JVP primitives as experimental APIs |
| [LSM/full-matrix TD](../initialization-full-matrix-resolved-20261002/README.md) | Both arms complete 12 jobs and pass 5/12, with explicitly added initialization measurements | No evidence to change the initialization default |
| [Stopping floors](../stopping-floor-20261002/README.md) | 161 accepted FD steps give 2.41× loss reduction; modest geometry improvement; still descending | Retain resolution-aware audit evidence; do not infer convergence or change optimizer defaults |
| [Maintained policy](../exploratory_continuation/maintained_policy/README.md) | Two completed real-policy cases plus explicitly interrupted partial runs | Coupled adapters remain experimental; the planned superiority comparison is incomplete |

The central [research report](../../docs/reports/exploration_2026-10-02.md)
separates these follow-ups from the initial ten-priority campaign. Unknown
topology on measured data, a complete matched maintained-policy comparison,
and eventual TOP-009 recovery remain unestablished and are closed research
items in this campaign, not queued work or resolved scientific questions.

## Validation and provenance

[validate.sh](validate.sh) gives the exact CPU regression command;
[tests.log](tests.log) records **119 passed**, with 14 dependency deprecation
warnings and no skips. It includes the cleaned interface,
new audit/adapter/source/initializer/stopping checks, the benchmark CLI, and
the first campaign's solver and experiment regressions.
The [separate portable-fix check](portable-audit-tests.log) loads the exact
audit-only runner blob committed in `8e619088`, excluding the experimental
adapter hooks, and passes all 23 selected cleaned-interface tests.

[manifest.json](manifest.json) records source and retained artifact SHA256
hashes. It is a post-run inventory. Individual execution manifests and source
snapshots retain their original identities, including superseded pilots and
interrupted trajectories. Later report edits and the streaming-audit change
are not represented as the code used by earlier running processes.

The reviewed initializer map labels unattainable probes explicitly. Raw
qualification data, failed pilot records, work receipts and post-fit-only
geometry scoring are retained. Concurrent CPU timings are descriptive;
the audit memory comparison uses isolated processes.
Narrow Git attributes preserve the original generated SVG, plan and log bytes
without treating their generated whitespace as source formatting errors.
