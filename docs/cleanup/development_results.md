# Development results reorganisation

## User decision, 2026-11-17

Keep the agreed development evidence, name it to distinguish it from final results,
and leave a new `results/` directory empty. The retained folder is
[`development_results/`](../../development_results/README.md).

## What changed

- Retained 620 files (46.1 MiB before index and documentation)
  from the original 7146 files (1.34 GiB).
- Kept the complete sealed TG-002 inputs, 60 selected BEM endpoints, 30 GauGal
  endpoints/images, settings, failure records and compact development checks.
- Preserved the entire old tree at commit `af68817f7917cfa927355862dad4e3929c098321`.
  The [index](../../development_results/archive_index.json) records every original Git blob.
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
