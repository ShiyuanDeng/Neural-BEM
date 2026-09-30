# Resolution control, frozen before execution

The primary 512-node full-band runs show numerical stops and unresolved
endpoints. Repeat all six original scenes with **1024/2048 forward nodes**,
keeping **M=K=255**, initial curves, observations, frequency ladder, LM settings,
per-stage quotas and total work/time budgets exactly the same. Do not change
the spectral bands when doubling quadrature: the question is whether the
primary failure is a forward-resolution artifact at the same model capacity.

This is a numerical sensitivity control selected because of the primary audit
failures, not a retrospectively selected winning configuration. All six runs,
including stops and timeouts, must be reported. The primary outcomes remain
unchanged. There is no localization or adaptive band restriction in either arm.

The control driver injects only the doubled-node schedule and a separate output
directory into the unchanged, hash-verified primary runner. The source and
input hashes, actual stage settings and complete histories are recorded.
