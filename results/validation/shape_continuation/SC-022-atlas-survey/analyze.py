"""SC-022 descriptive analysis: rebuild summaries and figures from saved artifacts only.

No solves. Reads each case's `result.json`, `atlas.npz` and the evaluation-only
`true_error_EVALUATION_ONLY.npz`. The true error is used here only to
describe the recorded layers; nothing here feeds back into an inversion.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CASES = ("wrong_circle", "circle_to_star", "circle_to_c")
ARMS = ("borges", "fixed32")
TITLES = dict(wrong_circle="Wrong circle", circle_to_star="Circle to five-lobe star", circle_to_c="Circle to C (non-star)")


def pair(values, band):
    values = np.asarray(values, float)
    return np.concatenate((np.abs(values[..., :1]),
                           np.hypot(values[..., 1:band + 1], values[..., band + 1:])), axis=-1)


def cosine(a, b):
    na, nb = np.linalg.norm(a, axis=-1), np.linalg.norm(b, axis=-1)
    return np.where((na > 0) & (nb > 0), np.sum(a * b, axis=-1) / np.maximum(na * nb, 1e-300), np.nan)


def band_fraction(values, band, low, high):
    energy = pair(values, band) ** 2
    return energy[..., low:high + 1].sum(-1) / np.maximum(energy.sum(-1), 1e-300)


def summarize(arm, case):
    folder = HERE / "runs" / arm / case
    atlas = np.load(folder / "atlas.npz")
    truth = np.load(folder / "true_error_EVALUATION_ONLY.npz")
    result = json.loads((folder / "result.json").read_text())
    P = int(atlas["atlas_band"])
    f = atlas["frequencies_hz"] / 1e9
    t = truth["coefficients"]  # (S, D)
    lm, gn = atlas["lm_step"], atlas["gn_step"]  # (S, F, D)
    states = []
    for i in range(len(atlas["stage"])):
        states.append(dict(
            stage=int(atlas["stage"][i]), iteration=int(atlas["iteration"][i]),
            trajectory_loss=float(atlas["trajectory_loss"][i]),
            true_error_rms_mm=float(truth["rms_m"][i] * 1e3), true_error_max_mm=float(truth["maximum_m"][i] * 1e3),
            true_error_beyond_P_rms_mm=float(truth["beyond_band_rms_m"][i] * 1e3),
            true_error_fraction_above_16=float(band_fraction(t[i], P, 17, P)),
            true_error_fraction_above_32=float(band_fraction(t[i], P, 33, P)),
            relative_residual=dict(zip(f.round(3).astype(str), atlas["relative_residual"][i].round(8).tolist())),
            cos_lm_step_truth=dict(zip(f.round(3).astype(str), np.round(cosine(lm[i], t[i]), 4).tolist())),
            cos_gn_step_truth=dict(zip(f.round(3).astype(str), np.round(cosine(gn[i], t[i]), 4).tolist())),
            cos_stage_lm_step_truth=float(cosine(atlas["stage_lm_step"][i], t[i])),
            stage_lm_step_fraction_above_32=float(band_fraction(atlas["stage_lm_step"][i], P, 33, P)),
            lm_step_norm_mm=dict(zip(f.round(3).astype(str), (np.linalg.norm(lm[i], axis=-1) * 1e3).round(5).tolist()))))
    return dict(arm=arm, case=case, trajectory=dict(status=result["status"], reason=result["reason"],
                elapsed_seconds=result["elapsed_seconds"], work_units=result["work"]["work_units"],
                initial_geometry=result["initial_geometry"], final_geometry=result["final_geometry"],
                stages=result["stage_scores"]), states=states)


def trajectory_consistency(arm, case):
    """Recorded first-trial steps versus the atlas-assembled stage proposal in the run's own band."""
    folder = HERE / "runs" / arm / case
    atlas = np.load(folder / "atlas.npz")
    P = int(atlas["atlas_band"])
    stage, iteration = atlas["stage"], atlas["iteration"]
    bounds_rule = (0.012, 0.018, 0.006)
    config = json.loads((folder / "configuration.json").read_text())
    band = {s["label"]: s["update_modes"] for s in config["stages"]}
    errors = []
    for number in sorted(set(stage.tolist())):
        history = json.loads((folder / f"stage_{number}_history.json").read_text())
        M = band[f"stage_{number}"]
        keep = np.r_[0, np.arange(1, M + 1), P + np.arange(1, M + 1)]
        order = np.r_[0, np.arange(1, M + 1), np.arange(1, M + 1)]
        bounds = np.where(order == 0, bounds_rule[0], np.where(order == 1, bounds_rule[1], bounds_rule[2]))
        rows = [i for i in range(len(stage)) if stage[i] == number]
        trials = {t["iteration"]: t for t in history["trials"] if t.get("status") == "accepted"}
        for a, b in zip(rows, rows[1:]):
            trial = trials.get(int(iteration[b]))
            live = float(atlas["next_damping"][a])
            if trial is None or trial["backtrack"] != 0 or not np.isclose(trial["damping"], live, rtol=1e-12):
                continue
            train = [j for j, f in enumerate(atlas["frequencies_hz"]) if f in (0.5e9, 0.75e9, 1.0e9, 1.25e9)][:number]
            gram = sum(atlas["gauss_newton"][a, j][np.ix_(keep, keep)] for j in train) / len(train)
            grad = sum(atlas["gradient"][a, j][keep] for j in train) / len(train)
            proposal = np.clip(np.linalg.solve(gram + live * np.diag(np.maximum(np.diag(gram), 1.0)), -grad), -bounds, bounds)
            recorded = np.array(history["history"][int(iteration[b])]["step_m"])
            errors.append(float(np.linalg.norm(proposal - recorded) / np.linalg.norm(recorded)))
    return dict(checked_steps=len(errors), maximum_relative_difference=max(errors) if errors else None)


def figure(arm, case, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm, TwoSlopeNorm
    folder = HERE / "runs" / arm / case
    atlas = np.load(folder / "atlas.npz")
    truth = np.load(folder / "true_error_EVALUATION_ONLY.npz")
    P = int(atlas["atlas_band"])
    f = atlas["frequencies_hz"] / 1e9
    stage, iteration = atlas["stage"], atlas["iteration"]
    picks = [0, int(np.flatnonzero(stage == 1)[-1]), len(stage) - 1]
    labels = ["start", "end of stage 1", "final"]
    fig, axes = plt.subplots(3, 4, figsize=(17, 11), gridspec_kw=dict(width_ratios=[1, 1, 1, .45]))
    extent = [f[0] - .0625, f[-1] + .0625, -.5, P + .5]
    for row, (i, label) in enumerate(zip(picks, labels)):
        sens = pair(np.sqrt(np.clip(np.einsum("fdd->fd", atlas["gauss_newton"][i]), 0, None)), P).T
        step = pair(atlas["lm_step"][i], P).T * 1e3
        err = pair(truth["coefficients"][i], P) * 1e3
        # Signed agreement of each frequency's LM step with the true error, per harmonic.
        agree = np.sign(atlas["lm_step"][i] * truth["coefficients"][i])  # (F, D)
        weight = np.abs(atlas["lm_step"][i] * truth["coefficients"][i])
        signed = np.concatenate((agree[:, :1] * weight[:, :1],
                                 agree[:, 1:P + 1] * weight[:, 1:P + 1] + agree[:, P + 1:] * weight[:, P + 1:]), axis=1)
        norm = np.max(np.abs(signed), axis=1, keepdims=True)
        signed = (signed / np.where(norm > 0, norm, 1)).T
        im = axes[row, 0].imshow(sens, origin="lower", aspect="auto", extent=extent,
                                 norm=LogNorm(vmin=max(sens.max() * 1e-8, 1e-12), vmax=sens.max()), cmap="magma")
        fig.colorbar(im, ax=axes[row, 0], label="sensitivity (per m)")
        im = axes[row, 1].imshow(step, origin="lower", aspect="auto", extent=extent,
                                 norm=LogNorm(vmin=max(step.max() * 1e-6, 1e-9), vmax=step.max()), cmap="viridis")
        fig.colorbar(im, ax=axes[row, 1], label="|LM step| (mm)")
        im = axes[row, 2].imshow(signed, origin="lower", aspect="auto", extent=extent,
                                 norm=TwoSlopeNorm(0, -1, 1), cmap="coolwarm_r")
        fig.colorbar(im, ax=axes[row, 2], label="step·truth, signed, per-k normalized")
        axes[row, 3].barh(np.arange(P + 1), err, color="0.3")
        axes[row, 3].set_xscale("log")
        axes[row, 3].set_ylim(-.5, P + .5)
        axes[row, 3].set_xlabel("true error (mm)")
        for col in range(3):
            axes[row, col].set_ylabel("harmonic p of h")
            axes[row, col].axvline(0.5, color="w", lw=.5, ls=":")
            axes[row, col].axvline(1.25, color="w", lw=.5, ls=":")
            axes[row, col].axhline(32, color="w", lw=.6, ls="--")
        axes[row, 0].set_title(f"{label} (stage {stage[i]}, it {iteration[i]}): sensitivity")
        axes[row, 1].set_title("per-frequency LM step")
        axes[row, 2].set_title("does k's step point at the truth? (blue yes)")
        axes[row, 3].set_title("true error (eval only)")
    for ax in axes[-1, :3]:
        ax.set_xlabel("frequency (GHz); dotted: training range; dashed: M=32")
    fig.suptitle(f"SC-022 {TITLES[case]}, band rule {arm}: atlas at three trajectory states")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    rows = {}
    for arm in ARMS:
        for case in CASES:
            if not (HERE / "runs" / arm / case / "atlas.npz").exists():
                print(f"{arm}/{case}: atlas missing", file=sys.stderr)
                continue
            rows[f"{arm}/{case}"] = summarize(arm, case)
            rows[f"{arm}/{case}"]["trajectory_consistency"] = trajectory_consistency(arm, case)
            figure(arm, case, HERE / f"atlas_{arm}_{case}.png")
    (HERE / "analysis.json").write_text(json.dumps(rows, indent=1) + "\n")
    for case, row in rows.items():
        g0, g1 = row["trajectory"]["initial_geometry"], row["trajectory"]["final_geometry"]
        print(case, row["trajectory"]["status"], "Hausdorff %.2f -> %.3f mm" % (g0["hausdorff_m"] * 1e3, g1["hausdorff_m"] * 1e3),
              "states", len(row["states"]), "consistency", row["trajectory_consistency"])


if __name__ == "__main__":
    main()
