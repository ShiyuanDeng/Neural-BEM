# Development results reorganisation

## User decision, 2026-11-17

Keep the agreed development evidence, name it to distinguish it from final results,
and leave a new `results/` directory empty. The retained folder is
[`development_results/`](../../../Neural_SDF_BEM_AD/legacy_from_organised/2026-11-17/versions/development_results_cleanup/development_results/README.md).

## What changed

- Retained 620 files (46.1 MiB before index and documentation)
  from the original 7146 files (1.34 GiB).
- Kept the complete sealed TG-002 inputs, 60 selected BEM endpoints, 30 GauGal
  endpoints/images, settings, failure records and compact development checks.
- Preserved the entire old tree at commit `af68817f7917cfa927355862dad4e3929c098321`.
  The [index](../../../Neural_SDF_BEM_AD/development_results/archive_index.json) records every original Git blob.
- Updated benchmark and GauGal input readers, the saved-comparison reader and source
  links. New run destinations still use `results/`; historical raw records are unchanged.
- Preserved the native GauGal timings as a separate compact table.

## Checks

Before removal, all original result files matched the committed tree and there
were no untracked or ignored result files. Every retained copy was checked against
its original SHA-256 before documentation links were adjusted.

Verified the TG-002 seal and loaded all 30 cases through both input readers.
All 90 comparison endpoints, images/settings and diagnostic records are present;
the comparison JSON is numerically unchanged. No solver experiment was run.

Confirmed that results/ is empty and retained files are not ignored by Git.

## Later preservation in the original workspace, 2026-11-17

The user subsequently asked to keep all removed documentation and results
locally in `/home/drdeng/Neural_SDF_BEM_AD`, including earlier cleanups.

The transfer restored missing files from the recorded pre-cleanup trees and
kept differing versions separately. It also preserved the pre-refit November
results, including failed-run evidence. Existing legacy files were not replaced.

See [the documentation cleanup record](documentation.md) and the
[legacy index](../../../Neural_SDF_BEM_AD/legacy_from_organised/2026-11-17/index.json).
The retained development inputs here and the current `results/` are unchanged.

## Remove the remaining local legacy copies, 2026-11-17

Question: can the organised workspace keep only current results and the sealed
TG-002 inputs, with historical outputs read from the original workspace?

The user asked to move legacy results as well. The earlier transfer already
preserved the full historical results and compact development copies. Verify
the remaining copies before removing them from `development_results/` here.

Keep `development_results/TG-002/` unchanged. Update the clean GauGal import and
historical report readers to use `/home/drdeng/Neural_SDF_BEM_AD/development_results/`.
Preserve original paths inside saved manifests as historical provenance.

Verify the saved import settings and case list without fitting, writing results
or rescoring. No new experiment is needed.

**Complete.** Verified all 487 non-input source files against their preserved
copies, removed 486 legacy files, and replaced the old README with an input-location
note. The 136-file TG-002 bundle is unchanged.

The clean GauGal importer found all 30 historical cases and reproduced the saved
run settings, stopping before any write. The historical figure reader loaded all
30 reconstructions from the original workspace. No fitting or rescoring was run.
