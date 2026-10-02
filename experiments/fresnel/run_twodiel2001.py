#!/usr/bin/env python3
"""Two-circle measured-data inversion initialized by a Born correlation image.

This fixes the number and circular shape of the components. It does not test
the repository's topology controller or unconstrained two-boundary recovery.
"""
from __future__ import annotations
import json
from pathlib import Path
import time

if __package__:
    from .run_fresnel2001 import ROOT, plt, np, relative_error
else:
    from run_fresnel2001 import ROOT, plt, np, relative_error
from scipy.constants import epsilon_0, mu_0, c
from scipy.special import hankel1
from scipy.optimize import least_squares
from solvers.io.fresnel2001 import load_fresnel2001, calibrate_line_sources
from ordered_boundary import circle, OrderedBoundary2D
from gpr_bem_kress import Material
from gpr_bem_kress.multicomponent import solve_multicomponent_kress_tmz_total_field_batch


def correlation_image(data, calibration):
    axis = np.linspace(-0.08, 0.08, 129)
    xx, yy = np.meshgrid(axis, axis)
    points = np.column_stack((xx.ravel(), yy.ravel()))
    result = np.zeros(len(points))
    mask = np.zeros((36, 72))
    mask[np.arange(36)[:, None], data.receiver_labels - 1] = 1
    for fi in (1, 3, 5):
        wave = 2 * np.pi * data.frequencies_hz[fi] / c
        measured = np.zeros((36, 72), complex)
        measured[np.arange(36)[:, None], data.receiver_labels - 1] = data.scattered[fi]
        gs = 0.25j * hankel1(0, wave * np.linalg.norm(points[:, None] - data.source_points, axis=-1))
        gs *= calibration.source_strengths[fi]
        gr = 0.25j * hankel1(0, wave * np.linalg.norm(points[:, None] - data.receiver_points, axis=-1))
        correlation = np.sum(gs.conj() * (gr.conj() @ measured.T), axis=1)
        norm = np.sum(abs(gs)**2 * (abs(gr)**2 @ mask.T), axis=1)
        power = abs(correlation)**2 / norm
        result += power / power.max()
    first = points[np.argmax(result)]
    remaining = result.copy()
    remaining[np.linalg.norm(points - first, axis=1) < 0.05] = 0
    second = points[np.argmax(remaining)]
    return axis, result.reshape(xx.shape), np.array([first, second])


def boundary(parameters_mm, nodes):
    return OrderedBoundary2D(tuple(circle(tuple(parameters_mm[3 * j:3 * j + 2] * 1e-3),
        parameters_mm[3 * j + 2] * 1e-3, component_id=f"cylinder_{j}").discretize(nodes)
        for j in range(2)))


def predict(data, calibration, parameters, fi, nodes=64):
    base = solve_multicomponent_kress_tmz_total_field_batch(
        boundary(parameters, nodes), data.source_points, data.receiver_points,
        2 * np.pi * data.frequencies_hz[fi], source_strength=calibration.source_strengths[fi],
        exterior=Material(1), interior=Material(3), eps0=epsilon_0, mu0=mu_0)
    return data.select_receiver_pairs(base.scattered_receiver)


def run():
    start = time.time()
    out = ROOT / "results/fresnel/twodiel"
    out.mkdir(parents=True, exist_ok=True)
    data = load_fresnel2001(ROOT / "data/fresnel/twodielTM_8f.exp")
    calibration = calibrate_line_sources(data)
    axis, indicator, centers = correlation_image(data, calibration)
    parameters = np.column_stack((centers * 1000, [20, 20])).ravel()
    initial = parameters.copy()
    lo, hi = parameters.copy(), parameters.copy()
    for j in range(2):
        lo[3*j:3*j+2] -= 10
        hi[3*j:3*j+2] += 10
        lo[3*j+2], hi[3*j+2] = 8, 23
    report = {"data_sha256": data.source_sha256, "initial_parameters_mm": initial.tolist(),
              "model": "two circles, fixed epsr=3, full multiple-scattering Kress",
              "initialization": "normalized Born correlation power, 2/4/6 GHz; two peaks separated at least 50 mm",
              "coordinate_frame": "absolute table labels; source label 1 at +x",
              "nodes_per_circle": 64, "stages": [], "nominal_forward": []}
    for nominal in ([0,-45,15,0,45,15], [-45,0,15,45,0,15]):
        report["nominal_forward"].append({"parameters_mm": nominal,
            "relative_misfit": [relative_error(predict(data, calibration, np.array(nominal), fi), data.scattered[fi]) for fi in range(8)]})
    for stop in range(8):
        def residual(values):
            chunks = []
            for fi in range(stop + 1):
                delta = (predict(data, calibration, values, fi) - data.scattered[fi]).ravel()
                delta /= np.linalg.norm(data.scattered[fi]) * np.sqrt(stop + 1)
                chunks.extend((delta.real, delta.imag))
            return np.concatenate(chunks)
        fit = least_squares(residual, parameters, jac="3-point", diff_step=1e-4,
                            bounds=(lo, hi), x_scale="jac", max_nfev=30,
                            ftol=1e-7, xtol=1e-7, gtol=1e-7)
        parameters = fit.x
        row = {"maximum_frequency_ghz": stop + 1, "parameters_mm": parameters.tolist(),
               "relative_misfit": [relative_error(predict(data, calibration, parameters, fi), data.scattered[fi]) for fi in range(stop + 1)],
               "nfev": int(fit.nfev), "status": int(fit.status),
               "minimum_bound_distance_mm": float(np.min(np.minimum(parameters-lo,hi-parameters)))}
        report["stages"].append(row)
        print(json.dumps(row), flush=True)
        (out / "metrics.json").write_text(json.dumps(report, indent=2)+"\n")
    report["refinement_relative_prediction_change"] = [relative_error(
        predict(data, calibration, parameters, fi), predict(data, calibration, parameters, fi, 128)) for fi in range(8)]
    report["elapsed_seconds"] = time.time()-start
    (out / "metrics.json").write_text(json.dumps(report, indent=2)+"\n")
    np.savez_compressed(out / "reconstruction.npz", indicator=indicator, image_axis_m=axis,
                        initial_parameters_mm=initial, final_parameters_mm=parameters)
    fig, ax = plt.subplots(1, 2, figsize=(9, 4), constrained_layout=True)
    ax[0].imshow(indicator, origin="lower", extent=(-80,80,-80,80), cmap="inferno")
    for curve in boundary(parameters, 128).components:
        ax[0].plot(*curve.points.T*1000, "c-")
    ax[0].set(xlabel="x (mm)", ylabel="y (mm)", title="Born image and recovered circles")
    for row in report["nominal_forward"]:
        ax[1].plot(np.arange(1,9), row["relative_misfit"], "--", label=str(row["parameters_mm"]))
    ax[1].plot(np.arange(1,9), report["stages"][-1]["relative_misfit"], "ko-", label="Recovered")
    ax[1].set(xlabel="Frequency (GHz)", ylabel="Relative scattered-field error")
    ax[1].legend(fontsize=7)
    fig.savefig(out / "twodiel_summary.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    run()
