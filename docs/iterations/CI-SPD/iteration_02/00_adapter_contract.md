# ON-002 TG-002 adaptation: operator contract

Authorized by the direct ON-002 launch, 2026-10-05 01:39:26 UTC.
This is an adapted known-material multifrequency occupancy model, not released
unknown-material SingleTX reconstruction or a claim about its published timing.

## Physical normalization

Convert package coordinates to metres using `x_m=origin_m+length_unit_m*x`,
and package wavenumber to inverse metres using `k_m=k/length_unit_m`.
The point source is `strength*i*H0^(1)(k_m*r)/4`. The physical integral equation
is `u=u_inc+k_m^2*G*(chi*u)` with `chi=(contrast-1)*b`.
There is no extra length factor in the 2D source Green function. The volume
operator and receiver map include pixel cell area exactly once; the Gaussian
Galerkin testing adds its own physical integration area. Both real and damped
wavenumbers use the outgoing complex Hankel function, without a real-only
Torch Bessel shortcut.

Build the zero-padded translation-invariant free-space pixel kernel for the
Problem domain. Nonself source cells use tensor four-point Gauss quadrature;
the singular square cell uses the exact radial Hankel primitive and 32-point
angular quadrature. Receiver/incident waves use physical cell-centre samples.
No SingleTX archive operator or target-dependent support region is used.

## Gaussian representation and material information

Reuse the pinned GauGal synthetic builder, separable Gaussian projections,
FFT propagation, lumped coefficient product, batched BiCGSTAB and adjoint
operators. Fixed pixel/centre pairs are 128/112 and 256/224, with sigma=0.8
centre spacing. The sole declared escalation is 512/448. Coefficient occupancy
is initialized by deterministic exact disk/cell area integration; the released
normalized separable renderer smooths this onto the pixel lattice. The disk is
exactly the frozen centred 65 mm initial object. Native fields follow the
released Gaussian coefficient coupling; they are not silently replaced by a
pixel product of rendered occupancy and field. Their discrepancy from the
sharp disk is measured explicitly against independent Mie scattering.

Known contrast enters coefficientwise, including negative chi at contrast
0.5. The derivative multiplies by the same signed `(contrast-1)` once. The
released nonnegative contrast clamp must never be applied to chi.

## Acquisition, objective and qualification

All 24 transmitters are solved in one batch. Only the diagonal paired channels
are exposed, and off-diagonal entries of the data/mask are zero. The receiver
adjoint applies that same mask. Single-frequency loss is
`||pred-data||²/(2*||data||²)`; multifrequency loss and gradient must average
these quantities equally across the active catalog.

The adapter target is 1e-3 relative field discrepancy against the prescribed
sharp disk, separately from 1e-6 true linear-system residual. Use Jacobi
BiCGSTAB at cap 200, complex64/float32 initially. Recompute true forward and
adjoint residuals and refuse gradients from unconverged systems. Algebraic
system and paired sensor adjoints and occupancy finite differences are
required. Independent disk control is evaluated in package coordinates so
it checks the metre conversion as well as the operator sign/readout.

One adapter repair is available, as in the approved plan. A refinement failure
may release the one 512 escalation or precision repair. A failed qualification
closes the adapter and blocks inverse/hybrid fitting: no unmatched-physics
speed ratios are allowed. Retain native occupancy, prediction, exact reference,
solver residuals, phase times, hashes and all failures.

## Source and resource boundary

GauGal remains read-only at `3ec2627d3ff7329453ec7b76469a0761d6f6e3de`.
B is pinned at launch `6f2c1408` in an ordinary source archive. The maintained
BEM package has no import of GauGal. Hold compute exclusive then source shared
for every numerical batch; hashes before/after detect mutation. Source edits
hold source exclusive. Staging/commit/push use Git exclusive and include only
ON-002-owned reviewed files.
