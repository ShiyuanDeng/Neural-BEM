# BRG checkpoint patches, 17 November 2026

Upstream: `flatironinstitute/inverse-obstacle-scattering2d`, commit
`bda24bddbf4562497280b671bc174ef891b47c6b`.

| Patch | Status | Purpose |
|---|---|---|
| `01-wrapper-script-paths.patch` | Applied in memory by the wrapper | Supply startup once and place generated data under BRG results |
| `02-remove-undefined-lam-save.patch` | Applied in memory on `data_retry` | Remove an undefined, unused impedance variable from the transmission save |
| `03-preserve-transmission-derivative-parameters.patch` | Applied to external checkout for checks; proposed for full run | Copy `bc` so the geometry derivative receives all transmission parameters |
| `04-update-transmission-wavenumbers.patch` | Applied to external checkout for checks; proposed for full run | Set both wavenumbers at each RLA frequency from the driver's fixed ratio |
| `05-remove-obsolete-driver-argument.patch` | Proposed only; not applied | Remove the unused eighth driver argument; the wrapper already calls with seven |

Only patches 03 and 04 alter files in the external checkout. Their total is
four added lines and one removed line. Patches 01 and 02 describe runtime
script edits; the executed star source is saved with its results. The path
in patch 01 names the first data attempt; retry output has its own folder.

The seven-argument wrapper calls avoid patch 05 in the checked path. No
coefficient-normalization fix, multi-component repair or zero-gradient
optimizer change has been made. The paper's unpublished driver behavior
cannot be established from these checks.

To reproduce in a fresh pinned checkout, build its MEX files and apply 03.
Run `python experiments/baselines/brg/run_stage.py low_frequency_stale_disk`
from the main repository: it must fail comparison with the direct reference.
Then apply 04 and run the same command with `low_frequency_fixed_disk`:
all three residual and curve differences must be below 1e-10.
Existing output directories are deliberately protected against overwrite;
use a fresh checkout/output location for reproduction. The frozen input is
`results/brg/examples/low_frequency_stale/low_frequency_data.mat`.

The earlier exact-true-shape harness is retained as failure evidence. Do not
rerun `low_frequency_fixed`: the exact-fit zero-gradient path crashes the
upstream MEX. The accepted check uses the shipped unit-disk start instead.

[Results](../../../docs/iterations/brg_adaptation/01_run_published_examples/results.md)
and `checkpoint_source_hashes.json` record the checked source state.
