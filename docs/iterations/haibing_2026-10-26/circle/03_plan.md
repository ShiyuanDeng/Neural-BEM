# HB-004 circle formulas and response propagation

Can the proposed circle blocks reproduce the maintained Müller matrix and
paired fields? Does ItI propagation cross a circle DtN pole accurately, and
what changes for damped wavenumbers?

Use the TG-002 centred 65 mm start, actual acquisition, endpoint frequencies
0.25/2.5 GHz, contrasts 0.5/4/13.3 and real/damped copies: 12 forward calls.
At Ku64 compare all four blocks against independent Bessel formulas, and
paired predictions against the existing independent Mie implementation.
Measure analytic assembly and modal forward times separately; this is not
a whole-fit speed comparison. Check the radius derivative of V at the same
12 conditions with one centred difference pair of analytic evaluations.

For item 11 integrate the stated scalar ItI ODE for modes 0–16 across the
first J0 pole at the largest interior wavenumber, real and damped, with
two tolerances (four integrations). Compare with the direct Bessel ratio
that never forms DtN. Record pole behaviour and unitarity defects. This
tests the circular special case only; general-curve closure and coupling
to the exterior remain open. No inverse fit, no production change.

Stop after these fixed comparisons. Preserve failures and report them.
Use single-thread CPU BLAS and cores 12–15. Code and JSON provide the
necessary numerical checks; no unrelated test suite is needed.
