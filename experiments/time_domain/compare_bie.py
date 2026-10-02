"""Synthesize Kress frequency responses and compare absolute gprMax waveforms."""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "solvers"), str(ROOT)]

import numpy as np
from scipy.special import hankel1
from scipy.signal import correlate, correlation_lags
from scipy.interpolate import CubicSpline
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ordered_boundary import circle
from gpr_bem_kress.polarization import solve_polarized_transmission
from experiments.polarization.run_validation import circle_series, relative_error


def positive_transform(values, dt, frequencies, time_offset=0):
    values = np.asarray(values)
    times = np.arange(len(values)) * dt + time_offset
    return dt * (np.exp(2j * np.pi * frequencies[:, None] * times[None, :]) @ values)


def synthesize(spectrum_plus, frequency_step, nfft=32768):
    """Positive-transform convention, physical units; zero-pad high frequencies."""
    if not np.isfinite(frequency_step) or frequency_step <= 0 or len(spectrum_plus) < 2:
        raise ValueError("Require at least two frequency bins and a finite positive spacing.")
    if nfft < 2 * (len(spectrum_plus) - 1):
        raise ValueError("nfft must resolve every input frequency.")
    dt = 1 / (nfft * frequency_step)
    signal = np.fft.irfft(np.conj(spectrum_plus), n=nfft, axis=0) / dt
    return np.arange(nfft) * dt, signal


def trace_metrics(predicted, measured, dt):
    rows = []
    for receiver in range(predicted.shape[1]):
        a, b = predicted[:, receiver], measured[:, receiver]
        scale = np.linalg.norm(a) * np.linalg.norm(b)
        correlations = correlate(b, a, mode="full", method="fft") / scale
        lags = correlation_lags(len(b), len(a), mode="full")
        peak = np.argmax(correlations)
        rows.append(dict(receiver=receiver,
            correlation_zero_lag=float(a @ b / scale),
            correlation_best_lag=float(correlations[peak]),
            best_lag_ps=float(lags[peak] * dt * 1e12),
            absolute_peak_time_error_ps=float(abs(np.argmax(abs(a)) - np.argmax(abs(b))) * dt * 1e12),
            relative_l2=float(np.linalg.norm(a - b) / np.linalg.norm(a)),
            peak_amplitude_ratio=float(np.max(abs(b)) / np.max(abs(a)))))
    return rows


def end_taper(times, width=2e-9):
    """Fixed cosine taper of the last 2 ns, shared by both numerical methods."""
    if width <= 0 or width >= times[-1]:
        raise ValueError("Taper width must be positive and shorter than the record.")
    start = times[-1] - width
    phase = np.clip((times - start) / width, 0, 1)
    return .5 * (1 + np.cos(np.pi * phase))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/time_domain")
    parser.add_argument("--nodes", type=int, default=128)
    parser.add_argument("--frequencies", type=int, default=512)
    parser.add_argument("--maximum-frequency", type=float, default=3e9)
    parser.add_argument("--reuse-bie-response", action="store_true",
                        help="Reuse an existing response only when its recorded inputs match.")
    args = parser.parse_args()
    if args.nodes < 8 or args.nodes % 2 or args.frequencies < 2 or not np.isfinite(args.maximum_frequency) or args.maximum_frequency <= 0:
        parser.error("Use even nodes >=8, at least two frequencies, and a finite positive maximum frequency.")
    paths = sorted(args.output.glob("fdtd_dx*mm.npz"), key=lambda p: -float(np.load(p)["cell_size"]))
    if not paths:
        raise FileNotFoundError("Run run_fdtd.py with the gprMax interpreter first.")
    finest = np.load(paths[-1])
    sources, receivers = finest["source"], finest["receivers"]
    properties = json.loads(paths[-1].with_suffix(".json").read_text())
    if properties["gprmax_version"] != "3.1.7":
        raise ValueError("The half-step source normalization is qualified for gprMax3.1.7 only.")
    eps0, mu0 = properties["eps0"], properties["mu0"]
    frequencies = np.linspace(0, args.maximum_frequency, args.frequencies)
    waves = 2 * np.pi * frequencies * np.sqrt(eps0 * mu0)
    curve = circle((.4, .4), .1).discretize(args.nodes)
    field = np.zeros((len(frequencies), len(receivers)), complex)
    incident = field.copy()
    cached_path = args.output / "bie_frequency_response.npz"
    if args.reuse_bie_response:
        cached = np.load(cached_path)
        for name, values in (("frequencies", frequencies), ("source", sources), ("receivers", receivers),
                             ("nodes", args.nodes), ("eps0", eps0), ("mu0", mu0)):
            if name not in cached or not np.array_equal(cached[name], values):
                raise ValueError(f"Cached BIE response has different or unverified {name}.")
        field, incident, bie_seconds = cached["scattered"], cached["incident"], float(cached["build_seconds"])
    else:
        started = time.perf_counter()
        for index in range(1, len(frequencies)):
            field[index] = solve_polarized_transmission(curve, sources, receivers, waves[index],
                2 * waves[index]).scattered_receiver[0]
            incident[index] = .25j * hankel1(0, waves[index] * np.linalg.norm(receivers - sources[0], axis=1))
        bie_seconds = time.perf_counter() - started
    series_checks = []
    for index in np.linspace(1, len(frequencies) - 1, 5, dtype=int):
        reference = circle_series(.1, sources - .4, receivers - .4, waves[index], 2 * waves[index])[0]
        series_checks.append(dict(frequency_hz=float(frequencies[index]), relative_l2=relative_error(field[index], reference)))
    np.savez_compressed(args.output / "bie_frequency_response.npz", frequencies=frequencies,
        scattered=field, incident=incident, source=sources, receivers=receivers,
        nodes=args.nodes, eps0=eps0, mu0=mu0, build_seconds=bie_seconds)
    all_rows = []
    saved_traces = {}
    df = frequencies[1]
    for path in paths:
        data = np.load(path)
        dt = float(data["dt"])
        # gprMax 3.1.7 samples current at n*dt but uses it over E_n -> E_(n+1).
        current = positive_transform(data["source_current"], dt, frequencies, time_offset=dt / 2)
        strength = 2j * np.pi * frequencies * mu0 * current
        expected_spectrum = strength[:, None] * field
        expected_background = strength[:, None] * incident
        times, predicted = synthesize(expected_spectrum, df)
        _, bg_predicted = synthesize(expected_background, df)
        raw_times = np.arange(len(data["scattered"])) * dt
        window = end_taper(raw_times)
        predicted_on_fdtd_grid = CubicSpline(times, predicted)(raw_times)
        background_on_fdtd_grid = CubicSpline(times, bg_predicted)(raw_times)
        # Match the finite temporal observation on both arms before filtering.
        # Otherwise the still-nonzero coda is cut off in only the FDTD arm,
        # and its artificial edge contributes broadband ringing to the metric.
        expected_spectrum = positive_transform(predicted_on_fdtd_grid * window[:, None], dt, frequencies)
        expected_background = positive_transform(background_on_fdtd_grid * window[:, None], dt, frequencies)
        measured_spectrum = positive_transform(data["scattered"] * window[:, None], dt, frequencies)
        measured_background = positive_transform(data["background"] * window[:, None], dt, frequencies)
        times, predicted = synthesize(expected_spectrum, df)
        _, measured = synthesize(measured_spectrum, df)
        _, bg_predicted = synthesize(expected_background, df)
        _, bg_measured = synthesize(measured_background, df)
        # Both arms receive exactly the same 0..3 GHz band limitation.
        mask = times <= (len(data["scattered"]) - 1) * dt
        times = times[mask]
        predicted, measured = predicted[mask], measured[mask]
        metrics = trace_metrics(predicted, measured, times[1])
        row = dict(cell_size_m=float(data["cell_size"]), dt_fdtd=dt,
            shared_taper_start_ns=float(raw_times[-1] * 1e9 - 2), shared_taper_width_ns=2,
            scattered_relative_l2=relative_error(measured, predicted),
            background_relative_l2=relative_error(bg_measured[mask], bg_predicted[mask]),
            min_zero_lag_correlation=min(r["correlation_zero_lag"] for r in metrics),
            min_best_lag_correlation=min(r["correlation_best_lag"] for r in metrics),
            max_abs_peak_time_error_ps=max(r["absolute_peak_time_error_ps"] for r in metrics),
            median_abs_peak_time_error_ps=float(np.median([r["absolute_peak_time_error_ps"] for r in metrics])),
            receivers=metrics)
        all_rows.append(row)
        saved_traces[path.stem + "_predicted"] = predicted
        saved_traces[path.stem + "_measured"] = measured
        saved_traces[path.stem + "_times"] = times
    np.savez_compressed(args.output / "trace_comparison.npz", **saved_traces)
    report = dict(source="1 A Ricker line current, f0=1GHz, t0=sqrt(2)/f0; no fitted amplitude/phase/time calibration",
        fourier_convention="F_plus=integral f(t) exp(+i omega t) dt; irfft(conj(F_plus))/dt",
        observation_window="Both arms use the same finite record and a fixed cosine taper over its last2ns, then the same0–3GHz filter. BIE high-frequency truncation precedes this window; FDTD has its native bandwidth.",
        source_strength="i omega mu0 I_plus; exact stored gprMax source samples at effective times (n+1/2)dt",
        scene=dict(radius_m=.1, target_epsr=4, source=sources.tolist(), receivers=receivers.tolist()),
        frequencies=args.frequencies, maximum_frequency_hz=args.maximum_frequency,
        bie_nodes=args.nodes, bie_seconds=bie_seconds, circle_series_checks=series_checks,
        results=all_rows)
    (args.output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    figure, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    for axis, receiver in zip(axes, [0, 10, 19]):
        axis.plot(times * 1e9, predicted[:, receiver], color="black", label="BIE, 512 frequencies")
        axis.plot(times * 1e9, measured[:, receiver], "--", label="gprMax, finest grid")
        axis.set_ylabel("Scattered Ez (V/m)")
        axis.set_title(f"Receiver {receiver}: x={receivers[receiver, 0]:.2f} m")
        axis.grid(alpha=.2)
    axes[0].legend()
    axes[-1].set_xlabel("Time (ns)")
    axes[-1].set_xlim(1.5, 9)
    figure.tight_layout()
    figure.savefig(args.output / "trace_overlay.png", dpi=160)
    plt.close(figure)
    figure, axes = plt.subplots(1, 3, figsize=(12, 6), sharey=True)
    extent = [.5, 20.5, times[-1] * 1e9, times[0] * 1e9]
    scale = np.max(abs(predicted))
    for axis, values, title in zip(axes, [predicted, measured, measured - predicted],
            ["BIE", "gprMax", "gprMax − BIE"]):
        im = axis.imshow(values, aspect="auto", extent=extent, cmap="RdBu_r", vmin=-scale, vmax=scale)
        axis.set_ylim(9, 1)
        axis.set_title(title)
        axis.set_xlabel("Receiver number")
    axes[0].set_ylabel("Time (ns)")
    figure.colorbar(im, ax=axes, label="Scattered Ez (V/m)", shrink=.8)
    figure.savefig(args.output / "bscan_comparison.png", dpi=160, bbox_inches="tight")
    plt.close(figure)
    print(json.dumps({"bie_seconds":bie_seconds,"rows":[{k:v for k,v in r.items() if k!="receivers"} for r in all_rows]},indent=2))


if __name__ == "__main__":
    main()
