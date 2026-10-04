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
