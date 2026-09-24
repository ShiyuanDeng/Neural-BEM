"""SC-026 first analysis of the consolidated atlas. No solves; descriptive only.

Physical conventions: coefficients a (m) of the normal distance in normalized
arclength carry the Fourier mass W = diag(1, 1/2, ...), so ||h||_RMS^2 = a^T W a.
Directions are compared through the generalized eigenproblem G v = mu W v:
mu is the squared normalized-data change per squared RMS normal move (1/m^2).

"Determined" is a declared noise model, not a measured one: a direction is
determined when a given RMS move changes the data by at least the norm of
0.1% relative noise on each of the 48 real measurements per frequency, i.e.
mu >= (1e-3 * sqrt(48 * F) / move)^2 for F stacked frequencies. Two moves are
reported: "strict" (0.1 mm) and "lenient" (1 mm). Only the ratio of noise to
move matters. A scale-free step measure (no noise model) is also reported:
the step's Rayleigh quotient q^T G q / q^T W q relative to the largest mu.

Stacked frequency sets SUM the per-frequency blocks (independent
measurements), unlike the stage objective, which averages them.
Truth-derived layers (normal-ray error, distances, radii) are EVALUATION ONLY.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.linalg import eigh

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[3]), str(HERE.parents[3] / "solvers")]
from experiments.shape_continuation import atlas_cases as ac  # noqa: E402
from experiments.shape_continuation import spd_cases as sc  # noqa: E402
from experiments.shape_continuation.atlas_survey import band_coordinates, rms_weights  # noqa: E402

P = 48
W = rms_weights(P)
ORDERS = np.r_[0, np.arange(1, P + 1), np.arange(1, P + 1)]
TRAIN_HZ = (0.5e9, 0.75e9, 1.0e9, 1.25e9)
NOISE = dict(strict=(1e-3, 1e-4), lenient=(1e-3, 1e-3))  # (relative noise, RMS move in m)
CASES = ("wrong_circle", "circle_to_star", "circle_to_c", "kite", "peanut", "hook")


def threshold(frequencies, noise=NOISE["strict"]):
    eta, move = noise
    return (eta * np.sqrt(48 * frequencies) / move) ** 2


def generalized(G):
    """Eigenvalues mu (descending) and W-orthonormal eigenvectors of G v = mu W v."""
    mu, V = eigh(G, np.diag(W))
    order = np.argsort(mu)[::-1]
    return np.clip(mu[order], 0, None), V[:, order]


def wavenumbers():
    catalog, _ = ac.load_case(HERE.parent / "SC-022-atlas-survey", "wrong_circle")
    return np.array([o.wavenumber for o in catalog])


def main():
    k = wavenumbers()
    hz = np.array(ac.CATALOG_HZ)
    index = sc.read(HERE / "index.json")
    by_key = {(r["case"], r["state_key"]): r for r in index}
    out = dict(noise_models={k_: dict(relative_noise=v[0], rms_move_m=v[1]) for k_, v in NOISE.items()})
    per_state = []
    steps = []
    next_cosines = []
    histories = {}
    for case in CASES:
        cells = np.load(HERE / "cells" / f"{case}.npz")
        evaluation = np.load(HERE / "evaluation" / f"{case}_EVALUATION_ONLY.npz")
        J, r = cells["jacobian"], cells["residual"]
        keys = list(cells["state_key"])
        row_of = {key: i for i, key in enumerate(keys)}
        G_all = np.einsum("sfri,sfrj->sfij", J, J)
        g_all = np.einsum("sfri,sfr->sfi", J, r)
        for i, key in enumerate(keys):
            G, g = G_all[i], g_all[i]
            rec = dict(case=case, key=key, symmetric_rms_mm=float(evaluation["symmetric_rms_m"][i] * 1e3),
                       radius_mm=float(evaluation["tightest_radius_m"][i] * 1e3))
            # (1) determined count and harmonic frontier per frequency
            counts, frontier = {label: [] for label in NOISE}, {label: [] for label in NOISE}
            for j in range(len(hz)):
                mu, _ = generalized(G[j])
                diag = np.diag(G[j]) / W
                pair = np.r_[diag[0], diag[1:P + 1] + diag[P + 1:]] / np.r_[1, np.full(P, 2)]
                for label, noise in NOISE.items():
                    counts[label].append(int(np.sum(mu >= threshold(1, noise))))
                    ok = np.flatnonzero(pair >= threshold(1, noise))
                    frontier[label].append(int(ok.max()) if len(ok) else -1)
            rec.update(determined=counts, frontier=frontier)
            # (2) agreement of per-frequency gradients (covectors: metric W^-1)
            gw = g / np.sqrt(W)
            norms = np.linalg.norm(gw, axis=1)
            cos = (gw @ gw.T) / np.outer(norms, norms)
            train = [int(np.flatnonzero(hz == f)[0]) for f in TRAIN_HZ]
            rec.update(train_gradient_min_cosine=float(np.min(cos[np.ix_(train, train)])),
                       catalog_negative_pair_fraction=float(np.mean(cos[np.triu_indices(len(hz), 1)] < 0)))
            # (3) share of the evaluation-only normal-ray error in determined directions, cumulative F
            e = evaluation["normal_ray"][i]
            total = float(e @ (W * e) + evaluation["normal_ray_beyond_m"][i] ** 2)
            share = {label: [] for label in NOISE}
            for n in range(1, len(hz) + 1):
                mu, V = generalized(G[:n].sum(0))
                coefficients = V.T @ (W * e)
                for label, noise in NOISE.items():
                    share[label].append(float(np.sum(coefficients[mu >= threshold(n, noise)] ** 2) / total)
                                        if total > 0 else np.nan)
            rec["error_share_determined_cumulative"] = share
            rec["error_beyond_48_share"] = float(evaluation["normal_ray_beyond_m"][i] ** 2 / total) if total > 0 else np.nan
            per_state.append(rec)
        # (4) the steps actually taken, measured in the stage's determined subspace
        entries = [r_ for r_ in index if r_["case"] == case]
        sequence = defaultdict(list)
        for entry in entries:
            for occ in entry["occurrences"]:
                sequence[(occ["run"], occ["stage"])].append((occ["iteration"], entry["state_key"], occ["band"]))
        for (run, stage), items in sequence.items():
            items.sort()
            path = HERE.parent / run / f"stage_{stage}_history.json"
            if path not in histories:
                histories[path] = {h["iteration"]: h for h in sc.read(path)["history"]}
            history = histories[path]
            train = [int(np.flatnonzero(hz == f)[0]) for f in TRAIN_HZ[:stage]]
            following = (int(np.flatnonzero(hz == TRAIN_HZ[stage])[0]) if stage < 4
                         else int(np.flatnonzero(hz == 1.5e9)[0]))
            for it, key, _ in items:
                g_stage = g_all[row_of[key]][train].sum(0) / np.sqrt(W)
                g_next = g_all[row_of[key]][following] / np.sqrt(W)
                next_cosines.append(dict(case=case, run=run, stage=stage, iteration=it,
                                         cosine=float(g_stage @ g_next / np.linalg.norm(g_stage) / np.linalg.norm(g_next)),
                                         distance_mm=float(evaluation["symmetric_rms_m"][row_of[key]] * 1e3)))
            for (it0, key0, band), (it1, key1, _) in zip(items, items[1:]):
                step = np.array(history[it1]["step_m"])
                if band is None or len(step) != 2 * band + 1 or not np.any(step):
                    continue
                full = np.zeros(2 * P + 1)
                full[band_coordinates(band, P)] = step
                i0, i1 = row_of[key0], row_of[key1]
                mu, V = generalized(G_all[i0][train].sum(0))
                coefficients = V.T @ (W * full)
                energy = float(full @ (W * full))
                undetermined = {label: float(np.sum(coefficients[mu < threshold(len(train), noise)] ** 2) / energy)
                                for label, noise in NOISE.items()}
                G_stage = G_all[i0][train].sum(0)
                rayleigh = float(full @ G_stage @ full / energy / max(mu[0], 1e-300))
                steps.append(dict(case=case, run=run, stage=stage, band=band, iteration=it1,
                                  step_rms_mm=float(np.sqrt(energy) * 1e3), undetermined_share=undetermined,
                                  relative_sensitivity=rayleigh,
                                  radius_before_mm=float(evaluation["tightest_radius_m"][i0] * 1e3),
                                  radius_after_mm=float(evaluation["tightest_radius_m"][i1] * 1e3),
                                  distance_before_mm=float(evaluation["symmetric_rms_m"][i0] * 1e3),
                                  distance_after_mm=float(evaluation["symmetric_rms_m"][i1] * 1e3)))
    truth_radius = {}
    for case in CASES:
        bundle = "SC-022-atlas-survey" if case in ("wrong_circle", "circle_to_star", "circle_to_c") else "SC-025-band-policies"
        _, truth = ac.load_case(HERE.parent / bundle, case)
        truth_radius[case] = float(sc.LENGTH / np.max(np.abs(truth.nodes(8192).curvatures)) * 1e3)
    for step in steps:  # evaluation only: a >20% radius drop ending below half the truth's tightest radius
        step["pathological_sharpening"] = bool(step["radius_after_mm"] < 0.8 * step["radius_before_mm"]
                                               and step["radius_after_mm"] < 0.5 * truth_radius[step["case"]])
    out["truth_tightest_radius_mm"] = truth_radius
    out["states"] = len(per_state)
    out["steps"] = len(steps)
    out.update(summaries(per_state, steps, next_cosines, k, hz))
    (HERE / "analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    (HERE / "analysis_states.json").write_text(json.dumps(per_state) + "\n")
    (HERE / "analysis_steps.json").write_text(json.dumps(steps) + "\n")
    (HERE / "analysis_next_frequency.json").write_text(json.dumps(next_cosines) + "\n")
    figure(per_state, steps, k, hz)
    print(json.dumps({key: value for key, value in out.items() if key not in ("noise_models",)}, indent=1))


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    keep = np.isfinite(x) & np.isfinite(y)
    rx, ry = np.argsort(np.argsort(x[keep])), np.argsort(np.argsort(y[keep]))
    return float(np.corrcoef(rx, ry)[0, 1])


def summaries(states, steps, next_cosines, k, hz):
    out = {}
    freq = np.round(hz / 1e9, 3).astype(str)
    radius = np.array([s["radius_mm"] for s in states])
    dist = np.array([s["symmetric_rms_mm"] for s in states])
    for label in NOISE:
        frontier = np.array([s["frontier"][label] for s in states], float)
        determined = np.array([s["determined"][label] for s in states], float)
        out[f"determined_{label}"] = dict(
            frontier_over_k_median=dict(zip(freq, np.round(np.median(frontier, 0) / k, 2).tolist())),
            count_median=dict(zip(freq, np.median(determined, 0).tolist())),
            frontier_median_smooth_radius_ge_8mm=dict(zip(freq, np.median(frontier[radius >= 8], 0).tolist())),
            frontier_median_rough_radius_lt_4mm=dict(zip(freq, np.median(frontier[radius < 4], 0).tolist())),
            smooth_states=int(np.sum(radius >= 8)), rough_states=int(np.sum(radius < 4)))
    bins = ((0, 0.1), (0.1, 1), (1, 5), (5, 15), (15, 100))
    cos = np.array([s["train_gradient_min_cosine"] for s in states])
    out["training_gradients_any_opposed_pair"] = {
        f"{lo}-{hi} mm": dict(states=int(np.sum((dist >= lo) & (dist < hi))),
                             fraction=float(np.mean(cos[(dist >= lo) & (dist < hi)] < 0)))
        for lo, hi in bins if np.any((dist >= lo) & (dist < hi))}
    c = np.array([x["cosine"] for x in next_cosines])
    d = np.array([x["distance_mm"] for x in next_cosines])
    out["stage_gradient_vs_next_frequency"] = dict(
        occurrences=len(c), negative_fraction=float(np.mean(c < 0)),
        by_distance={f"{lo}-{hi} mm": dict(occurrences=int(np.sum((d >= lo) & (d < hi))),
                                          negative_fraction=float(np.mean(c[(d >= lo) & (d < hi)] < 0)),
                                          median_cosine=float(np.median(c[(d >= lo) & (d < hi)])))
                     for lo, hi in bins if np.any((d >= lo) & (d < hi))},
        by_stage={str(st): dict(occurrences=int(np.sum([x["stage"] == st for x in next_cosines])),
                                negative_fraction=float(np.mean([x["cosine"] < 0 for x in next_cosines if x["stage"] == st])))
                  for st in (1, 2, 3, 4)})
    for label in NOISE:
        share = np.array([s["error_share_determined_cumulative"][label] for s in states])
        out[f"error_share_determined_{label}"] = {
            f"{lo}-{hi} mm": dict(states=int(np.sum((dist >= lo) & (dist < hi))),
                                 at_f_max={freq[n]: float(np.nanmedian(share[(dist >= lo) & (dist < hi), n]))
                                           for n in (2, 4, 6, 8, 10, 12, 18)})
            for lo, hi in bins if np.any((dist >= lo) & (dist < hi))}
    rho = np.array([s["relative_sensitivity"] for s in steps])
    ratio = np.array([s["radius_after_mm"] / s["radius_before_mm"] for s in steps])
    progress = np.array([s["distance_after_mm"] / s["distance_before_mm"] for s in steps])
    sharpening = ratio < 0.8
    out["steps_taken"] = dict(
        count=len(steps), sharpening_steps=int(sharpening.sum()),
        relative_sensitivity_quantiles=np.quantile(rho, [.1, .25, .5, .75, .9]).tolist(),
        relative_sensitivity_median_sharpening=float(np.median(rho[sharpening])),
        relative_sensitivity_median_other=float(np.median(rho[~sharpening])),
        spearman_relative_sensitivity_vs_radius_ratio=spearman(rho, ratio),
        spearman_relative_sensitivity_vs_distance_ratio=spearman(rho, progress),
        sharpening_fraction_by_relative_sensitivity={
            f"{lo:g}-{hi:g}": dict(steps=int(np.sum((rho >= lo) & (rho < hi))),
                                  sharpening=float(np.mean(sharpening[(rho >= lo) & (rho < hi)])),
                                  median_distance_ratio=float(np.median(progress[(rho >= lo) & (rho < hi)])))
            for lo, hi in ((0, 1e-4), (1e-4, 1e-3), (1e-3, 1e-2), (1e-2, 1e-1), (1e-1, 1.01))
            if np.any((rho >= lo) & (rho < hi))},
        undetermined_share_median={label: float(np.median([s["undetermined_share"][label] for s in steps]))
                                   for label in NOISE},
        pathological=dict(
            steps=int(sum(s["pathological_sharpening"] for s in steps)),
            by_stage={str(st): int(sum(s["pathological_sharpening"] and s["stage"] == st for s in steps)) for st in (1, 2, 3, 4)},
            by_band={str(b): int(sum(s["pathological_sharpening"] and s["band"] == b for s in steps))
                     for b in sorted({s["band"] for s in steps if s["pathological_sharpening"]})},
            relative_sensitivity_median=float(np.median([s["relative_sensitivity"] for s in steps if s["pathological_sharpening"]])),
            relative_sensitivity_median_other=float(np.median([s["relative_sensitivity"] for s in steps if not s["pathological_sharpening"]])),
            step_rms_median_mm=float(np.median([s["step_rms_mm"] for s in steps if s["pathological_sharpening"]])),
            step_rms_median_other_mm=float(np.median([s["step_rms_mm"] for s in steps if not s["pathological_sharpening"]])),
            rate_by_step_rms_mm={f"{lo:g}-{hi:g}": float(np.mean([s["pathological_sharpening"] for s in steps
                                                                 if lo <= s["step_rms_mm"] < hi]))
                                 for lo, hi in ((0, .3), (.3, 1), (1, 3), (3, 10), (10, 100))},
            stage_1_rate_by_band={str(b): float(np.mean([s["pathological_sharpening"] for s in steps
                                                         if s["stage"] == 1 and s["band"] == b]))
                                  for b in sorted({s["band"] for s in steps if s["stage"] == 1})}),
        by_band={str(b): dict(steps=int(np.sum([s["band"] == b for s in steps])),
                              relative_sensitivity_median=float(np.median([s["relative_sensitivity"] for s in steps if s["band"] == b])),
                              sharpening_fraction=float(np.mean([s["radius_after_mm"] / s["radius_before_mm"] < 0.8
                                                                 for s in steps if s["band"] == b])))
                 for b in sorted({s["band"] for s in steps})})
    return out


def figure(states, steps, k, hz):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 4, figsize=(21, 4.8))
    radius = np.array([s["radius_mm"] for s in states])
    frontier = np.array([s["frontier"]["strict"] for s in states], float)
    for group, color, label in ((radius >= 8, "C0", "radius ≥ 8 mm"), ((radius >= 4) & (radius < 8), "C1", "4–8 mm"),
                                (radius < 4, "C3", "< 4 mm")):
        axes[0].plot(k, np.median(frontier[group], 0), "o-", color=color, label=f"{label} ({group.sum()})")
        axes[0].fill_between(k, *np.percentile(frontier[group], [25, 75], axis=0), color=color, alpha=.15)
    axes[0].plot(k, 3 * k, "k--", lw=1, label="ladder 3k")
    axes[0].plot(k, 2.5 * k, "k:", lw=1, label="SC-015 2.5k")
    axes[0].set_xlabel("k (package units)")
    axes[0].set_ylabel("highest determined harmonic (strict)")
    axes[0].legend(fontsize=8)
    axes[0].set_title("determined band vs k, by state roughness")
    dist = np.array([s["symmetric_rms_mm"] for s in states])
    for label, style in (("strict", "-"), ("lenient", "--")):
        share = np.array([s["error_share_determined_cumulative"][label] for s in states])
        for (lo, hi), color in zip(((0.1, 1), (1, 5), (5, 15), (15, 100)), ("C0", "C1", "C2", "C3")):
            group = (dist >= lo) & (dist < hi)
            axes[1].plot(hz / 1e9, np.nanmedian(share[group], 0), style, color=color,
                         label=f"{lo}–{hi} mm ({group.sum()})" if label == "strict" else None)
    axes[1].axvline(1.25, color="k", lw=.6, ls=":")
    axes[1].set_xlabel("f_max of cumulative data (GHz); dotted: SPD's last")
    axes[1].set_ylabel("share of true error in determined directions")
    axes[1].legend(fontsize=8, title="solid strict, dashed lenient", title_fontsize=7)
    axes[1].set_title("how much of the error can the data see?")
    rho = np.array([s["relative_sensitivity"] for s in steps])
    ratio = np.array([s["radius_after_mm"] / s["radius_before_mm"] for s in steps])
    progress = np.array([s["distance_after_mm"] / s["distance_before_mm"] for s in steps])
    bad = np.array([s["pathological_sharpening"] for s in steps])
    axes[2].scatter(rho[~bad], ratio[~bad], s=5, alpha=.4, label="other steps")
    axes[2].scatter(rho[bad], ratio[bad], s=12, c="C3", label="pathological sharpening (all stage 1)")
    axes[2].legend(fontsize=8)
    axes[2].set_xscale("log")
    axes[2].set_yscale("log")
    axes[2].axhline(1, color="k", lw=.6)
    axes[2].set_xlabel("step sensitivity / best direction's (Rayleigh quotient)")
    axes[2].set_ylabel("tightest radius after / before (eval only)")
    axes[2].set_title("do weakly sensed steps sharpen the curve?")
    axes[3].scatter(rho, progress, s=5, alpha=.4, c="C2")
    axes[3].set_xscale("log")
    axes[3].set_yscale("log")
    axes[3].axhline(1, color="k", lw=.6)
    axes[3].set_xlabel("step sensitivity / best direction's")
    axes[3].set_ylabel("distance to truth after / before (eval only)")
    axes[3].set_title("do weakly sensed steps make progress?")
    fig.tight_layout()
    fig.savefig(HERE / "analysis.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
