# Iteration 04 — what the published compression construction actually transfers

Opened by completed **LAU-002**, authorized by the user's 2026-09-17 instruction
to catch up with the literature. [Contract](../iteration_03/03_plan.md) ·
[Full measured record and source map](../../../../results/validation/laurent/LAU-002-20260917-closeout/README.md).

**Verdict: scalar mechanism reproduced; transmission transfer conditional.**
The earlier retained-fraction masks were not a reproduction of the published
method. The new independent implementation reproduces its splitting/index
construction and convergence, while preserving unresolved printed-table
differences. At 2,047 scalar unknowns, mu=1.1 retains 0.687% of positions and
reaches analytic-density L2 error 1.63e-11. Dense assembly remains in use.

The literal mask fails all tested noncircular transmission cases through
trace cutoff 128. A declared adaptation separates mask resolution from trace
resolution; it passes physical fields, residuals, six independent directional
derivatives and objective derivatives with 19.6–25.8% fewer represented
forward slots for the two ellipses and two lower-frequency stars. The two
circles also pass with larger savings. Both higher-frequency stars fail every
tested setting. Protected principal-log terms do not improve the smallest
passing count relative to identity protection alone.

All 24 full controls qualify; 89/312 compressed settings pass physical gates,
47 also reduce represented slots versus the original smaller dense system,
covering six of eight cases. All 48 representative compressed-model FD checks
pass; 1,872 individual physical directional comparisons are audited.
**77 tests pass**, and both final evidence bundles pass hash and data read-back.

The prior claim of no useful noncircular entry reduction is narrowed by these
results. No runtime improvement is established: transfer assembly/solves are
still dense, protected terms are counted, derivative and factorization storage
are not included. Strong scalar sparsity at large n is not a promise of equally
strong transmission compression at our small working resolutions.

Full literature parity remains open: exact printed-table conventions, fast
assembly, and transmission/shape-derivative analysis. Table 4's printed count
statistics fail their own defining identity; that is documented without
assuming it invalidates the theorem. The source's analytic bound is stretched
exponential and its frequency-dependent onset is unresolved.

The next useful performance question is whether assembling/applying retained
entries actually beats the qualified nodal/compiled path once setup and
derivatives are included. No new experiment ID, inverse campaign, production
promotion, branch, or worktree was created beyond the authorized LAU-002 work.
