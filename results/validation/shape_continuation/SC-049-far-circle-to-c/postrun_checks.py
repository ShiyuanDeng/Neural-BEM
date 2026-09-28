"""Inspect the failed endpoint: exact geometry checks and four CPU field controls.

No trajectory restart or changed numerical tolerances. Charged separately.
"""
import importlib.util
import os
from pathlib import Path
import time
import numpy as np
from experiments.shape_continuation import atlas_strategy_tests as ast, atlas_cases as ac, spd_cases as sc
from experiments.shape_continuation.forward import Work, solve
from ordered_boundary import sampled_self_intersection_count
from ordered_boundary.validation_cache import intersection_validation, validation_cache

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sc049_driver_check',HERE/'run.py')
driver=importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
driver.verify()
assert not (HERE/'postrun_checks.json').exists()
script_hash=sc.digest(Path(__file__))
sc.write(HERE/'postrun_check_manifest.json',dict(script_sha256=script_hash,
    scope='Read-only numerical verification of the recorded failed endpoint; no trajectory restart',
    field_unit_cap=4,wall_seconds_cap=120,geometry_grids=[512,1024,2048]))
started=time.perf_counter()
geometry=[]
for state in sc.read(HERE/'accepted.json')['states']:
    curve=ast.curve_from(state['curve'])
    for n in (512,1024,2048):
        counts={}
        for backend in ('reference','spatial'):
            with intersection_validation(backend):
                counts[backend]=sampled_self_intersection_count(curve.nodes(n).points)
        geometry.append(dict(iteration=state['iteration'],nodes=n,counts=counts,
                             identical=counts['reference']==counts['spatial']))
assert all(r['identical'] for r in geometry)

curve=ast.curve_from(sc.read(HERE/'result.json')['curve'])
catalog=ast.catalog_only('circle_to_c')
work=Work(max_forwards=4,max_seconds=120)
cpu,rows={},[]
os.environ['SC_FORWARD_BACKEND']='cpu'
with np.load(HERE/'final_atlas.npz') as saved:
    for n in (512,1024):
        for index in (2,18):
            o=catalog[index]
            with intersection_validation('reference'),validation_cache('cache'):
                result=solve(curve,o.wavenumber,ac.contrast(),o.acquisition,n,work=work)
            cpu[n,index]=result.prediction
            expected=saved[f'prediction_{n}'][index]
            error=float(np.linalg.norm(result.prediction-expected)/np.linalg.norm(expected))
            rows.append(dict(frequency_hz=ac.CATALOG_HZ[index],nodes=n,cpu_gpu_relative=error,backend=result.backend))
refinement=[dict(frequency_hz=ac.CATALOG_HZ[i],cpu_relative=float(
    np.linalg.norm(cpu[512,i]-cpu[1024,i])/np.linalg.norm(cpu[1024,i]))) for i in (2,18)]
assert sc.digest(Path(__file__))==script_hash
driver.verify()
sc.write(HERE/'postrun_checks.json',dict(passed=all(r['cpu_gpu_relative']<=1e-10 for r in rows),
    geometry=geometry,cpu_fields=rows,cpu_refinement=refinement,work=work.summary(),
    seconds=time.perf_counter()-started,script_sha256=script_hash))
print('POSTRUN',max(r['cpu_gpu_relative'] for r in rows),refinement,'units',work.attempted,flush=True)
