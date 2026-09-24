"""Matched single-object comparison with the previous explicit Fourier inverse.

The harness alone imports the old inverse. Solver/controller modules remain
independent. Prepare immutable JSON inputs once, then every arm reads those
same observations and the same initial Cartesian curve. All costs are charged
in single-frequency forward solves, including failed trials and atlas probes.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

import numpy as np

from .atlas import Whitening
from .continuation import run_adaptive
from .forward import PointSourceAcquisition, Work, BudgetExceeded, solve
from .geometry import FourierCurve, grid_size
from .inverse import FitConfig, Observation
from .metrics import area_error, boundary_distance
from .policy import AtlasPolicy
from .run import provenance

ARMS = ("legacy_cartesian", "fixed", "band", "frequency", "full")
CASES = tuple(f"{initial}-to-{target}" for target in ("circle", "star")
              for initial in ("circle", "ellipse", "star"))
TRAIN = (0.5, 1.5, 2.5)
HOLDOUT = (0.25, 1.0, 2.0)
LENGTH = 0.05
CENTER = 0.5 + 0.5j


def write(path, value):
    def portable(item):
        if isinstance(item, np.ndarray): return portable(item.tolist())
        if isinstance(item, np.generic): return portable(item.item())
        if isinstance(item, dict): return {k: portable(v) for k,v in item.items()}
        if isinstance(item, (tuple, list)): return [portable(v) for v in item]
        if isinstance(item, float) and not np.isfinite(item): return None
        return item
    path.write_text(json.dumps(portable(value), indent=2, allow_nan=False) + "\n")


def complex_record(value):
    value = np.asarray(value)
    return dict(real=value.real.tolist(), imag=value.imag.tolist())


def complex_array(value):
    return np.asarray(value["real"]) + 1j*np.asarray(value["imag"])


def shape_record(shape):
    return complex_record(shape.coefficients)


def load_shape(value):
    return FourierCurve(complex_array(value))


def dimensionless(shape):
    coefficients = shape.coefficients.copy()
    coefficients[shape.band] -= CENTER
    return FourierCurve(coefficients/LENGTH)


def physical(shape):
    coefficients = shape.coefficients*LENGTH
    coefficients[shape.band] += CENTER
    return FourierCurve(coefficients)


def from_cartesian(state):
    cosine = state.cosine_coefficients[:, 0] + 1j*state.cosine_coefficients[:, 1]
    sine = state.sine_coefficients[:, 0] + 1j*state.sine_coefficients[:, 1]
    band = len(cosine)-1
    coefficients = np.zeros(2*band+1, complex)
    coefficients[band] = cosine[0]
    coefficients[band+1:] = (cosine[1:]-1j*sine[1:])/2
    coefficients[:band] = ((cosine[1:]+1j*sine[1:])/2)[::-1]
    return FourierCurve(coefficients)


def source_hashes():
    root = Path(__file__).resolve().parents[2]
    paths = [*root.glob("run_*.py"), *root.glob("config/*.py"),
             *root.glob("solvers/**/*.py"), *Path(__file__).parent.glob("*.py")]
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def prepare(output, max_forwards, max_seconds):
    from run_sdf_inverse_comparison import _build_target, _build_problem, _ring_scan
    from run_mlp_sdf_inverse_comparison import _initial_teacher
    from sdf_inverse import build_ordered_sdf_geometry
    from sdf_inverse.curve_updates import fit_cartesian_fourier_curve_state

    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(provenance=provenance(), source_sha256=source_hashes(),
        cases=list(CASES), arms=list(ARMS), train_ghz=list(TRAIN), holdout_ghz=list(HOLDOUT),
        max_forward_frequency_solves=max_forwards, max_seconds=max_seconds,
        maximum_mode_legacy=6, legacy_iterations=150, num_pairs=24,
        length_unit_m=LENGTH, origin_m=[CENTER.real, CENTER.imag],
        new_config=asdict(FitConfig(max_iterations=50, backtracks=0,
                                  curvature_tail_tolerance=0.01)),
        new_minimum_storage=128, new_max_decisions=12,
        gates=dict(boundary_upper_m=0.001, train_relative=0.003, holdout_relative=0.05,
                   endpoint_field_refinement=1e-6),
        scope="Single objects; known lossless materials. No topology or material inversion.",
        differences=["Legacy uses cumulative frequencies; new arms use one frequency at a time.",
          "Legacy uses polar-angle Cartesian K6 and finite-difference LM; new arms use arclength normal GN/SD.",
          "New arms retain at least 128 storage modes to resolve the inherited non-circular starts.",
          "The same solve/time caps apply; algorithms may stop before exhausting them.",
          "Only three measured training frequencies exist; no extra observations are generated for adaptation."])
    write(output/"manifest.json", manifest)
    for target_name in ("circle", "star"):
        target = _build_target(target_name)
        sources, receivers = _ring_scan(center=target.center, standoff=0.30, num_pairs=24)
        problem = _build_problem(TRAIN+HOLDOUT, sources, receivers)
        if (problem.exterior.sigma or problem.interior.sigma
                or problem.exterior.mur != problem.interior.mur):
            raise ValueError("Bridge requires lossless equal-permeability materials.")
        truth_data = target.observations(problem)
        oracle = target.oracle_diagnostics(problem) or {}
        if oracle.get("maximum_relative_difference", 0) > 1e-7:
            raise RuntimeError("Independent observation oracle failed refinement.")
        physical_truth_points = target.exact_boundary_polyline(2048)
        truth = FourierCurve.from_samples(physical_truth_points[:, 0]+1j*physical_truth_points[:, 1], 6)
        waves = problem.angular_frequencies*np.sqrt(problem.eps0*problem.mu0*problem.exterior.epsr)
        shared = dict(target=target_name, target_parameters=target.parameter_dict(),
            oracle_name=target.truth_oracle, oracle_diagnostics=oracle,
            frequencies_ghz=list(TRAIN+HOLDOUT), wavenumbers=(waves*LENGTH).tolist(),
            contrast=problem.interior.epsr/problem.exterior.epsr,
            sources_m=sources.tolist(), receivers_m=receivers.tolist(),
            strengths=complex_record(problem.source_strengths), observations=complex_record(truth_data),
            truth=shape_record(dimensionless(truth)))
        for initial in ("circle", "ellipse", "star"):
            geometry = target.geometry_config(target.default_num_nodes)
            extracted = build_ordered_sdf_geometry(_initial_teacher(initial), geometry).curve
            state = fit_cartesian_fourier_curve_state(extracted, maximum_mode=6,
                                                      component_id="legacy-comparison")
            data = dict(shared, initial_name=initial, geometry_config=asdict(geometry),
                initial_cartesian_cosine=state.cosine_coefficients.tolist(),
                initial_cartesian_sine=state.sine_coefficients.tolist(),
                initial=shape_record(dimensionless(from_cartesian(state))))
            case = output/"inputs"/f"{initial}-to-{target_name}"
            case.mkdir(parents=True)
            write(case/"input.json", data)
            print(json.dumps(dict(prepared=case.name)), flush=True)


def observations(data):
    origin = np.array([CENTER.real, CENTER.imag])
    sources = (np.array(data["sources_m"])-origin)/LENGTH
    receivers = (np.array(data["receivers_m"])-origin)/LENGTH
    strengths = complex_array(data["strengths"])
    values = complex_array(data["observations"])
    return tuple(Observation(k, PointSourceAcquisition(sources, receivers, strength), values[:, i])
                 for i, (k, strength) in enumerate(zip(data["wavenumbers"], strengths)))


class LegacyCatalogPolicy(AtlasPolicy):
    """Storage qualification and a bounded terminal loop, shared by all new arms."""
    def storage_for(self, wavenumber, perimeter, band, previous_curve_modes):
        return max(128, super().storage_for(wavenumber, perimeter, band, previous_curve_modes))

    @staticmethod
    def progressed(context):
        # No truth/holdout enters stopping. Repeating a completed frequency
        # must produce meaningful data decrease, not merely accept tiny steps.
        if not AtlasPolicy.progressed(context):
            return False
        result = context.history[-1].result
        if result.stop_reason in ("data_fit", "stationary", "small_step", "no_acceptable_step"):
            return False
        history = [r for r in result.history if "relative_residual" in r]
        if len(history) >= 2:
            before, after = history[0]["relative_residual"], history[-1]["relative_residual"]
            return before-after > 1e-4*max(before, 1e-15)
        return False


def run_new(data, arm, manifest, directory):
    obs = observations(data)[:len(TRAIN)]
    work = Work(max_forwards=manifest["max_forward_frequency_solves"],
                max_seconds=manifest["max_seconds"])
    config = FitConfig(**manifest["new_config"])
    policy = LegacyCatalogPolicy(obs, data["contrast"], work, mode=arm, config=config)
    shape = load_shape(data["initial"])
    trace = []
    def checkpoint(record):
        nonlocal shape
        if record.committed:
            shape = record.result.shape
        row = dict(index=record.index, k=record.decision.stage.wavenumber,
            stage=asdict(record.decision.stage), stop=record.result.stop_reason,
            committed=record.committed, shape=shape_record(shape),
            forwards=work.attempted, residual=float(record.result.relative_residual)
                if np.isfinite(record.result.relative_residual) else None,
            seconds=perf_counter()-work.started)
        trace.append(row)
        write(directory/"checkpoint.json", row)
        write(directory/"trajectory.json", trace)
    try:
        result = run_adaptive(shape, obs, data["contrast"], policy, work=work,
            max_decisions=manifest["new_max_decisions"], on_decision=checkpoint)
        shape, stop = result.shape, result.stop_reason
        failure = None
    except BudgetExceeded:
        stop, failure = "budget_exhausted", None
    except Exception as exc:
        stop, failure = "failed", f"{type(exc).__name__}: {exc}"
    elapsed = perf_counter()-work.started
    # Probe records can contain NaNs when a model cannot be evaluated. Replace
    # these by null before writing portable, strictly valid JSON.
    def clean(value):
        if isinstance(value, dict): return {k: clean(v) for k,v in value.items()}
        if isinstance(value, list): return [clean(v) for v in value]
        if isinstance(value, float) and not np.isfinite(value): return None
        return value
    write(directory/"probes.json", clean(policy.probes))
    return shape, dict(stop=stop, failure=failure, forwards=work.attempted,
        work=work.summary(), elapsed_seconds=elapsed, decisions=len(trace),
        highest_wavenumber=max([x["k"] for x in trace], default=None),
        probe_forwards=sum(x["forwards"] for x in policy.probes)), trace


def run_legacy(data, manifest, directory):
    """Existing Cartesian optimizer/config and cumulative-frequency schedule."""
    import torch
    from run_sdf_inverse_comparison import _build_problem
    from run_mlp_sdf_inverse_comparison import (_frequency_continuation_plan,
        _effective_stage_budget, _mode_budget, CONTINUATION_CUMULATIVE_FREQUENCIES)
    from sdf_inverse import (AlternatingNeuralInverseConfig, NeuralRedistanceConfig,
        ComplexScatteredData, run_alternating_neural_inverse, predict_paired_curve_response)
    from sdf_inverse.explicit_fourier import CartesianFourierCurveState
    from sdf_inverse.geometry import OrderedSDFGeometryConfig
    from sdf_inverse.curve_updates import cartesian_fourier_state_curve
    from gpr_bem_kress.execution import execution

    geometry = OrderedSDFGeometryConfig(**data["geometry_config"])
    state = CartesianFourierCurveState(data["initial_cartesian_cosine"],
        data["initial_cartesian_sine"], "legacy-comparison")
    curve = cartesian_fourier_state_curve(state, geometry_config=geometry)
    current_shape = load_shape(data["initial"])
    config = AlternatingNeuralInverseConfig(
        redistance=NeuralRedistanceConfig(bounds=geometry.bounds), max_iterations=150,
        maximum_mode=6, maximum_modal_field_update_m=0.002,
        geometry_change_tolerance_m=0.0002, direct_curve_retraction="cartesian_fourier",
        distillation_policy="curve_only", tangential_penalty_weight=0.,
        maximum_parameter_speed_ratio=16., regauge_to_polar_angle=True)
    started, forwards, accepted, trace = perf_counter(), 0, 0, []
    def predictor(curve, problem, geometry, **kwargs):
        nonlocal forwards
        count = len(problem.angular_frequencies)
        if (forwards+count > manifest["max_forward_frequency_solves"]
                or perf_counter()-started >= manifest["max_seconds"]):
            raise BudgetExceeded("Shared frequency-solve/time budget exhausted.")
        forwards += count
        with execution(kernels="reference", device="cpu"):
            return predict_paired_curve_response(curve, problem, geometry, **kwargs)
    values = complex_array(data["observations"])
    plan = _frequency_continuation_plan(TRAIN, 150, strategy=CONTINUATION_CUMULATIVE_FREQUENCIES)
    stop, failure, reached = "not_started", None, None
    try:
        for stage in plan:
            problem = _build_problem(stage.train_frequencies_ghz,
                                    data["sources_m"], data["receivers_m"])
            count = len(stage.train_frequencies_ghz)
            mode = min(6, _mode_budget(problem, curve.points, None)["maximum_mode"]+1)
            budget = _effective_stage_budget(stage=stage.stage, stage_count=len(plan),
                planned_max_iterations=stage.max_iterations, total_iterations=150,
                accepted_updates_before_stage=accepted)
            def progress(item):
                nonlocal current_shape, reached
                # Stored Cartesian curves are sampled uniformly in their own
                # parameter. Recover the exact K6 polynomial for checkpoints.
                points = np.asarray(item.geometry_points)
                current_shape = dimensionless(FourierCurve.from_samples(points[:, 0]+1j*points[:, 1], 6))
                reached = data["wavenumbers"][count-1]
                row = dict(index=len(trace), stage=stage.stage, k=reached,
                    shape=shape_record(current_shape), forwards=forwards,
                    residual=float(item.relative_l2_error), seconds=perf_counter()-started)
                trace.append(row)
                write(directory/"checkpoint.json", row)
                write(directory/"trajectory.json", trace)
            result = run_alternating_neural_inverse(torch.nn.Identity(),
                ComplexScatteredData(problem, values[:, :count]), geometry, solver="kress",
                config=replace(config, max_iterations=budget, maximum_mode=mode),
                progress_callback=progress, initial_curve=curve,
                initial_cartesian_curve_state=state, curve_forward_predictor=predictor)
            curve, state = result.final_curve, result.final_cartesian_curve_state
            current_shape = dimensionless(from_cartesian(state))
            accepted += len(result.iterations)-1
            stop = result.stop_reason
    except BudgetExceeded:
        stop = "budget_exhausted"
    except Exception as exc:
        stop, failure = "failed", f"{type(exc).__name__}: {exc}"
    return current_shape, dict(stop=stop, failure=failure, forwards=forwards,
        elapsed_seconds=perf_counter()-started, highest_wavenumber=reached,
        probe_forwards=0, optimizer="legacy Cartesian K6 finite-difference LM",
        config=asdict(config)), trace


def score(data, shape):
    truth = load_shape(data["truth"])
    error, bound = boundary_distance(truth, shape)
    scores = dict(boundary_m=error*LENGTH, boundary_upper_m=(error+bound)*LENGTH,
                  area=area_error(truth, shape))
    predictions, refinements = [], []
    obs = observations(data)
    length = shape.nodes(grid_size(shape.band)).perimeter
    for observation in obs:
        nodes = 2*int(np.ceil(max(256, 2*(shape.band+1)+2,
            30*length*observation.wavenumber*max(1, np.sqrt(data["contrast"]))/ (2*np.pi))/2))
        coarse = solve(shape, observation.wavenumber, data["contrast"], observation.acquisition, nodes).prediction
        fine = solve(shape, observation.wavenumber, data["contrast"], observation.acquisition, 2*nodes).prediction
        predictions.append(fine)
        refinements.append(float(np.linalg.norm(coarse-fine)/max(np.linalg.norm(fine), 1e-300)))
    predicted = np.asarray(predictions).T
    expected = complex_array(data["observations"])
    errors = np.linalg.norm(predicted-expected, axis=0)/np.linalg.norm(expected, axis=0)
    def relative(section):
        return float(np.linalg.norm((predicted-expected)[:, section])/np.linalg.norm(expected[:, section]))
    scores.update(train_relative=relative(slice(0, 3)), holdout_relative=relative(slice(3, None)),
        per_frequency_relative=errors.tolist(), worst_holdout_relative=float(max(errors[3:])),
        endpoint_field_refinement=max(refinements))
    return scores


def run_one(output, case, arm):
    manifest = json.loads((output/"manifest.json").read_text())
    if source_hashes() != manifest["source_sha256"]:
        raise RuntimeError("Numerical sources changed after preparation; use a fresh bundle.")
    path = output/"inputs"/case/"input.json"
    data = json.loads(path.read_text())
    directory = output/"runs"/case/arm
    directory.mkdir(parents=True, exist_ok=False)
    common = dict(case=case, arm=arm, input_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    write(directory/"manifest.json", common)
    shape, result, trace = (run_legacy(data, manifest, directory) if arm == "legacy_cartesian"
                            else run_new(data, arm, manifest, directory))
    record = dict(common, **result, shape=shape_record(shape))
    # Persist before evaluation so a slow/failed evaluator cannot erase a run.
    record.pop("config", None)
    write(directory/"result.json", record)
    try:
        scores = score(data, shape)
        gate = manifest["gates"]
        passed = (scores["boundary_upper_m"] <= gate["boundary_upper_m"]
            and scores["train_relative"] <= gate["train_relative"]
            and scores["worst_holdout_relative"] <= gate["holdout_relative"]
            and scores["endpoint_field_refinement"] <= gate["endpoint_field_refinement"]
            and result["failure"] is None)
        record.update(scores=scores, passed=passed)
    except Exception as exc:
        record.update(passed=False, evaluation_failure=f"{type(exc).__name__}: {exc}")
    write(directory/"result.json", record)
    print(json.dumps({k: record.get(k) for k in ("case", "arm", "stop", "forwards", "passed", "scores")}), flush=True)


def report(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    manifest = json.loads((output/"manifest.json").read_text())
    rows, records = [], []
    for case in manifest["cases"]:
        data = json.loads((output/"inputs"/case/"input.json").read_text())
        digest = hashlib.sha256((output/"inputs"/case/"input.json").read_bytes()).hexdigest()
        for arm in manifest["arms"]:
            path = output/"runs"/case/arm/"result.json"
            record = json.loads(path.read_text()) if path.exists() else dict(case=case, arm=arm, stop="missing", passed=False)
            if path.exists() and record["input_sha256"] != digest:
                raise RuntimeError("Input hash mismatch.")
            records.append(record)
            s = record.get("scores", {})
            def number(key, factor=1.):
                return f"{s[key]*factor:.4g}" if key in s else "—"
            rows.append(f"| {case} | {arm} | {record['stop']} | {record.get('forwards', '—')} "
                f"| {record.get('elapsed_seconds', 0):.1f} | {number('boundary_m', 1000)} "
                f"| {number('train_relative')} | {number('worst_holdout_relative')} "
                f"| {'PASS' if record.get('passed') else 'FAIL'} |")
    write(output/"comparison.json", records)
    text = ["# SC-018 — previous explicit Fourier single-object cases", "",
        "Shared independent observations, initial curves and per-arm budgets. "
        "Boundary error is symmetric sampled Hausdorff; acceptance uses its conservative upper bound. "
        "Held-out error below is the worst of three unused frequencies.", "",
        "| Case | Arm | Stop | Frequency solves | Seconds | Boundary mm | Train rel. | Worst holdout rel. | Gates |",
        "|---|---|---|---:|---:|---:|---:|---:|---|", *rows, "",
        "![Recovered boundaries](boundaries.png)", "",
        "## Comparison contract", "",
        *["- "+item for item in manifest["differences"]], "",
        "All new arms use SC-017's optimizer settings with 50 updates per decision, "
        "minimum storage band 128, and a shared terminal progress guard. "
        "The legacy arm uses the existing cumulative-frequency Cartesian K6 optimizer "
        "with its original 150-update allocation and 2-mm modal step limit.", "",
        f"Per-arm caps: {manifest['max_forward_frequency_solves']} single-frequency forward solves "
        f"and {manifest['max_seconds']:g} seconds. Preparation and endpoint scoring are excluded for all arms. "
        "Elapsed times include checkpoint writing and concurrent resource contention; they are descriptive.", "",
        "Recovery gates: boundary upper bound ≤1 mm, training relative L2 ≤0.003, "
        "worst holdout relative L2 ≤0.05, N/2N endpoint field discrepancy ≤1e-6. "
        "A passed gate does not imply nanometre parity with the historical star recovery.", "",
        "Inputs, every checkpoint and endpoint are portable JSON. Input and numerical-source "
        "hashes are checked. Failures and budget stops remain in the table."]
    (output/"README.md").write_text("\n".join(text)+"\n")
    fig, axes = plt.subplots(2, 3, figsize=(12, 8))
    colors = dict(zip(ARMS, ("black", "C0", "C1", "C2", "C3")))
    for ax, case in zip(axes.ravel(), manifest["cases"]):
        data = json.loads((output/"inputs"/case/"input.json").read_text())
        for key, style, label in (("truth", "k--", "truth"), ("initial", "k:", "initial")):
            points = physical(load_shape(data[key])).values(4096)
            ax.plot(points.real, points.imag, style, lw=1.5, label=label)
        for r in records:
            if r["case"] == case and "shape" in r:
                points = physical(load_shape(r["shape"])).values(4096)
                ax.plot(points.real, points.imag, color=colors[r["arm"]], lw=1, alpha=.8, label=r["arm"])
        ax.set_title(case)
        ax.set_aspect("equal")
        ax.legend(fontsize=6)
        ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(output/"boundaries.png", dpi=160)
    plt.close(fig)
    print("\n".join(rows), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--one", nargs=2, metavar=("CASE", "ARM"))
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    parser.add_argument("--max-forwards", type=int, default=6000)
    parser.add_argument("--max-seconds", type=float, default=600)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.output, args.max_forwards, args.max_seconds)
    if args.one:
        run_one(args.output, *args.one)
    if args.run:
        (args.output/"logs").mkdir(exist_ok=True)
        def job(case, arm):
            command = [sys.executable, "-m", __package__+".legacy_cases", "--output", str(args.output), "--one", case, arm]
            with (args.output/"logs"/f"{case}-{arm}.log").open("w") as log:
                limit = json.loads((args.output/"manifest.json").read_text())["max_seconds"] + 180
                try:
                    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=limit)
                    status = result.returncode
                except subprocess.TimeoutExpired:
                    status = "process_timeout"
            write(args.output/"logs"/f"{case}-{arm}.status.json", dict(process_returncode=status))
            print(json.dumps(dict(case=case, arm=arm, process_returncode=status)), flush=True)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs = [pool.submit(job, c, a) for c in args.cases for a in args.arms]
            for future in as_completed(jobs): future.result()
        report(args.output)
    elif args.report:
        report(args.output)


if __name__ == "__main__":
    main()
