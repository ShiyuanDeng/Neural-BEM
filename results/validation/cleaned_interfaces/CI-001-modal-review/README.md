# CI-001-modal review: all 36 configurations with modal Müller

2026-10-01. The user ran the frozen CI-001 policy on all 36 configurations,
with `solver=modal_muller`, `device=auto`, four frequency threads and one
worker. The run was 01:16–01:34 BST on commit `4f8ab6bf`. This folder compares
it case by case with the nodal CI-001 campaign (`5cabf238`) and diagnoses
each difference.

**Result: modal passes 19/36 against nodal's 28/36. 27 cases are identical:
same status, same stage decisions, same work units, endpoints within
2.3e-7 mm, and about 3× less wall time. The remaining 9 cases fail for two
modal-only defects:**

- **Graf refusal at the original start (7 cases).** Every `development_c` and
  `opposite_c` start is refused before localization.
- **Under-resolved production level (2 cases).** Two contrast-13.3 stages
  stop partway with a resolution `NUMERICAL_FAILURE`.

**Neither defect is a policy or optimizer difference. Both are in the
service, and both are fixable.**

## Outcome against nodal CI-001

| | Modal | Nodal |
|---|---:|---:|
| Pass the frozen contract | **19** | 28 |
| Recovered | 28 | 34 |
| Same status / same stage decisions / same units | 27 / 27 / 27 | – |
| Exceptions (original-start audit refused) | 7 | 0 |
| Resolution `NUMERICAL_FAILURE` | 2 | 0 |
| Device fallbacks / failed derivatives | 0 / 0 | – |

The 27 identical cases are 19 passes and 8 regressions that nodal shares:

- `circle_to_star`, a noiseless residual shortfall;
- seven noisy cases that stop at the declared discrepancy.

These are the known CI-001 findings and are not caused by the backend. All
38,395 modal evaluations ran on `cuda-modal`.

## Problem 1: Graf refusal at offset starts (7 cases)

Affected: `far__development_c`, `far__opposite_c`, `modal__c{2,4,13.3}__development_c`
and `modal__c{4,13.3}__opposite_c`.

The prescribed start is a circle of radius 1.3 units centred 4.3–4.6
units from the origin. The nearest source or receiver lies outside the curve,
0.37 units (`development_c`) or 0.19 units (`opposite_c`) from it. Kress
512 and 1024 agree to ≤ 1.2e-14 there.

The modal service expands sources and receivers about the curve centre
`z_0`. The ratio ρ/d of the bounding radius to the nearest point is 0.78 or
0.87. Every evaluation therefore raises `Graf expansion needs more than 128
orders`. The initial audit therefore fails, and the runner stops with
`Original-start numerical audit failed` (19–22 refused evaluations per case).

[`diagnose.py graf`](diagnose.py) evaluates the service's own bound in log
space ([diagnostics_graf.json](diagnostics_graf.json)):

| Start | ρ/d | Required order (0.25 / 2.5 GHz) | Order where H_l(kd) overflows | Cap |
|---|---:|---:|---:|---:|
| `development_c` | 0.777 | 131 / 136 | 154 / 251 | 128 |
| `opposite_c` | 0.871 | 240 / 248 | 151 / 244 | 128 |

Raising the cap is not enough. The service multiplies an unscaled
H_l(kd), which overflows float64 near order 150 at 0.25 GHz, by an unscaled
regular wave of size about (kρ/2)^l/l!. At `opposite_c` the required order
exceeds the overflow order. The defect is the unscaled factorization, not
the 128 cap alone. The same arithmetic limits any curve whose bounding
circle about `z_0` comes close to the acquisition, including elongated
curves.

## Problem 2: production resolution too coarse at contrast 13.3 (2 cases)

Affected:

- `modal__c13.3__shifted_star`: stops at `fixed_M49` with 0 accepted steps.
  It is not recovered (RMS 0.016 mm against nodal 0.0013 mm; Hausdorff bound
  0.068 mm against 0.034 mm).
- `modal__c13.3__new_asymmetric`: stops at `fixed_M61` after 1 step. It is
  still recovered, but fails the residual gate.

LM's acceptance check found a production-versus-refined prediction
discrepancy of 1.27e-7 and 1.08e-7. The tolerance is 1e-7, at 2.25–2.5 GHz.
Nodal's discrepancy in the same stages is ≤ 5.4e-14.

[`diagnose.py resolution`](diagnose.py) evaluates the archived stage-start
curves (K=192) against 1024-node Kress, at the four highest frequencies
([diagnostics_resolution.json](diagnostics_resolution.json)):

| Curve | Kress 512 | Modal K_trace 96 (production) | 128 (refined) | 160 | 192 |
|---|---:|---:|---:|---:|---:|
| `shifted_star` M49 | ≤ 2.1e-14 | 1.3–5.2e-8 | 3.6–9.7e-11 | ≤ 3.2e-13 | ≤ 5.6e-13 |
| `new_asymmetric` M61 | ≤ 2.0e-14 | 3.0–9.3e-8 | 1.4–3.8e-10 | ≤ 1.1e-12 | ≤ 1.4e-12 |

The resolution rule `K_trace = max(64, 32*ceil(K/64))` depends only on the
storage band. It ignores the interior wavenumber, which is 3.8 k at contrast
13.3, and the shape detail released at high M. At K=192 its production level
sits within 2× of the 1e-7 acceptance tolerance. The replayed stages
qualified that level, but only up to M43.

The margin is thin across the campaign. The worst modal discrepancy per case
exceeds 1e-8 in 4 cases and 1e-9 in 8. Nodal stays ≤ 3.1e-13 except in the
two contrast-13.3 C cases that it also does not recover.

## Runtime (single unmatched runs)

The two campaigns ran on the same host, with the same settings and one run
each. This is not the repeated matched-pair runtime gate.

| 27 identical cases | Modal | Nodal | Ratio |
|---|---:|---:|---:|
| Sum of case wall times | 923 s | 2,754 s | 3.0× |
| Sum of fit + localization | 856 s | 2,373 s | 2.8× |
| Per-case speed-up | – | – | 2.4–4.1× (median 3.0×) |

The modal stage seconds (thread-summed over all 36 cases) are:

| Stage | Seconds | Share |
|---|---:|---:|
| Graf waves (CPU) | 624 | 47% |
| Assembly (CUDA) | 332 | 25% |
| LU | 170 | 13% |
| Geometry | 117 | 9% |
| Fields | 68 | 5% |
| Jacobian | 25 | 2% |

So the CPU Graf step, not the CUDA assembly, is now the largest physics
cost.

## Recommended fixes (proposed, not run)

1. **Scaled Graf factorization.** Carry Ĥ_l = H_l(kd)·(kρ/2)^l/l!, built by
   the forward ratio recurrence in log space, against the unit regular waves
   (ζ/ρ)^n. Take the order from the same bound evaluated in log space, with
   no fixed cap.

   Falsifiable test: the seven refused starts evaluate at all 19
   frequencies within 1e-12 of 1024-node Kress, and those seven cases then
   reproduce nodal CI-001's decisions.
2. **One-step-finer modal profile.** Use production `K_trace = 32*ceil(K/64)+32`
   (128 at K=192) and refined +32 (160). On the two failing curves this gives
   ≤ 3.8e-10 at production and ≤ 1.1e-12 at refined. It costs about 1.45× per
   CPU assembly at K=192.

   Falsifiable test: replaying both failing stages from their archived
   starts gives discrepancies ≤ 1e-9 and nodal's stage decisions.
3. **Then** rerun the nine affected cases as a new modal campaign. Both fixes
   edit `modal_*.py`, which `CI-001-modal`'s manifest hashes. Next, speed
   work should go to the Graf stage, for example caching the per-frequency
   outgoing factors.

## Reproduce

```bash
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
"$PY" -m experiments.cleaned_interface.modal_muller report --output results/validation/cleaned_interfaces/CI-001-modal
D=results/validation/cleaned_interfaces/CI-001-modal-review
"$PY" $D/summarize.py            # summary.json: per-case comparison with nodal CI-001
"$PY" $D/diagnose.py graf        # diagnostics_graf.json
"$PY" $D/diagnose.py resolution  # diagnostics_resolution.json
```
