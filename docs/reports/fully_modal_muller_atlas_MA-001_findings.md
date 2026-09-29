# MA-001: short findings on the modal-atlas vision

2026-09-28. Claude (Opus 5.5). This is an exploratory note, not a qualified
result. It concerns the
[fully modal Müller atlas research vision](fully_modal_muller_atlas_research_vision.md).

The code, data and full write-up are **not** on this branch. They are on
`claude/magical-meitner-11naoj`:
[results](https://github.com/ShiyuanDeng/Neural-BEM/blob/claude/magical-meitner-11naoj/docs/iterations/modal_atlas/iteration_02/01_results.md),
[review of the vision](https://github.com/ShiyuanDeng/Neural-BEM/blob/claude/magical-meitner-11naoj/docs/iterations/modal_atlas/iteration_01/02_proposals/02_independent_review.md),
[evidence](https://github.com/ShiyuanDeng/Neural-BEM/blob/claude/magical-meitner-11naoj/results/validation/modal_atlas/MA-001/README.md),
and `experiments/modal_atlas/`. Nothing on this branch was changed apart from
these two report files.

## Scope and caveats

- **Code version.** The BIE part used this branch as of `d2cd5cf9`
  (27 September). It ran with CPU reference kernels. Later commits
  (SPD-011 to SPD-014, SC-049, the CUDA default and native geometry
  acceleration) were **not** in that checkout, and MA-001 has not been re-run
  on them.
- **Circle part.** This is an independent analytic (Mie) model. It does not
  depend on any of this branch's code.
- **Coverage.** One contrast (0.5), paired data, and eleven states (five
  truths and six trajectory endpoints). One of these, SC-038's sharp-tip
  `F_released_m/kite`, was not resolved at 512/1024 nodes and was excluded.
- **Analysis only.** First-order sensitivities. No controller, policy or
  default was tested or changed.

## Findings, with how much weight each can carry

1. **The §6 pair identity checks out numerically.**
   `J_p = Δ L Σ U_n V_{−p−n}` matched an exact circle calculation to the
   finite-difference floor. On the qualified BIE states it matched nodal
   quadrature to `≤ 3e-8`, and it matched `shape_jacobian` to `≤ 6e-16`.
   This looks robust. Re-running on the current solver code would confirm it
   still holds there.

2. **A possible explanation for iteration 04's ~2.5k frontier.** On the
   circle, the observable band follows the combined width of the forward and
   reciprocal field spectra. `frontier/kR` drifted from 2.5 toward 2.2
   between kR = 8 and 64, which fits the classical `2k` diffraction limit plus
   a slowly growing margin. On the BIE states, the two spectra's widths at 10%
   and 1% bracketed the frontier in 188 of 190 cases. If this holds more
   widely, it suggests the linear `2.53k` fit may have been partly a
   consequence of its `k ≤ 20` window. I have not compared this against
   iteration 04's own setup.

3. **A possible mechanism for the contrast-10 breakdown, probably not for the
   kite/C failures.** When `k_i > k_e`, trapped (whispering-gallery) modes
   appear. On the circle, near those poles, sensitivity rose sharply and the
   10% linearization radius followed the vision's single-pole formula closely
   (constant about 0.10–0.13). Averaged over frequency, the radius was about
   10× shorter at contrast 10 than at 0.33 or 0.5. The continuation benchmark
   uses contrast 0.5, where the circle has no such modes. So this mechanism
   seems unlikely to explain the kite/C finite-validity problems there. That
   is a circle-based argument and has not been tested on noncircular
   high-contrast shapes.

4. **Sensitivities appear to need less trace resolution than the traces
   themselves.** On the qualified BIE states, the projected band needed for
   column `p` at tolerance `τ` was close to `K_trace(√τ) + 0.6p`. This
   measures projection of exact traces only. A modal solve at reduced cutoff
   could behave differently, and that was not tested.

5. **Cancellation did not seem to explain dim atlas cells at contrast 0.5.**
   Cell brightness tracked the available field magnitude closely
   (correlation ≈ 0.99, median cancellation factor ≈ 2). This may not carry
   over to higher contrast.

## What may be useful independently of the newer changes

- The circle results (2 and 3) do not use this branch's code, so the newer
  solver changes should not affect them.
- The per-frequency field-spectrum width (item 2) might serve as a cheap,
  prospective band indicator. It is computed from traces the inverse already
  has. Whether it helps continuation is untested. SC-043 suggests any such
  signal should face a matched test against the fixed and stagnation controls.
- Items 1, 4 and 5 were measured on the older code. They would need a quick
  re-check before being relied on with the current backend.

## Amendment, 2026-09-29

The MA-001 code, docs and evidence were imported unchanged onto
`feature/shape-frequency-continuation` (`experiments/modal_atlas/`,
`docs/iterations/modal_atlas/`, `results/validation/modal_atlas/MA-001/`).
[MA-001R](../../results/validation/modal_atlas/MA-001R/README.md) re-ran Part B
on the current code (`032092cd`, CUDA default). Every integer quantity is
identical and continuous quantities agree to round-off, so findings 1, 4 and 5
no longer need the re-check this note asked for.
