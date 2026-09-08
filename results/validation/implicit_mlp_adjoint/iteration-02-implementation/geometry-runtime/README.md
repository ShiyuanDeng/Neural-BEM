# Stage 0 polygon replay, 2026-09-08

`report.json` records exact scalar/vectorized intersection equality for 25 unique
polygons (13,417 vertices total): the real saved circle state 60 and star state 47
production extraction and both conversion-audit levels, plus near-contact cases.
`polygons.npz` preserves the replay arrays under their content hashes.

Both implementations give identical full geometry outcomes, conversion metrics,
and accepted curve arrays. A fresh, deliberately underresolved bandwidth-8 fit
of the saved star state rejects with the identical conversion-distance reason.
Historical rejected candidates cannot be replayed: the September-8 bundles saved
rejection metadata, but did not save those proposed weights or polygons. The fresh
underresolved fit is not presented as a historical candidate.

The scalar predicate took 10.94 s over the unique corpus; the vectorized predicate
took 0.89 s (12.3 times faster). Frozen geometry builds measured 5.47 s replay /
1.23 s vectorized for the circle and 10.50 s replay / 4.10 s vectorized for the
star. Replay build timings include exact checks and deduplicated scalar answers;
they are not isolated pure-legacy benchmarks. No BEM solve or inverse was run.

Reproduce the 29-second bounded diagnostic:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python audit_implicit_mlp_geometry_runtime.py --max-seconds 90
```

Replay every selected circle/star saved state when desired:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python audit_implicit_mlp_geometry_runtime.py --all-selected-states --max-seconds 120
```

The cap is checked between frozen geometry builds. Supply additional archived
rejected polygons with `--extra-polygon-npz path/to/polygons.npz` if they become
available; every array must be a cyclic `(N, 2)` polygon without duplicated
endpoint. Existing files in the selected output directory are replaced.
