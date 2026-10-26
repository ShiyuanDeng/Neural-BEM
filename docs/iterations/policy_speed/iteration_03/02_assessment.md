# PS-003: assessment from saved evidence

## Research questions and answers

1. **Why does hook need many iterations? Partly answered.** M11/M15 make
   small raw proposals near the existing step threshold. Bounds and rejected
   trial curves do not explain those accepted steps; damping is not isolated.
2. **Which existing policy saves time while recovering hook? Answered for
   these measurements.** H3 `compact_release` is fastest at 16.256 s, against
   saved GU-002's 30.294 s. This is a 46.3% observed fit-time reduction.
3. **Does slider transfer to the four other cases? Answered for the selected
   cases.** Baseline recovers three; H3 recovers two. H3 retains kite and
   c-shape, loses circle's numerical qualification, and does not recover aphex.

The 13 saved runs match the [approved plan](../iteration_02/03_plan.md).
This assessment reads their records; it adds no fits or reference reruns.

## What the evidence establishes

[GU-002](../../../../results/validation/cleaned_interfaces/GU-002/slider/runs/hook__c13.3/result.json)
used 40 accepted M11/M15 iterations and 15.93 s, without rejected trials.

[PS-002](../../../../results/validation/cleaned_interfaces/PS-002/runs/hook__c13.3/result.json) exited earlier at higher losses; M43/M49 then cost
9.703 s, including eight rejected trials.

In H1/H3, every accepted M11/M15 C9 proposal equals its bounded and used
step. The last coordinate norms are 0.108–0.173 micrometres. Each stage ends
with four damping retries and 40 skipped proposals below the step threshold.

The local stall involves small C9 proposals, rather than bounds or C11
rejections. Their cause remains unresolved; GU-002 lacks these diagnostics.

[D1](../../../../results/validation/cleaned_interfaces/PS-003/D1/runs/hook__c13.3/result.json)
preserves GU-002's earlier-stage losses exactly, then omits M11/M15. It takes
43.477 s and fails physics in M55. Earlier release is not a successful shortcut here.

H3 uses 122 accepted iterations, versus GU-002's 125: work becomes cheaper.
H1 also recovers (25.455 s); H2 fails numerical checks and the residual
limit (0.005236 > 0.003).

[D2](../../../../results/validation/cleaned_interfaces/PS-003/D2/manifest.json)
changes H3's full-catalog `K_trace` (recorded as Ku) to 128, including its
required coefficient workspace. Both recover with 122 accepted iterations.

Both dispatch 1,348 forward and 1,305 reciprocal calls and charge 2,653 units.
D2 took 3.441 s longer. This supports a physics-resolution cost saving; compact
storage and other bundled effects remain incompletely separated.

No H1/H3 hook stage uses entry reuse or the shortened-progress exit, so neither
explains this saving. These optional policies leave the spectral default unchanged.

## Transfer and numerical validity

| Case | Baseline fit s / recovery | H3 fit s / recovery | Finding |
|---|---:|---:|---|
| circle c4 | 2.213 / yes | 1.495 / no | Numerical qualification regression |
| kite c0.5 | 41.826 / yes | 15.664 / yes | Recovery retained |
| c-shape c13.3 | 12.261 / yes | 8.924 / yes | Recovery retained |
| aphex c13.3 | 80.703 / no | 58.573 / no | No new recovery |

Circle's H3 shape and residual errors are almost identical to baseline. Its
[largest relative Jacobian discrepancy](../../../../results/validation/cleaned_interfaces/PS-003/O1S/runs/circle__c4/final_audit.json)
is 0.003476 in the cosine-36 column, whose refined norm is only 4.72e-10.

The absolute normalized difference is 1.64e-12. The
[check](../../../../experiments/benchmark/audit.py) divides by column norm with
a 1e-30 floor: weak-column sensitivity, not demonstrated shape failure.

Five circle columns still fail. Aphex's largest Jacobian discrepancy is
0.003248 in a column of norm 7.57; its field check also fails.
Small shape error cannot establish recovery.

## Timing, limitations and research decision

Fit times exclude final numerical checks; H3 adds 1.701 s and D2 1.641 s.
Batch wall timers are usable; overlapping frequency-thread durations are not
summed. Actual dispatched calls and charged work remain distinct on failures.

Saved histories omit one terminal accepted row in 17 quota-ending stages
across D1, O2B, O2S, O4B and O4S. Stage results preserve counts and final losses;
the missing accepted timestamps and gradients cannot be reconstructed exactly.

H1/H3 M11/M15 and H3/D2 counts are unaffected. Plots must identify gaps;
stage endpoint times are not accepted-state times. See C12 in
[fit_stage](../../../../solvers/bem_inverse/fit_stage.py).

**The bounded study provides credible progress:** a recovered hook improvement,
a useful controlled resolution comparison, and an honest transfer result.
It does not establish a generally faster replacement, repeatability, or 30-case success.

Keep defaults. Separately approved work could investigate circle's weak-column
qualification and aphex's field agreement. Q1 remains partial; no further
fits are authorized by this exhausted allowance.
