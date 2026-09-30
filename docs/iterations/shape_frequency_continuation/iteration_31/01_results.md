# SC-051: frequency continuation with full Fourier bands

2026-09-30. User-directed comparison on all current SC and modal-atlas inverse
configurations. Owner: Codex; independent reviewer: unassigned. Existing
`feature/shape-frequency-continuation` checkout; no branch or worktree created.
Production defaults are unchanged.

## Result

Frequency-only continuation with **M=K=255 from the first frequency** recovers
**0/36 single-object configurations**, against **34/36** for the established
strategies selected before fitting. It has higher boundary RMS in every one
of the 41 comparisons, including five coupled local-refinement cases.

| Panel | Configurations | Median RMS, frequency only / established (mm) |
|---|---:|---:|
| Original six scenes | 6 | 11.758 / 0.003260 |
| Fresh shapes and noise draws | 6 | 12.588 / 0.090271 |
| Far starts, including noise | 7 | 194.273 / 0.012405 |
| Additional modal-atlas contrast cases | 17 | 194.273 / 0.001965 |
| Coupled local cases | 4 | 3.7647 / 0.83691 |
| Intrinsically perturbed coupled case | 1 | 3.8560 / 0.70472 |

The two single-object reference misses are the C at contrast 13.3, from its
original and opposite starts. The coupled references improve local geometry
but do not meet the common strict residual gate; their recovery counts are
kept separate from the single-object benchmark.

The full-band arm returns 36 numerical stops and five completed, stalled
schedules. Nineteen returned endpoints pass their numerical audits, but none
passes even the geometry-only RMS/Hausdorff criteria. Its disadvantage is
therefore not just an artifact of rejecting weak high-mode Jacobian columns.

## Meaning and limits

M=K=255 is the complete non-Nyquist Fourier band on the 512-node primary mesh:
there is no policy band cap or band ladder. This is a finite discretization,
not literal infinite bandwidth. The only continuation is the cumulative
available real-frequency ladder. The existing projected-update derivative,
LM damping and step controls, acceptance checks, and noise discrepancy stop
remain active. Localization, cleanup, complex-frequency damping, adaptive
band selection and an extra tail are absent.

The comparison is between complete strategies. There is no single adaptive
policy already established as best on every panel. The reference set uses
SC-043 fixed release, SC-044 recurrent cleanup, SC-050 localization plus
warm-up, MA-005 damped initialization plus adaptive frontier tail, SC-047 joint
M3→M5, and SC-048 compact M5. SC-043 stagnation is also reported separately:
the full-band vanilla arm loses on all six original scenes against that
explicit adaptive comparator as well. These comparisons do not isolate M/K
from differences in initialization or data access.

At the first frequency the single-object Jacobian has 48 real data rows and
511 update coordinates, hence at least 463 null directions. This explains
why numerical damping and spectral scheduling address different issues; it
does not prove a common cause for every observed numerical stop. The tested
finite-difference geometry implementation at M=255 also lies beyond the
bands of the established policies. The result supports retaining those
policies on this benchmark, not a theorem against unrestricted inverses.

The six original scenes also have a separately frozen N=1024/2048 sensitivity
control with unchanged M/K and fitting budgets. All six completed their
declared attempt and none recovered: RMS ranges from 8.44 to 19.94 mm. The
star reaches its wall limit while still accepting steps; hook completes the
ladder with no further accepted steps after the first frequency. C passes its
endpoint numerical audit. The individual outcomes and recovered kite endpoint
audit are in the report. The kite worker terminated abruptly during audit; the
cause is unestablished, and up to 126 lost audit work units remain additional
to recorded work. No fitting state was changed to recover that audit.

## Evidence

- [Complete report, plots and resolution controls](../../../../results/validation/shape_continuation/SC-051-frequency-only/README.md)
- [Per-configuration comparison](../../../../results/validation/shape_continuation/SC-051-frequency-only/comparison.csv)
- [Frozen experiment plan](../../../../results/validation/shape_continuation/SC-051-frequency-only/plan.md)
- [Sources, input hashes and reference selection](../../../../results/validation/shape_continuation/SC-051-frequency-only/manifest.json)
- [Execution and interruption accounting](../../../../results/validation/shape_continuation/SC-051-frequency-only/execution.json)
- [Evidence verification](../../../../results/validation/shape_continuation/SC-051-frequency-only/verification.json)

Vanilla fitting consumed 2,606 physical work units and 12,071.6 summed worker
seconds. Audits, reference scoring and resolution controls are charged
separately. The older SC-043/044 reference costs are suffix-only, and host
load/runtime versions differ; no wall-time speedup is claimed. Reference
endpoints were re-scored on the identical stored observations at 1024/2048
nodes. Original numerical-audit receipts and separate historical timeout
qualifications are preserved. Fifteen targeted LM and coupled-object tests
and 2,641 evidence assertions pass. The star's final accepted checkpoint
matches its returned endpoint; the timeout occurs before the next gradient
history row, and that gap is explicitly verified and disclosed. No new
strategy is promoted and no successor experiment is launched.
