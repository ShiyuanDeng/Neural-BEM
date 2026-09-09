# Radial-Fourier topology challenges

Three user-directed extensions of the iteration-01 topology-birth benchmark
now pass their declared full-profile gates. The inverse never uses truth
geometry for topology proposals or accepted steps. Truth is used only for
qualification and the dashed video overlays.

| Case | Accepted topology path | Training relative L2 | Holdout relative L2 | Worst geometry error | Video |
|---|---|---:|---:|---:|---|
| [Large enclosing circle → two circles](challenge-suite-20260909-091144/large-split/README.md) | Low-frequency background-TD replace-one-by-two | `1.93e-7` | `1.19e-6` | `1.08e-8 m` | [MP4](challenge-suite-20260909-091144/large-split/large-split.mp4) |
| [Far wrong circle → two circles](challenge-suite-20260909-092226/far-circle/README.md) | Low-frequency background-TD replace-one-by-two; obsolete component removed | `1.93e-7` | `1.19e-6` | `1.08e-8 m` | [MP4](challenge-suite-20260909-092226/far-circle/far-circle.mp4) |
| [Middle circle → diagonal ellipse and star](challenge-suite-20260909-093211/ellipse-star/README.md) | Low-frequency replace-one-by-two, K1→K2→K5 shape continuation, then 0.5/1.5-GHz refinement | `5.68e-3` | `5.25e-2` at 2.5 GHz | `5.52e-4 m` | [MP4](challenge-suite-20260909-093211/ellipse-star/ellipse-star.mp4) |

Every topology replacement decreased the real objective at both 64- and
128-node component resolutions. The circle observations use the independent
multi-cylinder cylindrical-harmonic oracle. The ellipse/star observation uses
independent analytic truth curves discretized at 256 nodes per component.

Only the successful case bundles listed above are retained as repository
evidence. Earlier local exploratory runs exposed two useful adverse regimes:
an additive birth alone leaves a far-away ghost component, and accumulating
topological derivatives at 1.5 GHz can select a star-edge scattering hotspot
instead of the component centre. The successful policy therefore uses 0.5 GHz
for topology decisions and activates the higher training frequency only after
the two components and radial modes are established.

Reproduce one or all cases with `run_radial_fourier_topology_challenges.py` and
the `--profile full` option.
