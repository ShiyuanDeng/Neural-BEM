import json, pathlib, sys
from concurrent.futures import ProcessPoolExecutor
from experiments.modal_atlas.analyze import analyze
d = pathlib.Path(sys.argv[1])
paths = sorted(d.glob('*.npz'))
with ProcessPoolExecutor(11) as pool:
    res = dict(zip([p.stem.replace('__', '/') for p in paths], pool.map(analyze, paths)))
pathlib.Path(sys.argv[2]).write_text(json.dumps(res))
