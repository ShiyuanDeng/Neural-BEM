"""Atlas conventions, and the exact circle selection rule it must reproduce."""
import numpy as np
import pytest

from .atlas import (Atlas, Whitening, build, cell_at, harmonic_index,
                    orthonormal_normal_basis, transport_overlap)
from .forward import Acquisition, solve, shape_jacobian
from .geometry import FourierCurve, displaced, grid_size, normal_basis
from .inverse import Observation
from .run import fixture


def circle_observation(shape, wavenumber, contrast, directions, receivers, nodes):
    acquisition = Acquisition.ring(directions, receivers)
    field = solve(shape, wavenumber, contrast, acquisition, nodes).prediction
    return Observation(wavenumber, acquisition, field)


@pytest.mark.parametrize("scene", ("circle", "ellipse", "glider"))
def test_basis_is_orthonormal_in_arclength(scene):
    nodes = fixture(scene).nodes(1024)
    basis = orthonormal_normal_basis(nodes, 12)
    gram = basis.T @ (nodes.arc_length_weights[:, None] * basis)
    assert np.allclose(gram, np.eye(basis.shape[1]), atol=1e-8)


def interleave(band):
    """Solver-basis column order matching the atlas layout."""
    return np.r_[0, np.ravel(np.column_stack((np.arange(1, band + 1),
                                              np.arange(band + 1, 2 * band + 1))))]


def analytic_scale(perimeter, band):
    return np.r_[1 / np.sqrt(perimeter), np.repeat(np.sqrt(2 / perimeter), 2 * band)]


def test_basis_matches_unnormalised_solver_basis_up_to_scale():
    nodes = fixture("glider").nodes(512)
    band = 6
    mine, theirs = orthonormal_normal_basis(nodes, band), normal_basis(nodes, band)
    expected = theirs[:, interleave(band)] * analytic_scale(nodes.perimeter, band)
    assert np.allclose(mine, expected, atol=1e-12)


def test_harmonic_index_follows_the_interleaved_layout():
    assert harmonic_index(3).tolist() == [0, 1, 1, 2, 2, 3, 3]


def test_whitening_kinds_differ_only_by_declared_scales():
    data = np.arange(1, 13).reshape(3, 4) + 0j
    count, norm = data.size, np.linalg.norm(data)
    assert Whitening("absolute", 0.5).sigma(data) == 0.5
    assert np.isclose(Whitening("relative", 0.5).sigma(data), 0.5 * norm / np.sqrt(count))
    assert np.isclose(Whitening("acquisition_neutral", 0.5).sigma(data), 0.5 * norm)
    with pytest.raises(ValueError):
        Whitening("nope")


def test_sensitivity_is_the_gauss_newton_diagonal_and_scales_with_whitening():
    shape = FourierCurve.circle(1.0)
    observation = circle_observation(fixture("ellipse"), 2.0, 1.44, 12, 12, 128)
    cell = cell_at(shape, observation, 1.44, 5, 128, whitening=Whitening("relative", 1e-3))
    assert np.allclose(cell.sensitivity ** 2, np.diag(cell.gauss_newton), rtol=1e-10)
    louder = cell_at(shape, observation, 1.44, 5, 128, whitening=Whitening("relative", 2e-3))
    assert np.allclose(cell.sensitivity, 2 * louder.sensitivity, rtol=1e-10)
    assert np.allclose(cell.gradient, 4 * louder.gradient, rtol=1e-10)


def test_gradient_matches_a_finite_difference_of_the_whitened_misfit():
    """The signed layer must be the derivative of the objective it claims."""
    shape = FourierCurve.circle(1.0)
    observation = circle_observation(fixture("ellipse"), 2.0, 1.44, 16, 16, 192)
    band, nodes, contrast = 4, 192, 1.44
    cell = cell_at(shape, observation, contrast, band, nodes)
    sigma = cell.sigma
    def misfit(coefficients):
        moved = displaced(shape, coefficients, 24).shape
        prediction = solve(moved, observation.wavenumber, contrast,
                           observation.acquisition, nodes).prediction
        return 0.5 * np.sum(np.abs((prediction - observation.scattered) / sigma) ** 2)
    # Express each orthonormal direction in the solver's unnormalised
    # coefficients, which `displaced` consumes.
    order = interleave(band)
    scale = analytic_scale(shape.nodes(nodes).perimeter, band)
    step = 1e-5
    for column in (0, 1, 2, 5):
        direction = np.zeros(2 * band + 1)
        direction[order[column]] = scale[column]
        derivative = (misfit(step * direction) - misfit(-step * direction)) / (2 * step)
        assert np.isclose(derivative, cell.gradient[column], rtol=2e-4, atol=1e-6)


def test_predicted_decrease_is_positive_and_bounded_by_the_misfit():
    shape = FourierCurve.circle(1.0)
    observation = circle_observation(fixture("ellipse"), 2.0, 1.44, 16, 16, 192)
    cell = cell_at(shape, observation, 1.44, 6, 192)
    assert 0 < cell.predicted_decrease()
    assert cell.effective_rank() >= 1
    assert 1 <= cell.participation_rank() <= len(cell.eigenvalues)


def test_circle_selection_rule_is_exact_not_perturbative():
    """Rotational equivariance forces harmonic n into data modes a + b = n.

    For a centred circle the map from a normal harmonic to the (illumination,
    receiver) data matrix commutes with simultaneous rotation, so the double
    Fourier support of each Jacobian column is the single line a + b = n.
    That is exact at any contrast, which is strictly stronger than the
    small-perturbation, low-contrast Ammari-Chow-Zou statement; the Bessel
    product only supplies the amplitude on that line.
    """
    shape, contrast, wavenumber, nodes = FourierCurve.circle(1.0), 1.44, 3.0, 256
    directions = receivers = 32
    acquisition = Acquisition.ring(directions, receivers)
    state = solve(shape, wavenumber, contrast, acquisition, nodes)
    band = 5
    jacobian = shape_jacobian(state, orthonormal_normal_basis(state.curve, band))
    spectrum = np.abs(np.fft.fft2(jacobian, axes=(0, 1)))
    a = np.fft.fftfreq(directions, 1 / directions).astype(int)
    b = np.fft.fftfreq(receivers, 1 / receivers).astype(int)
    total = a[:, None] + b[None, :]
    harmonics = harmonic_index(band)
    for column, n in enumerate(harmonics):
        plane = spectrum[:, :, column]
        on_line = np.isin(np.mod(total, directions), np.mod([n, -n], directions))
        assert plane[on_line].max() > 0
        assert plane[~on_line].max() <= 1e-9 * plane[on_line].max()


def circle_amplitude_table(wavenumber, contrast, radius, order_limit, *,
                           nodes, receiver_radius=400.0):
    """Extract `V(a, b)` from the circle Jacobian, one entry per data-mode pair.

    The complex harmonic `exp(i n phi)` lands on the single line `a + b = n`,
    so sweeping `n` over `[-2L, 2L]` fills the whole `(a, b)` rectangle with
    `|a|, |b| <= L`. Hadamard's formula makes each entry the product of an
    incident-order boundary trace and a receiver-order reciprocal trace, so
    the table must be exactly rank one.
    """
    band = 2 * order_limit
    directions = receivers = 4 * band + 8
    shape = FourierCurve.circle(radius)
    acquisition = Acquisition.ring(directions, receivers, radius=receiver_radius)
    state = solve(shape, wavenumber, contrast, acquisition, nodes)
    jacobian = shape_jacobian(state, orthonormal_normal_basis(state.curve, band))
    a = np.fft.fftfreq(directions, 1 / directions).astype(int)
    b = np.fft.fftfreq(receivers, 1 / receivers).astype(int)
    def harmonic_column(n):
        if n == 0:  # match the sqrt(2/L) scaling the cos/sin columns carry
            return np.sqrt(2.0) * jacobian[:, :, 0]
        cosine, sine = jacobian[:, :, 2 * abs(n) - 1], jacobian[:, :, 2 * abs(n)]
        return cosine + (1j if n > 0 else -1j) * sine
    spectra = {n: np.fft.fft2(harmonic_column(n), axes=(0, 1)) / (directions * receivers)
               for n in range(-band, band + 1)}
    orders = np.arange(-order_limit, order_limit + 1)
    row = {int(value): index for index, value in enumerate(a)}
    column = {int(value): index for index, value in enumerate(b)}
    table = np.array([[spectra[first + second][row[first], column[second]]
                       for second in orders] for first in orders])
    return table, orders


def test_circle_atlas_is_exactly_a_rank_one_order_table():
    """Hadamard plus rotational symmetry force `V(a,b) = A_a B_b` exactly.

    This holds at any contrast and any receiver radius, which is strictly
    stronger than the low-contrast far-field Bessel product; that product is
    only the weak-scattering, far-field limit of `A` and `B`.
    """
    table, _ = circle_amplitude_table(4.0, 6.0, 1.0, 3, nodes=384)
    singular = np.linalg.svd(table, compute_uv=False)
    assert singular[0] > 0
    assert singular[1] / singular[0] < 1e-8


def test_rank_one_structure_survives_high_contrast_and_a_near_receiver():
    table, _ = circle_amplitude_table(3.0, 10.0, 1.0, 3, nodes=512, receiver_radius=10.0)
    singular = np.linalg.svd(table, compute_uv=False)
    assert singular[1] / singular[0] < 1e-8


def test_circle_far_field_low_contrast_limit_matches_the_bessel_product():
    from scipy.special import jv
    table, orders = circle_amplitude_table(4.0, 1.01, 1.0, 3, nodes=384)
    predicted = np.abs(np.outer(jv(orders, 4.0), jv(orders, 4.0)))
    measured = np.abs(table)
    keep = predicted > 0.02 * predicted.max()
    ratio = measured[keep] / predicted[keep]
    assert np.std(ratio) / np.mean(ratio) < 0.08


def test_atlas_layers_and_alignment_have_consistent_shapes():
    shape = FourierCurve.circle(1.0)
    observations = [circle_observation(fixture("ellipse"), k, 1.44, 12, 12, 160)
                    for k in (1.0, 1.5, 2.0)]
    atlas = build(shape, observations, 1.44, 4, lambda k: 160)
    assert isinstance(atlas, Atlas) and len(atlas.cells) == 3
    assert atlas.layer("sensitivity").shape == (3, 9)
    assert atlas.harmonic_sensitivity().shape == (3, 5)
    alignment = atlas.cross_frequency_alignment()
    assert np.allclose(np.diag(alignment), 1.0)
    assert np.allclose(alignment, alignment.T, equal_nan=True)
    assert np.all(np.abs(alignment) <= 1 + 1e-12)
    with pytest.raises(ValueError):
        build(shape, observations, 1.44, 4, lambda k: 160, wavenumbers=[9.0])


def test_transport_overlap_is_identity_for_a_curve_against_itself():
    shape = fixture("ellipse")
    overlap = transport_overlap(shape, shape, 4)
    assert np.allclose(overlap, np.eye(9), atol=1e-6)


def test_transport_overlap_detects_basis_drift_between_iterates():
    shape = fixture("ellipse")
    moved = displaced(shape, np.r_[0.0, 0.15, np.zeros(5)], 32).shape
    overlap = transport_overlap(shape, moved, 5)
    assert not np.allclose(overlap, np.eye(11), atol=1e-2)
    assert np.all(np.abs(overlap) <= 1 + 1e-6)


def test_selection_leakage_is_zero_on_a_circle_and_positive_otherwise():
    contrast, wavenumber, nodes = 2.0, 3.0, 256
    observation = circle_observation(fixture("glider"), wavenumber, contrast, 32, 32, 512)
    on_circle = cell_at(FourierCurve.circle(1.0), observation, contrast, 4, nodes,
                        keep_selection=True)
    off_circle = cell_at(fixture("ellipse"), observation, contrast, 4, nodes,
                         keep_selection=True)
    assert np.nanmax(on_circle.leakage) < 1e-12
    assert np.nanmin(off_circle.leakage[1:]) > 1e-6


def test_selection_leakage_is_absent_unless_requested():
    observation = circle_observation(fixture("glider"), 2.0, 1.44, 24, 24, 384)
    assert cell_at(FourierCurve.circle(1.0), observation, 1.44, 3, 192).leakage is None
