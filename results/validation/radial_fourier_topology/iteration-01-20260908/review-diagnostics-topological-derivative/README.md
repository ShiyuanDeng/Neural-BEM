# Review diagnostics: the current-domain topological derivative

Probes run on 2026-09-08 by Claude to support
[`03_claude_review.md`](../../../../../docs/iterations/radial_fourier_topology/iteration_01/02_proposals/03_claude_review.md),
the second review of the
[topology-aware radial-Fourier brief](../../../../../docs/iterations/radial_fourier_topology/iteration_01/02_proposals/01_radial_fourier_topology_initial_instructions.md),
at `3835f69f378323d3ee6752e069a79d74f1f3207b`.

**These probes run no BEM, no inverse and no optimizer.** Every forward value
comes from the independent `multicylinder_ref` cylindrical-harmonic oracle, so
no Kress discretization question is entangled with the derivative question
being asked. The scalar objective is the production
`sdf_inverse.optimization.normalized_complex_residual` helper with unit
frequency weights. Nothing in the repository is modified. Total cost is about
22 seconds on one thread.

| File | Contents |
|---|---|
| `topology_probe_common.py` | Shared scene, objective and topological-derivative expressions |
| `topological_derivative_asymptotics.py` | G1 probe: finite-radius insertion quotients against the derivative |
| `topological_derivative_asymptotics.txt` | Its full-precision output |
| `topological_derivative_localization.py` | G2/G3 probe: frequency sweep, threshold region, birth line search |
| `topological_derivative_localization.txt` | Its full-precision output |

## Scene and conventions

The scene is the repository's declared two-circle case, `config/two_circle_config.py`:
components of radius `0.035 m` at `(0.43, 0.50) m` and `(0.57, 0.50) m`, sand
exterior `epsr = 6`, plastic interior `epsr = 3`, both lossless and nonmagnetic.
The acquisition is the one in
`pytest/solver_comparisons/test_two_circle_comparison.py`: 24 paired ring
stations at `0.30 m` standoff about `(0.50, 0.50)` with the `0.06 m`
transmitter/receiver offset, and the `1e-6` source strength of
`run_sdf_inverse_comparison._build_problem`.

The measurement set is the paired diagonal only. The objective is

    J = 0.5 * sum_f (w_f / s_f^2) * sum_s |p_sf - d_sf|^2

with `s_f` the fixed observed-column norm. The free-space Green function is
`0.25j * H0^(1)(k r)`, matching both the Kress receiver operator and the
oracle's `line_source_incident_field_matrix`.

## The expression under test

    D_T J(z; Omega) = sum_f (w_f / s_f^2)
                      Re[ (k_i^2 - k_e^2)
                          sum_s conj(p_sf - d_sf) u_sf(z) G_f(z, x_r(s)) ]

`u_sf(z)` is the current-domain total field at `z` for physical source `s`,
carrying the source strength. `G_f(z, x_r)` is the current-domain total field at
`z` for a **unit** line source at the paired receiver, which is the reciprocal
form of the receiver-to-`z` Green response. There is no leading minus sign and
no factor of one half.

`topological_derivative_asymptotics` compares this against

    Q_rho(z) = (J(Omega + B_rho(z)) - J(Omega)) / (pi rho^2)

over a decreasing radius ladder, for the empty background (T0) and for the
non-empty current domain `Omega = {A}` (T1).

`topological_derivative_localization` computes the field on a declared
inspection disk of radius `0.20 m` about the scene centre — chosen so every
inspection point stays `0.10 m` clear of every source and receiver, since the
raw field is logarithmically singular at the stations — at two grid
resolutions, then applies the relative threshold `D_T J < (1 - C0) min D_T J`,
labels 4-connected regions, seeds a circle at the equivalent-area radius of the
region holding the global minimum, and scores each backtracked radius with the
unchanged objective.
