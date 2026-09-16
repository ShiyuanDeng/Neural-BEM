"""The adjoint geometry pullback differentiates actual Method-B rebuilding."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from sdf_inverse.geometry import OrderedSDFGeometryConfig, build_ordered_sdf_geometry
from sdf_inverse.method_b_pullback import MethodBPullbackError, build_method_b_pullback


class SmoothNeuralField(torch.nn.Module):
    """An asymmetric regular contour with genuinely coupled neural weights."""

    def __init__(self):
        super().__init__()
        with torch.random.fork_rng():
            torch.manual_seed(71)
            self.network = torch.nn.Sequential(
                torch.nn.Linear(2, 5, dtype=torch.float64),
                torch.nn.Tanh(),
                torch.nn.Linear(5, 1, dtype=torch.float64),
            )

    def forward(self, points):
        delta = points - points.new_tensor((0.061, -0.043))
        radial = torch.sqrt((delta[:, 0] / 0.63).square() + (delta[:, 1] / 0.48).square()) - 1.0
        return radial + 0.08 * self.network(points).reshape(-1)


def _config():
    return OrderedSDFGeometryConfig(
        bounds=((-1.0, -0.9), (1.1, 1.0)), grid_shape=(39, 41),
        projected_samples=32, bandwidth=5, num_nodes=32,
        arclength_dense_resolution=96, validation_resolution=96,
    )


def test_replay_matches_actual_native_curve_and_retains_parameter_graph():
    model = SmoothNeuralField()
    reference = build_ordered_sdf_geometry(model, _config()).curve
    pullback = build_method_b_pullback(model, _config(), reference_curve=reference)
    for name in ("points", "first_derivatives", "second_derivatives"):
        tensor = getattr(pullback, name)
        assert tensor.requires_grad
        np.testing.assert_allclose(tensor.detach().numpy(), getattr(reference, name), rtol=2e-11, atol=2e-12)
    assert pullback.curve is reference
    assert pullback.maximum_replay_error < 1e-11
    assert all(parameter.grad is None for parameter in model.parameters())


@pytest.mark.parametrize("derivative_order", (0, 1, 2))
def test_neural_weight_pullback_matches_fresh_method_b_directional_differences(derivative_order):
    model = SmoothNeuralField()
    config = _config()
    pullback = build_method_b_pullback(model, config)
    names = ("points", "first_derivatives", "second_derivatives")
    name = names[derivative_order]
    rng = np.random.default_rng(32 + derivative_order)
    covector = rng.normal(size=(config.num_nodes, 2))
    value = (getattr(pullback, name) * torch.tensor(covector)).sum()
    parameters = tuple(model.parameters())
    gradients = torch.autograd.grad(value, parameters)
    directions = tuple(torch.tensor(rng.normal(size=tuple(parameter.shape))) for parameter in parameters)
    norm = torch.sqrt(sum(direction.square().sum() for direction in directions))
    directions = tuple(direction / norm for direction in directions)
    adjoint_direction = float(sum((gradient * direction).sum() for gradient, direction in zip(gradients, directions)))
    initial = tuple(parameter.detach().clone() for parameter in parameters)

    def rebuilt_value(step):
        with torch.no_grad():
            for parameter, original, direction in zip(parameters, initial, directions):
                parameter.copy_(original + step * direction)
        curve = build_ordered_sdf_geometry(model, config).curve
        return float(np.sum(getattr(curve, name) * covector))

    errors = []
    try:
        for step in (2e-5, 1e-5):
            difference = (rebuilt_value(step) - rebuilt_value(-step)) / (2.0 * step)
            errors.append(abs(difference - adjoint_direction))
            assert difference == pytest.approx(adjoint_direction, rel=2e-5, abs=2e-7)
    finally:
        with torch.no_grad():
            for parameter, original in zip(parameters, initial):
                parameter.copy_(original)
    assert max(errors) < 2e-7 + 2e-5 * abs(adjoint_direction)


def test_exact_grid_vertex_crossing_is_explicitly_rejected():
    class GridCircle(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.radius = torch.nn.Parameter(torch.tensor(0.5, dtype=torch.float64))

        def forward(self, points):
            return torch.linalg.vector_norm(points, dim=1) - self.radius

    config = OrderedSDFGeometryConfig(
        bounds=((-1.0, -1.0), (1.0, 1.0)), grid_shape=(33, 33),
        projected_samples=24, bandwidth=3, num_nodes=24,
        arclength_dense_resolution=64, validation_resolution=64,
    )
    with pytest.raises(MethodBPullbackError, match="exact Cartesian grid vertex"):
        build_method_b_pullback(GridCircle(), config)


def test_pullback_rejects_a_stale_forward_curve():
    model = SmoothNeuralField()
    config = _config()
    stale_curve = build_ordered_sdf_geometry(model, config).curve
    with torch.no_grad():
        model.network[-1].bias.add_(0.01)
    with pytest.raises(MethodBPullbackError, match="disagrees with production"):
        build_method_b_pullback(model, config, reference_curve=stale_curve)
