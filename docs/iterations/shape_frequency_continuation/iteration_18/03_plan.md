# SC-037 — relax the state restriction earlier

2026-09-25. Authorized by the user's autonomous research instruction.
Owner: Codex; independent reviewer unassigned. Existing checkout only.

Question: can a simple, less restrictive later state ladder retain SC-035's
peanut/C benefit and avoid its 16% star regression? The four cases remain
explicit development cases. Choose one coherent candidate, not a family sweep.

Decisive comparison: SC-035 K=8/12/16/20/192 versus K=8/16/32/64/192. The latter
doubles storage capacity at each new frequency after the common first stage;
it is a numerical schedule, not a truth-derived minimum feature scale.
Everything else, including M=3/5/7/9, the centred projection and its complete
Jacobian, the observations/weights, 22 iterations, the solver and guards,
remains unchanged. Reuse exactly the accepted SC-035 low-K stage-one curve,
damping reset at the next stage, and charge its work to every path. Retain the
same final old-data release/repeat stage as both SC-035 arms.

Run peanut/C/star/kite once each. Per-path total cap 3,000 units including its
stage-one prefix, and 2,700 seconds minus prefix time; aggregate 12,000 inverse
units plus 76 final evaluation fields. Four concurrent single-thread workers;
no isolated timing claim. Preserve intermediate stage results and numerical
failures. No numerical source changes; no additional qualification is needed
for this schedule-only intervention using the already checked update.

Useful outcome: star RMS <=1.05 times the matched SC-035 high-K star, while
peanut and C remain within 25% of SC-035 low-K error and kite is no worse than
SC-035 low K by more than 25%. The gate is for selecting this development
candidate, not claiming generalization or promoting a production default.
Truth only scores completed fits, never chooses their updates or iterates.
If the tradeoff remains, close this schedule hypothesis without a grid search.

API map: a small driver calls the frozen SC-035 `run_stages` and `state_update`
with new `FitStage.curve_modes`; save source/input hashes and prefix links.
A report compares completed endpoints and pre/post-release states. The
Müller/Kress solver and baseline SPD-L stay unchanged.
