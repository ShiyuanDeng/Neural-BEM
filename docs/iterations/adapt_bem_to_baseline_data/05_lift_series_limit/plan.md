# Proposal — lift the A3 series limit; implementation waits for the user

18 November 2026, `bem-gpu`. **Written proposal only; no solver lock or solver
edit.** The coordinator authorized at most 15 minutes of small standalone
probes. No fit, new schedule, dataset tuning or implementation is authorized.

1. **Limit.** [A3 `regular_kernels`](../../../../solvers/bem_inverse/a3_waves.py)
   sums alternating powers of the centred curve. Large terms cancel to small
   regular waves; `EPS*I0(abs(k)*rho)` estimates round-off amplification.
   Raising `series_loss` accepts lost digits rather than fixing them. At
   k=15 the cavity has `k*rho=43.785`, versus the present cap near 24.7;
   star has 23.358. A3 also supplies reciprocal receiver waves used by B7.

2. **Recommendation.** Add an opt-in A3 fallback: evaluate integer Bessel J
   waves on an oversampled periodic Fourier curve, evaluate flux analytically
   from adjacent orders and the exact curve derivative, then FFT to the existing
   modal window and apply the existing order scaling. Use SciPy's stable
   [AMOS-backed J evaluator](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.jv.html)
   and the [Bessel derivative recurrence](https://dlmf.nist.gov/10.6.E1).
   For real positive frequencies, double the grid until retained values/flux agree and alias tails pass;
   refuse at the declared sample/memory cap. No finite-difference flux.
   **This introduces boundary sampling in A3**, while A2 modal assembly stays
   unchanged. It is a method choice requiring the user's go. One alternative:
   rebuild the complete coefficient power recurrence in adaptive arbitrary
   precision, including geometry products, then round once. This preserves
   the coefficient-only design but is likely much slower; higher-precision
   final summation alone cannot repair already-rounded wave arrays.

3. **Next limits.** `K_trace` controls traces, while the coefficient workspace
   must resolve geometry, waves and repeated products independently. The current
   storage-band rule and `K_trace+64` are not high-frequency accuracy guarantees;
   qualify both independently. The probe finds cavity incident modes 97–256
   carry 1.27e-3 relative norm at k=15; that is not a solved-trace error.
   A3 Graf still
   requires receivers outside the coefficient bounding circle; its convergence
   deteriorates near that circle. Graf and plane-wave orders have a 1024 search
   cap; the probe needs only plane/Graf orders 97/89 at argument 45.
   Interior arguments near 65 enter **A2**, not the
   exterior A3 waves: radial coefficients already use extended-precision Miller
   recurrence and analytic Bessel products. Their decay/tail checks, projected
   radial workspace, matrix conditioning and memory remain independent limits.
   The scalar radial probe passes at arguments 45/65 (degree 93, 240 terms);
   that does not check the assembled operator.
   Fixing A3 alone does not prove a k=15 fit will finish.

4. **Default.** Put a general, default-off fallback option at A3's existing
   refusal, before allocating power arrays. Only explicitly enabled calls whose
   current loss estimate exceeds `series_loss` take it. Keep the existing
   arithmetic and default receipts unchanged; ordinary defaults never reach
   the fallback because the option is off, even on a previously refused case.
   Unqualified complex frequencies retain their existing refusal. No dataset
   name, shape, radius or frequency constant enters solver code.

5. **Proofs after approval.** Check values/flux against analytic disks and
   independent high-precision samples through exterior arguments 45 and interior
   arguments 65. Check grid, modal-window and trace convergence separately;
   plane and point tables, masks, B7 complete-slider differences and material
   columns; CPU/GPU agreement below 1e-10. Require unchanged CPU default bytes
   and GPU results within newly measured pre-edit repeatability, plus the full
   suite. Finally qualify the retained cavity/star true-shape fields through
   k=15 against saved BRG data before requesting any inverse reruns.

6. **Estimate/risk.** Allow 6–10 focused work hours for implementation and
   proofs, possibly 1–2 days if trace/window convergence fails. Main risks are
   alias control, order scaling and increased high-frequency assembly cost.
   The 3 s [probe](results.md) finds grid/reconstruction errors below 4e-15,
   but cannot certify fitted geometries or the one-hour fit ceiling.

7. **Series setting.** With the qualified fallback enabled, restore BRG's
   `series_loss=1e-9`: it becomes the switch threshold for the legacy evaluator,
   not a relaxed accuracy target for the new one. Keep the current 1e-6 wrapper
   setting until approval and qualification; lowering it now would refuse
   more cases. The default setting remains 1e-9 throughout.

**Probe budget/command:** one CPU process, one BLAS thread, at most 900 s,
no full forward solve or inverse. Run
`PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
/home/drdeng/miniconda3/envs/EMNerf/bin/python
experiments/bem_on_baseline_data/series_limit_proposal/probe.py`.
Outputs: `results/bem/baseline_data/series_limit_proposal/2026-11-18/`;
actual probe evidence goes in `results.md`. Measure A3 grid agreement, existing
order choices and A2 scalar radial expansion at the requested range; success
means feasibility evidence only. **Implementation remains awaiting user go/no-go.**
