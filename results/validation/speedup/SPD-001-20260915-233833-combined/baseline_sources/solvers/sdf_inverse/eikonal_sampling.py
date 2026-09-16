"""Deterministic, iteration-local samples for the implicit inverse penalty."""

from __future__ import annotations

import hashlib
import numpy as np
import torch


def sample_set_hash(points):
    values = points.detach().cpu().numpy() if isinstance(points, torch.Tensor) else points
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes()).hexdigest()


def regularization_points(model, geometry_config, config):
    """Rebuild only at accepted states; callers freeze these during search.

    The baseline RNG draw is identical to the historical uniform-box draw.
    The mixed arm uses half that seeded global draw and half raw-contour
    arc-length samples, displaced along field normals by deterministic offsets.
    """
    parameter = next(model.parameters())
    bounds = np.asarray(geometry_config.bounds)
    count = config.regularization_samples
    global_count = count if config.eikonal_sampling == "uniform_box" else count // 2
    values = np.random.default_rng(config.random_seed).uniform(bounds[0], bounds[1], (global_count, 2))
    if config.eikonal_sampling == "contour_band":
        from sdf_to_ordered_boundary import FrontendConfig, ProjectionConfig, TorchImplicitField2D, prepare_single_component
        from .geometry import _projection_residual_tolerance
        field = TorchImplicitField2D(model, dtype=parameter.dtype, device=parameter.device,
                                     sign_convention="negative_inside")
        raw = prepare_single_component(field, FrontendConfig(
            bounds=geometry_config.bounds, grid_shape=geometry_config.grid_shape,
            projected_samples=max(geometry_config.projected_samples, count),
            projection=ProjectionConfig(residual_tolerance=_projection_residual_tolerance(parameter.dtype)),
        )).projected_points
        lengths = np.linalg.norm(np.roll(raw, -1, axis=0) - raw, axis=1)
        s = np.r_[0., np.cumsum(lengths)]
        if s[-1] <= 0 or np.any(lengths <= 0):
            raise ValueError("Contour sampling requires a regular nondegenerate polygon.")
        n = count - global_count
        nodes = np.arange(n) * s[-1] / n
        closed = np.vstack((raw, raw[0]))
        anchors = np.column_stack([np.interp(nodes, s, closed[:, j]) for j in range(2)])
        x = torch.tensor(anchors, dtype=parameter.dtype, device=parameter.device, requires_grad=True)
        gradient = torch.autograd.grad(model(x).sum(), x)[0].detach().cpu().numpy()
        magnitude = np.linalg.norm(gradient, axis=1)
        if np.any(magnitude <= 0) or not np.all(np.isfinite(magnitude)):
            raise ValueError("Contour sampling encountered a zero or nonfinite field gradient.")
        # A seeded permutation spreads signed offsets around the contour.
        offsets = np.random.default_rng(config.random_seed).permutation(
            np.linspace(-config.contour_band_half_width_m, config.contour_band_half_width_m, n))
        band = anchors + offsets[:, None] * gradient / magnitude[:, None]
        values = np.vstack((values, band))
    return torch.tensor(values, dtype=parameter.dtype, device=parameter.device)
