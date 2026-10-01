# CI-001-modal: all 36 configurations with modal Müller

2026-10-01. The user ran the campaign. Claude reviewed it.

## Request

After commit `4f8ab6bf`, the user asked for "the command to run all 36 of
them". They ran the frozen CI-001 policy with `solver=modal_muller`,
`device=auto`, four frequency threads and one worker, into
`results/validation/cleaned_interfaces/CI-001-modal`. They then asked:
"alr you come back in <your estimated finish time> then do a short analyse
and identify problems. document and cp your findings first."

No source file was changed in this cycle. Evidence:
[CI-001-modal review](../../../../results/validation/cleaned_interfaces/CI-001-modal-review/README.md).

## Result

| | Modal | Nodal CI-001 |
|---|---:|---:|
| Pass | **19/36** | 28/36 |
| Recovered | 28/36 | 34/36 |
| Identical status, stage decisions and units | 27/36 | – |

**The 27 identical cases** comprise 19 passes and 8 shared regressions
(`circle_to_star` and seven noisy discrepancy stops). Endpoints agree within
2.3e-7 mm. On the same host they took about 3× less wall time: 923 s against
2,754 s summed, with per-case speed-ups of 2.4–4.1×. These are single
unmatched runs, not the runtime gate.

**The 9 status changes have two modal-only causes:**

1. **Graf refusal at offset starts (7 cases: every `development_c` and
   `opposite_c`).** The start circle sits 0.19–0.37 units from the nearest
   source or receiver. Measured from the curve centre, ρ/d is 0.78–0.87.
   The bound needs 131–248 Graf orders, and the cap is 128. Beyond the
   cap, the unscaled H_l(kd) overflows near order 150 at 0.25 GHz. The
   initial audit is therefore refused.
2. **Production resolution too coarse (2 contrast-13.3 cases at M49/M61).**
   K_trace 96 gives errors of 1.3–9.3e-8 against Kress 1024 at 2.1–2.5 GHz,
   within 2× of the 1e-7 acceptance tolerance. LM's
   production/refined check fails. K_trace 128 gives ≤ 3.8e-10 and 160 gives
   ≤ 1.1e-12. Nodal 512 gives ≤ 2.1e-14.

All 38,395 modal evaluations ran on CUDA, with no fallback and no failed
derivative. The CPU Graf step is now the largest physics stage (47%),
ahead of the CUDA assembly (25%).

## Interpretation

The policy and LM were unchanged. Where the service evaluates, the modal
backend drives them to the same decisions as nodal Kress. Both failure
classes are service limits that the earlier fixtures and replays never
reached:

- the replays started near the acquisition centre;
- the replays stopped at M43.

The campaign therefore does not establish modal retention (19/36), but it
locates exactly what blocks it.

## Next (proposed, not run)

1. **Scaled Graf factorization.** Use Ĥ_l = H_l(kd)(kρ/2)^l/l! with unit
   regular waves, and a log-space order bound with no fixed cap. Test: the
   seven starts agree with Kress 1024 to 1e-12 at all 19 frequencies.
2. **One-step-finer modal profile.** Production 128 and refined 160 at
   K=192. Test: replaying the two failing stages gives discrepancies ≤ 1e-9
   and nodal's decisions.
3. **Rerun the nine affected cases** as a new modal campaign. Both fixes
   change hashed `modal_*.py` files.
