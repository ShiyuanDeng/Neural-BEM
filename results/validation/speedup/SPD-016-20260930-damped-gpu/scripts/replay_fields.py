"""Fresh combined table-field arm, preserving baseline driver and output schema."""
import json
import sys
import time
from pathlib import Path
from experiments.modal_atlas import damped_screen as ds
from runtime import install
from field_runtime import install_fields

contrast,scene,destination=float(sys.argv[1]),sys.argv[2],Path(sys.argv[3])
install()
_,_,counters=install_fields()
target=destination/'fields/D'/ds.tag(contrast)/scene
if target.exists():
    raise FileExistsError(target)
started=time.perf_counter()
row=ds.attempt('D',contrast,scene,root=destination/'fields')
(target/'field_counters.json').write_text(json.dumps(counters,indent=2)+'\n')
print('WALL_SECONDS',time.perf_counter()-started,flush=True)
if row['outcome']=='EXCEPTION':
    raise RuntimeError(row['traceback'])
assert counters['table_calls']>0
print('SUMMARY',json.dumps(dict(mode='fields',contrast=contrast,scene=scene,outcome=row['outcome'],
      recovered=row['recovered'],metrics=row['metrics'],units=row['fit_and_localization_units'],
      seconds=row['seconds'],counters=counters)),flush=True)
