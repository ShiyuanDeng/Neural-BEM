"""How far the first-order atlas keeps predicting, measured rather than assumed.

An atlas cell is a derivative. Every use of it - a sensitivity map, a
Gauss-Newton step, a frequency ranking - silently assumes that a finite
boundary motion still behaves like its linearization. This module measures
where that stops being true, in two separate senses:

* `linearization_error`: purely forward. Compare the measured change in the
  scattered data against `J h` for a finite normal displacement `h`. No
  residual, no optimizer, no truth enters, so the result is a property of
  the geometry, contrast, frequency and shape direction alone.
* `step_quality`: the optimization sense. Compare the actual whitened misfit
  decrease of a finite step against the quadratic model's prediction.

The first answers "is the cell still a derivative here?"; the second answers
"is the cell still useful here?". They are not the same question, and the
horizon they report need not coincide.
"""
from dataclasses import dataclass, field

import numpy as np

from .atlas import orthonormal_normal_basis, to_solver_coefficients
from .forward import solve, shape_jacobian
from .geometry import FourierCurve, grid_size, normal_basis, integer


@dataclass(frozen=True)
class Perturbed:
    shape: FourierCurve
    representation_error: float
    rms_displacement: float
    maximum_displacement: float


def perturbed(shape, coefficients, storage_band, *, samples=None, tolerance=1e-3):
    """Displace along the normal WITHOUT changing the arclength gauge.

    `geometry.displaced` also reparameterizes, which is right inside the
    optimizer and wrong here: a gauge change would make the measured finite
    difference depend on a projection tolerance rather than on geometry.

    The truncation error of the displaced curve is checked RELATIVE to the
    displacement being measured, not against an absolute geometric floor.
    Both scale linearly in the amplitude, so this requirement fixes a band
    once for a direction instead of demanding ever larger bands as the ladder
    shrinks. A unit normal is only analytic, not band-limited, so the band
    needed is set by the curve's own normal field rather than by the harmonic.
    """
    coefficients = np.asarray(coefficients, float)
    storage_band = integer(storage_band, "storage band")
    band = len(coefficients) // 2
    count = samples or grid_size(max(shape.band, storage_band, band))
    nodes = shape.nodes(count)
    normal = nodes.normals[:, 0] + 1j * nodes.normals[:, 1]
    raw = to_solver_coefficients(coefficients, nodes.perimeter)
    displacement = normal_basis(nodes, band) @ raw
    target = shape.values(count) + displacement * normal
    result = FourierCurve.from_samples(target, storage_band)
    error = float(np.max(np.abs(result.values(count) - target)))
    rms = float(np.sqrt(np.sum(displacement ** 2 * nodes.arc_length_weights) / nodes.perimeter))
    allowed = tolerance * rms if rms > 0 else 1e-12 * nodes.perimeter / (2 * np.pi)
    if error > allowed:
        raise ValueError(f"Displaced curve unresolved at band {storage_band}: "
                         f"{error:.3g} against an allowance of {allowed:.3g}.")
    result.validate()
    return Perturbed(result, error, rms, float(np.max(np.abs(displacement))))


def default_storage_band(shape, band):
    """Generous band for a displaced curve; `perturbed` still checks it."""
    return 3 * max(shape.band, integer(band, "band", minimum=0)) + 32


def unit_direction(band, column):
    """Atlas coefficients selecting one orthonormal shape harmonic column."""
    direction = np.zeros(2 * integer(band, "band", minimum=0) + 1)
    direction[column] = 1.0
    return direction


@dataclass(frozen=True)
class HorizonProbe:
    """One direction's ladder of finite displacements at one frequency."""
    wavenumber: float
    label: str
    amplitudes: np.ndarray           # requested RMS normal displacement
    achieved: np.ndarray             # measured RMS normal displacement
    relative_error: np.ndarray       # ||dF - J h|| / ||J h||
    linear_norm: np.ndarray          # ||J h||
    actual_norm: np.ndarray          # ||dF||
    representation_error: np.ndarray
    failures: tuple = field(default_factory=tuple)

    def horizon(self, tolerance=0.1):
        """RMS displacement where `relative_error` first reaches `tolerance`.

        Interpolated in log-log between ladder rungs. `inf` means the whole
        ladder stayed inside tolerance; `0` means even the smallest rung was
        already outside it, which is a statement about the ladder, not a
        certificate that no smaller horizon exists.
        """
        error, amplitude = np.asarray(self.relative_error), np.asarray(self.achieved)
        good = np.isfinite(error) & (amplitude > 0)
        error, amplitude = error[good], amplitude[good]
        if len(error) == 0:
            return float("nan")
        crossed = np.nonzero(error >= tolerance)[0]
        if len(crossed) == 0:
            return float("inf")
        index = int(crossed[0])
        if index == 0:
            return 0.0
        low, high = index - 1, index
        span = np.log(error[high]) - np.log(error[low])
        if span <= 0:
            return float(amplitude[high])
        weight = (np.log(tolerance) - np.log(error[low])) / span
        return float(np.exp(np.log(amplitude[low])
                            + weight * (np.log(amplitude[high]) - np.log(amplitude[low]))))

    def order(self):
        """Fitted slope of log(relative error) against log(amplitude).

        A correctly measured first-order remainder gives slope near one. A
        slope near zero means the ladder is dominated by discretization or
        solver noise rather than by shape nonlinearity.
        """
        error, amplitude = np.asarray(self.relative_error), np.asarray(self.achieved)
        good = np.isfinite(error) & (error > 0) & (amplitude > 0) & (error < 0.3)
        if good.sum() < 3:
            return float("nan")
        return float(np.polyfit(np.log(amplitude[good]), np.log(error[good]), 1)[0])


def linearization_error(shape, wavenumber, contrast, acquisition, nodes, band,
                        directions, amplitudes, *, storage_band=None, work=None,
                        samples=None, tolerance=1e-8, state=None, jacobian=None):
    """Measure `||F(Gamma + h) - F(Gamma) - J h|| / ||J h||` on a ladder.

    `directions` maps a label to unit-norm atlas coefficients; `amplitudes`
    are RMS normal displacements in the same length unit as the geometry.
    The base solve and Jacobian are computed once and may be supplied.
    """
    if state is None:
        state = solve(shape, wavenumber, contrast, acquisition, nodes, work=work)
    basis = orthonormal_normal_basis(state.curve, band)
    if jacobian is None:
        jacobian = shape_jacobian(state, basis, work=work)
    perimeter = float(state.curve.perimeter)
    storage_band = storage_band or default_storage_band(shape, band)
    probes = []
    for label, direction in directions.items():
        direction = np.asarray(direction, float)
        rows = {name: [] for name in ("achieved", "relative_error", "linear_norm",
                                      "actual_norm", "representation_error")}
        failures = []
        for amplitude in amplitudes:
            # Unit L2(ds) columns: coefficient a gives RMS displacement a/sqrt(L).
            coefficients = direction * amplitude * np.sqrt(perimeter)
            try:
                moved = perturbed(shape, coefficients, storage_band,
                                  samples=samples, tolerance=tolerance)
                prediction = solve(moved.shape, wavenumber, contrast, acquisition,
                                   nodes, work=work).prediction
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                failures.append(dict(amplitude=float(amplitude), detail=str(exc)))
                for name in rows:
                    rows[name].append(np.nan)
                continue
            linear = jacobian @ coefficients
            actual = prediction - state.prediction
            linear_norm = float(np.linalg.norm(linear))
            rows["achieved"].append(moved.rms_displacement)
            rows["linear_norm"].append(linear_norm)
            rows["actual_norm"].append(float(np.linalg.norm(actual)))
            rows["representation_error"].append(moved.representation_error)
            rows["relative_error"].append(float(np.linalg.norm(actual - linear)
                                                / linear_norm) if linear_norm > 0 else np.nan)
        probes.append(HorizonProbe(float(wavenumber), label, np.asarray(amplitudes, float),
                                   *[np.asarray(rows[name], float) for name in
                                     ("achieved", "relative_error", "linear_norm",
                                      "actual_norm", "representation_error")],
                                   failures=tuple(failures)))
    return probes, state, jacobian


@dataclass(frozen=True)
class StepQuality:
    """A finite step's actual misfit decrease against the quadratic model."""
    wavenumber: float
    label: str
    steps: np.ndarray
    predicted_decrease: np.ndarray
    actual_decrease: np.ndarray
    achieved: np.ndarray

    @property
    def ratio(self):
        predicted = np.where(self.predicted_decrease > 0, self.predicted_decrease, np.nan)
        return self.actual_decrease / predicted

    def useful_fraction(self, threshold=0.5):
        ratio = self.ratio
        return float(np.nanmean(ratio >= threshold)) if len(ratio) else float("nan")


def step_quality(shape, observation, contrast, nodes, band, cell, direction,
                 steps, *, storage_band=None, work=None, samples=None,
                 tolerance=1e-8, label="step"):
    """Walk one direction and compare the measured misfit with the GN model.

    `cell` supplies the gradient and Gauss-Newton block at `shape`, so the
    model is exactly the one an optimizer would trust. `direction` is in atlas
    coefficients; the ladder multiplies it by each entry of `steps`.
    """
    direction = np.asarray(direction, float)
    perimeter = float(shape.nodes(grid_size(shape.band)).perimeter)
    storage_band = storage_band or default_storage_band(shape, band)
    slope = float(cell.gradient @ direction)
    curvature = float(direction @ cell.gauss_newton @ direction)
    predicted, actual, achieved = [], [], []
    for step in steps:
        model = step * slope - 0.5 * step ** 2 * curvature
        predicted.append(-model)  # decrease in 0.5||r||^2 for a descent direction
        try:
            moved = perturbed(shape, step * direction, storage_band,
                              samples=samples, tolerance=tolerance)
            prediction = solve(moved.shape, observation.wavenumber, contrast,
                               observation.acquisition, nodes, work=work).prediction
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            actual.append(np.nan)
            achieved.append(np.nan)
            continue
        residual = (prediction - observation.scattered) / cell.sigma
        actual.append(cell.whitened_misfit - float(0.5 * np.sum(np.abs(residual) ** 2)))
        achieved.append(moved.rms_displacement)
    return StepQuality(float(observation.wavenumber), label, np.asarray(steps, float),
                       np.asarray(predicted, float), np.asarray(actual, float),
                       np.asarray(achieved, float))


def gauss_newton_direction(cell, band_limit=None, tolerance=1e-8):
    """Rank-truncated GN step from a cell, optionally restricted to a band.

    Restricting to `band_limit` harmonics is what a continuation schedule does
    when it declares an update bandwidth; doing it here keeps the comparison
    between bandwidths on one cell rather than on separate solves.
    """
    from .atlas import harmonic_index
    gradient, block = cell.gradient, cell.gauss_newton
    keep = np.ones(len(gradient), bool)
    if band_limit is not None:
        keep = harmonic_index((len(gradient) - 1) // 2) <= band_limit
    eigenvalues, eigenvectors = np.linalg.eigh(block[np.ix_(keep, keep)])
    top = float(eigenvalues.max()) if len(eigenvalues) else 0.0
    step = np.zeros(len(gradient))
    if top <= 0:
        return step
    usable = eigenvalues > tolerance * top
    projected = eigenvectors[:, usable].T @ gradient[keep]
    step[keep] = -eigenvectors[:, usable] @ (projected / eigenvalues[usable])
    return step
