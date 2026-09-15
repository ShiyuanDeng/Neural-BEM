"""Fixed-budget fitting controls for the opt-in Method-B failure study.

These controls share the production redistance loss, but deliberately omit
early stopping and best-state selection. They are not an inverse optimizer.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math

import numpy as np
import torch

from .continuous_distance import signed_distance_to_continuous_curve
from .neural import (
    NeuralRedistanceConfig, SmoothMLPSDF2D, _dense_arclength_boundary_samples,
    _quality_metrics, _redistance_objective,
)


@dataclass
class FitData:
    arrays: dict[str, np.ndarray]
    tensors: dict[str, torch.Tensor]
    length_scale: float
    target_diagnostics: dict


def prepare_fit_data(curve, config: NeuralRedistanceConfig, *, polygon_nodes=32):
    """Use historical sample locations with their actual smooth distances.

    This mirrors production's ``smooth_curve/legacy_polygon`` sampling. All
    branches share the resulting object; targets are constructed only once.
    """
    if config.distance_target != "smooth_curve" or config.smooth_boundary_sampling != "legacy_polygon":
        raise ValueError("This control requires smooth distances at shared legacy sample locations.")
    bounds = np.asarray(config.bounds)
    boundary, normals = _dense_arclength_boundary_samples(
        curve.discretize(polygon_nodes), config.boundary_oversampling_factor,
    )
    rng = np.random.default_rng(config.seed)
    samples = rng.uniform(*bounds, size=(config.sample_count, 2))
    heldout = rng.uniform(*bounds, size=(config.heldout_sample_count, 2))
    offsets = np.vstack((boundary + config.normal_offset_m * normals,
                         boundary - config.normal_offset_m * normals))
    u = np.linspace(0, 1, max(32, math.ceil(math.sqrt(config.sample_count))), endpoint=False)
    lo, hi = bounds
    box = np.vstack((
        np.column_stack((lo[0] + (hi[0]-lo[0])*u, np.full_like(u, lo[1]))),
        np.column_stack((np.full_like(u, hi[0]), lo[1] + (hi[1]-lo[1])*u)),
        np.column_stack((hi[0] - (hi[0]-lo[0])*u, np.full_like(u, hi[1]))),
        np.column_stack((np.full_like(u, lo[0]), hi[1] - (hi[1]-lo[1])*u)),
    ))
    groups = dict(sample=samples, offset=offsets, heldout=heldout, box=box, boundary=boundary)
    targets, diagnostics = signed_distance_to_continuous_curve(
        np.vstack(list(groups.values())), curve,
        tolerance_m=config.distance_target_tolerance_m,
        initial_samples=config.distance_initial_samples,
        maximum_samples=config.distance_maximum_samples, return_diagnostics=True,
    )
    split = np.split(targets, np.cumsum([len(x) for x in groups.values()])[:-1])
    arrays = {f"{key}_points": value.copy() for key, value in groups.items()}
    arrays.update({f"{key}_targets": value.copy() for key, value in zip(groups, split)})
    probe = curve.discretize(config.distance_maximum_samples).points
    if np.any(probe <= lo) or np.any(probe >= hi) or np.any(arrays["box_targets"] <= 0):
        raise ValueError("The smooth fitting target must remain strictly inside the bounds.")
    return FitData(arrays, {k: torch.tensor(v, dtype=torch.float64) for k, v in arrays.items()},
                   float(.5 * np.max(hi-lo)), diagnostics)


def fit_loss(model, data, config, weight, *, create_graph):
    t = data.tensors
    return _redistance_objective(
        model, t["sample_points"], t["sample_targets"], t["boundary_points"],
        t["offset_points"], t["offset_targets"], t["box_points"], t["box_targets"],
        boundary_targets=t["boundary_targets"], length_scale=data.length_scale,
        config=config, eikonal_weight=weight, create_graph=create_graph,
    )


def fit_metrics(model, data, config):
    """Independent gates; Eikonal is measured even in the zero-weight arm."""
    t = data.tensors
    train, boundary, eikonal, eikonal_max = _quality_metrics(
        model, t["sample_points"], t["sample_targets"], t["boundary_points"],
        boundary_targets=t["boundary_targets"],
    )
    heldout, _, heldout_eikonal, _ = _quality_metrics(
        model, t["heldout_points"], t["heldout_targets"], t["boundary_points"],
        boundary_targets=t["boundary_targets"],
    )
    components = {}
    with torch.no_grad():
        for key in ("sample", "boundary", "offset", "box"):
            residual = (model(t[f"{key}_points"]).reshape(-1)-t[f"{key}_targets"])/data.length_scale
            components[key] = float(torch.mean(residual.square()))
    components["eikonal"] = eikonal**2
    gates = dict(heldout_distance=heldout <= config.distance_rms_tolerance_m,
                 boundary_residual=boundary <= config.boundary_max_tolerance_m,
                 training_eikonal=eikonal <= config.eikonal_rms_tolerance)
    return dict(train_distance_rms_m=train, heldout_distance_rms_m=heldout,
                boundary_target_residual_max_m=boundary, eikonal_rms=eikonal,
                eikonal_max=eikonal_max, heldout_eikonal_rms=heldout_eikonal,
                unweighted_loss_components=components, gates=gates,
                combined_training_gate=all(gates.values()))


def fit_steps(model, optimizer, data, config, *, steps, weight):
    """Exactly ``steps`` Adam updates, retaining the last state and all losses."""
    if steps < 0 or not np.isfinite(weight) or weight < 0:
        raise ValueError("Invalid fixed fitting budget or Eikonal weight.")
    history = []
    was_training = model.training
    model.eval()
    try:
        for _ in range(steps):
            optimizer.zero_grad(set_to_none=True)
            loss = fit_loss(model, data, config, weight, create_graph=True)
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite fitting loss.")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10., error_if_nonfinite=True)
            optimizer.step()
            if any(not torch.isfinite(p).all() for p in model.parameters()):
                raise FloatingPointError("Nonfinite fitted model parameters.")
            history.append(float(loss.detach()))
    finally:
        model.train(was_training)
    return history


def checkpoint(model, optimizer):
    return dict(model=deepcopy(model.state_dict()), optimizer=deepcopy(optimizer.state_dict()))


def fork_checkpoint(model, state, *, learning_rate):
    """Clone both weights and Adam moments, with no tensor storage shared."""
    branch = deepcopy(model)
    branch.load_state_dict(deepcopy(state["model"]), strict=True)
    optimizer = torch.optim.Adam(branch.parameters(), lr=learning_rate)
    optimizer.load_state_dict(deepcopy(state["optimizer"]))
    return branch, optimizer


def model_from_metadata(metadata, arrays=None, *, prefix=None):
    geometry = metadata.get("geometric_initialization")
    model = SmoothMLPSDF2D(
        bounds=metadata["bounds"], hidden_features=metadata["hidden_features"],
        hidden_layers=metadata["hidden_layers"], fourier_frequencies=tuple(metadata["fourier_frequencies"]),
        geometric_center=None if geometry is None else tuple(geometry["center"]),
        geometric_radius=None if geometry is None else geometry["radius"],
        seed=metadata["seed"], dtype=torch.float64, device="cpu",
    )
    if arrays is not None:
        if prefix is None:
            raise ValueError("A frozen model prefix is required.")
        model.load_state_dict({key: torch.tensor(arrays[prefix+key], dtype=value.dtype)
                               for key, value in model.state_dict().items()}, strict=True)
    return model


def conversion_settings(grids, samples, bandwidths, arclengths):
    """One-factor sweeps sharing the most resolved anchor, with no duplicates."""
    anchor = (max(grids), max(samples), max(bandwidths), max(arclengths))
    rows = []
    seen = set()
    for axis, values in enumerate((grids, samples, bandwidths, arclengths)):
        for value in values:
            row = list(anchor)
            row[axis] = value
            row = tuple(row)
            if row not in seen:
                rows.append(row)
                seen.add(row)
    return rows


def transfer_comparison(*, start_objective, direct_objective, actual_objective,
                        no_op_objective, intended_motion_m, no_op_drift_m,
                        references_resolved, predicted_change):
    """Never call an unresolved or non-improving proposal a successful transfer."""
    margin = 1e-12 * max(start_objective, np.finfo(float).tiny)
    direct_descent = direct_objective < start_objective - margin
    actual_descent = actual_objective < start_objective - margin
    return dict(
        predicted_objective_change=predicted_change,
        direct_objective_change=direct_objective-start_objective,
        actual_objective_change=actual_objective-start_objective,
        actual_minus_no_op_objective_change=actual_objective-no_op_objective,
        no_op_drift_over_intended_motion=None if intended_motion_m == 0 else no_op_drift_m/intended_motion_m,
        direct_descent=direct_descent, actual_descent=actual_descent,
        transfer_descent_observed=bool(references_resolved and direct_descent and actual_descent),
        # This diagnostic is not sufficient to authorize an inverse acceptance.
        strict_inverse_acceptance_evaluated=False,
    )
