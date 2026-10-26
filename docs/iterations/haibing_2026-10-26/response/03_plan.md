# HB-003 direct tests of Haibing items 6–8

## Questions

1. Does high-mode Schur feedback preserve the 24 measured responses, and can
   a diagonal high-block inverse with Neumann correction make it cheaper?
2. Does a forward–adjoint reduced model obtain second/fourth local response
   orders on an actual saved shape direction, and what does projection cost?
3. Do dual-residual and LM-defect bounds cover physical errors, and are they tight?

## Scope fixed before execution

Read Haibing_directions.md items 6–8 and original Word §§13–18. Use actual
TG-002 hook c13.3 states from PS-003/H3 and IS-001 matrices. No inverse fits,
no truth-based choice of direction, and no maintained-solver changes.

Schur: release Ku64 and final Ku128, 2.5 GHz real and damped. Retain modes
N/4 and N/2 in both traces. Compare full LU, exact elimination with all
source/receiver feedback, dropping H, and diagonal high inverse with q=0,2,4.
Record errors, spectral norm/radius of high correction, setup and solve cost.
Three timing repetitions on saved matrices; this does not repeat physics.

ROM: hook release iteration 0→1 accepted coefficient difference (1.139 mm).
Use fixed Ku64 and the actual saved linear slider coefficient path. Assemble
at alpha=0, ±0.001, 1, 0.5, 0.25, 0.125, 0.0625 for real and damped 2.5 GHz.
Include all 24 source and 24 true adjoint receiver columns, using a union
orthonormal basis; enrich with central-difference directional snapshots.
The ±0.001 difference approximates a derivative and its error floor is explicit.
Compare paired response errors and adjacent slopes. Charge anchor snapshots,
basis construction, projection, solve, and complete physical assembly separately.
A model can pass local accuracy without demonstrating whole-fit savings.

DWR: for each ROM target compute the actual primal/dual residual identity,
all-channel norm bound using a measured smallest singular value, and objective
error bound after the benchmark's fixed residual scaling. SVD is a numerical
estimate, not a rounding-controlled certificate. Record its cost separately.

LM: reuse FI-001 hook_release 19-frequency exact fields and Jacobian. Use
Marquardt diagonal metric and lambda=1e-6,1e-3,1; compare five CG iterates with
the full solve and compute the fixed-system defect bound. This tests linear
solve error only, with no approximate-J claim or candidate acceptance.

Single-thread BLAS on CPU cores 8–11. Stop after these comparisons; failures
and nonconvergence remain evidence. CPU-only timing, machine load recorded.
