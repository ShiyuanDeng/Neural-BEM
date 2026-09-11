"""One additional future cohort, following completion of the five first shards."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import run_future_shards as scheduler

if __name__ == '__main__':
    for arm in scheduler.experiment.ARMS:
        assert not (scheduler.OUTPUT / 'comparison/cartesian' / arm / 'm0.001-s11').exists()
    record = dict(created_utc=datetime.now(timezone.utc).isoformat(), cohort=[.001,11], workers=1,
        scheduling='Original Cartesian worker is at 1e-4 seed 47; it will skip this completed cohort',
        launcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), wall_time_comparison=False)
    (scheduler.OUTPUT / 'additional_shards_2.json').write_text(json.dumps(record, indent=2)+'\n')
    scheduler.run_cohort((.001,11))
