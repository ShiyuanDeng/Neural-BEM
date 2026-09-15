# TOP-018 implementation review

2026-09-15. Owner/reviewer: Codex `/root`; owner review, without an independent
agent. The user approved the named audit and conditional pair by replying “yesh”
to the explicit approval question. This record follows the
[current-checkout source map](../../docs/iterations/topology/iteration_11/02_proposals/02_TOP018_current_checkout_review.md).

## Implementation and decisions

- `experiments/top018/run.py` is the experiment wrapper. It imports the existing
  `fit_stage`, `run_schedule`, physical prediction, scorer and acceptance rule.
  No historical driver, solver, geometry owner or numerical default is edited.
  Locating the wrapper here also avoids changing the legacy TOP-017 root-driver
  source-discovery assumptions. TOP-018 explicitly hashes its own Python files.
- Both arms deserialize the verified COMMON coefficients. Each stage receives
  `(256, 512)` explicitly and creates new optimizer-local caches. No old density,
  derivative or residual is passed into an inverse. Input hashes, full source
  hashes, objective identities and resolution settings bind all reused evidence.
- Reuse is restricted to the three exactly identified saved audit states. The
  only two measured/current source differences are pinned to reviewed hashes.
  No other changed numerical source is ignored. Candidate replay is checked
  against the unique archived numerical obstruction and its matched base.
- Phase A measures COMMON at all six frequencies and 128/256/512. Its derivative
  check uses only the first and last rows of the existing deterministic basis,
  the inherited `1e-4`/`5e-5` steps, and the same gauge retraction and independently
  feasible sides. No complete spectrum or inverse is called. The inherited
  two-scale threshold is 0.25; the signal must exceed five times the maximum of
  repeatability, `64*eps`, and resolution disagreement in the same normalized
  directional residual change. Zero/nonfinite norms and floor-limited signals
  fail qualification. All new prediction and repeatability calls are charged.
- The residual builder retains its actual pair-major/frequency-minor real
  flatten followed by imaginary flatten, with equal frequency weights. The
  scalar objective matches the plan; no alternative residual ordering is added.
- Each inherited complete-Jacobian/step reservation and 12-solve endpoint reserve
  remains binding. Per-arm caps are 7,000 solves / 7,200 seconds; Phase A is
  256 / 900. One campaign deadline spans all phases. At most two subprocesses
  read frozen source and write separate result directories, with single-thread
  BLAS. The sum of their fixed caps cannot exceed 14,256 new solves.
- Normal/quota transitions remain inherited. Numerical, physical, derivative,
  implementation and hard-resource failures cannot release a later stage.
  A numerical hard stop may receive affordable reporting-only scoring from its
  reserved work; that cannot change its failed status or restart anything.
- The inherited candidate-failure snapshot already saves full coefficients and
  computed predictions without extra solves. TOP-018 keeps accepted/rejected
  identities separate and adds objective associations to the saved records.
- `experiments/top018/summarize.py` reads JSON and checks hashes, stages, scores,
  gradients, failed-candidate snapshots and solve accounting without importing
  physical solvers. It produces the resolution table, two-arm scorecard, work
  ledger, README and artifact manifest. The fixed final stage is never replaced
  by a better-scoring earlier stage. The separate central row reuses TOP-017.

## Validation and limitations

The first combined mocked/geometry regression run passed 86 tests. The final
source-bound pre-dispatch record is `validation.json`, with exact command and
log digest. It includes the additional 256/512 rejected-candidate snapshot test.
No test dispatches a physical forward or inverse. The final source is frozen
only after these checks pass; the result bundle copies both the record and log.

Checks cover Phase-A fail/pass dispatch, common starts, resolution/frequency
exposure, planned quota transitions, hard stops, reporting-only scoring, feasible
stencils, numerical floors, cache separation, accepted-state preservation,
complete-batch/endpoint reservation, unchanged defaults and expired campaign
dispatch. Existing optimizer hooks are compared with their archived source.

No new matrix-factorization/RHS accounting is added. Interrupted derivative
detail retains the inherited completeness flag; unavailable endpoint gradients
remain unavailable. A finite saved-state audit cannot guarantee qualification
of every future candidate. Any such obstruction closes this bounded experiment.

**Review decision:** accept this implementation for its approved pre-dispatch
tests and conditional numerical contract. No change to the scientific scope,
numerical tolerances, or resource ceilings is authorized by this review.

## Post-run reporting correction — 2026-09-15

Both numerical schedules completed before a list/tuple frequency-metadata
comparison failed in the final annotation loop. After both workers stopped,
the owner verified all frozen source/input hashes, preserved the original
metrics and tracebacks, and corrected the comparison to compare sequence values.
The annotation helper can now rebuild identities from saved records without
physical calls; the campaign also exposes failed worker exits in its status.
Two new tests reproduce this exact inherited metadata seam; all 89 final tests
pass. The [closeout review](../../results/validation/topology/TOP-018-20260915-resolution-qualified-pair/closeout_review.md)
records numerical provenance `9bde9d1`, later reporting hashes and zero-physics
reconciliation. The pre-dispatch validation record above remains historical.
