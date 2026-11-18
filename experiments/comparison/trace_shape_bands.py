"""Measure slider directions and coefficient carryover on saved TG-002 curves only."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize_scalar, root
from shapely import linestrings, STRtree
from shapely.geometry import LinearRing

from bem_inverse.continuation.geometry import cleanup, grid_size, resize
from bem_inverse.geometry_update_methods.slider import SliderUpdate
from bem_inverse.io import curve_from, read, write
from experiments.benchmark import scenes
from experiments.comparison.scoring import PROTOCOL, region, region_scores

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "results/bem/stage_stops/2026-11-18"
ORIGINAL = ROOT / "results/bem/default_clean_uc_fc"
INPUTS = ROOT / "development_results/TG-002/inputs"
OUTPUT = ROOT / "results/bem/stage_scheduling/2026-11-18/shape_bands"
FIGURES = ROOT / "docs/iterations/investigate_bem_stage_scheduling/01_trace_stage_stops_and_shape_bands/figures"
MM = 1000 * scenes.LENGTH
MODE_MM = 0.001  # one micrometre in a signed Cartesian coefficient
CASES = ("c_shape", "kite", "aphex_twin", "cog")
SURFACE, INK, MUTED = "#fcfcfb", "#0b0b0b", "#52514e"


def ring(curve):
    points = curve.values(PROTOCOL["curve_samples"]) * MM
    return region([points])[0]


def correspondence(entry, truth, count):
    """Pair points by normalized arclength with the least-squares cyclic phase."""
    def arc(curve):
        z = curve.values(count)
        z = np.r_[z, z[0]]
        distance = np.r_[0., np.cumsum(np.abs(np.diff(z)))]
        return distance / distance[-1], z

    entry_s, entry_z = arc(entry)
    truth_s, truth_z = arc(truth)
    uniform = np.arange(count) / count
    base = np.interp(uniform, entry_s, entry_z)
    target = np.interp(uniform, truth_s, truth_z)
    corr = np.fft.ifft(np.fft.fft(target) * np.fft.fft(base).conj()).real
    near = np.argmax(corr) / count

    def paired(s, phase):
        return np.interp((s + phase) % 1., truth_s, truth_z)

    phase = minimize_scalar(lambda u: np.mean(abs(paired(uniform, u) - base)**2),
                            bounds=(near - 1/count, near + 1/count), method="bounded",
                            options={"xatol": 1e-12}).x
    return paired(entry_s[:-1], phase), phase % 1.


def projection(entry, end, truth, band, other_band=None):
    count = 4096
    nodes = entry.nodes(count)
    normal = nodes.normals @ np.array([1., 1j])
    weights = np.sqrt(nodes.arc_length_weights / nodes.perimeter)
    target, phase = correspondence(entry, truth, count)

    def weighted_move(points):
        return weights * MM * ((points - entry.values(count)) * normal.conj()).real

    gap = weighted_move(target)
    moved = weighted_move(end.values(count))
    slider = SliderUpdate(scenes.LENGTH, device="cpu")

    def project(m):
        space = slider.prepare(entry, m, entry.band)
        columns = weights[:, None] * slider.velocities(space, nodes)
        return columns @ np.linalg.lstsq(columns, gap, rcond=None)[0]

    reachable = project(band)
    length = np.linalg.norm(reachable)
    result = dict(phase_turns=phase, normal_gap_mm=np.linalg.norm(gap), reachable_mm=length,
                outside_mm=np.linalg.norm(gap-reachable),
                reachable_energy_fraction=length**2 / (gap @ gap),
                actual_normal_move_mm=np.linalg.norm(moved),
                actual_along_reachable_gap_mm=moved @ reachable / length,
                normal_gap_after_move_fixed_pairing_mm=np.linalg.norm(gap-moved))
    if other_band is not None:
        other = project(other_band)
        result.update(other_update_band=other_band, other_reachable_mm=np.linalg.norm(other),
                      other_outside_mm=np.linalg.norm(gap-other))
    return result


def ranges(modes):
    """Sorted signed orders as inclusive pairs."""
    result = []
    for value in sorted(int(m) for m in modes):
        if result and value == result[-1][1] + 1:
            result[-1][1] = value
        else:
            result.append([value, value])
    return result


def changes(entry, end):
    delta = abs(end.coefficients - entry.coefficients) * MM
    ranked = np.argsort(-delta)
    return dict(exactly_changed_orders=ranges(end.modes[delta > 0]),
                changed_by_at_least_1um=ranges(end.modes[delta >= MODE_MM]),
                largest_mm_by_order=[[int(end.modes[i]), float(delta[i])] for i in ranked[:3] if delta[i]])


def carryover(stages, ends, entries, final):
    records = []
    for i, (start, end) in enumerate(zip(entries, ends)):
        changed = start.coefficients != end.coefficients
        set_here = abs(end.coefficients - start.coefficients) * MM >= MODE_MM
        later = {}
        targets = [(s["stage"], c) for s, c in zip(stages[i+1:], ends[i+1:])]
        for label, target in [*targets, ("final", final)]:
            delta = abs(resize(target, end.band).coefficients - end.coefficients) * MM
            later[label] = dict(identical_after_any_change=ranges(end.modes[changed & (delta == 0)]),
                                identical=ranges(end.modes[set_here & (delta == 0)]),
                                within_1um=ranges(end.modes[set_here & (delta < MODE_MM)]))
        records.append(dict(origin=stages[i]["stage"], set_here=ranges(end.modes[set_here]), later=later))
    return records


def analyse(shape, arm):
    case = shape + "__c4"
    is_original = arm == "original"
    path = ORIGINAL / case / "fit.json" if is_original else SOURCE / arm / (case + ".json")
    saved = read(path)
    stages = saved["stages"]
    ends = [curve_from(s["curve"]) for s in stages]
    truth = curve_from(read(INPUTS / shape / "truth.json"))
    true_region = ring(truth)
    opening = true_region.convex_hull.difference(true_region) if shape == "c_shape" else None
    previous = curve_from(read(INPUTS / "start.json"))
    measured = []
    entries = []
    for i, (stage, end) in enumerate(zip(stages, ends)):
        entry = resize(previous, end.band)
        extra = abs(entry.modes) > previous.band
        assert end.band >= previous.band
        assert np.array_equal(resize(entry, previous.band).coefficients, previous.coefficients)
        assert not np.any(entry.coefficients[extra])
        cleanup_here = stage["stage"] == "full_4_M25"
        if cleanup_here:
            entry = cleanup(entry)
            if is_original:
                event, = [e for e in saved["decisions"] if e["reason"] == "policy cleanup entered"]
                assert np.array_equal(entry.coefficients, curve_from(event["curve"]).coefficients)

        entries.append(entry)
        a, b = ring(entry), ring(end)
        score = lambda outline: region_scores(outline, true_region)["area_error"]
        record = dict(stage=stage["stage"], update_band=stage["M"], storage_band=end.band,
                      steps=stage["accepted_steps"], zero_padded_orders=int(extra.sum()), cleanup=cleanup_here,
                      entry_loss=stage["initial_loss"], exit_loss=stage["final_loss"],
                      entry_area_error=score(a), exit_area_error=score(b), contrast=stage["contrast"],
                      stop=stage["stop"], outcome=stage["outcome"], detail=stage["detail"],
                      **changes(entry, end))
        if "area_error" in stage:
            assert np.isclose(record["exit_area_error"], stage["area_error"], atol=1e-10)
        if not stage["accepted_steps"]:
            assert np.array_equal(entry.coefficients, end.coefficients)
        if opening is not None:
            record.update(opening_filled_at_entry=a.intersection(opening).area / opening.area,
                          opening_filled_at_exit=b.intersection(opening).area / opening.area)
        if i < 4:
            other = stage["M"] + (2 if is_original else -2)
            record["projection"] = projection(entry, end, truth, stage["M"], other)
        elif is_original and shape in ("c_shape", "kite"):
            record["projection"] = projection(entry, end, truth, stage["M"])
        measured.append(record)
        previous = end
    final = curve_from(saved["final_curve"]) if is_original else ends[-1]
    if is_original:
        assert np.array_equal(final.coefficients, ends[-1].coefficients)
    else:
        assert np.isclose(saved["final_area_error"], measured[-1]["exit_area_error"])
    return dict(source=str(path.relative_to(ROOT)), stages=measured,
                orders_at_later_exits=carryover(stages, ends, entries, final))


def crossing_check(curve):
    """Check the trial grid and refine crossings on the scoring grid against the series."""
    def coordinates(count):
        z = curve.values(count)
        return np.column_stack((z.real, z.imag))

    n = PROTOCOL["curve_samples"]
    points = coordinates(n)
    segments = linestrings(np.stack((points, np.roll(points, -1, axis=0)), axis=1))
    ii, jj = STRtree(segments).query(segments, predicate="crosses")
    crossings = []
    for i, j in zip(ii[ii < jj], jj[ii < jj]):
        def difference(t):
            z = np.exp(1j * np.outer(t, curve.modes)) @ curve.coefficients
            return np.array([(z[1]-z[0]).real, (z[1]-z[0]).imag])

        guess = 2*np.pi*(np.array([i, j])+.5)/n
        solution = root(difference, guess, tol=1e-12)
        residual = MM * np.linalg.norm(difference(solution.x))
        assert residual < 1e-8 and np.all(abs(solution.x-guess) < 2*np.pi/n)
        crossings.append(dict(parameters_rad=solution.x.tolist(), separation_mm=residual))
    return dict(simple_at_trial_grid=LinearRing(coordinates(grid_size(curve.band))).is_simple,
                simple_at_scoring_grid=LinearRing(points).is_simple, crossings=crossings)


def kite_interaction():
    short, extended = (read(SOURCE / arm / "kite__c4.json")["stages"] for arm in ("wider", "both"))
    a, b = short[0], extended[0]
    common = a["accepted_iteration_loss_contrast"]
    assert common == b["accepted_iteration_loss_contrast"][:len(common)]
    records = []
    for s, t in zip(short, extended):
        left, right = curve_from(s["curve"]), curve_from(t["curve"])
        records.append(dict(stage=s["stage"], wider_step=s["accepted_steps"], both_step=t["accepted_steps"],
                            wider_loss=s["final_loss"], both_loss=t["final_loss"],
                            wider_contrast=s["contrast"], both_contrast=t["contrast"],
                            wider_error=s["area_error"], both_error=t["area_error"],
                            wider_crossing_check=crossing_check(left), both_crossing_check=crossing_check(right),
                            **changes(left, right)))
    return dict(common_through_step=common[-1][0], common_last=common[-1],
                next_extended=b["accepted_iteration_loss_contrast"][len(common)],
                endpoints=records)


def figure():
    fig, axes = plt.subplots(2, 3, figsize=(9, 5.4), facecolor=SURFACE)
    for row, (shape, arms, picks, labels) in enumerate([
        ("c_shape", ["wider", "original"], [0, 2, -1], ["Stage 1", "Stage 3", "Final"]),
        ("kite", ["wider", "both"], [0, 1, 2], ["Stage 1", "Stage 2", "Stage 3"]),
    ]):
        target = curve_from(read(INPUTS / shape / "truth.json")).values(2048) * MM
        curves = []
        for arm in arms:
            path = (ORIGINAL / (shape + "__c4") / "fit.json" if arm == "original"
                    else SOURCE / arm / (shape + "__c4.json"))
            stages = read(path)["stages"]
            curves.append([curve_from(stages[i]["curve"]).values(2048) * MM for i in picks])
        all_points = np.concatenate([target, *curves[0], *curves[1]])
        for col, ax in enumerate(axes[row]):
            def draw(points, **kwargs):
                closed = np.r_[points, points[0]]
                ax.plot(closed.real, closed.imag, **kwargs)
            ax.set_facecolor(SURFACE)
            for curve, arm, color in zip(curves, arms, ["#15775c", "#b64d28"]):
                draw(curve[col], color=color, lw=1.6, label={"original": "Original", "wider": "Wider",
                                                             "both": "Wider + longer"}[arm])
            draw(target, color=MUTED, ls="--", lw=1.1, label="Truth")
            ax.set(xlim=(all_points.real.min()-4, all_points.real.max()+4),
                   ylim=(all_points.imag.min()-4, all_points.imag.max()+4), aspect="equal")
            ax.set_title(labels[col], color=INK, fontsize=11)
            ax.set_axis_off()
        axes[row, 0].text(-.07, .5, "C-shape" if row == 0 else "Kite", rotation=90,
                          va="center", transform=axes[row, 0].transAxes, color=INK, fontweight="bold")
        axes[row, -1].legend(loc="center left", bbox_to_anchor=(1.02, .5), frameon=False)
    fig.subplots_adjust(left=.08, right=.80, top=.94, bottom=.12, hspace=.22)
    fig.text(.08, .035, "Clean TG-002, contrast 4. Saved stage exits in a shared frame per shape (no new solves).",
             color=MUTED, fontsize=9)
    FIGURES.mkdir(exist_ok=True, parents=True)
    fig.savefig(FIGURES / "shape_bands_outlines.png", dpi=160)
    plt.close(fig)


def main():
    for shape in CASES:
        result = {arm: analyse(shape, arm) for arm in ("original", "wider")}
        if shape == "kite":
            result["wider_vs_both"] = kite_interaction()
        write(OUTPUT / (shape + ".json"), result)
    figure()


if __name__ == "__main__":
    main()
