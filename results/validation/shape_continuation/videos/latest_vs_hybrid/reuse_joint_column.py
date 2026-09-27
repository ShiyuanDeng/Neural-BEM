"""Reuse the unchanged joint order scores at kite's final block transition.

Changing nominal M changes only the inside/near summaries, not the fields,
residual, complete QR order column, frontier, spectrum or geometry. This
avoids another field evaluation after a parallel cache hit lost the in-memory
Jacobian. The full displayed column includes every computed order (0..48).
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def key(signature):
    return hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[:24]


def main():
    spec = importlib.util.spec_from_file_location('cache_reuse_renderer', HERE / 'render.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prepared = module.read(HERE / 'prefill/phase11_step2/prepared/kite.json')
    signature = prepared['tracks'][0][0]['signature']
    source = HERE / 'display_cache/kite' / (key(signature) + '.json')
    data = module.read(source)
    tracks, _, _ = module.collect('kite', 'fixed')
    step = next(s for s in tracks[1] if s['phase'] == 12 and s['iteration'] == 0)
    assert module.ta.shot_key(module.curve_for_step(step)) == signature['curve']
    assert signature['nodes'] == step['nodes'] and signature['active'] == list(range(19))
    assert step['update_modes'] == 40 and signature['M'] == 34
    d = np.asarray(data['column']) ** 2
    assert len(d) == module.av.BAND + 1 == 49
    assert abs(d[:35].sum() / d.sum() - data['inside']) < 1e-14
    assert abs(d[35:38].sum() / d.sum() - data['near']) < 1e-14
    data.update(signature=dict(signature, M=40), inside=float(d[:41].sum() / d.sum()),
                near=float(d[41:44].sum() / d.sum()))
    data['cache_reuse'] = dict(source=source.name, operation='Reaggregate the unchanged full QR order column at M40.',
                              source_sha256=module.sc.digest(source), new_field_solves=0)
    target = source.parent / (key(data['signature']) + '.json')
    if not target.exists():
        temp = target.with_suffix('.tmp')
        module.write(temp, data)
        temp.replace(target)
    module.write(HERE / 'joint_column_reuse.json', data['cache_reuse'])
    print('Reused unchanged geometry/frequencies/grid at M40; zero field solves.')


if __name__ == '__main__':
    main()
