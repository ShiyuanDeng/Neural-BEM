# Restoring the legacy single-object controls to the SPD comparison fitter

2026-09-24. Author: Claude (Opus 5.5). Independent reviewer: unassigned.
**User direction, verbatim:** "big problem is current spd baseline cant even
recover single star shaped objects while we clearly had legacy pipeline that
succeeded. check latest commit for more. if those missing criteria seems
convincing to you then add them to our spd here, so at least we are not fixing
sc toward a solved issue."

## Why this comes before SC-033

SC-030 compared the clean hybrid with SPD-008 on the six SC cases. The SPD arm
stopped on circle (7.49 mm RMS) and star (7.34 mm). The legacy single-object
inverse recovers both from the same starts (SC-018). If the SC track measures
its progress against a baseline that fails a solved problem, it can end up
"fixing" a difference that the legacy controls already fix. The comparison
baseline therefore gets those controls first. SC-033 stays proposed and
unapproved.

## Evidence

- [SPD single-object diagnostic](../../../../../results/validation/speedup/SPD-single-object-diagnostic-20260924/README.md)
  (commits `541124f`, `23238c9`). The SPD fitter itself, started at K4 and
  widened to K17 (4 → 6 → 9 → 17), recovers the circle (2.5e-9 mm radial RMS)
  and the star (1.0e-6 mm). The full-K17 initial Jacobian has condition number
  8.75e9, compared with 1.694 at K4. Adding only the legacy m⁴ ridge at full K17
  gives 0.008 mm radial RMS on the circle, but the run hit its 900 s diagnostic
  limit in stage 3.
- Measured here from SC-030's saved stage-1 trajectories (script:
  `first_moves.py`, recorded in the SC-034 bundle). The first accepted boundary
  moves are **20.4 mm (circle)** and **40.8 mm (star)**. The circle's true shape
  has no radial content above mode 5, yet the fit has **8.85 mm** RMS of it by
  the end of stage 1. The star's fit has 9.21 mm after the first accepted step.
  Kite and peanut show the same pattern (first moves 12.9 and 17.6 mm; 6.5–6.7 mm
  RMS above mode 5 by the end of stage 1).
- The legacy code's own record of this failure
  (`solvers/sdf_inverse/neural_optimization.py:246–252`): "a growing ripple at
  the highest available mode: undamped Gauss-Newton inverts the near-null column
  of an unresolvable harmonic, rescaling an oversized step keeps that direction,
  and an any-decrease test accepts the result forever." Four controls were added
  against it: the damping floor, the m⁴ ridge, the damping-enforced trust region
  and Armijo. SC-030's SPD trajectories show that failure.

## Decision on each legacy control

| Control | Legacy single-object inverse | SPD-008 as run in SC-030 | Decision |
|---|---|---|---|
| Low-order start with harmonic continuation | Radial orders 3/5/5 | K17 (33 directions) from the first frequency | **Add.** Strongest evidence: it alone recovers circle and star. The ladder is Cartesian K = 4/6/8/10, radial orders 3/5/7/9, which is the hybrid's M through the declared mapping K = M + 1 (`spd_cases.py`), so shape capacity is matched |
| m⁴ step ridge | `1e-4 · max diag(JᵀJ) · m⁴` outside the damping | None | **Add.** It targets the documented ripple mechanism; the circle full-K17 control supports it. It prices the step, not the state, so it does not bias the stationary point |
| Damping floor | 1e-6 | Machine tiny | **Add** as part of the package; not separately attributed |
| Physical trust region | 2 mm maximum normal move; damping raised (then refined in log λ) until the step fits; rescale only as fallback | Per-coefficient clips (18/12/3 mm Cartesian roles); accepted moves of 13–41 mm | **Add.** The measured oversized moves are exactly what it bounds |
| Armijo acceptance | 1e-4 of the linear-model decrease | Any decrease, plus refined agreement | **Add** as part of the package |
| Parameter-speed cap, tangential prior | Cartesian chart without a gauge | Polar-angle gauge removes reparameterization directions | **Do not add.** The gauge subsumes them |
| Adaptive FD stencil shrinking | Up to 4 shrinks | FD-compatible stencil; star stopped on one unresolved column at a distorted endpoint | **Defer.** A symptom of the path; reconsider only if the restored fitter still reaches the stencil guard |
| Smaller-step retry after a cross-resolution failure | Not a legacy control | Whole-stage numerical failure | **Defer**, as already decided for the hybrid |
| Frequency schedule 0.5/1.5/2.5 GHz | Legacy | SC's 0.5/0.75/1.0/1.25 GHz | **Not changed.** Both SC methods share the SC schedule |

All additions are opt-in: `StepSafeguards` in `solvers/sdf_inverse/radial_topology.py`
and a `step_safeguards=None` pass-through in `run_top017.fit_stage`. The
topology pipeline's production defaults, and the TOP-025/SPD-008
qualifications, are untouched. With the controls off, the code must replay
SC-030's SPD circle trajectory exactly.

## Representation compatibility

The SPD polar-angle chart holds only curves that are star-shaped about their
centre. On a 61 × 61 grid of candidate centres within ±30 mm of the centroid,
**C and hook have no point about which they are star-shaped**. Circle, star,
kite and peanut do. SPD endpoints on C and hook are therefore limited by the
representation, whatever the step controls. Only circle, star, kite and
peanut are fair tests of the restored fitter.

## Proposed contract

[SC-034 plan](../03_plan.md): three SPD arms (ladder only, controls only, both)
on the six SC cases, with a pre-declared adoption rule for the combined arm.
