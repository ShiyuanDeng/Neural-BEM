# One simulated TG-002 case

## What the package supplies

The pinned CC-CSI tree supplies measured-data drivers, background FDFD
assembly (`MaxwellFDFD_add/FDFDpars.m`, `csi_build_system.m`,
`mycreate_eqTM.m`) and the analytic TM observation kernel in
`functions/ReadFreData.m`. It does not ship a complete synthetic target
driver for its paper's synthetic rows. The pinned MaxwellFDFD dependency
also has `maxwell_run`, `solve_eq_direct` and a dielectric-cylinder example.
These are sufficient to build a forward from its own material/matrix
builders; no BEM-generated data are used in this preparation.

Our driver is `experiments/baselines/csi/generate_synthetic.m`. It supplies
the true dielectric map to the unchanged native `FDFDpars` material path,
solves its sparse TM system for scattered fields, and applies the unchanged
native receiver kernel. A dummy point source is required to build the
matrix; its returned RHS is discarded. Actual illumination uses the
native calibrated incident fields and the dielectric scattered-field RHS.
This is an owned assembly driver, rather than a claimed reproduction of
an unavailable author synthetic-data script.

## Frozen truth and two grids

Only `circle` is prepared. `experiments.benchmark.scenes.truth_fixture`
provides its frozen boundary and placement. Multiplication by `S.LENGTH`
expresses it in metres relative to the acquisition centre. There is no
shape rotation, recentering on the target, scale change or fitted position.
The exact boundary is sampled at 8192 points for material membership.
The cylinder has radius 50 mm and centroid (18.021345,12.618682) mm.
Relative permittivity is 4, hence susceptibility 3 in vacuum.

Both grids have half-width 103.75 mm. Forward cells are 0.625 mm on
332-by-332 nodes; inversion cells are 1.25 mm on 166-by-166 nodes. Native
TM material values live at dual cell centres. The wrapper samples the
polygon there and supplies the resulting 1-or-4 array through `OBJ`.
The native `mean_material_node` averages the four neighbours onto Ez's
primary grid. `forward_material.mat` retains both arrays. The separately
saved `geometry.mat` also holds a point-membership primary-grid map for
viewing the truth; it is not silently substituted for the native averaged
material array. There is a five-cell PML, as in the shipped assembly.

Each frequency checks that the native true matrix, divided by its
normalized frequency squared, equals the native normalized vacuum matrix
minus the diagonal Ez susceptibility, to relative tolerance 1e-12.
The relative scattered-system solve residual must be below 1e-9.
These are numerical consistency checks, not an independent physical
qualification. The later BEM forward must cross-check the true boundary.

## Table, mask and calibration

The first-opus layout keeps 36 transmitters at radius 0.72 m and 72
possible receivers at radius 0.76 m. Each source uses 49 measured
receivers, in the original `dielTM_dec8f` row order. All eight frequencies
1-8 GHz are present. Receiver indices in the template preserve the mask.
The seven columns are source index, receiver index, GHz, real/imaginary
total field, real/imaginary incident field. They have 49*36*8 = 14112 rows.
The truth and forward grid are never inputs to the inverse.

Source index becomes 10*(index-1)-2.5 degrees; receiver index becomes
5*(index-1) degrees. Positions use radius*cos(angle), radius*sin(angle).
The incident amplitude is the canonical unit scalar Green function
`1j/4*besselh(0,1,-k*r)`. This is independent of grid cell size.
Native `ReadFreData` calibrates every source at its middle measured
receiver (index 25 of 49). Its scalar normalization is incident divided
by its analytic incident prediction. For this synthetic source it should
be `1/omega_normalized^2`, real and identical across sources. Forward and
inverse use different normalized omega, but the same physical incident
field. The resulting values are recorded; no bypass of calibration is
used. Native scattered data are total minus incident.

The phasor convention is exp(+j omega t), with outgoing Hankel-2 behavior
through the negative argument in Hankel-1. Later BEM ingestion must
conjugate these complex tables for its exp(-j omega t) convention and
retain the same mask, physical axes and source calibration. The relevant
roles are source/receiver waves in A3 and predicted measurements in A4 of
the inverse information chain. This preparation does not enter the
default BEM path or change any BEM code.

## Inversion and evidence

`run_preparation.py probe` reads only the generated seven-column table.
Its owned first-opus driver copy sets the agreed domain and cell,
frequencies 1-8 GHz, native back-propagation start and 64 MF-CC-CSI
iterations. Projection, PML, border, objective and line search stay
unchanged. The full campaign is not launched.

`final_contrast.mat`, cost CSV, logs, resource samples and small JSON are
committed. Full histories, geometry/material arrays and the synthetic
table remain local and git-ignored; manifests give commands, byte counts
and SHA-256. The complete data table can be regenerated, but the later
BEM comparison must consume the retained file rather than independently
regenerating nominally equivalent data.
