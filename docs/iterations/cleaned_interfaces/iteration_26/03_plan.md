# NL-001: is the grid search needed? TG-002 with and without localization

Pre-registered 2026-10-04. **PROPOSED — NOT APPROVED TO RUN.** The user replied "go" to
building TG-002 and pre-registering this experiment. Running NL-001 needs a separate,
explicit approval. Branch: the existing `feature/shape-frequency-continuation`. No new
branch or worktree. Owner: Claude. Independent reviewer: unassigned. No production default
or earlier source/result changes.

## Why

The CI-001 policy starts every fit with an exhaustive disk search
(`localization.py`: about 750k centre × radius candidates from exact Mie data). In SC-050,
from far starts, the shape continuation alone recovered 0/6 transfer cases and recovered
6/6 with the search. So the far-start results are owed to the grid search, not to the
node-free physics.

The user decided on 2026-10-04 to stop using far-start cases. Future scenes may be visibly
off-centre, but they must be recoverable without any grid search. TG-002 is the
replacement benchmark. NL-001 measures whether the grid search still matters on it.

## Inputs (TG-002, frozen before any fit)

Ten scenes: `circle`, `kite`, `peanut`, `star`, `asymmetric`, `c_shape`, `hook`, `cross`,
`cog` and `aphex_twin`. Each is at contrasts 0.5, 4 and 13.3, giving 30 cases. Definitions
are in `experiments/benchmark/scenes.py`; inputs and qualification are in
`results/validation/cleaned_interfaces/TG-002/`.

- **One start for every case:** a 65 mm circle at (0.5, 0.5) m.
- **Target centroids are 22–38 mm off centre,** each in a different direction, with frozen
  rotations. `test_placements_are_the_frozen_preregistered_values` pins them.
- **This offset range has recorded support:** SC-043/SC-044 recovered all 12 contrast-0.5
  configurations from 13–39 mm offsets with no localization. Those runs used the older SC
  policy, so this is evidence, not proof, for the current policy.
- **Data:** noiseless real and damped (k(1 + 0.25i)) catalogs, computed with CPU reference
  `nodal_kress` and qualified by N1024/N2048 doubling at 1e-8.

## One change

Both arms use the node-free configuration: `modal_muller` physics and the
`certified_spectral` (NU-006) geometry update. Everything else is the default
`CumulativePolicy`, unchanged.

- **Arm A (primary):** `localization='none'`. `campaign.keep_start` replaces the grid
  search. The prescribed start is kept, and the policy's 0.25 GHz damped warm-up (band 1,
  a circle fit) then moves it. This is an injected `fit(..., localization_adapter=)`; no
  sealed source is edited.
- **Arm B (matched control):** `localization='grid'`, the legacy SC-050 disk search.

```bash
PYTHONPATH=solvers:. python -m experiments.benchmark.nl001 run --arm A
PYTHONPATH=solvers:. python -m experiments.benchmark.nl001 run --arm B
PYTHONPATH=solvers:. python -m experiments.benchmark.nl001 report
```

Execution: `device=auto` (CUDA), 4 frequency threads, 2 workers. The cap is 3 workers,
because fits can peak near 8 GB each. Arm A runs first, then arm B. Output goes to
`results/validation/cleaned_interfaces/NL-001/{A,B}/runs/<case>/`. An existing run folder is
reused, and an incomplete one is refused. Exceptions count as not recovered.

Budget: the policy's own per-case caps apply (13,412 units, 1,800 s fit, 300 s audit). The
worst case is 60 × 2,100 s / 2 workers ≈ 17.5 h. Typical runs should be far shorter, but no
modal timing on these scenes exists yet, so no typical figure is claimed.

## Recovery (unchanged CI-001 gates)

A case is recovered only if all of these hold: the final numerical audit passes, RMS ≤ 1 mm,
the Hausdorff upper bound ≤ 2 mm, and every per-frequency relative residual ≤ 0.003 (the
data are noiseless).

## Readings (pre-registered)

- **P1 (near-start capture, arm A, contrast 0.5):** the six scenes with recorded near-start
  history (`circle`, `kite`, `peanut`, `star`, `c_shape`, `hook`) recover at least 5/6.
  - Fewer than 5 means the current policy has lost the old SC near-start capture, and that
    loss must be explained before NL-001 is read further.
- **P2 (does the grid matter), the decision reading:** at each contrast, arm A recovers at
  least (arm B − 1) of the 10 scenes.
  - If this holds at all three contrasts, new experiments run without the grid search, and
    the node-free claim is stated without a locator. `--localization none` is already the
    benchmark CLI default.
  - If it fails at any contrast, the grid search is load-bearing there. Report the scenes;
    any claim at that contrast must name the two-part method (disk locator, then node-free
    refinement).
- **P3 (hard tail):** at contrast 13.3, `c_shape` fails in both arms. This is consistent with
  FM-003 to FM-005, where it needed a stage-2 census. At least one of `cog` and `aphex_twin`
  also fails at 13.3 in arm A, the scenes with the most high-band content.
- **Reported, not predicted:** per-case seconds and work units for A against B, final RMS,
  and outcome categories.

No scene is dropped and no placement is changed after any result. A failed prediction is
reported as failed.
