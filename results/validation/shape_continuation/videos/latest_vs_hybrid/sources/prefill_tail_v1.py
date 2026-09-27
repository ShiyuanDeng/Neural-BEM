"""Prepare three independent later kite states with the unchanged renderer.

The main scene worker is still in block 1. These block 2/3 states are selected
by their recorded position, never by quality. Shared display cache writes are
atomic; auxiliary numerical work is retained separately in prefill_work.json.
"""
from concurrent.futures import ProcessPoolExecutor
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def worker(position):
    spec = importlib.util.spec_from_file_location('prefill_renderer', HERE / 'render.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tracks, _, sources = module.collect('kite', 'fixed')
    phase, iteration = position
    step = next(s for s in tracks[1] if s['phase'] == phase and s['iteration'] == iteration)
    truth = module.ast.curve_from(module.read(module.ast.source_folder('kite') / 'truth.json'))
    expected = 1000 * module.symmetric_rms_distance(module.curve_for_step(step), truth.values(16384), module.sc.LENGTH)
    # Reuse the entire existing numerical and refinement path; only select a
    # single stored state for this independent preparation job.
    module.collect = lambda case, policy: ([[step], [step]], (expected, expected), sources)
    folder = HERE / 'prefill' / f'phase{phase}_step{iteration}'
    (folder / 'display_cache').mkdir(parents=True, exist_ok=True)
    link = folder / 'display_cache/kite'
    if not link.exists():
        link.symlink_to((HERE / 'display_cache/kite').resolve(), target_is_directory=True)
    original_write = module.write

    def atomic_write(path, value):
        path = Path(path)
        temp = path.with_name(path.name + f'.prefill{phase}_{iteration}.tmp')
        original_write(temp, value)
        temp.replace(path)

    module.write = atomic_write
    result = module.prepare_case(('kite', 'fixed', str(folder)))
    return dict(position=position, **result)


if __name__ == '__main__':
    positions = [(11, 1), (11, 2), (12, 1)]
    with ProcessPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(worker, positions))
    result = dict(rows=rows, forward_solves=sum(r['diagnostic_work']['attempted'] for r in rows),
                  reciprocal_batches=sum(r['diagnostic_work']['jacobians'] for r in rows),
                  selection='SC-043 fixed kite blocks 2 and 3, positive accepted iteration indices')
    (HERE / 'prefill_work.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
