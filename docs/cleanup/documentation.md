# Documentation cleanup

Question: which documentation is needed to understand the code and the current
Stage 1 comparison, without keeping earlier development work in the active tree?

## User decision, 2026-11-17

Keep only the relevant Stage 1 work under `docs/iterations/`. Remove the general
README, evidence, directions and workflow documents outside iteration folders.
Keep `docs/reference/` because it helps explain the code. Keep `docs/cleanup/`
as the record of decisions and implementation.

The user wants the same reduction of old material as the results cleanup.
This scope applies to `docs/`; repository-root and package documentation are
outside this change.

## Selected layout

```text
docs/
  reference/
  cleanup/
  iterations/
    AGENTS.md
    evaluate_our_method/
      01_measure_clean_and_noisy_recovery/
        plan.md
        results.md
      02_run_ablations/
        plan.md
        results.md
      03_record_untuned_gaugal_reference/
        plan.md
        results.md
```

Each completed activity now has a focused plan and a results summary from the
saved metrics. The original combined plan and earlier proposal were preserved
unchanged in the legacy workspace before the old folder was removed.

The report, figures, comparison tables, old plan and handoff for the run on
2 November 2026 describe the earlier development comparison. They need not
remain in the active documentation tree after cleanup.

## Naming decision, 2026-11-17

User: "stop using this letter name that have no information in it" and
"current iteration name should be changed to baseline_generation".

Use the run date in prose: the Stage 1 run on 17 November 2026 and the earlier
TG-002 comparison run on 2 November 2026. Add the purpose when a date alone
could be ambiguous. That first rename used `baseline_generation/`; the later
action-based structure in D21–D22 supersedes it.

The old identifier for the November comparison was also used for a separate
SingleTX case-8 plan dated 5 October 2026 on the continuation branch. Do not
merge these experiments when replacing names.

Historical result paths, execution records and saved settings retain their
original strings. They are evidence of what ran. The current import command
is `import-gaugal-2026-11-02`; it reads the same saved clean reconstructions.

## Removals

- `docs/README.md`, `docs/evidence.md`, `docs/directions.md`.
- `docs/iterations/README.md` and `implementation_principles.md`.
- The old anchoring, inverse reorganisation, cleaned interfaces, frequency
  interpolation, geometry charts, geometry updates, Haibing, linear solves,
  overnight, policy speed and trial curves tracks.
- The remaining `gaugal_comparison/` tree. Its Stage 1 material was initially
  retained in `baseline_generation/`, then reorganised under D21–D22.
- The Stage 2 `baselines/` track, including its four previously uncommitted
  files, now preserved in the original workspace.

## Preservation and dependencies

Tracked history is available at
`fff46e343da899314b7057e4fbd931559d205c91` on `organised`. The later transfer
decision below also preserves the material locally in the original workspace.

The four previously untracked baseline decision files were copied byte for byte
to the original workspace before their organised copies were deleted.

Historical citations in retained docs now point to their preserved local copies.
Current code explanations and user decisions remain here. Current results and
sealed inputs were not removed or changed. The later D19 follow-up removed the
remaining duplicate legacy outputs from `development_results/`.

The November 2 report and its `comparison.json` now live in the original
workspace. The historical report and figure readers use that workspace, as
does the saved clean GauGal import. The current Stage 1 runner reads `results/`.

## Implementation status

Stage 1 now lives in the three activity folders shown above. Each has `plan.md`
and `results.md`; current links use those paths. Results were summarized from
saved evidence without fitting or rescoring.

**Complete.** The initial deletion removed 61 files after verifying their copies.
The subsequent iteration reorganisation added the activity plans and results
and preserved the two replaced source documents in the legacy workspace.

Preserved 7,116 files (1,369.01 MiB) in the original workspace: 6,912 missing
paths and 204 differing versions. Another 181,305 source path/version pairs
were already present. No existing legacy file was overwritten.

The [legacy index](../../../Neural_SDF_BEM_AD/legacy_from_organised/2026-11-17/index.json)
records source revisions, hashes, destinations and all 61 deletions. The
[legacy guide](../../../Neural_SDF_BEM_AD/legacy_from_organised/2026-11-17/README.md)
explains where to find the restored material.

## Transfer to the original workspace, 2026-11-17

Question: can the original workspace hold all documentation and results removed
by the October cleanup, the earlier results cleanup and this documentation cleanup,
without replacing its existing versions?

Destination: `/home/drdeng/Neural_SDF_BEM_AD`, on its existing
`feature/shape-frequency-continuation` branch. The organised workspace keeps
`reference/`, `cleanup/`, `evaluate_our_method/`, current results and the sealed
TG-002 inputs. Historical development outputs are read from the original workspace.

Use the saved trees before the October cleanup, before the November refits,
before the results cleanup, and before this cleanup. Also preserve the current
contents of every file removed now, including the four uncommitted baseline files.

Copy missing paths into the original workspace. If the original path already
contains a different version, preserve the incoming version under
`legacy_from_organised/2026-11-17/versions/`, with an index recording its source
and destination. Never overwrite existing legacy work.

Verify copied bytes against their Git blobs or current source bytes before
deleting the organised copies. Repoint surviving documentation to the actual
legacy destination. Every copy and each deletion source matched its Git blob hash. No solver runs
or documentation tests were performed.

## Remaining legacy-result duplicates, 2026-11-17

Under D19, removed another 486 verified legacy files from `development_results/`
and replaced its old README with an input-location note. Only the sealed TG-002
bundle remains there. The legacy index records these sources and destinations.

The importer and historical figure reader loaded all 30 saved cases from the
original workspace; the importer retained the saved settings exactly and was
stopped before writing. No fitting or rescoring was performed.

## Reorganise current iterations, 2026-11-17

Question: can each completed part of the 17 November study have its own
verb-named activity, with a plan and results together, without losing the
original combined decisions?

The user approved the new iteration rules and requested "reorganise current
iterations". Split the work into clean/noisy recovery, ablations and the untuned
GauGal reference. The independent forward check stays with clean/noisy recovery.

**Complete.** Created six files under `evaluate_our_method/`. Reports summarize
all 370 saved scores: 120 core BEM fits, 200 ablation fits, 20 new GauGal fits
and 30 imported clean GauGal fits. No experiments or rescoring were run.

Preserved the exact combined plan and proposal under the original workspace's
`docs/iterations/baseline_generation/`, with hashes in the legacy index. Removed
the old active folder and updated README, decision-history and code pointers.
The plans explicitly identify this as a reorganisation after execution.

## Shorten the final comparison report, 2026-11-19

Under D24, use saved final fits to show each method on shared simulation
cases and give the measured cylinder a separate comparison.

**Complete.** The [report](../iterations/final_comparison_report.md) shows
the clean circle and kite across four measurement settings, followed by the four
measured-cylinder fits. The activity reports retain the development evidence.
