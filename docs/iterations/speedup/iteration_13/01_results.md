# SPD-016: damped attempts are 2.43–2.75x faster

2026-09-30. **COMPLETE / PASS; experimental grid + assembly prototype.**
The user asked Codex to continue Claude's interrupted investigation while
preserving files being reorganised. The [contract](../iteration_12/03_spd016_plan.md)
was executed entirely through bundle-local scripts on the existing
`feature/shape-frequency-continuation` branch. No production source or default
was changed, and no branch/worktree was created. Owner: Codex; self-review only.

The useful combination is Hankel order recurrence with GPU contraction for the
Mie localization grid, followed by complex-frequency GPU matrix assembly using
Chebyshev tables on the fixed damping ray `1+0.25i` and existing device LU.
Geometry checks, near-pair series, objectives, schedules, budgets, tolerances,
refined acceptance checks and endpoint scoring retain their original code.

| Complete MA-004 D attempt | Fresh reference | Accelerated | Speedup | Work units, both arms |
|---|---:|---:|---:|---:|
| Shifted star, contrast 0.5 | 245.45 s | 101.11 s | 2.43x | 1,536 |
| New asymmetric, contrast 13.3 | 396.52 s | 143.95 s | 2.75x | 2,321 |

Both recover, with endpoint RMS 0.01824086 mm and 0.01136343 mm respectively.
All configurations, localization starts, outcomes, stage and accepted-step
counts, trial/acceptance decisions and work counters match. All 123 saved
accepted curves agree within 1.83e-11 relative coefficient norm; the largest
RMS difference is 8.24e-13 mm. Both fresh baselines reproduce the archived
numerical records exactly. The 27 primary numerical checks pass, including
matrix, prediction, Jacobian and full-grid comparisons.

The conditional source/receiver-field table also passes 24 numerical checks,
five reference-fallback checks and both complete replays. It supplies **no
consistent incremental saving**: 107.81 s versus 101.11 s on the star, and
143.44 s versus 143.95 s on the asymmetric case. Preserve this negative result;
the recommended prototype is grid plus assembly, without the field extension.

These are two noiseless single-object development cases, one run per arm/scene,
with sequential workers, four frequency threads and one BLAS thread on a shared
RTX 5090. Timings cover complete D attempts from original circles, including
localization and audits, but exclude the later MA-005 DF tail. Whole-process
ratios including startup are 2.40x and 2.74x. There is no noisy-data,
multicomponent, general-complex-frequency or production-integration claim.

All six attempts recover; total numerical subprocess time is 23.19 minutes,
within the 45-minute budget. All 163 reference source/input hashes and both
script manifests verify. Claude's original scripts, failed import logs and
preliminary measurements are preserved separately from the fresh evidence.

The [evidence bundle](../../../../results/validation/speedup/SPD-016-20260930-damped-gpu/README.md)
contains the exact commands, environment, scripts, hashes, full trajectories,
comparisons and limitations. No further campaign is scheduled. The qualified
prototype is ready to inform integration once the file organisation is settled.
