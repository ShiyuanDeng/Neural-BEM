# Method-B implicit-parameter evidence

These runs optimize small implicit-model parameter sets, rebuilding extraction,
Method B and the selected MOD/Kress forward prediction for each objective.
They supply controls for the active [strict MLP + Method B repair](../../../docs/pipelines/strict_mlp_method_b.md).
They are not proof of scalable strict full-network recovery.

| Bundle | Initialization and target |
|---|---|
| [wrong-circle-mie-20260902](wrong-circle-mie-20260902/summary.md) | Wrong circle to circle; Mie observations |
| [wrong-ellipse-mie-20260902](wrong-ellipse-mie-20260902/summary.md) | Non-distance ellipse to circle; Mie observations |
| [random-feature-implicit-mie-20260902](random-feature-implicit-mie-20260902/summary.md) | Seeded random-feature implicit field to circle; Mie observations |
| [wrong-star-nystrom-20260903](wrong-star-nystrom-20260903/summary.md) | Wrong star controls to five-lobe star; independent Nyström observations |

Original IDs are retained; recorded UTC dates take precedence over suffixes.
Full outcomes and rerun dispositions are in the [catalogue](../../README.md).
