# Codex review reproducers, 2026-09-22

Executable checks Codex ran against commit `8e5c152`, preserved unmodified.
`checks.json` is its output; `reference_sources.json` pins the twelve reference
files read, with SHA-256 digests and permalinks.

The findings and their resolution are in
[iteration 02's review record](../../../../docs/iterations/shape_frequency_continuation/iteration_02/02_proposals/01_codex_review_resolution.md).

`checks.py` **no longer runs against current source**: its `warmup_probe` builds
`FitConfig(steepest_descent_iterations=1)`, and resolving that finding removed
the field. That is the intended outcome, not a regression. The two behaviours it
probed are now covered by `test_direction_policy_does_not_depend_on_how_updates_are_chunked`
and `test_each_direction_is_filtered_to_admissibility_independently` in
`experiments/shape_continuation/test_controller.py`.
