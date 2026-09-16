# SPD-002 — make the fast CPU inverse the pipeline default

- Approval: **APPROVED**, user's 2026-09-16 instruction: “go make this default.
  i expect this to speed up current pipeline”. This supersedes the earlier
  opt-in-only restriction for this implementation.
- Execution: **IN PROGRESS**. Existing branch/checkout; no new branch/worktree.
- Owner/reviewer: Codex `/root`, self-review.

Use analytic coefficient Jacobians for Cartesian components and fast
real-argument CPU kernels throughout topology refinement and continuation.
Keep radial coefficient FD until its analytic bridge exists. CUDA stays optional.
Expose a shared reference profile for FD/reference CPU, inherited by spawned
workers and recorded in manifests. Retain the FD-compatible constrained-stencil
policy, original LM/feasibility/acceptance formulas, source guards and run limits.

Before edits, process inspection found no active numerical or video worker.
Historical SPD-001 and TOP result bundles remain immutable. Runtime switches
are scoped; explicit numerical execution contexts take precedence.

Integration must count analytic base systems in existing physical-solve totals
and charge derivative assemblies separately against work budgets. Test success,
failure, cap enforcement, context restoration, reference selection and worker
inheritance. Preserve the existing frozen-source guard for historical TOP-017.

Validation: existing relevant solver/controller/continuation tests plus new
real-operator default and accounting checks. Then two full current-pipeline
controls, `death` and `split`, from original saved starts/observations, each
with reference and fast profiles sequentially at original production/refined
resolutions and all four continuation stages. Reuse prepared observations only;
no truth enters optimization. Compare recovery gates, topology events, retained
geometry and wall time. Single timings per arm; no all-twelve-scene claim.

Controls use a fresh SPD-002 result directory. Freeze numerical source/input
hashes before timing and stop on drift or concurrent numerical work. Per arm:
existing 4000 topology and 8012 continuation work caps, 600/7200-second local
watchdogs; additionally stop the four-arm validation at 2400 seconds total.
All attempts and failures remain recorded. Do not silently extend these limits.
Results open iteration 03; default promotion itself is directly user-authorized.
