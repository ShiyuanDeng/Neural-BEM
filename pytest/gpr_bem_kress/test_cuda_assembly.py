"""SPD-011: opt-in CUDA Kress assembly reproduces the CPU reference system."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import linalg, special

from gpr_bem_kress import build_muller_system
from gpr_bem_kress.execution import execution
from ordered_boundary import circle, ellipse

torch = pytest.importorskip("torch")
pytestmark = pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")

from gpr_bem_kress import cuda_assembly  # noqa: E402


def _curve(nodes):
    return ellipse((0.03, -0.04), 0.08, 0.045, rotation=0.31, component_id="cuda-ellipse").discretize(
        nodes, require_even=True)


def test_cephes_port_matches_scipy_to_roundoff_of_the_hankel_magnitude():
    x = np.concatenate([np.geomspace(1e-6, 1.0, 20001), np.linspace(1.0, 60.0, 200001)])
    values = [v.cpu().numpy() for v in cuda_assembly.bessel012(torch.from_numpy(x).cuda())]
    for order, (j, y) in enumerate(zip(values[0::2], values[1::2])):
        magnitude = np.hypot(special.jv(order, x), special.yv(order, x))
        assert np.max(np.abs(j - special.jv(order, x)) / magnitude) < 1e-14
        assert np.max(np.abs(y - special.yv(order, x)) / magnitude) < 1e-14


@pytest.mark.parametrize("nodes, k_exterior", [(64, 3.0), (128, 12.0), (256, 40.0)])
def test_device_system_matches_the_reference_builder(nodes, k_exterior):
    curve = _curve(nodes)
    k_interior = 1.6 * k_exterior
    with execution(kernels="reference", device="cpu"):
        reference = build_muller_system(curve, k_exterior, k_interior).system_matrix
    matrix = cuda_assembly.build_muller_matrix(curve, k_exterior, k_interior).cpu().numpy()
    assert np.max(np.abs(matrix - reference)) <= 1e-14 * np.max(np.abs(reference))


def test_near_series_branch_is_exercised_and_matches():
    curve = circle((0.0, 0.0), 0.05, component_id="cuda-circle").discretize(256, require_even=True)
    k_exterior, k_interior = 20.0, 28.0
    spacing = 2 * np.pi * 0.05 / 256
    assert 28.0 * spacing <= 0.75  # nearest neighbours use the power-log series
    with execution(kernels="reference", device="cpu"):
        reference = build_muller_system(curve, k_exterior, k_interior).system_matrix
    matrix = cuda_assembly.build_muller_matrix(curve, k_exterior, k_interior).cpu().numpy()
    assert np.max(np.abs(matrix - reference)) <= 1e-14 * np.max(np.abs(reference))


def test_unsupported_inputs_are_declined():
    curve = _curve(32)
    assert cuda_assembly.supported(curve, 3.0, 4.0)
    assert not cuda_assembly.supported(curve, 3.0 - 0.1j, 4.0)
    assert not cuda_assembly.supported(curve, 3.0, 3.0)
    assert not cuda_assembly.supported(curve, -3.0, 4.0)
    assert not cuda_assembly.supported(curve.points, 3.0, 4.0)
    with pytest.raises(ValueError):
        cuda_assembly.build_muller_matrix(curve, 3.0 - 0.1j, 4.0)


def test_device_factors_solve_with_the_residual_guard():
    curve = _curve(128)
    matrix = cuda_assembly.build_muller_matrix(curve, 5.0, 8.0)
    rng = np.random.default_rng(11)
    rhs = rng.standard_normal((256, 3)) + 1j * rng.standard_normal((256, 3))
    solution, residual = cuda_assembly.DeviceFactors(matrix).solve(rhs)
    reference = linalg.lu_solve(linalg.lu_factor(matrix.cpu().numpy()), rhs)
    assert residual < 1e-13
    assert np.linalg.norm(solution - reference) <= 1e-12 * np.linalg.norm(reference)
    vector, _ = cuda_assembly.DeviceFactors(matrix).solve(rhs[:, 0])
    assert vector.shape == (256,) and np.allclose(vector, solution[:, 0], rtol=0, atol=1e-12)


def test_factors_release_device_memory_after_the_first_solve():
    curve = _curve(128)
    matrix = cuda_assembly.build_muller_matrix(curve, 5.0, 8.0)
    factors = cuda_assembly.DeviceFactors(matrix)
    reference = matrix.cpu().numpy()
    del matrix
    rhs = np.ones((256, 2), complex)
    first, first_residual = factors.solve(rhs)
    assert factors._resident is None and isinstance(factors.host, np.ndarray)  # nothing left on the device
    assert np.array_equal(factors.host, reference) and not factors.host.flags.writeable
    second, second_residual = factors.solve(rhs)  # residual check from the uploaded host matrix
    assert np.array_equal(first, second) and first_residual == second_residual < 1e-13


def _two_component_boundary(nodes):
    from ordered_boundary import OrderedBoundary2D
    first = ellipse((-0.06, 0.01), 0.04, 0.025, rotation=0.2, component_id="left").discretize(
        nodes, require_even=True)
    second = circle((0.07, -0.02), 0.03, component_id="right").discretize(nodes, require_even=True)
    return OrderedBoundary2D((first, second))


@pytest.mark.parametrize("nodes, k_exterior", [(64, 3.0), (128, 20.0)])
def test_multicomponent_device_system_matches_the_reference_builder(nodes, k_exterior):
    from gpr_bem_kress.multicomponent import build_multicomponent_muller_system
    boundary = _two_component_boundary(nodes)
    k_interior = 1.4 * k_exterior
    with execution(kernels="reference", device="cpu"):
        reference = build_multicomponent_muller_system(boundary, k_exterior, k_interior).system_matrix
    matrix = cuda_assembly.build_multicomponent_muller_matrix(boundary, k_exterior, k_interior).cpu().numpy()
    assert np.max(np.abs(matrix - reference)) <= 1e-14 * np.max(np.abs(reference))
    assert np.array_equal(cuda_assembly.build_system_matrix(boundary, k_exterior, k_interior).cpu().numpy(), matrix)


def test_multicomponent_device_assembly_keeps_the_clearance_guard():
    from ordered_boundary import OrderedBoundary2D
    from gpr_bem_kress.multicomponent import MultiComponentKressGeometryError
    touching = OrderedBoundary2D((
        circle((-0.0301, 0.0), 0.03, component_id="a").discretize(64, require_even=True),
        circle((0.0301, 0.0), 0.03, component_id="b").discretize(64, require_even=True)))
    with pytest.raises(MultiComponentKressGeometryError):
        cuda_assembly.build_multicomponent_muller_matrix(touching, 3.0, 4.0)
