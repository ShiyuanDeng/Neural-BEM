"""SC-026 first analysis of the consolidated atlas. No solves; descriptive only.

Physical conventions: coefficients a (m) of the normal distance in normalized
arclength carry the Fourier mass W = diag(1, 1/2, ...), so ||h||_RMS^2 = a^T W a.
Directions are compared through the generalized eigenproblem G v = mu W v:
mu is the squared normalized-data change per squared RMS normal move (1/m^2).

"Determined" is a declared noise model, not a measured one: a direction is
determined when a 0.1 mm RMS move changes the data by at least the norm of
0.1% relative noise on each of the 48 real measurements per frequency,
i.e. mu >= (1e-3 * sqrt(48 * F) / 1e-4)^2 for F stacked frequencies. The
alternative threshold (1 mm, 1%) gives the same ratio and is not repeated;
0.1 mm / 1e-4 and 1 mm / 1e-3 are reported for sensitivity.

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
NOISE = dict(main=(1e-3, 1e-4), coarse=(1e-3, 1e-3), fine=(1e-4, 1e-4))  # (relative noise, RMS move in m)
CASES = ("wrong_circle", "circle_to_star", "circle_to_c", "kite", "peanut", "hook")


def threshold(frequencies, noise=NOISE["main"]):
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
            share = []
            for n in range(1, len(hz) + 1):
                mu, V = generalized(G[:n].sum(0))
                coefficients = V.T @ (W * e)
                share.append(float(np.sum(coefficients[mu >= threshold(n)] ** 2) / total) if total > 0 else np.nan)
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
                undetermined = float(np.sum(coefficients[mu < threshold(len(train))] ** 2) / energy)
                steps.append(dict(case=case, run=run, stage=stage, band=band, iteration=it1,
                                  step_rms_mm=float(np.sqrt(energy) * 1e3), undetermined_share=undetermined,
                                  radius_before_mm=float(evaluation["tightest_radius_m"][i0] * 1e3),
                                  radius_after_mm=float(evaluation["tightest_radius_m"][i1] * 1e3),
                                  distance_before_mm=float(evaluation["symmetric_rms_m"][i0] * 1e3),
                                  distance_after_mm=float(evaluation["symmetric_rms_m"][i1] * 1e3)))
    out["states"] = len(per_state)
    out["steps"] = len(steps)
    out.update(summaries(per_state, steps, k, hz))
    (HERE / "analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    (HERE / "analysis_states.json").write_text(json.dumps(per_state) + "\n")
    (HERE / "analysis_steps.json").write_text(json.dumps(steps) + "\n")
    figure(per_state, steps, k, hz)
    print(json.dumps({key: value for key, value in out.items() if key not in ("noise_models",)}, indent=1))


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    keep = np.isfinite(x) & np.isfinite(y)
    rx, ry = np.argsort(np.argsort(x[keep])), np.argsort(np.argsort(y[keep]))
    return float(np.corrcoef(rx, ry)[0, 1])


def summaries(states, steps, k, hz):
    out = {}
    smooth = [s for s in states if s["radius_mm"] >= 8]
    rough = [s for s in states if s["radius_mm"] < 4]
    frontier = np.array([s["frontier"]["main"] for s in states], float)
    determined = np.array([s["determined"]["main"] for s in states], float)
    out["frontier_over_k_median_by_frequency"] = dict(zip(np.round(hz / 1e9, 3).astype(str),
                                                          np.round(np.median(frontier, 0) / k, 2).tolist()))
    out["determined_count_median_by_frequency"] = dict(zip(np.round(hz / 1e9, 3).astype(str),
                                                           np.median(determined, 0).tolist()))
    for name, group in (("smooth_radius_ge_8mm", smooth), ("rough_radius_lt_4mm", rough)):
        f = np.array([s["frontier"]["main"] for s in group], float)
        d = np.array([s["determined"]["main"] for s in group], float)
        out[f"{name}"] = dict(states=len(group),
                              frontier_median=dict(zip(np.round(hz / 1e9, 3).astype(str), np.median(f, 0).tolist())),
                              determined_median=dict(zip(np.round(hz / 1e9, 3).astype(str), np.median(d, 0).tolist())))
    for label in ("coarse", "fine"):
        d = np.array([s["determined"][label] for s in states], float)
        out[f"determined_count_median_by_frequency_{label}"] = dict(zip(np.round(hz / 1e9, 3).astype(str),
                                                                       np.median(d, 0).tolist()))
    cos = np.array([s["train_gradient_min_cosine"] for s in states])
    dist = np.array([s["symmetric_rms_mm"] for s in states])
    out["gradient_agreement"] = dict(
        train_min_cosine_negative_fraction=float(np.mean(cos < 0)),
        spearman_train_min_cosine_vs_distance=spearman(cos, dist),
        by_distance={f"{lo}-{hi} mm": dict(states=int(np.sum((dist >= lo) & (dist < hi))),
                                          negative_fraction=float(np.mean(cos[(dist >= lo) & (dist < hi)] < 0)))
                     for lo, hi in ((0, 0.1), (0.1, 1), (1, 5), (5, 15), (15, 100)) if np.any((dist >= lo) & (dist < hi))})
    share = np.array([s["error_share_determined_cumulative"] for s in states])
    out["error_share_determined"] = {
        f"{lo}-{hi} mm": dict(states=int(np.sum((dist >= lo) & (dist < hi))),
                             at_f_max={str(round(hz[n] / 1e9, 3)): float(np.nanmedian(share[(dist >= lo) & (dist < hi), n]))
                                       for n in (0, 3, 7, 11, 18)})
        for lo, hi in ((0, 0.1), (0.1, 1), (1, 5), (5, 15), (15, 100)) if np.any((dist >= lo) & (dist < hi))}
    undetermined = np.array([s["undetermined_share"] for s in steps])
    ratio = np.array([s["radius_after_mm"] / s["radius_before_mm"] for s in steps])
    progress = np.array([s["distance_after_mm"] / s["distance_before_mm"] for s in steps])
    sharpening = ratio < 0.8
    out["steps_taken"] = dict(
        count=len(steps),
        undetermined_share_quantiles=np.quantile(undetermined, [.1, .25, .5, .75, .9]).round(4).tolist(),
        spearman_undetermined_vs_radius_ratio=spearman(undetermined, ratio),
        spearman_undetermined_vs_distance_ratio=spearman(undetermined, progress),
        sharpening_steps=int(sharpening.sum()),
        undetermined_share_median_sharpening=float(np.median(undetermined[sharpening])) if sharpening.any() else None,
        undetermined_share_median_other=float(np.median(undetermined[~sharpening])),
        by_band={str(b): dict(steps=int(np.sum([s["band"] == b for s in steps])),
                              undetermined_median=float(np.median([s["undetermined_share"] for s in steps if s["band"] == b])),
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
    frontier = np.array([s["frontier"]["main"] for s in states], float)
    for group, color, label in ((radius >= 8, "C0", "radius ≥ 8 mm"), ((radius >= 4) & (radius < 8), "C1", "4–8 mm"),
                                (radius < 4, "C3", "< 4 mm")):
        axes[0].plot(k, np.median(frontier[group], 0), "o-", color=color, label=f"{label} ({group.sum()})")
        axes[0].fill_between(k, *np.percentile(frontier[group], [25, 75], axis=0), color=color, alpha=.15)
    axes[0].plot(k, 3 * k, "k--", lw=1, label="ladder 3k")
    axes[0].plot(k, 2.5 * k, "k:", lw=1, label="SC-015 2.5k")
    axes[0].set_xlabel("k (package units)")
    axes[0].set_ylabel("highest determined harmonic (0.1 mm, 0.1% noise)")
    axes[0].legend(fontsize=8)
    axes[0].set_title("determined band by state roughness")
    dist = np.array([s["symmetric_rms_mm"] for s in states])
    cos = np.array([s["train_gradient_min_cosine"] for s in states])
    axes[1].scatter(dist, cos, s=5, c=np.log10(radius), cmap="viridis")
    axes[1].set_xscale("log")
    axes[1].axhline(0, color="k", lw=.6)
    axes[1].set_xlabel("symmetric RMS distance to truth (mm, eval only)")
    axes[1].set_ylabel("min gradient cosine, 0.5–1.25 GHz")
    axes[1].set_title("do the training frequencies agree?")
    share = np.array([s["error_share_determined_cumulative"] for s in states])
    for lo, hi, color in ((0, 1, "C0"), (1, 5, "C1"), (5, 15, "C2"), (15, 100, "C3")):
        group = (dist >= lo) & (dist < hi)
        if group.any():
            axes[2].plot(hz / 1e9, np.nanmedian(share[group], 0), "o-", color=color, label=f"{lo}–{hi} mm ({group.sum()})")
    axes[2].set_xlabel("f_max of cumulative data (GHz)")
    axes[2].set_ylabel("share of true error in determined directions")
    axes[2].legend(fontsize=8)
    axes[2].set_title("how much of the error can the data see?")
    undetermined = np.array([s["undetermined_share"] for s in steps])
    ratio = np.array([s["radius_after_mm"] / s["radius_before_mm"] for s in steps])
    axes[3].scatter(undetermined, ratio, s=5, alpha=.4)
    axes[3].set_yscale("log")
    axes[3].axhline(1, color="k", lw=.6)
    axes[3].set_xlabel("share of the step taken in undetermined directions")
    axes[3].set_ylabel("tightest radius after / before (eval only)")
    axes[3].set_title("does undetermined motion roughen the curve?")
    fig.tight_layout()
    fig.savefig(HERE / "analysis.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
