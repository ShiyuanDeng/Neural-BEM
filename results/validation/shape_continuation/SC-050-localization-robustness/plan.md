# SC-050: localization, continuation and numerical robustness

Frozen before any strategy outcome, 2026-09-28. User authorized scientific
experiments and more scenes after a one-hour wait for Claude's review. Wait
completed at 02:42 UTC; SPD-014 reviewed state preserved in b7173758 and the
roundoff amendment is a separate commit. No optimizer default changes.

## Questions and evidence

SC-049 decreased its active-frequency loss from 3.740 to 0.546 while RMS
boundary error grew from 168.8 to 188.4 mm. Its area shrank about 87%; its
mean boundary position moved away from the C. The next candidate failed the
512/1024 field agreement gate. The last accepted state's full-catalog atlas
also failed its field gate. This demonstrates harmful accepted progress and
a numerical obstruction, not proof of a converged local minimum.

* H1: a data-only center/radius search enters a better attraction region before
  deformable shape fitting. This is a low-dimensional full-wave search, not a
  MUSIC or Born implementation. Bao, Hou & Li (2007), [JCP](https://doi.org/10.1016/j.jcp.2007.08.020),
  motivate combining localization and continuation; their direct imaging and
  acquisition differ from ours. We use our exact paired near-field model.
* H2: a 0.25 GHz M=1 warm-up can recover position/size before M=3 at 0.5 GHz.
  Borges, Rachh & Greengard (2022), [§2.1](https://arxiv.org/html/2210.11607v1#S2.SS1),
  use low-frequency continuation with gradually increasing shape complexity
  for penetrable objects and explicitly give no global convergence guarantee.
  Their far-field plane-wave data differ from our 24 paired near-field channels.
* H3: smaller steps or doubled quadrature may avoid the numerical obstruction,
  but need not fix localization. Borges & Greengard (2014),
  [§3](https://arxiv.org/html/1408.5436v1#S3), discuss bandlimited updates,
  damping, and improved initial guesses for sound-soft obstacles. Applying
  these ideas here is a hypothesis, not an identical-physics replication.
* Cavity caution: [Askham et al. (2023)](https://arxiv.org/abs/2308.00559)
  examine sensitivity to initialization and frequency paths for sound-soft
  cavities. The penetrable comparison above also documents difficult cavity
  reconstructions. A single successful C does not establish general robustness.

## Frozen development comparison

Original SC-049 observations, target and initial circle (0.32,0.62), r=0.065 m.
Six full attempts, one each, without restart or truth-selected best iterates:

1. `baseline`: exact SC-049 schedule, 512/1024 nodes.
2. `low`: prepend 0.25 GHz, M=1, K=4, 44 iterations, quota 600.
3. `localize`: data-only global circle search, then baseline.
4. `localize_low`: localization then the same low-frequency warm-up.
5. `small_steps`: baseline with all coefficient step bounds divided by four.
6. `refined`: baseline at 1024/2048; same tolerances and work-unit cap.

Localization: all 9x9 centers over [0.28,0.72]^2 and radii 0.025,0.045,0.065 m,
using equally weighted relative complex residuals at 0.25,0.375,0.5 GHz.
Every grid point evaluated at 128 and 256 nodes, requiring field discrepancy
<=1e-7. Rank by 256-node loss. Then 12 deterministic coordinate-search rounds
at 512/1024, starting steps (0.02,0.02,0.0075)m, six neighbors per round;
halve steps only when none improves. Radii constrained [0.015,0.075]m and
circles contained in physical [0.2,0.8]^2. Every local candidate requires the
same 1e-7 gate; rank by refined loss. Maximum 2000 forward units, 600 s.
This bounded search does not prove a global minimum or cover all admissible
object sizes/locations. No target geometry enters it.

All variants share cap 13412 fit+localization physical units and 1800 s.
Unchanged stage quotas; localization and warm-up consume the common budget.
Remaining stages: SC-049 prefix, releases M=11,15,19, one K64 cleanup, fixed
M=25,31,37. Production and refined residual decrease both required. All hard
stops preserved. Full-catalog initial/final field/Jacobian/directional-FD audits
(cap 130 each, 300 s each); same field tolerances, J and FD <=1e-3. Endpoint
always last accepted, never best truth. Report localization and fitting costs
separately and combined; doubled node count is not equal wall cost per unit.

Select one non-baseline policy for transfer using development data ONLY:
first prefer completed schedules with passing full endpoint audits, then any
passing endpoint audit, then all remaining; within group smallest maximum
catalog relative residual, ties by units then arm name. Record selection before
transfer fits. Truth errors do not select the policy. If none qualifies,
transfer is explicitly exploratory, not promotion.

## Prespecified robustness scenes

Definitions and initial circles are pinned in run.py before data generation:
original C from opposite side; translated/rotated C off the search grid;
a translated/rotated five-lobe star; a new asymmetric 3/4/7-lobe shape; a new
thin C with 122-degree half angle; and the asymmetric shape with a fixed 1%
complex RMS noise draw (seed 50061). Noise scene uses unchanged fitting policy,
so it tests noise transfer without noise-specific tuning. Start radius 65 mm;
all circles spatially displaced. Baseline and selected policy get one attempt
per scene, same caps. No transfer-based tuning or additional winning-arm selection.

Fresh clean observations: Muller 2048 nodes, checked against 1024 at all 19
frequencies <=1e-8; independent Kress formulation at 0.25,1.25,2.5 GHz <=1e-8.
If a fixture fails qualification, keep it as a declared withheld scene; do not
replace it based on reconstruction results. Reused C observations retain the
original oracle receipt. Freeze source archive before generating; separately
seal input hashes before development. One numerical worker, four frequency
threads, single BLAS thread, explicit CUDA; no timing comparison to historical
runs with different concurrency.

Primary clean success: full audit passes, RMS<=1mm, bounded Hausdorff<=2mm,
maximum catalog relative residual<=0.003. For noisy scene separately report
geometry success plus residual <=3 times realized per-frequency noise (with
0.003 floor); never call noisy result clean-threshold success. All work,
qualification failures, numerical stops, budget stops and endpoints retained.
Six development plus twelve transfer attempts maximum: maximum fit work
18*13412=241416, plus audits 4680, endpoint residual evaluations 342, and at
most 4*41 fresh-data solves. Per-attempt caps apply; partial runs stay visible.

Post-run analysis: atlas at original initial state gives linearized radius /
translation / M3 residual projections at 0.25,0.5 GHz; these are local evidence,
not global identifiability certificates. Compare actual localization objective
landscape and all endpoint geometry/field metrics. Plot all transfer endpoints,
including failures, and the development ablation. Distinguish input qualification,
optimizer termination, numerical qualification and true reconstruction success.
