# IS-001 execution details

## Questions

Where does production physics time go at Ku64/128? Can all-RHS anchored
GMRES beat current LU, including its anchor setup? Where is the crossover?

This execution follows the registered plan. No inverse fits or solver changes.
The user replaced the historical overnight deadline with completion and review.

The saved final `fixed_M67` curve has K136/Ku128 and zero new accepted steps.
Its endpoint was accepted in `fixed_M55` (K112/Ku96), then carried through
storage promotions. We replay the actual final K136 representation at Ku128.
The nearby anchor is `fixed_M55` iteration 3 padded with exact zeros to K136.
At Ku64 use `release_M11` iteration 15 and its consecutive iteration 14 anchor.
The large step is its actual first accepted step, iteration 0 to iteration 1.

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
Use restart 60 and at most 1800 matrix actions. LU uses both 24-column batches.

Raise Ku64/128/256/512 on the same release curve, checking memory before each.
Stay below 6 GB combined host resident plus live GPU allocation. If the next
size cannot fit, report a bounded crossover rather than extrapolating a win.
Cores 12–17, single-thread BLAS; record machine load and GPU use in receipts.

Before solver timings, coordinator review added rank-aware full block Arnoldi
alongside global GMRES. Dependent RHS columns are removed by SVD; two
orthogonalizing passes retain the combined Krylov space. Deflation uses the
current operator-action scale, including right preconditioning. Both solvers
report the true residual and any nonconvergence. Check actual slider-Jacobian
error separately from trace-product moments because cancellation may amplify
moment error. A complex 40-by-40 system with duplicated RHS columns gave
true residual below 1e-12 for both methods, cold and anchored.

Ku512 completed within 2.396 GiB peak live GPU plus 1.564 GiB peak host RSS.
Its saved matrices are split losslessly into current and anchor files to keep
each below the ordinary GitHub per-file limit. No extra experiment was run.

The first Ku64 real solve comparison exposed an accuracy issue in an unscaled
48-RHS block: source RHS norms are about 2e-7, reciprocal RHS about 0.2.
An excellent aggregate residual can hide inaccurate source fields. Its
receipt is preserved unchanged as `release_Ku64_real_solves.json` (the block
methods missed the 1e-9 field requirement); the initial failed receipt-write
run is also kept. Before remaining comparisons, normalize each RHS column
to unit norm inside both Krylov methods and restore physical units for
accuracy. Tolerance stays 1e-12. Save these as `*_balanced_solves.json`.
This changes the numerical scaling, not the requested accuracy or scene.

Cold baselines run at the requested production sizes Ku64/128. The larger
Ku256/512 studies compare anchored methods to LU only, which answers the
registered crossover question without repeating an unrelated cold baseline.

Coordinator review stopped repeated failed 1800-action solves. The remaining
size loop was interrupted during a repeated cold failure; its log and partial
records are preserved. Resume skips all saved repetitions and runs a failing
method only until its first failure; successful methods retain three timings.
The large-step pair is an early accepted-step stress test, not a recorded
refused or halved trial. Report its measured physical displacement explicitly.
