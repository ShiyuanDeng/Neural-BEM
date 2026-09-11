# Review diagnostics: modal identifiability and the arc-length chart

Probes run on 2026-09-08 by Claude to support
[`03_claude_second_review.md`](../../../../../docs/iterations/implicit_mlp/iteration_03/02_proposals/03_claude_second_review.md),
the second review of the [direct Method-B Fourier proposal](../../../../../docs/iterations/implicit_mlp/iteration_03/02_proposals/01_chatgpt_guide.md).
They are separate from the [first review's chart probes](../review-diagnostics/README.md),
which were read-only over saved contours.

**These probes run Kress forward solves.** No inverse is run, no MLP is loaded,
no extraction, projection, Method-B fit, conversion audit or adjoint is
evaluated, and no saved artifact is modified. Every solve is on a frozen
analytic curve built by the production `radial_fourier_state_curve` retraction
at the long run's node count and bandwidth: 194 Kress nodes, bandwidth 96. The
probe declares `(0,0)-(1,1)` bounds where the run uses `(0.3,0.3)-(0.7,0.7)`; on
the curve-only path the bounds serve only as a containment check, which every
curve here passes with margin under either box, and the Kress solve depends on
the curve and the problem alone. Total cost is roughly 700 forward solves, about ten
minutes on one thread.

| File | Contents |
|---|---|
| `modal_identifiability.py` | Modal Jacobian, sensitivity and coherence probe |
| `modal_identifiability.txt` | Its full-precision output |
| `target_arclength_bandwidth.py` | Chart, bandwidth and frozen-tail-floor probe (analytic; no solves) |
| `target_arclength_bandwidth.txt` | Its full-precision output |

## What `modal_identifiability` measures

For a frozen curve it builds the central finite-difference Jacobian of the
measured data with respect to twelve shape directions — the two centre
translations and radial polar modes 0 and 2..10 — under seven acquisitions, and
reports:

* **per-mode sensitivity**, the norm of each Jacobian column;
* **coherence** `|<J_a, J_b>| / (||J_a|| ||J_b||)`, which is 1 when an
  acquisition cannot separate two boundary modes at first order;
* the **singular spectrum** of the twelve-column Jacobian.

Residual normalization matches the inverse's own objective: each frequency
column is divided by the fixed norm of the observed column at that frequency,
with unit frequency weights. Radial mode 1 is omitted because it is the
translation gauge, carried by the two centre columns; this mirrors the
production radial chart.

Two states are probed: the exact target star, and the shared initial neural
contour reduced to a radial fit through mode 10. Two finite-difference steps
are reported, the radial inverse's production `200 um` and `100 um`; every
coherence agrees to four decimals between them, so the conclusions do not
depend on the step.

## What `target_arclength_bandwidth` measures

Method B refits by arc length, so the chart a direct Cartesian control would
optimize is the Fourier expansion in the **arc-length** parameter. The star is
exactly bandwidth 6 in the **polar-angle** parameter, because
`(R + A cos 5t)(cos t, sin t)` expands to modes 1, 4 and 6 only. Arc length is a
nonlinear remap of that parameter — the star's polar-parameter speed ratio is
`2.151657` — so the same curve is not bandlimited in the chart actually used.
The probe prices that difference, then prices the error floor of the proposal's
frozen-tail design, whose achievable curves are

```text
free active modes 0..B_a  +  the initial curve's modes above B_a.
```

Because the frozen modes are L2-orthogonal to the active ones, the parameterwise
L2 displacement of the best achievable curve is exactly the L2 norm of the
frozen-tail difference, minimized over the parameter-origin gauge. That
minimization is done in coefficient space by Parseval over 2,048 gauge shifts;
the reported maximum is evaluated on a dense grid at the minimizing shift.

## Caveats that travel with the numbers

The modal probe is a **linearization at two states**, over **twelve low-order
directions**. A well-conditioned twelve-column Jacobian says the low-mode
inverse problem is locally well posed. It says nothing about the conditioning of
the full 386-coefficient Cartesian map or the 8,577-weight neural map, and it is
not a global statement about the objective landscape between those two states.

The initial state is a **radial fit through mode 10** of the shared initial
contour, not that contour itself; its mean radius `60.0024 mm` and mode-5
amplitude `7.1807 mm` reproduce the values `01_results.md` reports for the true
initial contour, but its higher modes are discarded by construction.

`polar` modes here are the same objects as the polar spectra of `01_results.md`,
and are **not** the Cartesian modes of the first review's chart probe: a polar
mode-5 star is Cartesian modes 4 and 6. The bandwidth probe reports Cartesian
modes and states its parameter explicitly in every table.

Coherence is a first-order, two-column quantity. A pair at `0.36` is coupled,
not degenerate; it means the two directions are partly confusable in the data,
not that the acquisition cannot see either. No causal claim about a trajectory
follows from a coherence value alone.

The frozen-tail floor is a **parameterwise displacement in the shared
arc-length parameter**, not a symmetric point-to-curve distance, and so is not
directly comparable with the `raw symmetric RMS` metrics of `01_results.md`.
Parameterwise displacement upper-bounds pointwise curve distance.

Timings quoted in the review — `0.185 s` for one multistatic-8 two-frequency
Kress solve and `0.127 s` for one 194-node curve build — are single-thread
engineering measurements from this machine, not controlled benchmarks.
