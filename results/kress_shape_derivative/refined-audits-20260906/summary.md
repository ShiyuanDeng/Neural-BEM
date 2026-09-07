# Complete discrete Kress derivative: bounded validation

All finite differences call the unchanged production forward on perturbed continuous curves.
Analytical JVPs and conjugate-adjoint contractions include A, RHS, receiver map and the direct incident term for total fields.

Discrete gate: 96/96 case/node/direction records passed.
Finest-grid independent/reference-refinement gate: True.
Physical derivative refinement and independent oracle checks are separate from that fixed-node gate.

| Case | Direction | N | Best same-branch FD mixed ratio | Adjoint/JVP difference |
|---|---|---:|---:|---:|
| circle | translation_x | 128 | 1.475e-02 | 5.204e-17 |
| circle | translation_y | 128 | 6.765e-03 | 1.605e-17 |
| circle | scale | 128 | 8.793e-05 | 2.279e-16 |
| circle | shape_mode4 | 128 | 1.721e-04 | 1.903e-17 |
| circle | interior_epsr | 128 | 9.625e-05 | 2.082e-17 |
| circle | exterior_epsr | 128 | 1.807e-04 | 2.494e-16 |
| circle | mixed | 128 | 1.120e-04 | 7.394e-17 |
| circle | tangential_phase | 128 | 1.494e-02 | 6.633e-17 |
| ellipse | translation_x | 128 | 5.871e-03 | 1.388e-17 |
| ellipse | translation_y | 128 | 1.128e-02 | 5.096e-17 |
| ellipse | scale | 128 | 2.940e-04 | 4.012e-17 |
| ellipse | shape_mode4 | 128 | 1.958e-04 | 2.288e-17 |
| ellipse | interior_epsr | 128 | 5.360e-05 | 4.280e-17 |
| ellipse | exterior_epsr | 128 | 2.018e-04 | 8.457e-17 |
| ellipse | mixed | 128 | 5.872e-05 | 1.605e-17 |
| ellipse | tangential_phase | 128 | 8.353e-03 | 3.495e-16 |
| star | translation_x | 128 | 4.380e-03 | 4.510e-17 |
| star | translation_y | 128 | 1.061e-02 | 7.546e-17 |
| star | scale | 128 | 1.768e-04 | 1.691e-17 |
| star | shape_mode4 | 128 | 6.679e-05 | 4.619e-17 |
| star | interior_epsr | 128 | 1.779e-04 | 5.898e-17 |
| star | exterior_epsr | 128 | 1.939e-04 | 9.888e-17 |
| star | mixed | 128 | 1.430e-04 | 1.119e-16 |
| star | tangential_phase | 128 | 2.647e-02 | 8.405e-16 |
| zero_contrast | translation_x | 128 | 1.149e-03 | 6.653e-16 |
| zero_contrast | translation_y | 128 | 1.047e-03 | 1.866e-15 |
| zero_contrast | scale | 128 | 1.343e-03 | 4.721e-15 |
| zero_contrast | shape_mode4 | 128 | 3.151e-03 | 3.775e-15 |
| zero_contrast | interior_epsr | 128 | 7.338e-06 | 1.776e-15 |
| zero_contrast | exterior_epsr | 128 | 7.751e-05 | 1.776e-15 |
| zero_contrast | mixed | 128 | 4.288e-05 | 1.776e-15 |
| zero_contrast | tangential_phase | 128 | 1.117e-03 | 9.310e-15 |

Total wall time: 77.77 s.
The experiment differentiates a declared finite-dimensional, fixed-correspondence curve path; it does not return a uniquely determined arbitrary normal-gradient density.
No production optimizer, topology policy, or quadrature default was changed.
