# Short acquisition inverse review

The completed paired-8 versus multistatic-8 comparison supports a longer,
controlled star experiment with acquisition as the only changed factor.
No inverse or BEM computation ran during this saved-data review.

[Decision, evidence, and next command](../../../../docs/iterations/implicit_mlp/iteration_02/05_acquisition_review.md)

- `motion_review.md/json`: signed motion, symmetric boundary distances,
  phase-aware five-lobe coefficients, and matched-work comparison.
- `motion_review.py`: reusable saved-run review with `--run-dir` and
  `--output-dir`; new reports require review and do not inherit promotion.
- `optimizer_review.py/md/json/csv`: true saved Adam state, clipping, bounds,
  accepted-step algebra, and proposal geometry.
- `geometry_review.py/md/json/csv`: field stability and binding trial constraints.
- `plot_review.py`, `comparison.png/pdf`: saved short-run comparison figures.
- `promotion.json`: reviewed initialization, evidence hashes, scope and caveats.
- `decisions.json`: hash-bound input to the explicit longer experiment.

The short run took about 17 minutes including validation and reporting; both
inverse phases together took 337 seconds. These are measured runtimes for the
short run, not guaranteed timings for the longer comparison.

The updated runner passed 96 relevant regression tests, including 39 matched
runner tests. Actual initialization/evidence hashes and report links were
verified. See `validation.json` for the exact validation scope.
