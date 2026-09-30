"""One fresh D attempt; failure is a nonzero exit, original driver writes all evidence."""
import json
import sys
import time
from pathlib import Path
from experiments.modal_atlas import damped_screen as ds

mode, contrast, scene, destination = sys.argv[1], float(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
if mode == 'accelerated':
    from runtime import install
    install()
elif mode != 'baseline':
    raise ValueError(mode)
target = destination / mode / 'D' / ds.tag(contrast) / scene
if target.exists():
    raise FileExistsError('Fresh output required: ' + str(target))
t = time.perf_counter()
row = ds.attempt('D', contrast, scene, root=destination / mode)
print('WALL_SECONDS', time.perf_counter()-t, flush=True)
if row['outcome'] == 'EXCEPTION':
    raise RuntimeError(row['traceback'])
print('SUMMARY', json.dumps(dict(mode=mode,contrast=contrast,scene=scene,
      outcome=row['outcome'],recovered=row['recovered'],metrics=row['metrics'],
      units=row['fit_and_localization_units'],seconds=row['seconds'])),flush=True)
