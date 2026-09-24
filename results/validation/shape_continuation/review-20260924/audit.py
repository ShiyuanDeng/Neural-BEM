"""Read-only numerical audit of SC-020/021/022; no forward or inverse solves.

Run from the repository root with PYTHONPATH=solvers:. and one BLAS thread.
Requires the six local SC-022 atlas/truth NPZ pairs. Writes only this review's
audit.json, never the original experiment records.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = HERE.parent
SURVEY = BASE / "SC-022-atlas-survey"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cosine(a, b, mass=None):
    mass = np.ones(len(a)) if mass is None else mass
    return float(np.sum(mass * a * b) / np.sqrt(np.sum(mass * a*a) * np.sum(mass * b*b)))


def main():
    spec = importlib.util.spec_from_file_location("sc022_analysis", SURVEY / "analyze.py")
    analysis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analysis)
    report = dict(scope="Saved-artifact audit and analytic circle geometry; no physics solves",
                  audit_script_sha256=digest(Path(__file__)),
                  reused_step_consistency_script_sha256=digest(SURVEY / "analyze.py"),
                  numpy_version=np.__version__,
                  reviewed_commit=subprocess.check_output(
                      ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                  bundles={}, trajectories={})
    for name in ("SC-020-spd-matched-hybrid", "SC-021-hybrid-update-band-32"):
        folder = BASE / name
        manifest = read(folder / "manifest.json")
        summary = read(folder / "comparison.json")["summary"]
        report["bundles"][name] = dict(
            stored_verification=read(folder / "verification.json"),
            input_hashes_match=all(digest(folder / p) == item["sha256"]
                                   for p, item in manifest["inputs"].items()),
            recorded_sources_changed_now=[p for p, sha in manifest["source_sha256"].items()
                                         if not (ROOT / p).exists() or digest(ROOT / p) != sha],
            work_units={arm: summary[arm]["work_units"] for arm in ("spd", "hybrid")})
    manifest = read(SURVEY / "manifest.json")
    hashes = manifest["amendments"][-1]["source_sha256"] if manifest.get("amendments") else manifest["source_sha256"]
    report["sc022_integrity"] = dict(
        input_hashes_match=all(digest(SURVEY / p) == sha for p, sha in manifest["inputs"].items()),
        recorded_sources_changed_now=[p for p, sha in hashes.items()
                                     if not (ROOT / p).exists() or digest(ROOT / p) != sha])
    for arm in ("borges", "fixed32"):
        for case in ("wrong_circle", "circle_to_star", "circle_to_c"):
            folder = SURVEY / "runs" / arm / case
            summary = read(folder / "atlas_summary.json")
            atlas = np.load(folder / "atlas.npz")
            truth = np.load(folder / "true_error_EVALUATION_ONLY.npz")
            P = int(atlas["atlas_band"])
            mass = np.r_[1., np.full(2 * P, .5)]  # normalized-arclength RMS metric
            stored_lm = atlas["lm_step"]
            evaluation = read(folder / "result.json")
            row = dict(states=summary["states"], unique_curves=summary["unique_curves"],
                cells=summary["cells"],
                atlas_hash_matches=digest(folder / "atlas.npz") == summary["atlas_sha256"],
                truth_hash_matches=digest(folder / "true_error_EVALUATION_ONLY.npz") == summary["true_error_sha256"],
                consistency=analysis.trajectory_consistency(arm, case),
                hausdorff_m=evaluation["final_geometry"]["hausdorff_m"],
                work_units=evaluation["work"]["work_units"],
                stages=[dict(stage=s["stage"], accepted=s["accepted"], stop=s["stop"],
                             hausdorff_m=s["geometry"]["hausdorff_m"]) for s in evaluation["stage_scores"]],
                initial_median_raw_step_coefficient_norm_mm=float(np.median(np.linalg.norm(stored_lm[0], axis=1))*1e3),
                initial_median_raw_step_physical_rms_mm=float(np.median(np.sqrt(np.sum(mass*stored_lm[0]**2, axis=1)))*1e3),
                first_last_spectral_rank_at_relative_1e_10=[],
                final_stage_alignment=dict(coefficient_cosine=cosine(atlas["stage_lm_step"][-1], truth["coefficients"][-1]),
                    physical_rms_cosine=cosine(atlas["stage_lm_step"][-1], truth["coefficients"][-1], mass)),
                damping_range=[float(atlas["next_damping"].min()), float(atlas["next_damping"].max())])
            for index in (0, len(atlas["stage"])-1):
                eigen = np.linalg.eigvalsh(atlas["gauss_newton"][index])
                row["first_last_spectral_rank_at_relative_1e_10"].append(
                    np.sum(eigen > 1e-10 * eigen[:, -1:], axis=1).tolist())
            # Independent replay of the model gain for actual accepted steps.
            # This uses the preceding state's G,g and the recorded clipped/halved
            # step, not a component sliced from a full-space solution.
            ratios = []
            config = read(folder / "configuration.json")
            stage_bands = {i+1: s["update_modes"] for i, s in enumerate(config["stages"])}
            for number in range(1, 5):
                histories = read(folder / f"stage_{number}_history.json")["history"]
                indices = np.flatnonzero(atlas["stage"] == number)
                M = stage_bands[number]
                keep = np.r_[0, np.arange(1, M+1), P+np.arange(1, M+1)]
                active = [j for j, f in enumerate(atlas["frequencies_hz"])
                          if f in (0.5e9, 0.75e9, 1e9, 1.25e9)][:number]
                for before, after in zip(indices, indices[1:]):
                    step = np.asarray(histories[int(atlas["iteration"][after])]["step_m"])
                    G = atlas["gauss_newton"][before, active].mean(axis=0)[np.ix_(keep, keep)]
                    g = atlas["gradient"][before, active].mean(axis=0)[keep]
                    predicted = float(-g @ step - .5 * step @ G @ step)
                    actual = float(atlas["trajectory_loss"][before] - atlas["trajectory_loss"][after])
                    ratios.append(dict(stage=number, iteration=int(atlas["iteration"][after]),
                                       predicted=predicted, actual=actual,
                                       ratio=actual/predicted if predicted > 0 else None))
            row["accepted_step_model_gains"] = ratios
            if arm == "borges" and case == "circle_to_star":
                # Illustrative local linear counterfactuals, not trial curves or
                # policy successes. Same saved G,g,lambda; different retained
                # coordinates. Alignment uses the existing evaluation proxy.
                examples = []
                for frequency in (.75e9, 1e9, 1.25e9):
                    j = int(np.flatnonzero(atlas["frequencies_hz"] == frequency)[0])
                    G, g = atlas["gauss_newton"][-1, j], atlas["gradient"][-1, j]
                    pair = np.array([15, P+15])
                    selections = {
                        "full_P48": np.arange(2*P+1),
                        "current_M9_plus_pair15": np.r_[0, np.arange(1, 10), P+np.arange(1, 10), pair],
                        "contiguous_M15": np.r_[0, np.arange(1, 16), P+np.arange(1, 16)]}
                    for label, keep in selections.items():
                        H = G[np.ix_(keep, keep)]
                        step = -np.linalg.solve(H + float(atlas["next_damping"][-1]) *
                            np.diag(np.maximum(np.diag(H), 1.)), g[keep])
                        component = step[[int(np.flatnonzero(keep == p)[0]) for p in pair]]
                        examples.append(dict(frequency_hz=frequency, space=label,
                            damping=float(atlas["next_damping"][-1]),
                            pair15_proxy_cosine=cosine(component, truth["coefficients"][-1, pair]),
                            pair15_amplitude_mm=float(np.linalg.norm(component)*1e3)))
                row["final_star_space_dependence_examples"] = examples
            report["trajectories"][f"{arm}/{case}"] = row
            atlas.close()
            truth.close()

    # Exact counterexample to treating signed closest distance as a normal
    # displacement: the actual SC-022 initial circle and circle target.
    angle = np.arange(16384) * (2*np.pi/16384)
    normal = np.exp(1j*angle)
    offset, radius, target = -.02+.02j, .065, .05
    points = offset + radius*normal
    proxy = target - np.abs(points)
    b = np.real(offset*np.conj(normal))
    exact = -b + np.sqrt(b*b + target*target - abs(offset)**2) - radius
    miss = np.abs(points + proxy*normal) - target
    report["circle_distance_proxy_counterexample"] = dict(
        initial_radius_m=radius, target_radius_m=target, offset_m=[offset.real, offset.imag],
        proxy_minus_normal_ray_rms_mm=float(np.sqrt(np.mean((proxy-exact)**2))*1e3),
        proxy_minus_normal_ray_max_mm=float(np.max(np.abs(proxy-exact))*1e3),
        after_proxy_move_max_distance_to_circle_mm=float(np.max(np.abs(miss))*1e3),
        after_exact_normal_move_max_distance_m=float(np.max(np.abs(np.abs(points+exact*normal)-target))))
    report["totals"] = dict(states=sum(x["states"] for x in report["trajectories"].values()),
        unique_curves_within_runs=sum(x["unique_curves"] for x in report["trajectories"].values()),
        cells=sum(x["cells"] for x in report["trajectories"].values()),
        checked_first_trial_steps=sum(x["consistency"]["checked_steps"] for x in report["trajectories"].values()),
        maximum_step_replay_relative_error=max(x["consistency"]["maximum_relative_difference"] or 0
                                              for x in report["trajectories"].values()))
    (HERE / "audit.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps(dict(totals=report["totals"], circle_check=report["circle_distance_proxy_counterexample"]), indent=2))


if __name__ == "__main__":
    main()
