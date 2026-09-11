"""Is the neural gradient chain still correct at late states?

A review diagnostic for the gradient-diagnosis addendum. It re-runs, at frozen
saved accepted states, the correctness checks the long run performed only at
state 0, and splits the chain so the two halves can be blamed separately:

    weights --[A] Method-B reverse--> curve jets --[B] Kress pullback--> dL

    stage B   Kress objective adjoint and geometry pullback
    stage A   extraction, projection, Fourier fit, arc-length refit reverse
    A o B     the composite the inverse actually used

Each stage is compared against central finite differences of the production
forward path at the same frozen state. No inverse is run, no optimizer step is
taken, no production file is written and no saved artifact is modified. Weights
are restored after every perturbation.

Stage A needs no BEM solve at all: it contracts the differentiable Method-B
replay with a fixed random covector and finite-differences the production
geometry build. Stage B and the composite need forward solves.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT), str(ROOT / "solvers")]

import run_implicit_mlp_iteration2_matched as matched  # noqa: E402
from sdf_inverse.geometry import (  # noqa: E402
    OrderedSDFGeometryConfig, OrderedSDFGeometryError, build_ordered_sdf_geometry,
)
from sdf_inverse.implicit_adjoint import implicit_mlp_data_gradient  # noqa: E402
from sdf_inverse.method_b_pullback import build_method_b_pullback  # noqa: E402
from sdf_inverse.models import (  # noqa: E402
    SirenImplicitField2D, build_siren_parameter_controller,
)
from sdf_inverse.optimization import ComplexScatteredData  # noqa: E402

RUN = (
    ROOT / "results/validation/implicit_mlp_adjoint/iteration-02-final"
    / "long-acquisition-20260908T174300326691Z"
)
ARMS = {"E0": ("paired", (0.5, 1.5)), "E1": ("multistatic", (0.5, 1.5))}
STEPS = (2.0e-5, 1.0e-5, 5.0e-6)
SEED = 724


def load_state(arm, state, geometry_config, initial):
    constructor = dict(initial["constructor"])
    constructor["dtype"] = torch.float64
    model = SirenImplicitField2D(**constructor)
    checkpoint = torch.load(
        RUN / arm / f"accepted_{state:03d}.pt", map_location="cpu", weights_only=False
    )
    model.load_state_dict(checkpoint["state_dict"])
    return model, build_siren_parameter_controller(model)


def relative(analytic, finite):
    return abs(finite - analytic) / max(abs(finite), abs(analytic), 1e-12)


def stage_a(model, controller, geometry_config, rng):
    """Method-B reverse against finite differences of the production build.

    Contract the differentiable replay's point and first-derivative tensors
    with one fixed random covector, backpropagate to the weights, and compare
    the directional derivative with central differences of the same scalar
    formed from the production ``build_ordered_sdf_geometry`` curve.
    """

    curve = build_ordered_sdf_geometry(model, geometry_config).curve
    pullback = build_method_b_pullback(model, geometry_config, reference_curve=curve)
    covector_points = torch.tensor(
        rng.normal(size=tuple(pullback.points.shape)), dtype=pullback.points.dtype
    )
    covector_first = torch.tensor(
        rng.normal(size=tuple(pullback.first_derivatives.shape)),
        dtype=pullback.first_derivatives.dtype,
    )
    scalar = (covector_points * pullback.points).sum() + (
        covector_first * pullback.first_derivatives
    ).sum()
    parameters = [p for p in model.parameters() if p.requires_grad]
    grads = torch.autograd.grad(scalar, parameters, allow_unused=True)
    gradient = np.concatenate([
        (np.zeros(p.numel()) if g is None else g.detach().cpu().numpy().ravel())
        for p, g in zip(parameters, grads)
    ])

    vector = controller.parameter_vector()
    direction = rng.normal(size=vector.size)
    direction /= np.linalg.norm(direction)
    analytic = float(gradient @ direction)

    def probe(shift):
        controller.assign(vector + shift)
        built = build_ordered_sdf_geometry(model, geometry_config).curve
        points = torch.tensor(np.asarray(built.points), dtype=pullback.points.dtype)
        first = torch.tensor(
            np.asarray(built.first_derivatives), dtype=pullback.first_derivatives.dtype
        )
        return float((covector_points * points).sum() + (covector_first * first).sum())

    rows = []
    try:
        for step in STEPS:
            high = probe(step * direction)
            low = probe(-step * direction)
            finite = (high - low) / (2.0 * step)
            rows.append({"step": step, "analytic": analytic, "finite_difference": finite,
                         "relative_error": relative(analytic, finite)})
    finally:
        controller.assign(vector)
    return rows, float(pullback.maximum_replay_error)


def composite(model, controller, data, geometry_config, rng):
    """The production composite gradient against central differences of the loss."""

    vector = controller.parameter_vector()
    gradient, diagnostic = implicit_mlp_data_gradient(model, data, geometry_config)
    direction = rng.normal(size=vector.size)
    direction /= np.linalg.norm(direction)
    analytic = float(gradient @ direction)
    rows = []
    try:
        for step in STEPS:
            controller.assign(vector + step * direction)
            high = matched.data_loss(model, data, geometry_config)
            controller.assign(vector - step * direction)
            low = matched.data_loss(model, data, geometry_config)
            finite = (high - low) / (2.0 * step)
            rows.append({"step": step, "analytic": analytic, "finite_difference": finite,
                         "relative_error": relative(analytic, finite)})
    finally:
        controller.assign(vector)
    return rows, diagnostic, float(np.linalg.norm(gradient))


def report(rows, label):
    worst = max(row["relative_error"] for row in rows[-2:])
    print(f"    {label:22} " + "  ".join(
        f"h={row['step']:.0e}:{row['relative_error']:.2e}" for row in rows
    ) + f"  | worst of last two: {worst:.3e}")
    return worst


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("a", "all"), default="all")
    parser.add_argument("--states", default="")
    parser.add_argument("--arms", default="E0,E1")
    parser.add_argument("--steps", default="")
    args = parser.parse_args()
    global STEPS
    if args.steps:
        STEPS = tuple(float(value) for value in args.steps.split(","))

    print(__doc__)
    initial = torch.load(RUN / "shared_initial.pt", map_location="cpu", weights_only=False)
    geometry_config = OrderedSDFGeometryConfig(**initial["geometry_config"])
    observations = np.load(RUN / "observations.npz")
    print(f"geometry: {geometry_config.num_nodes} nodes, bandwidth "
          f"{geometry_config.bandwidth}, bounds {geometry_config.bounds}")
    print(f"finite-difference steps {STEPS}, seed {SEED}\n")

    summary = {}
    for arm, (acquisition, frequencies) in ARMS.items():
        if arm not in args.arms.split(","):
            continue
        trajectory = json.load(open(RUN / arm / "geometry_trajectory.json"))
        available = [entry["iteration"] for entry in trajectory]
        chosen = ([int(s) for s in args.states.split(",") if s]
                  or sorted({available[0], available[len(available) // 3],
                             available[2 * len(available) // 3], available[-2],
                             available[-1]}))
        data = ComplexScatteredData(
            matched.build_problem(acquisition, frequencies), observations[arm], np.ones(2)
        )
        print(f"########## {arm}: {acquisition}, states {chosen} of 0..{available[-1]} ##########")
        for state in chosen:
            if state not in available:
                print(f"  state {state}: no saved checkpoint"); continue
            model, controller = load_state(arm, state, geometry_config, initial)
            rng = np.random.default_rng(SEED)
            print(f"  --- state {state} ---")
            try:
                rows, replay = stage_a(model, controller, geometry_config, rng)
                worst_a = report(rows, "A  Method-B reverse")
                print(f"    {'':22} replay error {replay:.3e} m")
            except (OrderedSDFGeometryError, RuntimeError) as exc:
                worst_a, replay = None, None
                print(f"    A  Method-B reverse     UNAVAILABLE: {type(exc).__name__}: {exc}")
            worst_c, norm = None, None
            if args.stage == "all":
                try:
                    rows, diagnostic, norm = composite(
                        model, controller, data, geometry_config, np.random.default_rng(SEED)
                    )
                    worst_c = report(rows, "AoB composite")
                    print(f"    {'':22} gradient norm {norm:.4f}, "
                          f"replay {diagnostic['method_b_replay_maximum_error']:.3e} m")
                except (OrderedSDFGeometryError, RuntimeError) as exc:
                    print(f"    AoB composite          UNAVAILABLE: {type(exc).__name__}: {exc}")
            summary[f"{arm}/{state}"] = {"stage_a": worst_a, "composite": worst_c,
                                         "replay_error_m": replay, "gradient_norm": norm}
        print()

    print("########## summary: worst relative error over the two smallest steps ##########")
    print(f"  {'state':10} {'A Method-B reverse':>20} {'AoB composite':>16} {'replay error m':>16}")
    for key, value in summary.items():
        def fmt(x, spec=".3e"):
            return "n/a" if x is None else format(x, spec)
        print(f"  {key:10} {fmt(value['stage_a']):>20} {fmt(value['composite']):>16} "
              f"{fmt(value['replay_error_m']):>16}")


if __name__ == "__main__":
    main()
