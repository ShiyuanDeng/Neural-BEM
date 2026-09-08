#!/usr/bin/env python3
"""Bounded physical/modal Kress observability study; no inverse geometry updates.

Native analytic star curves and normal arc-length probes are diagnostic shape
directions, not a replacement for the production MLP/Method-B ownership loop.
The frequency sweep runs only after the original-band derivative gates pass.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from time import perf_counter

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

import numpy as np
from scipy.interpolate import CubicSpline

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "solvers"))
from ordered_boundary import PeriodicParameterization2D, star
from gpr_bem_kress.shape_derivative import KressDirection, linearize_kress_forward
from sdf_inverse.forward import IndexedForwardProblem, predict_indexed_curve_response
from sdf_inverse.geometry import OrderedSDFGeometryConfig
from run_sdf_inverse_comparison import _build_problem, _ring_scan, StarTarget

RMS_M = 1e-3
PHYSICAL_NAMES = ("center_x", "center_y", "mean_radius", "amplitude", "rotation")
THRESHOLDS = (1e-2, 1e-3, 1e-4)


def rotate(v, clockwise=False):
    return np.stack((v[..., 1], -v[..., 0]), axis=-1) if clockwise else np.stack((-v[..., 1], v[..., 0]), axis=-1)


@dataclass
class Probe:
    name: str
    family: str
    native_unit: str
    evaluator: object
    rms_native: float = 1.0

    @property
    def scale(self):
        return RMS_M / self.rms_native


def star_probes(location, maximum_mode=10):
    """Coherent jets; normal modes are uniform in arc length, not polar angle."""
    center, radius, amplitude, angle = ((.48, .52), .06, .12, .25) if location == "initial" else ((.5, .5), .05, .25, 0.)
    producer = star(center, radius, amplitude, 5, rotation=angle)
    dense_t = np.linspace(0, 2*np.pi, 8192, endpoint=False)
    dense = producer.evaluate(dense_t)
    speed = np.linalg.norm(dense.first_derivatives, axis=1)
    normals = rotate(dense.first_derivatives / speed[:, None], clockwise=True)
    probes = []
    for axis, name in enumerate(PHYSICAL_NAMES[:2]):
        def translation(t, axis=axis):
            v = np.zeros(np.asarray(t).shape + (2,)); v[..., axis] = 1
            return v, np.zeros_like(v), np.zeros_like(v)
        probes.append(Probe(name, "physical", "m", translation))
    def radius_jets(t):
        v = producer.evaluate(t)
        return (v.points-center)/radius, v.first_derivatives/radius, v.second_derivatives/radius
    probes.append(Probe("mean_radius", "physical", "m", radius_jets))
    amp0 = star(center, radius, 0., 5, rotation=angle)
    amp1 = star(center, radius, .5, 5, rotation=angle)
    def amplitude_jets(t):
        a, b = amp0.evaluate(t), amp1.evaluate(t)
        return tuple(2*(getattr(b, k)-getattr(a, k)) for k in ("points", "first_derivatives", "second_derivatives"))
    probes.append(Probe("amplitude", "physical", "relative amplitude", amplitude_jets))
    def rotation_jets(t):
        v = producer.evaluate(t)
        return rotate(v.points-center), rotate(v.first_derivatives), rotate(v.second_derivatives)
    probes.append(Probe("rotation", "physical", "rad", rotation_jets))
    for probe in probes:
        normal_velocity = np.sum(probe.evaluator(dense_t)[0]*normals, axis=1)
        probe.rms_native = float(np.sqrt(np.sum(normal_velocity**2*speed)/np.sum(speed)))

    # Spectral primitive of speed; only its periodic part is interpolated.
    spectrum = np.fft.fft(speed)
    modes = np.fft.fftfreq(len(speed), 1/len(speed))
    primitive = np.zeros_like(spectrum)
    primitive[1:] = spectrum[1:] / (1j*modes[1:])
    periodic = np.fft.ifft(primitive).real
    spline = CubicSpline(np.r_[dense_t, 2*np.pi], np.r_[periodic, periodic[0]], bc_type="periodic")
    mean_speed = float(np.mean(speed)); length = 2*np.pi*mean_speed
    def modal_jets(t, mode, sine):
        values = producer.evaluate(t)
        x1, x2, x3 = values.first_derivatives, values.second_derivatives, values.third_derivatives
        q = np.linalg.norm(x1, axis=-1)
        q1 = np.sum(x1*x2, axis=-1)/q
        q2 = (np.sum(x2*x2+x1*x3, axis=-1)-q1*q1)/q
        n = rotate(x1/q[..., None], clockwise=True)
        n1 = rotate(x2/q[..., None]-x1*(q1/q**2)[..., None], clockwise=True)
        n2 = rotate(x3/q[..., None]-2*x2*(q1/q**2)[..., None]-x1*(q2/q**2)[..., None]+2*x1*(q1*q1/q**3)[..., None], clockwise=True)
        s = mean_speed*np.asarray(t)+spline(np.asarray(t) % (2*np.pi))-spline(0.)
        k = 2*np.pi*mode/length
        phase = k*s
        factor = np.sqrt(2.) if mode else 1.
        f = factor*(np.sin(phase) if sine else np.cos(phase))
        df_ds = factor*k*(np.cos(phase) if sine else -np.sin(phase))
        f1 = df_ds*q
        f2 = -k*k*f*q*q+df_ds*q1
        return f[..., None]*n, f1[..., None]*n+f[..., None]*n1, f2[..., None]*n+2*f1[..., None]*n1+f[..., None]*n2
    for mode in range(maximum_mode+1):
        for sine in ((False,) if mode == 0 else (False, True)):
            name = "mode_0" if mode == 0 else f"mode_{mode}_{'sin' if sine else 'cos'}"
            probes.append(Probe(name, "modal", "m RMS normal motion", lambda t, m=mode, s=sine: modal_jets(t, m, s)))
    return producer, probes


def perturbed_curve(producer, probe, step):
    def evaluate(t):
        base = producer.evaluate(t)
        velocity = probe.evaluator(t)
        return tuple(getattr(base, key)+step*probe.scale*v for key, v in zip(("points", "first_derivatives", "second_derivatives"), velocity))
    return PeriodicParameterization2D("star_probe", evaluate)


def relative(value, reference):
    return float(np.linalg.norm(value-reference)/max(np.linalg.norm(reference), 1e-30))


def real_stack(matrix):
    return np.concatenate((matrix.real, matrix.imag), axis=0)


def spectrum_metrics(matrix):
    real = real_stack(matrix)
    singular = np.linalg.svd(real, compute_uv=False)
    # Include structural null values when rows < columns.
    singular = np.pad(singular, (0, max(0, real.shape[1]-len(singular))))
    norms = np.linalg.norm(real, axis=0)
    correlation = (real.T @ real) / np.maximum(np.outer(norms, norms), 1e-300)
    return singular, correlation, {str(t): int(np.sum(singular > t*singular[0])) for t in THRESHOLDS}


def write_csv(path, rows):
    if rows:
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--num-nodes", type=int, default=256)
    parser.add_argument("--refined-nodes", type=int, default=512)
    parser.add_argument("--maximum-mode", type=int, default=10)
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args(argv)
    if args.num_nodes < 32 or args.num_nodes % 2 or args.refined_nodes <= args.num_nodes or args.refined_nodes % 2 or not 5 <= args.maximum_mode <= 10:
        parser.error("Use even nodes >=32, a larger even refinement, and maximum-mode 5..10.")
    out = args.output_dir
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"Refusing to replace result bundle {out}")
    out.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    commands = "env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 " + shlex.join([sys.executable, str(Path(__file__).name), *(sys.argv[1:] if argv is None else argv)])
    (out/"commands.txt").write_text(commands+"\n")
    source_files = [Path(__file__), ROOT/"solvers/sdf_inverse/forward.py", ROOT/"solvers/gpr_bem_kress/shape_derivative.py", ROOT/"solvers/ordered_boundary/analytic.py"]
    provenance = {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "utc": datetime.now(timezone.utc).isoformat(), "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}, "command": commands, "python": sys.version, "numpy": np.__version__}
    (out/"provenance.json").write_text(json.dumps(provenance, indent=2)+"\n")
    tables = {name: [] for name in ("physical_jacobian", "modal_jacobian", "singular_values", "column_correlations", "derivative_validation", "resolution_validation")}
    records = {}; spectra = []; work = {"forward_frequency_solves": 0, "jvp_frequency_solves": 0}
    def solve(producer, problem, nodes):
        config = OrderedSDFGeometryConfig(bounds=((.3,.3),(.7,.7)), num_nodes=nodes)
        result = predict_indexed_curve_response(producer.discretize(nodes, require_even=True), problem, config, retain_kress_state=True)
        work["forward_frequency_solves"] += len(problem.angular_frequencies)
        return result
    def flush():
        for name, rows in tables.items():
            write_csv(out/(name+".csv"), rows)
    def frequency_batch(frequencies, validate_fd):
        for location in ("initial", "target"):
            producer, probes = star_probes(location, args.maximum_mode)
            for count in (8, 12):
                sources, receivers = _ring_scan(center=(.5,.5), standoff=.3, num_pairs=count)
                paired = _build_problem(frequencies, sources, receivers)
                full = IndexedForwardProblem.from_paired(paired, multistatic=True)
                coarse, fine = (solve(producer, full, n) for n in (args.num_nodes, args.refined_nodes))
                derivatives = []
                for base, nodes in ((coarse, args.num_nodes), (fine, args.refined_nodes)):
                    native_columns = []
                    t = base.geometry_build.curve.parameters
                    for probe in probes:
                        jets = probe.evaluator(t)
                        direction = KressDirection(points=jets[0], first_derivatives=jets[1], second_derivatives=jets[2])
                        columns = [full.select_response(linearize_kress_forward(state, direction).d_scattered_receiver) for state in base.kress_states]
                        work["jvp_frequency_solves"] += len(columns)
                        native_columns.append(np.stack(columns, axis=1))
                    derivatives.append(np.stack(native_columns, axis=-1))
                coarse_j, fine_j = derivatives
                arms = [(f"paired-{count}", IndexedForwardProblem.from_paired(paired))]
                if count == 8:
                    arms.append(("multistatic-8", full))
                for arm, selection in arms:
                    indices = selection.source_indices*count+selection.receiver_indices
                    for f, frequency in enumerate(frequencies):
                        response = fine.scattered_response[indices, f]
                        j = fine_j[indices, f, :]
                        scaled = j*np.array([p.scale for p in probes])
                        records[(location, arm, frequency)] = (response, scaled, probes)
                        tables["resolution_validation"].append(dict(location=location, acquisition=arm, frequency_ghz=frequency, direction="forward", relative_change=relative(coarse.scattered_response[indices,f], response), threshold=1e-6))
                        for c, probe in enumerate(probes):
                            tables["resolution_validation"].append(dict(location=location, acquisition=arm, frequency_ghz=frequency, direction=probe.name, relative_change=relative(coarse_j[indices,f,c], j[:,c]), threshold=1e-4))
                            tables[probe.family+"_jacobian"].append(dict(location=location, acquisition=arm, frequency_ghz=frequency, direction=probe.name, native_unit=probe.native_unit, rms_normal_m_per_native_unit=probe.rms_native, native_increment_for_1mm_rms=probe.scale, native_complex_sensitivity_norm=float(np.linalg.norm(j[:,c])), sensitivity_norm_1mm=float(np.linalg.norm(scaled[:,c])), relative_sensitivity_1mm=float(np.linalg.norm(scaled[:,c])/np.linalg.norm(response))))
                if validate_fd:
                    names = {"center_x", "amplitude", "rotation", "mode_5_cos", "mode_5_sin", f"mode_{args.maximum_mode}_cos"}
                    for c, probe in enumerate(probes):
                        if probe.name not in names:
                            continue
                        for step in (.1, .03, .01):
                            minus = solve(perturbed_curve(producer, probe, -step), full, args.refined_nodes)
                            plus = solve(perturbed_curve(producer, probe, step), full, args.refined_nodes)
                            fd = (plus.scattered_response-minus.scattered_response)/(2*step)
                            for arm, selection in arms:
                                indices = selection.source_indices*count+selection.receiver_indices
                                for f, frequency in enumerate(frequencies):
                                    tables["derivative_validation"].append(dict(location=location, acquisition=arm, frequency_ghz=frequency, direction=probe.name, rms_perturbation_m=step*RMS_M, relative_error=relative(fd[indices,f], fine_j[indices,f,c]*probe.scale)))
                flush()
                print(f"Completed {location}, {count} sources, frequencies {frequencies}; elapsed {perf_counter()-started:.1f}s", flush=True)
    frequency_batch((.5, 1.5), True)
    baseline_resolved = all(row["relative_change"] < row["threshold"] for row in tables["resolution_validation"])
    fd_groups = {}
    for row in tables["derivative_validation"]:
        key = tuple(row[k] for k in ("location", "acquisition", "frequency_ghz", "direction"))
        fd_groups.setdefault(key, []).append(row)
    fd_pass = all(min(r["relative_error"] for r in group) < 1e-4 and sorted(group, key=lambda r:r["rms_perturbation_m"])[0]["relative_error"] < sorted(group, key=lambda r:r["rms_perturbation_m"])[-1]["relative_error"] for group in fd_groups.values())
    sweep_executed = baseline_resolved and fd_pass and not args.baseline_only
    if sweep_executed:
        frequency_batch((.25, 1., 2., 2.5), False)
    all_frequencies = sorted(set(key[2] for key in records))
    for family in ("physical", "modal"):
        for row in tables[family+"_jacobian"]:
            target_norm = np.linalg.norm(records[("target", row["acquisition"], row["frequency_ghz"])][0])
            row["relative_sensitivity_1mm"] = row["sensitivity_norm_1mm"] / float(target_norm)
    sets = [(f,) for f in all_frequencies]+[(.5,1.5)]
    if sweep_executed:
        sets += [(.5,2.5), (1.5,2.5), (.5,1.5,2.5), (.5,1.,1.5,2.,2.5)]
    # Fixed target-response normalization per arm/frequency; observations are
    # never selected or tuned using holdout. Also preserve absolute spectra.
    for location in ("initial", "target"):
        for arm in ("paired-8", "paired-12", "multistatic-8"):
            for frequencies in sets:
                probes = records[(location, arm, frequencies[0])][2]
                for family in ("physical", "modal"):
                    columns = [i for i,p in enumerate(probes) if p.family == family]
                    names = [probes[i].name for i in columns]
                    for weighting in ("absolute", "target_relative"):
                        matrices = []
                        for frequency in frequencies:
                            scale = np.linalg.norm(records[("target", arm, frequency)][0]) if weighting == "target_relative" else 1.
                            matrices.append(records[(location, arm, frequency)][1][:,columns]/scale)
                        matrix = np.concatenate(matrices, axis=0)
                        singular, correlation, ranks = spectrum_metrics(matrix)
                        metadata = dict(location=location, acquisition=arm, frequencies_ghz="+".join(map(str,frequencies)), family=family, weighting=weighting)
                        spectra.append(dict(**metadata, singular_values=singular.tolist(), effective_rank=ranks, real_rows=2*matrix.shape[0], columns=matrix.shape[1]))
                        for i, value in enumerate(singular):
                            tables["singular_values"].append(dict(**metadata, index=i, singular_value=float(value), relative_value=float(value/singular[0])))
                        for i, first in enumerate(names):
                            for j, second in enumerate(names):
                                tables["column_correlations"].append(dict(**metadata, direction_a=first, direction_b=second, correlation=float(correlation[i,j])))
    flush()
    resolved = all(row["relative_change"] < row["threshold"] for row in tables["resolution_validation"])
    metrics = dict(configuration=vars(args)|{"output_dir": str(out)}, baseline_resolution_pass=baseline_resolved, derivative_fd_pass=fd_pass, all_frequency_resolution_pass=resolved, frequency_sweep_executed=sweep_executed, frequencies_ghz=all_frequencies, holdout_frequencies_ghz=[3.], normalization={"geometry_rms_m": RMS_M, "data": "native complex fields and fixed per-frequency exact-target Kress response norm; frequency contributions summed", "noise_model": "none; relative spectra are conditioning diagnostics, not a statistical recovery certificate"}, spectra=spectra, work=work, wall_seconds=perf_counter()-started, stop_reason="completed_requested_diagnostics" if resolved and fd_pass else "derivative_or_resolution_gate_failed", rejection_reason_counts={})
    (out/"metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False)+"\n")
    np.savez_compressed(out/"jacobians.npz", **{f"{location}_{arm}_{frequency}": values[1] for (location,arm,frequency),values in records.items()})
    plot_results(out, tables, spectra)
    (out/"README.md").write_text(f"# Star acquisition observability\n\nCommit `{provenance['commit']}` with source hashes in provenance.json.\n\nExact analytic wrong initial star and target; Kress {args.num_nodes}/{args.refined_nodes} native-angle nodes. No Method-B conversion or MLP fit is used by these diagnostic probes. Production geometry remains unchanged. Physical columns and arc-length normal modes 0..{args.maximum_mode} use equal 1 mm RMS normal motion. Native derivatives retain their declared units.\n\nAcquisitions: paired-8 and paired-12 select source i/receiver i; multistatic-8 retains all 64 source-major entries using the same eight sources and receivers. Ring radius 0.3 m, receiver offset 0.06/0.3 rad, source strength 1e-6, original materials. Probe frequencies: {all_frequencies} GHz; reserved holdout: 3 GHz, unused here. No optimizer, accepted/rejected trial loop, or holdout tuning. Rejection counts: {{}}.\n\nBudget: one bounded baseline plus conditional six-frequency study at two shapes and two resolutions, central differences for six directions at three perturbation magnitudes in the original band. Actual work: {work}; wall time {metrics['wall_seconds']:.1f} s. Stop: `{metrics['stop_reason']}`.\n\nBaseline resolution pass: {baseline_resolved}; finite-difference convergence-window pass: {fd_pass}; sweep executed: {sweep_executed}; all-frequency resolution pass: {resolved}. Thresholds are recorded per row. Spectra include structural zero singular values and ranks at 1e-2, 1e-3, 1e-4. Absolute spectra preserve field units; target-relative spectra normalize each frequency by its exact-target prediction norm, matching equal relative frequency contributions.\n\nThis establishes local sensitivities and sampled-resolution stability for the declared diagnostic shape spaces, conditional on passing gates. It does not prove global nonlinear or neural recovery, a noise-dependent usable rank, or convergence of an MLP/Method-B representation. See the parent decision table before any long neural run.\n")
    print(json.dumps({k:v for k,v in metrics.items() if k not in ("spectra", "configuration")}, indent=2), flush=True)
    return 0 if resolved and fd_pass else 1


def plot_results(out, tables, spectra):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), constrained_layout=True)
    for row, location in enumerate(("initial", "target")):
        for col, (family, name) in enumerate((("physical", "amplitude"), ("physical", "rotation"), ("modal", "mode_5_cos"))):
            ax = axes[row,col]
            for arm in ("paired-8", "paired-12", "multistatic-8"):
                values = sorted([r for r in tables[family+"_jacobian"] if r["location"] == location and r["acquisition"] == arm and r["direction"] == name], key=lambda r:r["frequency_ghz"])
                ax.semilogy([r["frequency_ghz"] for r in values], [r["relative_sensitivity_1mm"] for r in values], "o-", label=arm)
            ax.set(title=f"{location}: {name}", xlabel="Frequency (GHz)", ylabel="Relative sensitivity / 1 mm RMS")
    axes[0,0].legend(); fig.savefig(out/"sensitivity.png", dpi=170); plt.close(fig)
    fig, axes = plt.subplots(2,2,figsize=(10,7), constrained_layout=True)
    for row, location in enumerate(("initial", "target")):
        for col, family in enumerate(("physical", "modal")):
            ax = axes[row,col]
            for record in spectra:
                if record["location"] == location and record["family"] == family and record["frequencies_ghz"] == "0.5+1.5" and record["weighting"] == "target_relative":
                    ax.semilogy(np.arange(1,len(record["singular_values"])+1), np.maximum(record["singular_values"],1e-16), "o-", label=record["acquisition"])
            ax.set(title=f"{location}: {family}", xlabel="Singular value index", ylabel="Singular value / 1 mm RMS")
    axes[0,0].legend(); fig.savefig(out/"singular_spectra.png", dpi=170); plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
