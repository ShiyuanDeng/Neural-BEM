"""Frequency x shape-harmonic characterization on the current boundary.

The object built here is deliberately *not* a single heatmap. At one geometry
`Gamma`, one contrast and one whitening convention it stores, per available
wavenumber, four distinct layers that the literature repeatedly conflates:

1. `sensitivity[p]`  - whitened column norm, local visibility only.
2. `gradient[p]`     - signed residual projection, first-order descent.
3. `gauss_newton`    - the FULL P x P block, so cross-harmonic ambiguity
                       survives; its diagonal is layer 1 squared.
4. `spectrum`        - eigenvalues/vectors of that block, i.e. the collective
                       observable shape directions.

Conventions that must be declared before any cell is interpreted:

* Shape coordinates are normal displacements `h = sum_p a_p phi_p`, with
  `phi_p` ORTHONORMAL in `L^2(ds)` on the current curve. A Cartesian Fourier
  coefficient of `z(t)` is not a shape direction; rescaling `phi_p` rescales
  every diagonal information measure, so the normalization is fixed here once.
* Data are whitened by `C_l = sigma_l^2 I`. `sigma_l` follows a declared
  `Whitening`; nothing else in this module divides by a data norm.
* Everything is evaluated at the supplied geometry. No cell is a statement
  about a different iterate, and none is a resolution or identifiability
  certificate on its own.
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .forward import Acquisition, Work, solve, shape_jacobian, timed
from .geometry import FourierCurve, arclength_angles, grid_size, integer


def orthonormal_normal_basis(curve, band):
    """Arclength harmonics scaled to unit `L^2(ds)` norm on this curve.

    Columns are ordered `[1, cos(s), sin(s), ..., cos(band s), sin(band s)]`
    in the normalized arclength angle, matching `geometry.normal_basis` up to
    the scaling `1/sqrt(L)` and `sqrt(2/L)`. That scaling is what makes a
    column norm comparable between harmonics, between wavenumbers and between
    iterates with different perimeters.
    """
    band = integer(band, "atlas band", minimum=0)
    angles, length = arclength_angles(curve)
    phase = angles[:, None] * np.arange(1, band + 1)
    raw = np.column_stack((np.ones(len(angles)), np.cos(phase), np.sin(phase)))
    scale = np.concatenate(([1.0 / np.sqrt(length)],
                            np.repeat(np.sqrt(2.0 / length), 2 * band)))
    # Interleave cos/sin so column p+1 pairs with p for a harmonic, as the
    # reordering below expects; keep the flat layout the solver already uses.
    order = np.empty(2 * band + 1, int)
    order[0] = 0
    order[1::2] = np.arange(1, band + 1)
    order[2::2] = np.arange(band + 1, 2 * band + 1)
    return raw[:, order] * scale[order]


def harmonic_index(band):
    """Harmonic number of each basis column: 0, 1, 1, 2, 2, ..."""
    band = integer(band, "atlas band", minimum=0)
    return np.repeat(np.arange(band + 1), np.r_[1, np.full(band, 2)])


@dataclass(frozen=True)
class Whitening:
    """`C_l = sigma_l^2 I`; the only place a data scale enters the atlas.

    `relative` sets `sigma_l = level * ||d_l|| / sqrt(n_l)`: independent noise
    at a fixed fraction of the per-datum RMS amplitude of that frequency's own
    data. Whitened sensitivities then carry the honest `sqrt(n_l)` gain of a
    larger acquisition. `absolute` sets `sigma_l = level` for every frequency,
    so frequencies with physically larger fields keep their advantage.
    `acquisition_neutral` sets `sigma_l = level * ||d_l||`, which removes the
    acquisition-size gain and is useful for separating physics from growing
    receiver counts. It is NOT a statistical whitening and is labelled here as
    a display convention.
    """
    kind: str = "relative"
    level: float = 1e-3

    def __post_init__(self):
        if self.kind not in ("relative", "absolute", "acquisition_neutral"):
            raise ValueError("kind must be relative, absolute or acquisition_neutral.")
        if not np.isfinite(self.level) or self.level <= 0:
            raise ValueError("Noise level must be positive.")

    def sigma(self, data):
        data = np.asarray(data)
        count = data.size
        if self.kind == "absolute":
            return float(self.level)
        norm = float(np.linalg.norm(data))
        if norm == 0:
            raise ValueError("Cannot whiten against zero data.")
        if self.kind == "relative":
            return self.level * norm / np.sqrt(count)
        return self.level * norm


@dataclass(frozen=True)
class AtlasCell:
    """One wavenumber's reduced characterization at one geometry."""
    wavenumber: float
    sigma: float
    data_count: int
    sensitivity: np.ndarray          # (P,)   ||C^-1/2 J_p||
    gradient: np.ndarray             # (P,)   Re<J_p, C^-1 r>
    gauss_newton: np.ndarray         # (P,P)  Re(J* C^-1 J)
    eigenvalues: np.ndarray          # (P,)   descending
    eigenvectors: np.ndarray         # (P,P)  columns match eigenvalues
    relative_residual: float
    whitened_misfit: float           # 0.5 ||C^-1/2 r||^2
    leakage: Optional[np.ndarray] = field(default=None, repr=False)

    @property
    def correlation(self):
        """Normalized GN block: 1 on the diagonal, cross-talk off it."""
        scale = np.sqrt(np.clip(np.diag(self.gauss_newton), np.finfo(float).tiny, None))
        return self.gauss_newton / np.outer(scale, scale)

    def effective_rank(self, tolerance=1e-6):
        """Count of eigenvalues above `tolerance` times the largest."""
        top = float(self.eigenvalues[0]) if len(self.eigenvalues) else 0.0
        return int(np.sum(self.eigenvalues > tolerance * top)) if top > 0 else 0

    def participation_rank(self):
        """Spectral entropy rank exp(H) of the normalized eigenvalue mass."""
        total = float(np.sum(self.eigenvalues))
        if total <= 0:
            return 0.0
        weight = np.clip(self.eigenvalues / total, np.finfo(float).tiny, None)
        return float(np.exp(-np.sum(weight * np.log(weight))))

    def predicted_decrease(self, tolerance=1e-10):
        """Gauss-Newton predicted misfit decrease `0.5 g^T H^+ g`.

        This is the local model's own claim, not a measured improvement. The
        pseudo-inverse uses a relative eigenvalue cutoff, so it reports what a
        rank-truncated GN solve would predict.
        """
        top = float(self.eigenvalues[0]) if len(self.eigenvalues) else 0.0
        if top <= 0:
            return 0.0
        keep = self.eigenvalues > tolerance * top
        projected = self.eigenvectors[:, keep].T @ self.gradient
        return float(0.5 * np.sum(projected ** 2 / self.eigenvalues[keep]))


@dataclass(frozen=True)
class Atlas:
    """Cells at one geometry, on one common shape-harmonic basis."""
    band: int
    perimeter: float
    contrast: float
    whitening: Whitening
    cells: tuple

    @property
    def wavenumbers(self):
        return np.array([cell.wavenumber for cell in self.cells])

    @property
    def harmonics(self):
        return harmonic_index(self.band)

    def layer(self, name):
        return np.array([getattr(cell, name) for cell in self.cells])

    def harmonic_sensitivity(self):
        """Per-harmonic magnitude: cos/sin pairs combined in quadrature."""
        return _combine_pairs(self.layer("sensitivity") ** 2, self.band) ** 0.5

    def harmonic_gradient_norm(self):
        return _combine_pairs(self.layer("gradient") ** 2, self.band) ** 0.5

    def cross_frequency_alignment(self):
        """cos angle between whitened gradients of every frequency pair."""
        gradients = self.layer("gradient")
        norms = np.linalg.norm(gradients, axis=1)
        safe = np.where(norms > 0, norms, 1.0)
        unit = gradients / safe[:, None]
        alignment = unit @ unit.T
        alignment[norms == 0, :] = np.nan
        alignment[:, norms == 0] = np.nan
        return alignment


def _combine_pairs(values, band):
    """Sum column pairs (cos,sin) of the same harmonic; keep the constant."""
    values = np.asarray(values, float)
    head = values[..., :1]
    tail = values[..., 1:].reshape(*values.shape[:-1], band, 2).sum(axis=-1)
    return np.concatenate((head, tail), axis=-1)


def cell_at(shape, observation, contrast, band, nodes, *, whitening=None,
            work=None, keep_selection=False):
    """Build one cell: one forward solve, one Jacobian, then reductions only.

    The dense Jacobian is discarded before returning; only `P`-sized and
    `P x P` objects survive, so an atlas over many frequencies stays small.
    """
    whitening = Whitening() if whitening is None else whitening
    band = integer(band, "atlas band", minimum=0)
    state = solve(shape, observation.wavenumber, contrast,
                  observation.acquisition, nodes, work=work)
    basis = orthonormal_normal_basis(state.curve, band)
    jacobian = shape_jacobian(state, basis, work=work)
    residual = state.prediction - observation.scattered
    sigma = whitening.sigma(observation.scattered)
    flat = jacobian.reshape(-1, basis.shape[1]) / sigma
    whitened_residual = residual.ravel() / sigma
    with timed(work, "atlas_reduction"):
        gram = flat.conj().T @ flat
        gauss_newton = np.ascontiguousarray(gram.real)
        gauss_newton = 0.5 * (gauss_newton + gauss_newton.T)
        gradient = (flat.conj().T @ whitened_residual).real
        sensitivity = np.sqrt(np.clip(np.diag(gauss_newton), 0, None))
        eigenvalues, eigenvectors = np.linalg.eigh(gauss_newton)
        order = np.argsort(eigenvalues)[::-1]
        eigenvalues, eigenvectors = eigenvalues[order], eigenvectors[:, order]
        eigenvalues = np.clip(eigenvalues, 0, None)
        leakage = _selection_leakage(jacobian, band) if keep_selection else None
    scale = float(np.linalg.norm(observation.scattered)) or 1.0
    return AtlasCell(float(observation.wavenumber), float(sigma), int(residual.size),
                     sensitivity, gradient, gauss_newton, eigenvalues, eigenvectors,
                     float(np.linalg.norm(residual) / scale),
                     float(0.5 * np.sum(np.abs(whitened_residual) ** 2)), leakage)


def _selection_leakage(jacobian, band):
    """Energy fraction of each column OFF the circle's exact `a + b = n` line.

    On a centred circle rotational equivariance makes each column's double
    Fourier support exactly `a + b = +/- n`, so this is zero to solver
    accuracy. On any other curve the number measures how far the analytic
    selection rule has stopped holding at the present geometry, which is the
    quantity a circle-derived rule silently assumes away.
    """
    illuminations, receivers = jacobian.shape[:2]
    if illuminations != receivers:
        raise ValueError("Selection leakage needs equal illumination and receiver counts.")
    spectrum = np.abs(np.fft.fft2(jacobian, axes=(0, 1))) ** 2
    first = np.fft.fftfreq(illuminations, 1 / illuminations).astype(int)
    second = np.fft.fftfreq(receivers, 1 / receivers).astype(int)
    total = np.mod(first[:, None] + second[None, :], illuminations)
    harmonics = harmonic_index(band)
    energy = spectrum.sum(axis=(0, 1))
    on_line = np.array([spectrum[np.isin(total, np.mod([n, -n], illuminations)), column].sum()
                        for column, n in enumerate(harmonics)])
    return np.where(energy > 0, 1.0 - on_line / np.where(energy > 0, energy, 1.0), np.nan)


def build(shape, observations, contrast, band, node_rule, *, whitening=None,
          work=None, wavenumbers=None, keep_selection=False, progress=None):
    """Atlas over the supplied observations at one geometry.

    `node_rule(wavenumber)` supplies the quadrature size; it is an explicit
    caller decision so that an atlas is never silently built at a resolution
    the forward model does not support. Cells are independent solves.
    """
    whitening = Whitening() if whitening is None else whitening
    catalog = {float(o.wavenumber): o for o in observations}
    chosen = sorted(catalog) if wavenumbers is None else [float(k) for k in wavenumbers]
    missing = [k for k in chosen if k not in catalog]
    if missing:
        raise ValueError(f"No observation for wavenumbers {missing}.")
    cells = []
    perimeter = float(shape.nodes(grid_size(shape.band)).perimeter)
    for wavenumber in chosen:
        cell = cell_at(shape, catalog[wavenumber], contrast, band,
                       node_rule(wavenumber), whitening=whitening, work=work,
                       keep_selection=keep_selection)
        cells.append(cell)
        if progress is not None:
            progress(cell)
    return Atlas(int(band), perimeter, float(contrast), whitening, tuple(cells))


def transport_overlap(first, second, band):
    """Mixing of the two curves' arclength harmonic bases under normal transport.

    A harmonic index means a different function on a different curve. This
    reports `O[p,q] = <phi_p^first(x), phi_q^second(P(x))> ds` using the
    closest-point correspondence `P` between the sampled curves, which is the
    honest statement of how comparable two atlas cells from different iterates
    are. It is diagnostic; nothing in the controller assumes `O = I`.
    """
    count = grid_size(max(first.band, second.band, band))
    nodes_a, nodes_b = first.nodes(count), second.nodes(count)
    basis_a = orthonormal_normal_basis(nodes_a, band)
    basis_b = orthonormal_normal_basis(nodes_b, band)
    points_a, points_b = nodes_a.points, nodes_b.points
    index = np.argmin(((points_a[:, None, :] - points_b[None, :, :]) ** 2).sum(-1), axis=1)
    weights = nodes_a.arc_length_weights
    return basis_a.T @ (weights[:, None] * basis_b[index])
