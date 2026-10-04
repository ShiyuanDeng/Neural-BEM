# PC-002 focused validation

Before any inverse fitting: affected package, complete lower-level Kress suite,
TG-002 benchmark tests and cleaned-interface contract tests. 176 checks passed;
one new test fixture incorrectly removed frequencies before constructing the
policy. This test setup was corrected (no numerical implementation change),
and all seven new nodal tests passed in 4.20 s. The retained first log records
that fixture failure. Together the final unique affected checks are 177 passed.

Checks cover CPU/CUDA builder equivalence, legacy runner/LM behavior, exact
cache key invalidation/concurrent publication/bounds, cached versus uncached
real/damped fields/Jacobians, independent CPU comparison, full-trial finite
differences, stage escalation/refusal/work charging, and native profile audits
against CUDA N1024/N2048. TG-002 verify: sealed, 30 cases, verified true.

Environment: EMNerf Python, PYTHONPATH=solvers:., OMP/OPENBLAS/MKL threads=1.
No additional inverse comparison arms or repeated timing panel were run.

After fitting: the reference-resolution hook is owned by the physics service,
with no generic runner backend-name branch. An additional opaque-name probe
passes; the final package/interface suite passes all 51 tests in 32.80 s.
The result-bundle validator passes all 30 cases, 60 independent reference
comparisons/FD checks, source/input seals, zero CPU fallback and exact dispatch
accounting. Native audits pass 58/60; the two native refusals belong to failed
hook13.3/Aphex13.3 endpoints and are retained. No additional fits were run.
