"""SC-025: a frozen minimal band policy against the ladder, fixed M=32 and a progress controller.

Every arm runs SPD's cumulative schedule (frequencies, weights, quotas and
caps unchanged) with the backend variant SC-024(a) selected. Only the band M
of each stage differs, and it is chosen when the stage starts:

- `ladder`: Borges' M = floor(3 max(k, ki)) at the stage's highest frequency;
- `fixed32`: M = 32;
- `progress`: the ladder, but after a stage that stops with no decreasing
  step and less than 10% loss reduction, M doubles (at most 48);
- `atlas`: amendment A2's `parsimonious` rule on fresh P=48 atlas cells at
  the current curve for the stage's frequencies: the smallest band whose
  controlled, admissible step has at least 0.9 of the best band's model
  decrease. The cells are solves and reciprocal batches on the same ledger.

Truth enters only observation generation and the endpoint score, whose
return value the loop ignores. Held-out truths are built only by `prepare`
with `--held-out`, after the policy is frozen.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
import json
from pathlib import Path
import time

import numpy as np

from . import atlas_cases as ac
from . import conditional_study as cs
from . import spd_cases as sc
from .atlas_survey import band_coordinates, cell, conditional_step, predicted_decrease, symmetric_rms_distance
from .geometry import FourierCurve
from .lm_backend import Ledger, control_step, run_policy, stage_record
from .metrics import area_error, boundary_distance
from .updates import BorgesUpdate, UpdateRefused

ROOT = Path(__file__).resolve().parents[2]
SC022 = ROOT / "results/validation/shape_continuation/SC-022-atlas-survey"
# SC-023's declared rules and A1 did not qualify; A2's `parsimonious` rule did
# (SC-023 amendment_a2.json), so it is frozen here as the atlas arm.
FROZEN_RULE = "A2 parsimonious"
PARSIMONY = 0.9
FEATURE_DAMPING = 1e-3
# SC-024(a): V2 has the lowest summed final symmetric RMS over the ladder's three
# development runs (3.73 mm; V1 6.00, V3 6.55, V0 7.23).
BACKEND_VARIANT = dict(step_control="coefficient", projection_tolerance=1e-5)
ARMS = ("ladder", "fixed32", "progress", "atlas")
HELD_OUT = dict(
    kite=dict(kind="kite", scale_m=0.025, rotation=0.5, center=(0.505, 0.497)),
    peanut=dict(kind="peanut", radius_m=0.05, rotation=1.1, center=(0.497, 0.503)),
    hook=dict(kind="thick_arc", centreline_m=0.036, half_thickness_m=0.013, half_angle_deg=130.0,
              rotation=2.4, center=(0.496, 0.506), band=10))


def thick_arc(spec):
    """Thick arc with semicircular caps, sampled by arclength, smoothed to its natural band (as SC-022's C)."""
    R, w = spec["centreline_m"], spec["half_thickness_m"]
    alpha = np.radians(spec["half_angle_deg"])
    cap = np.linspace(0, np.pi, 600)
    pieces = [(R + w) * np.exp(1j * np.linspace(-alpha, alpha, 2000)),
              R * np.exp(1j * alpha) + w * np.exp(1j * (alpha + cap)),
              (R - w) * np.exp(1j * np.linspace(alpha, -alpha, 2000)),
              R * np.exp(-1j * alpha) + w * np.exp(1j * (-alpha + np.pi + cap))]
    p = np.concatenate(pieces)
    s = np.r_[0, np.cumsum(np.abs(np.diff(np.r_[p, p[0]])))]
    u = np.linspace(0, s[-1], 8192, endpoint=False)
    return np.interp(u, s, np.r_[p.real, p[0].real]) + 1j * np.interp(u, s, np.r_[p.imag, p[0].imag]), spec["band"]


def held_out_curve(name):
    """Package units about the scene centre. Only `prepare --held-out` calls this."""
    spec = HELD_OUT[name]
    t = 2 * np.pi * np.arange(8192) / 8192
    if spec["kind"] == "kite":
        points, band = spec["scale_m"] * (np.cos(t) + 0.65 * np.cos(2 * t) - 0.65 + 1.5j * np.sin(t)), 8
    elif spec["kind"] == "peanut":
        points, band = spec["radius_m"] * (0.75 + 0.3 * np.cos(2 * t)) * np.exp(1j * t), 8
    else:
        points, band = thick_arc(spec)
    points = points * np.exp(1j * spec["rotation"]) + complex(*spec["center"]) - sc.CENTER
    return FourierCurve.from_samples(points / sc.LENGTH, band)


def prepare(output, held_out):
    """Development inputs are copied from SC-022; held-out inputs are generated with SC-022's oracle."""
    inputs = output / "inputs"
    inputs.mkdir(parents=True, exist_ok=held_out)
    if not held_out:
        for case in ac.CASES:
            (inputs / case).mkdir()
            for name in ("observations.json", "truth.json", "oracle_check.json"):
                (inputs / case / name).write_bytes((SC022 / "inputs" / case / name).read_bytes())
        sc.write(output / "manifest.json", dict(experiment="SC-025", frozen_rule=FROZEN_RULE,
                 feature_damping=FEATURE_DAMPING, backend_variant=BACKEND_VARIANT, arms=ARMS,
                 held_out_declared=HELD_OUT, source_sha256=sc.source_hashes(),
                 inputs={str(p.relative_to(output)): ac.digest(p) for p in sorted(inputs.rglob("*.json"))},
                 prepared=time.strftime("%Y-%m-%dT%H:%M:%S%z")))
        return
    top025, cfg, base = ac.spd()
    freqs = np.asarray(ac.CATALOG_HZ)
    manifest = sc.read(output / "manifest.json")
    for name in HELD_OUT:
        truth = held_out_curve(name)
        truth.validate()
        values = ac.kress_predictions(truth, freqs, 1024)
        check = dict(oracle="SPD nodal Kress, 1024 nodes",
                     refinement_kress_2048_vs_1024=ac.relative(ac.kress_predictions(truth, freqs, 2048), values).tolist())
        obs = ac.observations(values)
        from .forward import solve
        muller = np.column_stack([solve(truth, o.wavenumber, ac.contrast(), o.acquisition, 1024).prediction for o in obs])
        check["cross_package_muller_1024_vs_oracle"] = ac.relative(muller, values).tolist()
        limits = dict(refinement=1e-9, cross=1e-8)
        worst = {kind: max([max(v) for k, v in check.items() if k.startswith(kind)], default=0.0) for kind in limits}
        from .geometry import reparameterize
        try:
            reparameterize(truth, ac.CURVE_MODES, tolerance=1e-7)
            representable = True
        except ValueError as exc:
            representable = str(exc)
        check.update(limits=limits, passed=bool(all(worst[k] <= limits[k] for k in limits)),
                     representable_at_K192_tolerance_1e_7=representable)
        folder = inputs / name
        folder.mkdir()
        sc.write(folder / "observations.json", dict(frequencies_hz=list(ac.CATALOG_HZ),
                 observed_real=values.real, observed_imag=values.imag))
        sc.write(folder / "truth.json", dict(case=name, real=truth.coefficients.real, imag=truth.coefficients.imag,
                 definition=HELD_OUT[name]))
        sc.write(folder / "oracle_check.json", check)
        print(json.dumps(dict(case=name, oracle_passed=check["passed"], worst=worst, representable=representable)), flush=True)
        if not check["passed"]:
            raise RuntimeError(f"{name}: oracle checks failed ({worst}).")
    manifest.setdefault("amendments", []).append(dict(reason="held-out inputs generated after the policy froze",
        source_sha256=sc.source_hashes(), recorded=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        inputs={str(p.relative_to(output)): ac.digest(p) for p in sorted(inputs.rglob("*.json"))}))
    sc.write(output / "manifest.json", manifest)


def verify(output):
    manifest = sc.read(output / "manifest.json")
    latest = manifest["amendments"][-1] if manifest.get("amendments") else manifest
    if sc.source_hashes() != latest["source_sha256"]:
        raise RuntimeError("Numerical sources changed after preparation.")
    for name, value in latest["inputs"].items():
        if ac.digest(output / name) != value:
            raise RuntimeError(f"Input changed: {name}")


class BandPolicy:
    """SPD's cumulative stages; `choose(template, history)` sets each stage's band when it starts."""

    def __init__(self, stages, choose, name):
        self.stages, self.choose, self.name = tuple(stages), choose, name
        self.decisions = []

    def next_stage(self, history):
        if len(history) >= len(self.stages):
            return None
        template = self.stages[len(history)]
        band, record = self.choose(template, history)
        self.decisions.append(dict(stage=template.label, band=int(band), **record))
        return replace(template, update_modes=int(band))


def progress_chooser(ladder_bands):
    def choose(template, history):
        n = len(history)
        if n == 0:
            return ladder_bands[0], dict(reason="ladder")
        previous = history[-1]
        band = previous_band = choose.bands[-1]
        reduction = (previous.initial_loss - previous.final_loss) / previous.initial_loss
        stalled = previous.stop_reason == "no_decreasing_step" and reduction < 0.1
        band = min(48, 2 * previous_band) if stalled else max(ladder_bands[n], previous_band)
        return band, dict(reason="doubled after stall" if stalled else "ladder or previous",
                          previous_reduction=float(reduction), previous_stop=previous.stop_reason)
    choose.bands = []

    def recorded(template, history):
        band, record = choose(template, history)
        choose.bands.append(band)
        return band, record
    return recorded


def atlas_chooser(stages, initial, update, config, contrast, ledger, catalog):
    """Amendment A2's `parsimonious` rule on fresh P=48 cells at the stage start.

    For each candidate band: the conditional LM step at FEATURE_DAMPING, the
    backend's own step control, and halving to the first trial the backend's
    refit gate admits (geometry only). Its model decrease, as a fraction of
    the stage loss, is the feature; the rule takes the smallest band within
    PARSIMONY of the best. The cells are charged to the run's ledger.
    """
    band_list = cs.bands(catalog, contrast)
    position = {o.wavenumber: i for i, o in enumerate(catalog)}

    def choose(template, history):
        n = len(history)
        curve = history[-1].curve if history else update.regauge(initial, template.curve_modes)[0]
        if curve.band < template.curve_modes:
            pad = template.curve_modes - curve.band
            curve = FourierCurve(np.pad(curve.coefficients, (pad, pad)))
        active = [position[o.wavenumber] for o in template.observations]
        ledger.begin_stage(f"policy_probe_{n + 1}", None)
        cells = []
        for j in active:
            ledger.reserve(2)
            ledger.charge("solve", "policy_probe")
            ledger.charge("reciprocal", "policy_probe")
            cells.append(cell(curve, catalog[j], contrast, template.nodes, cs.P, sc.LENGTH))
        G = sum(c.gauss_newton * w for c, w in zip(cells, template.weights))
        g = sum(c.gradient * w for c, w in zip(cells, template.weights))
        loss = sum(c.loss * w for c, w in zip(cells, template.weights))
        rows = []
        for band in band_list:
            keep = band_coordinates(band, cs.P)
            space = update.prepare(curve, band, curve.band)
            proposal = control_step(conditional_step(G, g, keep, FEATURE_DAMPING)[keep], space, update, config)
            fraction, halving = 0.0, None
            for h in range(config.max_backtracks + 1):
                try:
                    update.trial(space, 0.5 ** h * proposal)
                except UpdateRefused:
                    continue
                step = np.zeros(2 * cs.P + 1)
                step[keep] = 0.5 ** h * proposal
                fraction, halving = predicted_decrease(G, g, step) / loss, h
                break
            rows.append(dict(band=band, controlled_fraction=fraction, halving=halving))
        best = max(r["controlled_fraction"] for r in rows)
        band = min(r["band"] for r in rows if r["controlled_fraction"] >= PARSIMONY * best)
        return band, dict(rule="A2 parsimonious", loss=float(loss), features=rows)
    return choose


def run(output, case, arm):
    verify(output)
    catalog, truth = ac.load_case(output, case)
    ladder_schedule, config = ac.policy(catalog, "borges")
    config = replace(config, step_control=BACKEND_VARIANT["step_control"])
    update = BorgesUpdate(sc.LENGTH, projection_tolerance=BACKEND_VARIANT["projection_tolerance"])
    ledger = Ledger(cap=8012, seconds=7200.0)
    ladder_bands = [s.update_modes for s in ladder_schedule.stages]
    stages = ladder_schedule.stages
    if arm == "ladder":
        policy = BandPolicy(stages, lambda t, h: (t.update_modes, dict(reason="ladder")), "ladder")
    elif arm == "fixed32":
        policy = BandPolicy(stages, lambda t, h: (32, dict(reason="fixed")), "fixed32")
    elif arm == "progress":
        policy = BandPolicy(stages, progress_chooser(ladder_bands), "progress")
    else:
        choose = atlas_chooser(stages, ac.start_curve(), update, config, ac.contrast(), ledger, catalog)
        policy = BandPolicy(stages, choose, f"atlas: {FROZEN_RULE}")
    folder = output / "runs" / arm / case
    folder.mkdir(parents=True, exist_ok=False)
    sc.write(folder / "configuration.json", dict(arm=arm, update=update.settings(), backend=asdict(config),
             policy=policy.name, template_stages=[stage_record(s) for s in stages]))
    points = truth.values(16384)
    scores = []

    def geometry(curve):
        error, bound = boundary_distance(truth, curve)
        return dict(hausdorff_m=error * sc.LENGTH, hausdorff_upper_m=(error + bound) * sc.LENGTH,
                    symmetric_rms_m=symmetric_rms_distance(curve, points, sc.LENGTH), area=area_error(truth, curve),
                    tightest_radius_m=float(sc.LENGTH / np.max(np.abs(curve.nodes(8192).curvatures))))

    def endpoint(stage, result):
        scores.append(dict(stage=stage.label, band=stage.update_modes, geometry=geometry(result.curve),
                           outcome=result.outcome, stop=result.stop_reason, accepted=result.accepted_steps,
                           loss=result.final_loss, initial_loss=result.initial_loss))
        sc.write(folder / "stage_scores.json", scores)

    started = time.perf_counter()
    result = run_policy(ac.start_curve(), policy, ac.contrast(), update, config, ledger, on_stage=endpoint)
    outcomes = {}
    for record in result.stages:
        sc.write(folder / f"{record.stage_label}_history.json", dict(history=record.history, trials=record.trials,
                 acceptance_checks=record.acceptance_checks))
        for trial in record.trials:
            key = trial.get("reason") or trial.get("status")
            outcomes[key] = outcomes.get(key, 0) + 1
    summary = dict(case=case, arm=arm, status=result.status, reason=result.reason, detail=result.detail,
                   elapsed_seconds=time.perf_counter() - started, work=ledger.snapshot(),
                   decisions=policy.decisions, initial_geometry=geometry(ac.start_curve()),
                   final_geometry=geometry(result.curve), trial_outcomes=outcomes, stage_scores=scores,
                   final_curve=dict(real=result.curve.coefficients.real.tolist(),
                                    imag=result.curve.coefficients.imag.tolist()))
    sc.write(folder / "result.json", summary)
    return dict(case=case, arm=arm, status=result.status, bands=[d["band"] for d in policy.decisions],
                final_symmetric_rms_mm=summary["final_geometry"]["symmetric_rms_m"] * 1e3,
                final_hausdorff_mm=summary["final_geometry"]["hausdorff_m"] * 1e3, units=ledger.units)


def _run(job):
    try:
        return run(*job)
    except Exception as exc:
        return dict(job=[str(j) for j in job], error=repr(exc))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--held-out", action="store_true")
    parser.add_argument("--cases", nargs="+", default=list(ac.CASES))
    parser.add_argument("--arms", nargs="+", default=list(ARMS))
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.output, args.held_out)
    if args.run:
        jobs = [(args.output, case, arm) for case in args.cases for arm in args.arms]
        with ProcessPoolExecutor(args.workers) as pool:
            for row in pool.map(_run, jobs):
                print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
