# Saved SIREN input snapshot

`siren_circle.json` preserves the exact float64 network state, constructor and
Method B geometry configuration from
`results/inverse/implicit_mlp/2026-09-08/circle/kress_model.pt`, iteration 60.
The original file is a historical ignored local artifact; it is not modified
or required by the reproduction command.

The source path, original file SHA256, model class, accepted iteration and
training loss are inside the JSON. The benchmark records the JSON's own SHA256
in `../metrics.json`. Values were obtained with a `weights_only=True` read of
the original state and serialized as plain JSON; reconstruction requires no
pickle loading. JSON float serialization round-trips these float64 values
exactly. The script reconstructs `SirenImplicitField2D` and loads the state
without training or fitting.
