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

## TR-002: archived handoffs complete

All 24 declared handoffs were examined in 4.73 s using the TR-001 measurements
and 69 additional forward frequency solves. Eight endpoints fail the sampled
single-normal-graph test; nine more lie outside the current empirical radius
or sampled neighborhood. Seven indicators can be evaluated, and **none passes**
the sufficient next-stage inequality. The seven include transitions on successful
full-data trajectories, so this cannot be promoted to a useful rejection rule.

The normal-band remainder matters. For example, the contrast-4 full-data stage-4
endpoint has a 0.0405 mm retained-coordinate norm but a 0.1335 mm normal-band
tail. Its combined residual/model-error indicator is 0.3352 mm against the next
real-stage radius of 0.1755 mm. Excluding this tail would overstate applicability.
For the paired high-contrast C, all four checked early endpoints lack a qualified
single normal graph over truth. A truth-local theorem cannot justify those steps.

The result is **no practical handoff gate established**, not failed convergence
or a demonstrated fold. The current scalar sufficient estimate is too restrictive
on this sample. FM-003 census summaries were still pending when this experiment
captured its context; no partial census was truth-scored or duplicated.

The source refinement before TR-002 skips forward evaluation of already-inapplicable
remote projections, preserving their geometry and radius diagnostics. The full
curvature implementation also checks the archived objective value and counts
accepted continuation steps rather than correction attempts. All 23 preflight
tests passed again; TR-001's sealed source archive remains unchanged.

Evidence: [TR-002 report](../../../../results/validation/theory_radius/TR-002/README.md),
[summary](../../../../results/validation/theory_radius/TR-002/summary.json),
[validation](../../../../results/validation/theory_radius/TR-002/validation.json).

## Remaining approved diagnostic

TR-003 will distinguish
stationarity, resolved curvature, acceptance-margin stops and bounded branch
turning. No adaptive production policy or complex-geometry experiment has run.
