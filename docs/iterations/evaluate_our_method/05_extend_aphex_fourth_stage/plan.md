# Extend the original fourth stage for Aphex Twin

18 November 2026. The user asked whether stopping a moving stage caused the contrast-4 misses. The [four-case check](../04_check_stage_stops_and_shape_bands/results.md) found one promising original stage. Aphex Twin's loss fell 2.97% over its last five steps. Extending *all* early stages changed its starting point.

Replay just the fourth stage from the saved third-stage boundary and estimated contrast of the original centred run. Keep the real observations, default slider, update band 9, storage band 20, resolution and 4,000-unit stage quota. Allow 220 iterations and a nominal 240 seconds in this stage alone, then stop. This extra time tests what the stage can reach. It is a diagnostic choice outside the original whole-fit budget.

Check that the loss and estimated contrast at each of the first 22 steps and the boundary at step 22 match the reference. Compare the loss and area error at step 22 and at the stop. Check the last accepted step within the time the original fit had left. The recovery threshold is 5% area error. The test ends at stage four and supplies no full-fit score.

Budget one stage replay after the four-case comparisons, one GPU worker, no search. From the repository root run `PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.comparison.extend_aphex_stage`. Save its record under `results/bem/stage_stops/2026-11-18/aphex_fourth/` and its interpretation alongside this plan.
