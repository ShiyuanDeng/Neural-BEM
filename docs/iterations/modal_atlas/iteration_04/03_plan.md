# MA-004 plan: damped (complex-frequency) start for denser-than-host targets

2026-09-29. Owner: Claude (Opus 5.5). Independent reviewer: unassigned.
Authority: the user's 2026-09-29 instruction ("go next steps as you see fit,
you have my approval to stop only until genuine good news or hit every
wall"). Frozen before any MA-004 attempt ran. The only inverse evidence seen
so far is MA-002's and MA-003's. The plumbing smoke test ran two LM
iterations per damped stage and looked at no geometry error. No production
default, branch or worktree changes.

## Question

[MA-003](01_results.md) left one mechanism: resonance, which shortens the
linearization horizons and turns the first shape stages into wrong basins.
Evaluation-only probes showed that moving every wavenumber to `k(1 + iγ)`
restores the horizons, as the single-pole law predicts. At contrast 13.3 it
also puts the circle-localization optimum on the right object.

> **Does a damped start (localization and prefix at `k(1 + iγ)`), followed
> by an undamped pass and the unchanged releases, recover the denser-than-host
> failures without harming what works? Does it transfer to untouched scenes?**

`k(1 + iγ)` is the Fourier transform at ω of each time-domain trace damped by
`exp(−γωt)`. This is the Laplace–Fourier idea of Shin & Cha (GJI 2008, 2009),
applied here to penetrable boundary continuation. The pole law sizes it:
`|k(1 + iγ) − k*| ≥ γ Re k + |Im k*|`. Both wavenumbers scale by the same
complex factor, so the known contrast is unchanged. γ = 0.25 is fixed now. Both
0.25 and 0.5 restored the probes, and the smaller keeps more information. It is
not tuned on inverse outcomes.

## Arms

All arms except `frozen` use MA-003's exterior band.

| Arm | Localization | Prefix (warm-up, stages 1–4) | Then |
|---|---|---|---|
| frozen | SC-050 BIE search | real, borges band | releases (MA-002) |
| LB | dense Mie, real data | real | releases (MA-003 `both`) |
| R | dense Mie, real data | real | undamped stage-4 pass, releases |
| DP | dense Mie, real data | **damped** | undamped stage-4 pass, releases |
| D | dense Mie, **damped data** | **damped** | undamped stage-4 pass, releases |

The undamped stage-4 pass repeats stage 4 (the same four frequencies, M = 9,
K = 20, quota) at real frequencies, so no curve is truncated. R is its
extra-work control. Releases and fixed stages are exactly SC-050's. Damped
localization is MA-003's dense Mie search on damped data at the three lowest
frequencies. Its BIE 512/1024 qualification (≤ 1e-7) runs at the damped
frequencies. Damped forward solves run on the CPU reference path (the CUDA
backend covers real wavenumbers only) and keep the geometry validation of
`forward.solve`. The initial and final audits, endpoint residuals and
recovery definition are MA-003's and use the real catalog.

## Qualification before any attempt counts

- Damped Kress solve against exact Mie series on the disk at every contrast
  and catalog frequency at γ = 0.25: done, worst 7.7e-15
  ([`damped_mie_check.json`](../../../../results/validation/modal_atlas/MA-004/damped_mie_check.json)).
- Damped observations: 1,024/2,048 agreement ≤ 1e-8 per frequency, otherwise
  withheld.
- Replay: `frozen` must reproduce MA-002's contrast-4 C, and `LB` MA-003's
  `both` contrast-4 C, state for state.

## Stage 1: development (MA-002 scenes)

D at contrasts 0.5, 2, 4, 13.3 (12 attempts); DP and R at 4 and 13.3
(6 each). Predictions, written before running:

- D recovers the contrast-4 C, the 13.3 star and the 13.3 asymmetric; the
  13.3 C is uncertain.
- DP recovers the same three but not the 13.3 C, whose real-data circle
  localization is wrong.
- R recovers none.
- D loses no recovery at contrast 0.5 or 2.

**Gate G1 (releases stage 2):** D recovers at least 3 of the 4 MA-002
failures, and all 8 earlier recoveries.

## Stage 2: transfer (untouched scenes)

`opposite_c`, `shifted_rotated_c`, `new_thin_c` and `noisy_asymmetric`
(SC-050's fixtures) at contrasts 4 and 13.3, with frozen and D: 16 attempts,
one each. The noisy scene's real data use SC-050's noise model and seed. Its
damped data get an independent 1% draw (seed + 1). Real damped transforms of
noisy traces would have correlated noise; this is a simplification to disclose.

**Gate G2 (the claim):** D recovers at least 4 of the 8 transfer attempts and
at least 2 more than frozen, with every recovered endpoint passing its final
audit.

## Not claimed in advance

A pass would support a damped start for this acquisition and these
permittivities. It would not show:

- robustness to unknown permittivity, or to trace truncation and noise in
  real time-domain data;
- that γ = 0.25 is optimal;
- that the method is new in general. Laplace–Fourier continuation is
  established in seismic FWI; the connection claimed is the pole law's
  explanation and sizing in penetrable shape continuation.
