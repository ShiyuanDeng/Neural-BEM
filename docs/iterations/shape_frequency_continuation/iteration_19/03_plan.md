# SC-038 — release the update band on all available frequencies

2026-09-25. User-requested test on C and kite. Owner: Codex; independent
reviewer unassigned. Existing checkout; no new branch or worktree.

The previous K=192 release retained M=9. It tested removing the state cap,
not adding first-order update directions. Test the user's proposed remedy
with one three-stage suffix, without tuning its schedule to truth.

Start both arms from the exact SC-035 low-K stage-four endpoints, before the
old M=9 release. Zero-pad K=20 to K=192 without changing either boundary.
Use **all 19 existing frequencies, 0.25–2.5 GHz**, at every suffix stage,
with equal frequency weights and the existing numerical tolerances (1e-5
through 0.5 GHz, 1e-7 above). These observations are now fitting data, not
held-out evaluation data.

- `release_m`: M=11, 15, 19. These are the existing Borges band rule at
  1.5, 2.0 and 2.5 GHz; all data are available from the first stage.
- `fixed_m9`: M=9, 9, 9 on exactly the same data, K, stage count and budgets.

The matched control separates the added update directions from additional
data and optimizer work. K stays 192 in both arms to isolate M. Both use
the unchanged SC-035 centred projection and complete-construction Jacobian,
LM settings and 512/1024-node acceptance checks. Damping resets at each stage.
Each stage allows 22 iterations and 1,500 field/reciprocal units. Each suffix
has a 4,500-unit and 1,800-second ceiling; four paths reserve 18,000 new
inverse units. Report reused prefix work separately and in complete-path
totals. Four single-thread workers; no isolated runtime claim.

Before fitting, qualify M=19, K=192 on both starts using all-frequency field
and active-Jacobian refinement plus an actual-trial central difference.
Use the existing field tolerances and 1e-3 relative Jacobian/FD limits.
Audit all four returned endpoints similarly. Reserve 800 audit units and
76 final scoring solves. Qualification failure withholds fitting; numerical
failures and exhausted limits remain results, not reasons to loosen guards.

Save all three stage histories and endpoint curves. Truth scores returned
states only, never picks a mode count, iterate or rollback. Report geometric
RMS, Hausdorff distance, data residuals, stops and work, relative to the common
start, old SC-035 release and matched M=9 arm. Improvement beyond M=9 supports
the update-space explanation on that case; extra-data-only gains, remaining
bias or numerical stops narrow it. No default promotion or schedule sweep.
