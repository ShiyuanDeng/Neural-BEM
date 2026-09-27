"""Known-neighbour versus unknown-neighbour information at identical scaling."""
import hashlib
import json
from pathlib import Path

import numpy as np

from qualify import HERE, ROOT, LENGTH, setup, scene, manifest, write, verify, record_scene
from strategies import stage, CONFIG
from experiments.shape_continuation.forward import solve
from experiments.shape_continuation.inverse import Observation
from experiments.shape_continuation.lm_backend import Ledger, Objective
from experiments.shape_continuation.multi_object import MultiCurve, MultiUpdate, conditional_information
from qualify import ProjectedUpdate


def run():
    if (HERE / "atlas.json").exists():
        raise FileExistsError("Preserve the existing atlas.")
    if not json.loads((HERE / "qualification.json").read_text())["passed"]:
        raise RuntimeError("Qualification gate failed.")
    frozen = manifest(dict(nodes=256, update_modes=[3, 5], cap=200, seconds=600,
        metric="per-object RMS metres", data_metric="same coupled-observation frequency scales for all comparisons"))
    for source in (Path(__file__), HERE / "strategies.py"):
        frozen["source_sha256"][str(source.relative_to(ROOT))] = hashlib.sha256(source.read_bytes()).hexdigest()
    write(HERE / "atlas_manifest.json", frozen)
    catalog, contrast, _ = setup()
    ledger = Ledger(cap=200, seconds=600, endpoint_reserve=0)
    ledger.begin_stage("atlas", None)
    rows = []
    for sep in (.14, .20):
        current = scene(sep, initial=True)
        # Same physical acquisition and observation-derived scaling for all three
        # comparisons; alone does not claim it has the same measured field.
        ledger.reserve(4)
        observations = []
        for o in catalog:
            ledger.charge("solve", "observations")
            values = solve(scene(sep), o.wavenumber, contrast, o.acquisition, 512).prediction
            observations.append(Observation(o.wavenumber, o.acquisition, values))
        for modes in (3, 5):
            update = MultiUpdate(ProjectedUpdate(LENGTH))
            obj = Objective(stage(observations, modes), contrast, CONFIG, ledger)
            base = obj.production(current, "coupled")
            space = update.prepare(current, modes, current.band)
            jac = obj.jacobian(base, update, space)
            blocks = [jac[:, s] for s in space.slices]
            metrics = [update.base.metric(s, "mass") for s in space.local_spaces]
            conditional = conditional_information(blocks, metrics)
            alone = MultiCurve((current.components[1],), (current.ids[1],))
            alone_state = obj.production(alone, "alone")
            alone_space = update.prepare(alone, modes, alone.band)
            alone_jac = obj.jacobian(alone_state, update, alone_space)
            alone_row = conditional_information((alone_jac,), (metrics[1],))[0]
            rows.append(dict(separation_m=sep, modes=modes, state=record_scene(current),
                known_neighbour_singular_values=conditional[1]["singular_values"],
                unknown_neighbour_singular_values=conditional[1]["conditional_singular_values"],
                target_alone_singular_values=alone_row["singular_values"],
                conditional_fractions=[x["conditional_fraction"] for x in conditional],
                rank_threshold=conditional[1]["absolute_rank_threshold"],
                nuisance_loss_min_eigenvalue=float(np.linalg.eigvalsh(
                    np.linalg.solve(np.linalg.cholesky(metrics[1]), blocks[1].T) @
                    np.linalg.solve(np.linalg.cholesky(metrics[1]), blocks[1].T).T -
                    conditional[1]["conditional_gram"]).min())))
            write(HERE / "atlas.json", dict(rows=rows, work=ledger.snapshot()))
    verify(frozen)
    write(HERE / "atlas.json", dict(status="COMPLETE", rows=rows, work=ledger.snapshot()))


if __name__ == "__main__":
    run()
