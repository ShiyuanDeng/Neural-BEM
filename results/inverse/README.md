# Inverse evidence

The active research target is [strict MLP + Method B repair](../../docs/pipelines/strict_mlp_method_b.md).
These directories classify actual measured implementations; a directory name
does not certify completion of that repair.

| Directory | Geometry and role |
|---|---|
| [method_b](method_b/README.md) | Small implicit-model recovery through full extraction and Method B |
| [radial_fourier](radial_fourier/README.md) | Explicit radial shape, with strict/omitted/export MLP policies; diagnostic evidence |
| [shape_material](shape_material/README.md) | Explicit radial K2 and one interior material; local and restart controls |
| [neural_metric](neural_metric/comparison-20260906/README.md) | Frozen neural metrics acting on explicit geometry; no fitting during inversion |

Historical MLP-feedback and normal-update runs are in [legacy](../legacy/README.md).
Use the [catalogue](../README.md) for dates, scenes, outcomes and repair implications.
