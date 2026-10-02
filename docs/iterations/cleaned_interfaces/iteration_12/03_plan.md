# NU-004: modal Müller physics with the spline-free increment map (pre-registered)

2026-10-02. Implementation owner: Claude. Written and committed **before** any NU-004
run; the decision rules below are fixed.

## Approval

[Iteration 11](../iteration_11/01_results.md) proposed NU-004 as its first next step. The user
replied **"yes go"**. That reply approves NU-004 only. The other two proposals (a validity
check that does not sample, and a cheaper quadrature) have no ID and are not part of this plan.

## Scope, stated plainly

NU-004 combines the node-free forward solver (modal Müller,
[`modal_muller.py`](../../../../experiments/cleaned_interface/modal_muller.py), with the
iteration 07 scaled Graf factorization and 128/160 profile) and the spline-free trial map
(NU-003 `SpectralProjectedUpdate`). One node-based piece remains: the sampled
self-intersection test on the moved curve inside the trial map, inherited unchanged from
CI-001. A pass therefore means *node-free physics and spline-free geometry*, **not a fully
node-free inverse**. The earlier description of NU-004 as "fully node-free end to end"
overstated it.

## Arms

| Campaign | Solver | Trial map | Role |
|---|---|---|---|
| `NU-004-MS` | `modal_muller` | `SpectralProjectedUpdate` (NU-003) | decisive |
| `NU-004-MN` | `modal_muller` | `ProjectedUpdate` (CI-001 spline) | attribution control |
| `CI-001` (archived) | `nodal_kress` | `ProjectedUpdate` | reference |

The control is needed because the six core cases have not been run with the current modal
profile. CI-001-modal used the older 96/128 profile, and CI-001-modal-r2 reran only nine
other cases.

Both arms use NU-001's `ArmPolicy` (identical time caps; work-unit caps unchanged), the
unchanged CI-001 schedule, LM and clips, augmentation reused from CI-001, the RTX 5090 with
`device=auto` and four frequency threads, one case at a time, from the original start.
Code: [`nu004.py`](../../../../experiments/cleaned_interface/nu004.py). No frozen source is
modified.

## Decision rule (fixed)

**Decisive.** Apply the NU-001 rule, unchanged, to `NU-004-MS` against nodal CI-001:
- drift flags: max r_σ > 1.5; max r_σ > 1.1 × nodal; or log|W|² degree > 1.3 × nodal at any stage;
- match: (passes frozen gates or nodal does not) and (recovers or nodal does not);
- **retained** if there is no drift flag and the match count is ≥ 5/6.

**Attribution (applied only if MS is not retained).** Apply the same rule to `NU-004-MN`.
- If MN fails on the same cases as MS, the modal backend is the cause.
- If MN passes where MS fails, the spectral map interacts with modal physics.

**Logged, not decisive.** MS against MN: per-stage accepted steps, fit units and
final-curve distance. Also, for every arm: total wall time, physics seconds and geometry
seconds.

## Predictions

- MN matches nodal on 6/6, as CI-001-modal did on these cases under the older profile.
- MS is decision-identical to MN, as NU-003 was to nodal.
- The six-case wall time of MS is below nodal's 573 s. CI-001-modal took 181 s; the finer
  profile and the 2.2× geometry cost of the quadrature both add to that.

## Not in scope

All-36 retention, matched runtime pairs, the validity test that does not sample, and the
cheaper quadrature.
