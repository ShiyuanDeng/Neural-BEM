# GC-001 continuation: discriminate output-grid aliasing

2026-10-05. Before this continuation's dispatch. Same approved GC-001 scope:
locate the geometric precision differences. No production changes, extra inverse
experiment, new scene/state selection or timing rerun.

The registered main replay completed its six phases. It preserved 31 states and
279 common moves, with 277 acceptances and two identical self-intersection
refusals in every arm. Refined references qualify on 278/279 moves.

The registered six largest-disagreement factorial probes did **not** support
the initial hypothesis that cubic interpolation is the dominant error. In the
largest aphex trial, replacing inverse and position interpolation changes the
approximately 400.8 nm error by less than 0.1 nm. Similar persistence occurs
on the other five probes. This motivates checking the final sampled
uniform-arclength curve's FFT aliasing; the registered panel held that grid fixed.

Freeze the same six selection receipts. For each hold its original moved Fourier
curve and native integration grid fixed, vary **only** the target arclength
sampling grid N/2N/4N/8N before FFT cropping, using the same native inverse and
native position spline. Repeat with direct Fourier position evaluation and a
recorded coefficient-l1 omission bound. Then hold output at 8N and vary the
speed/arclength integration grid N/2N/4N/8N, with the original moved Fourier
curve still fixed. Record convergence and reference qualification. Do not use
the unresolved kite reference as an accuracy ranking.

The unchanged N/N cubic path must reproduce the maintained projection. Bounded
tests verify that and an analytic circle. Incremental six-case results go into
`GC-001/aliasing/`, with their own source commit/hash, selected-receipt hashes,
zero physics calls, completion/failure receipt and runtime. Main measurements
and source provenance remain intact. This is an adaptive attribution diagnostic,
not a new headline timing panel or independent confirmation sample.
