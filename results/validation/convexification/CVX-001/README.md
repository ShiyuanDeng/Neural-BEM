# CVX-001 analytic component evidence

Single registered run, 2026-10-11. All five gates passed. No inverse solve,
truth geometry, optimization, or new benchmark data was used.

See the [report](../../../../docs/iterations/convexification/CVX-001_results.md)
for the derivations, literature assumptions, exact command and interpretation,
and the [plan](../../../../docs/iterations/convexification/CVX-001_plan.md)
for the preregistered controls.

- `summary.json`: all nine interface checks, paired rank/null witness,
  fixed-source alias/continuation factors, literal weight arithmetic and gates.
- `manifest.json`: source SHA256 hashes, command, package versions and thread settings.
- `validation.json`: passed post-run source, link and saved-array checks, plus review record.
- `arrays.npz`: 24 by 24 null kernel and 3 by 4 continuation-factor array.
- `diagnostics.png`, `diagnostics.svg`: inspected scientific plots.

The null kernels are unrestricted exterior Helmholtz witnesses, not proven
differences of physical binary scatterers. Continuation factors do not measure
the actual scattering-tail amplitudes of TG-002. The weight check evaluates a
printed specification, not the cited authors' implementation.
