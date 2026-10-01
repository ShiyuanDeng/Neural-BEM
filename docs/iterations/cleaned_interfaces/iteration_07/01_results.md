# Modal Müller fixes: scaled Graf and a finer profile

2026-10-01. Implementation owner: Claude.

## Approval

[Iteration 06](../iteration_06/01_results.md) proposed three steps:

1. a scaled Graf factorization;
2. a one-step-finer modal profile;
3. a rerun of the nine affected cases.

The user replied **"yes go fix them"**.

## Change

- **`modal_operator.py`.** The Graf step now runs in scaled form. The
  regular waves are divided by s_l = (kρ/2)^|l|/|l|!, and the
  forward-recurrence Hankels `scaled_hankel` are multiplied by s_l. The
  `graf_order` bound now has a proved recurrence tail and no 128-order cap.
- **`modal_muller.py`.** Production `K_trace = max(64, 32*(ceil(K/64)+1))`,
  which is 128/160 at K=192 instead of 96/128.
- **Tests.** Two tests were added. One checks `scaled_hankel` against mpmath
  to order 260. The other checks the `opposite_c` start against Kress 1024.
  The profile assertion was updated.

No policy, LM, nodal or CI-001-frozen source changed, and CI-001 `verify`
passes. Evidence:
[fix bundle](../../../../results/validation/cleaned_interfaces/modal-muller-fixes-20261001/README.md).

## Measurements

| Check | Outcome |
|---|---|
| Recurrence against mpmath | ≈ 3e-15 to order 120. SciPy `hankel1`, used by the old code, is off by 1e-5 at order 120 |
| Test 1: seven starts within 1e-12 of Kress 1024, all frequencies, K_trace 64/96, CPU+CUDA | **Missed narrowly** (worst 2.4e-12, contrast 13.3; ≤ 1.5e-13 at contrast ≤ 2). The excess is at the high-contrast roundoff floor; the audit gap is ≤ 2.9e-12 against its 1e-7 tolerance |
| Test 2: the two stopped stages reproduce nodal's decisions | **Pass** (worst gaps 7.3e-9 and 3.9e-10) |
| Nine-case rerun (`CI-001-modal-r2`) | **7/9 now pass and match nodal** in decisions and units, RMS within 2.7e-7 mm, 2.8× less wall time. The two contrast-13.3 C cases (unrecovered by nodal too) stop at `fixed_M31` instead of nodal's `fixed_M43` |

A replay of the C stop reproduces it bit for bit. The rejected trial needs
K_trace ≈ 192–224 to reach the accuracy Kress 512 has (1e-7 at 128, 2.3e-9 at
160, 3.8e-11 at 192). The trace cutoff a curve needs depends on the curve,
not only on the storage band.

`prepare` hashed the test file, and the two tests were added after it. The
report was therefore produced against the archived test file, as recorded in
the bundle.

## Interpretation

Both failure classes found in CI-001-modal are removed. If the other 27 cases
stay identical under the finer profile, which is unverified, modal would
pass 26/36 against nodal's 28/36. The difference would be the two cases that
no backend recovers. Modal still refuses earlier than nodal there.

## Next (proposed, not run)

1. A fresh all-36 modal campaign, prepared from the committed fix.
2. A curve-adaptive trace cutoff, driven by the solved-trace tail, or one
   more fixed profile step. Test: the C replay matches nodal's first-trial
   decision.
