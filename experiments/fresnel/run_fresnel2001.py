#!/usr/bin/env python3
"""CPU Kress forward audit and Cartesian Fourier continuation on Fresnel 2001.

The raw-label coordinate system is kept throughout, including when it disagrees
with a published target drawing. Source gains use incident measurements only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[variable] = "1"

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "solvers"):
    sys.path.insert(0, str(path))

import numpy as np
from scipy.constants import epsilon_0, mu_0
from scipy.optimize import least_squares
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path as PolygonPath

from solvers.io.fresnel2001 import load_fresnel2001, calibrate_line_sources
from gpr_bem_kress import Material, solve_kress_tmz_total_field_batch
from gpr_bem_kress.shape_derivative import KressDirection, linearize_kress_forward
from ordered_boundary import circle, fourier_curve


def coefficient_slots(mode):
    return [("cos", 0, d) for d in range(2)] + [
        (kind, m, d) for m in range(1, mode + 1)
        for kind in ("cos", "sin") for d in range(2)]


def curve_from_parameters(parameters_mm, mode, nodes):
    cosine = np.zeros((mode + 1, 2))
    sine = np.zeros_like(cosine)
    for value, (kind, m, d) in zip(parameters_mm, coefficient_slots(mode)):
        (cosine if kind == "cos" else sine)[m, d] = value * 1e-3
    return fourier_curve(cosine, sine, component_id="fresnel_reconstruction").discretize(nodes)


def coefficient_directions(curve, mode):
    theta = curve.parameters
    directions = []
    for kind, m, d in coefficient_slots(mode):
        points = np.zeros_like(curve.points)
        first = np.zeros_like(points)
        if kind == "cos":
            points[:, d] = np.cos(m * theta) * 1e-3
            first[:, d] = -m * np.sin(m * theta) * 1e-3
        else:
            points[:, d] = np.sin(m * theta) * 1e-3
            first[:, d] = m * np.cos(m * theta) * 1e-3
        directions.append(KressDirection(points=points, first_derivatives=first))
    return directions


def forward(data, calibration, curve, frequency_index, epsr=3.0):
    return solve_kress_tmz_total_field_batch(
        curve, data.source_points, data.receiver_points,
        2 * np.pi * data.frequencies_hz[frequency_index],
        source_strength=calibration.source_strengths[frequency_index],
        exterior=Material(1.0), interior=Material(epsr), eps0=epsilon_0, mu0=mu_0)


def relative_error(predicted, measured):
    return float(np.linalg.norm(predicted - measured) / np.linalg.norm(measured))


def geometry_metrics(curve, reference_center=(-0.03, 0.0)):
    p = curve.points
    q = np.roll(p, -1, axis=0)
    cross = p[:, 0] * q[:, 1] - q[:, 0] * p[:, 1]
    area = 0.5 * cross.sum()
    centroid = np.sum((p + q) * cross[:, None], axis=0) / (6 * area)
    radius = np.sqrt(area / np.pi)
    axis = np.linspace(-0.07, 0.07, 561)
    xx, yy = np.meshgrid(axis, axis)
    pixels = np.column_stack((xx.ravel(), yy.ravel()))
    found = PolygonPath(p).contains_points(pixels)
    nominal = np.linalg.norm(pixels - reference_center, axis=1) <= 0.015
    # Orientation-independent shape diagnostic, explicitly not location IoU.
    centered = np.linalg.norm(pixels - centroid, axis=1) <= 0.015
    return {
        "centroid_mm": (centroid * 1000).tolist(),
        "equivalent_radius_mm": float(radius * 1000),
        "radius_error_vs_15mm_mm": float(abs(radius * 1000 - 15)),
        "centre_error_vs_requested_minus30_0_mm": float(np.linalg.norm(centroid - reference_center) * 1000),
        "offset_magnitude_error_vs_30mm_mm": float(abs(np.linalg.norm(centroid) * 1000 - 30)),
        "iou_vs_requested_minus30_0": float(np.sum(found & nominal) / np.sum(found | nominal)),
        "iou_vs_15mm_circle_at_recovered_centroid": float(np.sum(found & centered) / np.sum(found | centered)),
        "minimum_speed_m": float(np.min(curve.speeds)),
    }


class ContinuationObjective:
    def __init__(self, data, calibration, indices, mode, nodes, regularization):
        self.data, self.calibration, self.indices = data, calibration, indices
        self.mode, self.nodes = mode, nodes
        self.reg = np.array([regularization * m * m / 15 if m >= 2 else 0
                             for _, m, _ in coefficient_slots(mode)])
        self.cached = None
        self.evaluations = 0

    def evaluate(self, parameters):
        if self.cached is not None and np.array_equal(parameters, self.cached[0]):
            return self.cached
        curve = curve_from_parameters(parameters, self.mode, self.nodes)
        directions = coefficient_directions(curve, self.mode)
        residuals, jacobians, errors = [], [], []
        for fi in self.indices:
            base = forward(self.data, self.calibration, curve, fi)
            measured = self.data.scattered[fi]
            pred = self.data.select_receiver_pairs(base.scattered_receiver)
            norm = np.linalg.norm(measured) * np.sqrt(len(self.indices))
            residual = (pred - measured).ravel() / norm
            columns = [self.data.select_receiver_pairs(
                linearize_kress_forward(base, direction).d_scattered_receiver).ravel() / norm
                for direction in directions]
            jac = np.column_stack(columns)
            residuals.extend((residual.real, residual.imag))
            jacobians.extend((jac.real, jac.imag))
            errors.append(relative_error(pred, measured))
        residuals.append(self.reg * parameters)
        jacobians.append(np.diag(self.reg))
        self.evaluations += 1
        self.cached = (parameters.copy(), np.concatenate(residuals), np.vstack(jacobians), errors)
        return self.cached

    def fun(self, parameters):
        return self.evaluate(parameters)[1]

    def jac(self, parameters):
        return self.evaluate(parameters)[2]


def run(args):
    start = time.time()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    data = load_fresnel2001(args.data)
    calibration = calibrate_line_sources(data)
    requested = (-0.03, 0)
    orientation_centers = [requested, (0.03, 0), (0, -0.03), (0, 0.03)]
    report = {
        "data_file": str(args.data), "data_sha256": data.source_sha256,
        "data_source": "public teaching mirror; original publisher bytes not independently authenticated",
        "frequencies_ghz": (data.frequencies_hz / 1e9).tolist(),
        "shape": list(data.total.shape), "header_lines": len(data.header),
        "source_radius_m": 0.72, "receiver_radius_m": 0.76,
        "coordinate_frame": "source label 1 at +x, source label increases counterclockwise; receiver labels absolute",
        "calibration": "incident-only opposite-receiver complex line-source gain per frequency/transmitter",
        "incident_full_aperture_relative_error": calibration.relative_incident_error.tolist(),
        "nominal_radius_mm": 15, "fixed_epsr": 3,
        "forward_orientation_audit": [], "stages": [],
        "nodes": args.nodes, "cartesian_maximum_mode": args.mode,
        "regularization": args.regularization,
    }
    for center in orientation_centers:
        curve = circle(center, 0.015).discretize(args.nodes)
        errors = []
        for fi in range(len(data.frequencies_hz)):
            base = forward(data, calibration, curve, fi)
            errors.append(relative_error(data.select_receiver_pairs(base.scattered_receiver), data.scattered[fi]))
        report["forward_orientation_audit"].append({"center_mm": [v * 1000 for v in center], "relative_misfit": errors})
    slots = coefficient_slots(args.mode)
    parameters = np.zeros(len(slots))
    lo, hi = np.full(len(slots), -1.0), np.full(len(slots), 1.0)
    for j, (kind, m, d) in enumerate(slots):
        if m == 0:
            lo[j], hi[j] = -60, 60
        elif (kind, m, d) in [("cos", 1, 0), ("sin", 1, 1)]:
            parameters[j], lo[j], hi[j] = 25, 8, 40
        elif m == 1:
            lo[j], hi[j] = -4, 4
    initial = curve_from_parameters(parameters, args.mode, args.nodes)
    curves = [initial.points]
    for stop in range(len(data.frequencies_hz)):
        objective = ContinuationObjective(data, calibration, list(range(stop + 1)), args.mode, args.nodes, args.regularization)
        fit = least_squares(objective.fun, parameters, jac=objective.jac, bounds=(lo, hi),
                            x_scale="jac", max_nfev=args.max_nfev, ftol=1e-7, xtol=1e-7, gtol=1e-7)
        parameters = fit.x
        curve = curve_from_parameters(parameters, args.mode, args.nodes)
        metrics = geometry_metrics(curve)
        metrics.update(stage_maximum_ghz=float(data.frequencies_hz[stop] / 1e9),
                       relative_misfit_by_frequency=objective.evaluate(parameters)[3],
                       least_squares_status=int(fit.status), least_squares_message=fit.message,
                       nfev=int(fit.nfev), coefficient_parameters_mm=parameters.tolist(),
                       coefficients_at_bounds=[slots[i] for i in np.flatnonzero(np.isclose(parameters, lo, atol=1e-3) | np.isclose(parameters, hi, atol=1e-3))])
        report["stages"].append(metrics)
        curves.append(curve.points)
        print(json.dumps(metrics), flush=True)
        (out / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    # A doubled node count must change predictions much less than measured residuals.
    refined = curve_from_parameters(parameters, args.mode, 2 * args.nodes)
    convergence, predictions = [], []
    for fi in range(len(data.frequencies_hz)):
        coarse = data.select_receiver_pairs(forward(data, calibration, curve, fi).scattered_receiver)
        fine = data.select_receiver_pairs(forward(data, calibration, refined, fi).scattered_receiver)
        convergence.append(relative_error(coarse, fine))
        predictions.append(fine)
    report["refinement_relative_prediction_change"] = convergence
    report["elapsed_seconds"] = time.time() - start
    report["coefficient_slots"] = slots
    (out / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    np.savez_compressed(out / "reconstruction.npz", curves_m=curves, parameters_mm=parameters,
                        measured_scattered=data.scattered, predicted_scattered=predictions,
                        source_strengths=calibration.source_strengths,
                        frequencies_hz=data.frequencies_hz)
    fig, ax = plt.subplots(1, 3, figsize=(13, 4), constrained_layout=True)
    ax[0].plot(*initial.points.T * 1000, "k--", label="Initial 25 mm circle")
    for j in (1, 4, 8):
        ax[0].plot(*np.asarray(curves[j]).T * 1000, label=f"Through {j} GHz")
    nominal = circle(requested, 0.015).discretize(128)
    ax[0].plot(*nominal.points.T * 1000, ":", color="gray", label="Prompt nominal centre")
    ax[0].set(xlabel="x (mm)", ylabel="y (mm)", title="Raw-label coordinates", aspect="equal")
    ax[0].legend(fontsize=7)
    fghz = data.frequencies_hz / 1e9
    for row in report["forward_orientation_audit"]:
        ax[1].plot(fghz, row["relative_misfit"], "--", label=f"15 mm circle {row['center_mm']}")
    ax[1].plot(fghz, report["stages"][-1]["relative_misfit_by_frequency"], "ko-", label="Recovered K=2 boundary")
    ax[1].set(xlabel="Frequency (GHz)", ylabel="Relative scattered-field error", title="Measured data comparison")
    ax[1].legend(fontsize=6)
    ax[2].plot(np.arange(60, 301, 5), abs(data.incident[3, 0]), label="Measured")
    ax[2].plot(np.arange(60, 301, 5), abs(calibration.predicted_incident[3, 0]), label="Calibrated line source")
    ax[2].set(xlabel="Receiver angle relative to source (degrees)", ylabel="Incident amplitude", title="4 GHz antenna-model mismatch")
    ax[2].legend(fontsize=8)
    fig.savefig(out / "fresnel_summary.png", dpi=170)
    plt.close(fig)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/fresnel/dielTM_dec8f.exp")
    parser.add_argument("--output", type=Path, default=ROOT / "results/fresnel")
    parser.add_argument("--nodes", type=int, default=64)
    parser.add_argument("--mode", type=int, choices=(1, 2), default=2)
    parser.add_argument("--max-nfev", type=int, default=35)
    parser.add_argument("--regularization", type=float, default=0.1)
    arguments = parser.parse_args()
    run(arguments)
