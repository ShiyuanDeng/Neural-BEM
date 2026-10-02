"""Continue the study by replaying only work-limited paths with a higher cap."""
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
    selected=[r for r in originals if r.get('reason')=='TRIAL_SOLVE_CAP']
    def run(record):
        command=[sys.executable,'-m','experiments.exploratory_continuation.run','continuation',
            '--scene',record['scene'],'--arm',record['arm'],'--work-cap','512']
        completed=subprocess.run(command,cwd=ROOT,env=dict(os.environ,PYTHONPATH=f'{ROOT}/solvers:{ROOT}'),check=True)
        return dict(scene=record['scene'],arm=record['arm'],returncode=completed.returncode)
    with ThreadPoolExecutor(4) as pool: rows=list(pool.map(run,selected))
    (OUTPUT/'cap_extension_campaign.json').write_text(json.dumps(dict(
        old_cap=160,new_cap=512,rows=rows,reused_original_endpoints=len(originals)-len(selected),
        reuse_reason='Completed/non-budget-stopped deterministic paths are independent of a larger unused cap; no cap value enters the update rule.',
        original_capped_attempt_work_charged_separately=True),indent=2)+'\n')


if __name__=='__main__':main()
