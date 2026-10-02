"""Replay numerical-resolution failures at two explicit physics resolutions."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'results/exploratory_continuation'


def main():
    originals=[json.loads(p.read_text()) for p in (OUTPUT/'continuation').glob('scif_*/*.json')]
    selected=[r for r in originals if r.get('reason')=='NUMERICAL_FAILURE']
    def run(job):
        record,nodes=job
        folder='continuation_cap512'+(f'_n{nodes}' if nodes!=64 else '')
        result_path=OUTPUT/folder/record['arm']/f"{record['scene']}.json"
        command=[sys.executable,'-m','experiments.exploratory_continuation.run','continuation',
            '--scene',record['scene'],'--arm',record['arm'],'--work-cap','512','--nodes',str(nodes)]
        if not result_path.exists() or json.loads(result_path.read_text())['status']=='STARTED':
            subprocess.run(command,cwd=ROOT,env=dict(os.environ,PYTHONPATH=f'{ROOT}/solvers:{ROOT}'),check=True)
        result=json.loads(result_path.read_text())
        checks=[check for stage in result.get('stages',[]) for check in stage.get('acceptance_checks',[])]
        return dict(scene=record['scene'],arm=record['arm'],nodes=nodes,refined_nodes=2*nodes,
            status=result['status'],reason=result.get('reason'),
            maximum_trial_discrepancy=max((max(c['prediction_discrepancy']) for c in checks),default=None),
            numerical_obstructions=[c for c in checks if c.get('numerical_obstruction')],
            work=result['work'],endpoint=result.get('endpoint'))
    with ThreadPoolExecutor(4) as pool: rows=list(pool.map(run,[(r,n) for r in selected for n in (64,128)]))
    still_unresolved=[r for r in rows if r['nodes']==128 and r['status']=='HARD_STOP']
    with ThreadPoolExecutor(3) as pool: rows.extend(pool.map(run,[(r,256) for r in still_unresolved]))
    (OUTPUT/'resolution_diagnostic.json').write_text(json.dumps(dict(
        scope='Separate replay; N128/256 rows are not substituted into primary continuation comparison.',
        rows=rows),indent=2)+'\n')


if __name__=='__main__':main()
