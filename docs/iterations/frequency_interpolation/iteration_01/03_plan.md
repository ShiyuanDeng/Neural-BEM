# FI-001: predict held-out frequencies at a fixed curve

## Questions

1. At one fixed accepted curve, how many exact frequencies are needed to
   predict the other real-catalog frequencies? Predictions must meet the
   endpoint-check tolerances for measurements and Jacobian columns.
2. Counting all setup, how much per-curve physics time does that save?
   Answer separately for interpolating the matrix and interpolating the
   solved results.
3. Does contrast 13.3 break it, for example through sharp responses in
   frequency?

**Plan finalized 2026-10-26.** The user asked for 2–3 directions "to be
experimented overnight" and chose D02 among them. Execution starts when the
user launches this track's agent. Status: **NOT STARTED**.

Shared rules and the morning report: [overnight README](../../overnight_2026-10-26/README.md).
Fill in Track A there. Direction: [D02](../../../directions.md#d02-reuse-a-library-of-physical-responses).

## Why this question

Physics is most of the fit. In [PS-003](../../policy_speed/iteration_03/01_results.md)
H3's forward batches took 13.3 s of its 16.3 s hook fit. ON-001 totals put
most physics work in parts repeated per frequency: assembly, waves, LU and
fields ([evidence](../../../evidence.md)).

Earlier D02 work failed to transfer across **shapes** (LAU-003/004).
Interpolation across **frequency** at one curve has not been tested. The
curve changes each accepted iteration, so all setup is charged per curve.

[Haibing's review](../../../../Haibing_directions.md) bears on this:

- **Item 2:** frequency enters the Müller matrix through scalar radial
  coefficients, contracted with geometry shared by all frequencies. Matrix
  interpolation can therefore save only the per-frequency contraction.
- **Item 7:** a projected reduced model still needs the full matrix, so it
  saves solves, not assembly. It must also cover all source and receiver
  solutions.
- **Item 9:** frequency continuation is recursive linearization. The fit
  uses all 19 real frequencies from M11 onward.

## Inputs

Use saved accepted curves at their saved stage settings (K, Ku, frequencies):

| Curve | Source | Why |
|---|---|---|
| hook c13.3, release_M11 accepted | PS-003 H3 | Ku 64, high contrast, the fastest recovering run |
| hook c13.3, last fixed-stage accepted | PS-003 H3 | K192, Ku 128 |
| peanut c4, final accepted | NR-001 M1 | Smooth shape, middle contrast |

Use the 19-frequency real catalog from the sealed TG-002 inputs. The damped
catalog is optional and secondary.

## Method

The exact reference is the production modal Müller solve at the same curve
and resolution. Check accuracy on the CPU path (`SC_FORWARD_BACKEND=cpu`).
Time on the production path (CUDA assembly, CPU LU) when the GPU is idle.
If it is not idle, time on CPU and say so.

- **Arm A, matrix:** compute exact matrices at node frequencies, interpolate
  to held-out frequencies, then solve exactly. Interpolating the
  frequency-dependent coefficient arrays instead of matrix entries counts
  as Arm A.
- **Arm B, results:** interpolate predicted measurements and reciprocal
  Jacobian columns directly. This also skips waves, LU and solves at
  held-out frequencies.

Choose the interpolation family before measuring, for example polynomial
or rational in wavenumber. Use nested node sets including both catalog
ends, such as 4, 6, 8, 10, 12 and 14 of 19. Held-out frequencies must never
influence the choice of family or nodes.

Tolerances come from `experiments/benchmark/audit.py`:

- relative field error at most 1e-7 above 0.5 GHz, and 1e-5 at or below;
- relative Jacobian-column error at most 1e-3.

## Decision

An arm is **useful** if, on all three curves, the smallest passing node set
saves at least 25% of exact per-curve physics time, including node solves
and interpolant construction. Report a passing arm with a smaller saving as
"accurate but not worth it". If no node set passes, record "not accurate".

## Morning report

- A table with one row per curve, arm and node count. Columns: worst
  held-out field error, worst Jacobian error, exact s, interpolated s,
  saving.
- A plot of error against frequency for hook c13.3 at both resolutions.
- Track A's section of the overnight README, answering the three questions
  with numbers.

## Continuation, only if `AGENTS.md` then allows it

- **Useful:** repeat on two more saved curves, `kite__c0.5` and
  `c_shape__c13.3` from PS-003. Estimate the whole-fit saving from H3's
  recorded per-stage call counts, without fitting.
- **Not useful:** find where it breaks: which frequencies, which contrast,
  and whether sharp responses explain it.

No inverse fits. Stop all computation by 07:00 on 2026-10-27.

## Saved work

Prototype under `experiments/frequency_interpolation/`; results under
`results/validation/cleaned_interfaces/FI-001/`. Save settings, code
revision, node sets, errors, timings and machine load. Commit and push
after each completed step, then verify the push and working-tree status.
