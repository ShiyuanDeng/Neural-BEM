# Modal Müller fixes after CI-001-modal: scaled Graf and a finer profile

2026-10-01. The [CI-001-modal review](../CI-001-modal-review/README.md) found
two modal-only service limits behind 9 of the 36 status changes. It
proposed two fixes and a rerun of the affected cases. The user approved
with **"yes go fix them"**.

**Result: both identified problems are fixed. 7 of the 9 affected cases now
pass and match nodal CI-001: same stage decisions, same units, and RMS
within 2.7e-7 mm (≤ 1.5e-11 mm for the five low-contrast starts), in 2.8×
less wall time. The other 2 are the known
contrast-13.3 C failures, which nodal also does not recover.** Every
backend's run of those two ends in a resolution `NUMERICAL_FAILURE`. Modal
now gets past the start but stops at `fixed_M31`, where nodal stops at
`fixed_M43`, so they score `REGRESSION` against nodal's `PASS`. On the
rejected trial curve, modal needs K_trace ≈ 192–224 for the accuracy
Kress 512 reaches. A fixed profile cannot guarantee that margin. The other
27 cases have not been rerun with the finer profile.

## Changes

[`modal_operator.py`](../../../../experiments/cleaned_interface/modal_operator.py):

- **Scaled Graf factorization.** Row l of the regular waves is divided by
  s_l = (kρ/2)^|l|/|l|!. The outgoing factor H_l(kd) is multiplied by s_l
  and produced by the forward recurrence `scaled_hankel`. The products are
  unchanged, but orders of 250 and more neither overflow nor underflow.
  `graf_order` evaluates the same DLMF 10.14.4 bound through that
  recurrence and replaces the assumed ρ/d tail with a proved geometric
  ratio. If |H_(M-1)| ≤ |H_M| at some M ≥ |kd|, the recurrence keeps |H_l|
  increasing. Then b_(l+1)/b_l ≤ max((Mρ/d+a)/(M+1), ρ/d) for l ≥ M. The
  fixed 128-order cap is gone; refusal now happens only beyond 1024 orders.

[`modal_muller.py`](../../../../experiments/cleaned_interface/modal_muller.py):

- **One-step-finer profile.** Production is
  `K_trace = max(64, 32*(ceil(K/64)+1))` and refined adds 32. That is 128/160
  at K=192 (was 96/128) and 96/128 at K=128. K ≤ 64 (the damped prefix and
  warm-up) is unchanged.

Two tests were added. One checks `scaled_hankel` against mpmath to order 260,
including values beyond float64. The other evaluates the `opposite_c` start
against Kress 1024. The profile assertion was updated. Policy, LM, nodal and
CI-001-frozen sources are unchanged, and CI-001 `verify` passes.
`CI-001-modal` itself can no longer be re-verified, because it hashed the old
`modal_*.py`; its `sources.tar.gz` keeps them.

## Recurrence accuracy

The scaled recurrence agrees with mpmath to about 3e-15 relative up to
order 120 (x = 1.3, scale 0.1). SciPy's `hankel1` drifts there: 1.4e-12 at
order 118, 8e-9 at 119 and 1e-5 at 120. The old code used it up to order 128.

## Predeclared test 1: the seven refused starts

[`starts.py`](starts.py) ([starts.json](starts.json)). Every real frequency,
the initial audit's production and refined tokens (K_trace 64/96), CPU and
CUDA, against 1024-node CPU Kress.

| Start, contrast | Graf orders | CPU 64 / 96 | CUDA 64 / 96 | Audit 64-vs-96 | Kress 512 |
|---|---:|---:|---:|---:|---:|
| `development_c`, 0.5 | 131–136 | 1.5e-13 / 1.5e-13 | 1.5e-13 / 1.5e-13 | 2.2e-13 | 9.2e-15 |
| `development_c`, 2 | 131–136 | 5.6e-14 / 8.2e-14 | 7.7e-14 / 7.6e-14 | 1.1e-13 | 6.0e-15 |
| `development_c`, 4 | 131–136 | 1.5e-13 / 1.5e-13 | 1.1e-13 / 1.9e-13 | 2.1e-13 | 4.8e-15 |
| `development_c`, 13.3 | 131–136 | 9.1e-13 / 7.6e-13 | 8.3e-13 / 1.4e-12 | 1.5e-12 | 1.8e-14 |
| `opposite_c`, 0.5 | 240–248 | 1.2e-13 / 1.0e-13 | 1.3e-13 / 1.0e-13 | 2.0e-13 | 9.5e-15 |
| `opposite_c`, 4 | 240–248 | 5.2e-13 / 2.6e-13 | 2.2e-13 / 6.1e-13 | 3.6e-13 | 1.2e-14 |
| `opposite_c`, 13.3 | 240–248 | 1.0e-12 / 2.3e-12 | 1.1e-12 / 2.4e-12 | 2.9e-12 | 8.3e-14 |

The table's last case also stands for the `far` panel at contrast 0.5. Every
evaluation ran on `cuda-modal` or the CPU reference without refusal.

**The predeclared ≤ 1e-12 gate is missed: worst 2.4e-12, at contrast 13.3.**
The excess appears only at contrast 4 and 13.3. It is not monotone in
K_trace and differs between CPU and CUDA, so it is the high-contrast
roundoff floor, not truncation. The CPU service showed the same 1e-12 level
on the C fixture (9.9e-13 at contrast 13.3 and 2.5 GHz). The gate was again
set at the method's floor. What the audit uses, the production/refined
discrepancy, is ≤ 2.9e-12 against its 1e-7 tolerance.

## Profile evidence

[`diagnose.py resolution`](../CI-001-modal-review/diagnose.py) on the two
archived stage-start curves at K=192 is relative error against Kress 1024
at 2.1–2.5 GHz ([diagnostics_resolution.json](../CI-001-modal-review/diagnostics_resolution.json)):

| Curve | old production 96 | new production 128 | new refined 160 |
|---|---:|---:|---:|
| `shifted_star` M49 | ≤ 5.2e-8 | ≤ 9.7e-11 | ≤ 3.2e-13 |
| `new_asymmetric` M61 | ≤ 9.3e-8 | ≤ 3.8e-10 | ≤ 1.1e-12 |

CPU assembly at K=192 costs 0.23 s per frequency at 128, against 0.16 s
at 96.

## Predeclared test 2 and the rerun: the nine affected cases

[`CI-001-modal-r2`](../CI-001-modal-r2) ran 09:32–09:42 BST, with the same
settings as CI-001-modal (`device=auto`, four frequency threads, one
worker) and CI-001's sealed damped catalogs (same seal). The comparison
with nodal CI-001 is in [rerun_summary.json](rerun_summary.json).

| Case | Modal (before → now) | Nodal | Same decisions / units | RMS mm (modal / nodal) | Worst prod/ref gap (modal / nodal) | Wall s (modal / nodal) |
|---|---|---|---|---|---|---|
| `far__development_c` | REGRESSION → **PASS** | PASS | yes / yes | 9.757e-4 / 9.757e-4 | 3.1e-13 / 1.1e-14 | 28 / 77 |
| `far__opposite_c` | REGRESSION → **PASS** | PASS | yes / yes | 9.757e-4 / 9.757e-4 | 2.9e-13 / 1.1e-14 | 27 / 77 |
| `modal__c2__development_c` | REGRESSION → **PASS** | PASS | yes / yes | 6.854e-4 / 6.854e-4 | 3.8e-13 / 9.9e-14 | 35 / 99 |
| `modal__c4__development_c` | REGRESSION → **PASS** | PASS | yes / yes | 1.073e-3 / 1.073e-3 | 4.0e-13 / 2.7e-14 | 46 / 127 |
| `modal__c4__opposite_c` | REGRESSION → **PASS** | PASS | yes / yes | 1.073e-3 / 1.073e-3 | 3.5e-13 / 3.0e-14 | 46 / 125 |
| `modal__c13.3__shifted_star` | REGRESSION → **PASS** | PASS | yes / yes | 1.323e-3 / 1.323e-3 | 7.3e-9 / 4.7e-14 | 122 / 286 |
| `modal__c13.3__new_asymmetric` | REGRESSION → **PASS** | PASS | yes / yes | 1.965e-3 / 1.965e-3 | 3.9e-10 / 7.1e-14 | 83 / 213 |
| `modal__c13.3__development_c` | REGRESSION → REGRESSION | PASS* | no (stops `fixed_M31`) / 5462 vs 5996 | 6.63 / 6.40 | 1.0e-7 / 2.5e-6 | 88 / 312 |
| `modal__c13.3__opposite_c` | REGRESSION → REGRESSION | PASS* | no (stops `fixed_M31`) / 5462 vs 5996 | 6.63 / 6.40 | 1.0e-7 / 2.5e-6 | 88 / 313 |

\* Nodal is not recovered here either (RMS 6.4 mm). It stops with
`NUMERICAL_FAILURE` at `fixed_M43`, and its contract status is `PASS`
because its references fail the same way.

No physics fallbacks or failed evaluations occurred. The 9 cases summed
563 s against nodal's 1,628 s, a median per-case speed-up of 2.8×. These are
single unmatched runs. From about 09:39 to 09:43, a separate CUDA Kress
benchmark (`cuda-kress-matched-accuracy-20261001`, not part of this work) ran
on the same GPU. The last cases' wall times are therefore upper bounds.

**Predeclared test 2 passes for both cases it was declared on.**
`shifted_star` and `new_asymmetric` reproduce nodal's decisions, with worst
gaps of 7.3e-9 and 3.9e-10 against the 1e-7 tolerance.

### New finding: the contrast-13.3 C stop

[`candidate.py`](candidate.py) ([candidate.json](candidate.json)) replays
`fixed_M31` from its archived start, with the frozen policy operation. It
reproduces the archived stop bit for bit: the discrepancy is
1.0047953e-07 in both. It then resolves the rejected first trial. That
trial is a 0.46 mm LM step, with update modes up to 31, from a curve
already in the wrong basin (loss 0.33). Errors are against 2048-node Kress:

| GHz | Kress 512 | Modal 128 | 160 | 192 | 224 | 256 |
|---:|---:|---:|---:|---:|---:|---:|
| 2.125 | 1.6e-14 | 1.4e-8 | 3.8e-10 | 2.0e-11 | 4.9e-13 | 5.7e-13 |
| 2.25 | 1.7e-14 | 3.1e-8 | 6.9e-10 | 3.0e-11 | 7.7e-13 | 1.7e-12 |
| 2.375 | 2.7e-14 | 3.5e-8 | 5.1e-10 | 4.4e-11 | 5.4e-13 | 1.1e-12 |
| 2.5 | 4.0e-14 | 1.0e-7 | 2.3e-9 | 3.8e-11 | 7.6e-13 | 1.4e-12 |

At the stage's start curve, modal 128 is 3.5e-10 and 160 is 6e-13. The
trial's added detail is what costs about 2 digits. The trace cutoff a curve
needs therefore depends on the curve itself, not only on the storage band.

### Provenance note

`prepare` hashed `test_modal_muller.py`. The two new tests were added
28 s after `prepare` (09:32:50, while the run was in progress), so the
run's closing `verify` refused and `comparison.json` was not written. The
service sources the run imported (`modal_operator.py`, `modal_muller.py`)
are older than `prepare` and match the manifest. The run never imports the
test file.

`report` was produced by temporarily restoring the archived test file from
this campaign's `sources.tar.gz`, then re-applying the two tests. As a
result, `CI-001-modal-r2` does not re-verify against the current test file.

## Next (proposed, not run)

1. **Rerun all 36 in a fresh campaign** prepared from the committed fix. The
   profile change touches every K=192 stage, so the 27 previously identical
   cases need confirming, along with the runtime cost of 128/160.
2. **Curve-adaptive trace cutoff** for the two contrast-13.3 C stops.
   Recommended: add an a-posteriori check on the solved traces' tail, and
   raise K_trace in steps of 32 until the tail is below 1e-10 of the trace
   norm. The refined token keeps its +32 offset as the independent check.
   The simpler alternative is one more fixed step (160/192), at about 1.25×
   assembly cost per K=192 evaluation.

   Falsifiable test: the [`candidate.py`](candidate.py) replay accepts or
   rejects the first trial exactly as nodal does (nodal accepts 4 steps,
   then reaches the stage quota). Both C cases then stop no earlier than
   nodal's `fixed_M43`.

## Reproduce

```bash
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
D=results/validation/cleaned_interfaces/modal-muller-fixes-20261001
O=results/validation/cleaned_interfaces/CI-001-modal-r2
"$PY" -m pytest -q experiments/cleaned_interface/test_modal_muller.py
"$PY" $D/starts.py
"$PY" -m experiments.cleaned_interface.modal_muller prepare --output $O
"$PY" -m experiments.cleaned_interface.modal_muller augment --output $O \
    --reuse-from results/validation/cleaned_interfaces/CI-001 --allow-new-damped-data
"$PY" -m experiments.cleaned_interface.modal_muller run --output $O --solver modal_muller \
    --device auto --frequency-threads 4 --workers 1 --cases far__development_c far__opposite_c \
    modal__c2__development_c modal__c4__development_c modal__c13.3__development_c \
    modal__c4__opposite_c modal__c13.3__opposite_c modal__c13.3__shifted_star modal__c13.3__new_asymmetric
"$PY" -m experiments.cleaned_interface.modal_muller report --output $O
"$PY" results/validation/cleaned_interfaces/CI-001-modal-review/summarize.py $O $D/rerun_summary.json
"$PY" $D/candidate.py
```

`CI-001-modal-r2` was prepared from the uncommitted fix on top of `6e5c3e59`.
Its manifest records the changed files, and `sources.tar.gz` archives them.
