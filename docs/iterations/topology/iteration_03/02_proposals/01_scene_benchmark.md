# TOP-006 — broader automatic-topology scenes

The user asked on 2026-09-11 whether a large circle far from an ellipse and a
star would recover, and directed that current and future performance use more
scenes. TOP-005 only qualified allocation on circular split children. The old
ellipse-star challenge reached 0.552 mm maximum boundary error, but used a
prescribed two-object replacement and mode/frequency schedule; it is not
evidence for the automatic controller on a distant initialization.

Propose a permanent, versioned scene specification and a paired evaluation of
the current default A and selective F. Retain all five original controls and
add seven scenes: far circle to two circles; far circle to ellipse/star;
central circle to ellipse/star; enclosing circle to ellipse/star; empty start
to ellipse/star; far circle to two stars; far circle to three different shapes.

Report each scene and policy, including failures. Judge component count,
boundary agreement, material overlap, training and held-out prediction
separately. Save initial/final overlays and actual accepted trajectories.
Require future topology performance claims to include this full frozen suite,
with observations, acquisition, budgets and thresholds held fixed. New scenes
or acquisition changes get a new version and retain the prior benchmark.

No controller, solver, gauge, candidate, frequency-schedule or mode-promotion
change is proposed here. Additional tuning needs a later iteration.
