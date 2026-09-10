# Iteration 03 results — the Cartesian chart carries topology at radial parity

**Project:** Cartesian Fourier
**Experiment:** the user's 2026-09-10 direction — topology treatments for the
Cartesian Fourier chart, matching radial performance on every inverse case
**Date:** 2026-09-10
**Outcome:** all eight cases match. Five automatic topology inversions recover
with identical event sequences, and three challenge cases pass their declared
full-profile gates.

Only the chart differs. Both suites take the same observations, the same
independent oracles, the same schedules, budgets, resolutions and declared
tolerances, and neither receives a target component count or event policy. The
implementation and the five failures that shaped it are in
[02_implementation.md](02_implementation.md).

## Automatic topology inversions

The controller decides its own events. `run_fourier_topology_controller.py
--chart cartesian --profile full`, against the radial bundle
`results/inverse/radial_fourier/topology_controller/iteration-02-20260909`.

| Case | Components | Radial rel L2 | Cartesian rel L2 | Radial Hausdorff | Cartesian Hausdorff |
|---|---|---:|---:|---:|---:|
| repeated-birth | 0 → 1 → 2 → 3 | `1.62e-07` | `1.62e-07` | `9.251 um` | `9.262 um` |
| death | 3 → 2 | `1.10e-06` | `1.10e-06` | `40.54 um` | `40.58 um` |
| split | 1 → 2 | `2.89e-07` | `1.12e-05` | `15.60 um` | `295.9 um` |
| merge | 2 → 1 | `7.98e-05` | `7.88e-05` | `722.7 um` | `724.1 um` |
| mixed | 2 → 3 → 2 | `4.27e-07` | `4.28e-07` | `14.18 um` | `14.20 um` |

All five stop `recovered`. The accepted event sequences are identical case by
case — three births; one death; one split; one merge; a split then a death —
and no case needed an event the other did not.

Four of the five agree with the radial run to three significant figures in
both the data and the geometry. **The split does not**, and the reason is
recorded rather than smoothed over: the two runs accepted *different* cut
candidates. Radial's winner was a 12-mm corridor whose two children are
circular seeds, polished to `3.65e-08`; the Cartesian run's finite search
scored a 32-mm corridor with band-nine contour children better in the raw
objective, and only the best raw candidate of each event type and child count
receives the short polish budget, so the circle cut was left unpolished at
`0.204` and lost. Both runs then stopped at the controller's
`relative_error_tolerance` of `3e-3` as soon as they were inside it, which is
why the Cartesian run's `1.12e-05` is not refined further.

The two circle candidates themselves agree: raw `0.2014` radial against
`0.2038` Cartesian, for the same corridor. What differs is which corridors the
finite search retained at all — six families radial, nine Cartesian — off two
pre-split geometries whose bounding boxes agree to `0.14 mm`. So this is the
shared controller's discrete candidate search being sensitive to a sub-
millimetre difference in the state it is handed, not the Cartesian chart
representing or refining anything worse. It is downstream of the chart in the
sense that the two optimizers reached slightly different pre-split states, and
it would be worth confirming that the radial chart is equally sensitive; that
check is listed below.

## Challenge cases

`run_radial_fourier_topology_challenges.py --chart cartesian --profile full`,
against `results/inverse/radial_fourier/topology_challenges/`. Every declared
gate is the same in both charts: component count, cross-resolution topology
acceptance, monotone accepted objectives, training and holdout relative L2,
geometry error, and production-versus-refined prediction agreement.

| Case | Outcome | Train rel L2 (radial → Cartesian) | Holdout (radial → Cartesian) | Worst geometry error |
|---|---|---|---|---|
| Far wrong circle → two circles | **full_pass** | `1.928e-07` → `1.931e-07` | `1e-06` → `1e-06` | `10.79 nm` → `10.83 nm` |
| Large enclosing circle → two circles | **full_pass** | `1.928e-07` → `1.931e-07` | `1e-06` → `1e-06` | `10.79 nm` → `10.83 nm` |
| Middle circle → diagonal ellipse and star | **full_pass** | `5.678e-03` → `5.678e-03` | `5.245e-02` → `5.245e-02` | `551.6 um` → `551.6 um` |

The ellipse/star case is the strongest single piece of evidence here, because
it is eight staged optimizations deep and the two charts agree at every stage:

| Stage | Radial | Cartesian |
|---|---:|---:|
| pre-topology | `0.20782` | `0.20782` |
| split proposal, first component K1 | `0.19355` | `0.19355` |
| first component K2 | `0.18752` | `0.18752` |
| first component K5 | `0.17020` | `0.17020` |
| post-topology, 0.5 GHz | `6.1542e-03` | `6.1543e-03` |
| shape K2 | `7.3261e-07` | `7.3261e-07` |
| shape K5 | `3.3594e-10` | `3.3594e-10` |
| full training band | `7.1084e-05` | `7.1084e-05` |

The recorded stages agree just as closely: accepted iterations
`14, 15, 7, 14, 3` against `15, 15, 7, 14, 3`, infeasible trials `0, 15, 0, 0,
0` in both, and evaluation counts `105, 522, 264, 685, 180` against
`112, 528, 264, 685, 180` — identical in the last three stages, 1769 solves
against 1756 in total. One extra accepted update in the pre-topology stage is
the whole difference between the two runs.

## Cost

Iteration 1 reported the chart's cost honestly as roughly twice the radial
chart's — "26 coefficients against 11 means roughly 52 forward solves per
Jacobian against 22". **In the topology optimizer that gap is gone**, and
closing it was not an optimization but a correction: those 30 extra solves were
being spent probing coefficient directions the gauge annihilates. Measuring the
Jacobian along the gauge-fixed subspace instead costs `2K - 1` columns rather
than `4K + 2`. The matched two-circle regression now asserts *equal* evaluation
counts, and the ellipse/star case takes 1769 forward solves against the radial
run's 1756.

Iteration 1's own driver, `run_explicit_cartesian_fourier_inverse.py`, is
untouched and still pays the full `4K + 2`, so nothing here revises that run's
recorded cost. Whether the same correction applies to it is not measured.

Wall times are not a controlled comparison — the Cartesian cases here ran
eight-way concurrently on a 24-core machine and the radial bundles' concurrency
is not recorded — but they are in the same regime throughout: `13/14/106 s` for
the challenge cases against `12/12/93 s`.

## What this does and does not establish

It establishes that the Cartesian polar-angle chart carries automatic
birth, death, split and merge at the radial chart's accuracy, on this
project's noiseless same-material 0.5-GHz acquisition, without a target count
or event policy, and at the same cost.

It does not establish anything the radial cycle had not already established
about the physics: nested holes, touching boundaries, multi-material regions,
noise and global convergence remain outside the demonstrated scope, exactly as
in the radial bundle.

It also does not establish that the two charts are *different*. The opposite:
iteration 2's open question 3 asked whether the gauge-fixed Cartesian chart is
distinguishable from the radial chart in what it can represent, and the answer
these measurements reach is **no**. The gauge-fixed set is a linear subspace of
the coefficient space, and it is exactly the radial chart one band lower; a
radial component of band `K` embeds in it at band `K + 1` to machine precision,
and every fixed point of the re-gauge is such an embedding. The Cartesian
chart's extra capability — a contour no radial component can hold — survives
only where the gauge is *not* imposed, and that regime is the one iteration 1
measured and rejected. Under the Cartesian chart a contour fit that cannot be
gauge-fixed is refused outright: the split case's topology pass records 12 such
refusals.

## Candidate next checks

| Priority | Question | Cheapest discriminating check |
|---|---|---|
| 1 | Does the split's candidate-selection variance affect the radial chart too? | Re-run the radial split from a perturbed pre-split state and see whether it also selects a contour cut |
| 2 | Is the polish budget the actual lever? | Polish the best *two* raw candidates per group and re-run both charts; the change is shared, so both bundles must be regenerated |
| 3 | Does the chart buy anything at all once gauge-fixed? | It is now a testable claim that it does not. A target that is band-limited in polar angle but *not* star-shaped about its own mean would separate them, if one exists in this project's family |
| 4 | Does the un-gauged chart carry a non-star-shaped component through a topology event? | It is implemented and refused by policy, not by capability; measuring the drift directly would price that refusal |

## Reproduce

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/topology-matplotlib \
  python run_fourier_topology_controller.py --chart cartesian --profile full \
  --output results/inverse/cartesian_fourier/topology_controller/fresh-run

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/topology-matplotlib \
  python run_radial_fourier_topology_challenges.py --chart cartesian --profile full
```

Use `--case <name>` for one case, `--skip-video` for numerical work, and
`--render-only --output <bundle>` to re-render an existing controller bundle
without solving. Drop `--chart cartesian` to get the radial bundles these are
matched against; that path is unchanged.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest \
  pytest/sdf_inverse/test_cartesian_fourier_topology.py \
  pytest/sdf_inverse/test_cartesian_fourier_chart.py \
  pytest/sdf_inverse/test_topology_controller.py \
  pytest/sdf_inverse/test_radial_topology.py \
  pytest/sdf_inverse/test_radial_topology_challenges.py -q
```

## Evidence

- `results/inverse/cartesian_fourier/topology_controller/iteration-03-20260910/`
  — five inversion videos, metrics, trajectories, topology passes, observations
  and sensitivity rasters.
- `results/inverse/cartesian_fourier/topology_challenges/challenge-suite-20260910/`
  — three challenge bundles with videos, trajectories and TD rasters.
- Regressions: `pytest/sdf_inverse/test_cartesian_fourier_topology.py`
  (13 tests). The full `pytest/sdf_inverse` suite is 505 passing: the 492 that
  pre-date this iteration all still pass, and two of them changed only to
  follow a helper renamed from `_sample_radial` to `_sample_component` now
  that it samples either chart.
