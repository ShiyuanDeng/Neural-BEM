"""Render original saved baseline/F split trajectories without rerunning physics."""
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT))
import run_fourier_topology_controller as driver
from sdf_inverse.topology_controller import TopologyFrame


def render(arm):
    source=(ROOT/'results/validation/topology/TOP-001E-controller-20260911/A/split'
            if arm=='baseline'else OUT/'controller/F/split')
    records=json.loads((source/'trajectory.json').read_text())
    frames=tuple(TopologyFrame(driver.deserialize_state(r['state']),r['loss'],r['label'],r['cycle'])for r in records)
    events=json.loads((source/'metrics.json').read_text())['events']
    path=OUT/'media'/arm
    path.mkdir(parents=True,exist_ok=False)
    driver.render_case(path,f'split / {arm}',driver.case_spec('split')[1],frames,events)
    return arm

if __name__=='__main__':
    with ProcessPoolExecutor(max_workers=2)as pool:list(pool.map(render,('baseline','selective')))
