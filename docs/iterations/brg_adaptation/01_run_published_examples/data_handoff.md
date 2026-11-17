# BRG data handoff for the later BEM comparison

This records the public source at `bda24bddbf4562497280b671bc174ef891b47c6b`.
No BEM adapter has been implemented in activity 01.

## Files and layout

The shipped star data are in
[`star3_ik1_nk17_tensor_data_Transmission.mat`](../../../../results/brg/examples/data_retry/star3_ik1_nk17_tensor_data_Transmission.mat).
The clean cavity diagnostic data are in
[`low_frequency_data.mat`](../../../../results/brg/examples/low_frequency_stale/low_frequency_data.mat).
The star file is a MATLAB v5 MAT file; wrappers may also save v7.3/HDF5 files.

The normal upstream data container is a cell array `u_meas`, one struct per
frequency. The diagnostic names its equivalent cell array `data`.

| Field | Meaning and shape |
|---|---|
| `kh` | Exterior wavenumber, in inverse coordinate-length units; not GHz |
| `tgt` | Real `2 × N` receiver coordinates, repeated for each incidence |
| `t_dir` | `N × 1` incident propagation angles in radians |
| `uscat_tgt` | Complex `N × 1` scattered field at each paired receiver/angle |
| `err_est` | Optional analytic forward-check estimate; absent in the diagnostic |

The drivers build `meshgrid(t_receiver,t_direction)` and then flatten in
MATLAB column order. Direction varies fastest: all directions at receiver 1,
then all directions at receiver 2, and so on. In MATLAB,
`reshape(uscat_tgt,[n_direction,n_receiver]).'` yields a receiver-by-direction
table. The transpose must **not** conjugate. In NumPy, reshape the vector to
`(n_receiver,n_direction)` in C order. Prefer the explicit pairs when importing.

Angles start at zero and run counterclockwise without a repeated endpoint.
Receivers lie on radius 10. Incidence angles describe propagation directions,
not source positions on the receiver circle. The cavity driver uses
`ceil(10*kh)` receivers and directions, giving 10, 13, 15 at the diagnostic
frequencies. Preserve this ceiling for activity 01; the paper uses a floor.

## Fields, signs and scaling

[`compute_fields.m`](https://github.com/flatironinstitute/inverse-obstacle-scattering2d/blob/bda24bddbf4562497280b671bc174ef891b47c6b/src/%2Brla/compute_fields.m)
uses unit-amplitude incident plane waves with positive spatial phase.
Its `uscat_tgt` is the finite-radius exterior **scattered** field. It is not
the total field or a far-field amplitude with radial factors removed.
No source-strength calibration or receiver normalization is applied.

The outgoing Green function is the first-kind Hankel function with the
usual imaginary-quarter prefactor (`src/fortran/helm_kernels.f`). This is
the negative-time-phase convention. No conjugation is needed for BEM's same
time convention. Preserve both amplitude and the coordinate-wavenumber scale.

`bc.transk` lists interior first and exterior second. The cavity driver
sets `bc.q=1.5`, a wavenumber ratio, despite the misleading variable name
`q_plus_1`. Thus the squared material ratio is 2.25, and the susceptibility
relative to the background is 1.25. Both `transa` and `transb` are ones:
field and normal derivative are continuous, with equal density.

The paper defines its example contrast as the interior/exterior squared
wavenumber ratio in section 4.1. Its values below one correspond to negative
susceptibility; the later known-contrast adapter must account for that.
The opening sentence of section 4 reverses the ratio, but equation 1,
Remark 1.1 and section 4.1 resolve the convention used here.
[Paper](https://arxiv.org/html/2210.11607).

The shipped star generator is a separate dissipative example: interior
speed 0.5, dissipation `sqrt(3)*5+0.5`, and frequency-dependent complex
transmission coefficients. Its data must not be labeled as a clean,
real-contrast paper cavity case.

## Geometry, settings and timings

The shipped cavity is `geometries.charlie_cavity(10.2,n)`. Its identity with
the paper cavity is unverified; the paper figure differs in orientation
and scale. Geometry structs contain
`xs`, `ys`, parameter derivatives, speed, curvature, parameter step and
perimeter; use the ordered Cartesian boundary for later shape scoring.
The driver saves an initial 300-point truth, then generates at the larger
of 500 points and its 30-points-per-exterior-wavelength rule.

Activity 01 preserves shipped settings: steepest descent, Gaussian update
filter, 100 iterations, update stop 1e-3, default residual stop 1e-5,
curvature limit 0.1, minimum curvature band 20, and length-scaled update
modes. These differ from the paper settings and are not a table-B result.

Eight MATLAB compute threads are recorded in every stage's metadata.
The three corrected one-step RLA calls took 1.13, 1.14 and 1.16 s; those are
diagnostic timings, not complete-fit timings. MATLAB launch and export time
are included in each `run.json` wall time but excluded from inner timings.
CSI may have overlapped these runs. The full shipped run took 1395.81 s process wall time (122.04 s data,
1118.52 s inverse calls); the k=30 solve took 4.39 s for one iteration.
These are indicative because CSI overlapped. Native-versus-adapted BEM
timings remain pending.

In the [information chain](../../../reference/inverse_information_chain.md),
the later adapter needs A3 plane-wave inputs, A4 unpaired receiver/direction
tables and B5 the same observed scattered field. These BRG wrappers are
outside the default BEM path; no maintained solver file was edited.

## Full shipped run storage

The resumable wrapper writes one `local/data_NNN.mat` per frequency under
`results/brg/examples/shipped_cavity_full/`; its `measurement` struct uses
the same field layout described above. `frequency_NNN.mat` holds the compact
final curve and residual/timing record. Exact continuation structs are
`local/state_NNN.mat`, with full logs alongside them. Bulk files remain
local; `bulk_manifest.json` carries commands and SHA-256 values.

The generator's `err_est` is invalid for this shipped cavity because its
manufactured-solution source is outside the object. It does not measure
the plane-wave data error. Keep this limitation visible when importing data.
