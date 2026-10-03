# NU-007a completion protocol

2026-10-03. User authorized finishing NU-007 while another session runs the
relaxed-BIE campaign. Written before this rerun. No branch/worktree creation,
commit, or push is requested. Original NU-007 failed evidence stays intact.

## Isolation

FM-002 seals all existing numerical files. Until that active run finishes,
only new NU-007a driver/test/evidence files are added to the shared workspace.
Freeze current Python sources in a dedicated archive and stage the prospective
`certified_spectral` CUDA selection inside that archive only. Execute the
qualification from an extracted ordinary source snapshot under `/tmp`, not a
Git worktree. Read frozen historical data from the repository after checking
its recorded hashes. Never alter FM-002 files or its seals. Do not edit the
shared selection until the other run has completed its final verification.

## Fixed precheck

Repeat all 72 NU-006 last-in-stage states and 12 seeded trials per state:
three directions at 1e-7, 1e-3, 6e-3 and 1.8e-2 metres, seed 5. Same candidates,
status/refusal reasons, validity roles/tiers and bound-key presence are required.
For every compared increment/full bound require
`abs(host-device) <= 1e-9 * max(1, abs(host))`, the same side of 1, and the same
side of the regularity-floor predicate. Keep the original float64 certificate
and heuristic FFT allowance unchanged. Record fallbacks and runtime separately.
If a gate fails, diagnose before any full-path campaign or adoption.

This threshold-scaled rule was suggested by the already observed original
failure and its gap diagnostic, and confirmed on 36 replay trials. That
selection is disclosed; this is not an unseen-data preregistration.

Also test near-threshold real certificate comparisons, near-cusp/cusp/crossing
curves, clockwise refusal, device OOM fallback, and public CPU/CUDA selection.

## Full paths and integration

Only after the precheck and focused tests pass: run three sequential pairs of
NU-006 host certificates and NU-007 device certificates on all six core cases,
with matching original starts, exact observation bytes, modal physics, CUDA,
four frequency threads, one BLAS thread and the existing NU arm policy/caps.
Alternate arm order across repetitions. Wait for the other numerical process
before full-path timing. Track external work and environment around each fit;
interrupted/contended timings must not be labelled matched quiet-host evidence.

Require identical fresh CPU/GPU accepted states, final coefficients, decisions,
units and tier counts, with both audits passing. Compare with archived NU-006
decisions/units/tiers and apply the existing NU-001 no-drift and >=5/6 matching
rule against nodal CI-001. Preserve the existing circle_to_star regression.
Report per-case median wall/certificate seconds and every repetition. Report
runtime separately from numerical qualification; no all-36 claim is made.

If qualified, apply only the staged change in maintained
`solvers/bem_inverse/geometry_selection.py`: `certified_spectral` uses
`DeviceCertifiedUpdate` on CUDA and keeps `BatchedCertifiedUpdate` on CPU.
The public spline/nodal defaults and all relaxed-BIE code remain unchanged.
Run package/interface tests after integration and verify only intended files
changed relative to their recorded starting bytes. Shared docs/index files
are left to the concurrent owner; record the completed handoff here.

Predictions inherited from NU-007: <=15 s certificate work and 140–160 s wall
time across the six cases, with decisions/tiers retained. Predictions are
measurements to report, not reasons to alter the numerical acceptance gates.
