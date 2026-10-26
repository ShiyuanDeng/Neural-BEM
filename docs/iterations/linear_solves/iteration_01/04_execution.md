# IS-001 execution details

## Questions

Where does production physics time go at Ku64/128? Can all-RHS anchored
GMRES beat current LU, including its anchor setup? Where is the crossover?

This execution follows the registered plan. No inverse fits or solver changes.
The user replaced the historical overnight deadline with completion and review.

The saved final `fixed_M67` curve has K136/Ku128 and zero new accepted steps.
Its endpoint was accepted in `fixed_M55` (K112/Ku96), then carried through
storage promotions. We replay the actual final K136 representation at Ku128.
The nearby anchor is `fixed_M55` iteration3 padded with exact zeros to K136.
At Ku64 use `release_M11` iteration15 and its consecutive iteration14 anchor.
The large step is its actual first accepted step, iteration0 to iteration1.

Three warm repetitions follow one first use, at real and damped 2.5 GHz.
Production slider weights match M11/M67; their preparation is outside physics
timing. Geometry preparation is separate and can be shared over frequencies.
Forward trace solve, reciprocal trace solve and Hadamard work are split.

The initial solver comparison is batched global GMRES with one Frobenius
Krylov polynomial for all 48 right-hand sides. This is distinct from full
block Arnoldi and 48 independent SciPy GMRES calls. Both cold and fixed-LU
right preconditioning are timed; the current matrix forms true residuals.
Relative tolerance is 1e-12; predicted fields must agree with LU to 1e-9.
Save failures and nonconvergence, without retuning the tolerance afterward.
Use restart60 and at most 1800 matrix actions. LU uses both 24-column batches.

Raise Ku64/128/256/512 on the same release curve, checking memory before each.
Stay below 6 GB combined host resident plus live GPU allocation. If the next
size cannot fit, report a bounded crossover rather than extrapolating a win.
Cores12–17, single-thread BLAS; record machine load and GPU use in receipts.
