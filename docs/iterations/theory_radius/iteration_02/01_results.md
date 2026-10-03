# TR-001–003 diagnostic results

## TR-001: radius atlas complete

All 40 case/catalog/band rows passed the declared numerical qualification.
Execution used 9,448 forward frequency solves and 6,392 derivative batches in
585.92 s, overlapping FM-003. This is diagnostic cost, not a matched benchmark.
All 23 preflight/package tests passed. No forward solve or geometry probe failed.

At M5 with 0.5/0.75 GHz paired data, the contrast-4 and contrast-13.3 C have
almost identical real-frequency weakest sensitivities (0.04986 and 0.04941 per
mm in the normalized objective). Sampled Jacobian variation rises from
0.05097 to 1.3992 per mm², about 27.5x. The high-contrast C's empirical radius
is 0.00883 mm on real data and 0.36049 mm on damped data, about 40.8x larger.

Full data do not substantially enlarge this particular truth-local radius:
0.00939 mm real and 0.35132 mm damped. Consequently this local statistic alone
does not explain the global paired/full recovery difference. It supports a
nonlinearity explanation for the damping benefit near truth, not a new
identifiability or global convergence claim.

Of 936 additional radius probes, 911 exceed the declared origin-refinement
floor diagnostic; none has measured TCC ratio above 1/2 (maximum 0.32252).
Twenty-two of the 25 unresolved probes do exceed 1/2; these are numerical-floor
effects, not resolved theorem violations. Eight weakest singular values are
also unresolved against their Jacobian refinement errors. The raw tables and
plot retain those numbers; their qualification flags govern interpretation.

The Lipschitz constant is sampled, not bounded. No convergence certificate is
claimed. N512/1024 and FD gates qualify the four early probe frequencies;
the additional 19-frequency baseline spectra are descriptive diagnostics.

Evidence: [TR-001 report](../../../../results/validation/theory_radius/TR-001/README.md),
[numerical interpretation](../../../../results/validation/theory_radius/TR-001/ASSESSMENT.md),
[validation receipt](../../../../results/validation/theory_radius/TR-001/validation.json),
[preflight tests](../../../../results/validation/theory_radius/validation/preflight.log).

## Remaining approved diagnostics

TR-002 will test applicability at archived endpoints. TR-003 will distinguish
stationarity, resolved curvature, acceptance-margin stops and bounded branch
turning. No adaptive production policy or complex-geometry experiment has run.
