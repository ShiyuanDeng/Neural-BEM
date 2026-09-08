"""Bounded iteration-2 diagnostics; never an inverse optimizer.

Saved CSV weights own every frozen state. Truth geometry enters only scoring,
after residual-based directions have been computed. Field repair has no BEM
dependency and always returns the caller's weights to their original values.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field, replace
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import torch

from ordered_boundary import PeriodicParameterization2D
from sdf_to_ordered_boundary import FrontendConfig, ProjectionConfig, TorchImplicitField2D, prepare_single_component
from .geometry import OrderedSDFGeometryConfig, build_ordered_sdf_geometry
from .models import SirenImplicitField2D, build_siren_parameter_controller


class DiagnosticBudgetExceeded(RuntimeError):
    """A declared work limit was reached between atomic operations."""


@dataclass
class WorkBudget:
    max_evaluations: int = 120
    max_wall_seconds: float = 600.0
    evaluations: int = 0
    started: float = field(default_factory=perf_counter)
    operations: dict = field(default_factory=dict)
    partial_stage: object = None

    def check(self, operation=None, *, evaluation=False):
        if perf_counter() - self.started >= self.max_wall_seconds:
            raise DiagnosticBudgetExceeded("wall_time_cap")
        if evaluation and self.evaluations >= self.max_evaluations:
            raise DiagnosticBudgetExceeded("candidate_evaluation_cap")
        if evaluation:
            self.evaluations += 1
        if operation:
            self.operations[operation] = self.operations.get(operation, 0) + 1

    def report(self):
        return {"evaluations": self.evaluations, "wall_seconds": perf_counter() - self.started,
                "operations": dict(self.operations), "max_evaluations": self.max_evaluations,
                "max_wall_seconds": self.max_wall_seconds,
                "wall_cap_semantics": "checked between atomic calls; one call may overrun"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_hash(value):
    value = np.ascontiguousarray(value)
    return hashlib.sha256(str(value.shape).encode() + value.dtype.str.encode() + value.tobytes()).hexdigest()


def load_saved_case(run_dir):
    """Read real trajectory weights and immutable physical metadata.

    Do not infer weights from saved curves or repeat pretraining. Historical
    bundles store weights in raw_* CSV columns, not geometry_trajectory NPZ.
    """
    folder = Path(run_dir)
    checkpoint = torch.load(folder / "kress_model.pt", map_location="cpu", weights_only=True)
    constructor = dict(checkpoint["constructor"])
    constructor["dtype"] = torch.float64
    model = SirenImplicitField2D(**constructor)
    model.load_state_dict(checkpoint["state_dict"])
    controller = build_siren_parameter_controller(model)
    states, historical = {}, {}
    with (folder / "kress_trajectory.csv").open(newline="") as stream:
        reader = csv.DictReader(stream)
        columns = ["raw_" + name for name in controller.names]
        if not set(columns).issubset(reader.fieldnames):
            raise ValueError("Trajectory is missing actual named network-weight columns.")
        for row in reader:
            state = int(float(row["iteration"]))
            vector = np.array([float(row[name]) for name in columns])
            if not np.all(np.isfinite(vector)) or state in states:
                raise ValueError("Trajectory weights must be finite and state IDs unique.")
            states[state] = vector
            historical[state] = {key: row[key] for key in ("loss", "gradient_evaluated") if key in row}
    accepted_file = folder / "kress_accepted_iterates.json"
    if accepted_file.exists():
        for row in json.loads(accepted_file.read_text()):
            historical.setdefault(int(row["iteration"]), {}).update(row)
    trials_file = folder / "kress_trials.jsonl"
    trials = [json.loads(line) for line in trials_file.read_text().splitlines() if line.strip()] if trials_file.exists() else []
    metrics = json.loads((folder / "metrics.json").read_text())
    terminal = int(checkpoint["accepted_iteration"])
    if terminal in states and not np.array_equal(states[terminal], controller.parameter_vector()):
        raise ValueError("Terminal CSV weights do not exactly match the saved checkpoint.")
    sources = ["kress_model.pt", "kress_trajectory.csv", "kress_responses.npz", "metrics.json"]
    return {"folder": folder, "model": model, "controller": controller,
            "geometry": OrderedSDFGeometryConfig(**checkpoint["geometry_config"]),
            "optimizer": checkpoint["optimizer_config"], "checkpoint": checkpoint,
            "states": states, "historical": historical, "trials": trials, "metrics": metrics,
            "provenance": {name: sha256(folder / name) for name in sources}}


def saved_training_data(case):
    """Restore archived observations and physics, without regenerating truth."""
    from .forward import MaterialSpec, PairedForwardProblem
    from .optimization import ComplexScatteredData
    experiment = case["metrics"]["experiment"]
    frequencies = np.asarray(case["metrics"]["train_frequencies_ghz"])
    with np.load(case["folder"] / "kress_responses.npz", allow_pickle=False) as archive:
        all_frequencies = archive["frequencies_ghz"]
        columns = []
        for frequency in frequencies:
            matches = np.flatnonzero(np.isclose(all_frequencies, frequency, rtol=0, atol=1e-10))
            if len(matches) != 1:
                raise ValueError("Training frequency has no unique archived observation column.")
            columns.append(int(matches[0]))
        observed = archive["exact_scattered_response"][:, columns].copy()
    # September-8 checkpoints explicitly record this strength string; refuse
    # unsupported historical formats instead of using mutable config defaults.
    strength = experiment.get("source_strengths")
    if isinstance(strength, dict):
        strength = np.asarray(strength["real"]) + 1j * np.asarray(strength["imag"])
        if strength.ndim and len(strength) != len(frequencies):
            strength = strength[columns]
    elif experiment.get("source_strength") == "1e-6+0j at every frequency":
        strength = 1e-6 + 0j
    else:
        raise ValueError("No supported saved source-strength specification.")
    problem = PairedForwardProblem(
        source_points=experiment["source_points_m"], receiver_points=experiment["receiver_points_m"],
        angular_frequencies=2 * np.pi * frequencies * 1e9, source_strengths=strength,
        exterior=MaterialSpec(**experiment["exterior"]), interior=MaterialSpec(**experiment["interior"]),
        eps0=experiment.get("eps0_f_per_m", 8.8541878128e-12),
        mu0=experiment.get("mu0_h_per_m", 1.25663706212e-6))
    return ComplexScatteredData(problem, observed)


def historical_transition(case, state):
    trials = [row for row in case["trials"] if int(row["iteration"]) == state]
    accepted = next((row for row in trials if row.get("accepted")), None)
    preceding = None
    if accepted is not None:
        prior = [row for row in trials if row.get("method") == accepted.get("method")
                 and row.get("backtracks") == accepted.get("backtracks", 0) - 1]
        preceding = prior[-1] if prior else None
    return {"source": "historical saved trial log", "accepted_trial": accepted,
            "next_larger_rejected_trial": preceding,
            "binding_constraints": preceding.get("rejection_reasons", []) if preceding else None,
            "terminal_rejections": trials if accepted is None else None,
            "historical_adam_proposal": "unavailable; no moments/proposals reconstructed"}


def polygon_geometry(points):
    points = np.asarray(points)
    edge = np.roll(points, -1, axis=0) - points
    lengths = np.linalg.norm(edge, axis=1)
    if np.any(lengths == 0):
        raise ValueError("Polygon contains duplicate consecutive vertices.")
    perimeter = lengths.sum()
    weights = (lengths + np.roll(lengths, 1)) / (2 * perimeter)
    s = np.r_[0.0, np.cumsum(lengths[:-1])] / perimeter
    x, y = points.T
    cross = x * np.roll(y, -1) - y * np.roll(x, -1)
    center = np.array([np.sum((x + np.roll(x, -1)) * cross),
                       np.sum((y + np.roll(y, -1)) * cross)]) / (3 * cross.sum())
    return s, weights, float(perimeter), center


def normal_mode_basis(points, maximum_mode=20):
    """Discrete arc-weighted orthonormal trigonometric basis, <1,1>=1.

    Ordered weighted QR corrects quadrature nonorthogonality, preserving the
    nested spaces through each mode. The returned matrix records that change.
    """
    s, weights, _, _ = polygon_geometry(points)
    if 2 * maximum_mode + 1 >= len(points):
        raise ValueError("Contour needs more samples than modal degrees of freedom.")
    columns = [np.ones(len(points))]
    orders = [0]
    for mode in range(1, maximum_mode + 1):
        columns.extend([np.sqrt(2) * np.cos(2 * np.pi * mode * s),
                        np.sqrt(2) * np.sin(2 * np.pi * mode * s)])
        orders.extend([mode, mode])
    q, transform = np.linalg.qr(np.sqrt(weights)[:, None] * np.column_stack(columns))
    signs = np.where(np.diag(transform) < 0, -1.0, 1.0)
    return q * signs / np.sqrt(weights)[:, None], weights, np.asarray(orders)


def spectrum(values, points, maximum_mode=20, *, target_correction=None):
    basis, weights, orders = normal_mode_basis(points, maximum_mode)
    values = np.asarray(values)
    coefficients = basis.T @ (weights * values)
    residual = values - basis @ coefficients
    result = {"coefficients": coefficients, "orders": orders,
              "normalization": "arc-weighted QR of [1,sqrt(2)cos,sqrt(2)sin]; sum(weights)=1",
              "energy_0_5": float(np.sum(coefficients[orders <= 5] ** 2)),
              "energy_6_10": float(np.sum(coefficients[(orders >= 6) & (orders <= 10)] ** 2)),
              "energy_11_20": float(np.sum(coefficients[(orders >= 11) & (orders <= 20)] ** 2)),
              "unresolved_energy": float(weights @ residual ** 2),
              "rms": float(np.sqrt(weights @ values ** 2))}
    if target_correction is not None and np.all(np.isfinite(target_correction)):
        correction = basis.T @ (weights * target_correction)
        effects = {str(mode): float(np.sum(coefficients[orders == mode] * correction[orders == mode]))
                   for mode in np.unique(orders)}
        result.update(signed_effect_by_mode=effects,
                      signed_effect_definition="positive inner product removes current normal geometric error",
                      target_correction_coefficients=correction,
                      emphasized_star_modes={str(m): effects[str(m)] for m in (3, 4, 5, 6, 7, 9) if str(m) in effects})
    return result


def radial_spectrum(points, samples=512):
    _, _, perimeter, center = polygon_geometry(points)
    relative = np.asarray(points) - center
    angles = np.arctan2(relative[:, 1], relative[:, 0])
    radii = np.linalg.norm(relative, axis=1)
    increments = np.diff(np.unwrap(np.r_[angles, angles[0]]))
    single = bool(np.all(increments > 0) or np.all(increments < 0))
    result = {"center_m": center, "perimeter_m": perimeter, "polar_single_valued": single}
    if not single:
        result["radial_amplitudes_m"] = None
        return result
    grid = np.linspace(-np.pi, np.pi, samples, endpoint=False)
    values = np.interp(grid, angles, radii, period=2 * np.pi)
    coefficients = np.fft.rfft(values) / samples
    amplitudes = 2 * np.abs(coefficients)
    amplitudes[0] *= .5
    result.update(radial_amplitudes_m=amplitudes, radial_complex_coefficients=coefficients,
                  radial_rms_about_mean_m=float(np.std(values)))
    return result


def normal_correspondence(reference, normals, polygon):
    """Intersect each reference normal line with candidate segments.

    Select the nearest signed intersection; node numbering and parameter phase
    do not enter. Missing intersections are NaN and must not be interpreted.
    """
    return _polygon_normal_intersections(reference, normals, polygon)[0]


def _polygon_normal_intersections(reference, normals, polygon):
    reference, normals, polygon = map(np.asarray, (reference, normals, polygon))
    edge = np.roll(polygon, -1, axis=0) - polygon
    delta = polygon[None] - reference[:, None]
    cross = lambda a, b: a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]
    denominator = cross(normals[:, None], edge[None])
    valid = np.abs(denominator) > 1e-14 * np.linalg.norm(edge, axis=1)[None]
    with np.errstate(divide="ignore", invalid="ignore"):
        displacement = cross(delta, edge[None]) / denominator
        segment_fraction = cross(delta, normals[:, None]) / denominator
    valid &= (segment_fraction >= -1e-10) & (segment_fraction <= 1 + 1e-10)
    score = np.where(valid, np.abs(displacement), np.inf)
    indices = np.argmin(score, axis=1)
    answer = displacement[np.arange(len(reference)), indices]
    found = np.any(valid, axis=1)
    parameters = 2 * np.pi * (indices + segment_fraction[np.arange(len(reference)), indices]) / len(polygon)
    return np.where(found, answer, np.nan), np.where(found, parameters, np.nan)


def implicit_normal_correspondence(model, reference, normals, *, initial=None,
                                   tolerance_m=1e-12, maximum_iterations=12):
    """Local zero-field roots on fixed normal lines, without polygon bias.

    ``initial`` selects the local root when a normal line has several hits.
    Failed or nontransverse roots are NaN, never clipped or extrapolated.
    Re-extraction/topology checks remain the caller's responsibility.
    """
    reference, normals = map(np.asarray, (reference, normals))
    displacement = np.zeros(len(reference)) if initial is None else np.array(initial, dtype=float, copy=True)
    parameter = next(model.parameters())
    valid = np.isfinite(displacement)
    for _ in range(maximum_iterations + 1):
        positions = reference + np.where(valid, displacement, 0)[:, None] * normals
        points = torch.tensor(positions, dtype=parameter.dtype, device=parameter.device, requires_grad=True)
        values = model(points).reshape(-1)
        gradient = torch.autograd.grad(values.sum(), points)[0].detach().cpu().numpy()
        slope = np.einsum("ij,ij->i", gradient, normals)
        values = values.detach().cpu().numpy()
        valid &= np.isfinite(values) & np.isfinite(slope) & (np.abs(slope) > 1e-12 * np.linalg.norm(gradient, axis=1))
        step = np.divide(values, slope, out=np.zeros_like(values), where=valid)
        converged = valid & (np.abs(step) <= tolerance_m)
        if np.all(converged | ~valid):
            break
        displacement -= step
    return np.where(converged, displacement, np.nan)


def smooth_normal_correspondence(reference, normals, nodes, *, tolerance_m=1e-12,
                                 maximum_iterations=12):
    """Intersect fixed normals with the periodic interpolant of smooth nodes.

    Polygon hits initialize a local Newton solve only. Comparing polygon
    chords to a smooth normal velocity introduces an O(step) sampling error,
    even for an exactly translated circle.
    """
    reference, normals = map(np.asarray, (reference, normals))
    _, parameters = _polygon_normal_intersections(reference, normals, nodes)
    valid = np.isfinite(parameters)
    parameters = np.where(valid, parameters, 0)
    parameterization = interpolated_parameterization(nodes)
    tangent = np.column_stack((-normals[:, 1], normals[:, 0]))
    for _ in range(maximum_iterations + 1):
        evaluation = parameterization.evaluate(parameters)
        delta = evaluation.points - reference
        residual = np.einsum("ij,ij->i", delta, tangent)
        slope = np.einsum("ij,ij->i", evaluation.first_derivatives, tangent)
        valid &= np.isfinite(slope) & (np.abs(slope) > 1e-12 * np.linalg.norm(evaluation.first_derivatives, axis=1))
        converged = valid & (np.abs(residual) <= tolerance_m)
        if np.all(converged | ~valid):
            break
        parameters -= np.divide(residual, slope, out=np.zeros_like(residual), where=valid)
    displacement = np.einsum("ij,ij->i", delta, normals) / np.einsum("ij,ij->i", normals, normals)
    return np.where(converged, displacement, np.nan)


def nearest_target_normal_correction(reference, normals, target_points):
    """Normal projection of nearest target-segment displacement, for scoring.

    Its inner product with a normal velocity is minus the directional
    derivative of half the squared nearest-target distance (at unique nearest
    points). This is a post-direction score, not a normal-line intersection or
    a shape-update prescription.
    """
    reference, normals, target = map(np.asarray, (reference, normals, target_points))
    edge = np.roll(target, -1, axis=0) - target
    lengths2 = np.einsum("ij,ij->i", edge, edge)
    fraction = np.divide(np.einsum("nsi,si->ns", reference[:, None] - target[None], edge),
                         lengths2[None], out=np.zeros((len(reference), len(target))), where=lengths2[None] > 0)
    nearest = target[None] + np.clip(fraction, 0, 1)[..., None] * edge[None]
    difference = nearest - reference[:, None]
    indices = np.argmin(np.einsum("nsi,nsi->ns", difference, difference), axis=1)
    delta = difference[np.arange(len(reference)), indices]
    return np.einsum("ij,ij->i", delta, normals)


def field_quantities(model, points, direction=None):
    parameter = next(model.parameters())
    tensor = torch.tensor(np.array(points, copy=True), dtype=parameter.dtype, device=parameter.device, requires_grad=True)
    values = model(tensor).reshape(-1)
    gradient = torch.autograd.grad(values.sum(), tensor)[0].detach().cpu().numpy()
    norms = np.linalg.norm(gradient, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = {"G": norms, "inverse_G": 1 / norms, "normals": gradient / norms[:, None],
                  "field_values": values.detach().cpu().numpy()}
    if direction is not None:
        names, parameters = zip(*[(name, p) for name, p in model.named_parameters() if p.requires_grad])
        tangent, offset = [], 0
        for p in parameters:
            tangent.append(torch.as_tensor(direction[offset:offset + p.numel()], dtype=p.dtype, device=p.device).reshape_as(p))
            offset += p.numel()
        if offset != len(direction):
            raise ValueError("Weight direction does not match trainable parameter layout.")
        def evaluate(*parameters):
            return torch.func.functional_call(model, dict(zip(names, parameters)), (tensor.detach(),)).reshape(-1)
        _, numerator = torch.autograd.functional.jvp(evaluate, parameters, tuple(tangent))
        numerator = numerator.detach().cpu().numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            result.update(N=numerator, V=-numerator / norms)
    return result


def field_statistics(quantities, points):
    weights = polygon_geometry(points)[1]
    norms = quantities["G"]
    return {"minimum": float(norms.min()), "maximum": float(norms.max()),
            "rms": float(np.sqrt(weights @ norms ** 2)),
            "spread": float(norms.max() / norms.min()) if norms.min() > 0 else None,
            "zero_gradient_count": int(np.count_nonzero(norms == 0)),
            "gradient_values_are_unclipped": True}


def connected_tensor_jvp(output, parameters, direction):
    """JVP of an existing branch-local graph via reverse-over-reverse AD."""
    dual = torch.zeros_like(output, requires_grad=True)
    covectors = torch.autograd.grad((output * dual).sum(), parameters,
                                   create_graph=True, allow_unused=True, retain_graph=True)
    contraction = (dual * 0).sum()
    offset = 0
    for parameter, covector in zip(parameters, covectors):
        tangent = torch.as_tensor(direction[offset:offset + parameter.numel()],
                                  dtype=parameter.dtype, device=parameter.device).reshape_as(parameter)
        if covector is not None:
            contraction = contraction + (covector * tangent).sum()
        offset += parameter.numel()
    if offset != len(direction):
        raise ValueError("Direction differs from trainable tensor layout.")
    return torch.autograd.grad(contraction, dual, retain_graph=True)[0].detach().cpu().numpy()


def raw_contour(model, config, *, samples=None):
    parameter = next(model.parameters())
    implicit = TorchImplicitField2D(model, dtype=parameter.dtype, device=parameter.device,
                                    sign_convention="negative_inside")
    frontend = prepare_single_component(implicit, FrontendConfig(
        bounds=config.bounds, grid_shape=config.grid_shape,
        projected_samples=samples or max(512, config.projected_samples),
        projection=ProjectionConfig(residual_tolerance=1e-10)))
    component = frontend.single_component
    lo, hi = np.asarray(config.bounds)
    # Exact marching-cell signature detects local extraction branch changes;
    # equal signatures do not certify all subsequent projection branches.
    cells = np.floor((component.raw_contour - lo) / (hi - lo)
                     * (np.asarray(config.grid_shape)[::-1] - 1) + 1e-9).astype(np.int64)
    return component.projected_points.copy(), {
        "raw_marching_points": component.raw_contour,
        "marching_cell_hash": array_hash(cells), "marching_vertex_count": len(cells),
        "topology_single_component": frontend.num_components == 1,
        "projection_max_residual": component.projection_passes[-1].maximum_residual,
        "branch_check_scope": "marching-cell sequence; full projection/pullback branch consistency not certified"}


def interpolated_parameterization(nodes):
    """Periodic trigonometric interpolant, including the split even Nyquist."""
    nodes = np.asarray(nodes)
    count = len(nodes)
    coefficients = np.fft.fft(nodes, axis=0) / count
    modes = np.fft.fftfreq(count, d=1 / count)
    if count % 2 == 0:
        coefficients[count // 2] *= .5
        coefficients = np.vstack([coefficients, coefficients[count // 2]])
        modes = np.r_[modes, -modes[count // 2]]
    def evaluate(parameters):
        phase = np.exp(1j * np.outer(np.asarray(parameters).reshape(-1), modes))
        return tuple(((phase * (1j * modes)[None] ** order) @ coefficients).real for order in range(3))
    return PeriodicParameterization2D(component_id="frozen-diagnostic", evaluator=evaluate)


def report_geometry(model, config, budget, *, maximum_mode=20):
    """Measure fixed-limit conversion even when it is diagnostic-inadmissible."""
    from .geometry import measure_conversion_fidelity
    budget.check("geometry_characterization", evaluation=True)
    points, branch = raw_contour(model, config)
    # Disabling the throwing gate only exposes a diagnostic curve. The exact
    # unchanged limits are evaluated immediately below and remain in outputs.
    build = build_ordered_sdf_geometry(model, replace(config, conversion_tolerance_m=None))
    parameterization = interpolated_parameterization(build.curve.points)
    parameter = next(model.parameters())
    implicit = TorchImplicitField2D(model, dtype=parameter.dtype, device=parameter.device,
                                    sign_convention="negative_inside")
    fidelity = measure_conversion_fidelity(implicit, parameterization,
                                           replace(config, conversion_tolerance_m=2e-4))
    quantities = field_quantities(model, points)
    radial = np.linalg.norm(points - polygon_geometry(points)[3], axis=1)
    return {"evaluation_label": "fresh frozen-state evaluation", "raw_zero_contour_m": points,
            "method_b_boundary_m": build.curve.points, "branch": branch, "conversion": fidelity,
            "field_gradient": field_statistics(quantities, points), "G": quantities["G"],
            "raw_radial": radial_spectrum(points), "converted_radial": radial_spectrum(build.curve.points),
            "raw_arclength_radial_spectrum": spectrum(radial, points, maximum_mode)}, build, quantities


def residual_metric_directions(jacobian, residual, *, damping=1e-3, tsvd_cutoff=1e-3):
    """Data-only local directions. No geometric truth input is accepted."""
    jacobian, residual = np.asarray(jacobian), np.asarray(residual)
    u, singular, vt = np.linalg.svd(jacobian, full_matrices=False)
    if damping <= 0 or not 0 < tsvd_cutoff < 1:
        raise ValueError("Damping must be positive and TSVD relative cutoff between zero and one.")
    mu = damping * singular[0] ** 2 if len(singular) and singular[0] else damping
    projected = u.T @ residual
    retained = singular > tsvd_cutoff * singular[0] if len(singular) else np.zeros(0, bool)
    inverse = np.zeros_like(singular)
    inverse[retained] = 1 / singular[retained]
    return {"steepest_descent": -jacobian.T @ residual,
            "damped_gn": -vt.T @ ((singular / (singular ** 2 + mu)) * projected),
            "tsvd_gn": -vt.T @ (inverse * projected)}, {
                "singular_values": singular, "damping_relative": damping, "damping_mu": mu,
                "tsvd_relative_cutoff": tsvd_cutoff, "tsvd_retained_rank": int(retained.sum()),
                "direction_inputs": "normalized production training residual and curve Jacobian only"}


def first_order_window(alphas, errors, predicted_rms):
    alphas, errors = np.asarray(alphas), np.asarray(errors)
    valid = np.isfinite(errors) & (errors > 0)
    orders = []
    for i in range(len(alphas) - 1):
        orders.append(float(np.log(errors[i] / errors[i + 1]) / np.log(alphas[i] / alphas[i + 1]))
                      if valid[i] and valid[i + 1] and alphas[i] != alphas[i + 1] else None)
    windows = [i for i, order in enumerate(orders) if order is not None and order >= 1.3
               and errors[i + 1] <= .1 * alphas[i + 1] * predicted_rms]
    return {"displacement_error_orders": orders, "first_order_window_verified": bool(windows),
            "window_pairs": windows,
            "criterion": "error order >=1.3 and smaller-step relative displacement error <=0.1",
            "interpretation_allowed": bool(windows)}


def curve_metric_diagnostic(model, data, config, budget, *, maximum_mode=12,
                            fd_step_m=2e-5, damping=1e-3, tsvd_cutoff=1e-3,
                            maximum_step_m=2e-3, backtracks=4, target_points=None):
    """Resolved central-FD curve residual metric, with post-direction scoring."""
    from .forward import predict_paired_curve_response
    from .optimization import normalized_complex_residual
    budget.check("curve_metric_base_geometry", evaluation=True)
    base = build_ordered_sdf_geometry(model, config).curve
    basis, weights, orders = normal_mode_basis(base.points, maximum_mode)
    def residual(coefficients):
        budget.check("curve_metric_forward", evaluation=True)
        nodes = base.points + (basis @ coefficients)[:, None] * base.normals
        parameterization = interpolated_parameterization(nodes)
        # Check the whole explicit curve on a dense topology grid as well as
        # production nodes; no raw-to-Method-B fidelity notion exists here.
        from sdf_to_ordered_boundary.frontend import polygon_self_intersection_count
        dense = parameterization.discretize(max(config.validation_resolution, 4 * len(nodes))).points
        if polygon_self_intersection_count(dense):
            raise ValueError("Explicit diagnostic curve self-intersects on dense validation grid.")
        curve = parameterization.discretize(config.num_nodes, require_even=True)
        prediction = predict_paired_curve_response(curve, data.forward_problem, config, solver="kress")
        return normalized_complex_residual(prediction.scattered_response,
                                           data.observed_scattered_response, data.frequency_weights)[0], curve
    zero = np.zeros(basis.shape[1])
    r, _ = residual(zero)
    progress = {"evaluation_label": "fresh frozen-state evaluation", "status": "building_resolved_jacobian",
                "base_loss": .5 * float(r @ r), "completed_fd_columns": [], "maximum_mode": maximum_mode}
    budget.partial_stage = progress
    jacobians = []
    for epsilon in (fd_step_m, fd_step_m / 2):
        columns = []
        for index in range(len(zero)):
            step = zero.copy()
            step[index] = epsilon
            high, _ = residual(step)
            low, _ = residual(-step)
            columns.append((high - low) / (2 * epsilon))
            progress["completed_fd_columns"].append({"epsilon_m": epsilon, "column": index, "values": columns[-1]})
        jacobians.append(np.column_stack(columns))
    jacobian = jacobians[-1]
    difference = float(np.linalg.norm(jacobians[1] - jacobians[0]) / max(np.linalg.norm(jacobian), 1e-30))
    directions, metric = residual_metric_directions(jacobian, r, damping=damping, tsvd_cutoff=tsvd_cutoff)
    # Geometry truth is deliberately first touched after every direction exists.
    correction = normal_correspondence(base.points, base.normals, target_points) if target_points is not None else None
    nearest_correction = nearest_target_normal_correction(base.points, base.normals, target_points) if target_points is not None else None
    result = {"evaluation_label": "fresh frozen-state evaluation", "maximum_mode": maximum_mode,
              "basis_normalization": "arc-weighted orthonormal QR; mean-square normal motion=sum(c^2)",
              "basis": basis, "orders": orders, "arc_weights_normalized": weights,
              "residual_normalization": "production fixed observed-column norms, two unit frequency weights, no entry-count division",
              "base_loss": .5 * float(r @ r), "jacobian": jacobian,
              "fd_steps_m": [fd_step_m, fd_step_m / 2], "fd_relative_refinement_change": difference,
              "jacobian_resolved": difference <= .01, "metric": metric, "directions": {}}
    if correction is not None:
        result["target_normal_correspondence"] = {
            "missing_intersections": int(np.sum(~np.isfinite(correction))),
            "signed_normal_line_scores_interpretable": bool(np.all(np.isfinite(correction))),
            "supplementary_score": "nearest-target normal projection; positive inner product decreases half squared nearest-target distance at unique nearest points"}
    budget.partial_stage = result
    for name, direction in directions.items():
        motion = basis @ direction
        scale = min(1.0, maximum_step_m / max(float(np.max(np.abs(motion))), 1e-30))
        row = {"modal_direction": direction, "proposal_scale": scale,
               "motion_spectrum": spectrum(motion, base.points, min(20, (len(base.points) - 2) // 2), target_correction=correction),
               "linearized_loss": .5 * float(np.linalg.norm(r + jacobian @ (scale * direction)) ** 2),
               "trials": []}
        result["directions"][name] = row
        if correction is not None and np.all(np.isfinite(correction)):
            denominator = np.sqrt((weights @ motion ** 2) * (weights @ correction ** 2))
            row["signed_target_alignment"] = float(weights @ (motion * correction) / denominator) if denominator else None
        if nearest_correction is not None:
            score = spectrum(motion, base.points, min(20, (len(base.points) - 2) // 2), target_correction=nearest_correction)
            score["signed_effect_definition"] = result["target_normal_correspondence"]["supplementary_score"]
            row["nearest_target_distance_score"] = score
        for index in range(backtracks + 1):
            alpha = scale * .5 ** index
            trial = {"alpha": alpha, "admissible": False}
            try:
                candidate, curve = residual(alpha * direction)
                trial.update(loss=.5 * float(candidate @ candidate), admissible=True,
                             decreases_objective=bool(candidate @ candidate < r @ r),
                             actual_normal_motion_m=normal_correspondence(base.points, base.normals, curve.points))
            except DiagnosticBudgetExceeded:
                raise
            except ValueError as error:
                trial["geometry_error"] = f"{type(error).__name__}: {error}"
            row["trials"].append(trial)
        row["largest_decreasing_admissible_alpha"] = next((v["alpha"] for v in row["trials"] if v["admissible"] and v["decreases_objective"]), None)
        result["directions"][name] = row
    return result


def frozen_weight_directions(case, state, data, config, budget):
    """Fresh gradients plus genuine saved accepted transition/proposals."""
    from .forward import predict_paired_response
    from .implicit_adjoint import implicit_mlp_data_gradient, _eikonal, _flatten_gradient
    from .optimization import normalized_complex_residual
    model, controller = case["model"], case["controller"]
    budget.check("fresh_data_gradient", evaluation=True)
    forward = predict_paired_response(model, data.forward_problem, config, solver="kress", retain_kress_state=True)
    gradient, diagnostics = implicit_mlp_data_gradient(model, data, config, forward_result=forward)
    residual = normalized_complex_residual(forward.scattered_response, data.observed_scattered_response, data.frequency_weights)[0]
    optimizer = case["optimizer"]
    rng = np.random.default_rng(optimizer.get("random_seed", 0))
    bounds = np.asarray(config.bounds)
    samples = rng.uniform(bounds[0], bounds[1], (optimizer.get("regularization_samples", 512), 2))
    sample_source = "historical deterministic fixed uniform box sample rule"
    proposal_path = case["folder"] / f"kress_optimizer_{state:04d}.pt"
    saved = None
    if proposal_path.exists():
        # These explicitly selected, repository-produced local snapshots also
        # contain NumPy proposal arrays, which weights_only rejects in Torch 2.6.
        saved = torch.load(proposal_path, map_location="cpu", weights_only=False)
        saved_theta = np.asarray(saved["parameter_vector"])
        if not np.array_equal(saved_theta, controller.parameter_vector()):
            raise ValueError("Saved optimizer proposal belongs to different weights.")
        if "regularization_points" in saved:
            samples = np.asarray(saved["regularization_points"])
            sample_source = "actual saved optimizer sample set"
    elif optimizer.get("eikonal_sampling", "uniform") not in ("uniform", "uniform_box"):
        raise ValueError("Contour-aware state needs its saved regularization sample set for matched direction comparison.")
    parameters = tuple(p for p in model.parameters() if p.requires_grad)
    parameter = parameters[0]
    points = torch.tensor(samples, dtype=parameter.dtype, device=parameter.device)
    regularizer = optimizer.get("eikonal_weight", .01) * _eikonal(model, points, create_graph=True)
    weighted = _flatten_gradient(torch.autograd.grad(regularizer, parameters, allow_unused=True), parameters)
    total = gradient + weighted
    theta = controller.parameter_vector()
    fallback = controller.project(theta - total * (optimizer.get("learning_rate", .001) / max(np.max(np.abs(total)), 1.0))) - theta
    directions = {"negative_data_gradient": -gradient, "negative_weighted_eikonal_gradient": -weighted,
                  "negative_total_gradient": -total, "production_fallback": fallback}
    sources = {name: "fresh frozen-state evaluation" for name in directions}
    if state + 1 in case["states"]:
        directions["actual_accepted_delta_theta"] = case["states"][state + 1] - theta
        sources["actual_accepted_delta_theta"] = f"actual saved trajectory weights: state {state} -> {state + 1}"
    elif state - 1 in case["states"]:
        directions["last_incoming_accepted_delta_theta"] = theta - case["states"][state - 1]
        sources["last_incoming_accepted_delta_theta"] = (
            f"actual saved transition {state - 1} -> {state}; direction probed freshly at terminal state {state}, "
            "not a historical linearization of the incoming transition")
    if saved is not None:
        for name in ("raw_adam_proposal", "adam_proposal", "fallback_proposal"):
            if saved.get(name) is not None:
                directions["saved_" + name] = np.asarray(saved[name])
                sources["saved_" + name] = f"actual optimizer snapshot {proposal_path.name}, sha256={sha256(proposal_path)}"
    return directions, gradient, forward, {"data_gradient": diagnostics, "sources": sources,
        "base_loss": .5 * float(residual @ residual), "sample_hash": array_hash(samples),
        "sample_source": sample_source, "data_gradient_norm": float(np.linalg.norm(gradient)),
        "weighted_eikonal_gradient_norm": float(np.linalg.norm(weighted)),
        "historical_adam_available": saved is not None}


def neural_motion_diagnostic(case, state, data, config, budget, *, maximum_mode=20,
                             common_rms_m=1e-5, alphas=(1.0, .5, .25), target_points=None):
    from .forward import predict_paired_response
    from .optimization import normalized_complex_residual
    model, controller = case["model"], case["controller"]
    original = controller.parameter_vector().copy()
    directions, gradient, base_forward, info = frozen_weight_directions(case, state, data, config, budget)
    budget.check("neural_motion_raw_base")
    raw, branch = raw_contour(model, config)
    q = field_quantities(model, raw)
    converted = base_forward.geometry_build.curve
    weights = polygon_geometry(raw)[1]
    # Fixed-normal zero-field roots and the smooth converted interpolant avoid
    # the first-order tangential chord bias of re-extracted polygons. Subtract
    # baseline offsets to remove the extraction projection tolerance as well.
    raw_zero = implicit_normal_correspondence(model, raw, q["normals"])
    converted_zero = smooth_normal_correspondence(raw, q["normals"], converted.points)
    correction = normal_correspondence(raw, q["normals"], target_points) if target_points is not None else None
    nearest_correction = nearest_target_normal_correction(raw, q["normals"], target_points) if target_points is not None else None
    result = {"evaluation_label": "fresh frozen-state evaluation", "metadata": info,
              "raw_points_m": raw, "directions": {}, "alphas": alphas,
              "common_predicted_rms_motion_m": common_rms_m,
              "correspondence": "raw: local zero-field root on fixed normals; converted: periodic interpolant/normal intersection; independent extracted polygon motion retained",
              "raw_reference_projection_offsets_m": raw_zero}
    if correction is not None:
        result["target_normal_correspondence"] = {
            "missing_intersections": int(np.sum(~np.isfinite(correction))),
            "signed_normal_line_scores_interpretable": bool(np.all(np.isfinite(correction))),
            "supplementary_score": "nearest-target normal projection; positive inner product decreases half squared nearest-target distance at unique nearest points"}
    budget.partial_stage = result
    from .method_b_pullback import build_method_b_pullback
    parameters = tuple(p for p in model.parameters() if p.requires_grad)
    try:
        for name, direction in directions.items():
            budget.check("neural_direction_jvp")
            quantities = field_quantities(model, raw, direction)
            row = {"source": info["sources"][name], "actual_weight_direction": direction,
                   "actual_parameter_l2_scale": float(np.linalg.norm(direction)), "actual_scale": {}, "trials": []}
            result["directions"][name] = row
            for key in ("N", "G", "inverse_G", "V"):
                value = quantities[key]
                row["actual_scale"][key] = {"values": value, "spectrum": spectrum(value, raw, maximum_mode,
                    target_correction=correction if key == "V" else None)}
            if nearest_correction is not None:
                score = spectrum(quantities["V"], raw, maximum_mode, target_correction=nearest_correction)
                score["signed_effect_definition"] = result["target_normal_correspondence"]["supplementary_score"]
                row["nearest_target_distance_score"] = score
            rms = float(np.sqrt(weights @ quantities["V"] ** 2))
            if not np.isfinite(rms) or rms == 0:
                row["not_probed_reason"] = "nonfinite or zero predicted motion; low G was not clipped"
                result["directions"][name] = row
                continue
            common_scale = common_rms_m / rms
            scaled = direction * common_scale
            # Rebuild after preceding trial assignments, which increment Torch
            # parameter version counters even when the exact weights return.
            budget.check("discrete_method_b_motion_pullback")
            conversion = build_method_b_pullback(model, config, reference_curve=converted)
            row["method_b_pullback_replay_error_m"] = conversion.maximum_replay_error
            discrete_velocity = connected_tensor_jvp(conversion.points, parameters, scaled)
            discrete_normal_velocity = np.einsum("ij,ij->i", discrete_velocity, converted.normals)
            row.update(common_scale_factor=common_scale, common_N=quantities["N"] * common_scale,
                       common_V=quantities["V"] * common_scale,
                       full_pipeline_adjoint_derivative=float(gradient @ scaled),
                       discrete_method_b_velocity_m=discrete_velocity,
                       discrete_method_b_normal_velocity_m=discrete_normal_velocity)
            errors, valid_alphas = [], []
            for alpha in alphas:
                budget.check("neural_motion_trial", evaluation=True)
                trial = {"alpha": alpha}
                try:
                    controller.assign(original + alpha * scaled)
                    candidate_raw, candidate_branch = raw_contour(model, config)
                    predicted = alpha * common_scale * quantities["V"]
                    polygon_raw = normal_correspondence(raw, q["normals"], candidate_raw)
                    actual_raw = implicit_normal_correspondence(model, raw, q["normals"], initial=raw_zero + predicted) - raw_zero
                    error = float(np.sqrt(weights @ (actual_raw - predicted) ** 2))
                    trial.update(predicted_raw_motion_m=predicted, actual_raw_motion_m=actual_raw,
                                 actual_extracted_polygon_raw_motion_m=polygon_raw,
                                 missing_implicit_normal_roots=int(np.sum(~np.isfinite(actual_raw))),
                                 raw_prediction_rms_error_m=error,
                                 marching_branch_unchanged=branch["marching_cell_hash"] == candidate_branch["marching_cell_hash"],
                                 actual_raw_spectrum=spectrum(actual_raw, raw, maximum_mode, target_correction=correction))
                    errors.append(error)
                    valid_alphas.append(alpha)
                    # Fresh full-pipeline evaluation keeps every production
                    # geometry gate. Rejections are diagnostic measurements.
                    forward = predict_paired_response(model, data.forward_problem, config, solver="kress")
                    residual = normalized_complex_residual(forward.scattered_response, data.observed_scattered_response, data.frequency_weights)[0]
                    loss = .5 * float(residual @ residual)
                    actual_converted = smooth_normal_correspondence(raw, q["normals"], forward.geometry_build.curve.points) - converted_zero
                    converted_reference_motion = smooth_normal_correspondence(converted.points, converted.normals,
                                                                         forward.geometry_build.curve.points)
                    converted_weights = converted.arc_length_weights / converted.arc_length_weights.sum()
                    trial.update(actual_converted_motion_m=actual_converted, loss=loss,
                                 actual_converted_spectrum=spectrum(actual_converted, raw, maximum_mode, target_correction=correction),
                                 raw_to_converted_motion_rms_difference_m=float(np.sqrt(weights @ (actual_converted - actual_raw) ** 2)),
                                 full_pipeline_fd_derivative=(loss - info["base_loss"]) / alpha,
                                 discrete_method_b_prediction_rms_error_m=float(np.sqrt(converted_weights @ (
                                     converted_reference_motion - alpha * discrete_normal_velocity) ** 2)),
                                 derivative_absolute_error=abs((loss - info["base_loss"]) / alpha - gradient @ scaled),
                                 production_geometry_accepted=True)
                except DiagnosticBudgetExceeded:
                    raise
                except ValueError as error:
                    trial.update(error=f"{type(error).__name__}: {error}", production_geometry_accepted=False)
                finally:
                    controller.assign(original)
                row["trials"].append(trial)
            row["ift_validation"] = first_order_window(valid_alphas, errors, common_rms_m)
            result["directions"][name] = row
        result["weights_restored_exactly"] = np.array_equal(controller.parameter_vector(), original)
        return result
    finally:
        controller.assign(original)


def field_only_repair(model, controller, config, budget, *, steps=25, learning_rate=1e-5,
                      anchor_beta=1e8, samples=256, band_width_m=.005, maximum_mode=20):
    """Anchored near-interface Eikonal repair; never evaluates data or Kress."""
    if steps < 1 or steps > 200 or samples < 16 or anchor_beta <= 0 or learning_rate <= 0:
        raise ValueError("Repair requires 1..200 steps, >=16 samples and positive beta/lr.")
    original = controller.parameter_vector().copy()
    result = {"objective": "mean((norm(grad_x f)-1)^2) + beta*mean(f(frozen_contour)^2)",
              "data_evaluations": 0, "kress_evaluations": 0, "anchor_beta_per_m2": anchor_beta,
              "learning_rate": learning_rate, "requested_steps": steps, "history": []}
    budget.partial_stage = result
    try:
        before, _, before_q = report_geometry(model, config, budget, maximum_mode=maximum_mode)
        points = before["raw_zero_contour_m"]
        # Uniform arc-length anchor positions and deterministic interlaced offsets.
        from sdf_to_ordered_boundary.frontend import resample_closed_polygon
        anchors = resample_closed_polygon(points, samples)
        q = field_quantities(model, anchors)
        offsets = np.resize(np.linspace(-band_width_m, band_width_m, 9), samples)
        band = anchors + offsets[:, None] * q["normals"]
        parameter = next(model.parameters())
        anchors_t = torch.tensor(anchors, dtype=parameter.dtype, device=parameter.device)
        band_t = torch.tensor(band, dtype=parameter.dtype, device=parameter.device)
        from .implicit_adjoint import _eikonal
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        result.update(sample_hash=array_hash(band), anchor_hash=array_hash(anchors), before=before)
        for step in range(steps):
            budget.check("field_repair_step")
            optimizer.zero_grad(set_to_none=True)
            eikonal = _eikonal(model, band_t, create_graph=True)
            anchor = model(anchors_t).square().mean()
            objective = eikonal + anchor_beta * anchor
            if not torch.isfinite(objective):
                raise FloatingPointError("Nonfinite field-only repair objective.")
            objective.backward()
            optimizer.step()
            result["history"].append({"step": step, "band_eikonal": float(eikonal.detach()),
                                      "zero_anchor_m2": float(anchor.detach()), "objective": float(objective.detach())})
        after, _, _ = report_geometry(model, config, budget, maximum_mode=maximum_mode)
        motion = normal_correspondence(points, before_q["normals"], after["raw_zero_contour_m"])
        from .neural_optimization import maximum_curve_set_distance
        weights = polygon_geometry(points)[1]
        result.update(after=after, repaired_weights=controller.parameter_vector().copy(),
                      raw_maximum_set_movement_m=maximum_curve_set_distance(points, after["raw_zero_contour_m"]),
                      raw_rms_normal_movement_m=float(np.sqrt(weights @ motion ** 2)),
                      marching_branch_unchanged=before["branch"]["marching_cell_hash"] == after["branch"]["marching_cell_hash"],
                      converted_maximum_set_movement_m=maximum_curve_set_distance(
                          before["method_b_boundary_m"], after["method_b_boundary_m"]),
                      interpretation="Measure conditioning, conversion and movement jointly; no automatic promotion gate.")
        return result
    finally:
        controller.assign(original)
