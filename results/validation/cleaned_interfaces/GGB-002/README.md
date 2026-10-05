# GGB-002 — Four-frequency follow-up on cylinder case 8

The user approved GGB-002 on 2026-10-05 with "go" after reviewing its
[pre-registered plan](../../../../docs/iterations/CI-SPD/GGB-002_plan.md).
This explicitly requested external scene is an exception to the ordinary
TG-002 scene default. It uses the maintained modal Müller solver and
certified spectral updates with the original centred radius-0.35 m start.
Material is known; this is a shape-recovery control.

The original archive contains only 0.4 GHz observations. The new four-real-
frequency panel is 0.5, 0.75, 1.0, and 1.25 GHz. Observations are generated
independently using the original 93 active pixels, their original coordinates,
and the archived source/receiver conventions. The new 0.5 GHz observations
are shared exactly between the S1 control and F4 arm. Both retain modes
3 -> 7 -> 11. The entire damped/19-frequency continuation recipe is not used.

The field generator has point-cell off-diagonal Green entries and an
equal-area disk self-cell average. Its constants and pixel-current convention
are supported by the pinned [SingleTX physics implementation](https://github.com/gomenei/SingleTX-EISP/blob/772d6eb81269353d7396c85fefa8c0a6d5091477/physics.py)
and the archived operators. The preparation checks those operators directly,
then reproduces the clean archived 0.4 GHz fields to relative 3.22851e-6,
passing the declared 1e-5 gate. Source/receiver positions and the original
pixel-grid rounding are retained; the reduced volume systems are solved in
complex128. This reproduces the archived discrete physical model rather
than claiming continuum-exact data.

The adapter is a byte-identical snapshot of GGB-001's qualified full-matrix
adapter. Its SHA256 is
`f89e99aea299bd0f266b8a6facb844ffd7cf242afc8f2a5f96a2761c990ee084`.
It passes independent Mie field checks at all four frequencies and rebuilt-
geometry derivative checks at the two panel endpoints on CPU and CUDA.

| Artifact | Contents |
|---|---|
| `preparation.json` | Approval, official source provenance, generator gates, CUDA adapter qualification, source hashes and input seal |
| `inputs.npz` | Original target/acquisition, synthetic clean/noisy fields, sigmas, archived 0.4 GHz fields |
| `S1/result.json`, `F4/result.json` | Resolved settings, complete stages/trials, work and physics receipts, endpoint metrics and residuals |
| `S1/endpoint.npz`, `F4/endpoint.npz` | Returned curve, original-grid image, production/refined endpoint predictions |
| `report.md`, `comparison.png` | Per-frequency residuals, optimization evidence and reconstruction panels |
| `validation.json` | Read-back verification of sealed inputs, endpoint residuals, metrics and discrepancy decisions |
| `test_validation.json` | Pre-execution meaningful unit and maintained-package checks |

Source: `experiments/benchmark/ggb002.py` and `ggb002_adapter.py`.
Follow the commands in the plan. Runs use fresh directories and are never
automatically retried or tuned to their outcomes. Original GGB-001 evidence
in Gau-Gal remains unchanged.
