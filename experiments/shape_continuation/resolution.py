"""Forward/Jacobian resolution and timing screen, independent of optimization."""
import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from .forward import Acquisition, Work, solve, shape_jacobian
from .geometry import normal_basis
from .run import fixture, provenance, relative


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows, arrays = [], {}
    for scene in ("ellipse", "glider"):
        shape = fixture(scene)
        for k in (1., 4., 8.):
            acquisition = Acquisition.ring(int(10*k), int(10*k))
            previous_field = previous_jacobian = None
            for nodes in (64, 128, 256, 512):
                work = Work(max_forwards=1)
                started = perf_counter()
                state = solve(shape, k, 1.44, acquisition, nodes, work=work)
                forward_seconds = perf_counter() - started
                started = perf_counter()
                jacobian = shape_jacobian(state, normal_basis(state.curve, int(3 * 1.2 * k)), work=work)
                row = dict(scene=scene, wavenumber=k, nodes=nodes, forward_seconds=forward_seconds,
                           jacobian_seconds=perf_counter() - started, system_residual=state.system_residual,
                           field_difference=None if previous_field is None else relative(previous_field, state.prediction),
                           jacobian_difference=None if previous_jacobian is None else relative(previous_jacobian, jacobian),
                           work=work.summary())
                rows.append(row)
                prefix = f"{scene}_k{k:g}_n{nodes}"
                arrays[prefix+"_field"] = state.prediction
                # Retain selected fixed real contractions rather than large Jacobian tensors.
                direction = np.cos(np.arange(jacobian.shape[-1]))
                arrays[prefix+"_tangent"] = jacobian @ direction
                previous_field, previous_jacobian = state.prediction, jacobian
                print(json.dumps(row), flush=True)
                (args.output / "screen.json").write_text(json.dumps(dict(provenance=provenance(), rows=rows), indent=2)+"\n")
    np.savez_compressed(args.output / "responses.npz", **arrays)


if __name__ == "__main__":
    main()
