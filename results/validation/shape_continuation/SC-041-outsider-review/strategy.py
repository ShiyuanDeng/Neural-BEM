"""Outsider strategy runs for kite: the SC-038 M 11/15/19 release with a different curve band K.

Control (already on disk): SC-038/SC-040 release with K=192, which reaches RMS 0.1096 mm
at M=19 and carries a spurious 0.09 mm-radius flank feature. Each arm starts from the same
SC-035 stage-4 K=20 endpoint (before the feature exists), keeps every backend setting,
frequency weight, tolerance and node count (768/1536) of the dense kite stages, and changes
only `curve_modes`. Truth is used only for post-hoc scoring.

    python strategy.py K [label]
"""
import importlib.util
import json
from dataclasses import replace
from pathlib import Path
import sys
import time
import traceback

import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sc038 = load('sc038_run', RESULTS/'SC-038-update-band-release/run.py')
sc041 = load('sc041_run', RESULTS/'SC-041-atlas-decisions/run.py')

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.lm_backend import Ledger, fit_stage, stage_record, NORMAL_RETURN, STAGE_QUOTA
from ordered_boundary.validation_cache import geometry_validation

STAGE_SECONDS = 900
STAGE_UNITS = 1500


def main(K, label=None, start=None):
    label = label or f'K{K}'
    folder = HERE/'strategies'/label
    folder.mkdir(parents=True, exist_ok=False)
    stages, config, _ = sc038.schedules('kite', 'release_m')
    stages = [replace(s, curve_modes=K, nodes=768, refined_nodes=1536, quota=STAGE_UNITS) for s in stages]
    if start is None:
        curve, _ = sc038.prefix('kite')                  # SC-035 stage 4, K=20
        source = 'SC-035 kite low stage_4 endpoint (K=20)'
    else:
        curve, source = start
    if curve.band < K:
        curve = sc038.resize(curve, K)
    elif curve.band > K:
        c = np.array(curve.coefficients)[curve.band-K:curve.band+K+1]
        curve = FourierCurve(c)
        source += f', truncated to K={K}'
    update = sc038.ProjectedUpdate(sc.LENGTH)
    record = dict(label=label, K=K, source=source, stage_seconds=STAGE_SECONDS, stages=[stage_record(s) for s in stages],
                  initial_score=sc041.geometry_score('kite', curve), results=[])
    states = []
    for stage in stages:
        ledger = Ledger(cap=STAGE_UNITS, seconds=STAGE_SECONDS)
        ledger.begin_stage(stage.label, stage.quota)

        def checkpoint(i, value, stage=stage, ledger=ledger):
            states.append(dict(stage=stage.label, M=stage.update_modes, iteration=i, loss=value.loss,
                               curve=ast.curve_record(value.curve), work=ledger.snapshot()))
            (folder/'accepted.json').write_text(json.dumps(dict(states=states)) + '\n')

        started = time.time()
        try:
            with geometry_validation('cache'):
                result = fit_stage(curve, stage, ac.contrast(), update, config, ledger, on_accept=checkpoint)
        except Exception:
            record['results'].append(dict(stage=stage.label, traceback=traceback.format_exc()))
            break
        curve = result.curve
        row = dict(stage=stage.label, M=stage.update_modes, outcome=result.outcome, stop=result.stop_reason,
                   detail=result.detail, initial_loss=result.initial_loss, final_loss=result.final_loss,
                   units=ledger.units, seconds=time.time()-started, score=sc041.geometry_score('kite', curve),
                   curve=ast.curve_record(curve))
        record['results'].append(row)
        print(label, stage.label, row['outcome'], row['stop'], f"loss {row['final_loss']:.4g}",
              {k: round(v, 5) for k, v in row['score'].items()}, row['units'], flush=True)
        (folder/'result.json').write_text(json.dumps(record, indent=1) + '\n')
        if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
            break
    (folder/'result.json').write_text(json.dumps(record, indent=1) + '\n')


if __name__ == '__main__':
    main(int(sys.argv[1]), *sys.argv[2:3])
