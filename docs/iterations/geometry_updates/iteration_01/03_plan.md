# Simplify geometry updates

**Questions.** Can each geometry update and its checks be followed in one method
file? Can the active spectral update use direct area, speed and intersection
checks while preserving its projection and derivative calculations?

**Status.** Implemented on 2026-10-21 following the final scope decisions below.
Verification is recorded in [the implementation results](05_implementation.md).
This change includes no new inverse experiments.

Give each geometry update method its own script under
`solvers/bem_inverse/geometry_update_methods/`, exporting `geometry_update()`.
Use descriptive method names rather than numbered information-chain labels.

```text
geometry_update_methods/
    spline.py
    spectral.py
    certified_spectral.py       # Retained optional certificate method
    analytic_spectral.py
    gaussian_lipschitz.py
    similarity.py
    borges.py                   # Retained original update API
    certificates.py             # Optional certificate mathematics
    __init__.py                 # Selection binding and step bounds
```

Select the method once. Inside the backtracking loop, `fit_stage()` calls:

```python
candidate, diagnostics = geometry_update(
    current.curve, normal_update,
    prepared=prepared_geometry,
)
```

The selected callable binds the method settings before the loop. Each module
exports `geometry_update()` and owns its preparation, measurements, metric,
trial diagnostics and stored data in a flat class and a local data record.

The user chose this method-local arrangement on 2026-10-21, allowing duplication
where it makes each method readable. There is no shared `Prepared` redesign
and no update-class inheritance chain. Deduplication is deferred.

`prepared_geometry` holds reusable data for the current accepted curve:
normal-harmonic coordinates, base projections, sampling grids and derivatives.
Rebuild it after an accepted change; reuse it throughout backtracking.
Keep trial-only grid caches lazy. Ordinary curve operations, including values,
area, resizing and cleanup, live in `continuation/geometry.py`.

The active `spectral.geometry_update()` follows this sequence:

```python
projections = []
for count in [prepared.count, 2 * prepared.count]:
    nodes = sample_curve(curve, count)
    h = evaluate_normal_harmonics(normal_update, nodes.arclength)
    moved = fourier_from_samples(
        nodes.positions + h / length_unit_m * nodes.normals
    )
    check_area(moved.coefficients)
    moved_nodes = sample_curve(moved, count)
    check_speed(moved_nodes.speeds)
    check_intersection(moved_nodes.points)
    projections.append(arclength_projection(moved, moved_nodes, stored_band))

trial = curve.coefficients + projections[0] - prepared.base_projection
refined = curve.coefficients + projections[1] - prepared.fine_base_projection
check_projection_agreement(trial, refined, radius, tolerance)
candidate = FourierCurve(trial)
check_area(candidate.coefficients)
candidate_nodes = sample_curve(candidate)
check_speed(candidate_nodes.speeds)
check_intersection(candidate_nodes.points)
return candidate, diagnostics
```

The checks live in `checks.py` and receive numerical inputs, without an update
object, callbacks or timing wrappers. Area uses the weighted squared Fourier
coefficients; speed compares minimum with mean; intersection uses segment cross
products and touching tests on nonadjacent sampled segments.

`spectral.py` contains the spectral projection calculations: integrate speed to
obtain normalized arclength, then compute weighted Fourier sums in the stored
band. Methods using that same projection can call these numerical functions.

Keep grid/doubled-grid agreement, current tolerances and exact zero-step identity.
`analytic_spectral.py` owns its analytic preparation and uses the same sampled
spectral finite trial. The other methods own their finite construction.

Preserve batched derivative preparation and its caches. It must differentiate the
same finite geometry map used by `geometry_update()`. Keep physics evaluation,
acceptance and replacement of the current curve in `fit_stage()`.

Remove geometry-validity certificates from the active spectral path, including
increment bounds, full certificates and certificate overrides of sampled refusals.
Record the method as spectral with sampled validity, not `certified_spectral`.

Keep the certificate implementation in `certified_spectral.py` and its numerical
calculations in `certificates.py`, separately from the active method. Shared
curve mathematics and certificates no longer depend on experimental `n_update.py`.

Move all retained methods now, including similarity and the original Borges
interface. The upper `geometry.py`, `continuation/updates.py`, and previous
method paths retain compatibility exports; old `trial()` calls use the new code.

The maintained named pipelines and TG-002 select `spectral` with batched
preparation. Bare `fit()` retains its spline default. Historical explicit
certificate selections and saved evidence keep their original meaning.

This changes admissibility: sampled checks become decisive and no longer provide
a continuous-curve certificate. A current runtime improvement is not established;
the [saved timings](../../../evidence.md#41-how-it-was-built) include later GPU
improvements and do not compare the current implementations directly.

For implementation, reuse the focused geometry checks for construction, zero
steps, projection agreement and invalid-curve refusals. Compare constructed
coefficients where both methods accept; do not require identical acceptance after
removing certificates. No additional runs are included to establish speedup.
