# FM-001: acquisition and relaxed multi-receiver residuals

Frozen before execution, 2026-10-03. Baseline `b23dbf3e`, existing checkout
`feature/shape-frequency-continuation`. No branch/worktree creation, default
changes, parameter tuning, or truth-dependent fitting. Owner: Codex.

## Question and limits

Does full source–receiver acquisition recover the contrast-13.3 development C
from both prescribed starts? Does receiver-coupled relaxation add anything?
The user's preliminary disk/path evidence is motivation, not campaign evidence.
A straight-path barrier does not establish a basin. Positive paired-data
weights do not in general smooth resonant residuals like complex damping.

## Frozen sequence

0. Seal baseline sources, environment, inputs and this plan. Run the complete
   cleaned-interface suite and adjacent maintained-adapter/control regressions.
   Rerun `modal__c13.3__development_c` and `modal__c4__development_c` with the
   exact CI-001 policy/execution. Gate: archived decisions identical.
1. Implement opt-in full matrices (source-major flattening) and per-stage tau.
   `None` preserves the objective. Localization uses only the paired damped
   diagonal. For receiver rows C and existing factors of A, use
   `H=A^{-H} C^H`, `lambda=tau*median_s ||C_s||^2`,
   `W=sqrt(lambda)*(H^H H+lambda I)^{-1/2}`. Hold W fixed in the LM
   linearization; recompute the exact reduced objective for every production
   and refined trial. Preserve all numerical acceptance gates.
   Generate full real/damped catalogs for all 36 configurations at 1024 nodes
   and qualify against 2048 nodes. Verify clean paired diagonals against the
   archived clean signal. Preserve archived observed diagonals exactly; new
   off-diagonal noisy samples receive independent complex Gaussian 1% draws,
   with seeds and realized noise recorded. This resolves the simultaneous
   requirements of an unchanged paired diagonal and new independent noise.
   Gates: closed form versus stacked least squares <=1e-12; tau=1e12 versus
   ordinary reduced loss <=1e-9; default paired runner decisions equal CI-001;
   full-matrix complete-trial Jacobian relative FD error <=1e-3.
2. Evaluation only: repeat radius scans and stage-1/stage-4 straight paths to
   truth for contrast-13.3 C and c4 C, at production resolution. Include paired
   and full real, gamma=.25/.5/1 damped, tau=3/30 relaxed objectives. Report
   barriers without using them to select policy. Path checks do not gate arms.
3. Arm F: full matrix, unchanged CI-001 policy, first seven contrast-13.3 cases,
   then ten other modal cases, then nineteen contrast-.5 cases.
   Arm FRr: full matrix, real data in warm-up/prefix with tau=3,3,10,30,100,
   exact objective afterwards; seven contrast-13.3 then ten other modal cases.
   FRr localization still uses damped paired data and must be disclosed.
   Paired control is the frozen CI-001 archive.

## Gates and stopping

- G1: contrast-13.3 development C recovered from both starts in F or FRr.
- G2: no formerly recovered CI-001 case is lost within an arm.
- G3: recovery in F supports acquisition attribution; recovery only in FRr
  supports an additional relaxation effect. If neither works, report the
  stage where truth-distance stops falling. These are empirical attributions,
  limited to the tested acquisition, cases and fixed optimizer.
- Report the residual/numerical pass count separately from recovery (archive:
  28/36 passes, 34/36 recovered). Use the repository's frozen recovery gates:
  qualified endpoint, RMS <=1 mm, Hausdorff upper <=2 mm, each-frequency
  residual <=max(.003, 3*realized noise).
- After two bug-fix rounds if Phase-1 relaxation gates still fail, skip FRr
  and run F only, provided F's own acquisition/Jacobian gates pass.
- Stop an arm immediately after its second lost formerly recovered case;
  execute cases sequentially to make this exact. Preserve every failure.
- Do not tune tau, gamma, budgets or thresholds. CI-001 fitting nodes remain
  512/1024; catalog nodes are 1024/2048. Truth is for data synthesis, scoring
  and Phase 2 only. Use damped gamma=.25 in fitting/localization.
- Fallback: extend paths to c4 C, contrast-13.3 star and thin C to locate
  paired barriers. Preserve all evidence; explicitly report incomplete gates.

## Outputs and reproducibility

`results/validation/cleaned_interfaces/FM-001/` holds seals, input hashes,
tests, qualification receipts, controls, paths, per-arm runs and failures.
`iteration_18/01_results.md` and `docs/reports/overnight_2026-10-03.md` report
one table per arm and all gates. Record implementation/source seals before
campaign execution and never overwrite incomplete runs to hide a failure.
Approximate requested durations: Phase 0 20 min, Phase 1 1 h, Phase 2 30 min,
Phase 3 4–5 h; these estimates do not override the frozen numerical budgets.
