"""Figure 1 preparation. Default: a zero-solve plan. --mode smoke is bounded."""
import argparse
from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from .continuation import Decision, ResolutionGate, run_adaptive
from .forward import Acquisition, BudgetExceeded, Work, solve
from .geometry import FourierCurve, grid_size, integer
from .inverse import FitConfig, Observation
from .metrics import area_error
from .run import fixture, provenance, relative
from .schedule import Stage, paper_wavenumbers


SOURCE = "https://arxiv.org/html/2210.11607v1"


def even_at_least(value):
    return 2 * int(np.ceil(value / 2))


@dataclass(frozen=True)
class Figure1Case:
    contrast: float
    k_stop: float = 30.
    inverse_points_per_wavelength: float = 70.
    data_points_per_wavelength: float = 100.
    # Reference `update_geom` bounds |tail|_2/|all|_2 by eps_curv=0.1 over
    # |n| > max(n_curv_min, M), with n_curv_min=20 in the authors' drivers.
    # Our gate is the energy fraction, hence the squared tolerance below.
    minimum_curvature_modes: int = 20
    config: FitConfig = FitConfig(backtracks=0, curvature_tail_tolerance=1e-2)

    def __post_init__(self):
        if self.contrast not in (.33, 10.):
            raise ValueError("Figure 1 contrasts are ki²/k² = 0.33 and 10.")
        if self.k_stop not in paper_wavenumbers():
            raise ValueError("k_stop must belong to the paper grid 1:0.25:30.")
        for value in (self.inverse_points_per_wavelength, self.data_points_per_wavelength):
            if not np.isfinite(value) or value <= 0:
                raise ValueError("Resolution factors must be positive.")
        integer(self.minimum_curvature_modes, "minimum_curvature_modes")

    @property
    def wavenumbers(self):
        return paper_wavenumbers()[paper_wavenumbers() <= self.k_stop]

    def stage(self, shape, k):
        """Eq.12 exterior-k storage; §2 shortest wavelength for quadrature.

        The trust-region band is the reference code's max(n_curv_min, M), not
        the manuscript's ⌈ck⌉: a band below the update's own highest harmonic
        refuses every unfiltered Gauss-Newton step at low frequency.
        Kress also requires N > 2K. Recomputed at frequency handoffs using
        the current perimeter, not within candidate updates (declared gap).
        """
        length = shape.nodes(grid_size(shape.band)).perimeter
        largest = k * max(1., np.sqrt(self.contrast))
        modes = int(np.floor(3 * largest))
        storage = max(shape.band, modes,
                      int(np.ceil(self.inverse_points_per_wavelength * length * k / (2*np.pi))))
        nodes = even_at_least(max(64, 2 * (storage + 1),
            self.inverse_points_per_wavelength * length * largest / (2*np.pi)))
        return Stage(float(k), modes, storage, nodes,
                     max(self.minimum_curvature_modes, modes))

    def data_nodes(self, truth, k):
        # The exact polar fixture is retained; this is mean points/wavelength.
        # N/2N field qualification is mandatory before observations are used.
        length = truth.nodes(grid_size(truth.band)).perimeter
        return even_at_least(max(64, 2 * (truth.band + 1),
            self.data_points_per_wavelength * length * k * max(1., np.sqrt(self.contrast)) / (2*np.pi)))


def campaign_plan(cases):
    """Geometry arithmetic only. Counts on the initial circle are estimates."""
    initial, truth = FourierCurve.circle(), fixture("glider")
    records = []
    for case in cases:
        stages = []
        for k in case.wavenumbers:
            stage = case.stage(initial, k)
            data_nodes = case.data_nodes(truth, k)
            stages.append(dict(initial_circle_stage=asdict(stage),
                directions=int(10*k), receivers=int(10*k), receiver_radius=10.,
                reference_nodes=[data_nodes, 2 * data_nodes],
                # One complex128 (2N)x(2N) matrix, NOT total peak memory.
                single_inverse_matrix_bytes=16 * (2 * stage.nodes) ** 2,
                single_fine_reference_matrix_bytes=16 * (4 * data_nodes) ** 2))
        records.append(dict(settings=asdict(case), stages=stages))
    return dict(status="plan_only", forward_solves=0, paper=SOURCE,
        target="Figure 1 boundary inverse; no volume inverse", snapshots=[1., 5., 10.],
        exact_replication=False, audit="experiments/shape_continuation/PAPER.md",
        cases=records)


def write_json(path, record):
    path.write_text(json.dumps(record, indent=2) + "\n")


def run_case(case, output, work):
    """Execute the declared case with a shared budget and durable checkpoints.

    This is a harness: truth is used only for observations and area scoring.
    Its strategy sees the regular PolicyContext, with no scoring information.
    """
    output.mkdir(parents=True, exist_ok=False)
    import shapely
    truth, initial = fixture("glider"), FourierCurve.circle()
    write_json(output / "manifest.json", dict(provenance(), case=asdict(case),
        shapely=shapely.__version__, geos=shapely.geos_version_string,
        max_forwards=work.max_forwards, max_seconds=work.max_seconds,
        work_before=work.summary(), paper=SOURCE))
    observations, checks, reports = [], [], []
    status = "incomplete"
    final = initial
    try:
        for index, k in enumerate(case.wavenumbers):
            acquisition = Acquisition.ring(int(10*k), int(10*k))
            nodes = case.data_nodes(truth, k)
            coarse = solve(truth, k, case.contrast, acquisition, nodes, work=work).prediction
            fine = solve(truth, k, case.contrast, acquisition, 2*nodes, work=work).prediction
            error = relative(coarse, fine)
            checks.append(dict(wavenumber=float(k), nodes=[nodes, 2*nodes],
                               relative_difference=error, passed=error <= 1e-7))
            np.savez_compressed(output / f"observation_{index:03d}.npz", truth=truth.coefficients,
                wavenumber=k, directions=acquisition.directions, receivers=acquisition.receivers,
                scattered=fine, coarse_scattered=coarse)
            write_json(output / "observations.json", checks)
            if error > 1e-7:
                status = "unqualified_observations"
                break
            observations.append(Observation(float(k), acquisition, fine))
        else:
            def strategy(context):
                index = len(context.history)
                if index == len(observations) or (index and not context.history[-1].committed):
                    return None
                k = observations[index].wavenumber
                return Decision(case.stage(context.shape, k), case.config, "paper fixed frequency ladder")

            def checkpoint(record):
                nonlocal final
                if record.committed:
                    final = record.result.shape
                report = dict(index=record.index, decision=asdict(record.decision),
                    committed=record.committed, stop_reason=record.result.stop_reason,
                    relative_residual=record.result.relative_residual,
                    history=record.result.history, trials=record.result.trials,
                    qualification=asdict(record.qualification) if record.qualification else None,
                    work_before=record.work_before, work_after=record.work_after)
                # Save the trajectory BEFORE optional evaluation can fail.
                np.savez_compressed(output / f"decision_{record.index:03d}.npz",
                    **{f"state_{i}": s.coefficients for i, s in enumerate(record.result.states)},
                    committed_shape=final.coefficients)
                path = output / f"decision_{record.index:03d}.json"
                write_json(path, report)
                reports.append(report)
                if record.committed:
                    report["area_error"] = area_error(truth, final,
                        count=max(4096, grid_size(final.band)))
                    write_json(path, report)

            result = run_adaptive(initial, observations, case.contrast, strategy,
                work=work, max_decisions=len(observations), qualify=ResolutionGate(),
                on_decision=checkpoint)
            final = result.shape
            status = result.stop_reason
            if status == "policy_stop":
                status = "ladder_completed" if all(r.committed for r in result.history) else "resolution_failed"
    except BudgetExceeded:
        status = "budget_exhausted"
    except Exception as exc:
        status = "failed"
        write_json(output / "failure.json", dict(type=type(exc).__name__, message=str(exc)))
        raise
    finally:
        np.savez_compressed(output / "endpoint.npz", shape=final.coefficients)
        summary = dict(status=status, exact_replication=False, case=asdict(case),
            observation_checks=checks, decisions=reports, work=work.summary())
        write_json(output / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "smoke", "run"), default="plan")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contrast", type=float, choices=(.33, 10.))
    parser.add_argument("--k-stop", type=float)
    parser.add_argument("--max-forwards", type=int)
    parser.add_argument("--max-seconds", type=float)
    args = parser.parse_args(argv)
    if args.mode == "run" and (args.max_forwards is None or args.max_seconds is None):
        parser.error("run requires explicit --max-forwards and --max-seconds.")
    if args.mode != "run" and (args.max_forwards is not None or args.max_seconds is not None):
        parser.error("Work overrides apply only to run; smoke has fixed small caps.")
    if args.mode == "smoke" and args.k_stop is not None:
        parser.error("smoke is fixed at k=1, one update per contrast.")
    try:
        if args.mode == "run":
            integer(args.max_forwards, "max_forwards")
            if not np.isfinite(args.max_seconds) or args.max_seconds <= 0:
                raise ValueError("max_seconds must be positive.")
        cases = [Figure1Case(c, k_stop=1. if args.mode == "smoke" else (
            args.k_stop if args.k_stop is not None else 30.))
            for c in ((args.contrast,) if args.contrast is not None else (.33, 10.))]
    except ValueError as exc:
        parser.error(str(exc))
    if args.mode == "smoke":
        cases = [replace(c, config=replace(c.config, max_iterations=1)) for c in cases]
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "plan.json", campaign_plan(cases))
    if args.mode == "plan":
        print(json.dumps(dict(status="plan_only", cases=len(cases), forward_solves=0)))
        return
    # Smoke limits cover BOTH contrasts, data, inverse AND resolution checks.
    work = Work(max_forwards=16 if args.mode == "smoke" else args.max_forwards,
                max_seconds=30. if args.mode == "smoke" else args.max_seconds)
    started = perf_counter()
    reports = []
    for case in cases:
        report = run_case(case, args.output / f"contrast_{case.contrast:g}", work)
        reports.append(dict(contrast=case.contrast, status=report["status"]))
        if report["status"] != "ladder_completed":
            break
    summary = dict(mode=args.mode, cases=reports, work=work.summary(),
                   elapsed_seconds=perf_counter()-started, exact_replication=False)
    write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
