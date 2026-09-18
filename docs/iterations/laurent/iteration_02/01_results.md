# Iteration 02 — what LAU-001 settled, and the one thing it did not

> **2026-09-17 correction following independent review:** the “Settled” table
> below records the original interpretation, which overstates the completed
> checks. The campaign omitted independent physical derivative qualification,
> excluded objective accuracy from `passes_all`, used an unscaled residual,
> and omitted geometry-offset and new-illumination checks. Its refined 30%
> star mask also retains more entries than the entire smaller remainder.
> The user authorized repairs with “just keep fixin and testin”.
> [LAU-001-R1](03_plan.md) owns those repairs; corrected results open
> [iteration 03](../iteration_03/01_results.md). The prior bundle is preserved.

**Opened by the executed [LAU-001 plan](../iteration_01/03_plan.md), 2026-09-17.
Verdict `STRUCTURE_ONLY`. Stage: results recorded; no proposal yet.**

Measurements and their limitations live in the
[result bundle](../../../../results/validation/laurent/LAU-001-20260917-modal-derivative-compression/README.md).
This record holds the decisions and the next question; it does not duplicate the
tables.

## Settled

| Question | Answer |
|---|---|
| Is the verified singular split available natively? | **Yes.** `identity + log-symbol + smooth` reconstructs the assembled operator to `1e-16`. The brief's `SPLIT_UNAVAILABLE` contingency was never needed |
| Is the remainder's support analytically predictable? | **Yes, and it does not help.** The `(d, p*, log_order)` bound held with zero violations on every block of every case, but retains 1.000 on both noncircular fixtures. The structure is in the magnitudes, not the support |
| Does forward-only retention preserve geometry derivatives? | **No — decisively.** At full-level receiver accuracy (`1e-12`–`1e-14`) it gets `D_vY` 160%–760% wrong. The `R(η)=η·H` failure mode is physical, not hypothetical |
| Does derivative-aware selection help? | **Yes, by 5–13 orders of magnitude** in derivative error at matched retention and matched field accuracy, on both noncircular fixtures |
| Does retention survive refinement? | **Yes, it improves.** At doubled trace dimension both noncircular fixtures pass every gate at 0.300, including held-out directions. The retained fraction does not approach one |
| Does any of it save work? | **No.** Masks need all dense entries plus all training `D_vR`, and the solve stays dense. The only measured saving is `COEFFICIENT_WINDOW` (1.5–2.3× assembly), a different mechanism |

Two negatives worth preserving with their scope:

- **The circle fails at every retention.** Its remainder is nearly diagonal, so
  neither `R` nor four training derivatives carry signal at a held-out mode-5
  harmonic; at `ka5` derivative-aware is *worse* than forward-only. A mask
  trained on four directions is not validated for a fifth.
- **`k_out·a_ref = 10` (5.33 GHz) is `UNQUALIFIED`** on all three fixtures. The
  Bessel power series, not compression, is the limit — `0.92`–`1.9` relative
  error at 28 terms, still short of the control gate at 48. This bounds where
  any Laurent result on this path can currently be claimed.

## Not settled

1. **Whether retention converts into arithmetic.** No sparse assembly or solve
   exists, so 0.30 retention is an approximation-quality result only.
2. **The reciprocal/Hadamard derivative was never compressed.** The plan called
   for it as a separately labelled third arm; it was not run.
3. **The projected-Nyström control `A_M^proj` was verified but never swept**, so
   nothing here says whether these rules transfer to it.
4. **Self-review only.** No independent reviewer was assigned.

## Candidate next checks

Not approved; listed so a successor does not have to re-derive them.

- **The named diagnostic from the bundle:** does a structured sparse assembly and
  solve at 0.30 retention beat the current dense native assembly at matched field
  and derivative quality, on ellipse and star at `k_out·a_ref ∈ {2, 5}` and the
  refined trace dimension where both qualify? A negative closes coupling
  retention for this operator.
- **Qualify the `COEFFICIENT_WINDOW` axis properly.** It is the only Laurent
  assembly-cost lever with measured evidence. It needs the three-repeat
  alternating-order protocol, a frequency-resolved rule for `terms`, and a
  comparison against accuracy-matched nodal Kress before it means anything.
- **Close gaps 2 and 3** above, which are cheap and reuse this package unchanged.
- **Raise the frequency ceiling**, or state it as a hard scope boundary for the
  whole Laurent track. Every recorded Laurent inverse to date uses 0.5–2.5 GHz.

No successor experiment is proposed or approved. Per the workflow, a named ID
needs a proposal, a review and explicit user approval.
