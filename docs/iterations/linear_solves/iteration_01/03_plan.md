# IS-001: where solve time goes, and iterative solves against LU

## Questions

1. Where does one forward solve's time go now, on the production path at
   Ku 64 and Ku 128? Split assembly (CUDA), scipy LU (CPU), waves, trace
   solve, fields and Jacobian.
2. At those sizes, with every source and receiver right-hand side, can a
   block iterative solve beat LU at matched accuracy? Test it cold, and
   anchored on the previous accepted curve's LU.
3. If not, at what system size would it win, and after how many reuses of
   one anchor?

**Plan finalized 2026-10-26.** The user asked for 2–3 directions "to be
experimented overnight" and chose D04 among them. Execution starts when the
user launches this track's agent. Status: **COMPLETED**; see [results](01_results.md) and [execution notes](04_execution.md).

Shared rules and the morning report: [overnight README](../../overnight_2026-10-26/README.md).
Fill in Track C there. Direction: [D04](../../../directions.md#d04-solve-through-matrix-actions-and-reuse-previous-solves).

## Why this question

Historical AC-002 put LU at 5.6% of a new-curve solve and 25.1% of a reused
one, at K_trace 96 ([evidence](../../../evidence.md)). Current code still
factors on the CPU (`a4_fields.factorize`), even with CUDA assembly. Recent
fits spend most of their time at Ku 64 and Ku 128 ([PS-003](../../policy_speed/iteration_03/01_results.md)).

[Haibing's review](../../../../Haibing_directions.md) makes two claims:

- **Recommendation 4:** profile assembly against LU at the final size
  before investing in items 5–7. If LU is a small share, treat those items
  as checking tools, not speed-ups.
- **Item 5:** GMRES right-preconditioned by the old LU is standard. It needs
  a contraction below one, which an LM step at high frequency or contrast
  may break.

## Inputs

- hook c13.3, PS-003 H3: release_M11 accepted curve (Ku 64) and last
  fixed-stage accepted curve (Ku 128).
- Highest real frequency, 2.5 GHz, and its damped counterpart.
- Pairs of nearby curves for anchoring. Use consecutive accepted curves if
  the saved history holds them. Otherwise use stage entry/exit pairs and one
  recomputed accepted step; state which.

## Method

1. **Breakdown.** Time the current solve at both resolutions with the
   existing call boundaries. Report the median of repeats, and first use
   separately.
2. **Solvers.** Compare three ways of solving the assembled system:
   - dense LU (current);
   - GMRES, cold;
   - GMRES right-preconditioned by the nearby curve's LU (anchor).

   Use all right-hand sides the fit solves, both forward and reciprocal.
   Krylov recycling is optional.
3. **Contraction.** Estimate the anchored error contraction from the
   convergence rate. Do it for consecutive accepted curves and for one large
   step, such as a refused or halved trial.
4. **Crossover.** Raise Ku on the same curve, for example 64, 128, 256,
   512, while memory and time allow. Find where anchored GMRES beats LU, and
   how many reuses of one anchor are needed to repay its factorization.

The matrix is still assembled, so this tests the solve only, not avoided
assembly. Match accuracy: the iterative solve may change predicted
measurements by at most 1e-9 relative. That is 1% of the 1e-7 field
tolerance in `experiments/benchmark/audit.py`.

## Decision

If anchored GMRES is not faster than LU at Ku 64 and Ku 128, D04 closes for
the current workload. That includes the anchor's own cost spread over its
measured reuses. Report the crossover size and reuse count either way.

## Morning report

- A breakdown table at Ku 64 and Ku 128 with each part's share.
- A solver table: method, iterations, seconds, accuracy and contraction.
- A plot of time against system size showing the crossover.
- Track C's section of the overnight README, answering the three questions
  with numbers.

## Continuation, only if `AGENTS.md` then allows it

Only if anchored GMRES wins at Ku 128: measure it along a saved trajectory,
reusing one anchor until it stops paying. Otherwise stop; the breakdown is
the result. No inverse fits. Stop all computation by 07:00 on 2026-10-27.

## Saved work

Prototype under `experiments/linear_solves/`; results under
`results/validation/cleaned_interfaces/IS-001/`. Save settings, code
revision, timings, iteration counts, contraction estimates and machine
load. Commit and push after each completed step, then verify the push and
working-tree status.
