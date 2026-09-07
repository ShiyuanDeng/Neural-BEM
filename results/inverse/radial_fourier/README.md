# Explicit Radial Fourier inverse

These runs optimize an authoritative explicit radial curve. Even with
`legacy_strict` MLP fitting, they do not make the MLP own accepted geometry.
Canonical reconstruction succeeds in the recorded continuation and
representation-policy controls. This is the currently working reconstruction
reference for the [implicit MLP pipeline](../implicit_mlp/README.md).
Success on the explicit curve does not establish accurate neural fitting/export;
the saved MLP representation gates still fail in the milestone runs. Some
material/metric variants also retain failed reconstruction arms.

- [September 4 radial-continuation milestone](mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/summary.md): accurate canonical recovery, separate MLP gate failure.
- [Representation policies](representation_policies/README.md): identical-data strict, curve-only and final-export studies.
- [Shape/material variants](shape_material/README.md): fixed geometry or radial K2 with material parameters; grouped here by explicit geometry ownership.
- [Frozen neural-metric variants](neural_metric/comparison-20260906/README.md): radial geometry with different update metrics; no neural training in the inverse.
- [Pipeline explanation](../../../docs/pipelines/explicit_radial_fourier.md): exact ownership and current entry points.

Read reconstruction and representation outcomes separately in the [catalogue](../../README.md).
