# Progress on Haibing's proposed solver improvements

Which proposals work on our physical matrices and saved reconstruction
steps? Which reduce cost, and which only improve accuracy or error control?

We tested the proposals directly in four parallel component studies.
The strongest positive results are useful geometry bounds, accurate local
reduced models, and improved precision for tiny matrix-primitive changes.
None establishes faster full reconstruction. Several proposed accelerations
cost more than the current implementation at the tested sizes.

## A short meeting update

“I have now tested the main suggestions against our actual scattering
matrices and saved reconstruction trajectories. The geometry bound is
substantially more useful than the overnight refusal-only tests suggested.
The local reduced model shows the predicted second- and fourth-order error
decay, and incremental updates preserve tiny differences more accurately.

“The main limitation is cost. Incremental Chebyshev evaluation takes about
twice as long; enriched projection costs erase the smaller solve's saving.
Singular extraction helps compress the low-frequency single-layer block,
but at high frequency the tested remainder remains full rank and introduces
large cancellation. I would keep these as targeted tools rather than enable
them throughout the inverse solver.”

## Direct answers by proposal

Items refer to [Haibing's review](../../../Haibing_directions.md).
Section numbers refer to the [original Word proposal](<../../../Neural-BEM_原文及改进方案_合作者实现版 (1).docx>).
“Open” means the present evidence does not answer the broader claim.

| Item and original sections | Direct evidence | What can be concluded |
|---|---|---|
| 1 Maue and reversed transpose, §7 | Twelve circle matrix comparisons; worst block error 4.083e-9. | Already implemented; circle signs and normalization agree. General noncircle extended-band verification was not repeated. |
| 2 Singular weights and bands, §§8–9 | Psi1/Psi2 matrix agreement within 1.35e-15. At K24/N64, bands occupy 61.1%/93.7% of the matrix. | Exact band identity works. Tested low-frequency remainders compress; high-frequency ones remain full rank. No complete band-plus-low-rank solver demonstrated. |
| 3 Coefficient step region, §5 | Simple bound covers 69/146 accepted steps. Sharper A1 covers 22/24 selected steps versus 17/24 simple on that same sample. | Useful beyond near-circles, but some valid accepted steps remain outside the sufficient region. Reusing A1 is more promising than recomputing it just for validity. |
| 4 Incremental Chebyshev, §§10–11 | Roughly 2x direct cost; tiny-difference accuracy improves roughly 1700x against extended precision. | Precision benefit demonstrated for radial primitives; speed benefit rejected for this implementation. Complete incremental A/b/L remains open. |
| 5 Anchored solve and correction, §12 | Reuse IS-001: anchored methods lose through Ku256; one accepted step has stationary spectral radius 1.203. | No current-size solve acceleration established. Contraction must be checked, not assumed. |
| 6 Schur feedback, §13 | Exact elimination agrees within 2.8e-14. One diagonal high-block correction has spectral radius 1.096. | Feedback bookkeeping works; cheap high-mode inversion is not universally convergent. Exact elimination costs 0.957–1.064x LU here; no substantial saving. |
| 7 Forward–adjoint model, §§14–16 | Physical shape-path errors approach order 2 without and order 4 with directional enrichment. | The local approximation claim works. Enriched projection plus solve costs more than LU here. The cheaper base model has larger errors. |
| 8 Output and LM error bounds, §§17–18 | Physical DWR and fixed-system LM checks; norm bounds can greatly exceed actual errors. | Algebra is useful, but these bounds do not yet provide cheap practical acceptance control. Floating-point floors require explicit treatment. |
| 9 Separate bands and frequencies, §19 | Hook M67 has 33/135 strong directions with low frequencies, 106/135 with all 19, under the stated relative threshold. | Direct support for managing information separately from parameter count. No new adaptive schedule or recovery benefit demonstrated. |
| 10 Circle formulas, §20 | Paired fields agree with Mie within 2.896e-10; radial V derivative within 3.365e-9. | Disk special case works and is already available. Nonuniform near-circle approximation remains open. |
| 11 Riccati/ItI, §§21–22 | Circular pole crossing error 2.675e-10 real, 1.197e-9 damped at tight ODE tolerance. | Circle propagation works; damped unitarity is false. General-curve closure, transport and exterior coupling remain open. |

## Decisions supported by these results

- Keep exact assembly and LU as the working default.
- Treat sharper coefficient bounds as a reusable result of A1 preparation.
  Do not reject a curve merely because a sufficient bound is inconclusive.
- Use incremental primitives when the difference itself matters; the measured
  precision gain does not justify replacing direct assembly everywhere.
- Keep local ROM as a verified approximation option for further targeted
  work; dense projection and setup must be included in any speed claim.
- One Schur shortcut is promising: the final damped case gives 4.18e-10
  relative field error in 6.48 ms versus 12.15 ms for LU. The corresponding
  real case does not match that combination of accuracy and cost.
- Keep singular extraction restricted to its measured low-frequency promise.
  Do not infer that the full Müller matrix is banded.
- Keep general ItI propagation as research. The original document itself
  places it outside the first required implementation.

## Evidence and limits

| Study | Questions and detailed results |
|---|---|
| HB-001 | [Singular weights and incremental primitives](kernels/01_results.md) |
| HB-002 | [Safe steps and physical information spectra](geometry/01_results.md) |
| HB-003 | [Schur, reduced models and error bounds](response/01_results.md) |
| HB-004 | [Circle identities and circular ItI propagation](circle/01_results.md) |
| IS-001, reused | [Anchored solve comparison](../linear_solves/iteration_01/01_results.md) |

Each new study has a question-led plan, executable driver and saved numerical
receipts. No new inverse fits were needed. Saved TG-002 states and physical
Jacobians supply the comparisons; the circle flow is an analytic component
test. No maintained solver code or defaults were changed.

The studies used different saved shapes and settings, including optional H3
slider trajectories. Results establish the stated local behaviour, not an
all-30-case claim. Timings are CPU component measurements under parallel
load; they must not be added together into an end-to-end speed estimate.

This report adds numerical evidence. It neither verifies the review's
literature search nor establishes novelty or general mathematical guarantees.
