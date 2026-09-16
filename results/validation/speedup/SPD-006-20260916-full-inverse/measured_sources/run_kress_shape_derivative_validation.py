#!/usr/bin/env python3
"""Opt-in fixed-topology validation of the complete discrete Kress derivative.

Finite differences here are independent checks of the production forward;
they are not the derivative implementation. No inverse default is changed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "solvers"))

import numpy as np
import scipy

from gpr_bem_kress import KressSolveConfig, Material, solve_kress_tmz_total_field_batch
from ordered_boundary import fourier_curve
from sdf_to_ordered_boundary.artifacts import write_metrics_csv, write_npz, write_strict_json
from run_parameterization_aware_comparison import build_case

EPS0 = 8.8541878128e-12
MU0 = 1.25663706212e-6
PAIR_SOURCE = np.array([0, 1, 2, 0, 2, 0], dtype=int)
PAIR_RECEIVER = np.array([0, 2, 1, 3, 0, 0], dtype=int)
GEOMETRY_SCALE_M = 0.01


def _fresh_output(value):
    output = Path(value).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Validation output must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    return output


def _relative(first, second, *, floor=1e-30):
    return float(np.linalg.norm(first - second) / max(float(np.linalg.norm(second)), floor))


def _acquisition():
    source_angles = np.array([.1, 2.0, 4.4])
    receiver_angles = np.array([.4, 1.9, 3.7, 5.6])
    sources = .5 + .30 * np.column_stack((np.cos(source_angles), np.sin(source_angles)))
    receivers = .5 + .30 * np.column_stack((np.cos(receiver_angles), np.sin(receiver_angles)))
    strengths = 1e-6 * np.array([1 + .2j, -.7 + .4j, .3 - .8j])
    return sources, receivers, strengths


@dataclass(frozen=True)
class DirectionSpec:
    """A dimensionless scalar path and its exact coefficient derivative."""

    name: str
    cosine: np.ndarray
    sine: np.ndarray
    exterior_epsr: float = 0.0
    interior_epsr: float = 0.0
    phase_rate: float = 0.0


def _case_coefficients(name):
    source_name = "circle" if name == "zero_contrast" else name
    case = build_case(source_name)
    count = max(7, len(case.native.cosine_coefficients))
    cosine = np.zeros((count, 2))
    sine = np.zeros_like(cosine)
    cosine[:len(case.native.cosine_coefficients)] = case.native.cosine_coefficients
    sine[:len(case.native.sine_coefficients)] = case.native.sine_coefficients
    return cosine, sine, case.physical_parameters


def _directions(cosine, sine):
    def zeros():
        return np.zeros_like(cosine), np.zeros_like(sine)
    result = []
    for axis, name in enumerate(("translation_x", "translation_y")):
        dc, ds = zeros()
        dc[0, axis] = GEOMETRY_SCALE_M
        result.append(DirectionSpec(name, dc, ds))
    dc, ds = .2 * cosine.copy(), .2 * sine.copy()
    dc[0] = 0.0
    result.append(DirectionSpec("scale", dc, ds))
    dc, ds = zeros()
    dc[4, 0], ds[4, 1] = .004, .004
    result.append(DirectionSpec("shape_mode4", dc, ds))
    for name, exterior, interior in (("interior_epsr", 0., 1.), ("exterior_epsr", 1., 0.)):
        dc, ds = zeros()
        result.append(DirectionSpec(name, dc, ds, exterior, interior))
    dc, ds = zeros()
    dc[0] = [.003, -.002]
    dc[4, 0], ds[4, 1] = .002, .002
    result.append(DirectionSpec("mixed", dc, ds, .2, -.7))
    modes = np.arange(len(cosine))[:, None]
    result.append(DirectionSpec("tangential_phase", .3*modes*sine, -.3*modes*cosine,
                                phase_rate=.3))
    return tuple(result)


def _path(cosine, sine, direction, alpha):
    if direction.phase_rate:
        angles = np.arange(len(cosine))[:, None] * direction.phase_rate * alpha
        dc = cosine*np.cos(angles) + sine*np.sin(angles)
        ds = sine*np.cos(angles) - cosine*np.sin(angles)
    else:
        dc, ds = cosine + alpha*direction.cosine, sine + alpha*direction.sine
    return fourier_curve(dc, ds, component_id="frozen_derivative_case")


def _direction_jets(direction, parameters):
    # A velocity field need not itself be a regular closed curve. Evaluate its
    # Fourier series directly, without trying to validate it as a boundary.
    modes = np.arange(len(direction.cosine))
    phase = np.asarray(parameters)[:, None] * modes
    cosine, sine = np.cos(phase), np.sin(phase)
    dc, ds = direction.cosine, direction.sine
    return (
        cosine @ dc + sine @ ds,
        (-sine*modes) @ dc + (cosine*modes) @ ds,
        (-cosine*modes**2) @ dc + (-sine*modes**2) @ ds,
        (sine*modes**3) @ dc + (-cosine*modes**3) @ ds,
    )


def _core_direction(direction, curve):
    from gpr_bem_kress.shape_derivative import KressDirection
    return KressDirection(*_direction_jets(direction, curve.parameters),
                          exterior_epsr=direction.exterior_epsr,
                          interior_epsr=direction.interior_epsr)


def _solve(producer, num_nodes, frequencies, exterior_epsr, interior_epsr, acquisition,
           *, work):
    curve = producer.discretize(num_nodes, require_even=True)
    sources, receivers, strengths = acquisition
    results = []
    for omega in frequencies:
        work["production_forward_solves"] += 1
        results.append(solve_kress_tmz_total_field_batch(
            curve, sources, receivers, float(omega), strengths,
            exterior=Material(exterior_epsr), interior=Material(interior_epsr),
            eps0=EPS0, mu0=MU0, config=KressSolveConfig(),
        ))
    return tuple(results)


def _paired(forwards, observable="scattered"):
    return np.column_stack([getattr(value, observable + "_receiver")[PAIR_SOURCE, PAIR_RECEIVER]
                            for value in forwards])


def _branch_mask(forward):
    points = forward.system.geometry.points
    distances = np.linalg.norm(points[:, None] - points[None], axis=-1)
    threshold = forward.system.assembly_config.near_argument
    mask = max(abs(forward.system.k_exterior), abs(forward.system.k_interior))*distances <= threshold
    np.fill_diagonal(mask, False)
    return mask


def _transform(observed):
    # Fixed normalization depends on immutable data, never candidate parameters.
    norms = np.linalg.norm(observed, axis=0)
    reference = max(float(np.max(norms)), float(np.linalg.norm(observed))/np.sqrt(observed.shape[1]), 1.)
    scales = np.maximum(norms, 1e-12*reference)
    frequency_weights = np.linspace(.7, 1.3, observed.shape[1])
    diagonal = np.broadcast_to(np.sqrt(frequency_weights)/scales, observed.shape).ravel()
    transform = np.diag(np.r_[diagonal, diagonal])
    # Include real/imaginary mixing to test a general real weighting map.
    size = observed.size
    transform[0, size] = .15*diagonal[0]
    transform[size+1, 1] = -.1*diagonal[1]
    return transform


def _loss(predicted, observed, transform):
    residual = predicted - observed
    stacked = np.r_[residual.real.ravel(), residual.imag.ravel()]
    weighted = transform @ stacked
    return .5 * float(weighted @ weighted)


def _native_reference(producer, num_nodes, frequencies, exterior_epsr, interior_epsr,
                      acquisition, *, work):
    from nystrom_ref import build_curve, solve_transmission
    def evaluator(parameters):
        values = producer.evaluate(parameters)
        return values.points, values.first_derivatives
    native = build_curve(evaluator, num_nodes, "independent_derivative_reference")
    sources, receivers, strengths = acquisition
    columns = []
    for omega in frequencies:
        ke = float(omega)*np.sqrt(EPS0*MU0*exterior_epsr)
        ki = float(omega)*np.sqrt(EPS0*MU0*interior_epsr)
        work["nystrom_reference_solves"] += 1
        solution = solve_transmission(native, sources, receivers, complex(ke), complex(ki))
        columns.append((solution.scattered*strengths[:, None])[PAIR_SOURCE, PAIR_RECEIVER])
    return np.column_stack(columns)


def _mie_reference(producer, frequencies, exterior_epsr, interior_epsr, acquisition, *, work):
    import gpr_bem_ref
    from scipy.special import hankel1
    sources, receivers, strengths = acquisition
    evaluation = producer.evaluate(np.array([0., np.pi]))
    center = .5*(evaluation.points[0] + evaluation.points[1])
    radius = float(np.linalg.norm(evaluation.points[0] - center))
    columns = []
    for omega in frequencies:
        ke = float(omega)*np.sqrt(EPS0*MU0*exterior_epsr)
        ki = float(omega)*np.sqrt(EPS0*MU0*interior_epsr)
        work["mie_reference_evaluations"] += 1
        if int(np.ceil(3*max(abs(ke), abs(ki))*radius+40)) > 64:
            raise ValueError("Requested case exceeds this bounded driver's fixed Mie maximum_mode=64.")
        # Freeze the conservative mode range for every central-FD step.
        modes = np.arange(-64, 65)
        ratio = gpr_bem_ref.penetrable_cylinder_scattering_coefficient_ratio(modes, ke, ki, radius)
        source_delta, receiver_delta = sources[PAIR_SOURCE]-center, receivers[PAIR_RECEIVER]-center
        phase = np.arctan2(receiver_delta[:, 1], receiver_delta[:, 0]) - np.arctan2(source_delta[:, 1], source_delta[:, 0])
        unit = .25j*np.sum(
            hankel1(modes[None], ke*np.linalg.norm(source_delta, axis=1)[:, None])
            * hankel1(modes[None], ke*np.linalg.norm(receiver_delta, axis=1)[:, None])
            * ratio[None] * np.exp(1j*phase[:, None]*modes[None]), axis=1)
        columns.append(unit*strengths[PAIR_SOURCE])
    return np.column_stack(columns)


def _reference_case(name, producer, frequencies, exterior, interior, acquisition, work):
    if name in {"circle", "zero_contrast"}:
        response = _mie_reference(producer, frequencies, exterior, interior, acquisition, work=work)
        return response, dict(identity="independent_fixed_mode_Mie", maximum_mode=64,
                              self_convergence=None, final_nodes=None)
    history = []
    coarse = _native_reference(producer, 128, frequencies, exterior, interior, acquisition, work=work)
    for count in (256, 512):
        fine = _native_reference(producer, count, frequencies, exterior, interior, acquisition, work=work)
        error = _relative(coarse, fine)
        history.append(dict(coarse_nodes=count//2, fine_nodes=count, relative_difference=error))
        coarse = fine
        if error <= 1e-8:
            return fine, dict(identity="independent_nystrom_ref", self_convergence=history,
                              final_nodes=count, tolerance=1e-8)
    raise RuntimeError(f"Independent {name} field reference failed 1e-8 self-refinement: {history}")


def _reference_direction(name, cosine, sine, direction, frequencies, exterior, interior,
                         acquisition, work, *, reference_nodes):
    if direction.name == "tangential_phase":
        return np.zeros((len(PAIR_SOURCE), len(frequencies)), dtype=complex), dict(
            identity="exact_same_set_parameter_shift", note="Continuous fields do not depend on parameter phase; the finite-N derivative is not forced to zero.")
    if name == "zero_contrast":
        from sdf_inverse.cylinder_sensitivity_reference import matched_material_cylinder_epsr_jvp
        sources, receivers, strengths = acquisition
        result = np.column_stack([matched_material_cylinder_epsr_jvp(
            receivers[PAIR_RECEIVER], sources[PAIR_SOURCE], angular_frequency=float(omega),
            exterior_epsr=exterior, interior_epsr=interior,
            exterior_epsr_direction=direction.exterior_epsr,
            interior_epsr_direction=direction.interior_epsr,
            eps0=EPS0, mu0=MU0, radius=.05, center=(.5, .5),
            source_strength=strengths[PAIR_SOURCE], maximum_mode=64,
        ) for omega in frequencies])
        work["mie_analytic_direction_evaluations"] += len(frequencies)
        return result, dict(identity="analytic_Mie_matched_material_direction",
                            maximum_mode=64, note="Pure shape contribution is exactly zero in the continuous no-contrast problem.")
    mie = name == "circle" and direction.name not in {"shape_mode4", "mixed"}
    if not mie and direction.name not in {"translation_x", "shape_mode4", "interior_epsr"}:
        return None, dict(identity=None, reason="not_in_bounded_independent_direction_subset")
    histories, results = [], []
    step = 1e-4
    # Mie compares two step sizes; Nyström compares two independent node grids.
    nodes = (None, None) if mie else (max(128, reference_nodes//2), reference_nodes)
    for index, count in enumerate(nodes):
        h = step/(2**index) if mie else step
        predictions = []
        for sign in (-1., 1.):
            producer = _path(cosine, sine, direction, sign*h)
            arguments = (producer, frequencies, exterior+sign*h*direction.exterior_epsr,
                         interior+sign*h*direction.interior_epsr, acquisition)
            if mie:
                value = _mie_reference(*arguments, work=work)
            else:
                value = _native_reference(arguments[0], count, *arguments[1:], work=work)
            predictions.append(value)
        results.append((predictions[1]-predictions[0])/(2*h))
        histories.append(dict(step=h, num_nodes=count))
    discrepancy = _relative(results[0], results[1], floor=1e-18)
    return results[-1], dict(identity="independent_fixed_mode_Mie_FD" if mie else "independent_nystrom_FD",
                            refinement=histories, relative_refinement_difference=discrepancy,
                            maximum_mode=64 if mie else None,
                            note="Finite differences of a separately implemented oracle, not the derivative under test.")


def _fd_errors(jvps, minus, plus, step):
    mapping = {
        "system": ("d_system_matrix", lambda value: value.system.system_matrix),
        "rhs": ("d_right_hand_side", lambda value: value.right_hand_side),
        "receiver": ("d_receiver_matrix", lambda value: value.receiver_operator.state_rows),
        "solution": ("d_solution", lambda value: value.solution),
        "scattered": ("d_scattered_receiver", lambda value: value.scattered_receiver),
        "total": ("d_total_receiver", lambda value: value.total_receiver),
    }
    metrics = {}
    for label, (attribute, getter) in mapping.items():
        numerator = denominator = base_scale = 0.
        for tangent, negative, positive in zip(jvps, minus, plus):
            difference = (getter(positive)-getter(negative))/(2*step)
            exact = getattr(tangent, attribute)
            numerator += float(np.linalg.norm(difference-exact)**2)
            denominator += float(np.linalg.norm(exact)**2)
            physical_scale = float(np.linalg.norm(getter(positive)))
            if label in {"scattered", "total"}:
                # Scattering and its shape derivative can both vanish exactly
                # at matched materials. Their numerical absolute error must
                # use a nonvanishing physical field scale, not their zero norm.
                physical_scale = max(physical_scale, float(np.linalg.norm(positive.incident_receiver)))
            base_scale += physical_scale**2
        absolute_error, norm, scale = np.sqrt([numerator, denominator, base_scale])
        metrics[label+"_absolute_error"] = float(absolute_error)
        metrics[label+"_relative_error"] = float(absolute_error/max(norm, 1e-12*scale, 1e-30))
        metrics[label+"_mixed_ratio"] = float(absolute_error/(2e-5*norm + 1e-9*scale + 1e-25))
    return metrics


def _provenance():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    paths = [Path(__file__), ROOT/"run_parameterization_aware_comparison.py",
             ROOT/"docs/codex_sdf_kress_priorities_2026-09-05.md"]
    for package in ("gpr_bem_kress", "periodic_kress", "ordered_boundary",
                    "sdf_to_ordered_boundary", "sdf_inverse", "gpr_bem_ref", "nystrom_ref"):
        paths.extend(sorted((ROOT/"solvers"/package).glob("*.py")))
    return dict(commit=git("rev-parse", "HEAD"), dirty_status=git("status", "--short"),
                source_sha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths})


def _validation_exit_code(manifest):
    """A one-grid smoke checks discrete calculus, not physical convergence."""
    complete = manifest["discrete_gate_passed"] and (
        len(manifest["configuration"]["nodes"]) == 1 or manifest["physical_gate_passed"]
    )
    return 0 if complete else 2


def _write_summary(output, manifest):
    rows = manifest["derivative_records"]
    eligible = [row for row in rows if row["best_same_branch_fd_mixed_ratio"] is not None]
    failed = [row for row in eligible if not row["discrete_gate_passed"]]
    lines = ["# Complete discrete Kress derivative: bounded validation", "",
             "All finite differences call the unchanged production forward on perturbed continuous curves.",
             "Analytical JVPs and conjugate-adjoint contractions include A, RHS, receiver map and the direct incident term for total fields.", "",
             f"Discrete gate: {len(eligible)-len(failed)}/{len(rows)} case/node/direction records passed.",
             f"Finest-grid independent/reference-refinement gate: {manifest['physical_gate_passed']}.",
             "Physical derivative refinement and independent oracle checks are separate from that fixed-node gate.", "",
             "| Case | Direction | N | Best same-branch FD mixed ratio | Adjoint/JVP difference |",
             "|---|---|---:|---:|---:|"]
    for row in rows:
        if row["num_nodes"] != max(manifest["configuration"]["nodes"]):
            continue
        ratio = row["best_same_branch_fd_mixed_ratio"]
        ratio_text = "n/a" if ratio is None else f"{ratio:.3e}"
        lines.append(f"| {row['case']} | {row['direction']} | {row['num_nodes']} | {ratio_text} | {row['maximum_adjoint_jvp_absolute_difference']:.3e} |")
    lines += ["", f"Total wall time: {manifest['total_seconds']:.2f} s.",
              "The experiment differentiates a declared finite-dimensional, fixed-correspondence curve path; it does not return a uniquely determined arbitrary normal-gradient density.",
              "No production optimizer, topology policy, or quadrature default was changed."]
    (output/"summary.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def main(argv=None):
    from gpr_bem_kress.shape_derivative import (
        build_paired_objective_adjoint, linearize_kress_forward,
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", default=["circle", "ellipse", "star", "zero_contrast"],
                        choices=["circle", "ellipse", "star", "zero_contrast"])
    parser.add_argument("--nodes", nargs="+", type=int, default=[32, 64, 128])
    parser.add_argument("--frequencies-ghz", nargs="+", type=float, default=[.5, 1.5])
    parser.add_argument("--steps", nargs="+", type=float, default=[1e-2, 1e-3, 1e-4, 1e-5, 1e-6])
    options = parser.parse_args(argv)
    if (len(set(options.cases)) != len(options.cases)
            or len(set(options.nodes)) != len(options.nodes)
            or any(value < 16 or value % 2 for value in options.nodes)):
        parser.error("cases/nodes must be unique and node counts even and at least 16")
    if any(not np.isfinite(value) or value <= 0 for value in options.steps+options.frequencies_ghz):
        parser.error("steps and frequencies must be finite and positive")
    if (len(options.steps) < 2 or any(value > .01 for value in options.steps)
            or len(set(options.steps)) != len(options.steps)
            or options.steps != sorted(options.steps, reverse=True)):
        parser.error("use at least two distinct decreasing scaled FD steps, no larger than 0.01")
    nodes = sorted(options.nodes)
    output = _fresh_output(options.output_dir)
    started = perf_counter()
    frequencies = 2*np.pi*1e9*np.array(options.frequencies_ghz)
    acquisition = _acquisition()
    work = dict(production_forward_solves=0, nystrom_reference_solves=0,
                mie_reference_evaluations=0, mie_analytic_direction_evaluations=0,
                analytical_jvp_evaluations=0, adjoint_contexts=0,
                adjoint_direction_contractions=0)
    manifest = dict(schema="complete-discrete-kress-derivative-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        command=shlex.join([sys.executable, str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)]),
        provenance=_provenance(),
        environment={name: os.environ.get(name) for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "PYTHONPATH")},
        python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
        configuration=dict(cases=options.cases, nodes=nodes, steps=options.steps,
                           frequencies_ghz=options.frequencies_ghz, eps0=EPS0, mu0=MU0,
                           kress_config=asdict(KressSolveConfig()),
                           scaled_geometry_unit_m=GEOMETRY_SCALE_M,
                           derivative_relative_tolerance=2e-5,
                           derivative_absolute_tolerance="1e-9 times primal norm + 1e-25; receiver fields use max(primal,incident) norm",
                           objective_absolute_tolerance=1e-7,
                           adjoint_tolerance="1e-10*(1+abs(dJ))",
                           independent_field_reference_tolerance=1e-8,
                           independent_derivative_relative_tolerance=1e-5,
                           independent_derivative_absolute_tolerance="1e-8 times max(primal_scattered,incident) paired-field norm",
                           regularization="none; this validates the data objective"),
        acquisition=dict(source_points=acquisition[0].tolist(), receiver_points=acquisition[1].tolist(),
                         source_strengths_real=acquisition[2].real.tolist(),
                         source_strengths_imag=acquisition[2].imag.tolist(),
                         pair_source_indices=PAIR_SOURCE.tolist(), pair_receiver_indices=PAIR_RECEIVER.tolist(),
                         angular_frequencies=frequencies.tolist()),
        cases={}, derivative_records=[], fd_records=[], work=work,
        scope="single component, fixed topology/N/parameter correspondence/acquisition; full-space lossless nonmagnetic TMz")
    arrays = {}
    write_strict_json(output/"metrics.json", manifest)
    from scipy.special import hankel1
    sources, receivers, strengths = acquisition
    for case_index, name in enumerate(options.cases):
        cosine, sine, physical = _case_coefficients(name)
        producer = fourier_curve(cosine, sine, component_id="frozen_derivative_case")
        exterior, interior = 6., 6. if name == "zero_contrast" else 3.
        reference, reference_info = _reference_case(name, producer, frequencies, exterior, interior, acquisition, work)
        generator = np.random.default_rng(9071+case_index)
        noise_scale = .02*max(float(np.linalg.norm(reference))/np.sqrt(reference.size), 1e-8)
        noise = noise_scale*(generator.standard_normal(reference.shape)+1j*generator.standard_normal(reference.shape))/np.sqrt(2.)
        observed = reference + noise
        observed.setflags(write=False)
        observation_hash = hashlib.sha256(observed.tobytes()).hexdigest()
        incident = np.column_stack([
            strengths[PAIR_SOURCE]*.25j*hankel1(0, float(omega)*np.sqrt(EPS0*MU0*exterior)
                *np.linalg.norm(receivers[PAIR_RECEIVER]-sources[PAIR_SOURCE], axis=1))
            for omega in frequencies])
        observations = dict(scattered=observed, total=observed+incident)
        transforms = {observable: _transform(values) for observable, values in observations.items()}
        directions = _directions(cosine, sine)
        arrays[name+"_canonical_cosine"] = cosine
        arrays[name+"_canonical_sine"] = sine
        arrays[name+"_reference_scattered"] = reference
        arrays[name+"_observed_scattered"] = observed
        arrays[name+"_observed_total"] = observations["total"]
        arrays[name+"_complex_noise"] = noise
        for observable, transform in transforms.items():
            arrays[name+"_transform_"+observable] = transform
        case_record = dict(physical_geometry=physical, exterior_epsr=exterior, interior_epsr=interior,
                           observation_sha256=observation_hash, noise_seed=9071+case_index,
                           noise_complex_standard_deviation=noise_scale,
                           observation_policy="immutable independent reference plus seeded complex noise; total adds analytic incident field",
                           reference=reference_info, directions={}, forward_refinement=[],
                           derivative_refinement=[], independent_direction_checks=[])
        manifest["cases"][name] = case_record
        independent = {}
        for direction in directions:
            case_record["directions"][direction.name] = dict(
                cosine=direction.cosine.tolist(), sine=direction.sine.tolist(),
                exterior_epsr=direction.exterior_epsr, interior_epsr=direction.interior_epsr,
                phase_rate=direction.phase_rate)
            independent[direction.name] = _reference_direction(
                name, cosine, sine, direction, frequencies, exterior, interior, acquisition, work,
                reference_nodes=reference_info.get("final_nodes") or 256)
            if independent[direction.name][0] is not None:
                arrays[name+"_reference_jvp_"+direction.name] = independent[direction.name][0]
        previous_forward = None
        previous_jvps = {}
        for count in nodes:
            print(f"E validation: {name}, N={count}", flush=True)
            base = _solve(producer, count, frequencies, exterior, interior, acquisition, work=work)
            base_prediction = _paired(base)
            field_scale = max(float(np.linalg.norm(base_prediction)), float(np.linalg.norm(incident)), 1e-30)
            forward_row = dict(num_nodes=count,
                independent_relative_field_error=_relative(base_prediction, reference, floor=1e-18),
                independent_absolute_field_error=float(np.linalg.norm(base_prediction-reference)),
                independent_mixed_ratio=float(np.linalg.norm(base_prediction-reference)/(1e-6*np.linalg.norm(reference)+1e-9*field_scale)),
                previous_node_relative_difference=None if previous_forward is None else _relative(previous_forward, base_prediction, floor=1e-18),
                maximum_system_residual=max(value.linear_system_relative_residual for value in base))
            case_record["forward_refinement"].append(forward_row)
            previous_forward = base_prediction
            contexts = {}
            for observable in observations:
                work["adjoint_contexts"] += 1
                contexts[observable] = build_paired_objective_adjoint(
                    base, observations[observable], PAIR_SOURCE, PAIR_RECEIVER,
                    residual_transform=transforms[observable], observable=observable)
                np.testing.assert_allclose(contexts[observable].loss,
                    _loss(_paired(base, observable), observations[observable], transforms[observable]), rtol=1e-13, atol=1e-14)
            for direction in directions:
                record_started = perf_counter()
                tangent = _core_direction(direction, base[0].system.geometry)
                jvps = []
                for value in base:
                    work["analytical_jvp_evaluations"] += 1
                    jvps.append(linearize_kress_forward(value, tangent))
                paired_jvp = np.column_stack([value.d_scattered_receiver[PAIR_SOURCE, PAIR_RECEIVER] for value in jvps])
                arrays[f"{name}_{count}_{direction.name}_paired_jvp"] = paired_jvp
                gradients, adjoint_differences = {}, []
                for observable, context in contexts.items():
                    transform = transforms[observable]
                    delta = np.column_stack([getattr(value, "d_"+observable+"_receiver")[PAIR_SOURCE, PAIR_RECEIVER] for value in jvps])
                    residual = _paired(base, observable)-observations[observable]
                    weighted = transform @ np.r_[residual.real.ravel(), residual.imag.ravel()]
                    jvp_loss = float(weighted @ (transform @ np.r_[delta.real.ravel(), delta.imag.ravel()]))
                    work["adjoint_direction_contractions"] += 1
                    adjoint_loss = float(context.directional_derivative(tangent))
                    gradients[observable] = jvp_loss
                    adjoint_differences.append(abs(jvp_loss-adjoint_loss))
                step_records = []
                for step in options.steps:
                    minus, plus = [
                        _solve(_path(cosine, sine, direction, sign*step), count, frequencies,
                               exterior+sign*step*direction.exterior_epsr,
                               interior+sign*step*direction.interior_epsr, acquisition, work=work)
                        for sign in (-1., 1.)]
                    same_branch = all(np.array_equal(_branch_mask(value), _branch_mask(negative))
                                      and np.array_equal(_branch_mask(value), _branch_mask(positive))
                                      for value, negative, positive in zip(base, minus, plus))
                    row = dict(case=name, num_nodes=count, direction=direction.name,
                               step=step, same_near_direct_branch=same_branch,
                               **_fd_errors(jvps, minus, plus, step))
                    for observable in observations:
                        derivative = (_loss(_paired(plus, observable), observations[observable], transforms[observable])
                                      - _loss(_paired(minus, observable), observations[observable], transforms[observable]))/(2*step)
                        difference = abs(derivative-gradients[observable])
                        row[observable+"_objective_absolute_error"] = difference
                        row[observable+"_objective_mixed_ratio"] = difference/(1e-7+2e-5*abs(gradients[observable]))
                    row["maximum_mixed_ratio"] = max(value for key, value in row.items() if key.endswith("_mixed_ratio"))
                    manifest["fd_records"].append(row)
                    step_records.append(row)
                eligible = [row["maximum_mixed_ratio"] for row in step_records if row["same_near_direct_branch"]]
                best = min(eligible) if eligible else None
                adjoint_passes = all(error <= 1e-10*(1+abs(value)) for error, value in zip(adjoint_differences, gradients.values()))
                record = dict(case=name, num_nodes=count, direction=direction.name,
                    best_same_branch_fd_mixed_ratio=best,
                    same_branch_fd_step_count=len(eligible),
                    discrete_gate_passed=bool(best is not None and best <= 1 and adjoint_passes),
                    maximum_adjoint_jvp_absolute_difference=max(adjoint_differences),
                    scattered_objective_jvp=gradients["scattered"], total_objective_jvp=gradients["total"],
                    relative_physical_jvp_norm=float(np.linalg.norm(paired_jvp)/field_scale),
                    analytic_diagnostics=[dict(value.diagnostics) for value in jvps],
                    seconds=perf_counter()-record_started)
                errors = [row["scattered_absolute_error"] for row in step_records]
                record["fd_observed_orders"] = [float(np.log(errors[index]/errors[index+1])/np.log(options.steps[index]/options.steps[index+1]))
                    if errors[index] > 0 and errors[index+1] > 0 and options.steps[index] != options.steps[index+1] else None
                    for index in range(len(errors)-1)]
                manifest["derivative_records"].append(record)
                reference_jvp, information = independent[direction.name]
                if reference_jvp is not None:
                    case_record["independent_direction_checks"].append(dict(
                        direction=direction.name, num_nodes=count, oracle=information,
                        absolute_error=float(np.linalg.norm(paired_jvp-reference_jvp)),
                        relative_error=_relative(paired_jvp, reference_jvp, floor=1e-12*field_scale),
                        mixed_ratio=float(np.linalg.norm(paired_jvp-reference_jvp)/(1e-5*np.linalg.norm(reference_jvp)+1e-8*field_scale)),
                        oracle_refinement_passed=information.get("relative_refinement_difference", 0.) <= 1e-5,
                        primal_scaled_absolute_error=float(np.linalg.norm(paired_jvp-reference_jvp)/field_scale)))
                if direction.name in previous_jvps:
                    case_record["derivative_refinement"].append(dict(direction=direction.name,
                        coarse_num_nodes=previous_jvps[direction.name][0], fine_num_nodes=count,
                        relative_difference=_relative(previous_jvps[direction.name][1], paired_jvp, floor=1e-12*field_scale),
                        mixed_ratio=float(np.linalg.norm(previous_jvps[direction.name][1]-paired_jvp)/(1e-5*np.linalg.norm(paired_jvp)+1e-8*field_scale)),
                        primal_scaled_absolute_difference=float(np.linalg.norm(previous_jvps[direction.name][1]-paired_jvp)/field_scale)))
                previous_jvps[direction.name] = (count, paired_jvp)
                assert hashlib.sha256(observed.tobytes()).hexdigest() == observation_hash
            write_strict_json(output/"metrics.json", manifest)
            write_npz(output/"arrays.npz", **arrays)
    manifest["total_seconds"] = perf_counter()-started
    manifest["discrete_gate_passed"] = all(row["discrete_gate_passed"] for row in manifest["derivative_records"])
    physical_checks = []
    for name, case in manifest["cases"].items():
        independent = [row for row in case["independent_direction_checks"] if row["num_nodes"] == nodes[-1]]
        refinement = [row for row in case["derivative_refinement"]
                      if row["fine_num_nodes"] == nodes[-1] and row["direction"] != "tangential_phase"]
        phase = [row for row in manifest["derivative_records"] if row["case"] == name and row["direction"] == "tangential_phase"]
        phase_passed = phase[-1]["relative_physical_jvp_norm"] <= 1e-8 and (
            len(phase) >= 2 and (phase[-2]["relative_physical_jvp_norm"] <= 1e-8
                                or phase[-1]["relative_physical_jvp_norm"] <= .1*phase[-2]["relative_physical_jvp_norm"]))
        case["physical_gate_passed"] = bool(
            len(nodes) >= 2 and independent and refinement and phase_passed
            and case["forward_refinement"][-1]["independent_mixed_ratio"] <= 1.
            and all(row["mixed_ratio"] <= 1. and row["oracle_refinement_passed"] for row in independent)
            and all(row["mixed_ratio"] <= 1. for row in refinement))
        case["phase_invariance_gate_passed"] = phase_passed
        physical_checks.append(case["physical_gate_passed"])
    manifest["physical_gate_passed"] = all(physical_checks)
    manifest["task_e_gate_passed"] = manifest["discrete_gate_passed"] and manifest["physical_gate_passed"]
    write_strict_json(output/"metrics.json", manifest)
    write_metrics_csv(output/"finite_differences.csv", manifest["fd_records"])
    write_metrics_csv(output/"derivatives.csv", manifest["derivative_records"])
    write_npz(output/"arrays.npz", **arrays)
    _write_summary(output, manifest)
    print(f"E artifacts: {output}; discrete gate={manifest['discrete_gate_passed']}; physical gate={manifest['physical_gate_passed']}", flush=True)
    return _validation_exit_code(manifest)


if __name__ == "__main__":
    raise SystemExit(main())
