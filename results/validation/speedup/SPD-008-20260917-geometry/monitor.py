"""File-only 55-second progress monitor; no repository/numerical imports."""
import json
from pathlib import Path
import time

root = Path(__file__).resolve().parent
started = time.monotonic()
while True:
    try:
        campaign = root/'campaign'
        if not (campaign/'execution_status.json').exists():
            log = root/'qualification.log'
            rows = log.read_text().splitlines() if log.exists() else []
            value = dict(phase='qualification',last=rows[-1] if rows else 'starting')
        else:
            status = json.loads((campaign/'execution_status.json').read_text())
            timings = json.loads((campaign/'timings.json').read_text()) if (campaign/'timings.json').exists() else []
            value = dict(phase='campaign',status=status['status'],completed_workers=len(timings))
            if timings:
                last = timings[-1]
                value['last_completed'] = {k:last[k] for k in ('arm','scene','seconds','recovered')}
            if status['status']=='IN_PROGRESS':
                label,scene = status['jobs'][len(timings)]
                path = campaign/(label+'_'+scene+'.log')
                lines = path.read_text().splitlines() if path.exists() else []
                value.update(current_worker=[label,scene],last=lines[-1] if lines else 'topology / startup')
            else:
                value['final_status'] = status
        print(json.dumps(value),flush=True)
        if value.get('status') in ('COMPLETE','STOPPED'):
            break
    except (OSError,ValueError,IndexError) as exc:
        print(json.dumps(dict(transient_read=str(exc))),flush=True)
    if time.monotonic()-started > 12600:
        break
    time.sleep(55)
