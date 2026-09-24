# Legacy single-object recovery versus SC-030

2026-09-24. User-requested investigation. Owner: Codex; owner review only.
**COMPLETE: saved-artifact and source audit, zero field solves, no inverse reruns.**
No numerical defaults, measured bundles, or executed contracts were changed.

## Finding and correction

The successful legacy single-object inverse exists and does not need topology
treatment. SC-030 did **not** run that inverse with execution speedups. It ran
the topology pipeline's later, different continuation optimizer directly from
a wrong circle, with its full K17 space open. Calling that a representative
comparison against the successful legacy inverse was too broad.

The previous conversational explanation about missing topology preparation was
incomplete: it describes a difference from the full SPD campaign, but cannot
explain away the old single-object successes. SC-018 already establishes those
successes without any topology phase. SPD-008 names qualified execution
optimizations for its measured fitter; it is not evidence of recovery parity
between two different optimizer implementations.

## Successful evidence without topology

The September 10 [direct Cartesian run](../../../../../results/inverse/cartesian_fourier/cartesian-k6-ellipse-to-star-nystrom-kress-20260910/summary.md)
recovers a star from a wrong ellipse in **41 accepted updates**: 19 at 0.5 GHz,
20 at cumulative 0.5/1.5 GHz, and 2 at cumulative 0.5/1.5/2.5 GHz. Its active
Cartesian bands are **K4, K6, K6**. It uses no MLP optimization or topology
operations. Its very strict historical parity gate narrowly fails on the
training residual (1.296e-7 versus 1e-7), not practical geometry recovery.

More decisively, [SC-018](../../../../../results/validation/shape_continuation/SC-018-legacy-single-object/README.md)
freshly reran the same legacy implementation on circle/ellipse/star starts
against circle/star targets. **All six pass its practical recovery and numerical
gates.** Selected outcomes:

| Legacy case | Accepted updates by stage | Conservative boundary upper bound |
|---|---|---:|
| Circle to circle | 19 + 9 + 0 | 0.0192 mm |
| Circle to star | 19 + 16 + 0 | 0.0310 mm |
| Ellipse to star | 19 + 20 + 2 | 0.0310 mm |

The smaller sampled errors are retained in the artifacts; the table uses the
continuous-boundary upper bounds rather than claiming certified nanometres.

The [reproducible audit](legacy_baseline_audit/audit.json) verifies that SC-018
and SC-030's circle/star fixtures have the same starting boundaries to below
1e-9 m and the same target curves to below 1e-12 m. Their common observed
frequency columns agree to at worst 7.88e-15 relative for circle and 3.86e-10 for
star. At 0.5 GHz the star observations differ by only 4.85e-13. Different
targets or acquisition data therefore do not explain the first-stage failure.
The four inspected legacy numerical/driver files still match SC-018's hashes.

## What changed in the algorithm

| Mechanism | Successful legacy inverse | SC-030 SPD arm |
|---|---|---|
| Fitter | `run_alternating_neural_inverse`, explicit Cartesian `curve_only` path | `run_multiradial_fd_inverse` through `run_top017.fit_stage` |
| Shape space | Active K4 → K6 → K6; phase projection and trial regauging | K17 throughout; 33 polar-gauge directions |
| Frequency schedule | Cumulative 0.5 → 1.5 → 2.5 GHz | Cumulative 0.5 → 0.75 → 1.0 → 1.25 GHz |
| Step control | 2 mm maximum sampled normal displacement; damping search enforces the bound | Separate coefficient/direction clips; 18/12/3 mm Cartesian role bounds, not a 2 mm physical displacement cap |
| Step regularization | `1e-4 * max(diag(JᵀJ)) * m⁴` ridge, outside the LM damping multiplier | No equivalent modal ridge |
| Damping floor | 1e-6 | Machine-tiny floor |
| Acceptance | Armijo model-relative decrease, coefficient 1e-4 | Production decrease plus native refined numerical/decrease checks |
| Other guards | Parameter-speed ratio cap 16 | Native polar-gauge feasibility and 8 mm conservative radial certificate |
| Iteration allocation | 150 total; historical allocation 19/20/111 | 22 per stage |

Source paths: [legacy configuration and step construction](../../../../../solvers/sdf_inverse/neural_optimization.py),
[legacy schedule](../../../../../run_explicit_cartesian_fourier_inverse.py),
[SC-030 driver](../../../../../experiments/shape_continuation/spd008_comparison.py),
[SPD step construction](../../../../../solvers/sdf_inverse/radial_topology.py).
The coordinate systems also differ: numeric coefficient bounds alone are not
equivalent physical trust regions. These are algorithm changes, not cache or
kernel acceleration. The later frequency schedules differ, but the divergence
below already occurs on the shared first frequency.

## Where SC-030 goes wrong in the saved trajectory

Evaluating only saved Fourier coefficients on 4096 points gives:

| SC-030 target | First accepted displacement projected on the initial circle's normal | Radial RMS above mode 5 after that update |
|---|---:|---:|
| Circle | 20.350 mm | 0.081 mm |
| Star | 40.706 mm | 9.210 mm |

The starting circle has no such high-mode content. The true star's radial
profile has only the mean and mode 5. Circle's above-mode-5 radial RMS rises
to **4.156 mm by update 2**, then **7.993 mm by update 4**. Thus large, unwanted
shape oscillations appear before the terminal safeguards fire.

- Circle stops after 13 accepted updates at 0.5 GHz. The next candidate's
  512/1024 field discrepancy is 2.616e-5 versus a 1e-5 threshold. The retained
  state already has 8.850 mm radial RMS above mode 5.
- Star's first stage accepts 19 updates, but its conservative radial
  certificate ends at **8.000013 mm**, essentially the 8 mm floor. It records
  218 candidate refusals for that floor and 11 for nonmonotone polar angle.
  After another five accepted updates at 0.5/0.75 GHz, one derivative column
  becomes unresolved and the stage hard-stops.

The radial certificate is conservative: star's sampled minimum radius at the
first-stage endpoint is about 25.985 mm. Do not describe its 8 mm certificate
as an actual 8 mm neck or a curvature radius.

This closely resembles the spurious-ripple failure already documented in the
[September 6 development report](../../../../reports/inverse_development_through_2026-09-06.md#why-the-modal-step-is-regularized).
That report motivated the damping floor, mode-fourth-power ridge,
damping-controlled physical step bound and Armijo rule still present in the
successful legacy fitter. SC-030's chosen fitter does not retain those controls.

## Interpretation and next decision

**Established:** the baseline identity changed, known legacy controls were
absent, the common first-stage physical problem agrees, and oversized accepted
moves create high-mode structure before the observed stops. The numerical and
derivative stops are real; they are downstream symptoms in these trajectories.

**Not established:** which individual difference dominates, whether restoring
only one control suffices, or how the legacy method performs on all six atlas
shapes. That requires controlled reruns, not interpretation of these histories.
No derivative formula or forward solver implementation bug was established by
this audit. The existing SC-030 outcomes and exact cache equivalence remain valid
for the configuration actually measured.

Re-establish the successful single-object algorithm as the recovery reference
before a broad hybrid-superiority claim. First reproduce its circle/star
behavior, then qualify execution speedups separately. For a causal diagnosis,
hold the observations, starting curve, geometry and numerical checks fixed
while testing the early active band and the legacy step controls. Do not add
topology operations to explain a success that never needed them. Any subsequent
six-case comparison must declare its shared schedule and budget explicitly.
This review does not execute or approve SC-033 or a successor campaign.

## Reproduction

```bash
OPENBLAS_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python docs/iterations/shape_frequency_continuation/iteration_15/02_proposals/legacy_baseline_audit/audit.py
```

The script imports NumPy and the standard library only, reads saved artifacts,
checks the common fixtures and legacy source hashes, and regenerates
`legacy_baseline_audit/audit.json`. It does not import an optimizer or solver.
